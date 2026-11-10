import shutil

import pandas as pd

import refresco
from conftest import DATOS_PRUEBA


def ejecutar(copia, tmp_path, anterior=None, filtros=None):
    return refresco.ciclo(copia, "ACC · REAL", filtros or {}, anterior, carpeta_logs=tmp_path / "logs")


def ingresos(ciclo):
    kpis = ciclo["publicacion"]["resultados"]["kpis"].set_index("indicador")
    return float(kpis.loc["Ingresos válidos", "valor"])


def romper_columna(copia):
    lineas = pd.read_csv(copia / "lineas_pedido.csv", dtype=str)
    lineas.drop(columns="cantidad").to_csv(copia / "lineas_pedido.csv", index=False)


def test_primer_ciclo_correcto(copia, tmp_path):
    ciclo = ejecutar(copia, tmp_path)

    assert ciclo["estado"] == "correcto"
    assert not ciclo["desactualizado"]
    assert ingresos(ciclo) == 12876.88


def test_r5_sin_cambios_recalcula_y_registra(copia, tmp_path):
    primero = ejecutar(copia, tmp_path)
    segundo = ejecutar(copia, tmp_path, primero)
    tercero = ejecutar(copia, tmp_path, segundo)

    assert [segundo["estado"], tercero["estado"]] == ["sin cambios", "sin cambios"]
    assert tercero["publicacion"]["hora"] > primero["publicacion"]["hora"]
    assert ingresos(tercero) == ingresos(primero)
    assert len((tmp_path / "logs" / "refresco.log").read_text(encoding="utf-8").splitlines()) == 3


def test_r1_nueva_exportacion_cambia_los_kpis(copia, tmp_path):
    primero = ejecutar(copia, tmp_path)
    pedidos = pd.read_csv(copia / "pedidos.csv", dtype=str)
    pedidos.loc[pedidos["ref_odoo"] == "SO011", "estado"] = "CONFIRMADO"
    pedidos.to_csv(copia / "pedidos.csv", index=False)

    segundo = ejecutar(copia, tmp_path, primero)

    assert segundo["estado"] == "correcto"
    assert ingresos(segundo) == round(12876.88 + 749.95, 2)


def test_r4_csv_defectuoso_conserva_el_ultimo_valido_como_desactualizado(copia, tmp_path):
    primero = ejecutar(copia, tmp_path)
    romper_columna(copia)

    segundo = ejecutar(copia, tmp_path, primero)

    assert segundo["estado"] == "error de carga"
    assert segundo["desactualizado"]
    assert "cantidad" in segundo["motivo"]
    assert segundo["publicacion"]["hora"] == primero["publicacion"]["hora"]
    assert ingresos(segundo) == 12876.88


def test_caso_m_recuperacion_tras_csv_defectuoso(copia, tmp_path):
    primero = ejecutar(copia, tmp_path)
    romper_columna(copia)
    segundo = ejecutar(copia, tmp_path, primero)
    shutil.copy(DATOS_PRUEBA / "lineas_pedido.csv", copia / "lineas_pedido.csv")

    tercero = ejecutar(copia, tmp_path, segundo)

    assert tercero["estado"] == "correcto"
    assert not tercero["desactualizado"]
    assert tercero["publicacion"]["hora"] > primero["publicacion"]["hora"]


def test_relacion_huerfana_sin_resultado_previo_no_publica(copia, tmp_path):
    lineas = pd.read_csv(copia / "lineas_pedido.csv", dtype=str)
    lineas.loc[0, "id_pedido"] = "999"
    lineas.to_csv(copia / "lineas_pedido.csv", index=False)

    ciclo = ejecutar(copia, tmp_path)

    assert ciclo["estado"] == "datos inválidos"
    assert ciclo["publicacion"] is None
    assert "id_pedido inexistente" in ciclo["motivo"]


def test_csv_que_cambia_durante_la_lectura_no_se_publica(copia, tmp_path, monkeypatch):
    huellas = iter(["antes", "despues"])
    monkeypatch.setattr(refresco, "huella", lambda carpeta: next(huellas))

    ciclo = ejecutar(copia, tmp_path)

    assert ciclo["estado"] == "error de carga"
    assert ciclo["publicacion"] is None
    assert "exportación en curso" in ciclo["motivo"]
