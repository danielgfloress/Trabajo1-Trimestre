import pandas as pd
import pytest

import analiticas
import pipeline


@pytest.fixture
def resultados(copia):
    return analiticas.calcular_todo(pipeline.ejecutar_pipeline(copia))


def kpi(resultados, indicador):
    tabla = resultados["kpis"]
    return tabla.loc[tabla["indicador"] == indicador, "valor"].item()


def test_cancelados_no_cuentan_como_venta(resultados):
    pedidos = resultados["pedidos_unicos"]

    assert len(pedidos) == 12
    assert kpi(resultados, "Pedidos válidos (venta)") == "8"
    cancelados = pedidos[pedidos["estado"] == "CANCELADO"]
    assert cancelados["ref_odoo"].tolist() == ["SO006", "SO009"]
    assert not cancelados["es_venta"].any()


def test_pedido_con_varias_lineas_cuenta_una_vez(resultados):
    pedidos = resultados["pedidos_unicos"]
    so010 = pedidos[pedidos["ref_odoo"] == "SO010"]

    assert len(so010) == 1
    assert so010["num_lineas"].item() == 5
    assert so010["pares"].item() == 20
    assert so010["importe"].item() == pytest.approx(3999.80)


def test_ticket_medio_entre_pedidos_no_entre_lineas(resultados):
    assert float(kpi(resultados, "Ticket medio")) == pytest.approx(12876.88 / 8, abs=0.01)


def test_cifras_coinciden_con_sql(resultados):
    assert float(kpi(resultados, "Pares vendidos")) == 96
    assert float(kpi(resultados, "Ingresos válidos")) == pytest.approx(12876.88)
    assert resultados["clientes_rfm"]["frecuencia"].gt(0).sum() == 5


def test_rfm_cuenta_pedidos_no_lineas(resultados):
    rfm = resultados["clientes_rfm"]
    cli002 = rfm[rfm["codigo_odoo"] == "CLI002"]

    assert cli002["frecuencia"].item() == 2
    assert cli002["monetario"].item() == pytest.approx(1619.82 + 2239.80)


def test_variables_de_un_pedido(resultados):
    pedidos = resultados["pedidos_unicos"]
    so010 = pedidos[pedidos["ref_odoo"] == "SO010"].iloc[0]

    assert so010["anio"] == 2026
    assert so010["trimestre"] == 3
    assert so010["dia_semana"] == "miércoles"
    assert so010["precio_medio_par"] == pytest.approx(3999.80 / 20)


def test_variables_de_un_cliente(resultados):
    clientes = resultados["caracteristicas_clientes"]
    cli002 = clientes[clientes["codigo_odoo"] == "CLI002"].iloc[0]

    assert cli002["frecuencia_cliente"] == 2
    assert cli002["porcentaje_custom"] == 50.0
    assert cli002["intervalo_medio_dias"] == 48


def test_media_3_meses_previos_no_usa_el_mes_actual(resultados):
    demanda = resultados["demanda_modelo_mes"]
    runner = demanda[demanda["codigo_modelo"] == "D3-001"].set_index("mes")

    assert runner["unidades_modelo_mes"].tolist() == [20, 4, 0, 0]
    assert runner.loc["2026-07", "demanda_mes_anterior"] == 20
    assert pd.isna(runner.loc["2026-08", "media_3_meses_previos"])
    assert runner.loc["2026-09", "media_3_meses_previos"] == pytest.approx((20 + 4 + 0) / 3)


def test_talla_mas_solicitada(resultados):
    tallas = resultados["talla_mas_solicitada"]
    runner = tallas[tallas["codigo_modelo"] == "D3-001"].iloc[0]

    assert runner["talla_mas_solicitada"] == 41
    assert runner["pares_talla"] == 10


def test_estadistica_descriptiva_del_importe(resultados):
    tabla = resultados["estadistica_descriptiva"].set_index("variable")
    importe = tabla.loc["importe por pedido"]
    pares = tabla.loc["pares por pedido"]

    assert importe["n"] == 8
    assert importe["media"] == pytest.approx(12876.88 / 8, abs=0.01)
    assert importe["mediana"] == pytest.approx((1619.82 + 1619.92) / 2, abs=0.01)
    assert pd.isna(importe["moda"])
    assert pares["moda"] == 20
    assert importe["aviso"].startswith("muestra pequeña")


def test_estadistica_custom_frente_a_estandar(resultados):
    tabla = resultados["estadistica_por_grupo"]
    importe = tabla[tabla["variable"] == "importe por pedido"].set_index("grupo")

    assert importe.loc["CUSTOM", "n"] == 3
    assert importe.loc["ESTANDAR", "n"] == 5
    assert importe.loc["CUSTOM", "media"] == pytest.approx((2098.00 + 2239.80 + 3999.80) / 3, abs=0.01)


def test_hipotesis_custom_factura_mas(resultados):
    h1 = resultados["hipotesis"].iloc[0]

    assert h1["n"] == "3 / 5"
    assert h1["valor_observado"] == pytest.approx(2779.20 - 907.86, abs=0.01)
    assert h1["ic95_inferior"] > 0
    assert h1["conclusion"] == "se apoya"


def test_hipotesis_cancelacion_sin_evidencia(resultados):
    h3 = resultados["hipotesis"].iloc[2]

    assert h3["valor_observado"] == pytest.approx(1 / 4 * 100 - 1 / 8 * 100)
    assert h3["ic95_inferior"] < 0 < h3["ic95_superior"]
    assert h3["conclusion"] == "evidencia insuficiente"


def test_bootstrap_misma_semilla_mismo_resultado(resultados):
    pedidos = resultados["pedidos_unicos"]
    lineas = resultados["lineas_enriquecidas"]

    primera = analiticas.hipotesis(pedidos, lineas)
    segunda = analiticas.hipotesis(pedidos, lineas)
    pd.testing.assert_frame_equal(primera, segunda)


def test_filtro_por_modelo(copia):
    resultado = pipeline.ejecutar_pipeline(copia)
    filtrados = analiticas.calcular_todo(resultado, {"modelos": ["47"]})

    assert kpi(filtrados, "Pedidos válidos (venta)") == "2"
    assert float(kpi(filtrados, "Pares vendidos")) == 23
    assert float(kpi(filtrados, "Ingresos válidos")) == pytest.approx(569.97 + 3999.80)
