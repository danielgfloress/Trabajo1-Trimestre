import pandas as pd
import pytest

import analiticas
import pipeline


# Lee un CSV de la copia como texto
def leer(carpeta, archivo):
    return pd.read_csv(carpeta / archivo, dtype=str, keep_default_na=False)


# Incidencias cuya regla contiene un texto
def incidencias_de(resultado, texto):
    df = resultado["incidencias"]
    return df[df["regla"].str.contains(texto)]


# Una línea apunta al pedido 999, que no existe → bloqueante, no se publica
def test_id_huerfano(copia):
    lineas = leer(copia, "lineas_pedido.csv")
    lineas.loc[lineas["id_linea"] == "1", "id_pedido"] = "999"
    lineas.to_csv(copia / "lineas_pedido.csv", index=False)

    resultado = pipeline.ejecutar_pipeline(copia)

    huerfana = incidencias_de(resultado, "id_pedido inexistente")
    assert huerfana["registro"].tolist() == ["1"]
    assert huerfana["gravedad"].tolist() == ["bloqueante"]
    assert resultado["estado"] == "datos inválidos"
    assert resultado["publicable"] is False


# Pedido repetido → recuperable: se queda uno y sus líneas no se pierden
def test_pedido_duplicado_conserva_sus_lineas(copia):
    pedidos = leer(copia, "pedidos.csv")
    pd.concat([pedidos, pedidos.head(1)]).to_csv(copia / "pedidos.csv", index=False)

    resultado = pipeline.ejecutar_pipeline(copia)

    assert incidencias_de(resultado, "id_pedido duplicado")["gravedad"].tolist() == ["recuperable"]
    assert resultado["publicable"] is True
    assert len(resultado["tablas"]["pedidos"]) == 12
    assert len(resultado["tablas"]["lineas"]) == 25


# El merge no multiplica filas; si un modelo está duplicado, validate= da MergeError
def test_cardinalidad_del_merge(copia):
    resultado = pipeline.ejecutar_pipeline(copia)
    tablas = resultado["tablas"]

    df_lineas = analiticas.lineas_enriquecidas(tablas)
    assert len(df_lineas) == len(tablas["lineas"])

    con_duplicado = dict(tablas)
    con_duplicado["modelos"] = pd.concat([tablas["modelos"], tablas["modelos"].head(1)])
    with pytest.raises(pd.errors.MergeError):
        analiticas.lineas_enriquecidas(con_duplicado)


# Cantidad -5 → esa línea se rechaza (quedan 24)
def test_cantidad_negativa(copia):
    lineas = leer(copia, "lineas_pedido.csv")
    lineas.loc[lineas["id_linea"] == "1", "cantidad"] = "-5"
    lineas.to_csv(copia / "lineas_pedido.csv", index=False)

    resultado = pipeline.ejecutar_pipeline(copia)

    negativa = incidencias_de(resultado, "cantidad nula, cero o negativa")
    assert negativa["registro"].tolist() == ["1"]
    assert "1" not in resultado["tablas"]["lineas"]["id_linea"].tolist()
    assert len(resultado["tablas"]["lineas"]) == 24
