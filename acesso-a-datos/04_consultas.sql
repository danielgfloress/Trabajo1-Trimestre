SELECT p.ref_odoo, p.fecha_pedido, p.tipo, p.estado, p.importe_total
FROM pedidos p
JOIN clientes c ON c.id_cliente = p.id_cliente
WHERE c.codigo_odoo = 'CLI001'
ORDER BY p.fecha_pedido;

SELECT p.ref_odoo, c.nombre AS cliente, p.fecha_pedido, p.importe_total
FROM pedidos p
JOIN clientes c ON c.id_cliente = p.id_cliente
WHERE p.estado = 'CONFIRMADO'
  AND p.fecha_pedido >= '2026-09-01'
  AND p.fecha_pedido < '2026-11-01'
ORDER BY p.fecha_pedido;

SELECT DISTINCT p.ref_odoo, c.nombre AS cliente, p.estado, p.fecha_pedido
FROM pedidos p
JOIN clientes c ON c.id_cliente = p.id_cliente
JOIN lineas_pedido l ON l.id_pedido = p.id_pedido
JOIN almacen a ON a.id_almacen = l.id_almacen
JOIN modelos m ON m.id_modelo = a.id_modelo
WHERE m.nombre = 'Runner X'
ORDER BY p.fecha_pedido;

SELECT p.ref_odoo, c.nombre AS cliente, m.marca, m.nombre AS modelo, a.color_base AS color, a.talla,
       l.cantidad, l.precio_unitario, l.subtotal_linea, pe.nombre_diseno AS diseno
FROM pedidos p
JOIN clientes c ON c.id_cliente = p.id_cliente
JOIN lineas_pedido l ON l.id_pedido = p.id_pedido
JOIN almacen a ON a.id_almacen = l.id_almacen
JOIN modelos m ON m.id_modelo = a.id_modelo
LEFT JOIN personalizaciones pe ON pe.id_personalizacion = l.id_personalizacion
WHERE p.ref_odoo = 'SO008'
ORDER BY a.talla;

SELECT a.talla, SUM(l.cantidad) AS pares
FROM lineas_pedido l
JOIN pedidos p ON p.id_pedido = l.id_pedido
JOIN almacen a ON a.id_almacen = l.id_almacen
WHERE p.estado IN ('CONFIRMADO', 'ENTREGADO')
GROUP BY a.talla
ORDER BY a.talla;

SELECT m.marca, m.nombre AS modelo,
       SUM(l.cantidad) AS pares,
       SUM(l.subtotal_linea) AS importe,
       COUNT(DISTINCT p.id_pedido) AS pedidos
FROM lineas_pedido l
JOIN pedidos p ON p.id_pedido = l.id_pedido
JOIN almacen a ON a.id_almacen = l.id_almacen
JOIN modelos m ON m.id_modelo = a.id_modelo
WHERE p.estado IN ('CONFIRMADO', 'ENTREGADO')
GROUP BY m.marca, m.nombre
ORDER BY pares DESC, m.marca, modelo;

SELECT c.codigo_odoo, c.nombre AS cliente,
       COUNT(p.id_pedido) AS pedidos,
       COALESCE(SUM(p.importe_total), 0) AS importe
FROM clientes c
LEFT JOIN pedidos p ON p.id_cliente = c.id_cliente
                   AND p.estado IN ('CONFIRMADO', 'ENTREGADO')
GROUP BY c.codigo_odoo, c.nombre
ORDER BY importe DESC, c.nombre;

SELECT c.codigo_odoo, c.nombre AS cliente,
       COUNT(p.id_pedido) AS pedidos,
       SUM(p.importe_total) AS importe
FROM clientes c
JOIN pedidos p ON p.id_cliente = c.id_cliente
WHERE p.estado IN ('CONFIRMADO', 'ENTREGADO')
GROUP BY c.codigo_odoo, c.nombre
HAVING COUNT(p.id_pedido) >= 2
ORDER BY importe DESC;

SELECT p.ref_odoo, c.nombre AS cliente, p.estado, p.importe_total
FROM pedidos p
JOIN clientes c ON c.id_cliente = p.id_cliente
WHERE p.estado IN ('CONFIRMADO', 'ENTREGADO')
  AND p.importe_total > (
      SELECT AVG(importe_total)
      FROM pedidos
      WHERE estado IN ('CONFIRMADO', 'ENTREGADO')
  )
ORDER BY p.importe_total DESC;

SELECT
    (SELECT COUNT(*) FROM pedidos) AS total_pedidos,
    (SELECT COUNT(*) FROM pedidos WHERE estado IN ('CONFIRMADO', 'ENTREGADO')) AS pedidos_validos,
    (SELECT COALESCE(SUM(l.cantidad), 0)
       FROM lineas_pedido l JOIN pedidos p ON p.id_pedido = l.id_pedido
      WHERE p.estado IN ('CONFIRMADO', 'ENTREGADO')) AS pares_vendidos,
    (SELECT COALESCE(SUM(importe_total), 0)
       FROM pedidos WHERE estado IN ('CONFIRMADO', 'ENTREGADO')) AS importe_ventas;

SELECT e.estado, COUNT(p.id_pedido) AS pedidos
FROM (VALUES ('BORRADOR', 1), ('CONFIRMADO', 2), ('ENTREGADO', 3), ('CANCELADO', 4)) e(estado, orden)
LEFT JOIN pedidos p ON p.estado = e.estado
GROUP BY e.estado, e.orden
ORDER BY e.orden;

SELECT m.marca, m.nombre AS modelo, a.talla, SUM(l.cantidad) AS pares
FROM lineas_pedido l
JOIN pedidos p ON p.id_pedido = l.id_pedido
JOIN almacen a ON a.id_almacen = l.id_almacen
JOIN modelos m ON m.id_modelo = a.id_modelo
WHERE p.estado IN ('CONFIRMADO', 'ENTREGADO')
GROUP BY m.marca, m.nombre, a.talla
ORDER BY m.marca, m.nombre, a.talla;

SELECT m.marca, m.nombre AS modelo, a.color_base AS color, a.talla,
       a.stock_disponible, a.stock_minimo
FROM almacen a
JOIN modelos m ON m.id_modelo = a.id_modelo
WHERE a.stock_disponible <= 5
ORDER BY a.stock_disponible, m.marca, m.nombre, a.color_base, a.talla;

SELECT p.ref_odoo, c.nombre AS cliente, m.marca, m.nombre AS modelo, a.color_base AS color,
       pe.nombre_diseno AS diseno, pe.color_primario, pe.color_secundario,
       pe.texto_bordado, pe.escudo_club, a.talla, l.cantidad
FROM pedidos p
JOIN clientes c ON c.id_cliente = p.id_cliente
JOIN lineas_pedido l ON l.id_pedido = p.id_pedido
JOIN almacen a ON a.id_almacen = l.id_almacen
JOIN modelos m ON m.id_modelo = a.id_modelo
LEFT JOIN personalizaciones pe ON pe.id_personalizacion = l.id_personalizacion
WHERE p.ref_odoo = 'SO024'
ORDER BY a.talla;

WITH filtros AS (
    SELECT CAST(NULL AS VARCHAR) AS cliente,
           CAST('Runner X' AS VARCHAR) AS modelo,
           CAST('CONFIRMADO' AS VARCHAR) AS estado,
           CAST(NULL AS DATE) AS desde,
           CAST(NULL AS DATE) AS hasta
)
SELECT p.ref_odoo, c.nombre AS cliente, p.fecha_pedido, p.tipo, p.estado, p.importe_total
FROM pedidos p
JOIN clientes c ON c.id_cliente = p.id_cliente
CROSS JOIN filtros f
WHERE (f.cliente IS NULL OR c.nombre ILIKE '%' || f.cliente || '%')
  AND (f.modelo IS NULL OR EXISTS (
          SELECT 1
          FROM lineas_pedido l
          JOIN almacen a ON a.id_almacen = l.id_almacen
          JOIN modelos m ON m.id_modelo = a.id_modelo
          WHERE l.id_pedido = p.id_pedido AND m.nombre = f.modelo))
  AND (f.estado IS NULL OR p.estado = f.estado)
  AND (f.desde IS NULL OR p.fecha_pedido >= f.desde)
  AND (f.hasta IS NULL OR p.fecha_pedido < f.hasta + 1)
ORDER BY p.fecha_pedido DESC;
