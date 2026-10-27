CREATE OR REPLACE FUNCTION fn_precio_linea()
RETURNS TRIGGER AS $$
DECLARE
	v_estado pedidos.estado%TYPE;
	v_tipo pedidos.tipo%TYPE;
	v_precio_base modelos.precio_base%TYPE;
	v_admite_custom modelos.admite_custom%TYPE;
	v_recargo personalizaciones.recargo_unitario%TYPE;
BEGIN
	IF TG_OP = 'DELETE' THEN
		SELECT estado INTO v_estado FROM pedidos WHERE id_pedido = OLD.id_pedido;
		IF v_estado <> 'BORRADOR' THEN
			RAISE EXCEPTION 'No se pueden borrar líneas de un pedido en estado %', v_estado;
		END IF;
		RETURN OLD;
	END IF;

	IF TG_OP = 'UPDATE' AND NEW.id_pedido <> OLD.id_pedido THEN
		RAISE EXCEPTION 'Una línea no se puede cambiar de pedido';
	END IF;

	SELECT estado, tipo INTO v_estado, v_tipo FROM pedidos WHERE id_pedido = NEW.id_pedido;
	IF v_estado <> 'BORRADOR' THEN
		RAISE EXCEPTION 'No se pueden modificar líneas de un pedido en estado %', v_estado;
	END IF;

	SELECT m.precio_base, m.admite_custom INTO v_precio_base, v_admite_custom
	FROM almacen a
	JOIN modelos m ON m.id_modelo = a.id_modelo
	WHERE a.id_almacen = NEW.id_almacen;

	IF NEW.id_personalizacion IS NULL THEN
		IF v_tipo = 'CUSTOM' THEN
			RAISE EXCEPTION 'Las líneas de un pedido CUSTOM necesitan un diseño';
		END IF;
		v_recargo := 0;
	ELSE
		IF v_tipo <> 'CUSTOM' THEN
			RAISE EXCEPTION 'Un pedido ESTANDAR no puede llevar diseño personalizado';
		END IF;
		IF NOT v_admite_custom THEN
			RAISE EXCEPTION 'Este modelo no admite personalización';
		END IF;
		SELECT recargo_unitario INTO v_recargo
		FROM personalizaciones WHERE id_personalizacion = NEW.id_personalizacion;
	END IF;

	NEW.precio_unitario := v_precio_base + v_recargo;
	RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_precio_linea ON lineas_pedido;
CREATE TRIGGER trg_precio_linea
BEFORE INSERT OR UPDATE OR DELETE ON lineas_pedido
FOR EACH ROW EXECUTE FUNCTION fn_precio_linea();

CREATE OR REPLACE FUNCTION fn_total_pedido()
RETURNS TRIGGER AS $$
DECLARE
	v_id_pedido pedidos.id_pedido%TYPE;
BEGIN
	IF TG_OP = 'DELETE' THEN
		v_id_pedido := OLD.id_pedido;
	ELSE
		v_id_pedido := NEW.id_pedido;
	END IF;

	UPDATE pedidos
	SET importe_total = (
		SELECT COALESCE(SUM(subtotal_linea), 0)
		FROM lineas_pedido
		WHERE id_pedido = v_id_pedido
	)
	WHERE id_pedido = v_id_pedido;

	RETURN NULL;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_total_pedido ON lineas_pedido;
CREATE TRIGGER trg_total_pedido
AFTER INSERT OR UPDATE OR DELETE ON lineas_pedido
FOR EACH ROW EXECUTE FUNCTION fn_total_pedido();

CREATE OR REPLACE FUNCTION fn_proteger_total()
RETURNS TRIGGER AS $$
BEGIN
	IF pg_trigger_depth() = 1 THEN
		IF TG_OP = 'INSERT' THEN
			NEW.importe_total := 0;
		ELSIF NEW.importe_total <> OLD.importe_total THEN
			RAISE EXCEPTION 'El importe total se calcula automáticamente y no se puede modificar';
		END IF;
	END IF;
	RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_proteger_total ON pedidos;
CREATE TRIGGER trg_proteger_total
BEFORE INSERT OR UPDATE OF importe_total ON pedidos
FOR EACH ROW EXECUTE FUNCTION fn_proteger_total();

CREATE OR REPLACE FUNCTION fn_stock_pedido()
RETURNS TRIGGER AS $$
DECLARE
	v_linea RECORD;
	v_stock almacen.stock_disponible%TYPE;
BEGIN
	IF TG_OP = 'INSERT' THEN
		IF NEW.estado <> 'BORRADOR' THEN
			RAISE EXCEPTION 'Un pedido nuevo tiene que crearse en estado BORRADOR';
		END IF;
		RETURN NEW;
	END IF;

	IF NEW.estado = OLD.estado THEN
		RETURN NEW;
	END IF;

	IF OLD.estado = 'BORRADOR' AND NEW.estado = 'CONFIRMADO' THEN
		IF NOT EXISTS (SELECT 1 FROM lineas_pedido WHERE id_pedido = NEW.id_pedido) THEN
			RAISE EXCEPTION 'No se puede confirmar el pedido % porque no tiene líneas', NEW.ref_odoo;
		END IF;

		IF NEW.tipo = 'CUSTOM' AND (SELECT SUM(cantidad) FROM lineas_pedido WHERE id_pedido = NEW.id_pedido) < 20 THEN
			RAISE EXCEPTION 'Un pedido CUSTOM necesita al menos 20 pares (el pedido % tiene %)',
				NEW.ref_odoo, (SELECT SUM(cantidad) FROM lineas_pedido WHERE id_pedido = NEW.id_pedido);
		END IF;

		FOR v_linea IN
			SELECT l.id_almacen, SUM(l.cantidad) AS cantidad, m.nombre, a.color_base, a.talla
			FROM lineas_pedido l
			JOIN almacen a ON a.id_almacen = l.id_almacen
			JOIN modelos m ON m.id_modelo = a.id_modelo
			WHERE l.id_pedido = NEW.id_pedido
			GROUP BY l.id_almacen, m.nombre, a.color_base, a.talla
			ORDER BY l.id_almacen
		LOOP
			SELECT stock_disponible INTO v_stock
			FROM almacen WHERE id_almacen = v_linea.id_almacen
			FOR UPDATE;

			IF v_stock < v_linea.cantidad THEN
				RAISE EXCEPTION 'Stock insuficiente para % % talla %: se piden % y hay %',
					v_linea.nombre, v_linea.color_base, v_linea.talla, v_linea.cantidad, v_stock;
			END IF;

			UPDATE almacen
			SET stock_disponible = stock_disponible - v_linea.cantidad
			WHERE id_almacen = v_linea.id_almacen;
		END LOOP;

	ELSIF OLD.estado = 'CONFIRMADO' AND NEW.estado = 'CANCELADO' THEN
		UPDATE almacen a
		SET stock_disponible = a.stock_disponible + l.cantidad
		FROM (
			SELECT id_almacen, SUM(cantidad) AS cantidad
			FROM lineas_pedido
			WHERE id_pedido = NEW.id_pedido
			GROUP BY id_almacen
		) l
		WHERE a.id_almacen = l.id_almacen;

	ELSIF OLD.estado = 'BORRADOR' AND NEW.estado = 'CANCELADO' THEN
		NULL;

	ELSIF OLD.estado = 'CONFIRMADO' AND NEW.estado = 'ENTREGADO' THEN
		NULL;

	ELSE
		RAISE EXCEPTION 'No se puede pasar un pedido de % a %', OLD.estado, NEW.estado;
	END IF;

	RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_stock_pedido ON pedidos;
CREATE TRIGGER trg_stock_pedido
BEFORE INSERT OR UPDATE OF estado ON pedidos
FOR EACH ROW EXECUTE FUNCTION fn_stock_pedido();

CREATE OR REPLACE FUNCTION fn_auditoria()
RETURNS TRIGGER AS $$
DECLARE
	v_antiguo JSONB;
	v_nuevo JSONB;
	v_fila JSONB;
	v_id_usuario INTEGER;
	v_accion VARCHAR(60);
	v_resumen VARCHAR(500);
	v_cambio RECORD;
BEGIN
	IF TG_OP <> 'INSERT' THEN
		v_antiguo := to_jsonb(OLD);
	END IF;
	IF TG_OP <> 'DELETE' THEN
		v_nuevo := to_jsonb(NEW);
	END IF;
	v_fila := COALESCE(v_nuevo, v_antiguo);

	IF TG_OP = 'UPDATE' AND (v_nuevo - 'importe_total') = (v_antiguo - 'importe_total') THEN
		RETURN NULL;
	END IF;

	v_id_usuario := NULLIF(current_setting('app.id_usuario', true), '')::INTEGER;
	v_accion := NULLIF(current_setting('app.accion', true), '');

	IF TG_TABLE_NAME = 'pedidos' THEN
		IF TG_OP = 'INSERT' THEN
			v_accion := COALESCE(v_accion, 'CREAR_PEDIDO');
			v_resumen := 'Pedido ' || NEW.ref_odoo || ' creado (' || NEW.tipo || ') para el cliente ' || NEW.id_cliente;
		ELSIF TG_OP = 'UPDATE' AND NEW.estado <> OLD.estado THEN
			v_accion := COALESCE(v_accion,
				CASE NEW.estado
					WHEN 'CONFIRMADO' THEN 'CONFIRMAR_PEDIDO'
					WHEN 'CANCELADO' THEN 'CANCELAR_PEDIDO'
					WHEN 'ENTREGADO' THEN 'ENTREGAR_PEDIDO'
				END);
			v_resumen := 'Pedido ' || NEW.ref_odoo || ': ' || OLD.estado || ' -> ' || NEW.estado;
		ELSIF TG_OP = 'UPDATE' THEN
			v_accion := COALESCE(v_accion, 'MODIFICAR_PEDIDO');
			v_resumen := 'Pedido ' || NEW.ref_odoo || ' modificado:';
		ELSE
			v_accion := COALESCE(v_accion, 'BORRAR_PEDIDO');
			v_resumen := 'Pedido ' || OLD.ref_odoo || ' borrado';
		END IF;
	ELSE
		IF TG_OP = 'INSERT' THEN
			v_accion := COALESCE(v_accion, 'ANADIR_LINEA');
			v_resumen := 'Línea añadida al pedido ' || NEW.id_pedido || ': ' || NEW.cantidad || ' pares (almacén ' || NEW.id_almacen || ')';
		ELSIF TG_OP = 'UPDATE' THEN
			v_accion := COALESCE(v_accion, 'MODIFICAR_LINEA');
			v_resumen := 'Línea ' || NEW.id_linea || ' del pedido ' || NEW.id_pedido || ' modificada:';
		ELSE
			v_accion := COALESCE(v_accion, 'BORRAR_LINEA');
			v_resumen := 'Línea ' || OLD.id_linea || ' borrada del pedido ' || OLD.id_pedido;
		END IF;
	END IF;

	IF TG_OP = 'UPDATE' AND RIGHT(v_resumen, 1) = ':' THEN
		FOR v_cambio IN
			SELECT n.key, o.value AS antes, n.value AS despues
			FROM jsonb_each_text(v_nuevo) n
			JOIN jsonb_each_text(v_antiguo) o ON o.key = n.key
			WHERE n.value IS DISTINCT FROM o.value
		LOOP
			v_resumen := v_resumen || ' ' || v_cambio.key || ' ' || COALESCE(v_cambio.antes, 'vacío') || ' -> ' || COALESCE(v_cambio.despues, 'vacío') || ';';
		END LOOP;
	END IF;

	INSERT INTO log_eventos (id_usuario, tabla_afectada, operacion, id_registro_afectado, resumen_cambios, accion, datos_antiguos, datos_nuevos)
	VALUES (v_id_usuario, TG_TABLE_NAME, TG_OP, (v_fila ->> TG_ARGV[0])::INTEGER, LEFT(v_resumen, 500), v_accion, v_antiguo, v_nuevo);

	RETURN NULL;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_auditoria_pedidos ON pedidos;
CREATE TRIGGER trg_auditoria_pedidos
AFTER INSERT OR UPDATE OR DELETE ON pedidos
FOR EACH ROW EXECUTE FUNCTION fn_auditoria('id_pedido');

DROP TRIGGER IF EXISTS trg_auditoria_lineas ON lineas_pedido;
CREATE TRIGGER trg_auditoria_lineas
AFTER INSERT OR UPDATE OR DELETE ON lineas_pedido
FOR EACH ROW EXECUTE FUNCTION fn_auditoria('id_linea');
