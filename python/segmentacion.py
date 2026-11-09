import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

import config

VARIABLES = ["recencia_dias", "frecuencia", "monetario"]


def con_metadatos(df, funcion, filas_origen):
    df.attrs["funcion"] = funcion
    df.attrs["filas_origen"] = filas_origen
    return df


def no_calculable(motivo, filas_origen):
    df = pd.DataFrame([{"estado": "NO CALCULABLE", "motivo": motivo}])
    tablas = {nombre: con_metadatos(df.copy(), nombre, filas_origen)
              for nombre in ["clustering_evaluacion", "clustering_clientes", "clustering_perfil", "clustering_vs_rfm"]}
    return {"estado": "NO CALCULABLE", "motivo": motivo, "mejor_k": None, **tablas}


def preparar_variables(clientes):
    datos = clientes[VARIABLES].copy()
    datos["frecuencia"] = np.log1p(datos["frecuencia"])
    datos["monetario"] = np.log1p(datos["monetario"])
    return StandardScaler().fit_transform(datos)


def evaluar_k(matriz):
    filas = []
    for k in config.VALORES_K:
        if k >= len(matriz):
            continue
        modelo = KMeans(n_clusters=k, n_init=10, random_state=config.SEMILLA).fit(matriz)
        filas.append({
            "k": k,
            "silhouette": round(silhouette_score(matriz, modelo.labels_), 3),
            "inercia": round(modelo.inertia_, 2),
            "tamano_grupo_menor": int(np.bincount(modelo.labels_).min()),
        })
    return pd.DataFrame(filas)


def nombrar(perfil, referencia):
    frecuencia = "frecuentes" if perfil["frecuencia_mediana"] >= referencia["frecuencia"] else "ocasionales"
    valor = "alto gasto" if perfil["monetario_mediana"] >= referencia["monetario"] else "bajo gasto"
    recencia = "activos" if perfil["recencia_mediana"] <= referencia["recencia_dias"] else "alejados"
    return f"{frecuencia.capitalize()}, {valor}, {recencia}"


def clustering_clientes(df_rfm):
    clientes = df_rfm[df_rfm["frecuencia"] > 0].reset_index(drop=True)
    if len(clientes) < config.MINIMO_CLIENTES_CLUSTERING:
        motivo = (f"Solo hay {len(clientes)} clientes con compras válidas; se necesitan al menos "
                  f"{config.MINIMO_CLIENTES_CLUSTERING} para agrupar de forma defendible. "
                  "El modelo se demuestra con los datos SINTÉTICOS.")
        return no_calculable(motivo, len(clientes))

    matriz = preparar_variables(clientes)
    evaluacion = evaluar_k(matriz)
    mejor_k = int(evaluacion.loc[evaluacion["silhouette"].idxmax(), "k"])
    etiquetas = KMeans(n_clusters=mejor_k, n_init=10, random_state=config.SEMILLA).fit_predict(matriz)
    asignacion = clientes[["id_cliente", "codigo_odoo", "tipo_cliente", "segmento", *VARIABLES]].assign(cluster=etiquetas)

    perfil = asignacion.groupby("cluster").agg(
        clientes=("id_cliente", "count"),
        recencia_mediana=("recencia_dias", "median"),
        frecuencia_mediana=("frecuencia", "median"),
        monetario_mediana=("monetario", "median"),
        monetario_total=("monetario", "sum"),
    ).reset_index()
    perfil["porcentaje_clientes"] = (perfil["clientes"] / perfil["clientes"].sum() * 100).round(1)
    perfil["porcentaje_ingresos"] = (perfil["monetario_total"] / perfil["monetario_total"].sum() * 100).round(1)
    referencia = clientes[VARIABLES].median()
    perfil["nombre_grupo"] = perfil.apply(nombrar, axis=1, referencia=referencia)
    repetidos = perfil["nombre_grupo"].duplicated(keep=False)
    perfil.loc[repetidos, "nombre_grupo"] = perfil.loc[repetidos, "nombre_grupo"] + " (grupo " + perfil.loc[repetidos, "cluster"].astype(str) + ")"
    perfil = perfil.round(2)

    asignacion = asignacion.merge(perfil[["cluster", "nombre_grupo"]], on="cluster", how="left", validate="many_to_one")
    comparacion = pd.crosstab(asignacion["nombre_grupo"], asignacion["segmento"], margins=True, margins_name="Total").reset_index()
    comparacion.columns.name = None

    filas = len(clientes)
    return {
        "estado": "CALCULADO",
        "motivo": f"KMeans sobre {filas} clientes; k = {mejor_k} por mayor silhouette",
        "mejor_k": mejor_k,
        "clustering_evaluacion": con_metadatos(evaluacion, "clustering_evaluacion", filas),
        "clustering_clientes": con_metadatos(asignacion, "clustering_clientes", filas),
        "clustering_perfil": con_metadatos(perfil, "clustering_perfil", filas),
        "clustering_vs_rfm": con_metadatos(comparacion, "clustering_vs_rfm", filas),
    }
