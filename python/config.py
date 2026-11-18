# Configuración del proyecto: rutas, reglas de negocio y umbrales. Los demás archivos leen de aquí.
import os
from pathlib import Path

# Rutas (relativas a esta carpeta). Entrada y logs se pueden cambiar con variables de entorno
CARPETA_BASE = Path(__file__).parent
CARPETA_ENTRADA = Path(os.environ.get("SNEAKER_ENTRADA", CARPETA_BASE / "entrada_acc"))
CARPETA_SINTETICOS = CARPETA_BASE / "datos_sinteticos"
CARPETA_SALIDA = CARPETA_BASE / "outputs"
CARPETA_LOGS = Path(os.environ.get("SNEAKER_LOGS", CARPETA_BASE / "logs"))

# Los 5 CSV que exporta Acceso a Datos
ARCHIVOS = {
    "clientes": "clientes.csv",
    "modelos": "modelos.csv",
    "pedidos": "pedidos.csv",
    "lineas": "lineas_pedido.csv",
    "stock": "stock.csv",
}

# Columnas que tiene que tener cada CSV; si falta alguna, no se publica nada
COLUMNAS_OBLIGATORIAS = {
    "clientes": ["id_cliente", "codigo_odoo", "nombre", "tipo_cliente", "activo"],
    "modelos": ["id_modelo", "codigo_modelo", "marca", "nombre", "categoria", "precio_base", "admite_custom", "activo"],
    "pedidos": ["id_pedido", "ref_odoo", "fecha_pedido", "id_cliente", "tipo", "estado", "importe_total"],
    "lineas": ["id_linea", "id_pedido", "id_modelo", "color", "talla", "cantidad", "precio_unitario", "subtotal_linea", "personalizada"],
    "stock": ["id_modelo", "color", "talla", "stock_disponible", "stock_minimo", "fecha_corte"],
}

# Etiquetas para distinguir datos reales de sintéticos
ORIGENES = {"real": "ACC · REAL", "sintetico": "SINTÉTICO · generador_datos.py"}
CARPETAS_ENTRADA = {"real": CARPETA_ENTRADA, "sintetico": CARPETA_SINTETICOS}

# Formato de las fechas en los CSV
FORMATO_FECHA = "%Y-%m-%d %H:%M:%S"

# Reglas de negocio: estados, tipos y tallas permitidos
ESTADOS_VALIDOS = ["BORRADOR", "CONFIRMADO", "ENTREGADO", "CANCELADO"]
# Solo estos estados cuentan como venta (ingresos, pares, ticket...)
ESTADOS_VENTA = ["CONFIRMADO", "ENTREGADO"]
TIPOS_PEDIDO = ["ESTANDAR", "CUSTOM"]
TIPOS_CLIENTE = ["CLUB", "EQUIPO", "PARTICULAR"]
TALLAS_VALIDAS = list(range(36, 47))
DIAS_SEMANA = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]

# Margen de 1 céntimo al comparar importes (por redondeos)
TOLERANCIA_IMPORTE = 0.01
# Días de demanda que se usan para calcular la cobertura de stock
DIAS_DEMANDA_RECIENTE = 28
# Cada cuántos segundos se recalcula el dashboard
SEGUNDOS_REFRESCO = 60
# Semilla fija: el azar sale siempre igual (resultados reproducibles)
SEMILLA = 42

# Parámetros del generador de datos sintéticos
SINTETICO_PEDIDOS = 900
SINTETICO_CLIENTES = 45
SINTETICO_INICIO = "2025-01-01"
SINTETICO_MESES = 18
SINTETICO_MINIMO_CUSTOM = 20
CARPETA_SINTETICOS_INCIDENCIAS = CARPETA_SINTETICOS / "con_incidencias"

# Umbrales de los segmentos RFM de clientes
RFM_DIAS_RECIENTE = 60
RFM_DIAS_RIESGO = 120
RFM_FRECUENCIA_LEAL = 2
# Mínimos para que cohortes y KMeans tengan sentido; si no, NO CALCULABLE
MINIMO_CLIENTES_COHORTES = 10
MINIMO_CLIENTES_CLUSTERING = 20
# Número de grupos que se prueban en KMeans
VALORES_K = [2, 3, 4, 5]
# Estadística: muestra mínima y regla para elegir media o mediana
MINIMO_MUESTRA_ESTADISTICA = 30
UMBRAL_ASIMETRIA = 0.10
# Regla IQR para detectar valores atípicos
FACTOR_IQR = 1.5
MINIMO_MUESTRA_IQR = 4
