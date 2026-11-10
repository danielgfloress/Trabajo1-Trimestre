# Informe ejecutivo · Sneaker Factory

Para: dirección, producción y comercial. Datos: exportación de Acceso a Datos del 09/11/2026 (pedidos de junio a octubre de 2026). Salvo que se indique, todas las cifras son **reales** (ACC) y se pueden comprobar en el dashboard y en `outputs/real/`.

## Situación en una línea

**12.876,88 € en ventas válidas**: 8 pedidos confirmados o entregados y 96 pares, con un ticket medio de 1.609,61 €. Hay además 2 borradores pendientes (1.109,95 €) y 2 cancelados. Las cifras cuadran al céntimo con PostgreSQL (27 de 27 comprobaciones).

> **Aviso sobre la muestra:** son 12 pedidos de 7 clientes en 4 meses. Sirven para decidir prioridades inmediatas, no para hablar de tendencias. Las cifras pueden cambiar mucho con un solo pedido nuevo.

---

## Las 5 decisiones, por prioridad

### 1. Volcar el esfuerzo comercial en pedidos Custom para clubes y equipos

| | |
|---|---|
| **Observación** | 3 pedidos Custom (37,5 % de los pedidos válidos) generan el **64,7 % de los ingresos** (8.337,60 €) y el 62,5 % de los pares. Ticket medio Custom: **2.779,20 €**; estándar: 907,86 €. |
| **Interpretación** | La diferencia se apoya estadísticamente (+1.871 € por pedido, intervalo del 95 % de +849 € a +3.058 €), pero se debe sobre todo al volumen mínimo de 20 pares, no a que el cliente pague más por par. |
| **Propuesta** | Campaña a clubes y equipos de la cartera, y en especial a los que aún no repiten (ver decisión 3). Ofrecer diseños sobre los modelos que más se venden y admiten personalización (Runner X y ZoomX Invincible 3). |
| **Impacto esperado** | Cada Custom adicional equivale a unos 2-3 pedidos estándar en ingresos. |
| **Riesgo / límite** | Más dependencia de pocos clientes. Con 4 pedidos Custom no se sabe si se cancelan más (1 de 4 se canceló: 1.799,80 €). Conviene confirmar el diseño antes de producir. |
| **Evidencia** | `08_comparativa_tipo.png`, `05_boxplot_por_tipo.png`, vista Producto · **Origen: REAL** |

### 2. Asegurar stock y fabricación de los 4 modelos de clase A

| | |
|---|---|
| **Observación** | 4 de los 8 modelos vendidos concentran el **84,6 % de los ingresos**: ZoomX Invincible 3 (35,5 %), Runner X (19,1 %), Predator League FG (17,4 %) y Copa Pure II League FG (12,6 %). Los modelos C (Dunk Low y Air Force 1 Low) aportan el 2,9 %. |
| **Interpretación** | Son justo los modelos de los pedidos Custom de los clubes. El ranking depende de muy pocos pedidos. |
| **Propuesta** | Revisar cada semana el stock de los 4 modelos A en sus tallas centrales y no comprometer fabricación extra de los modelos C. |
| **Impacto esperado** | Evitar que un pedido de club se quede sin servir por falta de stock en las tallas que más se piden. |
| **Riesgo / límite** | La clasificación ABC puede cambiar entera con el próximo pedido grande. Hay que recalcularla con cada exportación (el dashboard lo hace solo). |
| **Evidencia** | `03_pareto_modelos.png`, `02_ranking_modelos.png`, `modelos_abc.csv` · **Origen: REAL** |

### 3. Convertir los borradores y reactivar a los clientes sin compra reciente

| | |
|---|---|
| **Observación** | Hay **1.109,95 €** en 2 borradores sin confirmar: SO011 (CLI003, 749,95 €) y SO012 (CLI007, 360,00 €). Esos 2 clientes no tienen ninguna compra válida. CLI006 lleva unos 150 días sin comprar («En riesgo»). Solo CLI005 es «Campeón». |
| **Interpretación** | CLI003 ya canceló un Custom (SO006). Es un cliente con interés, pero que no está cerrando ventas. |
| **Propuesta** | Llamada comercial esta semana a CLI003 y CLI007 para cerrar los borradores, y una oferta de reposición a CLI006. |
| **Impacto esperado** | Hasta +8,6 % de ingresos válidos si se confirman los dos borradores. |
| **Riesgo / límite** | Los segmentos RFM usan reglas fijas (60 y 120 días) y con 7 clientes son orientativos. La retención por cohortes no es defendible con 5 compradores. |
| **Evidencia** | Vista Clientes, `clientes_rfm.csv`, `07_dispersion_clientes.png` · **Origen: REAL** |

### 4. Planificar la producción por tallas centrando la curva en 41-43

| | |
|---|---|
| **Observación** | Las tallas 41, 42 y 43 suman el **70,8 %** de los pares vendidos (68 de 96); la 42 sola, el 29 %. Las tallas 36, 37, 45 y 46 no se han vendido. |
| **Interpretación** | Coincide con pedidos de equipos de adultos. Aun así, la prueba estadística de que «40-42 son más de la mitad» da **evidencia insuficiente**: el intervalo va del 45 % al 91 %. |
| **Propuesta** | En los pedidos Custom, proponer al club una curva por defecto centrada en 41-43, pero mantener siempre un mínimo de tallas extremas, sin recortarlas. |
| **Impacto esperado** | Menos stock inmovilizado en tallas poco pedidas. |
| **Riesgo / límite** | Casi todos los pares vienen de 3-4 clubes: otra plantilla, por ejemplo femenina o juvenil, cambiaría la curva por completo. |
| **Evidencia** | `06_mapa_calor_modelo_talla.png`, `matriz_modelo_talla.csv`, hipótesis H2 · **Origen: REAL** |

### 5. Empezar a guardar el histórico mensual para poder prever la demanda

| | |
|---|---|
| **Observación** | Con datos reales, la predicción es **NO CALCULABLE**: hay 1 mes con historial completo y hacen falta 9. En el laboratorio con datos **simulados**, el modelo (RandomForest) se equivoca un **26 % menos** que repetir el mes anterior (23,5 frente a 31,8 pares por modelo y mes), pero **se queda corto** unos 10 pares de media. |
| **Interpretación** | El método funciona y se puede aplicar en cuanto haya historia. El sesgo indica que, si la demanda crece, el modelo la infravalorará. |
| **Propuesta** | Exportar los CSV al menos una vez al mes y conservar las exportaciones. Mientras no haya 9 meses reales, planificar con el mes anterior y la media de 3 meses. Cuando se use el modelo, añadir un margen de seguridad. |
| **Impacto esperado** | Hacia mediados de 2027 habría una previsión mensual por modelo, contrastada con la referencia. |
| **Riesgo / límite** | Los resultados vienen de datos simulados con reglas inventadas: **no son una previsión de Sneaker Factory**. |
| **Evidencia** | Vista Laboratorio, `outputs/sintetico/graficos/10_prediccion_demanda.png`, `prediccion_evaluacion.csv` · **Origen: SINTÉTICO / PREDICTIVO** |

---

## Otras observaciones

- **Stock:** 2 variantes están por debajo del mínimo (Samba OG blanco y negro, talla 38: 2 pares; OMN1S blanco, talla 45: 3 pares). Ninguna ha tenido demanda en los últimos 28 días, así que **no es urgente reponerlas**: conviene revisar si ese stock mínimo tiene sentido. Origen: REAL (foto del 09/11/2026).
- **Calidad de los datos:** 740 filas sin ninguna incidencia y conciliación con SQL completa. Los datos de ACC son fiables para estos cálculos.
- **No se informa de margen ni de beneficio:** la base de datos no tiene costes de fabricación.
