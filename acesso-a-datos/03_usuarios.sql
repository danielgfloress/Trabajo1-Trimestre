CREATE EXTENSION IF NOT EXISTS pgcrypto;

INSERT INTO roles (nombre_rol, descripcion) VALUES
	('ADMIN', 'Administración: acceso completo, incluida la gestión de usuarios, productos y permisos'),
	('COMERCIAL', 'Ventas: crea, edita, confirma, cancela y entrega pedidos de clientes'),
	('USUARIO', 'Cliente registrado en la web: crea y consulta solo sus propios pedidos')
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
	('ADMIN', 'PRODUCTO_EDITAR', TRUE),
	('ADMIN', 'STOCK_EDITAR', TRUE),
	('COMERCIAL', 'PEDIDO_CONSULTAR', TRUE),
	('COMERCIAL', 'PEDIDO_CREAR', TRUE),
	('COMERCIAL', 'PEDIDO_EDITAR', TRUE),
	('COMERCIAL', 'PEDIDO_CONFIRMAR', TRUE),
	('COMERCIAL', 'PEDIDO_CANCELAR', TRUE),
	('COMERCIAL', 'PEDIDO_ENTREGAR', TRUE),
	('COMERCIAL', 'STOCK_CONSULTAR', TRUE),
	('COMERCIAL', 'INDICADORES_VER', TRUE),
	('COMERCIAL', 'DATOS_EXPORTAR', TRUE),
	('COMERCIAL', 'AUDITORIA_VER', FALSE),
	('COMERCIAL', 'USUARIOS_GESTIONAR', FALSE),
	('COMERCIAL', 'USUARIOS_EXPORTAR', FALSE),
	('COMERCIAL', 'PRODUCTO_EDITAR', FALSE),
	('COMERCIAL', 'STOCK_EDITAR', FALSE),
	('USUARIO', 'PEDIDO_CONSULTAR', TRUE),
	('USUARIO', 'PEDIDO_CREAR', TRUE),
	('USUARIO', 'PEDIDO_EDITAR', TRUE),
	('USUARIO', 'PEDIDO_CONFIRMAR', FALSE),
	('USUARIO', 'PEDIDO_CANCELAR', FALSE),
	('USUARIO', 'PEDIDO_ENTREGAR', FALSE),
	('USUARIO', 'STOCK_CONSULTAR', TRUE),
	('USUARIO', 'INDICADORES_VER', FALSE),
	('USUARIO', 'DATOS_EXPORTAR', FALSE),
	('USUARIO', 'AUDITORIA_VER', FALSE),
	('USUARIO', 'USUARIOS_GESTIONAR', FALSE),
	('USUARIO', 'USUARIOS_EXPORTAR', FALSE),
	('USUARIO', 'PRODUCTO_EDITAR', FALSE),
	('USUARIO', 'STOCK_EDITAR', FALSE)
) AS m (rol, operacion, permitido)
JOIN roles r ON r.nombre_rol = m.rol
ON CONFLICT (id_rol, operacion) DO UPDATE SET permitido = EXCLUDED.permitido;

INSERT INTO usuarios (username, password_hash, id_rol, activo)
SELECT u.username, u.password_hash, r.id_rol, TRUE
FROM (VALUES
	('admin', '$2a$10$CghyE6PQ6CTH5vB.07Mm7epWudFnuWy9pMW4rZurDK7Pvk7/wC0Ei', 'ADMIN'),
	('comercial1', '$2a$10$Z.Cxcf9UxSBOIKyNpEHkguBkXZLjL30a94JFD/6YO25.IorD96sfa', 'COMERCIAL')
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
	v_cliente_usuario INTEGER;
	v_cliente_pedido INTEGER;
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

	SELECT id_cliente INTO v_cliente_usuario FROM usuarios WHERE id_usuario = v_id_usuario;
	IF v_cliente_usuario IS NOT NULL THEN
		IF TG_TABLE_NAME = 'pedidos' THEN
			v_cliente_pedido := NEW.id_cliente;
			IF TG_OP = 'UPDATE' AND OLD.id_cliente IS DISTINCT FROM v_cliente_usuario THEN
				v_cliente_pedido := OLD.id_cliente;
			END IF;
		ELSE
			SELECT id_cliente INTO v_cliente_pedido FROM pedidos
			WHERE id_pedido = COALESCE(NEW.id_pedido, OLD.id_pedido);
		END IF;
		IF v_cliente_pedido IS DISTINCT FROM v_cliente_usuario THEN
			RAISE EXCEPTION 'Permiso denegado: el usuario % solo puede gestionar los pedidos de su propio cliente', v_id_usuario;
		END IF;
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

CREATE OR REPLACE FUNCTION fn_comprobar_permiso_catalogo()
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

	IF TG_TABLE_NAME = 'modelos' THEN
		v_operacion := 'PRODUCTO_EDITAR';
	ELSE
		v_operacion := 'STOCK_EDITAR';
	END IF;

	IF NOT fn_tiene_permiso(v_id_usuario, v_operacion) THEN
		RAISE EXCEPTION 'Permiso denegado: el usuario % no puede realizar la operación %', v_id_usuario, v_operacion;
	END IF;

	RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_permisos_modelos ON modelos;
CREATE TRIGGER trg_permisos_modelos
BEFORE INSERT OR UPDATE OR DELETE ON modelos
FOR EACH ROW EXECUTE FUNCTION fn_comprobar_permiso_catalogo();

DROP TRIGGER IF EXISTS trg_permisos_almacen ON almacen;
CREATE TRIGGER trg_permisos_almacen
BEFORE INSERT OR UPDATE OR DELETE ON almacen
FOR EACH ROW EXECUTE FUNCTION fn_comprobar_permiso_catalogo();

CREATE OR REPLACE FUNCTION fn_usuarios_json()
RETURNS JSON AS $$
	SELECT COALESCE(json_agg(json_build_object(
		'id_usuario', u.id_usuario,
		'username', u.username,
		'rol', r.nombre_rol,
		'activo', u.activo,
		'id_cliente', u.id_cliente,
		'fecha_creacion', to_char(u.fecha_creacion, 'YYYY-MM-DD HH24:MI:SS')
	) ORDER BY u.id_usuario), '[]'::json)
	FROM usuarios u
	JOIN roles r ON r.id_rol = u.id_rol;
$$ LANGUAGE sql;
