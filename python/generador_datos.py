import argparse
from pathlib import Path

import numpy as np
import pandas as pd

import config

MODELOS = [
    ("Sneakers", 89.90, True, 1.00, ["Blanco", "Negro"]),
    ("Sneakers", 119.99, True, 0.80, ["Blanco", "Gris"]),
    ("Sneakers", 129.99, False, 0.65, ["Negro", "Blanco y negro"]),
    ("Sneakers", 149.99, True, 0.45, ["Blanco", "Crema"]),
    ("Sneakers", 179.99, False, 0.30, ["Negro", "Verde"]),
    ("Sneakers", 219.99, False, 0.15, ["Blanco y rojo", "Negro"]),
    ("Fútbol", 84.99, True, 0.70, ["Negro", "Azul"]),
    ("Fútbol", 99.99, True, 0.55, ["Blanco", "Rojo y negro"]),
    ("Fútbol", 229.99, False, 0.20, ["Naranja", "Negro"]),
    ("Baloncesto", 74.99, True, 0.50, ["Negro", "Blanco"]),
    ("Baloncesto", 139.99, True, 0.35, ["Verde", "Negro"]),
    ("Baloncesto", 189.99, False, 0.20, ["Blanco y azul", "Negro"]),
    ("Boxeo", 69.99, True, 0.25, ["Negro", "Rojo"]),
    ("Boxeo", 199.99, False, 0.12, ["Negro y rosa", "Blanco"]),
]

ESTACIONALIDAD_GENERAL = [0.80, 0.75, 0.95, 1.00, 1.00, 0.95, 0.85, 1.05, 1.30, 1.10, 1.20, 1.35]
ESTACIONALIDAD_CATEGORIA = {
    "Fútbol": {8: 1.6, 9: 1.6},
    "Baloncesto": {9: 1.4, 10: 1.4},
    "Sneakers": {11: 1.3, 12: 1.3},
    "Boxeo": {1: 1.4},
}
CRECIMIENTO_MENSUAL = 0.015
TIPOS_CLIENTE = {"CLUB": 0.30, "EQUIPO": 0.25, "PARTICULAR": 0.45}
PROBABILIDAD_CUSTOM = {"CLUB": 0.30, "EQUIPO": 0.25, "PARTICULAR": 0.0}
LINEAS_ESTANDAR = {1: 0.45, 2: 0.35, 3: 0.20}
RECARGO_CUSTOM = (10.0, 20.0)
STOCK_MINIMO = 5


def formato_bool(serie):
    return serie.map({True: "true", False: "false"})


def peso_tallas():
    tallas = np.array(config.TALLAS_VALIDAS)
    pesos = np.exp(-0.5 * ((tallas - 41.5) / 2.0) ** 2)
    return tallas, pesos / pesos.sum()


def crear_modelos():
    filas = []
    for numero, (categoria, precio, custom, _, _) in enumerate(MODELOS, start=1):
        filas.append({
            "id_modelo": numero,
            "codigo_modelo": f"SIM-{numero:02d}",
            "marca": "SIMULADA",
            "nombre": f"{categoria} sintético {numero:02d}",
            "categoria": categoria,
            "precio_base": precio,
            "admite_custom": custom,
            "activo": True,
        })
    return pd.DataFrame(filas)


def crear_clientes(generador):
    tipos = generador.choice(list(TIPOS_CLIENTE), size=config.SINTETICO_CLIENTES, p=list(TIPOS_CLIENTE.values()))
    clientes = pd.DataFrame({
        "id_cliente": range(1, config.SINTETICO_CLIENTES + 1),
        "codigo_odoo": [f"SCLI{n:03d}" for n in range(1, config.SINTETICO_CLIENTES + 1)],
        "nombre": [f"Cliente sintético {n:03d}" for n in range(1, config.SINTETICO_CLIENTES + 1)],
        "tipo_cliente": tipos,
        "activo": True,
    })
    actividad = generador.lognormal(mean=0, sigma=0.9, size=len(clientes))
    return clientes, actividad / actividad.sum()


def repartir_pedidos_por_mes(generador):
    meses = pd.period_range(config.SINTETICO_INICIO, periods=config.SINTETICO_MESES, freq="M")
    pesos = np.array([ESTACIONALIDAD_GENERAL[m.month - 1] * (1 + CRECIMIENTO_MENSUAL * i) for i, m in enumerate(meses)])
    cuantos = generador.multinomial(config.SINTETICO_PEDIDOS, pesos / pesos.sum())
    return meses, cuantos


def fecha_aleatoria(generador, mes):
    dia = int(generador.integers(1, mes.days_in_month + 1))
    hora = int(generador.integers(9, 20))
    minuto = int(generador.choice([0, 15, 30, 45]))
    return pd.Timestamp(year=mes.year, month=mes.month, day=dia, hour=hora, minute=minuto)


def elegir_estado(generador, dias_antes_del_corte, tipo):
    cancelacion = 0.14 if tipo == "CUSTOM" else 0.08
    if dias_antes_del_corte <= 20:
        opciones = {"BORRADOR": 0.30, "CONFIRMADO": 0.70 - cancelacion, "CANCELADO": cancelacion}
    elif dias_antes_del_corte <= 45:
        opciones = {"CONFIRMADO": 0.55, "ENTREGADO": 0.45 - cancelacion, "CANCELADO": cancelacion}
    else:
        opciones = {"ENTREGADO": 1 - cancelacion, "CANCELADO": cancelacion}
    return generador.choice(list(opciones), p=list(opciones.values()))


def pesos_modelos(modelos, mes, solo_custom=False):
    pesos = []
    for (categoria, _, custom, popularidad, _) in MODELOS:
        peso = popularidad * ESTACIONALIDAD_CATEGORIA.get(categoria, {}).get(mes.month, 1.0)
        pesos.append(0.0 if solo_custom and not custom else peso)
    pesos = np.array(pesos)
    return pesos / pesos.sum()


def lineas_estandar(generador, modelos, mes, tipo_cliente):
    tallas, pesos_talla = peso_tallas()
    numero = generador.choice(list(LINEAS_ESTANDAR), p=list(LINEAS_ESTANDAR.values()))
    lineas = []
    usadas = set()
    while len(lineas) < numero:
        indice = generador.choice(len(MODELOS), p=pesos_modelos(modelos, mes))
        color = generador.choice(MODELOS[indice][4])
        talla = int(generador.choice(tallas, p=pesos_talla))
        if (indice, color, talla) in usadas:
            continue
        usadas.add((indice, color, talla))
        cantidad = int(generador.integers(1, 3)) if tipo_cliente == "PARTICULAR" else int(generador.integers(2, 13))
        lineas.append((indice, color, talla, cantidad, MODELOS[indice][1], False))
    return lineas


def lineas_custom(generador, modelos, mes):
    tallas, pesos_talla = peso_tallas()
    indice = generador.choice(len(MODELOS), p=pesos_modelos(modelos, mes, solo_custom=True))
    color = generador.choice(MODELOS[indice][4])
    total = int(generador.integers(config.SINTETICO_MINIMO_CUSTOM, 61))
    numero_tallas = int(generador.integers(2, 6))
    elegidas = sorted(generador.choice(tallas, size=numero_tallas, replace=False, p=pesos_talla))
    reparto = generador.multinomial(total - numero_tallas, np.full(numero_tallas, 1 / numero_tallas)) + 1
    precio = round(MODELOS[indice][1] + generador.uniform(*RECARGO_CUSTOM), 2)
    return [(indice, color, int(talla), int(cantidad), precio, True) for talla, cantidad in zip(elegidas, reparto)]


def crear_pedidos_y_lineas(generador, modelos, clientes, actividad):
    meses, cuantos = repartir_pedidos_por_mes(generador)
    corte = (meses[-1] + 1).to_timestamp() - pd.Timedelta(seconds=1)
    borradores = []
    for mes, numero in zip(meses, cuantos):
        for _ in range(numero):
            cliente = clientes.iloc[generador.choice(len(clientes), p=actividad)]
            es_custom = generador.random() < PROBABILIDAD_CUSTOM[cliente["tipo_cliente"]]
            borradores.append((fecha_aleatoria(generador, mes), cliente, "CUSTOM" if es_custom else "ESTANDAR", mes))
    borradores.sort(key=lambda b: b[0])

    pedidos, lineas = [], []
    for id_pedido, (fecha, cliente, tipo, mes) in enumerate(borradores, start=1):
        detalle = lineas_custom(generador, modelos, mes) if tipo == "CUSTOM" else lineas_estandar(generador, modelos, mes, cliente["tipo_cliente"])
        importe = 0.0
        for indice, color, talla, cantidad, precio, personalizada in detalle:
            subtotal = round(cantidad * precio, 2)
            importe += subtotal
            lineas.append({
                "id_linea": len(lineas) + 1,
                "id_pedido": id_pedido,
                "id_modelo": indice + 1,
                "color": color,
                "talla": talla,
                "cantidad": cantidad,
                "precio_unitario": precio,
                "subtotal_linea": subtotal,
                "personalizada": personalizada,
            })
        pedidos.append({
            "id_pedido": id_pedido,
            "ref_odoo": f"SSO{id_pedido:04d}",
            "fecha_pedido": fecha,
            "id_cliente": cliente["id_cliente"],
            "tipo": tipo,
            "estado": elegir_estado(generador, (corte - fecha).days, tipo),
            "importe_total": round(importe, 2),
        })
    return pd.DataFrame(pedidos), pd.DataFrame(lineas), corte


def crear_stock(generador, corte):
    tallas, pesos_talla = peso_tallas()
    filas = []
    for indice, (_, _, _, popularidad, colores) in enumerate(MODELOS):
        for color in colores:
            for talla, peso in zip(tallas, pesos_talla):
                media = 3 + popularidad * peso * 300
                filas.append({
                    "id_modelo": indice + 1,
                    "color": color,
                    "talla": int(talla),
                    "stock_disponible": int(generador.poisson(media)),
                    "stock_minimo": STOCK_MINIMO,
                    "fecha_corte": corte,
                })
    return pd.DataFrame(filas)


def generar(semilla=config.SEMILLA):
    generador = np.random.default_rng(semilla)
    modelos = crear_modelos()
    clientes, actividad = crear_clientes(generador)
    pedidos, lineas, corte = crear_pedidos_y_lineas(generador, modelos, clientes, actividad)
    stock = crear_stock(generador, corte)
    return {"clientes": clientes, "modelos": modelos, "pedidos": pedidos, "lineas": lineas, "stock": stock}


def introducir_incidencias(tablas):
    tablas = {nombre: df.astype(object).copy() for nombre, df in tablas.items()}
    pedidos, lineas, stock = tablas["pedidos"], tablas["lineas"], tablas["stock"]
    introducidas = []

    def anotar(tabla, registro, regla):
        introducidas.append({"tabla": tabla, "registro": str(registro), "regla_esperada": regla})

    lineas.loc[0, "id_pedido"] = 99999
    anotar("lineas", lineas.loc[0, "id_linea"], "03 · id_pedido inexistente")
    pedidos.loc[1, "fecha_pedido"] = "2025-02-30 10:00:00"
    anotar("pedidos", pedidos.loc[1, "ref_odoo"], "04 · fecha nula o imposible")
    lineas.loc[2, "cantidad"] = -3
    anotar("lineas", lineas.loc[2, "id_linea"], "05 · cantidad nula, cero o negativa")
    lineas.loc[3, "precio_unitario"] = "abc"
    anotar("lineas", lineas.loc[3, "id_linea"], "06 · precio no numérico o negativo")
    pedidos.loc[4, "estado"] = "ENVIADO"
    anotar("pedidos", pedidos.loc[4, "ref_odoo"], "07 · estado fuera de catálogo")
    lineas.loc[5, "talla"] = 50
    anotar("lineas", lineas.loc[5, "id_linea"], "08 · talla no válida")
    pedidos.loc[6, "id_cliente"] = None
    anotar("pedidos", pedidos.loc[6, "ref_odoo"], "09 · pedido sin cliente")
    pedidos.loc[7, "importe_total"] = float(pedidos.loc[7, "importe_total"]) + 100
    anotar("pedidos", pedidos.loc[7, "ref_odoo"], "12 · importe_total")
    stock.loc[0, "stock_disponible"] = -4
    anotar("stock", f"{stock.loc[0, 'id_modelo']}/{stock.loc[0, 'color']}/{stock.loc[0, 'talla']}", "11 · stock nulo o negativo")

    tablas["pedidos"] = pd.concat([pedidos, pedidos.iloc[[10]]], ignore_index=True)
    anotar("pedidos", pedidos.loc[10, "id_pedido"], "02 · id_pedido duplicado")
    tablas["stock"] = pd.concat([stock, stock.iloc[[20]]], ignore_index=True)
    anotar("stock", f"{stock.loc[20, 'id_modelo']}/{stock.loc[20, 'color']}/{stock.loc[20, 'talla']}", "11 · modelo, color y talla duplicados")
    return tablas, pd.DataFrame(introducidas)


def preparar(tablas):
    salida = {}
    for nombre, df in tablas.items():
        df = df.copy()
        for columna in df.columns:
            if pd.api.types.is_datetime64_any_dtype(df[columna]):
                df[columna] = df[columna].dt.strftime(config.FORMATO_FECHA)
            elif df[columna].map(lambda v: isinstance(v, (bool, np.bool_))).all():
                df[columna] = formato_bool(df[columna])
            elif df[columna].map(lambda v: isinstance(v, pd.Timestamp)).any():
                df[columna] = df[columna].map(lambda v: v.strftime(config.FORMATO_FECHA) if isinstance(v, pd.Timestamp) else v)
        salida[nombre] = df
    return salida


def guardar(tablas, carpeta):
    carpeta = Path(carpeta)
    carpeta.mkdir(parents=True, exist_ok=True)
    for nombre, df in preparar(tablas).items():
        df.to_csv(carpeta / config.ARCHIVOS[nombre], index=False, encoding="utf-8", float_format="%.2f")


def main(argumentos=None):
    parser = argparse.ArgumentParser(description="Genera el histórico SINTÉTICO de Sneaker Factory (nunca se mezcla con ACC)")
    parser.add_argument("--semilla", type=int, default=config.SEMILLA)
    parser.add_argument("--salida", type=Path, default=config.CARPETA_SINTETICOS)
    args = parser.parse_args(argumentos)

    tablas = generar(args.semilla)
    guardar(tablas, args.salida)
    con_errores, introducidas = introducir_incidencias(tablas)
    carpeta_errores = args.salida / config.CARPETA_SINTETICOS_INCIDENCIAS.name
    guardar(con_errores, carpeta_errores)
    introducidas.to_csv(carpeta_errores / "incidencias_introducidas.csv", index=False, encoding="utf-8")

    pedidos = tablas["pedidos"]
    print(f"Datos SINTÉTICOS (semilla {args.semilla}) en {args.salida}")
    print(f"  clientes: {len(tablas['clientes'])} · modelos: {len(tablas['modelos'])} · pedidos: {len(pedidos)} · "
          f"líneas: {len(tablas['lineas'])} · stock: {len(tablas['stock'])}")
    print(f"  meses: {pedidos['fecha_pedido'].dt.to_period('M').nunique()} "
          f"({pedidos['fecha_pedido'].min():%Y-%m} a {pedidos['fecha_pedido'].max():%Y-%m})")
    print(f"  copia con {len(introducidas)} incidencias introducidas en {carpeta_errores}")


if __name__ == "__main__":
    main()
