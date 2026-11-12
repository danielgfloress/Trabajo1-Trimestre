CREATE OR REPLACE FUNCTION fn_avisar_odoo()
RETURNS TRIGGER AS $$
BEGIN
	PERFORM pg_notify('odoo', json_build_object(
		'tabla', TG_TABLE_NAME,
		'id', (to_jsonb(NEW) ->> TG_ARGV[0])::INTEGER
	)::TEXT);
	RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_odoo_clientes
AFTER INSERT OR UPDATE ON clientes
FOR EACH ROW EXECUTE FUNCTION fn_avisar_odoo('id_cliente');

CREATE TRIGGER trg_odoo_modelos
AFTER INSERT OR UPDATE ON modelos
FOR EACH ROW EXECUTE FUNCTION fn_avisar_odoo('id_modelo');

CREATE TRIGGER trg_odoo_almacen
AFTER INSERT OR UPDATE ON almacen
FOR EACH ROW EXECUTE FUNCTION fn_avisar_odoo('id_almacen');

CREATE TRIGGER trg_odoo_pedidos
AFTER UPDATE OF estado ON pedidos
FOR EACH ROW
WHEN (NEW.estado <> 'BORRADOR' AND NEW.estado IS DISTINCT FROM OLD.estado)
EXECUTE FUNCTION fn_avisar_odoo('id_pedido');
