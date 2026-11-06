import numpy as np
import pandas as pd

import config


def poner_metadatos(df, funcion, filas_origen, fecha_corte, filtros=None):
    df.attrs["funcion"] = funcion
    df.attrs["filas_origen"] = filas_origen
    df.attrs["fecha_corte"] = str(fecha_corte.date()) if pd.notna(fecha_corte) else "sin fecha"
    df.attrs["filtros"] = filtros or {}
    return df


def fecha_corte(tablas):
    return tablas["stock"]["fecha_corte"].max()


def lineas_enriquecidas(tablas):
    lineas = tablas["lineas"]
    pedidos = tablas["pedidos"]
    modelos = tablas["modelos"][["id_modelo", "codigo_modelo", "marca", "nombre", "categoria"]].rename(columns={"nombre": "modelo"})
    clientes = tablas["clientes"][["id_cliente", "codigo_odoo", "nombre", "tipo_cliente"]].rename(columns={"nombre": "cliente"})

    df = lineas.merge(pedidos, on="id_pedido", how="left", validate="many_to_one")
    df = df.merge(modelos, on="id_modelo", how="left", validate="many_to_one")
    df = df.merge(clientes, on="id_cliente", how="left", validate="many_to_one")

    df["importe_linea"] = (df["cantidad"] * df["precio_unitario"]).round(2)
    df["es_venta"] = df["estado"].isin(config.ESTADOS_VENTA)
    df["mes"] = df["fecha_pedido"].dt.to_period("M")
    return poner_metadatos(df, "lineas_enriquecidas", len(lineas), fecha_corte(tablas))


def pedidos_unicos(tablas, df_lineas):
    por_pedido = df_lineas.groupby("id_pedido").agg(
        pares=("cantidad", "sum"),
        importe=("importe_linea", "sum"),
        num_lineas=("id_linea", "count"),
        num_modelos=("id_modelo", "nunique"),
    ).reset_index()

    df = tablas["pedidos"].merge(por_pedido, on="id_pedido", how="left", validate="one_to_one")
    df[["pares", "importe", "num_lineas", "num_modelos"]] = df[["pares", "importe", "num_lineas", "num_modelos"]].fillna(0)
    df["es_venta"] = df["estado"].isin(config.ESTADOS_VENTA)
    df["mes"] = df["fecha_pedido"].dt.to_period("M")
    return poner_metadatos(df, "pedidos_unicos", len(tablas["pedidos"]), fecha_corte(tablas))


def ventas_por_periodo(df_pedidos):
    ventas = df_pedidos[df_pedidos["es_venta"]]
    df = ventas.groupby("mes").agg(
        ingresos=("importe", "sum"),
        pares=("pares", "sum"),
        pedidos=("id_pedido", "nunique"),
    )
    if not df.empty:
        meses = pd.period_range(df.index.min(), df.index.max(), freq="M")
        df = df.reindex(meses, fill_value=0)
    df.index.name = "mes"
    df["ticket_medio"] = np.where(df["pedidos"] > 0, df["ingresos"] / df["pedidos"].replace(0, np.nan), np.nan)
    df["variacion_ingresos_pct"] = df["ingresos"].pct_change().replace([np.inf, -np.inf], np.nan) * 100
    df["media_3_meses_previos"] = df["ingresos"].shift(1).rolling(3).mean()
    if len(df) > 12:
        df["variacion_interanual_pct"] = df["ingresos"].pct_change(12) * 100
    else:
        df["variacion_interanual_pct"] = np.nan
    df = df.reset_index()
    df["mes"] = df["mes"].astype(str)
    return poner_metadatos(df.round(2), "ventas_por_periodo", len(ventas), df_pedidos["fecha_pedido"].max())


def modelos_abc(df_lineas):
    ventas = df_lineas[df_lineas["es_venta"]]
    df = ventas.groupby(["codigo_modelo", "marca", "modelo"]).agg(
        ingresos=("importe_linea", "sum"),
        pares=("cantidad", "sum"),
    ).reset_index().sort_values("ingresos", ascending=False)
    total = df["ingresos"].sum()
    df["peso_pct"] = df["ingresos"] / total * 100 if total else 0
    df["acumulado_pct"] = df["peso_pct"].cumsum()
    df["clase"] = pd.cut(df["acumulado_pct"].shift(1, fill_value=0), bins=[-1, 80, 95, 101], labels=["A", "B", "C"])
    df["ranking_pares"] = df["pares"].rank(ascending=False, method="min").astype(int)
    return poner_metadatos(df.round(2).reset_index(drop=True), "modelos_abc", len(ventas), df_lineas["fecha_pedido"].max())


def matriz_modelo_talla(df_lineas):
    ventas = df_lineas[df_lineas["es_venta"]]
    unidades = ventas.pivot_table(index=["codigo_modelo", "modelo"], columns="talla", values="cantidad", aggfunc="sum", fill_value=0)
    unidades.columns = [int(c) for c in unidades.columns]
    proporcion = unidades.div(unidades.sum(axis=1), axis=0).mul(100).round(1)
    unidades = poner_metadatos(unidades, "matriz_modelo_talla (pares)", len(ventas), df_lineas["fecha_pedido"].max())
    proporcion = poner_metadatos(proporcion, "matriz_modelo_talla (% de cada talla dentro del modelo)", len(ventas), df_lineas["fecha_pedido"].max())
    return unidades, proporcion


def custom_vs_estandar(df_pedidos):
    filas = []
    total_ingresos = df_pedidos.loc[df_pedidos["es_venta"], "importe"].sum()
    for tipo, grupo in df_pedidos.groupby("tipo"):
        ventas = grupo[grupo["es_venta"]]
        cancelados = (grupo["estado"] == "CANCELADO").sum()
        filas.append({
            "tipo": tipo,
            "pedidos_totales": len(grupo),
            "pedidos_venta": len(ventas),
            "pedidos_cancelados": int(cancelados),
            "tasa_cancelacion_pct": cancelados / len(grupo) * 100,
            "pares_vendidos": ventas["pares"].sum(),
            "ingresos": ventas["importe"].sum(),
            "ticket_medio": ventas["importe"].mean() if len(ventas) else np.nan,
            "cuota_ingresos_pct": ventas["importe"].sum() / total_ingresos * 100 if total_ingresos else 0,
        })
    df = pd.DataFrame(filas)
    return poner_metadatos(df.round(2), "custom_vs_estandar", len(df_pedidos), df_pedidos["fecha_pedido"].max())


def clientes_rfm(tablas, df_pedidos):
    corte = fecha_corte(tablas)
    ventas = df_pedidos[df_pedidos["es_venta"]]
    rfm = ventas.groupby("id_cliente").agg(
        ultima_compra=("fecha_pedido", "max"),
        frecuencia=("id_pedido", "nunique"),
        monetario=("importe", "sum"),
    ).reset_index()

    clientes = tablas["clientes"][["id_cliente", "codigo_odoo", "nombre", "tipo_cliente"]]
    df = clientes.merge(rfm, on="id_cliente", how="left", validate="one_to_one")
    df["recencia_dias"] = (corte - df["ultima_compra"]).dt.days
    df["frecuencia"] = df["frecuencia"].fillna(0).astype(int)
    df["monetario"] = df["monetario"].fillna(0).round(2)

    def segmento(fila):
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

    df["segmento"] = df.apply(segmento, axis=1)
    df = df.sort_values("monetario", ascending=False).reset_index(drop=True)
    return poner_metadatos(df, "clientes_rfm", len(ventas), corte)


def cohortes(df_pedidos):
    ventas = df_pedidos[df_pedidos["es_venta"]].copy()
    ventas["cohorte"] = ventas.groupby("id_cliente")["mes"].transform("min")
    ventas["edad_meses"] = (ventas["mes"] - ventas["cohorte"]).apply(lambda d: d.n)
    activos = ventas.pivot_table(index="cohorte", columns="edad_meses", values="id_cliente", aggfunc="nunique", fill_value=0)
    tamano = activos[0] if 0 in activos.columns else pd.Series(dtype=float)
    retencion = activos.div(tamano, axis=0).mul(100).round(1)
    retencion.index = retencion.index.astype(str)
    retencion.columns = [f"mes_{c}" for c in retencion.columns]
    retencion.insert(0, "clientes_cohorte", tamano.values)
    clientes = ventas["id_cliente"].nunique()
    retencion = poner_metadatos(retencion, "cohortes (% de clientes que vuelven a comprar)", len(ventas), df_pedidos["fecha_pedido"].max())
    if clientes < config.MINIMO_CLIENTES_COHORTES:
        retencion.attrs["aviso"] = f"Muestra insuficiente: solo {clientes} clientes con compras válidas. La retención es orientativa."
    return retencion


def stock_cobertura(tablas, df_lineas):
    corte = fecha_corte(tablas)
    desde = corte - pd.Timedelta(days=config.DIAS_DEMANDA_RECIENTE)
    recientes = df_lineas[df_lineas["es_venta"] & (df_lineas["fecha_pedido"] > desde) & (df_lineas["fecha_pedido"] <= corte)]
    demanda = recientes.groupby(["id_modelo", "color", "talla"])["cantidad"].sum().rename("demanda_28_dias").reset_index()

    modelos = tablas["modelos"][["id_modelo", "codigo_modelo", "marca", "nombre"]].rename(columns={"nombre": "modelo"})
    df = tablas["stock"].merge(modelos, on="id_modelo", how="left", validate="many_to_one")
    df = df.merge(demanda, on=["id_modelo", "color", "talla"], how="left", validate="one_to_one")
    df["demanda_28_dias"] = df["demanda_28_dias"].fillna(0).astype(int)
    semanal = df["demanda_28_dias"] / 4
    df["cobertura_semanas"] = np.where(semanal > 0, (df["stock_disponible"] / semanal.replace(0, np.nan)).round(1), np.nan)
    df["cobertura_texto"] = df["cobertura_semanas"].map(lambda v: "N/D" if pd.isna(v) else f"{v} semanas")
    df["alerta_stock_bajo"] = df["stock_disponible"] <= df["stock_minimo"]
    columnas = ["codigo_modelo", "marca", "modelo", "color", "talla", "stock_disponible", "stock_minimo",
                "demanda_28_dias", "cobertura_semanas", "cobertura_texto", "alerta_stock_bajo", "fecha_corte"]
    df = df[columnas].sort_values(["alerta_stock_bajo", "stock_disponible"], ascending=[False, True]).reset_index(drop=True)
    df = poner_metadatos(df, "stock_cobertura", len(tablas["stock"]), corte)
    df.attrs["aviso"] = "El stock es una foto en la fecha de corte, no un histórico de existencias."
    return df


def calidad_incidencias(resultado_pipeline):
    resumen = resultado_pipeline["resumen_calidad"].copy()
    incidencias = resultado_pipeline["incidencias"]
    total = resumen["filas_entrada"].sum()
    validas = resumen["filas_validas"].sum()
    resumen.attrs["tasa_integridad_pct"] = round(validas / total * 100, 1) if total else 0.0
    por_regla = incidencias.groupby(["regla", "gravedad"]).size().rename("veces").reset_index() if not incidencias.empty else pd.DataFrame(columns=["regla", "gravedad", "veces"])
    return poner_metadatos(resumen, "calidad_incidencias", int(total), pd.Timestamp(resultado_pipeline["hora_comprobacion"])), por_regla


def anomalias(df_lineas):
    filas = []
    for columna in ["precio_unitario", "cantidad"]:
        for categoria, grupo in df_lineas.groupby("categoria"):
            muestra = grupo if len(grupo) >= config.MINIMO_MUESTRA_IQR else df_lineas
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
                    "grupo_comparado": categoria if muestra is grupo else "todas las líneas (muestra pequeña)",
                    "tratamiento": "se conserva y se marca para revisar",
                })
    df = pd.DataFrame(filas, columns=["ref_odoo", "id_linea", "categoria", "modelo", "variable", "valor",
                                      "limite_inferior", "limite_superior", "grupo_comparado", "tratamiento"])
    return poner_metadatos(df, "anomalias (regla IQR)", len(df_lineas), df_lineas["fecha_pedido"].max())


def precio_y_margen(df_lineas):
    ventas = df_lineas[df_lineas["es_venta"]]
    if "coste_unitario" not in df_lineas.columns:
        df = pd.DataFrame([{
            "estado": "NO CALCULABLE",
            "motivo": "ACC no exporta un coste unitario fiable (modelo de datos común, apartado 3). No se inventan costes.",
            "precio_medio_ponderado_par": round(ventas["importe_linea"].sum() / ventas["cantidad"].sum(), 2) if len(ventas) else np.nan,
        }])
        return poner_metadatos(df, "precio_y_margen", len(ventas), df_lineas["fecha_pedido"].max())
    return None


def reconciliacion_sql(df_pedidos, df_lineas, carpeta=config.CARPETA_ENTRADA):
    ruta = carpeta / "reconciliacion_sql.csv"
    ventas = df_pedidos[df_pedidos["es_venta"]]
    pandas_valores = {
        "pedidos_validos": len(ventas),
        "pares_vendidos": float(ventas["pares"].sum()),
        "ingresos_validos": round(float(ventas["importe"].sum()), 2),
        "clientes_con_compra": int(ventas["id_cliente"].nunique()),
        "lineas_totales": len(df_lineas),
    }
    if not ruta.exists():
        df = pd.DataFrame([{"metrica": k, "valor_pandas": v, "valor_sql": np.nan, "diferencia": np.nan, "estado": "SIN DATO SQL"} for k, v in pandas_valores.items()])
        return poner_metadatos(df, "reconciliacion_sql", len(df_pedidos), df_pedidos["fecha_pedido"].max())
    sql = pd.read_csv(ruta, dtype={"metrica": str})
    sql["valor_sql"] = pd.to_numeric(sql["valor_sql"], errors="coerce")
    df = pd.DataFrame({"metrica": list(pandas_valores), "valor_pandas": list(pandas_valores.values())})
    df = df.merge(sql, on="metrica", how="left", validate="one_to_one")
    df["diferencia"] = (df["valor_pandas"] - df["valor_sql"]).round(2)
    df["estado"] = np.where(df["valor_sql"].isna(), "SIN DATO SQL", np.where(df["diferencia"].abs() <= config.TOLERANCIA_IMPORTE, "CUADRA", "DESCUADRE"))
    return poner_metadatos(df, "reconciliacion_sql", len(df_pedidos), df_pedidos["fecha_pedido"].max())


def kpis(df_pedidos, df_lineas, df_ventas_mes, df_abc):
    ventas = df_pedidos[df_pedidos["es_venta"]]
    lineas_venta = df_lineas[df_lineas["es_venta"]]
    pedidos_venta = len(ventas)
    ingresos = ventas["importe"].sum()
    pares = ventas["pares"].sum()
    custom = ventas[ventas["tipo"] == "CUSTOM"]

    def top(columna, valor):
        if lineas_venta.empty:
            return "—"
        serie = lineas_venta.groupby(columna)[valor].sum().sort_values(ascending=False)
        return f"{serie.index[0]} ({serie.iloc[0]:.0f})"

    variacion = df_ventas_mes["variacion_ingresos_pct"].iloc[-1] if len(df_ventas_mes) > 1 else np.nan
    n_top = max(1, int(np.ceil(len(df_abc) * 0.2)))
    pareto = df_abc["peso_pct"].head(n_top).sum() if len(df_abc) else np.nan
    estados = df_pedidos["estado"].value_counts()

    filas = [
        ("Pedidos únicos (actividad)", len(df_pedidos), "pedidos", "nº de id_pedido distintos, todos los estados", "—"),
        ("Pedidos por estado", ", ".join(f"{e} {estados.get(e, 0)}" for e in config.ESTADOS_VALIDOS), "pedidos", "conteo por estado", "—"),
        ("Pedidos válidos (venta)", pedidos_venta, "pedidos", "estado CONFIRMADO o ENTREGADO", "—"),
        ("Pares vendidos", pares, "pares", "Σ cantidad de las líneas de pedidos válidos", "—"),
        ("Ingresos válidos", round(ingresos, 2), "€", "Σ cantidad × precio_unitario de pedidos válidos", "—"),
        ("Ticket medio", round(ingresos / pedidos_venta, 2) if pedidos_venta else np.nan, "€/pedido", "ingresos ÷ pedidos válidos", f"{pedidos_venta} pedidos"),
        ("Pares por pedido", round(pares / pedidos_venta, 2) if pedidos_venta else np.nan, "pares/pedido", "pares ÷ pedidos válidos", f"{pedidos_venta} pedidos"),
        ("Peso Custom en pedidos", round(len(custom) / pedidos_venta * 100, 1) if pedidos_venta else np.nan, "%", "pedidos CUSTOM ÷ pedidos válidos", f"{pedidos_venta} pedidos"),
        ("Peso Custom en pares", round(custom["pares"].sum() / pares * 100, 1) if pares else np.nan, "%", "pares CUSTOM ÷ pares vendidos", f"{pares:.0f} pares"),
        ("Peso Custom en ingresos", round(custom["importe"].sum() / ingresos * 100, 1) if ingresos else np.nan, "%", "ingresos CUSTOM ÷ ingresos válidos", f"{ingresos:.2f} €"),
        ("Modelo más vendido", top("modelo", "cantidad"), "pares", "modelo con más pares en pedidos válidos", "—"),
        ("Talla más vendida", top("talla", "cantidad"), "pares", "talla con más pares en pedidos válidos", "—"),
        ("Mejor cliente", top("cliente", "importe_linea"), "€", "cliente con más ingresos válidos", "—"),
        ("Variación último mes", round(variacion, 1) if pd.notna(variacion) else "sin periodo anterior", "%", "(ingresos mes − mes anterior) ÷ mes anterior", "—"),
        ("Concentración Pareto", round(pareto, 1) if pd.notna(pareto) else np.nan, "%", f"peso del 20 % de modelos con más ingresos ({n_top} modelos)", f"{len(df_abc)} modelos vendidos"),
    ]
    df = pd.DataFrame(filas, columns=["indicador", "valor", "unidad", "formula", "denominador"])
    df["valor"] = df["valor"].astype(str)
    return poner_metadatos(df, "kpis", len(df_pedidos), df_pedidos["fecha_pedido"].max())


def aplicar_filtros(tablas, filtros):
    if not filtros:
        return tablas
    pedidos = tablas["pedidos"]
    lineas = tablas["lineas"]
    if filtros.get("desde") is not None:
        pedidos = pedidos[pedidos["fecha_pedido"] >= pd.Timestamp(filtros["desde"])]
    if filtros.get("hasta") is not None:
        pedidos = pedidos[pedidos["fecha_pedido"] < pd.Timestamp(filtros["hasta"]) + pd.Timedelta(days=1)]
    if filtros.get("tipos"):
        pedidos = pedidos[pedidos["tipo"].isin(filtros["tipos"])]
    if filtros.get("estados"):
        pedidos = pedidos[pedidos["estado"].isin(filtros["estados"])]
    if filtros.get("modelos"):
        lineas = lineas[lineas["id_modelo"].isin(filtros["modelos"])]
    if filtros.get("tallas"):
        lineas = lineas[lineas["talla"].isin(filtros["tallas"])]
    lineas = lineas[lineas["id_pedido"].isin(pedidos["id_pedido"])]
    if filtros.get("modelos") or filtros.get("tallas"):
        pedidos = pedidos[pedidos["id_pedido"].isin(lineas["id_pedido"])]
    filtradas = dict(tablas)
    filtradas["pedidos"] = pedidos
    filtradas["lineas"] = lineas
    return filtradas


def calcular_todo(resultado_pipeline, filtros=None):
    tablas = aplicar_filtros(resultado_pipeline["tablas"], filtros)
    df_lineas = lineas_enriquecidas(tablas)
    df_pedidos = pedidos_unicos(tablas, df_lineas)
    df_ventas_mes = ventas_por_periodo(df_pedidos)
    df_abc = modelos_abc(df_lineas)
    unidades, proporcion = matriz_modelo_talla(df_lineas)
    calidad, calidad_reglas = calidad_incidencias(resultado_pipeline)
    base = resultado_pipeline["tablas"]
    base_lineas = lineas_enriquecidas(base) if filtros else df_lineas
    base_pedidos = pedidos_unicos(base, base_lineas) if filtros else df_pedidos
    resultados = {
        "lineas_enriquecidas": df_lineas,
        "pedidos_unicos": df_pedidos,
        "ventas_por_periodo": df_ventas_mes,
        "modelos_abc": df_abc,
        "matriz_modelo_talla": unidades,
        "matriz_modelo_talla_pct": proporcion,
        "custom_vs_estandar": custom_vs_estandar(df_pedidos),
        "clientes_rfm": clientes_rfm(tablas, df_pedidos),
        "cohortes": cohortes(df_pedidos),
        "stock_cobertura": stock_cobertura(tablas, df_lineas),
        "calidad": calidad,
        "calidad_por_regla": calidad_reglas,
        "anomalias": anomalias(df_lineas),
        "precio_y_margen": precio_y_margen(df_lineas),
        "reconciliacion_sql": reconciliacion_sql(base_pedidos, base_lineas),
        "kpis": kpis(df_pedidos, df_lineas, df_ventas_mes, df_abc),
    }
    for nombre, df in resultados.items():
        df.attrs["filtros"] = {} if nombre == "reconciliacion_sql" else (filtros or {})
    return resultados
