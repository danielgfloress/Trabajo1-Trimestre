import pandas as pd
import pytest

import analiticas
import generador_datos
import pipeline
import segmentacion


# RFM de los datos sintéticos (hay clientes suficientes para KMeans)
@pytest.fixture(scope="module")
def rfm_sintetico(tmp_path_factory):
    carpeta = tmp_path_factory.mktemp("sintetico")
    generador_datos.guardar(generador_datos.generar(), carpeta)
    return analiticas.calcular_todo(pipeline.ejecutar_pipeline(carpeta))["clientes_rfm"]


# Ejecutar KMeans dos veces da exactamente los mismos grupos
def test_clustering_reproducible(rfm_sintetico):
    primera = segmentacion.clustering_clientes(rfm_sintetico)["clustering_clientes"]
    segunda = segmentacion.clustering_clientes(rfm_sintetico)["clustering_clientes"]

    pd.testing.assert_frame_equal(primera, segunda)
