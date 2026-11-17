#!/bin/bash

set -e
cd "$(dirname "$0")/.."
if [ -f .env ]; then
    source .env
fi
PSQL=${PSQL:-"docker exec -i d3kicks-db psql -U $POSTGRES_USER -d $POSTGRES_DB -q -At"}
DESTINO=${DESTINO:-psp/entrada}
mkdir -p "$DESTINO"

if [ $# -gt 0 ]; then
    PEDIDOS="$*"
else
    PEDIDOS=$($PSQL -c "SELECT ref_odoo FROM pedidos WHERE tipo = 'CUSTOM' AND estado IN ('CONFIRMADO', 'ENTREGADO') ORDER BY ref_odoo")
fi

for REF in $PEDIDOS; do
    if ! [[ "$REF" =~ ^SO[0-9]+$ ]]; then
        echo "  $REF: referencia no válida, se salta"
        continue
    fi
    $PSQL -c "\copy (SELECT p.ref_odoo, c.nombre AS cliente, m.nombre AS modelo, a.color_base AS color, pe.nombre_diseno AS diseno, pe.texto_bordado, a.talla, l.cantidad FROM pedidos p JOIN clientes c ON c.id_cliente = p.id_cliente JOIN lineas_pedido l ON l.id_pedido = p.id_pedido JOIN almacen a ON a.id_almacen = l.id_almacen JOIN modelos m ON m.id_modelo = a.id_modelo LEFT JOIN personalizaciones pe ON pe.id_personalizacion = l.id_personalizacion WHERE p.ref_odoo = '$REF' ORDER BY a.talla) TO STDOUT WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')" > "$DESTINO/ficha_$REF.csv.tmp"
    FILAS=$(($(wc -l < "$DESTINO/ficha_$REF.csv.tmp") - 1))
    if [ "$FILAS" -le 0 ]; then
        rm "$DESTINO/ficha_$REF.csv.tmp"
        echo "  $REF: no existe o no tiene líneas, no se genera ficha"
        continue
    fi
    mv "$DESTINO/ficha_$REF.csv.tmp" "$DESTINO/ficha_$REF.csv"
    echo "  ficha_$REF.csv: $FILAS filas"
done
echo "Exportación terminada: $(date '+%Y-%m-%d %H:%M:%S')"
