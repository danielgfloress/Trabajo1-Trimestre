# Lectura y validación de los CSV de Acceso a Datos.
# Pasos: 1) leer los CSV, 2) convertir tipos, 3) aplicar las 12 reglas de calidad, 4) resumen de calidad.
from datetime import datetime
from pathlib import Path

import pandas as pd

import config


# Apunta una incidencia (un problema encontrado en los datos) en la lista
def nueva_incidencia(lista, tabla, registro, regla, gravedad, tratamiento):
    lista.append({
        "tabla": tabla,
        "registro": str(registro),
        "regla": regla,
        "gravedad": gravedad,
        "tratamiento": tratamiento,
    })


# Paso 1: lee los 5 CSV y comprueba que existen, que no están vacíos y que tienen sus columnas
def cargar_tablas(carpeta):
    carpeta = Path(carpeta)
    tablas = {}
    manifiesto = []
    incidencias = []

    for nombre, archivo in config.ARCHIVOS.items():
        # Ruta completa del CSV (carpeta + nombre del fichero)
        ruta = carpeta / archivo

        # Si el fichero no existe, es un error bloqueante
        if not ruta.exists():
            nueva_incidencia(incidencias, nombre, archivo, "01 · fichero inexistente", "bloqueante", "no se publica")
            continue

        # Se lee todo como texto (dtype=str) para no perder nada; los tipos se convierten en el paso 2.
        # Solo las celdas vacías se consideran valores ausentes
        try:
            df = pd.read_csv(ruta, dtype=str, encoding="utf-8", keep_default_na=False, na_values=[""])
        except pd.errors.EmptyDataError:
            # El CSV está completamente vacío
            nueva_incidencia(incidencias, nombre, archivo, "01 · fichero vacío", "bloqueante", "no se publica")
            continue

        # Columnas obligatorias que no están en el CSV
        faltan = []
        for columna in config.COLUMNAS_OBLIGATORIAS[nombre]:
            if columna not in df.columns:
                faltan.append(columna)
        if faltan:
            nueva_incidencia(incidencias, nombre, archivo, "01 · faltan columnas: " + ", ".join(faltan), "bloqueante", "no se publica")
            continue

        # Tiene cabecera pero ninguna fila
        if df.empty:
            nueva_incidencia(incidencias, nombre, archivo, "01 · sin filas de datos", "bloqueante", "no se publica")
            continue

        tablas[nombre] = df
        # Manifiesto: qué fichero se leyó, cuántas filas y columnas, tamaño y fecha
        manifiesto.append({
            "fichero": archivo,
            "fecha_analisis": datetime.now().strftime(config.FORMATO_FECHA),
            "filas": len(df),
            "columnas": len(df.columns),
            "bytes": ruta.stat().st_size,
            "modificado": datetime.fromtimestamp(ruta.stat().st_mtime).strftime(config.FORMATO_FECHA),
        })

    return tablas, pd.DataFrame(manifiesto), incidencias


# Paso 2: convierte cada columna a su tipo (número, fecha o sí/no)
def convertir_tipos(tablas):
    numericas = {
        "modelos": ["precio_base"],
        "pedidos": ["importe_total"],
        "lineas": ["talla", "cantidad", "precio_unitario", "subtotal_linea"],
        "stock": ["talla", "stock_disponible", "stock_minimo"],
    }
    fechas = {"pedidos": ["fecha_pedido"], "stock": ["fecha_corte"]}
    booleanas = {"clientes": ["activo"], "modelos": ["admite_custom", "activo"], "lineas": ["personalizada"]}

    # Quita los espacios del principio y del final de todos los textos
    for nombre in tablas:
        for columna in tablas[nombre].columns:
            if pd.api.types.is_string_dtype(tablas[nombre][columna]):
                tablas[nombre][columna] = tablas[nombre][columna].str.strip()

    # A número. errors="coerce": si no se puede (por ejemplo "abc"), queda NaN (vacío) en vez de dar error
    for nombre, columnas in numericas.items():
        for columna in columnas:
            tablas[nombre][columna] = pd.to_numeric(tablas[nombre][columna], errors="coerce")

    # A fecha. Si la fecha es imposible (por ejemplo 30 de febrero), queda NaT (vacío)
    for nombre, columnas in fechas.items():
        for columna in columnas:
            tablas[nombre][columna] = pd.to_datetime(tablas[nombre][columna], format=config.FORMATO_FECHA, errors="coerce")

    # "true"/"false" del CSV a True/False
    for nombre, columnas in booleanas.items():
        for columna in columnas:
            tablas[nombre][columna] = tablas[nombre][columna].str.lower().map({"true": True, "false": False})
    return tablas


# Nombre de una fila de stock en las incidencias: modelo/color/talla
def nombre_stock(fila):
    return f"{fila['id_modelo']}/{fila['color']}/{fila['talla']}"


# Paso 3: aplica las 12 reglas de calidad del PDF.
# Cada fallo es una incidencia con su gravedad:
#   - bloqueante: no se publica nada
#   - recuperable: se quita esa fila y se sigue
#   - advertencia: solo se avisa
def validar(tablas):
    incidencias = []
    # Índices de las filas que se van a quitar de cada tabla (set = sin repetidos)
    rechazos = {}
    for nombre in tablas:
        rechazos[nombre] = set()

    clientes = tablas["clientes"]
    modelos = tablas["modelos"]
    pedidos = tablas["pedidos"]
    lineas = tablas["lineas"]
    stock = tablas["stock"]

    # Regla 02: IDs que no se pueden repetir.
    # duplicated() marca True las repeticiones; la primera aparición se queda
    claves = [("clientes", "id_cliente"), ("clientes", "codigo_odoo"), ("modelos", "id_modelo"), ("modelos", "codigo_modelo"),
              ("pedidos", "id_pedido"), ("pedidos", "ref_odoo"), ("lineas", "id_linea")]
    for nombre, clave in claves:
        df = tablas[nombre]
        repetidos = df[df[clave].notna() & df.duplicated(clave, keep="first")]
        for indice, fila in repetidos.iterrows():
            nueva_incidencia(incidencias, nombre, fila[clave], f"02 · {clave} duplicado", "recuperable", "se conserva la primera aparición")
            rechazos[nombre].add(indice)

    # Regla 03: claves huérfanas (apuntan a algo que no existe). isin = "está en", ~ = NO
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
        nueva_incidencia(incidencias, "stock", nombre_stock(fila), "03 · id_modelo inexistente", "bloqueante", "no se publica")

    # Regla 04: fecha vacía o imposible (quedó NaT al convertirla)
    for indice, fila in pedidos[pedidos["fecha_pedido"].isna()].iterrows():
        nueva_incidencia(incidencias, "pedidos", fila["ref_odoo"], "04 · fecha nula o imposible", "recuperable", "pedido rechazado")
        rechazos["pedidos"].add(indice)

    # Regla 05: cantidad vacía, cero o negativa
    for indice, fila in lineas[lineas["cantidad"].isna() | (lineas["cantidad"] <= 0)].iterrows():
        nueva_incidencia(incidencias, "lineas", fila["id_linea"], "05 · cantidad nula, cero o negativa", "recuperable", "línea rechazada")
        rechazos["lineas"].add(indice)

    # Regla 06: precio no numérico o negativo
    for indice, fila in lineas[lineas["precio_unitario"].isna() | (lineas["precio_unitario"] < 0)].iterrows():
        nueva_incidencia(incidencias, "lineas", fila["id_linea"], "06 · precio no numérico o negativo", "recuperable", "línea rechazada")
        rechazos["lineas"].add(indice)
    for _, fila in modelos[modelos["precio_base"].isna() | (modelos["precio_base"] <= 0)].iterrows():
        nueva_incidencia(incidencias, "modelos", fila["codigo_modelo"], "06 · precio base no numérico o no positivo", "advertencia", "se conserva el modelo")

    # Regla 07: estado o tipo que no está en el catálogo de config.py
    for indice, fila in pedidos[~pedidos["estado"].isin(config.ESTADOS_VALIDOS)].iterrows():
        nueva_incidencia(incidencias, "pedidos", fila["ref_odoo"], "07 · estado fuera de catálogo: " + str(fila["estado"]), "recuperable", "pedido rechazado")
        rechazos["pedidos"].add(indice)
    for indice, fila in pedidos[~pedidos["tipo"].isin(config.TIPOS_PEDIDO)].iterrows():
        nueva_incidencia(incidencias, "pedidos", fila["ref_odoo"], "07 · tipo fuera de catálogo: " + str(fila["tipo"]), "recuperable", "pedido rechazado")
        rechazos["pedidos"].add(indice)
    for _, fila in clientes[~clientes["tipo_cliente"].isin(config.TIPOS_CLIENTE)].iterrows():
        nueva_incidencia(incidencias, "clientes", fila["codigo_odoo"], "07 · tipo de cliente fuera de catálogo", "advertencia", "se conserva el cliente")

    # Regla 08: talla fuera de 36-46
    for indice, fila in lineas[~lineas["talla"].isin(config.TALLAS_VALIDAS)].iterrows():
        nueva_incidencia(incidencias, "lineas", fila["id_linea"], "08 · talla no válida: " + str(fila["talla"]), "recuperable", "línea rechazada")
        rechazos["lineas"].add(indice)
    for indice, fila in stock[~stock["talla"].isin(config.TALLAS_VALIDAS)].iterrows():
        nueva_incidencia(incidencias, "stock", nombre_stock(fila), "08 · talla no válida", "recuperable", "fila rechazada")
        rechazos["stock"].add(indice)

    # Regla 09: pedido sin cliente o línea sin modelo
    for indice, fila in pedidos[pedidos["id_cliente"].isna()].iterrows():
        nueva_incidencia(incidencias, "pedidos", fila["ref_odoo"], "09 · pedido sin cliente", "recuperable", "pedido rechazado")
        rechazos["pedidos"].add(indice)
    for indice, fila in lineas[lineas["id_modelo"].isna()].iterrows():
        nueva_incidencia(incidencias, "lineas", fila["id_linea"], "09 · línea sin modelo", "recuperable", "línea rechazada")
        rechazos["lineas"].add(indice)

    # Regla 10: misma línea repetida (mismo pedido, modelo, color y talla). keep=False marca todas las repetidas
    repetidas = lineas[lineas.duplicated(["id_pedido", "id_modelo", "color", "talla"], keep=False)]
    for _, fila in repetidas.iterrows():
        nueva_incidencia(incidencias, "lineas", fila["id_linea"], "10 · mismo pedido, modelo, color y talla en varias líneas", "advertencia", "se conservan y se suman")

    # Regla 11: stock vacío o negativo, y modelo-color-talla repetido
    for indice, fila in stock[stock["stock_disponible"].isna() | (stock["stock_disponible"] < 0)].iterrows():
        nueva_incidencia(incidencias, "stock", nombre_stock(fila), "11 · stock nulo o negativo", "recuperable", "fila rechazada")
        rechazos["stock"].add(indice)
    for indice, fila in stock[stock.duplicated(["id_modelo", "color", "talla"], keep="first")].iterrows():
        nueva_incidencia(incidencias, "stock", nombre_stock(fila), "11 · modelo, color y talla duplicados", "recuperable", "se conserva la primera aparición")
        rechazos["stock"].add(indice)

    # Regla 12 (a): el subtotal de la línea tiene que ser cantidad × precio
    calculado = (lineas["cantidad"] * lineas["precio_unitario"]).round(2)
    mal_subtotal = lineas[(calculado - lineas["subtotal_linea"]).abs() > config.TOLERANCIA_IMPORTE]
    for _, fila in mal_subtotal.iterrows():
        nueva_incidencia(incidencias, "lineas", fila["id_linea"], "12 · subtotal distinto de cantidad × precio", "advertencia", "se usa cantidad × precio")

    # Regla 12 (b): el total del pedido tiene que ser la suma de sus líneas
    suma_lineas = lineas.groupby("id_pedido")["subtotal_linea"].sum().reset_index()
    comparar = pedidos.merge(suma_lineas, on="id_pedido", how="left")
    comparar["subtotal_linea"] = comparar["subtotal_linea"].fillna(0)
    descuadres = comparar[(comparar["importe_total"] - comparar["subtotal_linea"]).abs() > config.TOLERANCIA_IMPORTE]
    for _, fila in descuadres.iterrows():
        nueva_incidencia(incidencias, "pedidos", fila["ref_odoo"], f"12 · importe_total {fila['importe_total']} ≠ suma de líneas {fila['subtotal_linea']:.2f}", "advertencia", "se usa la suma de líneas")

    # Regla 12 (c): pedidos con fecha posterior a la fecha de corte de la exportación
    fecha_corte = stock["fecha_corte"].max()
    if pd.notna(fecha_corte):
        for _, fila in pedidos[pedidos["fecha_pedido"] > fecha_corte].iterrows():
            nueva_incidencia(incidencias, "pedidos", fila["ref_odoo"], "12 · pedido posterior a la fecha de corte", "advertencia", "se conserva y se revisa")

    # Regla 12 (d): pedidos sin ninguna línea
    for _, fila in pedidos[~pedidos["id_pedido"].isin(lineas["id_pedido"])].iterrows():
        nueva_incidencia(incidencias, "pedidos", fila["ref_odoo"], "12 · pedido sin líneas", "advertencia", "cuenta en actividad, no en ventas")

    # Se quitan las filas rechazadas (en memoria: el CSV original no se toca)
    limpias = {}
    for nombre in tablas:
        limpias[nombre] = tablas[nombre].drop(index=list(rechazos[nombre]))

    # Si se ha rechazado un pedido (y no queda otra copia válida de él), también se quitan sus líneas
    pedidos_rechazados = tablas["pedidos"].loc[list(rechazos["pedidos"]), "id_pedido"]
    pedidos_rechazados = pedidos_rechazados[~pedidos_rechazados.isin(limpias["pedidos"]["id_pedido"])]
    arrastradas = limpias["lineas"]["id_pedido"].isin(pedidos_rechazados)
    for _, fila in limpias["lineas"][arrastradas].iterrows():
        nueva_incidencia(incidencias, "lineas", fila["id_linea"], "línea de un pedido rechazado", "advertencia", "línea rechazada")
    limpias["lineas"] = limpias["lineas"][~arrastradas]

    return limpias, incidencias


# Paso 4: resumen por tabla: filas de entrada, válidas, rechazadas y % de calidad
def resumir_calidad(tablas, limpias, incidencias):
    filas = []
    for nombre in config.ARCHIVOS:
        entrada = 0
        if nombre in tablas:
            entrada = len(tablas[nombre])
        validas = 0
        if nombre in limpias:
            validas = len(limpias[nombre])

        # Incidencias de esta tabla y cuántas son bloqueantes
        de_tabla = 0
        bloqueantes = 0
        for incidencia in incidencias:
            if incidencia["tabla"] == nombre:
                de_tabla += 1
                if incidencia["gravedad"] == "bloqueante":
                    bloqueantes += 1

        porcentaje = 0.0
        if entrada:
            porcentaje = round(validas / entrada * 100, 1)

        filas.append({
            "tabla": nombre,
            "filas_entrada": entrada,
            "filas_validas": validas,
            "filas_rechazadas": entrada - validas,
            "porcentaje_calidad": porcentaje,
            "incidencias": de_tabla,
            "bloqueantes": bloqueantes,
        })
    return pd.DataFrame(filas)


# Junta todos los pasos y devuelve un diccionario con los datos limpios, las incidencias y el estado
def ejecutar_pipeline(carpeta=config.CARPETA_ENTRADA, origen="ACC · REAL"):
    inicio = datetime.now()
    tablas, manifiesto, incidencias = cargar_tablas(carpeta)

    if len(tablas) < len(config.ARCHIVOS):
        # Falta algún CSV: no se puede seguir
        estado = "error de carga"
        limpias = {}
    else:
        tablas = convertir_tipos(tablas)
        limpias, nuevas = validar(tablas)
        incidencias = incidencias + nuevas

        # Con un solo error bloqueante, los datos no se publican
        hay_bloqueantes = False
        for incidencia in incidencias:
            if incidencia["gravedad"] == "bloqueante":
                hay_bloqueantes = True
        if hay_bloqueantes:
            estado = "datos inválidos"
        else:
            estado = "correcto"

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


# Guarda en CSV las incidencias, el resumen de calidad y el manifiesto
def guardar_calidad(resultado, carpeta_salida=config.CARPETA_SALIDA):
    carpeta_salida = Path(carpeta_salida)
    carpeta_salida.mkdir(exist_ok=True)
    resultado["incidencias"].to_csv(carpeta_salida / "incidencias.csv", index=False, encoding="utf-8")
    resultado["resumen_calidad"].to_csv(carpeta_salida / "resumen_calidad.csv", index=False, encoding="utf-8")
    resultado["manifiesto"].to_csv(carpeta_salida / "manifiesto_origen.csv", index=False, encoding="utf-8")


# Añade una línea al log con la fecha y la hora (modo "a": añade al final sin borrar lo anterior)
def registrar_log(texto, archivo="ejecuciones.log", carpeta=config.CARPETA_LOGS):
    carpeta = Path(carpeta)
    carpeta.mkdir(parents=True, exist_ok=True)
    with open(carpeta / archivo, "a", encoding="utf-8") as fichero:
        fichero.write(f"{datetime.now().strftime(config.FORMATO_FECHA)} | {texto}\n")


# Solo se ejecuta si se lanza este archivo directamente: python pipeline.py
if __name__ == "__main__":
    resultado = ejecutar_pipeline()
    guardar_calidad(resultado)
    print("Estado:", resultado["estado"])
    print(resultado["resumen_calidad"].to_string(index=False))
    if not resultado["incidencias"].empty:
        print()
        print(resultado["incidencias"].to_string(index=False))
