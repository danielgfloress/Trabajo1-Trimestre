import os, sys
import xmlrpc.client
import psycopg2, psycopg2.extras
from dotenv import load_dotenv

load_dotenv()
CREAR = "--crear" in sys.argv  # sin esta opción solo simula

# --- Odoo ---
URL, DB, KEY = os.getenv("ODOO_URL"), os.getenv("ODOO_DB"), os.getenv("ODOO_KEY")
uid = xmlrpc.client.ServerProxy(f"{URL}/xmlrpc/2/common").authenticate(DB, os.getenv("ODOO_USER"), KEY, {})
if not uid:
    sys.exit("No se pudo autenticar en Odoo")
models = xmlrpc.client.ServerProxy(f"{URL}/xmlrpc/2/object")

def odoo(modelo, metodo, args, kwargs=None):
    return models.execute_kw(DB, uid, KEY, modelo, metodo, args, kwargs or {})

def cliente_odoo(c):
    for campo, valor in (("ref", c["codigo_odoo"]), ("email", c["email"]), ("name", c["nombre"])):
        if valor:
            ids = odoo("res.partner", "search", [[[campo, "=", valor]]], {"limit": 1})
            if ids:
                odoo("res.partner", "write", [ids, {"ref": c["codigo_odoo"]}])
                return ids[0]
    return odoo("res.partner", "create", [{"name": c["nombre"], "email": c["email"],
                                          "phone": c["telefono"], "ref": c["codigo_odoo"]}])

def producto_odoo(l):
    ids = odoo("product.product", "search", [[["default_code", "=", l["codigo_modelo"]]]], {"limit": 1})
    if ids:
        odoo("product.product", "write", [ids, {"description_sale": l["descripcion"] or ""}])
        return ids[0]
    return odoo("product.product", "create", [{"name": l["modelo"], "default_code": l["codigo_modelo"],
                                              "list_price": float(l["precio_base"]),
                                              "description_sale": l["descripcion"] or ""}])

# --- PostgreSQL d3kicks ---
conn = psycopg2.connect(host=os.getenv("PG_HOST"), port=os.getenv("PG_PORT"),
                        dbname=os.getenv("POSTGRES_DB"), user=os.getenv("POSTGRES_USER"),
                        password=os.getenv("POSTGRES_PASSWORD"))
cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

cur.execute("""
    SELECT p.id_pedido, p.ref_odoo, c.codigo_odoo, c.nombre, c.email, c.telefono
    FROM pedidos p JOIN clientes c ON c.id_cliente = p.id_cliente
    WHERE p.estado = 'CONFIRMADO' ORDER BY p.id_pedido""")
pedidos = cur.fetchall()
print(f"Modo: {'CREAR' if CREAR else 'SIMULACION'} | Pedidos CONFIRMADOS en d3kicks: {len(pedidos)}")

for p in pedidos:
    ref = p["ref_odoo"]
    if odoo("sale.order", "search", [[["name", "=", ref]]], {"limit": 1}):
        print(f"{ref}: ya existe en Odoo, se omite")
        continue

    cur.execute("""
        SELECT m.codigo_modelo, m.nombre AS modelo, m.precio_base, m.descripcion, a.color_base, a.talla,
               l.cantidad, l.precio_unitario, pe.nombre_diseno, pe.texto_bordado
        FROM lineas_pedido l
        JOIN almacen a ON a.id_almacen = l.id_almacen
        JOIN modelos m ON m.id_modelo = a.id_modelo
        LEFT JOIN personalizaciones pe ON pe.id_personalizacion = l.id_personalizacion
        WHERE l.id_pedido = %s ORDER BY a.talla""", (p["id_pedido"],))
    lineas = cur.fetchall()

    if not CREAR:
        print(f"{ref}: se crearia para {p['nombre']} con {len(lineas)} lineas")
        continue

    try:
        lineas_odoo = []
        for l in lineas:
            desc = f"{l['modelo']} - {l['color_base']}, talla {l['talla']}"
            if l["nombre_diseno"]:
                desc += f" | Diseño: {l['nombre_diseno']}"
            if l["texto_bordado"]:
                desc += f" | Bordado: {l['texto_bordado']}"
            lineas_odoo.append([0, 0, {"product_id": producto_odoo(l), "name": desc,
                                       "product_uom_qty": int(l["cantidad"]),
                                       "price_unit": float(l["precio_unitario"])}])
        orden = odoo("sale.order", "create", [{"name": ref, "client_order_ref": ref,
                                              "partner_id": cliente_odoo(p), "order_line": lineas_odoo}])
        o = odoo("sale.order", "read", [[orden]], {"fields": ["name", "state", "amount_total"]})[0]
        print(f"{ref}: creado en Odoo ({o['name']}, estado {o['state']}, total {o['amount_total']})")
    except Exception as e:
        print(f"{ref}: ERROR -> {e}")

conn.close()