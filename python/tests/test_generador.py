import pandas as pd

import generador_datos


# Misma semilla (42) → mismos datos; otra semilla (7) → datos distintos
def test_misma_semilla_mismos_datos():
    primera = generador_datos.generar(42)
    segunda = generador_datos.generar(42)
    otra = generador_datos.generar(7)

    for nombre in primera:
        pd.testing.assert_frame_equal(primera[nombre], segunda[nombre])
    assert not primera["pedidos"].equals(otra["pedidos"])
