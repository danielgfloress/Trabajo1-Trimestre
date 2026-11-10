import pandas as pd
import pytest

import analiticas
import config
import generador_datos
import pipeline
import prediccion


@pytest.fixture(scope="module")
def demanda_sintetica(tmp_path_factory):
    carpeta = tmp_path_factory.mktemp("sintetico")
    generador_datos.guardar(generador_datos.generar(), carpeta)
    return analiticas.calcular_todo(pipeline.ejecutar_pipeline(carpeta))["demanda_modelo_mes"]


def test_datos_reales_insuficientes_avisan(copia):
    demanda = analiticas.calcular_todo(pipeline.ejecutar_pipeline(copia))["demanda_modelo_mes"]

    resultado = prediccion.predecir_demanda(demanda)

    assert resultado["estado"] == "NO CALCULABLE"
    for nombre in prediccion.TABLAS:
        assert resultado[nombre]["estado"].tolist() == ["NO CALCULABLE"]


def test_no_se_entrena_con_los_meses_de_prueba(demanda_sintetica):
    utiles = demanda_sintetica.dropna(subset=prediccion.NUMERICAS)

    entrenamiento, prueba = prediccion.separar_por_fecha(utiles)

    assert entrenamiento["mes"].max() < prueba["mes"].min()
    assert sorted(prueba["mes"].unique()) == sorted(utiles["mes"].unique())[-config.MESES_PRUEBA:]
    assert len(entrenamiento) + len(prueba) == len(utiles)


def test_ninguna_variable_usa_datos_futuros(demanda_sintetica):
    for _, serie in demanda_sintetica.sort_values("mes").groupby("codigo_modelo"):
        unidades = serie["unidades_modelo_mes"].tolist()
        anteriores = serie["demanda_mes_anterior"].tolist()
        medias = serie["media_3_meses_previos"].tolist()
        for i in range(3, len(unidades)):
            assert anteriores[i] == unidades[i - 1]
            assert medias[i] == pytest.approx(sum(unidades[i - 3:i]) / 3, abs=0.01)


def test_baseline_es_el_mes_anterior_y_se_compara(demanda_sintetica):
    resultado = prediccion.predecir_demanda(demanda_sintetica)
    detalle = resultado["prediccion_detalle"]
    evaluacion = resultado["prediccion_evaluacion"]

    claves = demanda_sintetica.set_index(["codigo_modelo", "mes"])["demanda_mes_anterior"]
    esperado = claves.loc[list(zip(detalle["codigo_modelo"], detalle["mes"]))].to_numpy()
    assert (detalle["baseline"].to_numpy() == esperado).all()
    assert set(evaluacion["metodo"]) == {"baseline (repetir el mes anterior)", "RandomForestRegressor"}
    assert {"mae", "rmse"} <= set(evaluacion.columns)


def test_prediccion_reproducible(demanda_sintetica):
    primera = prediccion.predecir_demanda(demanda_sintetica)["prediccion_detalle"]
    segunda = prediccion.predecir_demanda(demanda_sintetica)["prediccion_detalle"]

    pd.testing.assert_frame_equal(primera, segunda)
