#!/bin/bash
set -e
cd "$(dirname "$0")/.."
if [ -f ../.env ]; then
    source ../.env
fi
PSQL=${PSQL:-"docker exec -i d3kicks-db psql -U $POSTGRES_USER -d $POSTGRES_DB -q"}
mkdir -p entrada_acc

exportar() {
    $PSQL -c "\copy ($2) TO STDOUT WITH (FORMAT csv, HEADER true)" > "entrada_acc/$1.csv.tmp"
    mv "entrada_acc/$1.csv.tmp" "entrada_acc/$1.csv"
    echo "  $1.csv: $(($(wc -l < "entrada_acc/$1.csv") - 1)) filas"
}

echo "Exportando desde PostgreSQL a entrada_acc/ ..."
exportar clientes "SELECT id_cliente, codigo_odoo, nombre, tipo_cliente, CASE WHEN activo THEN 'true' ELSE 'false' END AS activo FROM clientes ORDER BY id_cliente"
exportar modelos "SELECT id_modelo, codigo_modelo, marca, nombre, categoria, precio_base, CASE WHEN admite_custom THEN 'true' ELSE 'false' END AS admite_custom, CASE WHEN activo THEN 'true' ELSE 'false' END AS activo FROM modelos ORDER BY id_modelo"
exportar pedidos "SELECT id_pedido, ref_odoo, to_char(fecha_pedido, 'YYYY-MM-DD HH24:MI:SS') AS fecha_pedido, id_cliente, tipo, estado, importe_total FROM pedidos ORDER BY id_pedido"
exportar lineas_pedido "SELECT l.id_linea, l.id_pedido, a.id_modelo, a.color_base AS color, a.talla, l.cantidad, l.precio_unitario, l.subtotal_linea, CASE WHEN l.id_personalizacion IS NULL THEN 'false' ELSE 'true' END AS personalizada FROM lineas_pedido l JOIN almacen a ON a.id_almacen = l.id_almacen ORDER BY l.id_linea"
exportar stock "SELECT id_modelo, color_base AS color, talla, stock_disponible, stock_minimo, to_char(now(), 'YYYY-MM-DD HH24:MI:SS') AS fecha_corte FROM almacen ORDER BY id_modelo, color_base, talla"
exportar reconciliacion_sql "SELECT 'pedidos_validos' AS metrica, COUNT(*)::numeric AS valor_sql FROM pedidos WHERE estado IN ('CONFIRMADO', 'ENTREGADO') UNION ALL SELECT 'pares_vendidos', COALESCE(SUM(l.cantidad), 0) FROM lineas_pedido l JOIN pedidos p ON p.id_pedido = l.id_pedido WHERE p.estado IN ('CONFIRMADO', 'ENTREGADO') UNION ALL SELECT 'ingresos_validos', COALESCE(SUM(l.subtotal_linea), 0) FROM lineas_pedido l JOIN pedidos p ON p.id_pedido = l.id_pedido WHERE p.estado IN ('CONFIRMADO', 'ENTREGADO') UNION ALL SELECT 'clientes_con_compra', COUNT(DISTINCT id_cliente) FROM pedidos WHERE estado IN ('CONFIRMADO', 'ENTREGADO') UNION ALL SELECT 'lineas_totales', COUNT(*) FROM lineas_pedido"
echo "Exportación terminada: $(date '+%Y-%m-%d %H:%M:%S')"
