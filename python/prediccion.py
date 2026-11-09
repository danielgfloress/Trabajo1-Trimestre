import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error

import config

OBJETIVO = "unidades_modelo_mes"
NUMERICAS = ["demanda_mes_anterior", "media_3_meses_previos", "mes_del_anio"]
TABLAS = ["prediccion_evaluacion", "prediccion_por_modelo", "prediccion_detalle", "prediccion_variables", "prediccion_proximo_mes"]


def con_metadatos(df, funcion, filas_origen):
    df.attrs["funcion"] = funcion
    df.attrs["filas_origen"] = filas_origen
    return df


def no_calculable(motivo, filas_origen):
    df = pd.DataFrame([{"estado": "NO CALCULABLE", "motivo": motivo}])
    tablas = {nombre: con_metadatos(df.copy(), nombre, filas_origen) for nombre in TABLAS}
    return {"estado": "NO CALCULABLE", "motivo": motivo, **tablas}


def matriz_variables(df, modelos):
    variables = df[NUMERICAS].copy()
    for modelo in modelos:
        variables[f"modelo_{modelo}"] = (df["codigo_modelo"] == modelo).astype(int)
    return variables


def nuevo_bosque():
    return RandomForestRegressor(n_estimators=config.BOSQUE_ARBOLES, max_depth=config.BOSQUE_PROFUNDIDAD,
                                 min_samples_leaf=config.BOSQUE_MINIMO_HOJA, random_state=config.SEMILLA, n_jobs=1)


def errores(real, estimado):
    return mean_absolute_error(real, estimado), np.sqrt(mean_squared_error(real, estimado))


def separar_por_fecha(utiles):
    meses = sorted(utiles["mes"].unique())
    meses_prueba = meses[-config.MESES_PRUEBA:]
    entrenamiento = utiles[~utiles["mes"].isin(meses_prueba)]
    prueba = utiles[utiles["mes"].isin(meses_prueba)]
    return entrenamiento, prueba


def siguiente_mes(demanda):
    ultimo = pd.Period(demanda["mes"].max(), freq="M")
    proximo = ultimo + 1
    filas = []
    for modelo, serie in demanda.sort_values("mes").groupby("codigo_modelo"):
        unidades = serie[OBJETIVO].tolist()
        filas.append({
            "codigo_modelo": modelo,
            "mes": str(proximo),
            "demanda_mes_anterior": unidades[-1],
            "media_3_meses_previos": np.mean(unidades[-3:]) if len(unidades) >= 3 else np.nan,
            "mes_del_anio": proximo.month,
        })
    return pd.DataFrame(filas)


def predecir_demanda(demanda):
    utiles = demanda.dropna(subset=NUMERICAS).copy()
    meses_utiles = utiles["mes"].nunique()
    necesarios = config.MESES_PRUEBA + config.MINIMO_MESES_ENTRENAMIENTO
    if meses_utiles < necesarios:
        motivo = (f"Solo hay {meses_utiles} meses con historial completo (3 meses previos); se necesitan {necesarios} "
                  f"({config.MINIMO_MESES_ENTRENAMIENTO} para entrenar y {config.MESES_PRUEBA} para evaluar). "
                  "La predicción se demuestra con los datos SINTÉTICOS.")
        return no_calculable(motivo, len(demanda))

    modelos = sorted(utiles["codigo_modelo"].unique())
    entrenamiento, prueba = separar_por_fecha(utiles)
    bosque = nuevo_bosque().fit(matriz_variables(entrenamiento, modelos), entrenamiento[OBJETIVO])

    detalle = prueba[["codigo_modelo", "mes", OBJETIVO]].rename(columns={OBJETIVO: "real"}).copy()
    detalle["baseline"] = prueba["demanda_mes_anterior"].to_numpy()
    detalle["prediccion"] = bosque.predict(matriz_variables(prueba, modelos)).round(1)
    detalle["error_baseline"] = (detalle["baseline"] - detalle["real"]).abs()
    detalle["error_modelo"] = (detalle["prediccion"] - detalle["real"]).abs().round(1)

    mae_base, rmse_base = errores(detalle["real"], detalle["baseline"])
    mae_modelo, rmse_modelo = errores(detalle["real"], detalle["prediccion"])
    mejora = (mae_base - mae_modelo) / mae_base * 100 if mae_base else np.nan
    conclusion = ("el modelo MEJORA a la referencia" if mae_modelo < mae_base
                  else "el modelo NO mejora a la referencia: no aporta frente a repetir el mes anterior")
    periodo = f"entrena {entrenamiento['mes'].min()} a {entrenamiento['mes'].max()} · evalúa {prueba['mes'].min()} a {prueba['mes'].max()}"
    evaluacion = pd.DataFrame([
        {"metodo": "baseline (repetir el mes anterior)", "mae": mae_base, "rmse": rmse_base,
         "sesgo": (detalle["baseline"] - detalle["real"]).mean()},
        {"metodo": "RandomForestRegressor", "mae": mae_modelo, "rmse": rmse_modelo,
         "sesgo": (detalle["prediccion"] - detalle["real"]).mean()},
    ]).round(2)
    evaluacion["filas_entrenamiento"] = len(entrenamiento)
    evaluacion["filas_prueba"] = len(prueba)
    evaluacion["periodo"] = periodo
    evaluacion["mejora_mae_pct"] = round(mejora, 1)
    evaluacion["conclusion"] = conclusion

    por_modelo = detalle.groupby("codigo_modelo").agg(
        pares_reales=("real", "sum"),
        mae_baseline=("error_baseline", "mean"),
        mae_modelo=("error_modelo", "mean"),
    ).round(2).reset_index()
    por_modelo["mejor"] = np.where(por_modelo["mae_modelo"] < por_modelo["mae_baseline"], "modelo",
                                   np.where(por_modelo["mae_modelo"] > por_modelo["mae_baseline"], "baseline", "empate"))

    variables = pd.DataFrame({"variable": matriz_variables(entrenamiento, modelos).columns,
                              "importancia": bosque.feature_importances_.round(3)}).sort_values("importancia", ascending=False)

    bosque_final = nuevo_bosque().fit(matriz_variables(utiles, modelos), utiles[OBJETIVO])
    proximo = siguiente_mes(demanda).dropna(subset=NUMERICAS)
    proximo["prediccion"] = bosque_final.predict(matriz_variables(proximo, modelos)).round(1)
    proximo["baseline"] = proximo["demanda_mes_anterior"]

    filas = len(utiles)
    return {
        "estado": "CALCULADO",
        "motivo": f"{periodo}; {conclusion}",
        "prediccion_evaluacion": con_metadatos(evaluacion, "prediccion_evaluacion", filas),
        "prediccion_por_modelo": con_metadatos(por_modelo, "prediccion_por_modelo", filas),
        "prediccion_detalle": con_metadatos(detalle.reset_index(drop=True), "prediccion_detalle", filas),
        "prediccion_variables": con_metadatos(variables.reset_index(drop=True), "prediccion_variables", filas),
        "prediccion_proximo_mes": con_metadatos(proximo[["codigo_modelo", "mes", "baseline", "prediccion"]].reset_index(drop=True),
                                                "prediccion_proximo_mes", filas),
    }
