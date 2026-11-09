from pathlib import Path

CARPETA_BASE = Path(__file__).parent
CARPETA_ENTRADA = CARPETA_BASE / "entrada_acc"
CARPETA_SINTETICOS = CARPETA_BASE / "datos_sinteticos"
CARPETA_SALIDA = CARPETA_BASE / "outputs"
CARPETA_LOGS = CARPETA_BASE / "logs"

ARCHIVOS = {
    "clientes": "clientes.csv",
    "modelos": "modelos.csv",
    "pedidos": "pedidos.csv",
    "lineas": "lineas_pedido.csv",
    "stock": "stock.csv",
}

COLUMNAS_OBLIGATORIAS = {
    "clientes": ["id_cliente", "codigo_odoo", "nombre", "tipo_cliente", "activo"],
    "modelos": ["id_modelo", "codigo_modelo", "marca", "nombre", "categoria", "precio_base", "admite_custom", "activo"],
    "pedidos": ["id_pedido", "ref_odoo", "fecha_pedido", "id_cliente", "tipo", "estado", "importe_total"],
    "lineas": ["id_linea", "id_pedido", "id_modelo", "color", "talla", "cantidad", "precio_unitario", "subtotal_linea", "personalizada"],
    "stock": ["id_modelo", "color", "talla", "stock_disponible", "stock_minimo", "fecha_corte"],
}

ORIGENES = {"real": "ACC · REAL", "sintetico": "SINTÉTICO · generador_datos.py"}
CARPETAS_ENTRADA = {"real": CARPETA_ENTRADA, "sintetico": CARPETA_SINTETICOS}

FORMATO_FECHA = "%Y-%m-%d %H:%M:%S"

ESTADOS_VALIDOS = ["BORRADOR", "CONFIRMADO", "ENTREGADO", "CANCELADO"]
ESTADOS_VENTA = ["CONFIRMADO", "ENTREGADO"]
TIPOS_PEDIDO = ["ESTANDAR", "CUSTOM"]
TIPOS_CLIENTE = ["CLUB", "EQUIPO", "PARTICULAR"]
TALLAS_VALIDAS = list(range(36, 47))
DIAS_SEMANA = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]

TOLERANCIA_IMPORTE = 0.01
DIAS_DEMANDA_RECIENTE = 28
SEGUNDOS_REFRESCO = 60
SEMILLA = 42

SINTETICO_PEDIDOS = 900
SINTETICO_CLIENTES = 45
SINTETICO_INICIO = "2025-01-01"
SINTETICO_MESES = 18
SINTETICO_MINIMO_CUSTOM = 20
CARPETA_SINTETICOS_INCIDENCIAS = CARPETA_SINTETICOS / "con_incidencias"

RFM_DIAS_RECIENTE = 60
RFM_DIAS_RIESGO = 120
RFM_FRECUENCIA_LEAL = 2
MINIMO_CLIENTES_COHORTES = 10
MINIMO_MUESTRA_ESTADISTICA = 30
UMBRAL_ASIMETRIA = 0.10
REPETICIONES_BOOTSTRAP = 2000
TALLAS_CENTRALES = [40, 41, 42]
FACTOR_IQR = 1.5
MINIMO_MUESTRA_IQR = 4
