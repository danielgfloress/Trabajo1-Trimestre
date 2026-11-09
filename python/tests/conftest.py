import shutil
from pathlib import Path

import pytest

import config

DATOS_PRUEBA = Path(__file__).parent / "datos"


@pytest.fixture
def copia(tmp_path):
    for archivo in config.ARCHIVOS.values():
        shutil.copy(DATOS_PRUEBA / archivo, tmp_path / archivo)
    return tmp_path
