# Diccionario de datos

Contrato de entrada de Python: los 5 CSV que exporta Acceso a Datos (`modelo_datos_comun.md`, apartado 9.2) más el fichero de reconciliación.
Todos se generan con `./exportar_acc.sh` desde PostgreSQL.

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
