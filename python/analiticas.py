# Todos los cálculos del proyecto: cada función recibe tablas de pandas y devuelve una tabla nueva (DataFrame).
# Este archivo NO usa Streamlit: lo usan igual main.py (consola) y app_dashboard.py (navegador).
from pathlib import Path

import numpy as np
import pandas as pd

import config
import segmentacion

# Nombre de cada día de la semana (pandas numera el lunes como 0)
NOMBRE_DIA = {0: "lunes", 1: "martes", 2: "miércoles", 3: "jueves", 4: "viernes", 5: "sábado", 6: "domingo"}


# Guarda en df.attrs de dónde sale cada tabla (función, filas, fecha de corte y filtros): es el "linaje"
def poner_metadatos(df, funcion, filas_origen, fecha_corte, filtros=None):
    df.attrs["funcion"] = funcion
    df.attrs["filas_origen"] = filas_origen
    if pd.notna(fecha_corte):
        df.attrs["fecha_corte"] = str(fecha_corte.date())
    else:
        df.attrs["fecha_corte"] = "sin fecha"
    if filtros:
        df.attrs["filtros"] = filtros
    else:
        df.attrs["filtros"] = {}
    return df


# Fecha de corte = fecha de la foto del stock que exportó Acceso a Datos
def fecha_corte(tablas):
    if "stock_completo" in tablas:
        stock = tablas["stock_completo"]
    else:
        stock = tablas["stock"]
    return stock["fecha_corte"].max()


# VISTA BASE 1: una fila por LÍNEA de pedido.
# Une cada línea con su pedido, su modelo y su cliente (como un JOIN de SQL).
def lineas_enriquecidas(tablas):
    lineas = tablas["lineas"]
    pedidos = tablas["pedidos"]

    # Del modelo y del cliente solo nos quedamos con algunas columnas. Las dos tienen una columna "nombre",
    # así que se renombran para que no se confundan
    modelos = tablas["modelos"][["id_modelo", "codigo_modelo", "marca", "nombre", "categoria"]]
    modelos = modelos.rename(columns={"nombre": "modelo"})
    clientes = tablas["clientes"][["id_cliente", "codigo_odoo", "nombre", "tipo_cliente"]]
    clientes = clientes.rename(columns={"nombre": "cliente"})

    # merge = JOIN. how="left": se quedan todas las líneas.
    # validate="many_to_one": muchas líneas → un solo pedido. Si un pedido estuviera repetido,
    # pandas daría error en vez de duplicar filas sin avisar
    df = lineas.merge(pedidos, on="id_pedido", how="left", validate="many_to_one")
    df = df.merge(modelos, on="id_modelo", how="left", validate="many_to_one")
    df = df.merge(clientes, on="id_cliente", how="left", validate="many_to_one")

    # Importe de la línea = cantidad × precio
    df["importe_linea"] = (df["cantidad"] * df["precio_unitario"]).round(2)
    # True si el pedido está CONFIRMADO o ENTREGADO (es una venta válida)
    df["es_venta"] = df["estado"].isin(config.ESTADOS_VENTA)
    # Mes del pedido (por ejemplo 2026-07)
    df["mes"] = df["fecha_pedido"].dt.to_period("M")
    return poner_metadatos(df, "lineas_enriquecidas", len(lineas), fecha_corte(tablas))


# DF 01 · VISTA BASE 2: una fila por PEDIDO.
# Un pedido con 3 líneas cuenta como 1 pedido, no como 3.
def pedidos_unicos(tablas, df_lineas):
    # groupby + agg: por cada pedido, suma los pares y el importe y cuenta líneas y modelos distintos
    por_pedido = df_lineas.groupby("id_pedido").agg(
        pares=("cantidad", "sum"),
        importe=("importe_linea", "sum"),
        num_lineas=("id_linea", "count"),
        num_modelos=("id_modelo", "nunique"),
    ).reset_index()

    # Se une con la tabla de pedidos (uno a uno). Los pedidos sin líneas quedan vacíos y se ponen a 0
    df = tablas["pedidos"].merge(por_pedido, on="id_pedido", how="left", validate="one_to_one")
    for columna in ["pares", "importe", "num_lineas", "num_modelos"]:
        df[columna] = df[columna].fillna(0)

    df["es_venta"] = df["estado"].isin(config.ESTADOS_VENTA)

    # Variables de calendario
    df["mes"] = df["fecha_pedido"].dt.to_period("M")
    df["anio"] = df["fecha_pedido"].dt.year
    df["trimestre"] = df["fecha_pedido"].dt.quarter
    df["dia_semana"] = df["fecha_pedido"].dt.day_of_week.map(NOMBRE_DIA)
    df["antiguedad_dias"] = (fecha_corte(tablas) - df["fecha_pedido"]).dt.days

    # Precio medio por par. Se cambia 0 por vacío (NaN) para no dividir entre 0
    df["precio_medio_par"] = (df["importe"] / df["pares"].replace(0, np.nan)).round(2)
    return poner_metadatos(df, "pedidos_unicos", len(tablas["pedidos"]), fecha_corte(tablas))


# DF 02: ventas de cada mes (ingresos, pares, pedidos y ticket medio) y su variación
def ventas_por_periodo(df_pedidos):
    ventas = df_pedidos[df_pedidos["es_venta"]]
    df = ventas.groupby("mes").agg(
        ingresos=("importe", "sum"),
        pares=("pares", "sum"),
        pedidos=("id_pedido", "nunique"),
    )

    # Añade con 0 los meses sin ventas, para que no haya huecos en la serie
    if not df.empty:
        todos_los_meses = pd.period_range(df.index.min(), df.index.max(), freq="M")
        df = df.reindex(todos_los_meses, fill_value=0)
    df.index.name = "mes"

    # Ticket medio = ingresos ÷ pedidos (0 pedidos → vacío, para no dividir entre 0)
    df["ticket_medio"] = df["ingresos"] / df["pedidos"].replace(0, np.nan)

    # pct_change: variación en % respecto al mes anterior.
    # Si el mes anterior fue 0, sale infinito: se cambia por vacío
    for columna in ["ingresos", "pares", "pedidos", "ticket_medio"]:
        variacion = df[columna].pct_change() * 100
        df[f"variacion_{columna}_pct"] = variacion.replace([np.inf, -np.inf], np.nan)

    # Media de los 3 meses ANTERIORES: shift(1) mueve los datos un mes (quita el mes actual)
    # y rolling(3).mean() hace la media de 3 en 3
    df["media_3_meses_previos"] = df["ingresos"].shift(1).rolling(3).mean()

    # Variación interanual (mismo mes del año anterior) solo si hay más de 12 meses
    if len(df) > 12:
        df["variacion_interanual_pct"] = df["ingresos"].pct_change(12) * 100
    else:
        df["variacion_interanual_pct"] = np.nan

    df = df.reset_index()
    df["mes"] = df["mes"].astype(str)
    return poner_metadatos(df.round(2), "ventas_por_periodo", len(ventas), df_pedidos["fecha_pedido"].max())


# Clase ABC según el % acumulado de los modelos que van por delante
def clase_abc(acumulado_antes):
    if acumulado_antes <= 80:
        return "A"
    if acumulado_antes <= 95:
        return "B"
    return "C"


# DF 03: ranking de modelos por ingresos y clase ABC (Pareto)
def modelos_abc(df_lineas):
    ventas = df_lineas[df_lineas["es_venta"]]
    df = ventas.groupby(["codigo_modelo", "marca", "modelo"]).agg(
        ingresos=("importe_linea", "sum"),
        pares=("cantidad", "sum"),
    ).reset_index()
    df = df.sort_values("ingresos", ascending=False)

    # Peso de cada modelo sobre el total de ingresos
    total = df["ingresos"].sum()
    if total:
        df["peso_pct"] = df["ingresos"] / total * 100
    else:
        df["peso_pct"] = 0
    # cumsum: % acumulado (el 1º, el 1º + el 2º, ...)
    df["acumulado_pct"] = df["peso_pct"].cumsum()

    # Clase A mientras los anteriores no lleguen al 80 %, B hasta el 95 %, C el resto
    acumulado_antes = df["acumulado_pct"].shift(1, fill_value=0)
    df["clase"] = acumulado_antes.apply(clase_abc)

    # Puesto en el ranking por pares (1 = el que más pares vende)
    df["ranking_pares"] = df["pares"].rank(ascending=False, method="min").astype(int)
    df = df.round(2).reset_index(drop=True)
    return poner_metadatos(df, "modelos_abc", len(ventas), df_lineas["fecha_pedido"].max())


# DF 04: tabla modelo × talla con los pares vendidos, y el % de cada talla dentro de su modelo
def matriz_modelo_talla(df_lineas):
    ventas = df_lineas[df_lineas["es_venta"]]

    # pivot_table: filas = modelo, columnas = talla, valores = suma de pares (0 si no hay)
    unidades = ventas.pivot_table(index=["codigo_modelo", "modelo"], columns="talla", values="cantidad",
                                  aggfunc="sum", fill_value=0)
    unidades.columns = [int(talla) for talla in unidades.columns]

    # Porcentaje: cada fila se divide entre el total de su fila (axis=0) y se multiplica por 100
    total_por_modelo = unidades.sum(axis=1)
    proporcion = unidades.div(total_por_modelo, axis=0).mul(100).round(1)

    ultima_fecha = df_lineas["fecha_pedido"].max()
    unidades = poner_metadatos(unidades, "matriz_modelo_talla (pares)", len(ventas), ultima_fecha)
    proporcion = poner_metadatos(proporcion, "matriz_modelo_talla (% de cada talla dentro del modelo)", len(ventas), ultima_fecha)
    return unidades, proporcion


# DF 05: compara los pedidos CUSTOM y ESTANDAR
def custom_vs_estandar(df_pedidos):
    filas = []
    total_ingresos = df_pedidos.loc[df_pedidos["es_venta"], "importe"].sum()
    # Se recorre cada tipo de pedido con su grupo de filas
    for tipo, grupo in df_pedidos.groupby("tipo"):
        ventas = grupo[grupo["es_venta"]]
        cancelados = (grupo["estado"] == "CANCELADO").sum()
        if len(ventas):
            ticket = ventas["importe"].mean()
        else:
            ticket = np.nan
        if total_ingresos:
            cuota = ventas["importe"].sum() / total_ingresos * 100
        else:
            cuota = 0
        filas.append({
            "tipo": tipo,
            "pedidos_totales": len(grupo),
            "pedidos_venta": len(ventas),
            "pedidos_cancelados": int(cancelados),
            # La tasa de cancelación se calcula sobre pedidos; la cuota, sobre euros
            "tasa_cancelacion_pct": cancelados / len(grupo) * 100,
            "pares_vendidos": ventas["pares"].sum(),
            "ingresos": ventas["importe"].sum(),
            "ticket_medio": ticket,
            "cuota_ingresos_pct": cuota,
        })
    df = pd.DataFrame(filas)
    return poner_metadatos(df.round(2), "custom_vs_estandar", len(df_pedidos), df_pedidos["fecha_pedido"].max())


# Reglas para poner a cada cliente en un segmento RFM (los umbrales están en config.py)
def segmento_rfm(fila):
    if fila["frecuencia"] == 0:
        return "Sin compras válidas"
    if fila["recencia_dias"] > config.RFM_DIAS_RIESGO:
        return "En riesgo"
    if fila["frecuencia"] >= config.RFM_FRECUENCIA_LEAL and fila["recencia_dias"] <= config.RFM_DIAS_RECIENTE:
        return "Campeón"
    if fila["frecuencia"] >= config.RFM_FRECUENCIA_LEAL:
        return "Leal"
    if fila["recencia_dias"] <= config.RFM_DIAS_RECIENTE:
        return "Nuevo / reciente"
    return "Ocasional"


# DF 06: RFM de cada cliente.
# Recency = días desde su última compra hasta la fecha de corte, Frequency = nº de pedidos válidos
# distintos (nunca líneas), Monetary = euros gastados en ventas válidas.
def clientes_rfm(tablas, df_pedidos):
    corte = fecha_corte(tablas)
    ventas = df_pedidos[df_pedidos["es_venta"]]
    rfm = ventas.groupby("id_cliente").agg(
        ultima_compra=("fecha_pedido", "max"),
        frecuencia=("id_pedido", "nunique"),
        monetario=("importe", "sum"),
    ).reset_index()

    # how="left": se quedan TODOS los clientes, también los que no han comprado nada
    clientes = tablas["clientes"][["id_cliente", "codigo_odoo", "nombre", "tipo_cliente"]]
    df = clientes.merge(rfm, on="id_cliente", how="left", validate="one_to_one")
    df["recencia_dias"] = (corte - df["ultima_compra"]).dt.days
    df["frecuencia"] = df["frecuencia"].fillna(0).astype(int)
    df["monetario"] = df["monetario"].fillna(0).round(2)

    # apply con axis=1: aplica la función segmento_rfm a cada fila
    df["segmento"] = df.apply(segmento_rfm, axis=1)
    df = df.sort_values("monetario", ascending=False).reset_index(drop=True)
    return poner_metadatos(df, "clientes_rfm", len(ventas), corte)


# Variables de comportamiento de cada cliente: nº de compras, % Custom y días medios entre compras
def caracteristicas_clientes(tablas, df_pedidos):
    ventas = df_pedidos[df_pedidos["es_venta"]].sort_values("fecha_pedido").copy()
    ventas["es_custom"] = ventas["tipo"] == "CUSTOM"
    # diff(): días entre cada compra y la anterior del mismo cliente
    ventas["dias_desde_anterior"] = ventas.groupby("id_cliente")["fecha_pedido"].diff().dt.days

    # La media de True/False es la proporción de True (por eso "mean" da el % de Custom)
    por_cliente = ventas.groupby("id_cliente").agg(
        frecuencia_cliente=("id_pedido", "nunique"),
        porcentaje_custom=("es_custom", "mean"),
        intervalo_medio_dias=("dias_desde_anterior", "mean"),
    ).reset_index()
    por_cliente["porcentaje_custom"] = (por_cliente["porcentaje_custom"] * 100).round(1)
    por_cliente["intervalo_medio_dias"] = por_cliente["intervalo_medio_dias"].round(1)

    clientes = tablas["clientes"][["id_cliente", "codigo_odoo", "tipo_cliente"]]
    df = clientes.merge(por_cliente, on="id_cliente", how="left", validate="one_to_one")
    df["frecuencia_cliente"] = df["frecuencia_cliente"].fillna(0).astype(int)
    return poner_metadatos(df, "caracteristicas_clientes", len(ventas), fecha_corte(tablas))


# Variables de demanda: pares de cada modelo en cada mes, los del mes anterior
# y la media de los 3 meses previos (solo usa meses pasados)
def demanda_modelo_mes(df_lineas):
    columnas = ["codigo_modelo", "mes", "unidades_modelo_mes", "demanda_mes_anterior", "media_3_meses_previos", "mes_del_anio"]
    ventas = df_lineas[df_lineas["es_venta"]]
    if ventas.empty:
        return poner_metadatos(pd.DataFrame(columns=columnas), "demanda_modelo_mes", 0, df_lineas["fecha_pedido"].max())

    # Pares vendidos de cada modelo en cada mes
    pares = ventas.groupby(["codigo_modelo", "mes"])["cantidad"].sum().reset_index()

    # Tabla con TODAS las combinaciones modelo-mes (también los meses en los que el modelo no se vendió)
    modelos = sorted(pares["codigo_modelo"].unique())
    meses = pd.period_range(ventas["mes"].min(), ventas["mes"].max(), freq="M")
    filas = []
    for modelo in modelos:
        for mes in meses:
            filas.append({"codigo_modelo": modelo, "mes": mes})
    df = pd.DataFrame(filas)

    # Se pegan los pares de cada combinación; las que no tienen ventas quedan con 0
    df = df.merge(pares, on=["codigo_modelo", "mes"], how="left")
    df["unidades_modelo_mes"] = df["cantidad"].fillna(0).astype(int)

    # Para cada modelo por separado: el dato del mes anterior y la media de los 3 meses anteriores
    trozos = []
    for modelo in modelos:
        trozo = df[df["codigo_modelo"] == modelo].copy()
        trozo["demanda_mes_anterior"] = trozo["unidades_modelo_mes"].shift(1)
        trozo["media_3_meses_previos"] = trozo["demanda_mes_anterior"].rolling(3).mean().round(2)
        trozos.append(trozo)
    df = pd.concat(trozos)

    df["mes_del_anio"] = df["mes"].dt.month
    df["mes"] = df["mes"].astype(str)
    return poner_metadatos(df[columnas], "demanda_modelo_mes", len(ventas), df_lineas["fecha_pedido"].max())


# Talla con más pares vendidos de cada modelo (si empatan, la más pequeña)
def talla_mas_solicitada(df_lineas):
    ventas = df_lineas[df_lineas["es_venta"]]
    pares = ventas.groupby(["codigo_modelo", "modelo", "talla"])["cantidad"].sum().reset_index()

    # Total de pares del modelo, repetido en cada fila de ese modelo (transform)
    pares["pares_modelo"] = pares.groupby("codigo_modelo")["cantidad"].transform("sum")

    # Se ordena de más a menos pares dentro de cada modelo y se queda la primera fila de cada modelo
    pares = pares.sort_values(["codigo_modelo", "cantidad", "talla"], ascending=[True, False, True])
    df = pares.drop_duplicates("codigo_modelo")
    df = df.rename(columns={"talla": "talla_mas_solicitada", "cantidad": "pares_talla"})
    df["peso_talla_pct"] = (df["pares_talla"] / df["pares_modelo"] * 100).round(1)
    return poner_metadatos(df.reset_index(drop=True), "talla_mas_solicitada", len(ventas), df_lineas["fecha_pedido"].max())


# DF 07: cohortes. Cada cliente pertenece al mes de su primera compra (su cohorte)
# y se mira qué % de clientes vuelve a comprar 0, 1, 2... meses después
def cohortes(df_pedidos):
    ventas = df_pedidos[df_pedidos["es_venta"]].copy()

    # transform("min"): el primer mes de compra del cliente, repetido en cada pedido suyo
    ventas["cohorte"] = ventas.groupby("id_cliente")["mes"].transform("min")

    # Meses que han pasado desde la primera compra (contando los meses como año × 12 + mes)
    numero_mes = ventas["fecha_pedido"].dt.year * 12 + ventas["fecha_pedido"].dt.month
    primer_numero_mes = numero_mes.groupby(ventas["id_cliente"]).transform("min")
    ventas["edad_meses"] = numero_mes - primer_numero_mes

    # Tabla: filas = cohorte, columnas = meses después, valores = nº de clientes distintos que compran
    activos = ventas.pivot_table(index="cohorte", columns="edad_meses", values="id_cliente", aggfunc="nunique", fill_value=0)

    # Tamaño de cada cohorte = clientes que compraron en el mes 0
    if 0 in activos.columns:
        tamano = activos[0]
    else:
        tamano = pd.Series(dtype=float)

    # Retención = clientes activos ÷ tamaño de la cohorte × 100
    retencion = activos.div(tamano, axis=0).mul(100).round(1)
    retencion.index = retencion.index.astype(str)
    retencion.columns = [f"mes_{columna}" for columna in retencion.columns]
    retencion.insert(0, "clientes_cohorte", tamano.values)

    clientes = ventas["id_cliente"].nunique()
    retencion = poner_metadatos(retencion, "cohortes (% de clientes que vuelven a comprar)", len(ventas), df_pedidos["fecha_pedido"].max())
    if clientes < config.MINIMO_CLIENTES_COHORTES:
        retencion.attrs["aviso"] = f"Muestra insuficiente: solo {clientes} clientes con compras válidas. La retención es orientativa."
    return retencion


# Texto de la cobertura: "N/D" si no se puede calcular
def texto_cobertura(semanas):
    if pd.isna(semanas):
        return "N/D"
    return f"{semanas} semanas"


# DF 08: stock de la foto + demanda de los últimos 28 días.
# Cobertura (semanas) = stock ÷ (pares de 28 días ÷ 4). Sin demanda → N/D
def stock_cobertura(tablas, df_lineas, umbral=None):
    corte = fecha_corte(tablas)
    desde = corte - pd.Timedelta(days=config.DIAS_DEMANDA_RECIENTE)

    # Ventas de los últimos 28 días antes del corte
    recientes = df_lineas[df_lineas["es_venta"] & (df_lineas["fecha_pedido"] > desde) & (df_lineas["fecha_pedido"] <= corte)]
    demanda = recientes.groupby(["id_modelo", "color", "talla"])["cantidad"].sum().rename("demanda_28_dias").reset_index()

    # Se une el stock con su modelo y con su demanda
    modelos = tablas["modelos"][["id_modelo", "codigo_modelo", "marca", "nombre"]].rename(columns={"nombre": "modelo"})
    df = tablas["stock"].merge(modelos, on="id_modelo", how="left", validate="many_to_one")
    df = df.merge(demanda, on=["id_modelo", "color", "talla"], how="left", validate="one_to_one")
    df["demanda_28_dias"] = df["demanda_28_dias"].fillna(0).astype(int)

    # Demanda por semana = demanda de 28 días ÷ 4. Si es 0 se cambia por vacío para no dividir entre 0
    semanal = df["demanda_28_dias"] / 4
    df["cobertura_semanas"] = (df["stock_disponible"] / semanal.replace(0, np.nan)).round(1)
    df["cobertura_texto"] = df["cobertura_semanas"].apply(texto_cobertura)

    # Alerta si el stock es menor o igual que el umbral (si no se indica, el stock mínimo de cada talla)
    if umbral is None:
        df["umbral_alerta"] = df["stock_minimo"]
    else:
        df["umbral_alerta"] = umbral
    df["alerta_stock_bajo"] = df["stock_disponible"] <= df["umbral_alerta"]

    columnas = ["codigo_modelo", "marca", "modelo", "color", "talla", "stock_disponible", "stock_minimo", "umbral_alerta",
                "demanda_28_dias", "cobertura_semanas", "cobertura_texto", "alerta_stock_bajo", "fecha_corte"]
    # Primero las alertas, y de menos a más stock
    df = df[columnas].sort_values(["alerta_stock_bajo", "stock_disponible"], ascending=[False, True]).reset_index(drop=True)
    df = poner_metadatos(df, "stock_cobertura", len(tablas["stock"]), corte)
    df.attrs["aviso"] = "El stock es una foto en la fecha de corte, no un histórico de existencias."
    return df


# DF 09: resumen de calidad por tabla y nº de incidencias de cada regla
def calidad_incidencias(resultado_pipeline):
    resumen = resultado_pipeline["resumen_calidad"].copy()
    incidencias = resultado_pipeline["incidencias"]

    # Tasa de integridad = filas válidas ÷ filas de entrada
    total = resumen["filas_entrada"].sum()
    validas = resumen["filas_validas"].sum()
    if total:
        resumen.attrs["tasa_integridad_pct"] = round(validas / total * 100, 1)
    else:
        resumen.attrs["tasa_integridad_pct"] = 0.0

    # Cuántas veces se ha incumplido cada regla
    if incidencias.empty:
        por_regla = pd.DataFrame(columns=["regla", "gravedad", "veces"])
    else:
        por_regla = incidencias.groupby(["regla", "gravedad"]).size().rename("veces").reset_index()

    hora = pd.Timestamp(resultado_pipeline["hora_comprobacion"])
    return poner_metadatos(resumen, "calidad_incidencias", int(total), hora), por_regla


# Estadísticos de una columna: media, mediana, moda, desviación típica, percentiles e IQR
def describir(serie, discreta):
    serie = serie.dropna()
    if serie.empty:
        return {"n": 0}

    media = serie.mean()
    mediana = serie.median()

    # La moda solo tiene sentido en números enteros (pares) y si algún valor se repite
    moda = np.nan
    if discreta and serie.value_counts().iloc[0] > 1:
        moda = serie.mode().min()

    # Si media y mediana se separan más de un 10 %, los datos son asimétricos y es mejor la mediana
    representativo = "media (simétrica)"
    if mediana != 0 and abs(media - mediana) / abs(mediana) > config.UMBRAL_ASIMETRIA:
        representativo = "mediana (asimétrica)"

    aviso = ""
    if len(serie) < config.MINIMO_MUESTRA_ESTADISTICA:
        aviso = f"muestra pequeña (n < {config.MINIMO_MUESTRA_ESTADISTICA})"

    q1 = serie.quantile(0.25)
    q3 = serie.quantile(0.75)
    return {
        "n": len(serie),
        "media": media,
        "mediana": mediana,
        "moda": moda,
        "desviacion": serie.std(),
        "minimo": serie.min(),
        "p25": q1,
        "p75": q3,
        "p90": serie.quantile(0.90),
        "maximo": serie.max(),
        "iqr": q3 - q1,
        "representativo": representativo,
        "aviso": aviso,
    }


# Estadística de importe, pares y precio (solo ventas válidas)
def estadistica_descriptiva(df_pedidos, df_lineas):
    pedidos = df_pedidos[df_pedidos["es_venta"]]
    lineas = df_lineas[df_lineas["es_venta"]]
    # (nombre, unidad, nivel, columna, ¿es un número entero?)
    variables = [
        ("importe por pedido", "€", "pedido", pedidos["importe"], False),
        ("pares por pedido", "pares", "pedido", pedidos["pares"], True),
        ("precio por par", "€/par", "línea", lineas["precio_unitario"], False),
        ("pares por línea", "pares", "línea", lineas["cantidad"], True),
    ]
    filas = []
    for nombre, unidad, nivel, serie, discreta in variables:
        fila = {"variable": nombre, "unidad": unidad, "nivel": nivel}
        fila.update(describir(serie, discreta))
        filas.append(fila)
    df = pd.DataFrame(filas).round(2)
    return poner_metadatos(df, "estadistica_descriptiva", len(pedidos), df_pedidos["fecha_pedido"].max())


# La misma estadística, pero separada por grupos (tipo de pedido o categoría)
def estadistica_por_grupo(df_pedidos, df_lineas):
    pedidos = df_pedidos[df_pedidos["es_venta"]]
    lineas = df_lineas[df_lineas["es_venta"]]
    # (nombre, unidad, tabla, columna para agrupar, columna a medir)
    comparaciones = [
        ("importe por pedido", "€", pedidos, "tipo", "importe"),
        ("pares por pedido", "pares", pedidos, "tipo", "pares"),
        ("precio por par", "€/par", lineas, "categoria", "precio_unitario"),
    ]
    medidas = ["n", "media", "mediana", "desviacion", "p25", "p75", "iqr", "aviso"]
    filas = []
    for nombre, unidad, datos, grupo, columna in comparaciones:
        for valor, trozo in datos.groupby(grupo):
            resumen = describir(trozo[columna], False)
            fila = {"variable": nombre, "unidad": unidad, "agrupado_por": grupo, "grupo": valor}
            for medida in medidas:
                fila[medida] = resumen.get(medida)
            filas.append(fila)
    df = pd.DataFrame(filas, columns=["variable", "unidad", "agrupado_por", "grupo"] + medidas).round(2)
    return poner_metadatos(df, "estadistica_por_grupo", len(pedidos), df_pedidos["fecha_pedido"].max())


# DF 10: valores atípicos con la regla IQR: fuera de [Q1 − 1,5·IQR, Q3 + 1,5·IQR].
# Se marcan para revisarlos; no se borran
def anomalias(df_lineas):
    filas = []
    for columna in ["precio_unitario", "cantidad"]:
        for categoria, grupo in df_lineas.groupby("categoria"):
            # Si la categoría tiene pocas líneas, se compara con todas las líneas
            if len(grupo) >= config.MINIMO_MUESTRA_IQR:
                muestra = grupo
                comparado_con = categoria
            else:
                muestra = df_lineas
                comparado_con = "todas las líneas (muestra pequeña)"

            q1 = muestra[columna].quantile(0.25)
            q3 = muestra[columna].quantile(0.75)
            iqr = q3 - q1
            minimo = q1 - config.FACTOR_IQR * iqr
            maximo = q3 + config.FACTOR_IQR * iqr

            fuera = grupo[(grupo[columna] < minimo) | (grupo[columna] > maximo)]
            for _, fila in fuera.iterrows():
                filas.append({
                    "ref_odoo": fila["ref_odoo"],
                    "id_linea": fila["id_linea"],
                    "categoria": categoria,
                    "modelo": fila["modelo"],
                    "variable": columna,
                    "valor": fila[columna],
                    "limite_inferior": round(minimo, 2),
                    "limite_superior": round(maximo, 2),
                    "grupo_comparado": comparado_con,
                    "tratamiento": "se conserva y se marca para revisar",
                })
    df = pd.DataFrame(filas, columns=["ref_odoo", "id_linea", "categoria", "modelo", "variable", "valor",
                                      "limite_inferior", "limite_superior", "grupo_comparado", "tratamiento"])
    return poner_metadatos(df, "anomalias (regla IQR)", len(df_lineas), df_lineas["fecha_pedido"].max())


# DF 11: Acceso a Datos no exporta el coste, así que el margen es NO CALCULABLE (no se inventa)
def precio_y_margen(df_lineas):
    ventas = df_lineas[df_lineas["es_venta"]]
    if "coste_unitario" in df_lineas.columns:
        return None
    if len(ventas):
        precio_medio = round(ventas["importe_linea"].sum() / ventas["cantidad"].sum(), 2)
    else:
        precio_medio = np.nan
    df = pd.DataFrame([{
        "estado": "NO CALCULABLE",
        "motivo": "ACC no exporta un coste unitario fiable (modelo de datos común, apartado 3). No se inventan costes.",
        "precio_medio_ponderado_par": precio_medio,
    }])
    return poner_metadatos(df, "precio_y_margen", len(ventas), df_lineas["fecha_pedido"].max())


# Dice si una cifra de pandas coincide con la de SQL
def estado_reconciliacion(fila):
    if pd.isna(fila["valor_sql"]):
        return "SIN DATO SQL"
    if pd.isna(fila["valor_pandas"]):
        return "DESCUADRE (solo en SQL)"
    if abs(fila["diferencia"]) <= config.TOLERANCIA_IMPORTE:
        return "CUADRA"
    return "DESCUADRE"


# DF 12: compara las cifras de pandas con las que calcula SQL (reconciliacion_sql.csv) y dice si cuadran
def reconciliacion_sql(df_pedidos, df_lineas, carpeta=config.CARPETA_ENTRADA):
    ruta = carpeta / "reconciliacion_sql.csv"
    ventas = df_pedidos[df_pedidos["es_venta"]]
    lineas_venta = df_lineas[df_lineas["es_venta"]]

    # Cifras calculadas con pandas (mismos nombres que las del CSV de SQL)
    valores = {
        "pedidos_validos": len(ventas),
        "pares_vendidos": float(ventas["pares"].sum()),
        "ingresos_validos": round(float(ventas["importe"].sum()), 2),
        "clientes_con_compra": int(ventas["id_cliente"].nunique()),
        "lineas_totales": len(df_lineas),
    }
    # Ingresos de cada mes
    for mes, valor in lineas_venta.groupby("mes")["importe_linea"].sum().items():
        valores[f"ingresos_mes_{mes}"] = round(float(valor), 2)
    # Pares de cada modelo y talla
    for (modelo, talla), valor in lineas_venta.groupby(["codigo_modelo", "talla"])["cantidad"].sum().items():
        valores[f"pares_{modelo}_talla_{int(talla)}"] = float(valor)

    df = pd.DataFrame({"metrica": list(valores.keys()), "valor_pandas": list(valores.values())})

    # Sin el CSV de SQL no hay con qué comparar
    if not ruta.exists():
        df["valor_sql"] = np.nan
        df["diferencia"] = np.nan
        df["estado"] = "SIN DATO SQL"
        return poner_metadatos(df, "reconciliacion_sql", len(df_pedidos), df_pedidos["fecha_pedido"].max())

    sql = pd.read_csv(ruta, dtype={"metrica": str})
    sql["valor_sql"] = pd.to_numeric(sql["valor_sql"], errors="coerce")

    # how="outer": se quedan las métricas de los dos lados, para ver lo que falta en cada uno
    df = df.merge(sql, on="metrica", how="outer", validate="one_to_one")
    df["diferencia"] = (df["valor_pandas"] - df["valor_sql"]).round(2)
    df["estado"] = df.apply(estado_reconciliacion, axis=1)
    return poner_metadatos(df, "reconciliacion_sql", len(df_pedidos), df_pedidos["fecha_pedido"].max())


# El primero del ranking (por ejemplo el modelo con más pares) con su valor entre paréntesis
def top_ventas(lineas_venta, columna, valor):
    if lineas_venta.empty:
        return "—"
    serie = lineas_venta.groupby(columna)[valor].sum().sort_values(ascending=False)
    return f"{serie.index[0]} ({serie.iloc[0]:.0f})"


# Divide sin error: si el denominador es 0 devuelve vacío (NaN)
def dividir(a, b):
    if b:
        return a / b
    return np.nan


# Los 15 indicadores principales, con su fórmula y su denominador.
# El ticket medio divide entre pedidos válidos, nunca entre líneas.
def kpis(df_pedidos, df_lineas, df_ventas_mes, df_abc):
    ventas = df_pedidos[df_pedidos["es_venta"]]
    lineas_venta = df_lineas[df_lineas["es_venta"]]
    pedidos_venta = len(ventas)
    ingresos = ventas["importe"].sum()
    pares = ventas["pares"].sum()
    custom = ventas[ventas["tipo"] == "CUSTOM"]

    # Variación del último mes (hace falta al menos 2 meses)
    if len(df_ventas_mes) > 1:
        variacion = df_ventas_mes["variacion_ingresos_pct"].iloc[-1]
    else:
        variacion = np.nan
    if pd.notna(variacion):
        texto_variacion = round(variacion, 1)
    else:
        texto_variacion = "sin periodo anterior"

    # Pareto: cuánto suman los modelos del 20 % superior (como mínimo 1 modelo)
    n_top = max(1, int(np.ceil(len(df_abc) * 0.2)))
    if len(df_abc):
        pareto = round(df_abc["peso_pct"].head(n_top).sum(), 1)
    else:
        pareto = np.nan

    # Pedidos por estado, en texto: "BORRADOR 2, CONFIRMADO 3, ..."
    estados = df_pedidos["estado"].value_counts()
    partes = []
    for estado in config.ESTADOS_VALIDOS:
        partes.append(f"{estado} {estados.get(estado, 0)}")
    texto_estados = ", ".join(partes)

    ticket = round(dividir(ingresos, pedidos_venta), 2)
    pares_pedido = round(dividir(pares, pedidos_venta), 2)
    custom_pedidos = round(dividir(len(custom), pedidos_venta) * 100, 1)
    custom_pares = round(dividir(custom["pares"].sum(), pares) * 100, 1)
    custom_ingresos = round(dividir(custom["importe"].sum(), ingresos) * 100, 1)

    # (indicador, valor, unidad, fórmula, denominador)
    filas = [
        ("Pedidos únicos (actividad)", len(df_pedidos), "pedidos", "nº de id_pedido distintos, todos los estados", "—"),
        ("Pedidos por estado", texto_estados, "pedidos", "conteo por estado", "—"),
        ("Pedidos válidos (venta)", pedidos_venta, "pedidos", "estado CONFIRMADO o ENTREGADO", "—"),
        ("Pares vendidos", pares, "pares", "Σ cantidad de las líneas de pedidos válidos", "—"),
        ("Ingresos válidos", round(ingresos, 2), "€", "Σ cantidad × precio_unitario de pedidos válidos", "—"),
        ("Ticket medio", ticket, "€/pedido", "ingresos ÷ pedidos válidos", f"{pedidos_venta} pedidos"),
        ("Pares por pedido", pares_pedido, "pares/pedido", "pares ÷ pedidos válidos", f"{pedidos_venta} pedidos"),
        ("Peso Custom en pedidos", custom_pedidos, "%", "pedidos CUSTOM ÷ pedidos válidos", f"{pedidos_venta} pedidos"),
        ("Peso Custom en pares", custom_pares, "%", "pares CUSTOM ÷ pares vendidos", f"{pares:.0f} pares"),
        ("Peso Custom en ingresos", custom_ingresos, "%", "ingresos CUSTOM ÷ ingresos válidos", f"{ingresos:.2f} €"),
        ("Modelo más vendido", top_ventas(lineas_venta, "modelo", "cantidad"), "pares", "modelo con más pares en pedidos válidos", "—"),
        ("Talla más vendida", top_ventas(lineas_venta, "talla", "cantidad"), "pares", "talla con más pares en pedidos válidos", "—"),
        ("Mejor cliente", top_ventas(lineas_venta, "codigo_odoo", "importe_linea"), "€", "cliente con más ingresos válidos", "—"),
        ("Variación último mes", texto_variacion, "%", "(ingresos mes − mes anterior) ÷ mes anterior", "—"),
        ("Concentración Pareto", pareto, "%", f"peso del 20 % de modelos con más ingresos ({n_top} modelos)", f"{len(df_abc)} modelos vendidos"),
    ]
    df = pd.DataFrame(filas, columns=["indicador", "valor", "unidad", "formula", "denominador"])
    # Todos los valores se guardan como texto, porque hay números y frases mezclados
    df["valor"] = df["valor"].astype(str)
    return poner_metadatos(df, "kpis", len(df_pedidos), df_pedidos["fecha_pedido"].max())


# Aplica los filtros (fechas, tipo, cliente, estado, modelo y talla). Un filtro vacío no quita nada.
def aplicar_filtros(tablas, filtros):
    if not filtros:
        return tablas
    pedidos = tablas["pedidos"]
    lineas = tablas["lineas"]
    stock = tablas["stock"]

    # Filtros que se aplican a los pedidos
    if filtros.get("desde") is not None:
        pedidos = pedidos[pedidos["fecha_pedido"] >= pd.Timestamp(filtros["desde"])]
    if filtros.get("hasta") is not None:
        # "hasta" incluye todo ese día: menor que el día siguiente
        pedidos = pedidos[pedidos["fecha_pedido"] < pd.Timestamp(filtros["hasta"]) + pd.Timedelta(days=1)]
    if filtros.get("tipos"):
        pedidos = pedidos[pedidos["tipo"].isin(filtros["tipos"])]
    if filtros.get("clientes"):
        clientes = tablas["clientes"]
        ids_clientes = clientes.loc[clientes["codigo_odoo"].isin(filtros["clientes"]), "id_cliente"]
        pedidos = pedidos[pedidos["id_cliente"].isin(ids_clientes)]
    if filtros.get("estados"):
        pedidos = pedidos[pedidos["estado"].isin(filtros["estados"])]

    # Filtros que se aplican a las líneas (y al stock)
    if filtros.get("modelos"):
        modelos = tablas["modelos"]
        ids_modelos = modelos.loc[modelos["codigo_modelo"].isin(filtros["modelos"]), "id_modelo"]
        lineas = lineas[lineas["id_modelo"].isin(ids_modelos)]
        stock = stock[stock["id_modelo"].isin(ids_modelos)]
    if filtros.get("tallas"):
        lineas = lineas[lineas["talla"].isin(filtros["tallas"])]
        stock = stock[stock["talla"].isin(filtros["tallas"])]

    # Solo las líneas de los pedidos que han pasado el filtro...
    lineas = lineas[lineas["id_pedido"].isin(pedidos["id_pedido"])]
    # ...y si se filtra por modelo o talla, solo los pedidos que tienen alguna de esas líneas
    if filtros.get("modelos") or filtros.get("tallas"):
        pedidos = pedidos[pedidos["id_pedido"].isin(lineas["id_pedido"])]

    filtradas = dict(tablas)
    filtradas["pedidos"] = pedidos
    filtradas["lineas"] = lineas
    filtradas["stock"] = stock
    # El stock completo se guarda para saber la fecha de corte aunque el filtro lo deje vacío
    filtradas["stock_completo"] = tablas["stock"]
    return filtradas


# Función principal: a partir de los datos limpios calcula TODOS los DataFrames.
# La usan main.py y el dashboard, así que las fórmulas son las mismas en los dos.
def calcular_todo(resultado_pipeline, filtros=None):
    if filtros is None:
        filtros = {}
    tablas = aplicar_filtros(resultado_pipeline["tablas"], filtros)

    # Las dos vistas base, de las que salen casi todas las demás
    df_lineas = lineas_enriquecidas(tablas)
    df_pedidos = pedidos_unicos(tablas, df_lineas)

    df_ventas_mes = ventas_por_periodo(df_pedidos)
    df_abc = modelos_abc(df_lineas)
    unidades, proporcion = matriz_modelo_talla(df_lineas)
    calidad, calidad_reglas = calidad_incidencias(resultado_pipeline)
    df_rfm = clientes_rfm(tablas, df_pedidos)
    clusters = segmentacion.clustering_clientes(df_rfm)

    # La conciliación con SQL siempre se hace SIN filtros (SQL calcula sobre todos los datos)
    if filtros:
        base_lineas = lineas_enriquecidas(resultado_pipeline["tablas"])
        base_pedidos = pedidos_unicos(resultado_pipeline["tablas"], base_lineas)
    else:
        base_lineas = df_lineas
        base_pedidos = df_pedidos

    resultados = {
        "lineas_enriquecidas": df_lineas,
        "pedidos_unicos": df_pedidos,
        "ventas_por_periodo": df_ventas_mes,
        "modelos_abc": df_abc,
        "matriz_modelo_talla": unidades,
        "matriz_modelo_talla_pct": proporcion,
        "custom_vs_estandar": custom_vs_estandar(df_pedidos),
        "clientes_rfm": df_rfm,
        "clustering_evaluacion": clusters["clustering_evaluacion"],
        "clustering_clientes": clusters["clustering_clientes"],
        "clustering_perfil": clusters["clustering_perfil"],
        "clustering_vs_rfm": clusters["clustering_vs_rfm"],
        "caracteristicas_clientes": caracteristicas_clientes(tablas, df_pedidos),
        "demanda_modelo_mes": demanda_modelo_mes(df_lineas),
        "talla_mas_solicitada": talla_mas_solicitada(df_lineas),
        "cohortes": cohortes(df_pedidos),
        "stock_cobertura": stock_cobertura(tablas, df_lineas, filtros.get("umbral_stock")),
        "calidad": calidad,
        "calidad_por_regla": calidad_reglas,
        "estadistica_descriptiva": estadistica_descriptiva(df_pedidos, df_lineas),
        "estadistica_por_grupo": estadistica_por_grupo(df_pedidos, df_lineas),
        "anomalias": anomalias(df_lineas),
        "precio_y_margen": precio_y_margen(df_lineas),
        "reconciliacion_sql": reconciliacion_sql(base_pedidos, base_lineas, Path(resultado_pipeline["carpeta"])),
        "kpis": kpis(df_pedidos, df_lineas, df_ventas_mes, df_abc),
    }

    # Cada tabla apunta qué filtros se usaron (la conciliación con SQL nunca lleva filtros)
    for nombre, df in resultados.items():
        if nombre == "reconciliacion_sql":
            df.attrs["filtros"] = {}
        else:
            df.attrs["filtros"] = filtros
    return resultados
