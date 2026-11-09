import pandas as pd

import main


def ejecutar(copia, tmp_path, *extra):
    salida = tmp_path / "salida"
    logs = tmp_path / "logs"
    codigo = main.main(["--entrada", str(copia), "--salida", str(salida), "--logs", str(logs), *extra])
    return codigo, salida / "real", logs / "ejecuciones.log"


def test_ejecucion_completa_genera_csv_y_png(copia, tmp_path):
    codigo, carpeta, log = ejecutar(copia, tmp_path)

    csvs = list(carpeta.glob("*.csv"))
    assert codigo == 0
    assert len(csvs) >= 10
    assert len(list((carpeta / "graficos").glob("*.png"))) == 8
    for ruta in csvs:
        df = pd.read_csv(ruta)
        assert set(df["origen"]) <= {"ACC · REAL"}
        assert "nombre" not in df.columns
    assert "estado=correcto" in log.read_text(encoding="utf-8")


def test_datos_invalidos_no_publican_resultados(copia, tmp_path):
    lineas = pd.read_csv(copia / "lineas_pedido.csv", dtype=str)
    lineas.loc[0, "id_pedido"] = "999"
    lineas.to_csv(copia / "lineas_pedido.csv", index=False)

    codigo, carpeta, log = ejecutar(copia, tmp_path)

    assert codigo == 1
    assert (carpeta / "incidencias.csv").exists()
    assert not (carpeta / "kpis.csv").exists()
    assert "sin publicar" in log.read_text(encoding="utf-8")


def test_filtros_por_consola(copia, tmp_path):
    codigo, carpeta, _ = ejecutar(copia, tmp_path, "--tarea", "descriptivo", "--modelos", "NIK-022", "--desde", "2026-09-01")

    kpis = pd.read_csv(carpeta / "kpis.csv").set_index("indicador")
    assert codigo == 0
    assert kpis.loc["Pares vendidos", "valor"] == "20"
    assert kpis.loc["Pares vendidos", "filtros"] == "desde: 2026-09-01; modelos: NIK-022"
