import pandas as pd
import pytest

import analiticas
import config
import generador_datos
import pipeline
import segmentacion


@pytest.fixture(scope="module")
def rfm_sintetico(tmp_path_factory):
    carpeta = tmp_path_factory.mktemp("sintetico")
    generador_datos.guardar(generador_datos.generar(), carpeta)
    return analiticas.calcular_todo(pipeline.ejecutar_pipeline(carpeta))["clientes_rfm"]


def test_datos_reales_insuficientes_avisan(copia):
    rfm = analiticas.calcular_todo(pipeline.ejecutar_pipeline(copia))["clientes_rfm"]

    resultado = segmentacion.clustering_clientes(rfm)

    assert resultado["estado"] == "NO CALCULABLE"
    assert "5 clientes" in resultado["motivo"]
    for nombre in ["clustering_evaluacion", "clustering_clientes", "clustering_perfil", "clustering_vs_rfm"]:
        assert resultado[nombre]["estado"].tolist() == ["NO CALCULABLE"]


def test_se_prueban_k_2_a_5_y_se_elige_el_mejor_silhouette(rfm_sintetico):
    resultado = segmentacion.clustering_clientes(rfm_sintetico)
    evaluacion = resultado["clustering_evaluacion"]

    assert resultado["estado"] == "CALCULADO"
    assert evaluacion["k"].tolist() == config.VALORES_K
    assert resultado["mejor_k"] == evaluacion.loc[evaluacion["silhouette"].idxmax(), "k"]


def test_cada_cliente_en_un_solo_grupo(rfm_sintetico):
    resultado = segmentacion.clustering_clientes(rfm_sintetico)
    asignacion = resultado["clustering_clientes"]
    compradores = (rfm_sintetico["frecuencia"] > 0).sum()

    assert len(asignacion) == compradores
    assert asignacion["id_cliente"].is_unique
    assert resultado["clustering_perfil"]["clientes"].sum() == compradores
    total = resultado["clustering_vs_rfm"].set_index("nombre_grupo").loc["Total", "Total"]
    assert total == compradores


def test_clustering_reproducible(rfm_sintetico):
    primera = segmentacion.clustering_clientes(rfm_sintetico)["clustering_clientes"]
    segunda = segmentacion.clustering_clientes(rfm_sintetico)["clustering_clientes"]

    pd.testing.assert_frame_equal(primera, segunda)
