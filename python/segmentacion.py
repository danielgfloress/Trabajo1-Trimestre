# Segmentación de clientes con KMeans (aprendizaje automático no supervisado):
# agrupa a los clientes que se parecen en recencia, frecuencia y gasto.
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

import config

# Las 3 variables con las que se agrupan los clientes (R, F y M)
VARIABLES = ["recencia_dias", "frecuencia", "monetario"]
NOMBRES_TABLAS = ["clustering_evaluacion", "clustering_clientes", "clustering_perfil", "clustering_vs_rfm"]


# Guarda en attrs qué función generó la tabla y con cuántas filas
def con_metadatos(df, funcion, filas_origen):
    df.attrs["funcion"] = funcion
    df.attrs["filas_origen"] = filas_origen
    return df


# Cuando no hay datos suficientes, las 4 tablas dicen "NO CALCULABLE" y el motivo
def no_calculable(motivo, filas_origen):
    resultado = {"estado": "NO CALCULABLE", "motivo": motivo, "mejor_k": None}
    for nombre in NOMBRES_TABLAS:
        df = pd.DataFrame([{"estado": "NO CALCULABLE", "motivo": motivo}])
        resultado[nombre] = con_metadatos(df, nombre, filas_origen)
    return resultado


# Prepara los números para KMeans:
# - log1p (logaritmo de 1 + x) suaviza los valores muy grandes, para que un cliente enorme no lo domine todo
# - StandardScaler pone las 3 variables en la misma escala (media 0, desviación 1);
#   si no, el gasto en euros pesaría mucho más que la frecuencia
def preparar_variables(clientes):
    datos = clientes[VARIABLES].copy()
    datos["frecuencia"] = np.log1p(datos["frecuencia"])
    datos["monetario"] = np.log1p(datos["monetario"])
    return StandardScaler().fit_transform(datos)


# Prueba k = 2, 3, 4 y 5 grupos y calcula el silhouette de cada uno
# (va de −1 a 1: cuanto más alto, mejor separados están los grupos)
def evaluar_k(matriz):
    filas = []
    for k in config.VALORES_K:
        # No se pueden hacer más grupos que clientes
        if k >= len(matriz):
            continue
        # n_init=10: prueba 10 arranques distintos y se queda con el mejor; random_state: siempre igual
        modelo = KMeans(n_clusters=k, n_init=10, random_state=config.SEMILLA).fit(matriz)
        filas.append({
            "k": k,
            "silhouette": round(silhouette_score(matriz, modelo.labels_), 3),
            "inercia": round(modelo.inertia_, 2),
            "tamano_grupo_menor": int(np.bincount(modelo.labels_).min()),
        })
    return pd.DataFrame(filas)


# Pone nombre a un grupo comparando sus medianas con las de todos los clientes
def nombrar(perfil, referencia):
    if perfil["frecuencia_mediana"] >= referencia["frecuencia"]:
        frecuencia = "Frecuentes"
    else:
        frecuencia = "Ocasionales"
    if perfil["monetario_mediana"] >= referencia["monetario"]:
        gasto = "alto gasto"
    else:
        gasto = "bajo gasto"
    if perfil["recencia_mediana"] <= referencia["recencia_dias"]:
        recencia = "activos"
    else:
        recencia = "alejados"
    return f"{frecuencia}, {gasto}, {recencia}"


# Segmentación de clientes con KMeans
def clustering_clientes(df_rfm):
    # Solo clientes que han comprado alguna vez
    clientes = df_rfm[df_rfm["frecuencia"] > 0].reset_index(drop=True)

    # Con menos de 20 clientes no se puede agrupar de forma defendible
    if len(clientes) < config.MINIMO_CLIENTES_CLUSTERING:
        motivo = (f"Solo hay {len(clientes)} clientes con compras válidas; se necesitan al menos "
                  f"{config.MINIMO_CLIENTES_CLUSTERING} para agrupar de forma defendible. "
                  "El modelo se demuestra con los datos SINTÉTICOS.")
        return no_calculable(motivo, len(clientes))

    # 1) Preparar los números y probar k = 2 a 5
    matriz = preparar_variables(clientes)
    evaluacion = evaluar_k(matriz)

    # 2) Se elige el k con mayor silhouette
    fila_mejor = evaluacion["silhouette"].idxmax()
    mejor_k = int(evaluacion.loc[fila_mejor, "k"])

    # 3) KMeans definitivo: a cada cliente le toca un número de grupo (0, 1, 2...)
    etiquetas = KMeans(n_clusters=mejor_k, n_init=10, random_state=config.SEMILLA).fit_predict(matriz)
    asignacion = clientes[["id_cliente", "codigo_odoo", "tipo_cliente", "segmento", "recencia_dias", "frecuencia", "monetario"]].copy()
    asignacion["cluster"] = etiquetas

    # 4) Perfil de cada grupo: nº de clientes y medianas de R, F y M
    perfil = asignacion.groupby("cluster").agg(
        clientes=("id_cliente", "count"),
        recencia_mediana=("recencia_dias", "median"),
        frecuencia_mediana=("frecuencia", "median"),
        monetario_mediana=("monetario", "median"),
        monetario_total=("monetario", "sum"),
    ).reset_index()
    perfil["porcentaje_clientes"] = (perfil["clientes"] / perfil["clientes"].sum() * 100).round(1)
    perfil["porcentaje_ingresos"] = (perfil["monetario_total"] / perfil["monetario_total"].sum() * 100).round(1)

    # 5) Nombre de cada grupo. Si dos grupos se llaman igual, se les añade su número
    referencia = clientes[VARIABLES].median()
    perfil["nombre_grupo"] = perfil.apply(nombrar, axis=1, referencia=referencia)
    repetidos = perfil["nombre_grupo"].duplicated(keep=False)
    perfil.loc[repetidos, "nombre_grupo"] = perfil.loc[repetidos, "nombre_grupo"] + " (grupo " + perfil.loc[repetidos, "cluster"].astype(str) + ")"
    perfil = perfil.round(2)

    # 6) Se pega el nombre del grupo a cada cliente
    asignacion = asignacion.merge(perfil[["cluster", "nombre_grupo"]], on="cluster", how="left", validate="many_to_one")

    # 7) Tabla cruzada: cuántos clientes de cada grupo KMeans hay en cada segmento RFM
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
