from datetime import datetime

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

import analiticas
import config
import pipeline
import visualizaciones as vis

ORIGEN = config.ORIGENES["real"]
VISTAS = ["Dirección", "Producto y ventas", "Clientes", "Almacén", "Calidad y auditoría", "Laboratorio (sintético)"]
CLAVES_FILTRO = ["f_fechas", "f_modelos", "f_tallas", "f_tipos", "f_estados", "f_clientes"]
NOMBRE_ESTADO = {"BORRADOR": "Borrador", "CONFIRMADO": "Confirmado", "ENTREGADO": "Entregado", "CANCELADO": "Cancelado"}
PLURAL_ESTADO = {"BORRADOR": "Borradores", "CONFIRMADO": "Confirmados", "ENTREGADO": "Entregados", "CANCELADO": "Cancelados"}

st.set_page_config(page_title="Sneaker Factory · Dashboard", layout="wide")


def restablecer_filtros():
    for clave in CLAVES_FILTRO:
        st.session_state.pop(clave, None)


def barra_lateral(tablas):
    pedidos = tablas["pedidos"]
    modelos = tablas["modelos"]
    vendidos = modelos[modelos["id_modelo"].isin(tablas["lineas"]["id_modelo"])]
    etiquetas_modelo = dict(zip(vendidos["codigo_modelo"], vendidos["codigo_modelo"] + " · " + vendidos["nombre"]))
    primero = pedidos["fecha_pedido"].min().date()
    ultimo = pedidos["fecha_pedido"].max().date()

    with st.sidebar:
        st.header("Filtros")
        fechas = st.date_input("Periodo", value=(primero, ultimo), min_value=primero, max_value=ultimo,
                               format="DD/MM/YYYY", key="f_fechas")
        st.multiselect("Modelo", list(etiquetas_modelo), format_func=etiquetas_modelo.get, placeholder="Todos", key="f_modelos")
        st.multiselect("Talla", sorted(int(t) for t in tablas["lineas"]["talla"].unique()), placeholder="Todas", key="f_tallas")
        st.multiselect("Tipo de pedido", config.TIPOS_PEDIDO, format_func=vis.NOMBRE_TIPO.get, placeholder="Todos", key="f_tipos")
        st.multiselect("Estado", config.ESTADOS_VALIDOS, format_func=NOMBRE_ESTADO.get, placeholder="Todos", key="f_estados")
        st.multiselect("Cliente", sorted(tablas["clientes"]["codigo_odoo"]), placeholder="Todos", key="f_clientes")
        st.button("Restablecer filtros", on_click=restablecer_filtros, width="stretch")
        st.caption("Un filtro vacío no restringe nada. Los filtros de modelo y talla dejan solo las líneas de ese modelo "
                   "o talla, así que los importes y pares de cada pedido se reducen a esas líneas.")

    filtros = {}
    if isinstance(fechas, tuple) and len(fechas) == 2 and (fechas[0] > primero or fechas[1] < ultimo):
        filtros["desde"], filtros["hasta"] = str(fechas[0]), str(fechas[1])
    for clave, nombre in [("f_modelos", "modelos"), ("f_tallas", "tallas"), ("f_tipos", "tipos"),
                          ("f_estados", "estados"), ("f_clientes", "clientes")]:
        if st.session_state.get(clave):
            filtros[nombre] = list(st.session_state[clave])
    return filtros


def mostrar_figura(figura, tabla=None, titulo_tabla="Ver los datos del gráfico"):
    st.pyplot(figura, clear_figure=True)
    plt.close(figura)
    if tabla is not None:
        with st.expander(titulo_tabla):
            st.dataframe(tabla, width="stretch", hide_index=True)


def valor_kpi(resultados, indicador):
    kpis = resultados["kpis"].set_index("indicador")["valor"]
    return pd.to_numeric(kpis.get(indicador), errors="coerce")


def variacion(valor):
    return None if pd.isna(valor) else f"{valor:+.1f} % frente al mes anterior"


def cabecera(resultado, resultados, segundos):
    corte = resultado["tablas"]["stock"]["fecha_corte"].max()
    filas = int(resultado["resumen_calidad"]["filas_validas"].sum())
    st.title("Sneaker Factory · Dashboard")
    columnas = st.columns(5)
    columnas[0].metric("Procedencia", ORIGEN)
    columnas[1].metric("Fecha de corte (ACC)", f"{corte:%d/%m/%Y %H:%M}")
    columnas[2].metric("Última comprobación", f"{resultado['hora_comprobacion']:%H:%M:%S}")
    columnas[3].metric("Filas válidas", f"{filas:,}".replace(",", "."))
    columnas[4].metric("Estado", resultado["estado"])
    st.caption(f"Recalculado en {resultado['segundos'] + segundos:.1f} s · Filtros: "
               f"{vis.texto_filtros(resultados['pedidos_unicos'].attrs.get('filtros'))}")


def vista_direccion(resultados):
    pedidos = resultados["pedidos_unicos"]
    ventas = pedidos[pedidos["es_venta"]]
    st.subheader("Totales del periodo filtrado")
    columnas = st.columns(4)
    columnas[0].metric("Ingresos válidos", vis.euros(valor_kpi(resultados, "Ingresos válidos")))
    columnas[1].metric("Pares vendidos", f"{valor_kpi(resultados, 'Pares vendidos'):.0f}")
    columnas[2].metric("Pedidos válidos", f"{valor_kpi(resultados, 'Pedidos válidos (venta)'):.0f}")
    columnas[3].metric("Ticket medio", vis.euros(valor_kpi(resultados, "Ticket medio")))
    st.caption(f"Ventas válidas = pedidos CONFIRMADOS y ENTREGADOS: {len(ventas)} de {len(pedidos)} pedidos del subconjunto. "
               "El ticket medio divide entre pedidos, no entre líneas.")

    meses = resultados["ventas_por_periodo"]
    if len(meses) >= 2:
        ultimo = meses.iloc[-1]
        st.subheader(f"Último mes ({ultimo['mes']}) frente al anterior")
        columnas = st.columns(4)
        columnas[0].metric("Ingresos del mes", vis.euros(ultimo["ingresos"]), variacion(ultimo["variacion_ingresos_pct"]))
        columnas[1].metric("Pares del mes", f"{ultimo['pares']:.0f}", variacion(ultimo["variacion_pares_pct"]))
        columnas[2].metric("Pedidos del mes", f"{ultimo['pedidos']:.0f}", variacion(ultimo["variacion_pedidos_pct"]))
        columnas[3].metric("Ticket del mes", vis.euros(ultimo["ticket_medio"]), variacion(ultimo["variacion_ticket_medio_pct"]))
    else:
        st.info("Hay menos de dos meses con ventas en el subconjunto: no hay periodo anterior con el que comparar.")

    st.subheader("Actividad por estado y peso de Custom")
    estados = pedidos["estado"].value_counts()
    columnas = st.columns(7)
    for columna, estado in zip(columnas, config.ESTADOS_VALIDOS):
        columna.metric(PLURAL_ESTADO[estado], int(estados.get(estado, 0)))
    columnas[4].metric("Custom en pedidos", f"{valor_kpi(resultados, 'Peso Custom en pedidos'):.1f} %")
    columnas[5].metric("Custom en pares", f"{valor_kpi(resultados, 'Peso Custom en pares'):.1f} %")
    columnas[6].metric("Custom en ingresos", f"{valor_kpi(resultados, 'Peso Custom en ingresos'):.1f} %")

    mostrar_figura(vis.evolucion_mensual(resultados, ORIGEN), meses)
    with st.expander("Todos los indicadores con su fórmula y denominador"):
        st.dataframe(resultados["kpis"], width="stretch", hide_index=True)


def vista_producto(resultados):
    izquierda, derecha = st.columns(2)
    with izquierda:
        mostrar_figura(vis.ranking_modelos(resultados, ORIGEN), resultados["modelos_abc"])
    with derecha:
        mostrar_figura(vis.pareto_modelos(resultados, ORIGEN), resultados["modelos_abc"])
    st.caption("Clase ABC: A = modelos que suman el primer 80 % de los ingresos, B = hasta el 95 %, C = el resto. "
               "Los A son los que conviene tener siempre fabricados.")

    mostrar_figura(vis.mapa_calor_modelo_talla(resultados, ORIGEN), resultados["matriz_modelo_talla_pct"].reset_index().rename(columns=str),
                   "Ver el % de cada talla dentro de su modelo")
    with st.expander("Talla más pedida de cada modelo"):
        st.dataframe(resultados["talla_mas_solicitada"], width="stretch", hide_index=True)

    izquierda, derecha = st.columns(2)
    with izquierda:
        mostrar_figura(vis.comparativa_tipo(resultados, ORIGEN), resultados["custom_vs_estandar"])
    with derecha:
        mostrar_figura(vis.boxplot_por_tipo(resultados, ORIGEN), resultados["estadistica_por_grupo"])
    st.caption("La tasa de cancelación se mide sobre pedidos; la cuota de ingresos, sobre euros. Son cosas distintas.")


def vista_pendiente(nombre):
    st.info(f"La vista «{nombre}» se añade en el siguiente paso.")


resultado_inicial = pipeline.ejecutar_pipeline(config.CARPETA_ENTRADA, ORIGEN)
if not resultado_inicial["publicable"]:
    st.error("Los CSV de entrada_acc/ no son válidos ahora mismo. Revisa la vista de calidad o vuelve a exportar desde ACC.")
    st.dataframe(resultado_inicial["incidencias"], width="stretch", hide_index=True)
    st.stop()

filtros = barra_lateral(resultado_inicial["tablas"])
vista = st.radio("Vista", VISTAS, horizontal=True, key="vista", label_visibility="collapsed")


@st.fragment(run_every=f"{config.SEGUNDOS_REFRESCO}s")
def panel(filtros, vista):
    resultado = pipeline.ejecutar_pipeline(config.CARPETA_ENTRADA, ORIGEN)
    inicio = datetime.now()
    resultados = analiticas.calcular_todo(resultado, filtros)
    cabecera(resultado, resultados, (datetime.now() - inicio).total_seconds())
    if vista == "Dirección":
        vista_direccion(resultados)
    elif vista == "Producto y ventas":
        vista_producto(resultados)
    else:
        vista_pendiente(vista)


panel(filtros, vista)
