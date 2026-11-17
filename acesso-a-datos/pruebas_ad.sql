-- =====================================================================
-- D3 Kicks · Pruebas de Acceso a Datos
-- Cada prueba es un bloque DO que muestra sus resultados con RAISE NOTICE
-- (pestaña Messages de pgAdmin) y termina deshaciendo sus cambios, así que
-- se pueden repetir sin estropear los datos de prueba.
-- Truco para deshacer: los cambios van dentro de un bloque BEGIN ... EXCEPTION;
-- al final se lanza la excepción 'deshacer' y PostgreSQL vuelve al punto
-- de guardado del bloque, como si no se hubiera hecho nada.
-- =====================================================================

-- PRUEBA 1. El precio de la línea y el total del pedido se calculan solos
DO $$
DECLARE
	v_pedido INTEGER;
	v_almacen INTEGER;
	v_antes NUMERIC;
	v_despues NUMERIC;
	v_precio NUMERIC;
BEGIN
	RAISE NOTICE '--- PRUEBA 1: precio y total automáticos ---';
	BEGIN
		PERFORM set_config('app.id_usuario', '1', true);
		SELECT id_pedido, importe_total INTO v_pedido, v_antes FROM pedidos WHERE ref_odoo = 'SO011';
		SELECT a.id_almacen INTO v_almacen
		FROM almacen a JOIN modelos m ON m.id_modelo = a.id_modelo
		WHERE m.codigo_modelo = 'D3-001' AND a.talla = 41;

		INSERT INTO lineas_pedido (id_pedido, id_almacen, cantidad, precio_unitario)
		VALUES (v_pedido, v_almacen, 2, 0)
		RETURNING precio_unitario INTO v_precio;

		SELECT importe_total INTO v_despues FROM pedidos WHERE id_pedido = v_pedido;
		RAISE NOTICE 'Línea insertada con precio 0 -> la base de datos pone %', v_precio;
		RAISE NOTICE 'Total de SO011: antes % / después % (+%)', v_antes, v_despues, v_despues - v_antes;
		RAISE EXCEPTION 'deshacer';
	EXCEPTION WHEN raise_exception THEN
		IF SQLERRM <> 'deshacer' THEN RAISE; END IF;
	END;
	RAISE NOTICE 'Cambios deshechos. Total actual de SO011: %',
		(SELECT importe_total FROM pedidos WHERE ref_odoo = 'SO011');
END $$;

-- PRUEBA 2. Confirmar descuenta el stock y cancelar lo devuelve
DO $$
DECLARE
	v_almacen INTEGER;
	v_evento RECORD;
BEGIN
	RAISE NOTICE '--- PRUEBA 2: confirmar y cancelar SO012 ---';
	SELECT l.id_almacen INTO v_almacen
	FROM lineas_pedido l JOIN pedidos p ON p.id_pedido = l.id_pedido
	WHERE p.ref_odoo = 'SO012';
	BEGIN
		PERFORM set_config('app.id_usuario', '1', true);
		RAISE NOTICE 'Stock inicial: %', (SELECT stock_disponible FROM almacen WHERE id_almacen = v_almacen);
		UPDATE pedidos SET estado = 'CONFIRMADO' WHERE ref_odoo = 'SO012';
		RAISE NOTICE 'Tras confirmar: %', (SELECT stock_disponible FROM almacen WHERE id_almacen = v_almacen);
		UPDATE pedidos SET estado = 'CANCELADO' WHERE ref_odoo = 'SO012';
		RAISE NOTICE 'Tras cancelar: %', (SELECT stock_disponible FROM almacen WHERE id_almacen = v_almacen);
		FOR v_evento IN
			SELECT accion, resumen_cambios FROM log_eventos ORDER BY id_evento DESC LIMIT 2
		LOOP
			RAISE NOTICE 'Auditoría: % | %', v_evento.accion, v_evento.resumen_cambios;
		END LOOP;
		RAISE EXCEPTION 'deshacer';
	EXCEPTION WHEN raise_exception THEN
		IF SQLERRM <> 'deshacer' THEN RAISE; END IF;
	END;
	RAISE NOTICE 'Cambios deshechos. SO012 vuelve a estar en %',
		(SELECT estado FROM pedidos WHERE ref_odoo = 'SO012');
END $$;

-- PRUEBA 3. No se puede confirmar un pedido sin stock suficiente
DO $$
BEGIN
	RAISE NOTICE '--- PRUEBA 3: stock insuficiente (SO011) ---';
	BEGIN
		UPDATE pedidos SET estado = 'CONFIRMADO' WHERE ref_odoo = 'SO011';
		RAISE NOTICE 'ERROR EN LA PRUEBA: se ha confirmado';
	EXCEPTION WHEN raise_exception THEN
		RAISE NOTICE 'Rechazado: %', SQLERRM;
	END;
END $$;

-- PRUEBA 4. Solo se permiten los cambios de estado válidos
DO $$
BEGIN
	RAISE NOTICE '--- PRUEBA 4: BORRADOR -> ENTREGADO (SO012) ---';
	BEGIN
		UPDATE pedidos SET estado = 'ENTREGADO' WHERE ref_odoo = 'SO012';
		RAISE NOTICE 'ERROR EN LA PRUEBA: se ha cambiado el estado';
	EXCEPTION WHEN raise_exception THEN
		RAISE NOTICE 'Rechazado: %', SQLERRM;
	END;
END $$;

-- PRUEBA 5. Un pedido CUSTOM necesita al menos 20 pares
DO $$
DECLARE
	v_cliente INTEGER;
	v_usuario INTEGER;
	v_pedido INTEGER;
	v_almacen INTEGER;
	v_diseno INTEGER;
BEGIN
	RAISE NOTICE '--- PRUEBA 5: pedido CUSTOM de 5 pares ---';
	BEGIN
		SELECT id_cliente INTO v_cliente FROM clientes WHERE codigo_odoo = 'CLI001';
		SELECT id_usuario INTO v_usuario FROM usuarios WHERE username = 'comercial1';
		SELECT a.id_almacen INTO v_almacen
		FROM almacen a JOIN modelos m ON m.id_modelo = a.id_modelo
		WHERE m.codigo_modelo = 'D3-001' AND a.talla = 42;

		INSERT INTO personalizaciones (nombre_diseno, color_primario, recargo_unitario)
		VALUES ('DIS-PRUEBA', 'AZUL', 15) RETURNING id_personalizacion INTO v_diseno;
		INSERT INTO pedidos (ref_odoo, id_cliente, id_usuario, tipo)
		VALUES ('SO999', v_cliente, v_usuario, 'CUSTOM') RETURNING id_pedido INTO v_pedido;
		INSERT INTO lineas_pedido (id_pedido, id_almacen, id_personalizacion, cantidad, precio_unitario)
		VALUES (v_pedido, v_almacen, v_diseno, 5, 0);

		UPDATE pedidos SET estado = 'CONFIRMADO' WHERE id_pedido = v_pedido;
		RAISE NOTICE 'ERROR EN LA PRUEBA: se ha confirmado';
	EXCEPTION WHEN raise_exception THEN
		RAISE NOTICE 'Rechazado: %', SQLERRM;
	END;
END $$;

-- PRUEBA 6. Permisos por rol y protección del importe total
DO $$
DECLARE
	v_admin INTEGER;
	v_comercial INTEGER;
	v_laura INTEGER;
BEGIN
	RAISE NOTICE '--- PRUEBA 6: permisos y total protegido ---';
	SELECT id_usuario INTO v_admin FROM usuarios WHERE username = 'admin';
	SELECT id_usuario INTO v_comercial FROM usuarios WHERE username = 'comercial1';
	SELECT id_usuario INTO v_laura FROM usuarios WHERE username = 'laura.martin@example.com';

	RAISE NOTICE 'admin puede ver la auditoría: %', fn_tiene_permiso(v_admin, 'AUDITORIA_VER');
	RAISE NOTICE 'comercial1 puede ver la auditoría: %', fn_tiene_permiso(v_comercial, 'AUDITORIA_VER');

	BEGIN
		PERFORM set_config('app.id_usuario', v_laura::TEXT, true);
		UPDATE pedidos SET estado = 'CANCELADO'
		WHERE ref_odoo = (SELECT MIN(p.ref_odoo) FROM pedidos p
		                  JOIN usuarios u ON u.id_cliente = p.id_cliente
		                  WHERE u.id_usuario = v_laura);
		RAISE NOTICE 'ERROR EN LA PRUEBA: Laura ha cancelado un pedido';
	EXCEPTION WHEN raise_exception THEN
		RAISE NOTICE 'Rechazado: %', SQLERRM;
	END;

	BEGIN
		PERFORM set_config('app.id_usuario', v_admin::TEXT, true);
		UPDATE pedidos SET importe_total = 1 WHERE ref_odoo = 'SO011';
		RAISE NOTICE 'ERROR EN LA PRUEBA: se ha cambiado el total';
	EXCEPTION WHEN raise_exception THEN
		RAISE NOTICE 'Rechazado: %', SQLERRM;
	END;
END $$;

-- =====================================================================
-- PRUEBAS DE LOS REQUISITOS MÍNIMOS DEL ENUNCIADO (Sneaker Factory)
-- =====================================================================

-- PRUEBA 7. DELETE: borrar una línea de un pedido en borrador (3.2)
-- El total se recalcula y la auditoría apunta BORRAR_LINEA. En un pedido
-- confirmado el mismo DELETE se rechaza.
DO $$
DECLARE
	v_linea INTEGER;
	v_antes NUMERIC;
BEGIN
	RAISE NOTICE '--- PRUEBA 7: DELETE de una línea ---';
	BEGIN
		PERFORM set_config('app.id_usuario', (SELECT id_usuario::TEXT FROM usuarios WHERE username = 'comercial1'), true);
		SELECT importe_total INTO v_antes FROM pedidos WHERE ref_odoo = 'SO011';
		SELECT MIN(l.id_linea) INTO v_linea FROM lineas_pedido l JOIN pedidos p ON p.id_pedido = l.id_pedido WHERE p.ref_odoo = 'SO011';
		DELETE FROM lineas_pedido WHERE id_linea = v_linea;
		RAISE NOTICE 'Línea % borrada de SO011. Total: % -> %', v_linea, v_antes,
			(SELECT importe_total FROM pedidos WHERE ref_odoo = 'SO011');
		RAISE NOTICE 'Auditoría: %', (SELECT accion || ' | ' || resumen_cambios FROM log_eventos ORDER BY id_evento DESC LIMIT 1);
		BEGIN
			DELETE FROM lineas_pedido WHERE id_pedido = (SELECT id_pedido FROM pedidos WHERE ref_odoo = 'SO008');
			RAISE NOTICE 'ERROR EN LA PRUEBA: se han borrado líneas de un pedido confirmado';
		EXCEPTION WHEN raise_exception THEN
			RAISE NOTICE 'Rechazado en SO008: %', SQLERRM;
		END;
		BEGIN
			DELETE FROM pedidos WHERE ref_odoo = 'SO011';
			RAISE NOTICE 'ERROR EN LA PRUEBA: se ha borrado un pedido';
		EXCEPTION WHEN raise_exception THEN
			RAISE NOTICE 'Rechazado borrar SO011: %', SQLERRM;
		END;
		RAISE EXCEPTION 'deshacer';
	EXCEPTION WHEN raise_exception THEN
		IF SQLERRM <> 'deshacer' THEN RAISE; END IF;
	END;
	RAISE NOTICE 'Cambios deshechos. SO011 sigue con % líneas y un total de %',
		(SELECT COUNT(*) FROM lineas_pedido l JOIN pedidos p ON p.id_pedido = l.id_pedido WHERE p.ref_odoo = 'SO011'),
		(SELECT importe_total FROM pedidos WHERE ref_odoo = 'SO011');
END $$;

-- PRUEBA 8. CASO DE PRUEBA COMÚN (pruebas A, B y C del enunciado)
-- CB Torres (CLI003) pide 40 pares de Runner X Custom en cuatro tallas.
-- A: se registra y confirma con el usuario comercial1 -> total, stock y auditoría.
-- B: otro pedido Custom sin stock suficiente se rechaza sin cambios parciales.
-- C: se cancela el pedido confirmado y el stock vuelve a su sitio.
DO $$
DECLARE
	v_comercial INTEGER;
	v_cliente INTEGER;
	v_diseno INTEGER;
	v_pedido INTEGER;
	v_otro INTEGER;
	v_primer_evento INTEGER;
	v_fila RECORD;
	v_stock_antes TEXT;
BEGIN
	RAISE NOTICE '--- PRUEBA 8: caso común, 40 pares de Runner X Custom ---';
	BEGIN
		SELECT id_usuario INTO v_comercial FROM usuarios WHERE username = 'comercial1';
		SELECT id_cliente INTO v_cliente FROM clientes WHERE codigo_odoo = 'CLI003';
		PERFORM set_config('app.id_usuario', v_comercial::TEXT, true);
		SELECT COALESCE(MAX(id_evento), 0) INTO v_primer_evento FROM log_eventos;
		SELECT string_agg(a.talla || ':' || a.stock_disponible, ' ' ORDER BY a.talla) INTO v_stock_antes
		FROM almacen a JOIN modelos m ON m.id_modelo = a.id_modelo
		WHERE m.codigo_modelo = 'D3-001' AND a.talla IN (38, 39, 40, 42);

		-- A. Alta del pedido Custom y confirmación
		INSERT INTO personalizaciones (nombre_diseno, color_primario, color_secundario, texto_bordado, recargo_unitario)
		VALUES ('DIS-SO100 CB Torres', '#1E3A8A', '#FFFFFF', 'CB TORRES', 10)
		RETURNING id_personalizacion INTO v_diseno;
		INSERT INTO pedidos (ref_odoo, id_cliente, id_usuario, tipo, fecha_entrega_objetivo)
		VALUES ('SO100', v_cliente, v_comercial, 'CUSTOM', CURRENT_DATE + 30)
		RETURNING id_pedido INTO v_pedido;
		INSERT INTO lineas_pedido (id_pedido, id_almacen, id_personalizacion, cantidad, precio_unitario)
		SELECT v_pedido, a.id_almacen, v_diseno, t.cantidad, 0
		FROM (VALUES (38, 10), (39, 10), (40, 10), (42, 10)) t (talla, cantidad)
		JOIN almacen a ON a.talla = t.talla
		JOIN modelos m ON m.id_modelo = a.id_modelo AND m.codigo_modelo = 'D3-001';
		UPDATE pedidos SET estado = 'CONFIRMADO' WHERE id_pedido = v_pedido;

		RAISE NOTICE 'A. Cabecera: %', (SELECT ref_odoo || ' | ' || tipo || ' | ' || estado || ' | ' || importe_total || ' €' FROM pedidos WHERE id_pedido = v_pedido);
		FOR v_fila IN
			SELECT a.talla, l.cantidad, l.precio_unitario, l.subtotal_linea
			FROM lineas_pedido l JOIN almacen a ON a.id_almacen = l.id_almacen
			WHERE l.id_pedido = v_pedido ORDER BY a.talla
		LOOP
			RAISE NOTICE 'A. Línea talla %: % pares x % = %', v_fila.talla, v_fila.cantidad, v_fila.precio_unitario, v_fila.subtotal_linea;
		END LOOP;
		RAISE NOTICE 'A. Stock Runner X antes:   %', v_stock_antes;
		RAISE NOTICE 'A. Stock Runner X después: %', (SELECT string_agg(a.talla || ':' || a.stock_disponible, ' ' ORDER BY a.talla)
			FROM almacen a JOIN modelos m ON m.id_modelo = a.id_modelo WHERE m.codigo_modelo = 'D3-001' AND a.talla IN (38, 39, 40, 42));
		FOR v_fila IN
			SELECT to_char(l.fecha_hora, 'YYYY-MM-DD HH24:MI:SS') AS hora, u.username, l.accion, l.resumen_cambios
			FROM log_eventos l LEFT JOIN usuarios u ON u.id_usuario = l.id_usuario
			WHERE l.id_evento > v_primer_evento ORDER BY l.id_evento
		LOOP
			RAISE NOTICE 'A. Auditoría: % | % | % | %', v_fila.hora, v_fila.username, v_fila.accion, v_fila.resumen_cambios;
		END LOOP;

		-- B. Otro pedido Custom de 20 pares en talla 40 (quedan 2): se rechaza entero
		BEGIN
			INSERT INTO pedidos (ref_odoo, id_cliente, id_usuario, tipo) VALUES ('SO101', v_cliente, v_comercial, 'CUSTOM')
			RETURNING id_pedido INTO v_otro;
			INSERT INTO lineas_pedido (id_pedido, id_almacen, id_personalizacion, cantidad, precio_unitario)
			SELECT v_otro, a.id_almacen, v_diseno, t.cantidad, 0
			FROM (VALUES (36, 5), (40, 15)) t (talla, cantidad)
			JOIN almacen a ON a.talla = t.talla
			JOIN modelos m ON m.id_modelo = a.id_modelo AND m.codigo_modelo = 'D3-001';
			UPDATE pedidos SET estado = 'CONFIRMADO' WHERE id_pedido = v_otro;
			RAISE NOTICE 'ERROR EN LA PRUEBA: se ha confirmado sin stock';
		EXCEPTION WHEN raise_exception THEN
			RAISE NOTICE 'B. Rechazado: %', SQLERRM;
		END;
		RAISE NOTICE 'B. Sin cambios parciales: talla 36 = % (sigue igual), talla 40 = %, ¿existe SO101? %',
			(SELECT a.stock_disponible FROM almacen a JOIN modelos m ON m.id_modelo = a.id_modelo WHERE m.codigo_modelo = 'D3-001' AND a.talla = 36),
			(SELECT a.stock_disponible FROM almacen a JOIN modelos m ON m.id_modelo = a.id_modelo WHERE m.codigo_modelo = 'D3-001' AND a.talla = 40),
			(SELECT COUNT(*) FROM pedidos WHERE ref_odoo = 'SO101');
		RAISE NOTICE 'B. Ningún stock negativo: %', (SELECT COUNT(*) FROM almacen WHERE stock_disponible < 0);

		-- C. Cancelar el pedido confirmado
		UPDATE pedidos SET estado = 'CANCELADO' WHERE id_pedido = v_pedido;
		RAISE NOTICE 'C. Estado: %. Stock Runner X tras cancelar: %', (SELECT estado FROM pedidos WHERE id_pedido = v_pedido),
			(SELECT string_agg(a.talla || ':' || a.stock_disponible, ' ' ORDER BY a.talla)
			 FROM almacen a JOIN modelos m ON m.id_modelo = a.id_modelo WHERE m.codigo_modelo = 'D3-001' AND a.talla IN (38, 39, 40, 42));
		RAISE NOTICE 'C. Auditoría: %', (SELECT to_char(fecha_hora, 'YYYY-MM-DD HH24:MI:SS') || ' | ' || accion || ' | ' || resumen_cambios
			FROM log_eventos ORDER BY id_evento DESC LIMIT 1);
		RAISE EXCEPTION 'deshacer';
	EXCEPTION WHEN raise_exception THEN
		IF SQLERRM <> 'deshacer' THEN RAISE; END IF;
	END;
	RAISE NOTICE 'Cambios deshechos. ¿Existe SO100? %', (SELECT COUNT(*) FROM pedidos WHERE ref_odoo = 'SO100');
END $$;

-- PRUEBA 9. ROLLBACK deliberado (prueba D): ni el cambio ni su auditoría quedan.
-- Se usa una transacción normal con BEGIN ... ROLLBACK. Para ver además que otra
-- conexión no ve nada hasta el COMMIT, está prueba_d_dos_conexiones.sql.
BEGIN;
SELECT set_config('app.id_usuario', (SELECT id_usuario::TEXT FROM usuarios WHERE username = 'comercial1'), true);
SELECT 'Antes' AS momento, (SELECT estado FROM pedidos WHERE ref_odoo = 'SO012') AS estado_so012,
       (SELECT COUNT(*) FROM log_eventos) AS eventos_auditoria,
       (SELECT a.stock_disponible FROM almacen a JOIN lineas_pedido l ON l.id_almacen = a.id_almacen
        JOIN pedidos p ON p.id_pedido = l.id_pedido WHERE p.ref_odoo = 'SO012') AS stock_xt6_41;
UPDATE pedidos SET estado = 'CONFIRMADO' WHERE ref_odoo = 'SO012';
SELECT 'Dentro de la transacción' AS momento, (SELECT estado FROM pedidos WHERE ref_odoo = 'SO012') AS estado_so012,
       (SELECT COUNT(*) FROM log_eventos) AS eventos_auditoria,
       (SELECT a.stock_disponible FROM almacen a JOIN lineas_pedido l ON l.id_almacen = a.id_almacen
        JOIN pedidos p ON p.id_pedido = l.id_pedido WHERE p.ref_odoo = 'SO012') AS stock_xt6_41;
ROLLBACK;
SELECT 'Después del ROLLBACK' AS momento, (SELECT estado FROM pedidos WHERE ref_odoo = 'SO012') AS estado_so012,
       (SELECT COUNT(*) FROM log_eventos) AS eventos_auditoria,
       (SELECT a.stock_disponible FROM almacen a JOIN lineas_pedido l ON l.id_almacen = a.id_almacen
        JOIN pedidos p ON p.id_pedido = l.id_pedido WHERE p.ref_odoo = 'SO012') AS stock_xt6_41;

-- PRUEBA 10. Inicio de sesión por rol (3.8)
-- Se crean tres usuarios temporales con contraseña conocida (uno por rol), se
-- comprueba fn_login y se deshace todo. Las contraseñas de los usuarios reales
-- no están en el repositorio.
DO $$
DECLARE
	v_fila RECORD;
BEGIN
	RAISE NOTICE '--- PRUEBA 10: inicio de sesión por rol ---';
	BEGIN
		PERFORM fn_crear_usuario('prueba_admin', 'Clave.Prueba1', 'ADMIN');
		PERFORM fn_crear_usuario('prueba_comercial', 'Clave.Prueba2', 'COMERCIAL');
		PERFORM fn_crear_usuario('prueba_usuario', 'Clave.Prueba3', 'USUARIO', (SELECT id_cliente FROM clientes WHERE codigo_odoo = 'CLI007'));
		FOR v_fila IN
			SELECT u.username, f.rol
			FROM (VALUES ('prueba_admin', 'Clave.Prueba1'), ('prueba_comercial', 'Clave.Prueba2'), ('prueba_usuario', 'Clave.Prueba3')) u (username, clave)
			LEFT JOIN LATERAL fn_login(u.username, u.clave) f ON TRUE
		LOOP
			RAISE NOTICE 'Login % -> rol %', v_fila.username, COALESCE(v_fila.rol, 'RECHAZADO');
		END LOOP;
		RAISE NOTICE 'Login prueba_admin con contraseña errónea -> % filas', (SELECT COUNT(*) FROM fn_login('prueba_admin', 'mala'));
		UPDATE usuarios SET activo = FALSE WHERE username = 'prueba_comercial';
		RAISE NOTICE 'Login prueba_comercial desactivado -> % filas', (SELECT COUNT(*) FROM fn_login('prueba_comercial', 'Clave.Prueba2'));
		RAISE NOTICE 'Hash guardado (inicio): %...', (SELECT LEFT(password_hash, 7) FROM usuarios WHERE username = 'prueba_admin');
		RAISE EXCEPTION 'deshacer';
	EXCEPTION WHEN raise_exception THEN
		IF SQLERRM <> 'deshacer' THEN RAISE; END IF;
	END;
END $$;

-- PRUEBA 11. Gestión de usuarios y permisos (3.8 y 3.11)
-- admin crea, cambia de rol y desactiva un usuario; cada paso queda en log_eventos
-- con su usuario y su hora. comercial1 intenta lo mismo y se rechaza sin cambios.
DO $$
DECLARE
	v_admin INTEGER;
	v_comercial INTEGER;
	v_nuevo INTEGER;
	v_primer_evento INTEGER;
	v_fila RECORD;
BEGIN
	RAISE NOTICE '--- PRUEBA 11: gestión de usuarios ---';
	SELECT id_usuario INTO v_admin FROM usuarios WHERE username = 'admin';
	SELECT id_usuario INTO v_comercial FROM usuarios WHERE username = 'comercial1';
	BEGIN
		SELECT COALESCE(MAX(id_evento), 0) INTO v_primer_evento FROM log_eventos;
		PERFORM set_config('app.id_usuario', v_admin::TEXT, true);
		v_nuevo := fn_crear_usuario('almacen1', 'Almacen.2026', 'COMERCIAL');
		RAISE NOTICE 'JSON tras crear: %', (SELECT json_agg(e ->> 'username' || CASE WHEN (e ->> 'activo')::BOOLEAN THEN '' ELSE ' (inactivo)' END)
			FROM json_array_elements(fn_exportar_usuarios(v_admin)) e);
		UPDATE usuarios SET id_rol = (SELECT id_rol FROM roles WHERE nombre_rol = 'ADMIN') WHERE id_usuario = v_nuevo;
		UPDATE usuarios SET id_rol = (SELECT id_rol FROM roles WHERE nombre_rol = 'COMERCIAL') WHERE id_usuario = v_nuevo;
		UPDATE usuarios SET activo = FALSE WHERE id_usuario = v_nuevo;
		RAISE NOTICE 'JSON tras desactivar: %', (SELECT json_agg(e ->> 'username' || CASE WHEN (e ->> 'activo')::BOOLEAN THEN '' ELSE ' (inactivo)' END)
			FROM json_array_elements(fn_exportar_usuarios(v_admin)) e);
		RAISE NOTICE '¿El JSON contiene algún hash? %', (fn_exportar_usuarios(v_admin)::TEXT LIKE '%$2a$%');
		FOR v_fila IN
			SELECT to_char(l.fecha_hora, 'YYYY-MM-DD HH24:MI:SS') AS hora, u.username, l.accion, l.resumen_cambios
			FROM log_eventos l LEFT JOIN usuarios u ON u.id_usuario = l.id_usuario
			WHERE l.id_evento > v_primer_evento ORDER BY l.id_evento
		LOOP
			RAISE NOTICE 'Auditoría: % | % | % | %', v_fila.hora, v_fila.username, v_fila.accion, v_fila.resumen_cambios;
		END LOOP;

		BEGIN
			UPDATE permisos_rol SET permitido = FALSE
			WHERE operacion = 'USUARIOS_GESTIONAR' AND id_rol = (SELECT id_rol FROM roles WHERE nombre_rol = 'ADMIN');
			RAISE NOTICE 'ERROR EN LA PRUEBA: el ADMIN ha perdido un permiso';
		EXCEPTION WHEN raise_exception THEN
			RAISE NOTICE 'Rechazado quitar permisos al ADMIN: %', SQLERRM;
		END;

		PERFORM set_config('app.id_usuario', v_comercial::TEXT, true);
		BEGIN
			PERFORM fn_crear_usuario('intruso', 'Intruso.2026', 'ADMIN');
			RAISE NOTICE 'ERROR EN LA PRUEBA: comercial1 ha creado un usuario';
		EXCEPTION WHEN raise_exception THEN
			RAISE NOTICE 'Rechazado crear usuario: %', SQLERRM;
		END;
		BEGIN
			PERFORM fn_exportar_usuarios(v_comercial);
			RAISE NOTICE 'ERROR EN LA PRUEBA: comercial1 ha exportado los usuarios';
		EXCEPTION WHEN raise_exception THEN
			RAISE NOTICE 'Rechazado exportar usuarios: %', SQLERRM;
		END;
		RAISE NOTICE '¿Existe intruso? %', (SELECT COUNT(*) FROM usuarios WHERE username = 'intruso');
		RAISE EXCEPTION 'deshacer';
	EXCEPTION WHEN raise_exception THEN
		IF SQLERRM <> 'deshacer' THEN RAISE; END IF;
	END;
END $$;

-- PRUEBA 12. Búsqueda con filtros y permisos en PostgreSQL (3.7, pruebas E y F)
DO $$
DECLARE
	v_comercial INTEGER;
	v_laura INTEGER;
BEGIN
	RAISE NOTICE '--- PRUEBA 12: búsqueda con filtros ---';
	SELECT id_usuario INTO v_comercial FROM usuarios WHERE username = 'comercial1';
	SELECT id_usuario INTO v_laura FROM usuarios WHERE username = 'laura.martin@example.com';
	RAISE NOTICE 'Sin filtros: % pedidos (SQL directo: %)', (SELECT COUNT(*) FROM fn_buscar_pedidos(v_comercial)), (SELECT COUNT(*) FROM pedidos);
	RAISE NOTICE 'Cliente Halcones + ENTREGADO: %', (SELECT string_agg(ref_odoo, ', ') FROM fn_buscar_pedidos(v_comercial, 'Halcones', NULL, 'ENTREGADO'));
	RAISE NOTICE 'Modelo Runner X + entre junio y julio: %', (SELECT string_agg(ref_odoo, ', ') FROM fn_buscar_pedidos(v_comercial, NULL, 'Runner X', NULL, '2026-06-01', '2026-07-31'));
	RAISE NOTICE 'Sin coincidencias: % filas', (SELECT COUNT(*) FROM fn_buscar_pedidos(v_comercial, 'Nadie'));
	RAISE NOTICE 'Laura sin filtros (solo los suyos): %', (SELECT string_agg(ref_odoo, ', ') FROM fn_buscar_pedidos(v_laura));
	RAISE NOTICE 'Laura pidiendo los de Club Halcones: % filas', (SELECT COUNT(*) FROM fn_buscar_pedidos(v_laura, 'Halcones'));
	BEGIN
		PERFORM * FROM fn_buscar_pedidos(v_comercial, NULL, NULL, 'PERDIDO');
	EXCEPTION WHEN raise_exception THEN
		RAISE NOTICE 'Consulta incorrecta: %', SQLERRM;
	END;
	BEGIN
		PERFORM * FROM fn_buscar_pedidos(NULL);
	EXCEPTION WHEN raise_exception THEN
		RAISE NOTICE 'Sin sesión: %', SQLERRM;
	END;
END $$;

-- PRUEBA 13. Indicadores y stock bajo comparados con SQL directo (3.12, prueba J)
DO $$
DECLARE
	v_comercial INTEGER;
	v_i RECORD;
BEGIN
	RAISE NOTICE '--- PRUEBA 13: indicadores y stock bajo ---';
	SELECT id_usuario INTO v_comercial FROM usuarios WHERE username = 'comercial1';
	SELECT * INTO v_i FROM fn_indicadores(v_comercial);
	RAISE NOTICE 'fn_indicadores: % pedidos, % válidos, % pares, % €, estados B/C/E/X = %/%/%/%',
		v_i.pedidos_totales, v_i.pedidos_validos, v_i.pares_vendidos, v_i.importe_ventas,
		v_i.borrador, v_i.confirmado, v_i.entregado, v_i.cancelado;
	RAISE NOTICE 'SQL directo:    % pedidos, % válidos, % pares, % €',
		(SELECT COUNT(*) FROM pedidos),
		(SELECT COUNT(*) FROM pedidos WHERE estado IN ('CONFIRMADO', 'ENTREGADO')),
		(SELECT SUM(l.cantidad) FROM lineas_pedido l JOIN pedidos p ON p.id_pedido = l.id_pedido WHERE p.estado IN ('CONFIRMADO', 'ENTREGADO')),
		(SELECT SUM(importe_total) FROM pedidos WHERE estado IN ('CONFIRMADO', 'ENTREGADO'));
	RAISE NOTICE 'Stock bajo con umbral 10: %', (SELECT string_agg(modelo || ' ' || talla || ' (' || stock_disponible || ')', '; ') FROM fn_stock_bajo(v_comercial, 10));
	RAISE NOTICE 'Stock bajo con el mínimo de cada talla: %', (SELECT string_agg(modelo || ' ' || talla || ' (' || stock_disponible || ')', '; ') FROM fn_stock_bajo(v_comercial));
	BEGIN
		PERFORM * FROM fn_indicadores((SELECT id_usuario FROM usuarios WHERE username = 'laura.martin@example.com'));
	EXCEPTION WHEN raise_exception THEN
		RAISE NOTICE 'Laura pide los indicadores: %', SQLERRM;
	END;
END $$;
