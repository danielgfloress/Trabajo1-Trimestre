# Gráficos con Matplotlib. Cada función recibe los resultados de analiticas.py y devuelve una figura.
# Los usan main.py (para guardar los PNG) y el dashboard (para enseñarlos en pantalla).
from datetime import datetime
from pathlib import Path

import matplotlib

# Modo sin ventana: los gráficos se dibujan en memoria (para guardarlos en PNG o enseñarlos en Streamlit)
matplotlib.use("Agg")

import matplotlib.pyplot as plt

# Nombre que se enseña de cada tipo de pedido
NOMBRE_TIPO = {"CUSTOM": "Custom", "ESTANDAR": "Estándar"}


# Formatea un número como euros al estilo español: 1234.5 → "1.234,50 €"
def euros(valor, decimales=2):
    if valor is None or valor != valor:  # valor != valor solo es cierto cuando el valor es NaN (vacío)
        return "—"
    texto = f"{valor:,.{decimales}f}"  # formato inglés: 1,234.50
    texto = texto.replace(",", "_").replace(".", ",").replace("_", ".")  # se cambian comas por puntos y al revés
    return texto + " €"


# Convierte el diccionario de filtros en texto, por ejemplo "tallas: 41, 42; tipos: CUSTOM"
def texto_filtros(filtros):
    if not filtros:
        return "sin filtros"
    partes = []
    for clave, valor in filtros.items():
        if valor is None or valor == [] or valor == "":
            continue
        if isinstance(valor, list):
            valor = ", ".join(str(v) for v in valor)
        partes.append(f"{clave}: {valor}")
    if not partes:
        return "sin filtros"
    return "; ".join(partes)


# Texto con la primera y la última fecha de los pedidos
def periodo(resultados):
    fechas = resultados["pedidos_unicos"]["fecha_pedido"].dropna()
    if fechas.empty:
        return "sin pedidos"
    return f"{fechas.min():%d/%m/%Y} – {fechas.max():%d/%m/%Y}"


# Crea una figura con su título, una frase de cómo leerla y, abajo, el origen, el periodo y los filtros.
# izquierda = margen izquierdo (más grande en las barras horizontales, para que quepan los nombres)
def nueva_figura(resultados, origen, titulo, lectura, columnas=1, izquierda=0.1):
    fig, ejes = plt.subplots(1, columnas, figsize=(10, 5.5))
    fig.suptitle(titulo, fontsize=14, fontweight="bold")
    fig.text(0.5, 0.90, lectura, ha="center", fontsize=9)
    filtros = resultados["pedidos_unicos"].attrs.get("filtros")
    pie = f"Origen: {origen}  ·  Periodo: {periodo(resultados)}  ·  Filtros: {texto_filtros(filtros)}  ·  Generado: {datetime.now():%d/%m/%Y %H:%M}"
    fig.text(0.01, 0.01, pie, fontsize=8)
    fig.subplots_adjust(top=0.82, bottom=0.2, left=izquierda)
    return fig, ejes


# Mensaje en el centro cuando no hay datos que dibujar
def sin_datos(eje, mensaje="Sin datos para los filtros aplicados"):
    eje.set_axis_off()
    eje.text(0.5, 0.5, mensaje, ha="center", va="center", fontsize=11, wrap=True)


# Gráfico 1: línea con los ingresos de cada mes
def evolucion_mensual(resultados, origen):
    datos = resultados["ventas_por_periodo"]
    fig, eje = nueva_figura(resultados, origen, "Ingresos válidos por mes",
                            "Suma de importes de pedidos CONFIRMADOS y ENTREGADOS de cada mes. Los meses sin ventas salen con 0 €.")
    if datos.empty:
        sin_datos(eje)
        return fig
    eje.plot(datos["mes"], datos["ingresos"], marker="o", label="Ingresos (€)")
    eje.set_xlabel("Mes")
    eje.set_ylabel("Ingresos (€)")
    eje.set_ylim(bottom=0)
    eje.tick_params(axis="x", labelrotation=45)
    eje.legend()
    eje.grid(True)
    return fig


# Gráfico 2: barras con los modelos que más pares venden
def ranking_modelos(resultados, origen, cuantos=10):
    datos = resultados["modelos_abc"].sort_values("pares", ascending=False).head(cuantos)
    fig, eje = nueva_figura(resultados, origen, f"Top {len(datos)} modelos por pares vendidos",
                            "Pares de pedidos válidos por modelo. Entre paréntesis, su clase ABC según ingresos.", izquierda=0.2)
    if datos.empty:
        sin_datos(eje)
        return fig
    # Se da la vuelta para que el primero salga arriba
    datos = datos.iloc[::-1]
    nombres = datos["codigo_modelo"] + " (" + datos["clase"].astype(str) + ")"
    eje.barh(nombres, datos["pares"], label="Pares vendidos")
    eje.set_xlabel("Pares vendidos")
    eje.set_ylabel("Modelo")
    eje.legend()
    return fig


# Gráfico 3: Pareto. Barras: % de ingresos de cada modelo. Línea: % acumulado
def pareto_modelos(resultados, origen):
    datos = resultados["modelos_abc"]
    fig, eje = nueva_figura(resultados, origen, "Concentración de ingresos por modelo (Pareto)",
                            "Barras: % de ingresos de cada modelo. Línea: % acumulado. La línea discontinua marca el 80 % (clase A).")
    if datos.empty:
        sin_datos(eje)
        return fig
    eje.bar(datos["codigo_modelo"], datos["peso_pct"], label="% de ingresos del modelo")
    eje.plot(datos["codigo_modelo"], datos["acumulado_pct"], marker="o", color="black", label="% acumulado")
    eje.axhline(80, linestyle="--", color="gray")
    eje.set_xlabel("Modelo")
    eje.set_ylabel("% de los ingresos válidos")
    eje.set_ylim(0, 105)
    eje.tick_params(axis="x", labelrotation=45)
    eje.legend()
    return fig


# Gráfico 4: histograma (distribución) del importe de cada pedido
def histograma_importes(resultados, origen):
    pedidos = resultados["pedidos_unicos"]
    importes = pedidos.loc[pedidos["es_venta"], "importe"]
    fig, eje = nueva_figura(resultados, origen, "Distribución del importe por pedido",
                            f"Nº de pedidos válidos en cada tramo de importe (n = {len(importes)}). La línea discontinua es la mediana.")
    if importes.empty:
        sin_datos(eje)
        return fig
    eje.hist(importes, bins="auto", edgecolor="white", label="Pedidos")
    eje.axvline(importes.median(), linestyle="--", color="black", label=f"Mediana: {euros(importes.median(), 0)}")
    eje.set_xlabel("Importe del pedido (€)")
    eje.set_ylabel("Nº de pedidos")
    eje.legend()
    return fig


# Gráfico 5: boxplot del importe por pedido, Custom frente a estándar
def boxplot_por_tipo(resultados, origen):
    pedidos = resultados["pedidos_unicos"]
    ventas = pedidos[pedidos["es_venta"]]
    fig, eje = nueva_figura(resultados, origen, "Importe por pedido: Custom frente a Estándar",
                            "Caja: del percentil 25 al 75. Línea de dentro: mediana. Con pocos pedidos, la caja es orientativa.")
    # Un grupo de importes por cada tipo que tenga ventas
    grupos = []
    nombres = []
    for tipo in ["ESTANDAR", "CUSTOM"]:
        importes = ventas.loc[ventas["tipo"] == tipo, "importe"]
        if len(importes):
            grupos.append(importes)
            nombres.append(f"{NOMBRE_TIPO[tipo]} (n = {len(importes)})")
    if not grupos:
        sin_datos(eje)
        return fig
    eje.boxplot(grupos)
    eje.set_xticks(range(1, len(nombres) + 1), nombres)
    eje.set_xlabel("Tipo de pedido")
    eje.set_ylabel("Importe del pedido (€)")
    return fig


# Gráfico 6: mapa de calor con los pares vendidos de cada modelo en cada talla
def mapa_calor_modelo_talla(resultados, origen):
    datos = resultados["matriz_modelo_talla"]
    fig, eje = nueva_figura(resultados, origen, "Pares vendidos por modelo y talla",
                            "Cada celda es el nº de pares vendidos de ese modelo en esa talla. Más oscuro = más pares.")
    if datos.empty:
        sin_datos(eje)
        return fig
    imagen = eje.imshow(datos.values, cmap="Blues", aspect="auto")
    eje.set_xticks(range(len(datos.columns)), datos.columns)
    # El índice de la tabla es (código, nombre del modelo): se enseña solo el código
    codigos = []
    for codigo, modelo in datos.index:
        codigos.append(codigo)
    eje.set_yticks(range(len(codigos)), codigos)
    # Se escribe el número dentro de cada celda que tiene ventas
    for fila in range(datos.shape[0]):
        for columna in range(datos.shape[1]):
            valor = datos.iat[fila, columna]
            if valor > 0:
                eje.text(columna, fila, int(valor), ha="center", va="center")
    eje.set_xlabel("Talla (EU)")
    eje.set_ylabel("Modelo")
    fig.colorbar(imagen, ax=eje, label="Pares")
    return fig


# Gráfico 7: dispersión de clientes. Cada punto es un cliente: días sin comprar frente a gasto
def dispersion_clientes(resultados, origen):
    datos = resultados["clientes_rfm"]
    datos = datos[datos["frecuencia"] > 0]
    fig, eje = nueva_figura(resultados, origen, "Clientes: días sin comprar frente a gasto",
                            "Cada punto es un cliente con compras válidas. Derecha = lleva más tiempo sin comprar; arriba = ha gastado más.")
    if datos.empty:
        sin_datos(eje)
        return fig
    eje.scatter(datos["recencia_dias"], datos["monetario"], label="Cliente")
    # Se escribe el código de los 8 que más gastan
    for _, fila in datos.nlargest(8, "monetario").iterrows():
        eje.annotate(fila["codigo_odoo"], (fila["recencia_dias"], fila["monetario"]))
    eje.set_xlabel("Días desde la última compra (recencia)")
    eje.set_ylabel("Gasto en ventas válidas (€)")
    eje.legend()
    return fig


# Gráfico 8: comparativa Custom frente a estándar en pedidos, pares e ingresos (3 gráficos pequeños)
def comparativa_tipo(resultados, origen):
    datos = resultados["custom_vs_estandar"]
    fig, ejes = nueva_figura(resultados, origen, "Custom frente a Estándar",
                             "Tres medidas distintas, cada una con su escala: pedidos válidos, pares vendidos e ingresos válidos.",
                             columnas=3)
    if datos.empty:
        for eje in ejes:
            sin_datos(eje)
        return fig
    nombres = []
    for tipo in datos["tipo"]:
        nombres.append(NOMBRE_TIPO.get(tipo, tipo))
    ejes[0].bar(nombres, datos["pedidos_venta"])
    ejes[0].set_title("Pedidos válidos")
    ejes[1].bar(nombres, datos["pares_vendidos"])
    ejes[1].set_title("Pares vendidos")
    ejes[2].bar(nombres, datos["ingresos"])
    ejes[2].set_title("Ingresos válidos (€)")
    return fig


# Gráfico 9: los grupos de clientes de KMeans (un color por grupo)
def grupos_clientes(resultados, origen):
    perfil = resultados["clustering_perfil"]
    fig, eje = nueva_figura(resultados, origen, "Grupos de clientes (KMeans)",
                            "Cada punto es un cliente y cada color, un grupo. Grupos hechos con recencia, frecuencia y gasto.")
    # Con pocos clientes, el KMeans es NO CALCULABLE y la tabla trae el motivo
    if "cluster" not in perfil.columns:
        sin_datos(eje, "NO CALCULABLE\n" + perfil["motivo"].iloc[0])
        return fig
    clientes = resultados["clustering_clientes"]
    for _, grupo in perfil.iterrows():
        del_grupo = clientes[clientes["cluster"] == grupo["cluster"]]
        eje.scatter(del_grupo["recencia_dias"], del_grupo["monetario"],
                    label=f"{grupo['nombre_grupo']} ({grupo['clientes']} clientes)")
    eje.set_xlabel("Días sin comprar")
    eje.set_ylabel("Gasto en ventas válidas (€)")
    eje.legend()
    return fig


# Gráfico 10: las variantes (modelo-color-talla) con stock bajo
def alertas_stock(resultados, origen, cuantas=15):
    stock = resultados["stock_cobertura"]
    alertas = stock[stock["alerta_stock_bajo"]].sort_values("stock_disponible").head(cuantas)
    titulo = "Variantes con stock bajo"
    if len(stock):
        titulo += f" (foto del {stock['fecha_corte'].max():%d/%m/%Y})"
    fig, eje = nueva_figura(resultados, origen, titulo,
                            f"Pares disponibles de las {cuantas} variantes más bajas en alerta (stock ≤ umbral). "
                            "Es una foto en la fecha de corte, no un histórico.", izquierda=0.3)
    if alertas.empty:
        sin_datos(eje, "Ninguna variante está por debajo del umbral")
        return fig
    alertas = alertas.iloc[::-1]
    nombres = alertas["codigo_modelo"] + " · " + alertas["color"] + " · T" + alertas["talla"].astype(int).astype(str)
    eje.barh(nombres, alertas["stock_disponible"], color="tab:orange", label="Pares disponibles")
    eje.set_xlabel("Pares disponibles")
    eje.legend()
    return fig


# Lista de gráficos: nombre del PNG → función que lo dibuja
FIGURAS = {
    "01_evolucion_mensual": evolucion_mensual,
    "02_ranking_modelos": ranking_modelos,
    "03_pareto_modelos": pareto_modelos,
    "04_histograma_importes": histograma_importes,
    "05_boxplot_por_tipo": boxplot_por_tipo,
    "06_mapa_calor_modelo_talla": mapa_calor_modelo_talla,
    "07_dispersion_clientes": dispersion_clientes,
    "08_comparativa_tipo": comparativa_tipo,
    "09_grupos_clientes": grupos_clientes,
    "10_alertas_stock": alertas_stock,
}


# Dibuja todos los gráficos y los devuelve en un diccionario
def todas_las_figuras(resultados, origen):
    figuras = {}
    for nombre, funcion in FIGURAS.items():
        figuras[nombre] = funcion(resultados, origen)
    return figuras


# Guarda cada gráfico como PNG en la carpeta indicada
def guardar_figuras(figuras, carpeta):
    carpeta = Path(carpeta)
    carpeta.mkdir(parents=True, exist_ok=True)
    rutas = []
    for nombre, figura in figuras.items():
        ruta = carpeta / f"{nombre}.png"
        figura.savefig(ruta, dpi=150)
        plt.close(figura)
        rutas.append(ruta)
    return rutas
