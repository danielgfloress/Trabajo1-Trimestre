# Diccionario de datos

Contrato de entrada de Python: los 5 CSV que exporta Acceso a Datos (`modelo_datos_comun.md`, apartado 9.2) más el fichero de reconciliación.
Todos se generan con `bash scripts/exportar_acc.sh` desde PostgreSQL.

## Formato común

| Aspecto | Valor |
|---|---|
| Codificación | UTF-8 |
| Separador | coma `,` |
| Decimal | punto `.` |
| Moneda | euros con IVA, sin símbolo |
| Fecha y hora | `YYYY-MM-DD HH:MM:SS` |
| Booleanos | `true` / `false` |
| Nulos | campo vacío (nunca se convierten en 0) |
| Escritura | se escribe `.csv.tmp` y se renombra al terminar |

Los `id_...` son **identificadores**: se leen como texto y nunca se usan en cálculos.

## clientes.csv · clave `id_cliente`

| Columna | Significado | Tipo | Valores permitidos | Nulos |
|---|---|---|---|---|
| id_cliente | Id interno de PostgreSQL | texto | único | no |
| codigo_odoo | Código común del cliente | texto | `CLI` + 3 dígitos, único | no |
| nombre | Club, equipo o persona | texto | — | no |
| tipo_cliente | Tipo de cliente | texto | CLUB, EQUIPO, PARTICULAR | no |
| activo | Cliente activo | booleano | true, false | no |

## modelos.csv · clave `id_modelo`

| Columna | Significado | Tipo | Valores permitidos | Nulos |
|---|---|---|---|---|
| id_modelo | Id interno | texto | único | no |
| codigo_modelo | Código común del modelo | texto | p. ej. `D3-001`, único | no |
| marca | Marca | texto | — | no |
| nombre | Nombre del modelo | texto | — | no |
| categoria | Categoría | texto | Sneakers, Baloncesto, Fútbol, Boxeo | no |
| precio_base | Precio de catálogo (€) | decimal | > 0 | no |
| admite_custom | Se puede personalizar | booleano | true, false | no |
| activo | Modelo a la venta | booleano | true, false | no |

## pedidos.csv · clave `id_pedido`

| Columna | Significado | Tipo | Valores permitidos | Nulos |
|---|---|---|---|---|
| id_pedido | Id interno | texto | único | no |
| ref_odoo | Número de pedido común | texto | `SO` + 3 dígitos, único | no |
| fecha_pedido | Fecha y hora del pedido | fecha | formato común | no (si es imposible, el pedido se rechaza) |
| id_cliente | Cliente (→ clientes) | texto | debe existir | no |
| tipo | Tipo de pedido | texto | ESTANDAR, CUSTOM | no |
| estado | Estado | texto | BORRADOR, CONFIRMADO, ENTREGADO, CANCELADO | no |
| importe_total | Total calculado por los triggers (€) | decimal | ≥ 0, = suma de líneas | no |

**Venta válida** = estado CONFIRMADO o ENTREGADO. El ingreso se reconoce en la fecha del pedido.

## lineas_pedido.csv · clave `id_linea`

| Columna | Significado | Tipo | Valores permitidos | Nulos |
|---|---|---|---|---|
| id_linea | Id interno | texto | único | no |
| id_pedido | Pedido (→ pedidos) | texto | debe existir | no |
| id_modelo | Modelo (→ modelos) | texto | debe existir | no |
| color | Color de la variante | texto | — | no |
| talla | Talla europea | entero | 36 a 46 | no |
| cantidad | Pares | entero | > 0 | no |
| precio_unitario | Precio por par con recargo Custom (€) | decimal | ≥ 0 | no |
| subtotal_linea | cantidad × precio_unitario (€) | decimal | = cantidad × precio | no |
| personalizada | Línea Custom | booleano | true, false | no |

## stock.csv · clave `id_modelo + color + talla`

| Columna | Significado | Tipo | Valores permitidos | Nulos |
|---|---|---|---|---|
| id_modelo | Modelo (→ modelos) | texto | debe existir | no |
| color | Color | texto | — | no |
| talla | Talla | entero | 36 a 46 | no |
| stock_disponible | Pares en almacén | entero | ≥ 0 | no |
| stock_minimo | Umbral de alerta | entero | ≥ 0 | no |
| fecha_corte | Momento de la exportación | fecha | formato común | no |

El stock es una **foto en la fecha de corte**, no un histórico.

## reconciliacion_sql.csv (opcional)

| Columna | Significado |
|---|---|
| metrica | pedidos_validos, pares_vendidos, ingresos_validos, clientes_con_compra, lineas_totales |
| valor_sql | La misma cifra calculada en PostgreSQL |

## Variables derivadas

Calculadas en `analiticas.py` a partir de los CSV; no vienen de ACC. **Disponible antes del mes** indica si se conoce antes de empezar el mes que se quiere predecir (si no, no puede usarse como predictor).

| Variable | Familia | Fórmula | Unidad | Nivel | Disponible antes del mes |
|---|---|---|---|---|---|
| anio | Calendario | año de `fecha_pedido` | año | pedido | sí |
| trimestre | Calendario | trimestre de `fecha_pedido` (1-4) | trimestre | pedido | sí |
| dia_semana | Calendario | día de la semana de `fecha_pedido` | lunes…domingo | pedido | sí |
| antiguedad_dias | Calendario | fecha de corte − `fecha_pedido` | días | pedido | no (depende del corte) |
| importe_linea | Economía | cantidad × precio_unitario | € | línea | no |
| precio_medio_par | Economía | importe del pedido ÷ pares del pedido | €/par | pedido | no |
| frecuencia_cliente | Comportamiento | nº de pedidos válidos distintos | pedidos | cliente | solo con pedidos anteriores |
| porcentaje_custom | Comportamiento | pedidos CUSTOM ÷ pedidos válidos × 100 | % | cliente | solo con pedidos anteriores |
| intervalo_medio_dias | Comportamiento | media de días entre compras válidas seguidas; vacío si solo hay una compra | días | cliente | solo con pedidos anteriores |
| unidades_modelo_mes | Demanda | Σ pares vendidos del modelo en el mes; 0 si ese mes no se vendió | pares | modelo-mes | no (es el objetivo) |
| demanda_mes_anterior | Demanda | `unidades_modelo_mes` del mes anterior | pares | modelo-mes | sí |
| media_3_meses_previos | Demanda | media de los 3 meses anteriores, sin incluir el mes actual; vacío si no hay 3 | pares | modelo-mes | sí |
| mes_del_anio | Demanda | número de mes (1-12) | mes | modelo-mes | sí |
| talla_mas_solicitada | Operaciones | talla con más pares vendidos del modelo; si empatan, la menor | talla | modelo | no |
| alerta_stock_bajo | Operaciones | stock_disponible ≤ stock_minimo | sí/no | modelo-color-talla | foto del corte |
| cobertura_semanas | Operaciones | stock ÷ (pares de los últimos 28 días ÷ 4); N/D sin demanda | semanas | modelo-color-talla | foto del corte |

Todas se calculan solo con ventas válidas (CONFIRMADO y ENTREGADO), salvo las de calendario, que existen para todos los pedidos.

## Datos sintéticos (`datos_sinteticos/`)

> **No son datos de Sneaker Factory.** Los genera `generador_datos.py` para poder estudiar segmentación y predicción con un histórico largo. Nunca se mezclan con `entrada_acc/` y todo lo que sale de ellos se rotula **SINTÉTICO · generador_datos.py**. No describen la demanda real.

Mismo contrato que los CSV de ACC (mismas columnas y formatos), con códigos propios para que no se confundan: modelos `SIM-01`…`SIM-14` (marca `SIMULADA`), clientes `SCLI001`…`SCLI045`, pedidos `SSO0001`…`SSO0900`.

| Parámetro | Valor | Dónde se cambia |
|---|---|---|
| Semilla | 42 (misma semilla → mismos CSV) | `config.SEMILLA` o `--semilla` |
| Pedidos | 900 | `config.SINTETICO_PEDIDOS` |
| Clientes | 45 | `config.SINTETICO_CLIENTES` |
| Modelos | 14 | lista `MODELOS` del generador |
| Periodo | 18 meses, de 01/2025 a 06/2026; fecha de corte 30/06/2026 23:59:59 | `config.SINTETICO_INICIO`, `config.SINTETICO_MESES` |

### Hipótesis de simulación

| # | Hipótesis | Cómo se aplica |
|---|---|---|
| S1 | Unos clientes compran mucho más que otros | cada cliente tiene un peso de actividad lognormal; pocos clientes concentran muchos pedidos |
| S2 | Hay meses fuertes y flojos | factor mensual general (máximo en septiembre y diciembre, mínimo en febrero) y +1,5 % de crecimiento al mes |
| S3 | Cada categoría tiene su temporada | Fútbol ×1,6 en agosto-septiembre, Baloncesto ×1,4 en septiembre-octubre, Sneakers ×1,3 en noviembre-diciembre, Boxeo ×1,4 en enero |
| S4 | Unos modelos son más populares | cada modelo tiene una popularidad fija (de 1,00 a 0,12) |
| S5 | Las tallas centrales se piden más | curva centrada en 41,5 con desviación 2 (tallas 36 a 46) |
| S6 | Solo clubes y equipos piden Custom | 30 % de los pedidos de clubes y 25 % de equipos; nunca particulares |
| S7 | Un Custom es un solo modelo en varias tallas | 20 a 60 pares repartidos en 2 a 5 tallas, solo modelos que admiten Custom, recargo de 10 a 20 €/par |
| S8 | Un pedido estándar tiene 1 a 3 líneas | particulares 1-2 pares por línea; clubes y equipos 2-12 |
| S9 | El estado depende de la antigüedad | más de 45 días: entregado o cancelado; 21-45 días: confirmado o entregado; últimos 20 días: también borradores. Cancelación 8 % estándar y 14 % Custom |
| S10 | El stock depende de la popularidad | stock por modelo, color y talla con media proporcional a popularidad × peso de la talla; mínimo 5 |

### Copia con incidencias (`datos_sinteticos/con_incidencias/`)

Los mismos datos con 11 errores introducidos a propósito para demostrar las reglas de calidad. `incidencias_introducidas.csv` dice qué registro se estropeó y qué regla debe saltar: ID huérfano (03), fecha imposible (04), cantidad negativa (05), precio no numérico (06), estado fuera de catálogo (07), talla 50 (08), pedido sin cliente (09), importe descuadrado (12), stock negativo (11), pedido duplicado (02) y stock duplicado (11).
