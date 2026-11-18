# Dashboard de Streamlit. Se arranca con:  streamlit run app_dashboard.py
# Este archivo solo PINTA: todos los números salen de analiticas.py (a través de refresco.py).
# Streamlit ejecuta este archivo de arriba abajo cada vez que el usuario toca algo.
import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

import analiticas
import config
import main
import pipeline
import refresco
import visualizaciones as vis

# Origen de los datos que se enseñan
ORIGEN = config.ORIGENES["real"]
ORIGEN_SINTETICO = config.ORIGENES["sintetico"]
# DataFrames que se pueden descargar en CSV (nombre en resultados: texto del botón)
DESCARGAS = {
    "kpis": "KPIs",
    "pedidos_unicos": "Pedidos únicos",
    "ventas_por_periodo": "Evolución mensual",
    "modelos_abc": "Modelos ABC",
    "matriz_modelo_talla": "Matriz modelo × talla",
    "clientes_rfm": "Clientes RFM",
    "stock_cobertura": "Stock y cobertura",
}
VISTAS = ["Dirección", "Producto y ventas", "Clientes", "Almacén", "Calidad y auditoría", "Laboratorio (sintético)"]
# Claves con las que se guardan los filtros en st.session_state (así no se pierden al refrescar)
CLAVES_FILTRO = ["f_fechas", "f_modelos", "f_tallas", "f_tipos", "f_estados", "f_clientes", "f_umbral"]

# Título de la pestaña del navegador y página a todo lo ancho
st.set_page_config(page_title="Sneaker Factory · Dashboard", layout="wide")


# Botón "Restablecer filtros": borra los filtros guardados
def restablecer_filtros():
    for clave in CLAVES_FILTRO:
        if clave in st.session_state:
            del st.session_state[clave]


# Barra lateral con los filtros. Devuelve un diccionario solo con los filtros que se han usado.
# Cada widget tiene una key: Streamlit guarda su valor en st.session_state
def barra_lateral(tablas):
    pedidos = tablas["pedidos"]
    primero = pedidos["fecha_pedido"].min().date()
    ultimo = pedidos["fecha_pedido"].max().date()

    # Opciones de cada filtro (solo modelos y tallas que se han vendido)
    modelos_vendidos = tablas["modelos"][tablas["modelos"]["id_modelo"].isin(tablas["lineas"]["id_modelo"])]
    opciones_modelos = sorted(modelos_vendidos["codigo_modelo"])
    opciones_tallas = sorted(int(talla) for talla in tablas["lineas"]["talla"].unique())
    opciones_clientes = sorted(tablas["clientes"]["codigo_odoo"])

    st.sidebar.header("Filtros")
    fechas = st.sidebar.date_input("Periodo", value=(primero, ultimo), min_value=primero, max_value=ultimo,
                                   format="DD/MM/YYYY", key="f_fechas")
    modelos = st.sidebar.multiselect("Modelo", opciones_modelos, placeholder="Todos", key="f_modelos")
    tallas = st.sidebar.multiselect("Talla", opciones_tallas, placeholder="Todas", key="f_tallas")
    tipos = st.sidebar.multiselect("Tipo de pedido", config.TIPOS_PEDIDO, placeholder="Todos", key="f_tipos")
    estados = st.sidebar.multiselect("Estado", config.ESTADOS_VALIDOS, placeholder="Todos", key="f_estados")
    clientes = st.sidebar.multiselect("Cliente", opciones_clientes, placeholder="Todos", key="f_clientes")
    umbral = st.sidebar.number_input("Umbral de alerta de stock (pares)", min_value=0, value=None, step=1,
                                     placeholder="Stock mínimo de ACC", key="f_umbral")
    st.sidebar.button("Restablecer filtros", on_click=restablecer_filtros)
    st.sidebar.caption("Un filtro vacío no restringe nada. Con modelo o talla, cada pedido cuenta solo sus líneas de ese modelo o talla.")

    # Solo se añaden los filtros que el usuario ha cambiado
    filtros = {}
    # El periodo solo filtra si se ha elegido un rango más corto que el de todos los pedidos
    if isinstance(fechas, tuple) and len(fechas) == 2:
        if fechas[0] > primero or fechas[1] < ultimo:
            filtros["desde"] = str(fechas[0])
            filtros["hasta"] = str(fechas[1])
    if modelos:
        filtros["modelos"] = modelos
    if tallas:
        filtros["tallas"] = tallas
    if tipos:
        filtros["tipos"] = tipos
    if estados:
        filtros["estados"] = estados
    if clientes:
        filtros["clientes"] = clientes
    if umbral is not None:
        filtros["umbral_stock"] = int(umbral)
    return filtros


# Pinta un gráfico y, debajo, un desplegable con la tabla de datos del gráfico
def mostrar_figura(figura, tabla):
    st.pyplot(figura)
    plt.close(figura)
    with st.expander("Ver los datos del gráfico"):
        st.dataframe(tabla, hide_index=True)


# Saca el valor (como número) de un KPI de la tabla de kpis
def valor_kpi(resultados, indicador):
    kpis = resultados["kpis"]
    valor = kpis.loc[kpis["indicador"] == indicador, "valor"].iloc[0]
    return pd.to_numeric(valor, errors="coerce")


# Texto de la variación respecto al mes anterior (para la flecha de st.metric)
def variacion(valor):
    if pd.isna(valor):
        return None
    return f"{valor:+.1f} % frente al mes anterior"


# Cabecera: origen, hora de la última comprobación y de la última actualización válida, filas, tiempo y estado
def cabecera(ciclo, numero):
    publicacion = ciclo["publicacion"]
    st.title("Sneaker Factory · Dashboard")

    columnas = st.columns(6)
    columnas[0].metric("Procedencia", ORIGEN)
    columnas[1].metric("Última comprobación", f"{ciclo['hora_comprobacion']:%H:%M:%S}")
    if publicacion:
        columnas[2].metric("Última actualización válida", f"{publicacion['hora']:%H:%M:%S}")
        columnas[3].metric("Filas válidas", publicacion["filas_validas"])
    else:
        columnas[2].metric("Última actualización válida", "—")
        columnas[3].metric("Filas válidas", "—")
    columnas[4].metric("Tiempo de proceso", f"{ciclo['segundos']:.1f} s")
    columnas[5].metric("Estado", ciclo["estado"])

    texto = f"Ciclo nº {numero} · se recalcula solo cada {config.SEGUNDOS_REFRESCO} s"
    if publicacion:
        corte = publicacion["resultado"]["tablas"]["stock"]["fecha_corte"].max()
        texto += f" · fecha de corte de la exportación de ACC: {corte:%d/%m/%Y %H:%M}"
        texto += f" · filtros: {vis.texto_filtros(publicacion['filtros'])}"
    st.caption(texto)

    # Al pulsarlo, Streamlit vuelve a ejecutar el archivo y se recalcula en el momento
    st.button("Actualizar ahora", key="actualizar")

    # Si el último ciclo ha fallado, aviso en rojo: se enseña el último resultado válido con su hora
    if ciclo["desactualizado"]:
        st.error(f"**DATOS DESACTUALIZADOS.** La comprobación de las {ciclo['hora_comprobacion']:%H:%M:%S} ha fallado "
                 f"({ciclo['estado']}): {ciclo['motivo']}. Se muestran los últimos resultados válidos, calculados el "
                 f"{publicacion['hora']:%d/%m/%Y a las %H:%M:%S}.")
    elif publicacion is None:
        st.error(f"**No hay resultados que mostrar.** {ciclo['estado']}: {ciclo['motivo']}. "
                 f"Se volverá a comprobar en {config.SEGUNDOS_REFRESCO} s o al pulsar «Actualizar ahora».")


# Vista 1 · Dirección: KPIs principales, último mes frente al anterior y evolución mensual
def vista_direccion(resultados):
    st.subheader("Totales del periodo filtrado")
    columnas = st.columns(4)
    columnas[0].metric("Ingresos válidos", vis.euros(valor_kpi(resultados, "Ingresos válidos")))
    columnas[1].metric("Pares vendidos", f"{valor_kpi(resultados, 'Pares vendidos'):.0f}")
    columnas[2].metric("Pedidos válidos", f"{valor_kpi(resultados, 'Pedidos válidos (venta)'):.0f}")
    columnas[3].metric("Ticket medio", vis.euros(valor_kpi(resultados, "Ticket medio")))
    st.caption("Ventas válidas = pedidos CONFIRMADOS y ENTREGADOS. El ticket medio divide entre pedidos, no entre líneas.")

    # Último mes frente al anterior (hacen falta al menos 2 meses)
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
        st.info("Hay menos de dos meses con ventas: no hay periodo anterior con el que comparar.")

    st.subheader("Pedidos por estado")
    estados = resultados["pedidos_unicos"]["estado"].value_counts()
    columnas = st.columns(4)
    for i, estado in enumerate(config.ESTADOS_VALIDOS):
        columnas[i].metric(estado, int(estados.get(estado, 0)))

    mostrar_figura(vis.evolucion_mensual(resultados, ORIGEN), meses)
    with st.expander("Todos los indicadores con su fórmula y denominador"):
        st.dataframe(resultados["kpis"], hide_index=True)


# Vista 2 · Producto y ventas: ranking ABC, Pareto, mapa de calor y Custom frente a estándar
def vista_producto(resultados):
    mostrar_figura(vis.ranking_modelos(resultados, ORIGEN), resultados["modelos_abc"])
    mostrar_figura(vis.pareto_modelos(resultados, ORIGEN), resultados["modelos_abc"])
    st.caption("Clase ABC: A = modelos que suman el primer 80 % de los ingresos, B = hasta el 95 %, C = el resto.")

    # El índice de la matriz (modelo) se pasa a columna para enseñarlo en la tabla
    matriz_pct = resultados["matriz_modelo_talla_pct"].reset_index()
    matriz_pct.columns = [str(columna) for columna in matriz_pct.columns]
    mostrar_figura(vis.mapa_calor_modelo_talla(resultados, ORIGEN), matriz_pct)
    with st.expander("Talla más pedida de cada modelo"):
        st.dataframe(resultados["talla_mas_solicitada"], hide_index=True)

    mostrar_figura(vis.comparativa_tipo(resultados, ORIGEN), resultados["custom_vs_estandar"])
    mostrar_figura(vis.boxplot_por_tipo(resultados, ORIGEN), resultados["estadistica_por_grupo"])
    st.caption("La tasa de cancelación se mide sobre pedidos; la cuota de ingresos, sobre euros.")


# Vista 3 · Clientes: segmentos RFM, cohortes y KMeans
def vista_clientes(resultados):
    # Se quita el nombre del cliente (dato personal); se enseña solo su código
    rfm = resultados["clientes_rfm"].drop(columns="nombre")
    compradores = rfm[rfm["frecuencia"] > 0]

    st.subheader("Segmentos RFM")
    st.dataframe(rfm["segmento"].value_counts())
    st.caption(f"«En riesgo» = más de {config.RFM_DIAS_RIESGO} días sin comprar · «Campeón» = {config.RFM_FRECUENCIA_LEAL} "
               f"compras o más y como mucho {config.RFM_DIAS_RECIENTE} días sin comprar · «Leal» = {config.RFM_FRECUENCIA_LEAL} "
               "compras o más · la frecuencia cuenta pedidos, no líneas.")
    st.dataframe(rfm, hide_index=True)
    mostrar_figura(vis.dispersion_clientes(resultados, ORIGEN), compradores)

    st.subheader("Retención por cohortes")
    cohortes = resultados["cohortes"]
    if cohortes.attrs.get("aviso"):
        st.warning(cohortes.attrs["aviso"])
    st.caption("Cada fila es el mes de la primera compra; mes_1, mes_2… = % de esos clientes que vuelven a comprar después.")
    tabla_cohortes = cohortes.reset_index()
    tabla_cohortes.columns = [str(columna) for columna in tabla_cohortes.columns]
    st.dataframe(tabla_cohortes, hide_index=True)

    st.subheader("Agrupación automática (KMeans)")
    perfil = resultados["clustering_perfil"]
    if "estado" in perfil.columns:
        # NO CALCULABLE con los datos reales: se explica el motivo
        st.info(perfil["motivo"].iloc[0] + " Ver la vista «Laboratorio (sintético)».")
    else:
        mostrar_figura(vis.grupos_clientes(resultados, ORIGEN), perfil)


# Vista 4 · Almacén: alertas de stock bajo y cobertura
def vista_almacen(resultados):
    stock = resultados["stock_cobertura"]
    st.warning(stock.attrs["aviso"])
    alertas = stock[stock["alerta_stock_bajo"]]

    columnas = st.columns(4)
    columnas[0].metric("Variantes (modelo-color-talla)", len(stock))
    columnas[1].metric("En alerta", len(alertas))
    columnas[2].metric("Pares en almacén", int(stock["stock_disponible"].sum()))
    columnas[3].metric(f"Pares pedidos en {config.DIAS_DEMANDA_RECIENTE} días", int(stock["demanda_28_dias"].sum()))
    st.caption(f"Cobertura = stock ÷ (pares pedidos en los últimos {config.DIAS_DEMANDA_RECIENTE} días ÷ 4), en semanas; "
               "«N/D» si no hubo demanda. El umbral se puede cambiar en la barra lateral.")

    mostrar_figura(vis.alertas_stock(resultados, ORIGEN), alertas)
    st.subheader("Todas las variantes")
    st.dataframe(stock, hide_index=True)


# Vista 5 · Calidad y auditoría: calidad por tabla, incidencias y conciliación con SQL
def vista_calidad(resultado, resultados):
    st.subheader("Calidad por tabla")
    st.dataframe(resultado["resumen_calidad"], hide_index=True)
    st.caption(f"Comprobación: {resultado['hora_comprobacion']:%d/%m/%Y %H:%M:%S} · "
               f"tasa de integridad global {resultados['calidad'].attrs.get('tasa_integridad_pct', 0)} %")

    st.subheader("Incidencias")
    incidencias = resultado["incidencias"]
    if incidencias.empty:
        st.success("Los CSV no tienen ninguna incidencia.")
    else:
        st.dataframe(incidencias, hide_index=True)
        st.dataframe(resultados["calidad_por_regla"], hide_index=True)

    st.subheader("Conciliación con Acceso a Datos (SQL)")
    st.dataframe(resultados["reconciliacion_sql"], hide_index=True)
    st.caption("Se compara siempre sin filtros: son las cifras que calcula PostgreSQL al exportar.")

    with st.expander("Manifiesto de los ficheros leídos"):
        st.dataframe(resultado["manifiesto"], hide_index=True)
    with st.expander("Valores atípicos (regla IQR): se conservan y se marcan para revisar"):
        st.dataframe(resultados["anomalias"], hide_index=True)


# Botones para descargar los DataFrames en CSV (con los filtros aplicados y sin nombres de clientes)
def descargas(publicacion):
    generado = f"{publicacion['hora']:%Y-%m-%d %H:%M:%S}"
    with st.expander("Descargar resultados (CSV)"):
        for clave, nombre in DESCARGAS.items():
            tabla = main.preparar_para_csv(publicacion["resultados"][clave], ORIGEN, generado, publicacion["filtros"])
            st.download_button(nombre, tabla.to_csv(index=False).encode("utf-8"), file_name=f"{clave}.csv",
                               mime="text/csv", key=f"descarga_{clave}", on_click="ignore")


# Laboratorio sintético. @st.cache_data guarda el resultado y solo lo recalcula si cambia la huella de sus CSV
@st.cache_data(show_spinner="Calculando el laboratorio sintético…")
def calcular_laboratorio(huella):
    resultado = pipeline.ejecutar_pipeline(config.CARPETA_SINTETICOS, ORIGEN_SINTETICO)
    if resultado["publicable"]:
        return resultado, analiticas.calcular_todo(resultado)
    return resultado, None


# Vista 6 · Laboratorio: KMeans con datos SINTÉTICOS, separado y rotulado
def vista_laboratorio():
    st.warning("**LABORATORIO CON DATOS SINTÉTICOS.** Esta vista usa datos INVENTADOS por generador_datos.py. "
               "No son ventas de Sneaker Factory y no se mezclan con los datos de ACC. Sirve para demostrar "
               "la segmentación, que con los datos reales no es calculable. Los filtros no se aplican aquí.")
    if not (config.CARPETA_SINTETICOS / config.ARCHIVOS["pedidos"]).exists():
        st.info("Todavía no hay datos sintéticos. Genéralos con: python generador_datos.py")
        return

    resultado, resultados = calcular_laboratorio(refresco.huella(config.CARPETA_SINTETICOS))
    if resultados is None:
        st.error("Los datos sintéticos no pasan la validación.")
        st.dataframe(resultado["incidencias"], hide_index=True)
        return

    st.subheader("Segmentación de clientes (KMeans)")
    st.dataframe(resultados["clustering_evaluacion"], hide_index=True)
    st.caption("Se prueba k = 2 a 5 y se elige el k con mayor silhouette (de −1 a 1: más alto = grupos más separados).")
    st.dataframe(resultados["clustering_perfil"], hide_index=True)
    mostrar_figura(vis.grupos_clientes(resultados, ORIGEN_SINTETICO), resultados["clustering_clientes"])
    st.subheader("Grupos KMeans frente a segmentos RFM")
    st.dataframe(resultados["clustering_vs_rfm"], hide_index=True)
    st.caption("Un grupo matemático no es una categoría comercial: KMeans junta clientes parecidos en números; "
               "RFM aplica reglas de negocio fijas.")


# Tablas para rellenar las opciones de los filtros: las del último ciclo o, al empezar, una primera lectura
def tablas_para_filtros():
    anterior = st.session_state.get("ciclo")
    if anterior and anterior["publicacion"]:
        return anterior["publicacion"]["resultado"]["tablas"]
    inicial = pipeline.ejecutar_pipeline(config.CARPETA_ENTRADA, ORIGEN)
    if inicial["publicable"]:
        return inicial["tablas"]
    return None


# Esta función se vuelve a ejecutar sola cada 60 s gracias a st.fragment(run_every=...),
# sin recargar la página y sin usar sleep. Es el refresco automático que pide el PDF.
@st.fragment(run_every=f"{config.SEGUNDOS_REFRESCO}s")
def panel(filtros, vista, hay_barra_lateral):
    # Un ciclo: leer, validar y recalcular (refresco.py). Se guarda en session_state para el siguiente ciclo
    ciclo = refresco.ciclo(config.CARPETA_ENTRADA, ORIGEN, filtros, st.session_state.get("ciclo"), config.CARPETA_LOGS)
    st.session_state["ciclos"] = st.session_state.get("ciclos", 0) + 1
    st.session_state["ciclo"] = ciclo
    cabecera(ciclo, st.session_state["ciclos"])

    # Si nunca ha habido datos válidos, solo se enseñan las incidencias
    if ciclo["publicacion"] is None:
        st.subheader("Incidencias que impiden publicar")
        st.dataframe(ciclo["resultado"]["incidencias"], hide_index=True)
        return
    # Si al arrancar no había datos para los filtros y ahora sí, se recarga la página para pintar la barra lateral
    if not hay_barra_lateral:
        st.rerun()

    resultados = ciclo["publicacion"]["resultados"]
    descargas(ciclo["publicacion"])

    # Pinta la vista elegida
    if vista == "Dirección":
        vista_direccion(resultados)
    elif vista == "Producto y ventas":
        vista_producto(resultados)
    elif vista == "Clientes":
        vista_clientes(resultados)
    elif vista == "Almacén":
        vista_almacen(resultados)
    elif vista == "Calidad y auditoría":
        vista_calidad(ciclo["resultado"], resultados)
    else:
        vista_laboratorio()


# --- Programa principal ---
tablas_filtros = tablas_para_filtros()
if tablas_filtros:
    filtros = barra_lateral(tablas_filtros)
else:
    filtros = {}
# Selector de vista (se guarda en session_state con key="vista", así no se pierde al refrescar)
vista = st.radio("Vista", VISTAS, horizontal=True, key="vista", label_visibility="collapsed")
panel(filtros, vista, tablas_filtros is not None)
