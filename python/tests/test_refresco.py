import pandas as pd

import refresco


# Ejecuta un ciclo de refresco con los CSV de la copia
def ejecutar(copia, tmp_path, anterior=None, filtros=None):
    return refresco.ciclo(copia, "ACC · REAL", filtros or {}, anterior, carpeta_logs=tmp_path / "logs")


# Ingresos válidos publicados en ese ciclo
def ingresos(ciclo):
    kpis = ciclo["publicacion"]["resultados"]["kpis"].set_index("indicador")
    return float(kpis.loc["Ingresos válidos", "valor"])


# Borra la columna cantidad para simular un CSV defectuoso
def romper_columna(copia):
    lineas = pd.read_csv(copia / "lineas_pedido.csv", dtype=str)
    lineas.drop(columns="cantidad").to_csv(copia / "lineas_pedido.csv", index=False)


# R5: 3 ciclos sin tocar los CSV → "sin cambios", mismas cifras y 3 líneas en el log
def test_r5_sin_cambios_recalcula_y_registra(copia, tmp_path):
    primero = ejecutar(copia, tmp_path)
    segundo = ejecutar(copia, tmp_path, primero)
    tercero = ejecutar(copia, tmp_path, segundo)

    assert [segundo["estado"], tercero["estado"]] == ["sin cambios", "sin cambios"]
    assert tercero["publicacion"]["hora"] > primero["publicacion"]["hora"]
    assert ingresos(tercero) == ingresos(primero)
    assert len((tmp_path / "logs" / "refresco.log").read_text(encoding="utf-8").splitlines()) == 3


# R1: SO011 pasa de BORRADOR a CONFIRMADO → los ingresos suben 749,95 €
def test_r1_nueva_exportacion_cambia_los_kpis(copia, tmp_path):
    primero = ejecutar(copia, tmp_path)
    pedidos = pd.read_csv(copia / "pedidos.csv", dtype=str)
    pedidos.loc[pedidos["ref_odoo"] == "SO011", "estado"] = "CONFIRMADO"
    pedidos.to_csv(copia / "pedidos.csv", index=False)

    segundo = ejecutar(copia, tmp_path, primero)

    assert segundo["estado"] == "correcto"
    assert ingresos(segundo) == round(12876.88 + 749.95, 2)


# R4: CSV roto → error de carga, pero se enseña el último resultado válido como desactualizado
def test_r4_csv_defectuoso_conserva_el_ultimo_valido_como_desactualizado(copia, tmp_path):
    primero = ejecutar(copia, tmp_path)
    romper_columna(copia)

    segundo = ejecutar(copia, tmp_path, primero)

    assert segundo["estado"] == "error de carga"
    assert segundo["desactualizado"]
    assert "cantidad" in segundo["motivo"]
    assert segundo["publicacion"]["hora"] == primero["publicacion"]["hora"]
    assert ingresos(segundo) == 12876.88
