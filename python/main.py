# Ejecución por consola: lee los CSV, los valida, calcula todo y guarda los resultados en outputs/.
# Ejemplos:
#   python main.py                          (datos reales)
#   python main.py --modo sintetico         (datos sintéticos)
#   python main.py --tallas 41 42 --desde 2026-07-01
import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd

import analiticas
import config
import pipeline
import visualizaciones

# Qué CSV se guardan en cada tarea (nombre del fichero: nombre del DataFrame)
SALIDAS = {
    "calidad": {
        "auditoria_reconciliacion_sql": "reconciliacion_sql",
    },
    "descriptivo": {
        "kpis": "kpis",
        "pedidos_unicos": "pedidos_unicos",
        "evolucion_mensual": "ventas_por_periodo",
        "modelos_abc": "modelos_abc",
        "matriz_modelo_talla": "matriz_modelo_talla",
        "stock_cobertura": "stock_cobertura",
    },
    "segmentacion": {
        "clientes_rfm": "clientes_rfm",
        "cohortes": "cohortes",
        "clustering_clientes": "clustering_clientes",
    },
}
# Tareas que se pueden pedir con --tarea
TAREAS = ["calidad", "descriptivo", "segmentacion", "graficos", "todo"]
# Columnas con nombres de clientes: no se guardan en los CSV (datos personales)
COLUMNAS_PERSONALES = ["nombre", "cliente"]


# Lee las opciones de la consola con argparse (python main.py --help las enseña todas)
def leer_argumentos(argumentos=None):
    parser = argparse.ArgumentParser(description="Sneaker Factory · análisis por consola de los CSV de Acceso a Datos")
    parser.add_argument("--modo", choices=["real", "sintetico"], default="real", help="real (CSV de ACC) o sintetico")
    parser.add_argument("--entrada", type=Path, help="carpeta de los CSV (por defecto la del modo)")
    parser.add_argument("--salida", type=Path, default=config.CARPETA_SALIDA, help="carpeta de resultados")
    parser.add_argument("--logs", type=Path, default=config.CARPETA_LOGS, help="carpeta del registro de ejecuciones")
    parser.add_argument("--tarea", choices=TAREAS, default="todo", help="qué generar")
    parser.add_argument("--desde", help="fecha inicial AAAA-MM-DD")
    parser.add_argument("--hasta", help="fecha final AAAA-MM-DD (incluida)")
    parser.add_argument("--modelos", nargs="+", help="códigos de modelo, p. ej. D3-001 NIK-022")
    parser.add_argument("--tallas", nargs="+", type=int, help="tallas, p. ej. 40 41")
    parser.add_argument("--tipos", nargs="+", choices=config.TIPOS_PEDIDO, help="ESTANDAR y/o CUSTOM")
    parser.add_argument("--estados", nargs="+", choices=config.ESTADOS_VALIDOS, help="estados de pedido")
    parser.add_argument("--clientes", nargs="+", help="códigos de cliente, p. ej. CLI001")
    parser.add_argument("--umbral-stock", type=int, help="alerta si el stock es menor o igual (por defecto, stock mínimo de ACC)")
    return parser.parse_args(argumentos)


# Junta los filtros en un diccionario, quitando los que no se han usado
def construir_filtros(args):
    todos = {
        "desde": args.desde,
        "hasta": args.hasta,
        "modelos": args.modelos,
        "tallas": args.tallas,
        "tipos": args.tipos,
        "estados": args.estados,
        "clientes": args.clientes,
        "umbral_stock": args.umbral_stock,
    }
    filtros = {}
    for clave, valor in todos.items():
        if valor:
            filtros[clave] = valor
    return filtros


# Antes de guardar: quita los nombres de clientes y añade las columnas origen, generado y filtros
def preparar_para_csv(df, origen, generado, filtros):
    # Si la tabla tiene un índice con información (por ejemplo, el modelo), se pasa a columna
    if not isinstance(df.index, pd.RangeIndex):
        df = df.reset_index()
    for columna in COLUMNAS_PERSONALES:
        if columna in df.columns:
            df = df.drop(columns=columna)
    df = df.copy()
    df["origen"] = origen
    df["generado"] = generado
    df["filtros"] = visualizaciones.texto_filtros(filtros)
    return df


# Guarda cada DataFrame en un CSV (UTF-8, sin índice) y devuelve la lista de rutas
def guardar_csv(tablas, carpeta, origen, generado, filtros):
    carpeta.mkdir(parents=True, exist_ok=True)
    rutas = []
    for nombre, df in tablas.items():
        ruta = carpeta / f"{nombre}.csv"
        preparar_para_csv(df, origen, generado, filtros).to_csv(ruta, index=False, encoding="utf-8")
        rutas.append(ruta)
    return rutas


# Programa principal de la consola
def main(argumentos=None):
    args = leer_argumentos(argumentos)
    inicio = time.perf_counter()
    generado = datetime.now().strftime(config.FORMATO_FECHA)
    origen = config.ORIGENES[args.modo]
    if args.entrada:
        entrada = args.entrada
    else:
        entrada = config.CARPETAS_ENTRADA[args.modo]
    salida = args.salida / args.modo
    filtros = construir_filtros(args)

    print(f"Sneaker Factory · {origen}")
    print(f"Entrada: {entrada}")
    print(f"Salida:  {salida}")
    print(f"Filtros: {visualizaciones.texto_filtros(filtros)}")

    # 1) Leer y validar los CSV. Los CSV de calidad se guardan siempre
    resultado = pipeline.ejecutar_pipeline(entrada, origen)
    calidad = {
        "resumen_calidad": resultado["resumen_calidad"],
        "incidencias": resultado["incidencias"],
        "manifiesto_origen": resultado["manifiesto"],
    }
    rutas = guardar_csv(calidad, salida, origen, generado, {})
    print(f"\nEstado de los datos: {resultado['estado']}")
    print(resultado["resumen_calidad"].to_string(index=False))

    # 2) Si hay errores bloqueantes: se explica el motivo y se termina con código 1 (error)
    if not resultado["publicable"]:
        incidencias = resultado["incidencias"]
        bloqueantes = incidencias[incidencias["gravedad"] == "bloqueante"]
        print("\nNO se publican resultados. Motivos:")
        print(bloqueantes[["tabla", "registro", "regla"]].to_string(index=False))
        pipeline.registrar_log(f"modo={args.modo} | entrada={entrada} | estado={resultado['estado']} | "
                               f"bloqueantes={len(bloqueantes)} | sin publicar", carpeta=args.logs)
        return 1

    # 3) Calcular todos los DataFrames y KPIs
    resultados = analiticas.calcular_todo(resultado, filtros)

    # 4) Guardar los CSV de las tareas pedidas
    if args.tarea == "todo":
        tareas = list(SALIDAS)
    elif args.tarea in SALIDAS:
        tareas = [args.tarea]
    else:
        tareas = []
    for tarea in tareas:
        tablas = {}
        for nombre_csv, nombre_df in SALIDAS[tarea].items():
            tablas[nombre_csv] = resultados[nombre_df]
        rutas += guardar_csv(tablas, salida, origen, generado, filtros)

    # 5) Guardar los gráficos en PNG
    pngs = []
    if args.tarea in ("graficos", "todo"):
        figuras = visualizaciones.todas_las_figuras(resultados, origen)
        pngs = visualizaciones.guardar_figuras(figuras, salida / "graficos")

    # 6) Enseñar los KPIs y apuntar la ejecución en logs/ejecuciones.log
    segundos = time.perf_counter() - inicio
    filas = int(resultado["resumen_calidad"]["filas_validas"].sum())
    print("\nIndicadores:")
    print(resultados["kpis"][["indicador", "valor", "unidad"]].to_string(index=False))
    print(f"\nGenerados {len(rutas)} CSV y {len(pngs)} PNG en {salida} ({segundos:.1f} s)")
    pipeline.registrar_log(f"modo={args.modo} | entrada={entrada} | estado={resultado['estado']} | filas_validas={filas} | "
                           f"tarea={args.tarea} | filtros={visualizaciones.texto_filtros(filtros)} | "
                           f"csv={len(rutas)} | png={len(pngs)} | {segundos:.1f} s", carpeta=args.logs)
    return 0


# Se ejecuta al lanzar: python main.py
if __name__ == "__main__":
    sys.exit(main())
