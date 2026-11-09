import pandas as pd
import pytest

import config
import generador_datos
import pipeline


@pytest.fixture(scope="module")
def carpeta_sintetica(tmp_path_factory):
    carpeta = tmp_path_factory.mktemp("sintetico")
    generador_datos.main(["--salida", str(carpeta)])
    return carpeta


def test_misma_semilla_mismos_datos():
    primera = generador_datos.generar(42)
    segunda = generador_datos.generar(42)
    otra = generador_datos.generar(7)

    for nombre in primera:
        pd.testing.assert_frame_equal(primera[nombre], segunda[nombre])
    assert not primera["pedidos"].equals(otra["pedidos"])


def test_cumple_los_minimos_del_pdf():
    tablas = generador_datos.generar()
    meses = tablas["pedidos"]["fecha_pedido"].dt.to_period("M")

    assert len(tablas["pedidos"]) >= 800
    assert len(tablas["lineas"]) >= 1600
    assert len(tablas["clientes"]) >= 40
    assert len(tablas["modelos"]) >= 12
    assert meses.nunique() == 18
    assert (meses.max() - meses.min()).n == 17


def test_datos_limpios_pasan_la_validacion(carpeta_sintetica):
    resultado = pipeline.ejecutar_pipeline(carpeta_sintetica)

    assert resultado["estado"] == "correcto"
    assert resultado["incidencias"].empty


def test_reglas_de_negocio():
    tablas = generador_datos.generar()
    pedidos, lineas = tablas["pedidos"], tablas["lineas"]
    pares = lineas.groupby("id_pedido")["cantidad"].sum()
    custom = pedidos.loc[pedidos["tipo"] == "CUSTOM", "id_pedido"]

    assert (pares[custom] >= config.SINTETICO_MINIMO_CUSTOM).all()
    assert (lineas["cantidad"] > 0).all()
    suma = lineas.groupby("id_pedido")["subtotal_linea"].sum().round(2)
    assert (pedidos.set_index("id_pedido")["importe_total"] - suma).abs().max() < 0.01
    assert pedidos["estado"].isin(config.ESTADOS_VALIDOS).all()


def test_copia_con_incidencias_se_detecta(carpeta_sintetica):
    carpeta = carpeta_sintetica / "con_incidencias"
    introducidas = pd.read_csv(carpeta / "incidencias_introducidas.csv", dtype=str)

    resultado = pipeline.ejecutar_pipeline(carpeta)
    detectadas = resultado["incidencias"]

    assert resultado["publicable"] is False
    for _, fila in introducidas.iterrows():
        mismas = detectadas[(detectadas["tabla"] == fila["tabla"]) & (detectadas["registro"] == fila["registro"])]
        assert mismas["regla"].str.startswith(fila["regla_esperada"]).any(), fila.to_dict()
