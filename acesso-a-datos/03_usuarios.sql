CREATE EXTENSION IF NOT EXISTS pgcrypto;

INSERT INTO roles (nombre_rol, descripcion) VALUES
 	('ADMIN', 'Administración: acceso completo, incluida la gestión de usuarios, roles y permisos'),
 	('COMERCIAL', 'Ventas: crea, edita, confirma y cancela pedidos de clientes'),
 	('ALMACEN', 'Almacén y producción: consulta pedidos y stock, marca pedidos entregados y prepara fichas de fabricación'),
+	('CLIENTE_WEB', 'Cliente registrado desde la web'),
+	('INVITADO_WEB', 'Usuario genérico para navegación web sin registro')
 ON CONFLICT (nombre_rol) DO UPDATE SET descripcion = EXCLUDED.descripcion;

INSERT INTO permisos_rol (id_rol, operacion, permitido)
SELECT r.id_rol, m.operacion, m.permitido
FROM (VALUES
	('ADMIN', 'PEDIDO_CONSULTAR', TRUE),
	('ADMIN', 'PEDIDO_CREAR', TRUE),
	('ADMIN', 'PEDIDO_EDITAR', TRUE),
	('ADMIN', 'PEDIDO_CONFIRMAR', TRUE),
	('ADMIN', 'PEDIDO_CANCELAR', TRUE),
	('ADMIN', 'PEDIDO_ENTREGAR', TRUE),
	('ADMIN', 'STOCK_CONSULTAR', TRUE),
	('ADMIN', 'INDICADORES_VER', TRUE),
	('ADMIN', 'DATOS_EXPORTAR', TRUE),
	('ADMIN', 'AUDITORIA_VER', TRUE),
	('ADMIN', 'USUARIOS_GESTIONAR', TRUE),
	('ADMIN', 'USUARIOS_EXPORTAR', TRUE),
	('COMERCIAL', 'PEDIDO_CONSULTAR', TRUE),
	('COMERCIAL', 'PEDIDO_CREAR', TRUE),
	('COMERCIAL', 'PEDIDO_EDITAR', TRUE),
	('COMERCIAL', 'PEDIDO_CONFIRMAR', TRUE),
	('COMERCIAL', 'PEDIDO_CANCELAR', TRUE),
	('COMERCIAL', 'PEDIDO_ENTREGAR', FALSE),
	('COMERCIAL', 'STOCK_CONSULTAR', TRUE),
	('COMERCIAL', 'INDICADORES_VER', TRUE),
	('COMERCIAL', 'DATOS_EXPORTAR', TRUE),
	('COMERCIAL', 'AUDITORIA_VER', FALSE),
	('COMERCIAL', 'USUARIOS_GESTIONAR', FALSE),
	('COMERCIAL', 'USUARIOS_EXPORTAR', FALSE),
	('ALMACEN', 'PEDIDO_CONSULTAR', TRUE),
	('ALMACEN', 'PEDIDO_CREAR', FALSE),
	('ALMACEN', 'PEDIDO_EDITAR', FALSE),
	('ALMACEN', 'PEDIDO_CONFIRMAR', FALSE),
	('ALMACEN', 'PEDIDO_CANCELAR', FALSE),
	('ALMACEN', 'PEDIDO_ENTREGAR', TRUE),
	('ALMACEN', 'STOCK_CONSULTAR', TRUE),
	('ALMACEN', 'INDICADORES_VER', TRUE),
	('ALMACEN', 'DATOS_EXPORTAR', TRUE),
	('ALMACEN', 'AUDITORIA_VER', FALSE),
	('ALMACEN', 'USUARIOS_GESTIONAR', FALSE),
	('ALMACEN', 'USUARIOS_EXPORTAR', FALSE)
	('ALMACEN', 'AUDITORIA_VER', FALSE),
 	('ALMACEN', 'USUARIOS_GESTIONAR', FALSE),
 	('ALMACEN', 'USUARIOS_EXPORTAR', FALSE),
+	('CLIENTE_WEB', 'PEDIDO_CREAR', TRUE),
+	('CLIENTE_WEB', 'PEDIDO_CONSULTAR', TRUE),
+	('INVITADO_WEB', 'PEDIDO_CREAR', TRUE)
) AS m (rol, operacion, permitido)
JOIN roles r ON r.nombre_rol = m.rol
ON CONFLICT (id_rol, operacion) DO UPDATE SET permitido = EXCLUDED.permitido;

INSERT INTO usuarios (username, password_hash, id_rol, activo)
SELECT u.username, u.password_hash, r.id_rol, TRUE
FROM (VALUES
	('admin', '$2a$10$CghyE6PQ6CTH5vB.07Mm7epWudFnuWy9pMW4rZurDK7Pvk7/wC0Ei', 'ADMIN'),
 	('comercial1', '$2a$10$Z.Cxcf9UxSBOIKyNpEHkguBkXZLjL30a94JFD/6YO25.IorD96sfa', 'COMERCIAL'),
 	('almacen1', '$2a$10$Mn9OTksnJl6UPMScnt2kfupAnGF32chK2nOU1ahyqOuibTjD0JY8.', 'ALMACEN'),
+	('invitado_web', '$2a$10$simulacionhashinvitado12345678901234567890123456789', 'INVITADO_WEB')
 ) AS u (username, password_hash, rol)
JOIN roles r ON r.nombre_rol = u.rol
ON CONFLICT (username) DO NOTHING;

CREATE OR REPLACE FUNCTION fn_login(p_username VARCHAR, p_password VARCHAR)
RETURNS TABLE (id_usuario INTEGER, username VARCHAR, rol VARCHAR) AS $$
	SELECT u.id_usuario, u.username, r.nombre_rol
	FROM usuarios u
	JOIN roles r ON r.id_rol = u.id_rol
	WHERE u.username = p_username
	  AND u.activo
	  AND u.password_hash = crypt(p_password, u.password_hash);
$$ LANGUAGE sql;

CREATE OR REPLACE FUNCTION fn_tiene_permiso(p_id_usuario INTEGER, p_operacion VARCHAR)
RETURNS BOOLEAN AS $$
	SELECT COALESCE((
		SELECT pr.permitido
		FROM usuarios u
		JOIN permisos_rol pr ON pr.id_rol = u.id_rol
		WHERE u.id_usuario = p_id_usuario
		  AND u.activo
		  AND pr.operacion = p_operacion
	), FALSE);
$$ LANGUAGE sql;

CREATE OR REPLACE FUNCTION fn_comprobar_permiso()
RETURNS TRIGGER AS $$
DECLARE
	v_id_usuario INTEGER;
	v_operacion VARCHAR(60);
BEGIN
	IF pg_trigger_depth() > 1 THEN
		RETURN COALESCE(NEW, OLD);
	END IF;

	v_id_usuario := NULLIF(current_setting('app.id_usuario', true), '')::INTEGER;
	IF v_id_usuario IS NULL THEN
		RETURN COALESCE(NEW, OLD);
	END IF;

	IF TG_TABLE_NAME = 'lineas_pedido' THEN
		v_operacion := 'PEDIDO_EDITAR';
	ELSIF TG_OP = 'INSERT' THEN
		v_operacion := 'PEDIDO_CREAR';
	ELSIF TG_OP = 'DELETE' THEN
		RAISE EXCEPTION 'Los pedidos no se borran: hay que cancelarlos';
	ELSIF NEW.estado <> OLD.estado THEN
		v_operacion := CASE NEW.estado
			WHEN 'CONFIRMADO' THEN 'PEDIDO_CONFIRMAR'
			WHEN 'CANCELADO' THEN 'PEDIDO_CANCELAR'
			WHEN 'ENTREGADO' THEN 'PEDIDO_ENTREGAR'
			ELSE 'PEDIDO_EDITAR'
		END;
	ELSE
		v_operacion := 'PEDIDO_EDITAR';
	END IF;

	IF NOT fn_tiene_permiso(v_id_usuario, v_operacion) THEN
		RAISE EXCEPTION 'Permiso denegado: el usuario % no puede realizar la operación %', v_id_usuario, v_operacion;
	END IF;

	RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_permisos_pedidos ON pedidos;
CREATE TRIGGER trg_permisos_pedidos
BEFORE INSERT OR UPDATE OR DELETE ON pedidos
FOR EACH ROW EXECUTE FUNCTION fn_comprobar_permiso();

DROP TRIGGER IF EXISTS trg_permisos_lineas ON lineas_pedido;
CREATE TRIGGER trg_permisos_lineas
BEFORE INSERT OR UPDATE OR DELETE ON lineas_pedido
FOR EACH ROW EXECUTE FUNCTION fn_comprobar_permiso();

CREATE OR REPLACE FUNCTION fn_usuarios_json()
RETURNS JSON AS $$
	SELECT COALESCE(json_agg(json_build_object(
		'id_usuario', u.id_usuario,
		'username', u.username,
		'rol', r.nombre_rol,
		'activo', u.activo,
		'fecha_creacion', to_char(u.fecha_creacion, 'YYYY-MM-DD HH24:MI:SS')
	) ORDER BY u.id_usuario), '[]'::json)
	FROM usuarios u
	JOIN roles r ON r.id_rol = u.id_rol;
$$ LANGUAGE sql;
