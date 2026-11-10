import pandas as pd

import config
import pipeline


def leer(carpeta, archivo):
    return pd.read_csv(carpeta / archivo, dtype=str, keep_default_na=False)


def reglas(resultado):
    return resultado["incidencias"]["regla"]


def test_ruta_inexistente(tmp_path):
    resultado = pipeline.ejecutar_pipeline(tmp_path / "no_existe")

    assert resultado["estado"] == "error de carga"
    assert resultado["publicable"] is False
    assert reglas(resultado).str.contains("fichero inexistente").sum() == len(config.ARCHIVOS)


def test_csv_vacio(copia):
    (copia / "clientes.csv").write_text("", encoding="utf-8")

    resultado = pipeline.ejecutar_pipeline(copia)

    assert resultado["publicable"] is False
    vacio = resultado["incidencias"][reglas(resultado).str.contains("fichero vacío")]
    assert vacio["tabla"].tolist() == ["clientes"]
    assert vacio["gravedad"].tolist() == ["bloqueante"]


def test_columna_ausente(copia):
    pedidos = leer(copia, "pedidos.csv")
    pedidos.drop(columns="fecha_pedido").to_csv(copia / "pedidos.csv", index=False)

    resultado = pipeline.ejecutar_pipeline(copia)

    assert resultado["publicable"] is False
    assert reglas(resultado).str.contains("faltan columnas: fecha_pedido").any()


def test_fecha_corrupta(copia):
    pedidos = leer(copia, "pedidos.csv")
    pedidos.loc[pedidos["ref_odoo"] == "SO001", "fecha_pedido"] = "2026-13-45 10:00:00"
    pedidos.to_csv(copia / "pedidos.csv", index=False)

    resultado = pipeline.ejecutar_pipeline(copia)

    fecha = resultado["incidencias"][reglas(resultado).str.contains("fecha nula o imposible")]
    assert fecha["registro"].tolist() == ["SO001"]
    assert "SO001" not in resultado["tablas"]["pedidos"]["ref_odoo"].tolist()
    assert len(resultado["tablas"]["pedidos"]) == 11
