from datetime import datetime
from pathlib import Path

import pandas as pd

import config


def nueva_incidencia(lista, tabla, registro, regla, gravedad, tratamiento):
    lista.append({
        "tabla": tabla,
        "registro": str(registro),
        "regla": regla,
        "gravedad": gravedad,
        "tratamiento": tratamiento,
    })


def cargar_tablas(carpeta):
    carpeta = Path(carpeta)
    tablas = {}
    manifiesto = []
    incidencias = []

    for nombre, archivo in config.ARCHIVOS.items():
        ruta = carpeta / archivo
        if not ruta.exists():
            nueva_incidencia(incidencias, nombre, archivo, "01 · fichero inexistente", "bloqueante", "no se publica")
            continue

        try:
            df = pd.read_csv(ruta, dtype=str, encoding="utf-8", keep_default_na=False, na_values=[""])
        except pd.errors.EmptyDataError:
            nueva_incidencia(incidencias, nombre, archivo, "01 · fichero vacío", "bloqueante", "no se publica")
            continue

        faltan = [c for c in config.COLUMNAS_OBLIGATORIAS[nombre] if c not in df.columns]
        if faltan:
            nueva_incidencia(incidencias, nombre, archivo, "01 · faltan columnas: " + ", ".join(faltan), "bloqueante", "no se publica")
            continue
        if df.empty:
            nueva_incidencia(incidencias, nombre, archivo, "01 · sin filas de datos", "bloqueante", "no se publica")
            continue

        tablas[nombre] = df
        manifiesto.append({
            "fichero": archivo,
            "fecha_analisis": datetime.now().strftime(config.FORMATO_FECHA),
            "filas": len(df),
            "columnas": len(df.columns),
            "bytes": ruta.stat().st_size,
            "modificado": datetime.fromtimestamp(ruta.stat().st_mtime).strftime(config.FORMATO_FECHA),
        })

    return tablas, pd.DataFrame(manifiesto), incidencias


def convertir_tipos(tablas):
    numericas = {
        "modelos": ["precio_base"],
        "pedidos": ["importe_total"],
        "lineas": ["talla", "cantidad", "precio_unitario", "subtotal_linea"],
        "stock": ["talla", "stock_disponible", "stock_minimo"],
    }
    fechas = {"pedidos": ["fecha_pedido"], "stock": ["fecha_corte"]}
    booleanas = {"clientes": ["activo"], "modelos": ["admite_custom", "activo"], "lineas": ["personalizada"]}

    for nombre in tablas:
        for columna in tablas[nombre].columns:
            if pd.api.types.is_string_dtype(tablas[nombre][columna]):
                tablas[nombre][columna] = tablas[nombre][columna].str.strip()
    for nombre, columnas in numericas.items():
        for columna in columnas:
            tablas[nombre][columna] = pd.to_numeric(tablas[nombre][columna], errors="coerce")
    for nombre, columnas in fechas.items():
        for columna in columnas:
            tablas[nombre][columna] = pd.to_datetime(tablas[nombre][columna], format=config.FORMATO_FECHA, errors="coerce")
    for nombre, columnas in booleanas.items():
        for columna in columnas:
            tablas[nombre][columna] = tablas[nombre][columna].str.lower().map({"true": True, "false": False})
    return tablas


def validar(tablas):
    incidencias = []
    rechazos = {nombre: set() for nombre in tablas}
    clientes = tablas["clientes"]
    modelos = tablas["modelos"]
    pedidos = tablas["pedidos"]
    lineas = tablas["lineas"]
    stock = tablas["stock"]

    claves = [("clientes", "id_cliente"), ("clientes", "codigo_odoo"), ("modelos", "id_modelo"), ("modelos", "codigo_modelo"),
              ("pedidos", "id_pedido"), ("pedidos", "ref_odoo"), ("lineas", "id_linea")]
    for nombre, clave in claves:
        df = tablas[nombre]
        repetidos = df[df[clave].notna() & df.duplicated(clave, keep="first")]
        for indice, fila in repetidos.iterrows():
            nueva_incidencia(incidencias, nombre, fila[clave], f"02 · {clave} duplicado", "recuperable", "se conserva la primera aparición")
            rechazos[nombre].add(indice)

    huerfanas = lineas[lineas["id_pedido"].notna() & ~lineas["id_pedido"].isin(pedidos["id_pedido"])]
    for _, fila in huerfanas.iterrows():
        nueva_incidencia(incidencias, "lineas", fila["id_linea"], "03 · id_pedido inexistente: " + fila["id_pedido"], "bloqueante", "no se publica")
    huerfanas = lineas[lineas["id_modelo"].notna() & ~lineas["id_modelo"].isin(modelos["id_modelo"])]
    for _, fila in huerfanas.iterrows():
        nueva_incidencia(incidencias, "lineas", fila["id_linea"], "03 · id_modelo inexistente: " + fila["id_modelo"], "bloqueante", "no se publica")
    huerfanas = pedidos[pedidos["id_cliente"].notna() & ~pedidos["id_cliente"].isin(clientes["id_cliente"])]
    for _, fila in huerfanas.iterrows():
        nueva_incidencia(incidencias, "pedidos", fila["ref_odoo"], "03 · id_cliente inexistente: " + fila["id_cliente"], "bloqueante", "no se publica")
    huerfanas = stock[stock["id_modelo"].notna() & ~stock["id_modelo"].isin(modelos["id_modelo"])]
    for _, fila in huerfanas.iterrows():
        nueva_incidencia(incidencias, "stock", f"{fila['id_modelo']}/{fila['color']}/{fila['talla']}", "03 · id_modelo inexistente", "bloqueante", "no se publica")

    for indice, fila in pedidos[pedidos["fecha_pedido"].isna()].iterrows():
        nueva_incidencia(incidencias, "pedidos", fila["ref_odoo"], "04 · fecha nula o imposible", "recuperable", "pedido rechazado")
        rechazos["pedidos"].add(indice)

    for indice, fila in lineas[lineas["cantidad"].isna() | (lineas["cantidad"] <= 0)].iterrows():
        nueva_incidencia(incidencias, "lineas", fila["id_linea"], "05 · cantidad nula, cero o negativa", "recuperable", "línea rechazada")
        rechazos["lineas"].add(indice)

    for indice, fila in lineas[lineas["precio_unitario"].isna() | (lineas["precio_unitario"] < 0)].iterrows():
        nueva_incidencia(incidencias, "lineas", fila["id_linea"], "06 · precio no numérico o negativo", "recuperable", "línea rechazada")
        rechazos["lineas"].add(indice)
    for _, fila in modelos[modelos["precio_base"].isna() | (modelos["precio_base"] <= 0)].iterrows():
        nueva_incidencia(incidencias, "modelos", fila["codigo_modelo"], "06 · precio base no numérico o no positivo", "advertencia", "se conserva el modelo")

    for indice, fila in pedidos[~pedidos["estado"].isin(config.ESTADOS_VALIDOS)].iterrows():
        nueva_incidencia(incidencias, "pedidos", fila["ref_odoo"], "07 · estado fuera de catálogo: " + str(fila["estado"]), "recuperable", "pedido rechazado")
        rechazos["pedidos"].add(indice)
    for indice, fila in pedidos[~pedidos["tipo"].isin(config.TIPOS_PEDIDO)].iterrows():
        nueva_incidencia(incidencias, "pedidos", fila["ref_odoo"], "07 · tipo fuera de catálogo: " + str(fila["tipo"]), "recuperable", "pedido rechazado")
        rechazos["pedidos"].add(indice)
    for _, fila in clientes[~clientes["tipo_cliente"].isin(config.TIPOS_CLIENTE)].iterrows():
        nueva_incidencia(incidencias, "clientes", fila["codigo_odoo"], "07 · tipo de cliente fuera de catálogo", "advertencia", "se conserva el cliente")

    for indice, fila in lineas[~lineas["talla"].isin(config.TALLAS_VALIDAS)].iterrows():
        nueva_incidencia(incidencias, "lineas", fila["id_linea"], "08 · talla no válida: " + str(fila["talla"]), "recuperable", "línea rechazada")
        rechazos["lineas"].add(indice)
    for indice, fila in stock[~stock["talla"].isin(config.TALLAS_VALIDAS)].iterrows():
        nueva_incidencia(incidencias, "stock", f"{fila['id_modelo']}/{fila['color']}/{fila['talla']}", "08 · talla no válida", "recuperable", "fila rechazada")
        rechazos["stock"].add(indice)

    for indice, fila in pedidos[pedidos["id_cliente"].isna()].iterrows():
        nueva_incidencia(incidencias, "pedidos", fila["ref_odoo"], "09 · pedido sin cliente", "recuperable", "pedido rechazado")
        rechazos["pedidos"].add(indice)
    for indice, fila in lineas[lineas["id_modelo"].isna()].iterrows():
        nueva_incidencia(incidencias, "lineas", fila["id_linea"], "09 · línea sin modelo", "recuperable", "línea rechazada")
        rechazos["lineas"].add(indice)

    repetidas = lineas[lineas.duplicated(["id_pedido", "id_modelo", "color", "talla"], keep=False)]
    for _, fila in repetidas.iterrows():
        nueva_incidencia(incidencias, "lineas", fila["id_linea"], "10 · mismo pedido, modelo, color y talla en varias líneas", "advertencia", "se conservan y se suman")

    for indice, fila in stock[stock["stock_disponible"].isna() | (stock["stock_disponible"] < 0)].iterrows():
        nueva_incidencia(incidencias, "stock", f"{fila['id_modelo']}/{fila['color']}/{fila['talla']}", "11 · stock nulo o negativo", "recuperable", "fila rechazada")
        rechazos["stock"].add(indice)
    for indice, fila in stock[stock.duplicated(["id_modelo", "color", "talla"], keep="first")].iterrows():
        nueva_incidencia(incidencias, "stock", f"{fila['id_modelo']}/{fila['color']}/{fila['talla']}", "11 · modelo, color y talla duplicados", "recuperable", "se conserva la primera aparición")
        rechazos["stock"].add(indice)

    calculado = (lineas["cantidad"] * lineas["precio_unitario"]).round(2)
    mal_subtotal = lineas[(calculado - lineas["subtotal_linea"]).abs() > config.TOLERANCIA_IMPORTE]
    for _, fila in mal_subtotal.iterrows():
        nueva_incidencia(incidencias, "lineas", fila["id_linea"], "12 · subtotal distinto de cantidad × precio", "advertencia", "se usa cantidad × precio")
    suma_lineas = lineas.groupby("id_pedido")["subtotal_linea"].sum()
    comparar = pedidos.set_index("id_pedido")[["ref_odoo", "importe_total"]].join(suma_lineas, how="left")
    comparar["subtotal_linea"] = comparar["subtotal_linea"].fillna(0)
    descuadres = comparar[(comparar["importe_total"] - comparar["subtotal_linea"]).abs() > config.TOLERANCIA_IMPORTE]
    for _, fila in descuadres.iterrows():
        nueva_incidencia(incidencias, "pedidos", fila["ref_odoo"], f"12 · importe_total {fila['importe_total']} ≠ suma de líneas {fila['subtotal_linea']:.2f}", "advertencia", "se usa la suma de líneas")
    fecha_corte = stock["fecha_corte"].max()
    if pd.notna(fecha_corte):
        for _, fila in pedidos[pedidos["fecha_pedido"] > fecha_corte].iterrows():
            nueva_incidencia(incidencias, "pedidos", fila["ref_odoo"], "12 · pedido posterior a la fecha de corte", "advertencia", "se conserva y se revisa")
    for _, fila in pedidos[~pedidos["id_pedido"].isin(lineas["id_pedido"])].iterrows():
        nueva_incidencia(incidencias, "pedidos", fila["ref_odoo"], "12 · pedido sin líneas", "advertencia", "cuenta en actividad, no en ventas")

    limpias = {nombre: tablas[nombre].drop(index=list(rechazos[nombre])) for nombre in tablas}
    pedidos_rechazados = tablas["pedidos"].loc[list(rechazos["pedidos"]), "id_pedido"]
    arrastradas = limpias["lineas"]["id_pedido"].isin(pedidos_rechazados)
    for _, fila in limpias["lineas"][arrastradas].iterrows():
        nueva_incidencia(incidencias, "lineas", fila["id_linea"], "línea de un pedido rechazado", "advertencia", "línea rechazada")
    limpias["lineas"] = limpias["lineas"][~arrastradas]

    return limpias, incidencias


def resumir_calidad(tablas, limpias, incidencias):
    filas = []
    for nombre in config.ARCHIVOS:
        entrada = len(tablas[nombre]) if nombre in tablas else 0
        validas = len(limpias[nombre]) if nombre in limpias else 0
        de_tabla = [i for i in incidencias if i["tabla"] == nombre]
        filas.append({
            "tabla": nombre,
            "filas_entrada": entrada,
            "filas_validas": validas,
            "filas_rechazadas": entrada - validas,
            "porcentaje_calidad": round(validas / entrada * 100, 1) if entrada else 0.0,
            "incidencias": len(de_tabla),
            "bloqueantes": sum(1 for i in de_tabla if i["gravedad"] == "bloqueante"),
        })
    return pd.DataFrame(filas)


def ejecutar_pipeline(carpeta=config.CARPETA_ENTRADA, origen="ACC · REAL"):
    inicio = datetime.now()
    tablas, manifiesto, incidencias = cargar_tablas(carpeta)

    if len(tablas) < len(config.ARCHIVOS):
        estado = "error de carga"
        limpias = {}
    else:
        tablas = convertir_tipos(tablas)
        limpias, nuevas = validar(tablas)
        incidencias += nuevas
        hay_bloqueantes = any(i["gravedad"] == "bloqueante" for i in incidencias)
        estado = "datos inválidos" if hay_bloqueantes else "correcto"

    df_incidencias = pd.DataFrame(incidencias, columns=["tabla", "registro", "regla", "gravedad", "tratamiento"])
    return {
        "origen": origen,
        "carpeta": str(carpeta),
        "estado": estado,
        "publicable": estado == "correcto",
        "hora_comprobacion": inicio,
        "segundos": (datetime.now() - inicio).total_seconds(),
        "tablas": limpias,
        "manifiesto": manifiesto,
        "incidencias": df_incidencias,
        "resumen_calidad": resumir_calidad(tablas, limpias, incidencias),
    }


def guardar_calidad(resultado, carpeta_salida=config.CARPETA_SALIDA):
    carpeta_salida = Path(carpeta_salida)
    carpeta_salida.mkdir(exist_ok=True)
    resultado["incidencias"].to_csv(carpeta_salida / "incidencias.csv", index=False, encoding="utf-8")
    resultado["resumen_calidad"].to_csv(carpeta_salida / "resumen_calidad.csv", index=False, encoding="utf-8")
    resultado["manifiesto"].to_csv(carpeta_salida / "manifiesto_origen.csv", index=False, encoding="utf-8")


if __name__ == "__main__":
    resultado = ejecutar_pipeline()
    guardar_calidad(resultado)
    print("Estado:", resultado["estado"])
    print(resultado["resumen_calidad"].to_string(index=False))
    if not resultado["incidencias"].empty:
        print()
        print(resultado["incidencias"].to_string(index=False))
