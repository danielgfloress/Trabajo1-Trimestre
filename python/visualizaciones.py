from datetime import datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np

import config

SUPERFICIE = "#fcfcfb"
TEXTO = "#0b0b0b"
TEXTO_SECUNDARIO = "#52514e"
REJILLA = "#e4e3df"
SERIE_1 = "#2a78d6"
SERIE_2 = "#eb6834"
AZULES = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
COLOR_TIPO = {"CUSTOM": SERIE_1, "ESTANDAR": SERIE_2}
NOMBRE_TIPO = {"CUSTOM": "Custom", "ESTANDAR": "Estándar"}

plt.rcParams.update({
    "figure.facecolor": SUPERFICIE,
    "axes.facecolor": SUPERFICIE,
    "axes.edgecolor": REJILLA,
    "axes.labelcolor": TEXTO_SECUNDARIO,
    "axes.titlecolor": TEXTO,
    "axes.titlesize": 13,
    "axes.titleweight": "bold",
    "axes.titlelocation": "left",
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "axes.axisbelow": True,
    "grid.color": REJILLA,
    "grid.linewidth": 0.8,
    "xtick.color": TEXTO_SECUNDARIO,
    "ytick.color": TEXTO_SECUNDARIO,
    "legend.frameon": False,
    "font.size": 10,
})


def texto_filtros(filtros):
    activos = {clave: valor for clave, valor in (filtros or {}).items() if valor not in (None, [], "")}
    if not activos:
        return "sin filtros"
    return "; ".join(f"{clave}: {', '.join(map(str, valor)) if isinstance(valor, list) else valor}" for clave, valor in activos.items())


def periodo(resultados):
    fechas = resultados["pedidos_unicos"]["fecha_pedido"].dropna()
    if fechas.empty:
        return "sin pedidos"
    return f"{fechas.min():%d/%m/%Y} – {fechas.max():%d/%m/%Y}"


def nueva_figura(resultados, origen, titulo, lectura, ancho=9, alto=5.2, columnas=1, izquierda=0.1):
    fig, ejes = plt.subplots(1, columnas, figsize=(ancho, alto))
    fig.suptitle(titulo, x=0.02, ha="left", fontsize=14, fontweight="bold", color=TEXTO)
    fig.text(0.02, 0.905, lectura, ha="left", va="top", fontsize=9.5, color=TEXTO_SECUNDARIO, wrap=True)
    linaje = (f"Origen: {origen}  ·  Periodo: {periodo(resultados)}  ·  Filtros: {texto_filtros(resultados['pedidos_unicos'].attrs.get('filtros'))}"
              f"  ·  Generado: {datetime.now():%d/%m/%Y %H:%M}")
    fig.text(0.02, 0.015, linaje, ha="left", fontsize=8, color=TEXTO_SECUNDARIO)
    fig.subplots_adjust(top=0.78, bottom=0.17, left=izquierda, right=0.97, wspace=0.35)
    return fig, ejes


def sin_datos(eje):
    eje.set_axis_off()
    eje.text(0.5, 0.5, "Sin datos para los filtros aplicados", ha="center", va="center", fontsize=12, color=TEXTO_SECUNDARIO)


def formato_euros(eje, eje_xy="y"):
    formato = matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:,.0f} €".replace(",", "."))
    (eje.yaxis if eje_xy == "y" else eje.xaxis).set_major_formatter(formato)


def evolucion_mensual(resultados, origen):
    datos = resultados["ventas_por_periodo"]
    fig, eje = nueva_figura(resultados, origen, "Ingresos válidos por mes",
                            "Suma de importes de pedidos CONFIRMADOS y ENTREGADOS en cada mes. Los meses sin ventas aparecen con 0 €.")
    if datos.empty:
        sin_datos(eje)
        return fig
    eje.plot(datos["mes"], datos["ingresos"], color=SERIE_1, linewidth=2, marker="o", markersize=8,
             markeredgecolor=SUPERFICIE, markeredgewidth=2)
    ultimo = datos.iloc[-1]
    eje.annotate(f"{ultimo['ingresos']:,.0f} €".replace(",", "."), (len(datos) - 1, ultimo["ingresos"]),
                 textcoords="offset points", xytext=(0, 10), ha="center", color=TEXTO)
    if len(datos) > 8:
        eje.tick_params(axis="x", labelrotation=45)
        fig.subplots_adjust(bottom=0.24)
    eje.set_xlabel("Mes")
    eje.set_ylabel("Ingresos (€)")
    eje.set_ylim(bottom=0)
    formato_euros(eje)
    eje.grid(axis="x", visible=False)
    return fig


def ranking_modelos(resultados, origen, cuantos=10):
    datos = resultados["modelos_abc"].sort_values("pares", ascending=False).head(cuantos)
    fig, eje = nueva_figura(resultados, origen, f"Top {len(datos)} modelos por pares vendidos",
                            "Pares de pedidos válidos por modelo. La etiqueta indica los pares y la clase ABC según ingresos.", izquierda=0.32)
    if datos.empty:
        sin_datos(eje)
        return fig
    datos = datos.iloc[::-1]
    nombres = datos["codigo_modelo"] + " · " + datos["modelo"]
    barras = eje.barh(nombres, datos["pares"], color=SERIE_1, height=0.6, edgecolor=SUPERFICIE, linewidth=2)
    for barra, pares, clase in zip(barras, datos["pares"], datos["clase"]):
        eje.text(barra.get_width(), barra.get_y() + barra.get_height() / 2, f"  {pares:.0f} · {clase}", va="center", color=TEXTO)
    eje.set_xlabel("Pares vendidos")
    eje.grid(axis="y", visible=False)
    eje.margins(x=0.15)
    return fig


def pareto_modelos(resultados, origen):
    datos = resultados["modelos_abc"]
    fig, eje = nueva_figura(resultados, origen, "Concentración de ingresos por modelo (Pareto)",
                            "Barras: % de ingresos de cada modelo. Línea: % acumulado. La línea discontinua marca el 80 % (límite de la clase A).")
    if datos.empty:
        sin_datos(eje)
        return fig
    posiciones = np.arange(len(datos))
    eje.bar(posiciones, datos["peso_pct"], color=SERIE_1, width=0.7, edgecolor=SUPERFICIE, linewidth=2, label="% de ingresos del modelo")
    eje.plot(posiciones, datos["acumulado_pct"], color=TEXTO, linewidth=2, marker="o", markersize=8,
             markeredgecolor=SUPERFICIE, markeredgewidth=2, label="% acumulado")
    eje.axhline(80, color=TEXTO_SECUNDARIO, linestyle="--", linewidth=1)
    eje.set_xticks(posiciones, datos["codigo_modelo"], rotation=45, ha="right")
    eje.set_ylabel("% de los ingresos válidos")
    eje.set_ylim(0, 105)
    eje.grid(axis="x", visible=False)
    eje.legend(loc="center right")
    return fig


def histograma_importes(resultados, origen):
    pedidos = resultados["pedidos_unicos"]
    importes = pedidos.loc[pedidos["es_venta"], "importe"]
    fig, eje = nueva_figura(resultados, origen, "Distribución del importe por pedido",
                            f"Nº de pedidos válidos en cada tramo de importe (n = {len(importes)}). La línea marca la mediana.")
    if importes.empty:
        sin_datos(eje)
        return fig
    eje.hist(importes, bins="auto", color=SERIE_1, edgecolor=SUPERFICIE, linewidth=2)
    mediana = importes.median()
    eje.axvline(mediana, color=TEXTO, linestyle="--", linewidth=1.5)
    eje.text(mediana, eje.get_ylim()[1] * 0.95, f"  mediana {mediana:,.0f} €".replace(",", "."), color=TEXTO, va="top")
    eje.set_xlabel("Importe del pedido (€)")
    eje.set_ylabel("Nº de pedidos")
    eje.yaxis.set_major_locator(matplotlib.ticker.MaxNLocator(integer=True))
    formato_euros(eje, "x")
    eje.grid(axis="x", visible=False)
    return fig


def boxplot_por_tipo(resultados, origen):
    pedidos = resultados["pedidos_unicos"]
    ventas = pedidos[pedidos["es_venta"]]
    tipos = [t for t in config.TIPOS_PEDIDO if (ventas["tipo"] == t).any()]
    fig, eje = nueva_figura(resultados, origen, "Importe por pedido: Custom frente a Estándar",
                            "Caja: del percentil 25 al 75. Línea: mediana. Puntos: cada pedido válido. Con pocos pedidos, la caja es orientativa.")
    if not tipos:
        sin_datos(eje)
        return fig
    grupos = [ventas.loc[ventas["tipo"] == t, "importe"] for t in tipos]
    cajas = eje.boxplot(grupos, patch_artist=True, widths=0.5, showfliers=False, medianprops={"color": TEXTO, "linewidth": 2})
    for caja, tipo in zip(cajas["boxes"], tipos):
        caja.set_facecolor(COLOR_TIPO[tipo])
        caja.set_alpha(0.35)
        caja.set_edgecolor(COLOR_TIPO[tipo])
    generador = np.random.default_rng(config.SEMILLA)
    for posicion, (grupo, tipo) in enumerate(zip(grupos, tipos), start=1):
        muchos = len(grupo) > 50
        x = posicion + generador.uniform(-0.18, 0.18, len(grupo)) if muchos else np.full(len(grupo), posicion)
        eje.scatter(x, grupo, color=COLOR_TIPO[tipo], s=12 if muchos else 50, alpha=0.5 if muchos else 1, zorder=3,
                    edgecolor=SUPERFICIE, linewidth=0.5 if muchos else 1.5)
    eje.set_xticks(range(1, len(tipos) + 1), [f"{NOMBRE_TIPO[t]} (n = {len(g)})" for t, g in zip(tipos, grupos)])
    eje.set_ylabel("Importe del pedido (€)")
    formato_euros(eje)
    eje.grid(axis="x", visible=False)
    return fig


def mapa_calor_modelo_talla(resultados, origen):
    datos = resultados["matriz_modelo_talla"]
    fig, eje = nueva_figura(resultados, origen, "Pares vendidos por modelo y talla",
                            "Cada celda es el nº de pares vendidos de ese modelo en esa talla. Más oscuro = más pares.", alto=6, izquierda=0.32)
    if datos.empty:
        sin_datos(eje)
        return fig
    mapa = matplotlib.colors.LinearSegmentedColormap.from_list("azules", AZULES)
    imagen = eje.imshow(datos.values, cmap=mapa, aspect="auto")
    eje.set_xticks(range(len(datos.columns)), datos.columns)
    eje.set_yticks(range(len(datos.index)), [f"{codigo} · {modelo}" for codigo, modelo in datos.index])
    maximo = datos.values.max()
    for fila in range(datos.shape[0]):
        for columna in range(datos.shape[1]):
            valor = datos.iat[fila, columna]
            if valor:
                eje.text(columna, fila, f"{valor:.0f}", ha="center", va="center",
                         color=SUPERFICIE if valor > maximo * 0.55 else TEXTO, fontsize=9)
    eje.set_xlabel("Talla (EU)")
    eje.grid(False)
    barra = fig.colorbar(imagen, ax=eje, fraction=0.03)
    barra.set_label("Pares")
    return fig


def dispersion_clientes(resultados, origen):
    datos = resultados["clientes_rfm"]
    datos = datos[datos["frecuencia"] > 0]
    rotulados = len(datos) if len(datos) <= 8 else 3
    fig, eje = nueva_figura(resultados, origen, "Clientes: días sin comprar frente a gasto",
                            "Cada punto es un cliente con compras válidas. Derecha = lleva más tiempo sin comprar; arriba = ha gastado más. "
                            f"Se rotulan los {rotulados} de mayor gasto.", izquierda=0.13)
    if datos.empty:
        sin_datos(eje)
        return fig
    eje.scatter(datos["recencia_dias"], datos["monetario"], s=60, color=SERIE_1, alpha=0.8,
                edgecolor=SUPERFICIE, linewidth=1.5, zorder=3)
    for _, fila in datos.nlargest(rotulados, "monetario").iterrows():
        eje.annotate(f"{fila['codigo_odoo']} ({fila['frecuencia']} ped.)", (fila["recencia_dias"], fila["monetario"]),
                     textcoords="offset points", xytext=(8, 6), color=TEXTO, fontsize=9)
    eje.set_xlabel("Días desde la última compra (recencia)")
    eje.set_ylabel("Gasto en ventas válidas (€)")
    eje.set_ylim(bottom=0)
    eje.set_xlim(0, datos["recencia_dias"].max() * 1.2)
    formato_euros(eje)
    return fig


def comparativa_tipo(resultados, origen):
    datos = resultados["custom_vs_estandar"]
    fig, ejes = nueva_figura(resultados, origen, "Custom frente a Estándar",
                             "Tres medidas distintas, cada una con su escala: pedidos válidos, pares vendidos e ingresos válidos.",
                             ancho=11, columnas=3)
    if datos.empty:
        for eje in ejes:
            sin_datos(eje)
        return fig
    nombres = [NOMBRE_TIPO.get(t, t) for t in datos["tipo"]]
    colores = [COLOR_TIPO.get(t, SERIE_1) for t in datos["tipo"]]
    paneles = [("pedidos_venta", "Pedidos válidos", "{:.0f}"), ("pares_vendidos", "Pares vendidos", "{:.0f}"),
               ("ingresos", "Ingresos válidos (€)", "{:,.0f} €")]
    for eje, (columna, titulo, formato) in zip(ejes, paneles):
        barras = eje.bar(nombres, datos[columna], color=colores, width=0.6, edgecolor=SUPERFICIE, linewidth=2)
        for barra, valor in zip(barras, datos[columna]):
            eje.text(barra.get_x() + barra.get_width() / 2, barra.get_height(), formato.format(valor).replace(",", "."),
                     ha="center", va="bottom", color=TEXTO)
        eje.set_title(titulo, fontsize=11)
        eje.yaxis.set_major_locator(matplotlib.ticker.MaxNLocator(integer=True))
        eje.grid(axis="x", visible=False)
        eje.margins(y=0.15)
    formato_euros(ejes[2])
    return fig


def grupos_clientes(resultados, origen):
    perfil = resultados["clustering_perfil"]
    calculable = "cluster" in perfil.columns
    columnas = len(perfil) if calculable else 1
    fig, ejes = nueva_figura(resultados, origen, "Grupos de clientes (KMeans)",
                             "Cada panel resalta en azul un grupo; en gris, el resto de clientes. "
                             "Grupos hechos con recencia, frecuencia y gasto escalados.",
                             ancho=max(9, 4.2 * columnas), columnas=columnas, izquierda=0.11)
    ejes = np.atleast_1d(ejes)
    if not calculable:
        ejes[0].set_axis_off()
        ejes[0].text(0.5, 0.5, "NO CALCULABLE\n" + perfil["motivo"].iloc[0], ha="center", va="center",
                     fontsize=10, color=TEXTO_SECUNDARIO, wrap=True)
        return fig
    clientes = resultados["clustering_clientes"]
    for eje, (_, grupo) in zip(ejes, perfil.iterrows()):
        dentro = clientes["cluster"] == grupo["cluster"]
        eje.scatter(clientes.loc[~dentro, "recencia_dias"], clientes.loc[~dentro, "monetario"], s=30, color=REJILLA, zorder=2)
        eje.scatter(clientes.loc[dentro, "recencia_dias"], clientes.loc[dentro, "monetario"], s=45, color=SERIE_1,
                    edgecolor=SUPERFICIE, linewidth=1.5, zorder=3)
        eje.set_title(f"{grupo['nombre_grupo']}\n{grupo['clientes']} clientes · {grupo['porcentaje_ingresos']:.0f} % de ingresos", fontsize=10)
        eje.set_xlabel("Días sin comprar")
        eje.set_ylim(0, clientes["monetario"].max() * 1.05)
        formato_euros(eje)
    ejes[0].set_ylabel("Gasto en ventas válidas (€)")
    return fig


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
}


def todas_las_figuras(resultados, origen):
    return {nombre: funcion(resultados, origen) for nombre, funcion in FIGURAS.items()}


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
