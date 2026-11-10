# Sneaker Factory · Ciencia de datos y dashboard (Ampliación de Python)

Pipeline reproducible en Python que lee las exportaciones CSV de Acceso a Datos (PostgreSQL), las valida, calcula los indicadores del negocio y los muestra en un dashboard de Streamlit que se recalcula cada 60 segundos. Incluye un histórico **sintético**, siempre separado de los datos reales, para la segmentación de clientes y la predicción de demanda.

```
PostgreSQL ──scripts/exportar_acc.sh──▶ entrada_acc/*.csv ──▶ pipeline.py ──▶ analiticas.py ──┬─▶ main.py         → outputs/
                                                                                              └─▶ app_dashboard.py → navegador
```

Python no se conecta a la base de datos ni a la API: su única entrada son los CSV.

---

## 1. Instalación

Requisitos: Python 3.12 o superior. Para exportar datos nuevos, además, Docker con el contenedor `d3kicks-db` en marcha y Git Bash.

```powershell
cd python
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Si PowerShell no deja activar el entorno: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` (una sola vez).

Las versiones están fijadas en `requirements.txt`: pandas, NumPy, Matplotlib, scikit-learn, Streamlit y pytest.

## 2. Estructura

| Ruta | Qué es |
|---|---|
| `app_dashboard.py` | dashboard Streamlit (solo orquesta y muestra) |
| `main.py` | ejecución por consola |
| `pipeline.py` | carga, control de esquema, 12 reglas de calidad, incidencias, log |
| `analiticas.py` | todos los DataFrames y KPIs (no importa Streamlit) |
| `visualizaciones.py` | los 11 gráficos (Matplotlib) |
| `segmentacion.py` | KMeans de clientes |
| `prediccion.py` | predicción de demanda, baseline y validación temporal |
| `refresco.py` | ciclo de refresco de 60 s (huella, estados, último resultado válido) |
| `generador_datos.py` | histórico sintético (semilla fija) y copia con incidencias |
| `config.py` | estados, reglas, umbrales, rutas y semilla |
| `scripts/exportar_acc.sh` | exporta los CSV desde PostgreSQL |
| `entrada_acc/` | CSV **reales** exportados por ACC |
| `datos_sinteticos/` | CSV **sintéticos** (y `con_incidencias/`) |
| `outputs/real/`, `outputs/sintetico/` | resultados: 15 CSV + 11 PNG por modo |
| `logs/` | `ejecuciones.log` (consola) y `refresco.log` (dashboard) |
| `tests/` | 53 pruebas automáticas (pytest) con datos fijos en `tests/datos/` |
| `docs/` | diccionario de datos, informes y guía de pruebas de integración |

## 3. Importar los CSV desde Acceso a Datos

Con Docker en marcha, desde la raíz del repositorio:

```powershell
bash python/scripts/exportar_acc.sh
```

Lee las credenciales del `.env` de la raíz (no se sube al repositorio) y ejecuta `\copy` dentro del contenedor. Escribe primero un `.csv.tmp` y lo renombra al terminar, así nunca se lee un fichero a medias. Genera:

| CSV | Contenido |
|---|---|
| `clientes.csv`, `modelos.csv`, `pedidos.csv`, `lineas_pedido.csv`, `stock.csv` | los 5 conjuntos del contrato |
| `reconciliacion_sql.csv` | las mismas cifras calculadas en SQL para contrastarlas con pandas: pedidos, pares, ingresos, clientes, líneas, ingresos de cada mes y pares de cada modelo y talla |

**Importante:** meter un pedido en PostgreSQL no cambia nada en Python hasta que se vuelve a ejecutar este script.

## 4. Contrato de datos y diccionario

Columnas, tipos, valores permitidos, nulos, formato (UTF-8, coma, punto decimal, `YYYY-MM-DD HH:MM:SS`, `true`/`false`), variables derivadas e hipótesis del sintético: **[docs/diccionario_datos.md](docs/diccionario_datos.md)**.

Reglas de negocio (en `config.py`):

- **Venta válida** = pedido `CONFIRMADO` o `ENTREGADO`. El ingreso se reconoce en la fecha del pedido.
- `BORRADOR` = pendiente; `CANCELADO` = no cuenta como venta. Ambos siguen en la «actividad».
- Ticket medio y pares por pedido se dividen entre **pedidos**, nunca entre líneas.
- No hay coste en los datos: **no se calcula margen** («NO CALCULABLE»).

## 5. Ejecución por consola

```powershell
python main.py                       # modo real: entrada_acc/ → outputs/real/
python main.py --modo sintetico      # datos_sinteticos/ → outputs/sintetico/
python main.py --help                # todas las opciones
```

| Opción | Uso |
|---|---|
| `--tarea` | `calidad`, `descriptivo`, `segmentacion`, `prediccion`, `graficos` o `todo` (por defecto) |
| `--entrada`, `--salida` | otras carpetas |
| `--desde`, `--hasta` | periodo `AAAA-MM-DD` |
| `--modelos D3-001 NIK-022` | por código de modelo |
| `--tallas 40 41` | por talla |
| `--tipos CUSTOM` | `ESTANDAR` / `CUSTOM` |
| `--estados CONFIRMADO` | por estado |
| `--clientes CLI001` | por código de cliente |
| `--umbral-stock 10` | alerta de stock con un umbral fijo (si no, el stock mínimo de ACC) |

Si los datos tienen errores bloqueantes, guarda solo la calidad (`resumen_calidad`, `incidencias`, `manifiesto_origen`), explica el motivo y termina con código 1. Cada ejecución añade una línea a `logs/ejecuciones.log`.

**Salidas (15 CSV + 11 PNG por modo).** Cada CSV lleva las columnas `origen`, `generado` y `filtros`, y ninguno incluye nombres de clientes. Calidad: `resumen_calidad`, `incidencias`, `manifiesto_origen`, `auditoria_reconciliacion_sql`. Descriptivo: `kpis`, `pedidos_unicos`, `evolucion_mensual`, `modelos_abc`, `matriz_modelo_talla`, `stock_cobertura`. Segmentación: `clientes_rfm`, `cohortes`, `clustering_clientes`. Predicción: `prediccion_evaluacion`, `prediccion_detalle`. Gráficos en `graficos/`.

**Regenerar los resultados:** `outputs/` se puede borrar entero; `python main.py` y `python main.py --modo sintetico` lo vuelven a crear igual (salvo la hora de `generado`). Los resultados no se editan a mano.

## 6. Dashboard

```powershell
streamlit run app_dashboard.py
```

Se abre en `http://localhost:8501`. Arranca siempre con los datos **reales** de ACC.

| Vista | Contenido |
|---|---|
| Dirección | ingresos, pares, pedidos y ticket; último mes frente al anterior; pedidos por estado; peso Custom; serie mensual |
| Producto y ventas | ranking y Pareto ABC, mapa de calor modelo × talla, Custom frente a estándar |
| Clientes | segmentos RFM con sus reglas, tabla filtrable, dispersión, cohortes, KMeans (o «no calculable») |
| Almacén | aviso de foto de stock, alertas bajo umbral, cobertura en semanas (N/D si no hay demanda) |
| Calidad y auditoría | semáforo por tabla, incidencias, huérfanas, conciliación con SQL, manifiesto, atípicos |
| Laboratorio (sintético) | KMeans y predicción con el histórico sintético, rotulado como tal |

**Filtros** (barra izquierda, combinables): periodo, modelo, talla, tipo, estado, cliente y umbral de stock. Un filtro vacío no restringe. «Restablecer filtros» los quita todos. Los filtros de modelo y talla reducen cada pedido a esas líneas, así que el denominador de los KPIs cambia; cada vista lo indica.

**Descargas:** desplegable «⬇ Descargar resultados» con 7 CSV filtrados (los mismos que genera `main.py`).

Debajo de cada gráfico, «Ver los datos del gráfico» muestra la tabla de la que sale.

## 7. Real frente a sintético

| | Real | Sintético |
|---|---|---|
| Origen | `entrada_acc/` (exportación de PostgreSQL) | `datos_sinteticos/` (`python generador_datos.py`) |
| Rótulo | `ACC · REAL` | `SINTÉTICO · generador_datos.py` |
| Códigos | `CLI001`, `SO001`, `D3-001`… | `SCLI001`, `SSO0001`, `SIM-01`… |
| Dónde se ve | todas las vistas del dashboard, `outputs/real/` | solo «Laboratorio (sintético)», `outputs/sintetico/` |

Nunca se mezclan. Con los datos reales (12 pedidos, 5 clientes compradores, 4 meses), el clustering y la predicción salen como **NO CALCULABLE** con su motivo. Se demuestran con el sintético y nunca se presentan como conclusiones de negocio.

```powershell
python generador_datos.py                # semilla 42 → siempre los mismos CSV
python generador_datos.py --semilla 7    # otro histórico
```

## 8. Actualización automática cada 60 s

El panel está dentro de `st.fragment(run_every="60s")`. En cada ciclo, o al pulsar «Actualizar ahora», `refresco.ciclo()`:

1. apunta la hora de comprobación y calcula una **huella** (MD5) del contenido de los 5 CSV;
2. lee y valida los datos sin modificarlos;
3. vuelve a calcular la huella: si ha cambiado durante la lectura (exportación a medias), no publica;
4. si todo es válido, recalcula **todos** los DataFrames a partir de esa misma versión y los publica juntos;
5. escribe una línea en `logs/refresco.log`: fecha, origen, estado, filas, duración, huella y motivo.

Estados: 🟢 **correcto** (datos nuevos) · 🟢 **sin cambios** (mismos CSV, recalculado igualmente) · 🔴 **datos inválidos** · 🔴 **error de carga**.

Los filtros y la vista elegida se conservan entre ciclos. **Recalcular cada 60 s no es lo mismo que tener datos nuevos:** si ACC no exporta, las cifras no cambian; solo cambian la hora de comprobación y el log.

## 9. Probar con datos nuevos

1. Con el dashboard abierto, mete o modifica un pedido en PostgreSQL. Los comandos SQL están en [docs/guia_pruebas_integracion.md](docs/guia_pruebas_integracion.md).
2. Exporta: `bash python/scripts/exportar_acc.sh`.
3. En el siguiente ciclo, o al pulsar «Actualizar ahora», el estado pasa a «correcto» y los KPIs cambian. La conciliación con SQL debe seguir en 🟢.

## 10. Recuperación tras un CSV erróneo

Si llega un CSV vacío, sin una columna obligatoria o con una relación huérfana:

- el dashboard **no publica** cálculos parciales;
- muestra en rojo **«DATOS DESACTUALIZADOS»**, con el motivo y la hora del último resultado válido, que sigue visible;
- la vista «Calidad y auditoría» y `logs/refresco.log` dicen qué fichero y qué regla fallaron.

Para recuperarse, basta con volver a exportar (`bash python/scripts/exportar_acc.sh`). En el siguiente ciclo el estado vuelve a «correcto», sin reiniciar la app. Si se arranca con datos inválidos, no se muestra ninguna cifra hasta que se arreglen.

## 11. Pruebas automáticas

```powershell
pytest
```

53 pruebas, en aproximadamente 1 minuto: carga y esquema, integridad, cálculos y KPIs, reconciliación, generador sintético, segmentación, predicción (sin entrenar con los meses de prueba ni usar datos futuros), consola, refresco y dashboard. Usan copias de `tests/datos/`, así que nunca modifican `entrada_acc/` ni `logs/`.

## 12. Documentación

- [docs/diccionario_datos.md](docs/diccionario_datos.md): contrato, variables derivadas e hipótesis del sintético.
- [docs/informe_tecnico.md](docs/informe_tecnico.md): método, calidad, fórmulas, conciliación, estadística, modelos, refresco, pruebas y limitaciones.
- [docs/informe_ejecutivo.md](docs/informe_ejecutivo.md): cinco decisiones para producción y comercial.
- [docs/guia_pruebas_integracion.md](docs/guia_pruebas_integracion.md): pasos de las pruebas A–O y R1–R6 con Docker.
