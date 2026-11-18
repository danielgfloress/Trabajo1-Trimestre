import pytest
from streamlit.testing.v1 import AppTest

import config

APP = str(config.CARPETA_BASE / "app_dashboard.py")


# Arranca el dashboard en modo prueba con los CSV de la copia
@pytest.fixture
def app(copia, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CARPETA_ENTRADA", copia)
    monkeypatch.setattr(config, "CARPETA_LOGS", tmp_path / "logs")
    return AppTest.from_file(APP, default_timeout=120).run()


# Abre las 6 vistas una a una y comprueba que ninguna da error
def test_todas_las_vistas_se_abren_sin_errores(app):
    for vista in app.radio(key="vista").options:
        app.radio(key="vista").set_value(vista).run()
        assert not app.exception, vista
