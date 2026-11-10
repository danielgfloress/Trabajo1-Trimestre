# Informe técnico · Sneaker Factory · Ciencia de datos y dashboard

Módulo de Ampliación de Python · 2.º DAM. Cifras calculadas sobre la exportación de ACC del 09/11/2026 (12 pedidos de prueba de `05_datos.sql`) y sobre el histórico sintético con semilla 42. Todas se pueden regenerar con `python main.py` y `python main.py --modo sintetico`.

## 1. Objetivo y alcance

Construir un proceso reproducible que convierta las exportaciones CSV de Acceso a Datos (PostgreSQL) en indicadores verificables, con un dashboard que se recalcula cada 60 s. Se separan siempre tres cosas: **datos reales** (ACC), **datos simulados** (generador propio) y **predicciones**.

Fuera del alcance, como indica el enunciado: conexión directa a PostgreSQL, API REST e interfaz web propia. La única entrada son los CSV.

## 2. Arquitectura

```
scripts/exportar_acc.sh ─▶ entrada_acc/ ─▶ pipeline.py ─▶ analiticas.py ─┬─▶ segmentacion.py / prediccion.py
                                           (carga y                       ├─▶ visualizaciones.py
                                            validación)                   ├─▶ main.py (consola) ─▶ outputs/
                                                                          └─▶ refresco.py ─▶ app_dashboard.py
generador_datos.py ─▶ datos_sinteticos/ ─▶ (mismo pipeline, rotulado SINTÉTICO)
```

- `app_dashboard.py` y `main.py` solo orquestan: llaman a **las mismas funciones**, así que no hay dos fórmulas para un mismo KPI.
- `pipeline.py`, `analiticas.py`, `segmentacion.py`, `prediccion.py` y `refresco.py` no importan Streamlit: se prueban con pytest.
- Reglas, umbrales, rutas y semilla están en `config.py`. Las carpetas de entrada y logs se pueden cambiar con las variables `SNEAKER_ENTRADA` y `SNEAKER_LOGS`.

## 3. Contrato de datos y ETL

Contrato completo en `docs/diccionario_datos.md`. Resumen:

| CSV | Clave | Uso |
|---|---|---|
| `clientes.csv` | `id_cliente` | comprador y tipo (CLUB, EQUIPO, PARTICULAR) |
| `modelos.csv` | `id_modelo` | catálogo, categoría y precio base |
| `pedidos.csv` | `id_pedido` | fecha, cliente, tipo (ESTANDAR/CUSTOM), estado, importe |
| `lineas_pedido.csv` | `id_linea` | modelo, color, talla, cantidad, precio, subtotal |
| `stock.csv` | `id_modelo + color + talla` | foto del almacén en la fecha de corte |

**Exportación.** `\copy (SELECT …) TO STDOUT` dentro del contenedor. La línea no tiene `id_modelo` en la base de datos; se obtiene uniendo `lineas_pedido → almacen`. Cada fichero se escribe como `.tmp` y se renombra al terminar.

**Carga** (`pipeline.cargar_tablas`):
- todo se lee como texto (`dtype=str`), así los ID nunca se convierten en números con los que se pueda operar;
- se comprueba que el fichero existe, que no está vacío y que tiene las columnas obligatorias;
- se genera un **manifiesto** con fichero, fecha de análisis, filas, columnas, bytes y fecha de modificación.

**Conversión de tipos** (`convertir_tipos`): `pd.to_numeric(errors="coerce")` y `pd.to_datetime(format=…, errors="coerce")` con formato explícito. Lo que no se puede convertir queda nulo y lo detecta una regla de calidad; **nunca se pone 0** en su lugar.

**Los CSV de entrada no se modifican nunca.** Las pruebas trabajan siempre con copias.

## 4. Reglas de calidad

Cada incidencia registra tabla, registro, regla, gravedad y tratamiento (`incidencias.csv`). `resumen_calidad.csv` da, por tabla, las filas de entrada, válidas y rechazadas, el % de calidad y el número de incidencias.

| # | Regla | Gravedad | Tratamiento |
|---|---|---|---|
| 01 | fichero inexistente, vacío o sin columnas obligatorias | bloqueante | no se publica nada |
| 02 | ID duplicado (cliente, modelo, pedido, línea, códigos Odoo) | recuperable | se conserva la primera aparición |
| 03 | clave huérfana (línea→pedido, línea→modelo, pedido→cliente, stock→modelo) | bloqueante | no se publica: un cruce incompleto falsearía los totales |
| 04 | fecha nula o imposible | recuperable | se rechaza el pedido y sus líneas |
| 05 | cantidad nula, cero o negativa | recuperable | se rechaza la línea |
| 06 | precio no numérico o negativo | recuperable | se rechaza la línea |
| 07 | estado o tipo fuera de catálogo | recuperable | se rechaza el pedido |
| 08 | talla fuera de 36-46 | recuperable | se rechaza la línea o la fila de stock |
| 09 | pedido sin cliente o línea sin modelo | recuperable | se rechaza |
| 10 | mismo pedido, modelo, color y talla repetidos | advertencia | se conservan y se suman (pueden ser legítimas) |
| 11 | stock negativo o duplicado por modelo-color-talla | recuperable | se rechaza la fila |
| 12 | subtotal ≠ cantidad × precio, total ≠ suma de líneas, pedido posterior al corte, pedido sin líneas | advertencia | se usa cantidad × precio; el pedido cuenta en actividad |

**Bloqueante** frente a **recuperable**: se bloquea cuando el problema impide confiar en cualquier cifra (falta un fichero o una relación). Se recupera cuando el error afecta a registros concretos que se pueden apartar sin contaminar el resto.

Datos reales del 09/11/2026: 740 filas de entrada, 740 válidas, **0 incidencias**. La copia sintética con 11 errores introducidos hace saltar las 11 reglas esperadas (`test_copia_con_incidencias_se_detecta`).

## 5. Integración relacional

`lineas_enriquecidas` une líneas con pedidos, modelos y clientes usando `merge(..., how="left", validate="many_to_one")`. Si un modelo o un cliente estuviera repetido, pandas lanza `MergeError` en vez de multiplicar filas en silencio (`test_cardinalidad_del_merge`). El resultado tiene exactamente las mismas filas que las líneas (25).

`pedidos_unicos` agrupa las líneas por `id_pedido` (pares, importe, nº de líneas, nº de modelos) y las une 1:1 con los pedidos (`validate="one_to_one"`). **Por qué un pedido con tres líneas no son tres pedidos:** SO010 tiene 5 líneas (tallas 40 a 44) y es una sola venta de 3.999,80 €. Contar líneas daría 25 «pedidos» en vez de 12 y un ticket medio de 643,84 € en vez de 1.609,61 €.

## 6. Conciliación con SQL

Al exportar, `reconciliacion_sql.csv` guarda las mismas cifras calculadas en PostgreSQL. `analiticas.reconciliacion_sql` las cruza con pandas (`merge` *outer*, `validate="one_to_one"`) y marca **CUADRA** si la diferencia es ≤ 0,01, o **DESCUADRE** en caso contrario (también si una métrica existe solo en SQL). Siempre se compara **sin filtros**.

| Métrica | pandas | SQL | Estado |
|---|---|---|---|
| pedidos válidos | 8 | 8 | CUADRA |
| pares vendidos | 96 | 96 | CUADRA |
| ingresos válidos | 12.876,88 | 12.876,88 | CUADRA |
| clientes con compra | 5 | 5 | CUADRA |
| líneas totales | 25 | 25 | CUADRA |
| ingresos de cada mes (4) | 06: 3.847,81 · 07: 3.169,37 · 08: 239,98 · 09: 5.619,72 | ídem | CUADRA |
| pares de cada modelo y talla (18 combinaciones) | — | — | CUADRA |

**27 de 27 cifras cuadran** (casos E y N). `test_caso_n_reconciliacion_detecta_descuadres` comprueba que un valor distinto sí se marca como descuadre.

## 7. Indicadores (KPIs)

Definiciones fijadas en `config.py`:
- **Venta válida** = `CONFIRMADO` o `ENTREGADO`. El ingreso se reconoce en la fecha del pedido.
- Importes con IVA y sin coste: **no se calcula margen** (`precio_y_margen` = «NO CALCULABLE»).
- Redondeo a 2 decimales solo al presentar.

| Indicador | Fórmula | Real |
|---|---|---|
| Pedidos únicos (actividad) | nº de `id_pedido`, todos los estados | 12 |
| Pedidos por estado | conteo | 2 borradores, 3 confirmados, 5 entregados, 2 cancelados |
| Pedidos válidos | estado ∈ {CONFIRMADO, ENTREGADO} | 8 |
| Pares vendidos | Σ cantidad de líneas de pedidos válidos | 96 |
| Ingresos válidos | Σ cantidad × precio de líneas de pedidos válidos | 12.876,88 € |
| Ticket medio | ingresos ÷ pedidos válidos | 1.609,61 € |
| Pares por pedido | pares ÷ pedidos válidos | 12,0 |
| Peso Custom | Custom ÷ total, en pedidos / pares / ingresos | 37,5 % / 62,5 % / 64,7 % |
| Top modelo, talla y cliente | máximo de la suma agrupada | Runner X (24 pares) · talla 42 (28) · CLI005 (4.929 €) |
| Variación mensual | (mes − mes anterior) ÷ mes anterior | septiembre +2.241,8 % sobre agosto (agosto tuvo 1 pedido) |
| Concentración Pareto | peso del 20 % de modelos con más ingresos | 54,6 % (2 de 8 modelos) |
| Cobertura | stock ÷ (pares de 28 días ÷ 4), en semanas | N/D: no hubo ventas en los 28 días anteriores al corte |

Con filtros, cada KPI se calcula sobre el subconjunto y el dashboard indica el denominador.

## 8. DataFrames analíticos

Todos son funciones de `analiticas.py` que devuelven un DataFrame con metadatos en `df.attrs`: función, filas de origen, fecha de corte y filtros.

| DataFrame | Expresión principal |
|---|---|
| 01 pedidos únicos | `groupby("id_pedido").agg(...)` + `merge(validate="one_to_one")` |
| 02 ventas por periodo | `groupby("mes")`, `reindex(period_range)`, `pct_change()`, `shift(1).rolling(3).mean()` |
| 03 modelos ABC | `sort_values`, `cumsum`, `pd.cut(acumulado previo, [80, 95])` |
| 04 matriz modelo × talla | `pivot_table(aggfunc="sum")` y `div(sum(axis=1))` para el % dentro del modelo |
| 05 Custom frente a estándar | `groupby("tipo")`, separando tasa de cancelación (pedidos) y cuota de ingresos (€) |
| 06 clientes RFM | `groupby("id_cliente")`, `nunique` de pedidos, `merge` con todos los clientes |
| 07 cohortes | `transform("min")` del mes de primera compra y `pivot_table(aggfunc="nunique")` |
| 08 stock y cobertura | `merge` stock-demanda de 28 días, `np.where` para N/D |
| 09 calidad | resumen por tabla, incidencias por regla, tasa de integridad |
| 10 anomalías | `quantile` y regla IQR por categoría (o global si hay pocas filas) |
| 11 precio y margen | «NO CALCULABLE» (no hay coste) |
| 12 reconciliación SQL | `merge` *outer* + `np.select` |

Además: `caracteristicas_clientes`, `demanda_modelo_mes`, `talla_mas_solicitada`, `estadistica_descriptiva`, `estadistica_por_grupo`, `hipotesis` y los de clustering y predicción.

## 9. Ingeniería de características

Se han creado 16 variables (detalle, unidad y disponibilidad temporal en el diccionario). **Calendario:** año, trimestre, día de la semana, antigüedad. **Economía:** importe de línea, precio medio por par. **Comportamiento:** frecuencia, % Custom, intervalo medio entre compras. **Demanda:** unidades por modelo y mes, mes anterior, media de los 3 meses previos, mes del año. **Operaciones:** talla más pedida, alerta de stock, cobertura.

La media de 3 meses se calcula con `shift(1).rolling(3)`: **no incluye el mes que se predice**. Lo comprueba `test_media_3_meses_previos_no_usa_el_mes_actual`.

## 10. Análisis exploratorio

| Variable (pedidos válidos) | n | media | mediana | desv. típica | IQR | estadístico representativo |
|---|---|---|---|---|---|---|
| importe por pedido | 8 | 1.609,61 € | 1.619,87 € | 1.246,51 € | 1.376,28 € | media (simétrica) |
| pares por pedido | 8 | 12,0 | 13,0 | 8,37 | 14,25 | media; moda 20 (mínimo Custom) |
| precio por par | 20 líneas | 147,52 € | 124,99 € | 49,38 € | 95,09 € | **mediana** (asimétrica) |
| pares por línea | 20 líneas | 4,8 | 4,0 | 2,38 | 3,0 | mediana |

Regla de elección: si |media − mediana| / mediana > 10 %, la distribución se considera asimétrica y se usa la mediana. La moda solo se da en variables discretas que se repiten. **Todas tienen n < 30: describen, pero no permiten generalizar.**

**Atípicos (IQR × 1,5 por categoría):** solo una línea, SO003 con 8 pares en una talla (límite 6,62). Es legítima: un pedido Custom de un club. Se conserva y se marca; no se borra ninguna anomalía de forma automática.

Gráficos (`outputs/*/graficos/`): serie mensual, ranking, Pareto, histograma, boxplot, mapa de calor, dispersión, comparativa por tipo, grupos KMeans, predicción y alertas de stock.

## 11. Hipótesis e incertidumbre

Se plantearon antes de mirar los resultados y se contrastan con un **intervalo de confianza del 95 % por bootstrap**: 2.000 remuestras con reemplazo, semilla 42 y percentiles 2,5 y 97,5. Se apoya si todo el intervalo está por encima de la referencia; hay evidencia insuficiente si la cruza.

| Hipótesis | Real: observado · IC 95 % · conclusión | Sintético: observado · IC 95 % · conclusión |
|---|---|---|
| H1 · un pedido Custom factura de media más que uno estándar | +1.871,34 € · [849; 3.058] · **se apoya** | +3.968,94 € · [3.639; 4.318] · se apoya |
| H2 · las tallas 40-42 son más de la mitad de los pares | 69,8 % · [45,5; 90,6] · **evidencia insuficiente** | 53,6 % · [49,9; 57,0] · evidencia insuficiente |
| H3 · los Custom se cancelan más que los estándar | +12,5 puntos · [−25; 62,5] · **evidencia insuficiente** | +10,9 puntos · [3,8; 18,6] · se apoya (solo en la simulación) |

**Lo que NO se puede afirmar:**
- que ser Custom **cause** el mayor importe: los Custom exigen 20 pares o más, así que la diferencia viene del volumen;
- que la mezcla de tallas valga para otros clientes: casi todos los pares vienen de 3-4 clubes;
- nada sobre cancelaciones con datos reales: con 4 pedidos Custom, una sola cancelación cambia la tasa del 0 al 25 %;
- el resultado sintético de H3 **no es evidencia**: refleja la regla de simulación S9 (14 % frente a 8 %) que pusimos nosotros.

## 12. Segmentación de clientes

**RFM** (una fila por cliente; fecha de referencia = corte de la exportación; frecuencia = pedidos válidos distintos, nunca líneas; monetario = ingresos válidos):

| Segmento | Regla | Real |
|---|---|---|
| Sin compras válidas | ningún pedido confirmado o entregado | 2 (CLI003, CLI007) |
| En riesgo | más de 120 días sin comprar | 1 (CLI006) |
| Campeón | 2 compras o más y ≤ 60 días | 1 (CLI005) |
| Leal | 2 compras o más | 2 (CLI001, CLI002) |
| Nuevo / reciente | 1 compra en ≤ 60 días | 0 |
| Ocasional | el resto | 1 (CLI004) |

Caso F: CLI002 tiene 2 compras (SO001 con 2 líneas y SO005 con 3), no 5.

**KMeans** (`segmentacion.py`):
- variables: recencia, log(1 + frecuencia) y log(1 + gasto), escaladas con `StandardScaler` (sin escalar, el gasto dominaría);
- se prueban k = 2 a 5 con `n_init=10` y `random_state=42`, y se elige el mayor *silhouette*;
- con **datos reales: NO CALCULABLE**, porque hay 5 compradores y el mínimo es 20 (caso J);
- con **datos sintéticos (45 clientes):** silhouette 0,398 (k=2), 0,374 (k=3), 0,387 (k=4) y 0,385 (k=5), así que se elige **k = 2**. Salen «Frecuentes, alto gasto, activos» (26 clientes, 89,3 % de los ingresos) y «Ocasionales, bajo gasto, alejados» (19 clientes, 10,7 %). Los nombres se ponen comparando las medianas de cada grupo con las globales.

**KMeans frente a RFM:** 10 clientes que RFM llama «Campeón» caen en el grupo de ocasionales. Un grupo matemático junta clientes parecidos en números; una categoría comercial aplica umbrales de negocio. Además, los umbrales RFM están pensados para el volumen real (1-2 compras): en el sintético, 35 de 45 clientes son «Campeón», así que esos umbrales no discriminan allí.

## 13. Predicción de demanda

- **Objetivo:** pares de cada modelo en el mes objetivo (`unidades_modelo_mes`). Los meses sin ventas cuentan como 0.
- **Predictores, todos disponibles antes del mes:** demanda del mes anterior, media de los 3 meses previos, mes del año y modelo (*one-hot*).
- **Baseline:** repetir la demanda del mes anterior.
- **Modelo:** `RandomForestRegressor` (300 árboles, profundidad máxima 6, mínimo 3 muestras por hoja, semilla 42). Capta la temporada y las diferencias entre modelos sin forma fija; la profundidad y la hoja mínima limitan el sobreajuste con pocas filas.
- **Validación temporal:** entrena con 2025-04 a 2026-03 (168 filas) y evalúa con los **3 últimos meses**, 2026-04 a 2026-06 (42 filas). Nunca se separa al azar (`test_no_se_entrena_con_los_meses_de_prueba`).

| Método | MAE | RMSE | Sesgo |
|---|---|---|---|
| Baseline (mes anterior) | 31,83 pares | 46,07 | +2,36 |
| RandomForest | **23,50 pares** | **33,39** | **−9,73** |

**Lectura:** el modelo reduce el MAE un 26,2 % y gana en 11 de 14 modelos. Pero **subestima** de forma sistemática (sesgo −9,7 pares por modelo y mes): un bosque de árboles no extrapola por encima de lo que ha visto, y el sintético crece un 1,5 % al mes. Por eso, sumando todos los modelos, la referencia se acerca más al total mensual en el gráfico. La variable con más peso es la media de 3 meses (57 %).

**Con datos reales: NO CALCULABLE.** Hay 1 mes con historial completo y hacen falta 9. Nada de este apartado es una previsión real.

## 14. Datos sintéticos

`generador_datos.py`: 900 pedidos, 1.775 líneas, 45 clientes, 14 modelos y 18 meses (01/2025-06/2026), con semilla 42. Respeta las reglas de negocio: claves válidas, Custom ≥ 20 pares con recargo, importes = suma de líneas, estados según antigüedad. Sigue las hipótesis S1-S10 del diccionario (concentración de clientes, estacionalidad general y por categoría, popularidad, curva de tallas...). No pretende representar la demanda real. La copia `con_incidencias/` introduce 11 errores, uno por regla. Misma semilla → mismos CSV (`test_misma_semilla_mismos_datos`).

## 15. Dashboard y refresco

Seis vistas: Dirección, Producto y ventas, Clientes, Almacén, Calidad y auditoría, y Laboratorio (sintético). Filtros transversales: periodo, modelo, talla, tipo, estado, cliente y umbral de stock. Hay 7 descargas CSV filtradas y una tabla de datos debajo de cada gráfico.

Cada 60 s (`st.fragment(run_every="60s")`), o al pulsar «Actualizar ahora», `refresco.ciclo()`:

1. registra la hora y calcula una huella MD5 del contenido de los 5 CSV;
2. ejecuta el pipeline completo (lectura, validación y cruces);
3. vuelve a calcular la huella; si cambió durante la lectura, la exportación está en curso y no se publica;
4. si los datos son válidos, recalcula **todos** los DataFrames con esa versión y publica un único resultado. El estado es «correcto» si la huella es nueva y «sin cambios» si es la misma (se recalcula igualmente, sin caché);
5. si no son válidos («datos inválidos» o «error de carga»), no publica: muestra el último resultado válido rotulado **DESACTUALIZADO**, con su hora original y el motivo;
6. escribe una línea en `logs/refresco.log` (fecha, origen, estado, filas, duración, huella y motivo), sin credenciales.

Los filtros y la vista se guardan en `st.session_state`, así que sobreviven al refresco. El laboratorio sintético se recalcula solo cuando cambia la huella de sus CSV.

## 16. Pruebas

**53 pruebas automáticas** (`pytest`, unos 70 s), siempre sobre copias de `tests/datos/`.

| Categoría del enunciado | Pruebas |
|---|---|
| Carga / esquema | ruta inexistente, CSV vacío, columna ausente, fecha corrupta |
| Integridad | ID huérfano, duplicado (conserva sus líneas), cardinalidad del merge, cantidad negativa, caso D (3 alertas sin tocar el original) |
| Cálculo | cancelados excluidos, pedido multilínea = 1 pedido, ticket entre pedidos, cifras SQL, RFM por pedidos (caso F), filtros, variables derivadas, estadística, hipótesis, reconciliación (caso N) |
| Reproducibilidad | misma semilla en el bootstrap, el generador, el clustering y la predicción |
| ML / temporalidad | no se entrena con meses de prueba, ninguna variable usa datos futuros, baseline = mes anterior, datos insuficientes (caso J) |
| Generador | mínimos del enunciado, reglas de negocio, datos limpios sin incidencias, la copia con errores dispara las 11 reglas |
| Consola | ejecución completa (CSV, PNG, origen, sin nombres, log), datos inválidos no publican, filtros |
| Refresco | correcto, R5 sin cambios con 3 ciclos registrados, R1 pedido nuevo, R4 CSV defectuoso → desactualizado, caso M recuperación, huérfana sin resultado previo, CSV que cambia durante la lectura |
| Dashboard | las 6 vistas sin errores, KPIs y descargas, R6 filtro persistente, CSV defectuoso → DESACTUALIZADO |

Las pruebas con la base de datos real (casos A, C, L, R1-R3 y K, con capturas antes y después) se describen en `docs/guia_pruebas_integracion.md`.

## 17. Limitaciones y sesgos

- **Muestra real muy pequeña:** 12 pedidos, 8 válidos, 5 clientes compradores y 4 meses. Las cifras describen la situación, pero no permiten inferir tendencias ni estacionalidad reales.
- **Concentración:** 3 pedidos Custom generan el 64,7 % de los ingresos. Cualquier cambio en uno de ellos mueve todos los indicadores.
- **Stock = foto del corte**, no un histórico. No se pueden reconstruir roturas pasadas.
- **Datos de prueba:** los pedidos de ACC son datos de demostración, no ventas reales de una empresa.
- **Zona horaria:** la base de datos trabaja en UTC (una hora menos que España). Afecta a la hora mostrada del corte, no a los cálculos, porque pedidos y corte usan el mismo reloj.
- **El sintético no es evidencia:** refleja las reglas S1-S10 que lo generan. Sus resultados de clustering, H3 y predicción solo demuestran que el método funciona.
- **Predicción:** sesgo negativo por no extrapolar la tendencia. Antes de usarla en producción habría que añadir tendencia o probar un modelo lineal con más meses reales.
