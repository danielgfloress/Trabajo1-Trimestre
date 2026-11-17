
BEGIN;
SELECT set_config('app.id_usuario', (SELECT id_usuario::TEXT FROM usuarios WHERE username = 'comercial1'), true);
UPDATE pedidos SET estado = 'CONFIRMADO' WHERE ref_odoo = 'SO012';
SELECT id_evento, accion, resumen_cambios FROM log_eventos ORDER BY id_evento DESC LIMIT 1;
-- -> la ventana 1 ya ve su evento CONFIRMAR_PEDIDO

-- [Ventana 2] paso 2: mirar desde otra conexión
SELECT estado FROM pedidos WHERE ref_odoo = 'SO012';
SELECT COUNT(*) AS eventos FROM log_eventos;
-- -> sigue en BORRADOR y el evento no aparece: aún no hay COMMIT

-- [Ventana 1] paso 3: deshacer
ROLLBACK;

-- [Ventana 2] paso 4: comprobar que no queda nada
SELECT estado FROM pedidos WHERE ref_odoo = 'SO012';
SELECT COUNT(*) AS eventos FROM log_eventos;
-- -> BORRADOR y el mismo número de eventos que antes


-- [Ventana 1] paso 5
BEGIN;
SELECT set_config('app.id_usuario', (SELECT id_usuario::TEXT FROM usuarios WHERE username = 'comercial1'), true);
UPDATE pedidos SET estado = 'CANCELADO' WHERE ref_odoo = 'SO012';

-- [Ventana 2] paso 6: todavía no se ve
SELECT estado FROM pedidos WHERE ref_odoo = 'SO012';

-- [Ventana 1] paso 7
COMMIT;

-- [Ventana 2] paso 8: ahora sí aparecen el cambio y su evento, con usuario y hora
SELECT estado FROM pedidos WHERE ref_odoo = 'SO012';
SELECT l.id_evento, to_char(l.fecha_hora, 'YYYY-MM-DD HH24:MI:SS') AS fecha_hora, u.username, l.accion, l.resumen_cambios
FROM log_eventos l LEFT JOIN usuarios u ON u.id_usuario = l.id_usuario
ORDER BY l.id_evento DESC LIMIT 1;
