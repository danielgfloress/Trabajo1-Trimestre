import pytest

import analiticas
import pipeline


# Calcula todo con los CSV de prueba
@pytest.fixture
def resultados(copia):
    return analiticas.calcular_todo(pipeline.ejecutar_pipeline(copia))


# Devuelve el valor de un KPI por su nombre
def kpi(resultados, indicador):
    tabla = resultados["kpis"]
    return tabla.loc[tabla["indicador"] == indicador, "valor"].item()


# 12 pedidos en total y 8 de venta: los 2 cancelados no cuentan como venta
def test_cancelados_no_cuentan_como_venta(resultados):
    pedidos = resultados["pedidos_unicos"]

    assert len(pedidos) == 12
    assert kpi(resultados, "Pedidos válidos (venta)") == "8"
    cancelados = pedidos[pedidos["estado"] == "CANCELADO"]
    assert cancelados["ref_odoo"].tolist() == ["SO006", "SO009"]
    assert not cancelados["es_venta"].any()


# SO010 tiene 5 líneas pero cuenta como 1 pedido de 20 pares
def test_pedido_con_varias_lineas_cuenta_una_vez(resultados):
    pedidos = resultados["pedidos_unicos"]
    so010 = pedidos[pedidos["ref_odoo"] == "SO010"]

    assert len(so010) == 1
    assert so010["num_lineas"].item() == 5
    assert so010["pares"].item() == 20
    assert so010["importe"].item() == pytest.approx(3999.80)


# Ticket medio = ingresos ÷ 8 pedidos (no ÷ líneas)
def test_ticket_medio_entre_pedidos_no_entre_lineas(resultados):
    assert float(kpi(resultados, "Ticket medio")) == pytest.approx(12876.88 / 8, abs=0.01)


# Mismas cifras que en SQL: 96 pares y 12 876,88 €
def test_cifras_coinciden_con_sql(resultados):
    assert float(kpi(resultados, "Pares vendidos")) == 96
    assert float(kpi(resultados, "Ingresos válidos")) == pytest.approx(12876.88)
    assert resultados["clientes_rfm"]["frecuencia"].gt(0).sum() == 5
