CREATE OR REPLACE FUNCTION fn_exigir_permiso(p_id_usuario INTEGER, p_operacion VARCHAR)
RETURNS VOID AS $$
BEGIN
	IF p_id_usuario IS NULL OR NOT fn_tiene_permiso(p_id_usuario, p_operacion) THEN
		RAISE EXCEPTION 'Permiso denegado: el usuario % no puede realizar la operación %',
			COALESCE(p_id_usuario::TEXT, '(sin sesión)'), p_operacion;
	END IF;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION fn_buscar_pedidos(
	p_id_usuario INTEGER,
	p_cliente VARCHAR DEFAULT NULL,
	p_modelo VARCHAR DEFAULT NULL,
	p_estado VARCHAR DEFAULT NULL,
	p_desde DATE DEFAULT NULL,
	p_hasta DATE DEFAULT NULL)
RETURNS TABLE (ref_odoo VARCHAR, cliente VARCHAR, fecha_pedido TIMESTAMP, tipo VARCHAR,
               estado VARCHAR, pares BIGINT, importe_total NUMERIC) AS $$
DECLARE
	v_cliente_usuario INTEGER;
BEGIN
	PERFORM fn_exigir_permiso(p_id_usuario, 'PEDIDO_CONSULTAR');

	IF p_estado IS NOT NULL AND p_estado NOT IN ('BORRADOR', 'CONFIRMADO', 'ENTREGADO', 'CANCELADO') THEN
		RAISE EXCEPTION 'El estado % no existe', p_estado;
	END IF;
	IF p_desde IS NOT NULL AND p_hasta IS NOT NULL AND p_desde > p_hasta THEN
		RAISE EXCEPTION 'La fecha inicial es posterior a la final';
	END IF;

	SELECT u.id_cliente INTO v_cliente_usuario FROM usuarios u WHERE u.id_usuario = p_id_usuario;

	RETURN QUERY
	SELECT p.ref_odoo, c.nombre, p.fecha_pedido, p.tipo, p.estado,
	       (SELECT COALESCE(SUM(l.cantidad), 0) FROM lineas_pedido l WHERE l.id_pedido = p.id_pedido),
	       p.importe_total
	FROM pedidos p
	JOIN clientes c ON c.id_cliente = p.id_cliente
	WHERE (v_cliente_usuario IS NULL OR p.id_cliente = v_cliente_usuario)
	  AND (p_cliente IS NULL OR c.nombre ILIKE '%' || p_cliente || '%' OR c.codigo_odoo = upper(p_cliente))
	  AND (p_modelo IS NULL OR EXISTS (
	          SELECT 1 FROM lineas_pedido l
	          JOIN almacen a ON a.id_almacen = l.id_almacen
	          JOIN modelos m ON m.id_modelo = a.id_modelo
	          WHERE l.id_pedido = p.id_pedido
	            AND (m.nombre ILIKE '%' || p_modelo || '%' OR m.codigo_modelo = upper(p_modelo))))
	  AND (p_estado IS NULL OR p.estado = p_estado)
	  AND (p_desde IS NULL OR p.fecha_pedido >= p_desde)
	  AND (p_hasta IS NULL OR p.fecha_pedido < p_hasta + 1)
	ORDER BY p.fecha_pedido DESC, p.ref_odoo;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION fn_indicadores(p_id_usuario INTEGER)
RETURNS TABLE (pedidos_totales BIGINT, pedidos_validos BIGINT, pares_vendidos BIGINT,
               importe_ventas NUMERIC, borrador BIGINT, confirmado BIGINT,
               entregado BIGINT, cancelado BIGINT) AS $$
BEGIN
	PERFORM fn_exigir_permiso(p_id_usuario, 'INDICADORES_VER');
	RETURN QUERY
	SELECT COUNT(*),
	       COUNT(*) FILTER (WHERE p.estado IN ('CONFIRMADO', 'ENTREGADO')),
	       (SELECT COALESCE(SUM(l.cantidad), 0)::BIGINT
	        FROM lineas_pedido l JOIN pedidos v ON v.id_pedido = l.id_pedido
	        WHERE v.estado IN ('CONFIRMADO', 'ENTREGADO')),
	       COALESCE(SUM(p.importe_total) FILTER (WHERE p.estado IN ('CONFIRMADO', 'ENTREGADO')), 0),
	       COUNT(*) FILTER (WHERE p.estado = 'BORRADOR'),
	       COUNT(*) FILTER (WHERE p.estado = 'CONFIRMADO'),
	       COUNT(*) FILTER (WHERE p.estado = 'ENTREGADO'),
	       COUNT(*) FILTER (WHERE p.estado = 'CANCELADO')
	FROM pedidos p;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION fn_stock_bajo(p_id_usuario INTEGER, p_umbral INTEGER DEFAULT NULL)
RETURNS TABLE (codigo_modelo VARCHAR, modelo VARCHAR, color VARCHAR, talla INTEGER,
               stock_disponible INTEGER, umbral INTEGER, faltan INTEGER) AS $$
BEGIN
	PERFORM fn_exigir_permiso(p_id_usuario, 'STOCK_CONSULTAR');
	IF p_umbral IS NOT NULL AND p_umbral < 0 THEN
		RAISE EXCEPTION 'El umbral no puede ser negativo';
	END IF;
	RETURN QUERY
	SELECT m.codigo_modelo, m.nombre, a.color_base, a.talla::INTEGER, a.stock_disponible::INTEGER,
	       COALESCE(p_umbral, a.stock_minimo)::INTEGER,
	       (COALESCE(p_umbral, a.stock_minimo) - a.stock_disponible)::INTEGER
	FROM almacen a
	JOIN modelos m ON m.id_modelo = a.id_modelo
	WHERE m.activo AND a.stock_disponible <= COALESCE(p_umbral, a.stock_minimo)
	ORDER BY a.stock_disponible, m.codigo_modelo, a.color_base, a.talla;
END;
$$ LANGUAGE plpgsql;


CREATE OR REPLACE FUNCTION fn_exportar_usuarios(p_id_usuario INTEGER)
RETURNS JSON AS $$
BEGIN
	PERFORM fn_exigir_permiso(p_id_usuario, 'USUARIOS_EXPORTAR');
	RETURN fn_usuarios_json();
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION fn_crear_usuario(p_username VARCHAR, p_password VARCHAR,
                                            p_rol VARCHAR, p_id_cliente INTEGER DEFAULT NULL)
RETURNS INTEGER AS $$
DECLARE
	v_id_rol INTEGER;
	v_id INTEGER;
BEGIN
	IF p_username IS NULL OR length(trim(p_username)) < 3 THEN
		RAISE EXCEPTION 'El nombre de usuario tiene que tener al menos 3 caracteres';
	END IF;
	IF p_password IS NULL OR length(p_password) < 8 THEN
		RAISE EXCEPTION 'La contraseña tiene que tener al menos 8 caracteres';
	END IF;
	SELECT id_rol INTO v_id_rol FROM roles WHERE nombre_rol = upper(p_rol);
	IF v_id_rol IS NULL THEN
		RAISE EXCEPTION 'El rol % no existe', p_rol;
	END IF;
	INSERT INTO usuarios (username, password_hash, id_rol, id_cliente)
	VALUES (lower(trim(p_username)), crypt(p_password, gen_salt('bf', 10)), v_id_rol, p_id_cliente)
	RETURNING id_usuario INTO v_id;
	RETURN v_id;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION fn_comprobar_permiso_usuarios()
RETURNS TRIGGER AS $$
DECLARE
	v_id_usuario INTEGER;
	v_id_admin INTEGER;
	v_pierde_admin BOOLEAN;
BEGIN
	SELECT id_rol INTO v_id_admin FROM roles WHERE nombre_rol = 'ADMIN';

	IF TG_TABLE_NAME = 'permisos_rol' AND TG_OP <> 'DELETE' THEN
		IF NEW.id_rol = v_id_admin AND NOT NEW.permitido THEN
			RAISE EXCEPTION 'El rol ADMIN tiene que conservar todos sus permisos';
		END IF;
	END IF;

	IF TG_TABLE_NAME = 'usuarios' AND TG_OP <> 'INSERT' THEN
		IF OLD.id_rol = v_id_admin AND OLD.activo THEN
			IF TG_OP = 'DELETE' THEN
				v_pierde_admin := TRUE;
			ELSE
				v_pierde_admin := NOT NEW.activo OR NEW.id_rol <> v_id_admin;
			END IF;
			IF v_pierde_admin THEN
				IF NOT EXISTS (SELECT 1 FROM usuarios u
				               WHERE u.id_rol = v_id_admin AND u.activo AND u.id_usuario <> OLD.id_usuario) THEN
					RAISE EXCEPTION 'Tiene que quedar al menos un administrador activo';
				END IF;
			END IF;
		END IF;
	END IF;

	IF pg_trigger_depth() > 1 THEN
		RETURN COALESCE(NEW, OLD);
	END IF;
	v_id_usuario := NULLIF(current_setting('app.id_usuario', true), '')::INTEGER;
	IF v_id_usuario IS NOT NULL AND NOT fn_tiene_permiso(v_id_usuario, 'USUARIOS_GESTIONAR') THEN
		RAISE EXCEPTION 'Permiso denegado: el usuario % no puede realizar la operación USUARIOS_GESTIONAR', v_id_usuario;
	END IF;
	RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_permisos_usuarios ON usuarios;
CREATE TRIGGER trg_permisos_usuarios
BEFORE INSERT OR UPDATE OR DELETE ON usuarios
FOR EACH ROW EXECUTE FUNCTION fn_comprobar_permiso_usuarios();

DROP TRIGGER IF EXISTS trg_permisos_roles ON roles;
CREATE TRIGGER trg_permisos_roles
BEFORE INSERT OR UPDATE OR DELETE ON roles
FOR EACH ROW EXECUTE FUNCTION fn_comprobar_permiso_usuarios();

DROP TRIGGER IF EXISTS trg_permisos_permisos_rol ON permisos_rol;
CREATE TRIGGER trg_permisos_permisos_rol
BEFORE INSERT OR UPDATE OR DELETE ON permisos_rol
FOR EACH ROW EXECUTE FUNCTION fn_comprobar_permiso_usuarios();

CREATE OR REPLACE FUNCTION fn_auditoria_usuarios()
RETURNS TRIGGER AS $$
DECLARE
	v_antiguo JSONB;
	v_nuevo JSONB;
	v_accion VARCHAR(60);
	v_resumen VARCHAR(500);
	v_id INTEGER;
	v_rol_antes VARCHAR(50);
	v_rol_despues VARCHAR(50);
BEGIN
	IF TG_OP <> 'INSERT' THEN v_antiguo := to_jsonb(OLD) - 'password_hash'; END IF;
	IF TG_OP <> 'DELETE' THEN v_nuevo := to_jsonb(NEW) - 'password_hash'; END IF;

	IF TG_TABLE_NAME = 'usuarios' THEN
		v_id := COALESCE(NEW.id_usuario, OLD.id_usuario);
		IF TG_OP = 'INSERT' THEN
			SELECT nombre_rol INTO v_rol_despues FROM roles WHERE id_rol = NEW.id_rol;
			v_accion := 'CREAR_USUARIO';
			v_resumen := 'Usuario ' || NEW.username || ' creado con el rol ' || v_rol_despues;
		ELSIF TG_OP = 'DELETE' THEN
			v_accion := 'BORRAR_USUARIO';
			v_resumen := 'Usuario ' || OLD.username || ' borrado';
		ELSIF NEW.id_rol <> OLD.id_rol THEN
			SELECT nombre_rol INTO v_rol_antes FROM roles WHERE id_rol = OLD.id_rol;
			SELECT nombre_rol INTO v_rol_despues FROM roles WHERE id_rol = NEW.id_rol;
			v_accion := 'CAMBIAR_ROL';
			v_resumen := 'Usuario ' || NEW.username || ': rol ' || v_rol_antes || ' -> ' || v_rol_despues;
		ELSIF NEW.activo <> OLD.activo THEN
			v_accion := CASE WHEN NEW.activo THEN 'ACTIVAR_USUARIO' ELSE 'DESACTIVAR_USUARIO' END;
			v_resumen := 'Usuario ' || NEW.username || CASE WHEN NEW.activo THEN ' activado' ELSE ' desactivado' END;
		ELSIF NEW.password_hash <> OLD.password_hash THEN
			v_accion := 'CAMBIAR_CONTRASENA';
			v_resumen := 'Usuario ' || NEW.username || ': contraseña cambiada';
		ELSE
			v_accion := 'MODIFICAR_USUARIO';
			v_resumen := 'Usuario ' || NEW.username || ' modificado';
		END IF;
	ELSE
		v_id := COALESCE(NEW.id_permiso, OLD.id_permiso);
		SELECT nombre_rol INTO v_rol_despues FROM roles WHERE id_rol = COALESCE(NEW.id_rol, OLD.id_rol);
		v_accion := 'CAMBIAR_PERMISO';
		v_resumen := 'Permiso ' || COALESCE(NEW.operacion, OLD.operacion) || ' del rol ' || v_rol_despues || ': '
			|| CASE WHEN TG_OP = 'DELETE' THEN 'borrado'
			        WHEN TG_OP = 'INSERT' THEN CASE WHEN NEW.permitido THEN 'concedido' ELSE 'denegado' END
			        ELSE CASE WHEN OLD.permitido THEN 'sí' ELSE 'no' END || ' -> ' || CASE WHEN NEW.permitido THEN 'sí' ELSE 'no' END END;
		IF TG_OP = 'UPDATE' AND NEW.permitido = OLD.permitido THEN
			RETURN NULL;
		END IF;
	END IF;

	INSERT INTO log_eventos (id_usuario, tabla_afectada, operacion, id_registro_afectado, resumen_cambios, accion, datos_antiguos, datos_nuevos)
	VALUES (NULLIF(current_setting('app.id_usuario', true), '')::INTEGER, TG_TABLE_NAME, TG_OP, v_id,
	        LEFT(v_resumen, 500), v_accion, v_antiguo, v_nuevo);
	RETURN NULL;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_auditoria_usuarios ON usuarios;
CREATE TRIGGER trg_auditoria_usuarios
AFTER INSERT OR UPDATE OR DELETE ON usuarios
FOR EACH ROW EXECUTE FUNCTION fn_auditoria_usuarios();

DROP TRIGGER IF EXISTS trg_auditoria_permisos ON permisos_rol;
CREATE TRIGGER trg_auditoria_permisos
AFTER INSERT OR UPDATE OR DELETE ON permisos_rol
FOR EACH ROW EXECUTE FUNCTION fn_auditoria_usuarios();
