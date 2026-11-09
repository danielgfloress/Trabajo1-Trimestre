import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

import config

APP = str(config.CARPETA_BASE / "app_dashboard.py")


@pytest.fixture
def app(copia, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CARPETA_ENTRADA", copia)
    monkeypatch.setattr(config, "CARPETA_LOGS", tmp_path / "logs")
    return AppTest.from_file(APP, default_timeout=120).run()


def metrica(app, etiqueta):
    return [m.value for m in app.metric if m.label == etiqueta]


def test_todas_las_vistas_se_abren_sin_errores(app):
    for vista in app.radio(key="vista").options:
        app.radio(key="vista").set_value(vista).run()
        assert not app.exception, vista


def test_kpis_y_descargas_con_datos_reales(app):
    assert metrica(app, "Ingresos válidos") == ["12.876,88 €"]
    assert metrica(app, "Pares vendidos") == ["96"]
    assert len(app.get("download_button")) >= 5


def test_r6_filtro_se_mantiene_al_cambiar_de_vista(app):
    app.multiselect(key="f_modelos").set_value(["NIK-022"]).run()
    app.radio(key="vista").set_value("Almacén").run()
    app.radio(key="vista").set_value("Dirección").run()

    assert app.multiselect(key="f_modelos").value == ["NIK-022"]
    assert metrica(app, "Pares vendidos") == ["23"]


def test_csv_defectuoso_muestra_desactualizado(app, copia):
    lineas = pd.read_csv(copia / "lineas_pedido.csv", dtype=str)
    lineas.drop(columns="cantidad").to_csv(copia / "lineas_pedido.csv", index=False)

    app.run()

    assert any("DESACTUALIZADOS" in aviso.value for aviso in app.error)
    assert metrica(app, "Ingresos válidos") == ["12.876,88 €"]
