import json
import os
import select
import sys
import time
import xmlrpc.client
from datetime import datetime
from pathlib import Path

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")
sys.stdout.reconfigure(encoding="utf-8")

CANAL = "odoo"
ESPERA_SEGUNDOS = 60
REINTENTO_SEGUNDOS = 10
SIN_IMPUESTOS = [(6, 0, [])]
ORDEN_TABLAS = {"clientes": 0, "modelos": 1, "almacen": 2, "pedidos": 3}
CONTEXTO_ENTREGA = {"skip_backorder": True, "skip_immediate": True, "skip_sms": True, "skip_expired": True}


def registrar(mensaje):
    print(f"[{datetime.now():%H:%M:%S}] {mensaje}", flush=True)


class Odoo:

    def __init__(self):
        self.db = os.getenv("ODOO_DB")
        self.clave = os.getenv("ODOO_KEY")
        url = os.getenv("ODOO_URL")
        comun = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
        self.version = comun.version()["server_version"]
        self.uid = comun.authenticate(self.db, os.getenv("ODOO_USER"), self.clave, {})
        if not self.uid:
            sys.exit("No se ha podido entrar en Odoo: revisa ODOO_USER y ODOO_KEY en el .env")
        self.objetos = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object", allow_none=True)

    def __call__(self, modelo, metodo, *args, **opciones):
        try:
            return self.objetos.execute_kw(self.db, self.uid, self.clave, modelo, metodo, list(args), opciones)
        except xmlrpc.client.Fault as error:
            if "cannot marshal None" in error.faultString:
                return None
            raise


def conectar_postgres():
    conexion = psycopg2.connect(
        host=os.getenv("PG_HOST"),
        port=os.getenv("PG_PORT"),
        dbname=os.getenv("POSTGRES_DB"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
        cursor_factory=psycopg2.extras.RealDictCursor,
    )
    conexion.autocommit = True
    return conexion


def referencia_cliente(cliente):
    return cliente["codigo_odoo"] or f"WEB{cliente['id_cliente']:03d}"


def codigo_variante(codigo_modelo, talla, color):
    return f"{codigo_modelo}-{talla}-{color}"


class Sincronizador:

    def __init__(self, odoo, postgres):
        self.odoo = odoo
        self.postgres = postgres
        self.variantes = {}
        self.almacen_de_variante = {}
        self.valores = {}
        self.atributos = {}
        self.ubicacion = None

    def consultar(self, sql, parametros=None):
        with self.postgres.cursor() as cursor:
            cursor.execute(sql, parametros)
            return cursor.fetchall()

    def preparar(self):
        grupo = self.odoo("ir.model.data", "search_read",
                          [("module", "=", "product"), ("name", "=", "group_product_variant")], fields=["res_id"])
        usuario = self.odoo("res.users", "read", [self.odoo.uid], fields=["groups_id"])[0]
        if grupo[0]["res_id"] not in usuario["groups_id"]:
            ajustes = self.odoo("res.config.settings", "create", {"group_product_variant": True})
            self.odoo("res.config.settings", "execute", [ajustes])
            registrar("Odoo: activadas las variantes de producto")
        for nombre in ("Talla", "Color"):
            ids = self.odoo("product.attribute", "search", [("name", "=", nombre)], limit=1)
            if not ids:
                ids = [self.odoo("product.attribute", "create", {"name": nombre, "create_variant": "always"})]
                registrar(f"Odoo: creado el atributo {nombre}")
            self.atributos[nombre] = ids[0]
        almacen = self.odoo("stock.warehouse", "search_read", [], fields=["lot_stock_id"], limit=1)
        self.ubicacion = almacen[0]["lot_stock_id"][0]

    def valor(self, atributo, nombre):
        clave = (atributo, nombre)
        if clave not in self.valores:
            id_atributo = self.atributos[atributo]
            ids = self.odoo("product.attribute.value", "search",
                            [("attribute_id", "=", id_atributo), ("name", "=", nombre)], limit=1)
            self.valores[clave] = ids[0] if ids else self.odoo(
                "product.attribute.value", "create", {"attribute_id": id_atributo, "name": nombre})
        return self.valores[clave]

    def sincronizar_cliente(self, id_cliente):
        cliente = self.consultar("SELECT * FROM clientes WHERE id_cliente = %s", (id_cliente,))[0]
        referencia = referencia_cliente(cliente)
        datos = {
            "name": cliente["nombre"],
            "ref": referencia,
            "email": cliente["email"] or False,
            "phone": cliente["telefono"] or False,
            "is_company": cliente["tipo_cliente"] in ("CLUB", "EQUIPO"),
            "customer_rank": 1,
            "active": cliente["activo"],
        }
        todos = ("active", "in", [True, False])
        ids = self.odoo("res.partner", "search", [("ref", "=", referencia), todos], limit=1)
        if not ids and cliente["email"]:
            ids = self.odoo("res.partner", "search", [("email", "=", cliente["email"]), todos], limit=1)
        if not ids:
            ids = self.odoo("res.partner", "search", [("name", "=", cliente["nombre"]), todos], limit=1)
        if not ids:
            id_odoo = self.odoo("res.partner", "create", datos)
            registrar(f"Cliente {referencia}: creado en Odoo")
            return id_odoo
        actual = self.odoo("res.partner", "read", ids, fields=list(datos))[0]
        cambios = {campo: valor for campo, valor in datos.items() if actual[campo] != valor}
        if cambios:
            self.odoo("res.partner", "write", ids, cambios)
            registrar(f"Cliente {referencia}: actualizado ({', '.join(cambios)})")
        return ids[0]

    def buscar_plantilla(self, codigo):
        todos = ("active", "in", [True, False])
        variantes = self.odoo("product.product", "search_read",
                              [("default_code", "=like", f"{codigo}-%"), todos], fields=["product_tmpl_id"], limit=1)
        if variantes:
            return [variantes[0]["product_tmpl_id"][0]]
        return self.odoo("product.template", "search", [("default_code", "=", codigo), todos], limit=1)

    def sincronizar_modelo(self, id_modelo):
        modelo = self.consultar("SELECT * FROM modelos WHERE id_modelo = %s", (id_modelo,))[0]
        filas = self.consultar("SELECT * FROM almacen WHERE id_modelo = %s ORDER BY talla", (id_modelo,))
        codigo = modelo["codigo_modelo"]
        datos = {
            "name": modelo["nombre"],
            "list_price": float(modelo["precio_base"]),
            "detailed_type": "product",
            "sale_ok": True,
            "taxes_id": [],
            "description_sale": modelo["descripcion"] or False,
            "active": modelo["activo"],
        }
        ids = self.buscar_plantilla(codigo)
        if ids:
            plantilla = ids[0]
            actual = self.odoo("product.template", "read", ids, fields=list(datos))[0]
            cambios = {campo: valor for campo, valor in datos.items() if actual[campo] != valor}
            if "taxes_id" in cambios:
                cambios["taxes_id"] = SIN_IMPUESTOS
            if cambios:
                self.odoo("product.template", "write", ids, cambios)
                registrar(f"Modelo {codigo}: actualizado ({', '.join(cambios)})")
        else:
            plantilla = self.odoo("product.template", "create",
                                  {**datos, "default_code": codigo, "taxes_id": SIN_IMPUESTOS})
            registrar(f"Modelo {codigo}: creado en Odoo")

        deseados = {
            "Talla": sorted({self.valor("Talla", str(f["talla"])) for f in filas}),
            "Color": sorted({self.valor("Color", f["color_base"]) for f in filas}),
        }
        lineas = self.odoo("product.template.attribute.line", "search_read",
                           [("product_tmpl_id", "=", plantilla)], fields=["attribute_id", "value_ids"])
        por_atributo = {linea["attribute_id"][0]: linea for linea in lineas}
        ordenes = []
        for nombre, valores in deseados.items():
            linea = por_atributo.get(self.atributos[nombre])
            if linea is None:
                ordenes.append((0, 0, {"attribute_id": self.atributos[nombre], "value_ids": [(6, 0, valores)]}))
            elif sorted(linea["value_ids"]) != valores:
                ordenes.append((1, linea["id"], {"value_ids": [(6, 0, valores)]}))
        if ordenes:
            self.odoo("product.template", "write", [plantilla], {"attribute_line_ids": ordenes})
            registrar(f"Modelo {codigo}: variantes de talla y color al día")

        valores_plantilla = self.odoo("product.template.attribute.value", "search_read",
                                      [("product_tmpl_id", "=", plantilla)], fields=["attribute_id", "name"])
        nombres = {v["id"]: (v["attribute_id"][1], v["name"]) for v in valores_plantilla}
        variantes = self.odoo("product.product", "search_read", [("product_tmpl_id", "=", plantilla)],
                              fields=["default_code", "product_template_attribute_value_ids"])
        por_combinacion = {}
        for variante in variantes:
            partes = dict(nombres[v] for v in variante["product_template_attribute_value_ids"] if v in nombres)
            if "Talla" in partes and "Color" in partes:
                por_combinacion[(partes["Talla"], partes["Color"])] = variante

        cantidades = {}
        for fila in filas:
            variante = por_combinacion.get((str(fila["talla"]), fila["color_base"]))
            if variante is None:
                registrar(f"Modelo {codigo}: falta en Odoo la variante talla {fila['talla']} {fila['color_base']}")
                continue
            codigo_odoo = codigo_variante(codigo, fila["talla"], fila["color_base"])
            if variante["default_code"] != codigo_odoo:
                self.odoo("product.product", "write", [variante["id"]], {"default_code": codigo_odoo})
            self.variantes[fila["id_almacen"]] = variante["id"]
            self.almacen_de_variante[variante["id"]] = fila["id_almacen"]
            cantidades[variante["id"]] = fila["stock_disponible"]

        usadas = set(cantidades)
        sobrantes = [v["id"] for v in por_combinacion.values() if v["id"] not in usadas]
        if sobrantes:
            self.odoo("product.product", "write", sobrantes, {"active": False})
        self.sincronizar_stock(cantidades, codigo)

    def sincronizar_stock(self, cantidades, etiqueta):
        if not cantidades:
            return
        quants = self.odoo("stock.quant", "search_read",
                           [("product_id", "in", list(cantidades)), ("location_id", "=", self.ubicacion)],
                           fields=["product_id", "quantity"])
        por_variante = {}
        for quant in quants:
            por_variante.setdefault(quant["product_id"][0], []).append(quant)
        contexto = {"inventory_mode": True}
        aplicar = []
        nuevos = []
        for variante, cantidad in cantidades.items():
            existentes = por_variante.get(variante, [])
            if abs(sum(q["quantity"] for q in existentes) - cantidad) < 0.001:
                continue
            if existentes:
                self.odoo("stock.quant", "write", [existentes[0]["id"]],
                          {"inventory_quantity": cantidad}, context=contexto)
                aplicar.append(existentes[0]["id"])
            else:
                nuevos.append({"product_id": variante, "location_id": self.ubicacion, "inventory_quantity": cantidad})
        if nuevos:
            creados = self.odoo("stock.quant", "create", nuevos, context=contexto)
            aplicar.extend(creados if isinstance(creados, list) else [creados])
        if aplicar:
            self.odoo("stock.quant", "action_apply_inventory", aplicar, context=contexto)
            registrar(f"Stock {etiqueta}: {len(aplicar)} tallas ajustadas")

    def sincronizar_almacen(self, id_almacen):
        fila = self.consultar("SELECT * FROM almacen WHERE id_almacen = %s", (id_almacen,))[0]
        if id_almacen not in self.variantes:
            self.sincronizar_modelo(fila["id_modelo"])
            return
        codigo = self.consultar("SELECT codigo_modelo FROM modelos WHERE id_modelo = %s", (fila["id_modelo"],))
        etiqueta = f"{codigo[0]['codigo_modelo']} talla {fila['talla']}"
        self.sincronizar_stock({self.variantes[id_almacen]: fila["stock_disponible"]}, etiqueta)

    def sincronizar_pedido(self, id_pedido):
        pedido = self.consultar("SELECT * FROM pedidos WHERE id_pedido = %s", (id_pedido,))[0]
        referencia = pedido["ref_odoo"]
        if pedido["estado"] == "BORRADOR":
            return
        lineas = self.consultar("""
            SELECT l.id_almacen, l.cantidad, l.precio_unitario, a.id_modelo, a.talla, a.color_base,
                   m.marca, m.nombre, pe.nombre_diseno, pe.texto_bordado
            FROM lineas_pedido l
            JOIN almacen a ON a.id_almacen = l.id_almacen
            JOIN modelos m ON m.id_modelo = a.id_modelo
            LEFT JOIN personalizaciones pe ON pe.id_personalizacion = l.id_personalizacion
            WHERE l.id_pedido = %s
            ORDER BY m.nombre, a.talla""", (id_pedido,))

        cliente = self.sincronizar_cliente(pedido["id_cliente"])
        lineas_odoo = []
        for linea in lineas:
            if linea["id_almacen"] not in self.variantes:
                self.sincronizar_modelo(linea["id_modelo"])
            descripcion = f"{linea['marca']} {linea['nombre']} · {linea['color_base']} · talla {linea['talla']}"
            if linea["nombre_diseno"]:
                descripcion += f" · diseño {linea['nombre_diseno']}"
            if linea["texto_bordado"]:
                descripcion += f" · bordado «{linea['texto_bordado']}»"
            lineas_odoo.append((0, 0, {
                "product_id": self.variantes[linea["id_almacen"]],
                "name": descripcion,
                "product_uom_qty": linea["cantidad"],
                "price_unit": float(linea["precio_unitario"]),
                "tax_id": SIN_IMPUESTOS,
            }))

        fecha = pedido["fecha_pedido"].strftime("%Y-%m-%d %H:%M:%S")
        datos = {
            "partner_id": cliente,
            "client_order_ref": referencia,
            "date_order": fecha,
            "commitment_date": pedido["fecha_entrega_objetivo"].strftime("%Y-%m-%d 12:00:00")
            if pedido["fecha_entrega_objetivo"] else False,
        }
        ids = self.odoo("sale.order", "search", [("name", "=", referencia)], limit=1)
        if not ids:
            orden = self.odoo("sale.order", "create", {**datos, "name": referencia, "order_line": lineas_odoo})
            registrar(f"Pedido {referencia}: creado en Odoo")
        else:
            orden = ids[0]
            estado_odoo = self.odoo("sale.order", "read", [orden], fields=["state"])[0]["state"]
            if estado_odoo in ("draft", "sent"):
                self.odoo("sale.order", "write", [orden], {**datos, "order_line": [(5, 0, 0)] + lineas_odoo})
                registrar(f"Pedido {referencia}: líneas actualizadas")

        estado_odoo = self.odoo("sale.order", "read", [orden], fields=["state"])[0]["state"]
        if pedido["estado"] == "CANCELADO":
            if estado_odoo != "cancel":
                self.odoo("sale.order", "action_cancel", [orden], context={"disable_cancel_warning": True})
                registrar(f"Pedido {referencia}: cancelado en Odoo")
            return
        if estado_odoo in ("draft", "sent"):
            self.odoo("sale.order", "action_confirm", [orden])
            self.odoo("sale.order", "write", [orden], {"date_order": fecha})
            registrar(f"Pedido {referencia}: confirmado en Odoo")
        elif estado_odoo == "cancel":
            registrar(f"Pedido {referencia}: está cancelado en Odoo y no se puede volver a abrir")
            return
        if pedido["estado"] == "ENTREGADO":
            self.entregar(orden, referencia)

    def entregar(self, orden, referencia):
        albaranes = self.odoo("stock.picking", "search",
                              [("sale_id", "=", orden), ("state", "not in", ["done", "cancel"])])
        if not albaranes:
            return
        variantes = set()
        for albaran in albaranes:
            movimientos = self.odoo("stock.move", "search_read",
                                    [("picking_id", "=", albaran), ("state", "not in", ["done", "cancel"])],
                                    fields=["product_id", "product_uom_qty"])
            for movimiento in movimientos:
                self.odoo("stock.move", "write", [movimiento["id"]],
                          {"quantity_done": movimiento["product_uom_qty"]})
                variantes.add(movimiento["product_id"][0])
            resultado = self.odoo("stock.picking", "button_validate", [albaran], context=CONTEXTO_ENTREGA)
            if isinstance(resultado, dict):
                registrar(f"Pedido {referencia}: Odoo pide revisar la entrega a mano ({resultado.get('res_model')})")
        registrar(f"Pedido {referencia}: entrega validada en Odoo")
        filas = [self.almacen_de_variante[v] for v in variantes if v in self.almacen_de_variante]
        if filas:
            stock = self.consultar("SELECT id_almacen, stock_disponible FROM almacen WHERE id_almacen = ANY(%s)",
                                   (filas,))
            self.sincronizar_stock({self.variantes[f["id_almacen"]]: f["stock_disponible"] for f in stock},
                                   referencia)

    def sincronizar_todo(self):
        registrar("Sincronización completa: clientes, modelos, stock y pedidos")
        for fila in self.consultar("SELECT id_cliente FROM clientes ORDER BY id_cliente"):
            self.sincronizar_cliente(fila["id_cliente"])
        for fila in self.consultar("SELECT id_modelo FROM modelos ORDER BY id_modelo"):
            self.sincronizar_modelo(fila["id_modelo"])
        for fila in self.consultar("SELECT id_pedido FROM pedidos WHERE estado <> 'BORRADOR' ORDER BY id_pedido"):
            self.sincronizar_pedido(fila["id_pedido"])
        registrar("Sincronización completa terminada: Odoo está igual que PostgreSQL")

    def atender(self, tabla, id_fila):
        acciones = {
            "clientes": self.sincronizar_cliente,
            "modelos": self.sincronizar_modelo,
            "almacen": self.sincronizar_almacen,
            "pedidos": self.sincronizar_pedido,
        }
        try:
            acciones[tabla](id_fila)
        except (psycopg2.OperationalError, psycopg2.InterfaceError, OSError):
            raise
        except Exception as error:
            registrar(f"ERROR al sincronizar {tabla} {id_fila}: {error}")

    def escuchar(self):
        with self.postgres.cursor() as cursor:
            cursor.execute(f"LISTEN {CANAL}")
        registrar("Escuchando cambios de PostgreSQL (Ctrl+C para salir)")
        while True:
            if not self.postgres.notifies:
                if select.select([self.postgres], [], [], ESPERA_SEGUNDOS) == ([], [], []):
                    continue
            self.postgres.poll()
            avisos = []
            while self.postgres.notifies:
                aviso = json.loads(self.postgres.notifies.pop(0).payload)
                avisos.append((aviso["tabla"], aviso["id"]))
            for tabla, id_fila in sorted(dict.fromkeys(avisos), key=lambda a: ORDEN_TABLAS[a[0]]):
                self.atender(tabla, id_fila)


def main():
    if not os.getenv("ODOO_URL"):
        registrar("Odoo no está configurado en el .env (ODOO_URL vacío): no se sincroniza")
        return
    una_vez = "--una-vez" in sys.argv
    while True:
        try:
            odoo = Odoo()
            postgres = conectar_postgres()
            registrar(f"Conectado a Odoo {odoo.version} y a PostgreSQL")
            sincronizador = Sincronizador(odoo, postgres)
            sincronizador.preparar()
            sincronizador.sincronizar_todo()
            if una_vez:
                return
            sincronizador.escuchar()
        except KeyboardInterrupt:
            registrar("Sincronizador detenido")
            return
        except (psycopg2.OperationalError, psycopg2.InterfaceError, OSError, xmlrpc.client.ProtocolError) as error:
            registrar(f"Conexión perdida ({error}); se reintenta en {REINTENTO_SEGUNDOS} s")
            time.sleep(REINTENTO_SEGUNDOS)


if __name__ == "__main__":
    main()
