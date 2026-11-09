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
CLAVES_FILTRO = ["f_fechas", "f_modelos", "f_tallas", "f_tipos", "f_estados", "f_clientes", "f_umbral", "f_segmento", "f_gravedad"]
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
        st.number_input("Umbral de alerta de stock (pares)", min_value=0, value=None, step=1,
                        placeholder="Stock mínimo de ACC", key="f_umbral")
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
    if st.session_state.get("f_umbral") is not None:
        filtros["umbral_stock"] = int(st.session_state["f_umbral"])
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


def vista_clientes(resultados):
    rfm = resultados["clientes_rfm"].drop(columns="nombre")
    compradores = rfm[rfm["frecuencia"] > 0]
    st.subheader("Segmentos RFM")
    segmentos = rfm["segmento"].value_counts()
    for columna, (segmento, cuantos) in zip(st.columns(len(segmentos)), segmentos.items()):
        columna.metric(segmento, int(cuantos))
    st.caption(f"Reglas: «Sin compras válidas» = ningún pedido confirmado o entregado · «En riesgo» = más de "
               f"{config.RFM_DIAS_RIESGO} días sin comprar · «Campeón» = {config.RFM_FRECUENCIA_LEAL} compras o más y "
               f"como mucho {config.RFM_DIAS_RECIENTE} días sin comprar · «Leal» = {config.RFM_FRECUENCIA_LEAL} compras o más · "
               f"«Nuevo / reciente» = 1 compra en los últimos {config.RFM_DIAS_RECIENTE} días · «Ocasional» = el resto. "
               "La frecuencia cuenta pedidos, no líneas.")
    elegidos = st.multiselect("Mostrar segmentos", list(segmentos.index), placeholder="Todos", key="f_segmento")
    st.dataframe(rfm[rfm["segmento"].isin(elegidos)] if elegidos else rfm, width="stretch", hide_index=True)
    mostrar_figura(vis.dispersion_clientes(resultados, ORIGEN), compradores)

    st.subheader("Retención por cohortes")
    cohortes = resultados["cohortes"]
    if cohortes.attrs.get("aviso"):
        st.warning(cohortes.attrs["aviso"])
    st.caption("Cada fila es el mes de la primera compra; mes_1, mes_2… = % de esos clientes que vuelven a comprar "
               "1, 2… meses después.")
    st.dataframe(cohortes.reset_index().rename(columns=str), width="stretch", hide_index=True)

    st.subheader("Agrupación automática (KMeans)")
    perfil = resultados["clustering_perfil"]
    if "estado" in perfil.columns:
        st.info(perfil["motivo"].iloc[0] + " Ver la vista «Laboratorio (sintético)».")
    else:
        mostrar_figura(vis.grupos_clientes(resultados, ORIGEN), perfil)
    with st.expander("Variables de comportamiento por cliente"):
        st.dataframe(resultados["caracteristicas_clientes"], width="stretch", hide_index=True)


def vista_almacen(resultados):
    stock = resultados["stock_cobertura"]
    aviso = stock.attrs["aviso"]
    if len(stock):
        aviso += f" Fecha de corte: {stock['fecha_corte'].max():%d/%m/%Y %H:%M}."
    st.warning(aviso)
    alertas = stock[stock["alerta_stock_bajo"]]
    columnas = st.columns(5)
    columnas[0].metric("Variantes (modelo-color-talla)", len(stock))
    columnas[1].metric("En alerta", len(alertas))
    columnas[2].metric("Pares en almacén", int(stock["stock_disponible"].sum()))
    columnas[3].metric(f"Pares pedidos en {config.DIAS_DEMANDA_RECIENTE} días", int(stock["demanda_28_dias"].sum()))
    columnas[4].metric("Variantes sin demanda reciente", int(stock["cobertura_semanas"].isna().sum()))
    umbral = resultados["pedidos_unicos"].attrs.get("filtros", {}).get("umbral_stock")
    texto_umbral = ("Umbral de alerta: stock mínimo de cada variante (dato de ACC)." if umbral is None
                    else f"Umbral de alerta manual: {umbral} pares.")
    st.caption(f"{texto_umbral} Cobertura = stock ÷ (pares pedidos en los últimos {config.DIAS_DEMANDA_RECIENTE} días ÷ 4), "
               "en semanas; «N/D» si no hubo demanda en ese periodo (no se inventa).")
    mostrar_figura(vis.alertas_stock(resultados, ORIGEN), alertas)
    solo_alertas = st.toggle("Ver solo las variantes en alerta", value=True, key="f_solo_alertas")
    st.dataframe(alertas if solo_alertas else stock, width="stretch", hide_index=True)


def semaforo(fila):
    if fila["bloqueantes"] > 0:
        return "🔴", "Bloqueante"
    if fila["incidencias"] > 0:
        return "🟡", "Con avisos"
    return "🟢", "Correcto"


def vista_calidad(resultado, resultados):
    resumen = resultado["resumen_calidad"]
    st.subheader("Semáforo por tabla")
    for columna, (_, fila) in zip(st.columns(len(resumen)), resumen.iterrows()):
        icono, texto = semaforo(fila)
        columna.metric(f"{icono} {fila['tabla']}", f"{fila['porcentaje_calidad']:.1f} %")
        columna.caption(f"{texto} · {fila['filas_validas']} de {fila['filas_entrada']} filas válidas, "
                        f"{fila['filas_rechazadas']} rechazadas, {fila['incidencias']} incidencias")
    st.caption(f"Comprobación: {resultado['hora_comprobacion']:%d/%m/%Y %H:%M:%S} · "
               f"tasa de integridad global {resultados['calidad'].attrs.get('tasa_integridad_pct', 0)} %")

    incidencias = resultado["incidencias"]
    st.subheader("Incidencias")
    if incidencias.empty:
        st.success("Los CSV no tienen ninguna incidencia.")
    else:
        gravedades = st.multiselect("Gravedad", ["bloqueante", "recuperable", "advertencia"], placeholder="Todas", key="f_gravedad")
        st.dataframe(incidencias[incidencias["gravedad"].isin(gravedades)] if gravedades else incidencias,
                     width="stretch", hide_index=True)
        st.dataframe(resultados["calidad_por_regla"], width="stretch", hide_index=True)
    huerfanas = incidencias[incidencias["regla"].str.startswith("03")] if not incidencias.empty else incidencias
    if huerfanas.empty:
        st.success("Sin relaciones huérfanas: todas las líneas, pedidos y stock apuntan a registros que existen.")
    else:
        st.error(f"{len(huerfanas)} relaciones huérfanas (bloquean la publicación).")

    st.subheader("Conciliación con Acceso a Datos (SQL)")
    conciliacion = resultados["reconciliacion_sql"].copy()
    conciliacion.insert(0, "semaforo", conciliacion["estado"].map({"CUADRA": "🟢", "DESCUADRE": "🔴"}).fillna("⚪"))
    st.dataframe(conciliacion, width="stretch", hide_index=True)
    st.caption("Se compara siempre sin filtros: son las cifras que calcula PostgreSQL al exportar.")

    with st.expander("Manifiesto de los ficheros leídos"):
        st.dataframe(resultado["manifiesto"], width="stretch", hide_index=True)
    with st.expander("Valores atípicos (regla IQR): se conservan y se marcan para revisar"):
        st.dataframe(resultados["anomalias"], width="stretch", hide_index=True)


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
    elif vista == "Clientes":
        vista_clientes(resultados)
    elif vista == "Almacén":
        vista_almacen(resultados)
    elif vista == "Calidad y auditoría":
        vista_calidad(resultado, resultados)
    else:
        vista_pendiente(vista)


panel(filtros, vista)
