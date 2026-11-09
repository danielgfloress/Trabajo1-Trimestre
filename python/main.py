import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd

import analiticas
import config
import pipeline
import prediccion
import visualizaciones

SALIDAS = {
    "calidad": {
        "calidad_por_regla": "calidad_por_regla",
        "auditoria_reconciliacion_sql": "reconciliacion_sql",
        "anomalias": "anomalias",
    },
    "descriptivo": {
        "kpis": "kpis",
        "pedidos_unicos": "pedidos_unicos",
        "evolucion_mensual": "ventas_por_periodo",
        "modelos_abc": "modelos_abc",
        "matriz_modelo_talla": "matriz_modelo_talla",
        "matriz_modelo_talla_pct": "matriz_modelo_talla_pct",
        "custom_vs_estandar": "custom_vs_estandar",
        "stock_cobertura": "stock_cobertura",
        "estadistica_descriptiva": "estadistica_descriptiva",
        "estadistica_por_grupo": "estadistica_por_grupo",
        "hipotesis": "hipotesis",
        "demanda_modelo_mes": "demanda_modelo_mes",
        "talla_mas_solicitada": "talla_mas_solicitada",
        "precio_y_margen": "precio_y_margen",
    },
    "segmentacion": {
        "clientes_rfm": "clientes_rfm",
        "caracteristicas_clientes": "caracteristicas_clientes",
        "cohortes": "cohortes",
        "clustering_evaluacion": "clustering_evaluacion",
        "clustering_clientes": "clustering_clientes",
        "clustering_perfil": "clustering_perfil",
        "clustering_vs_rfm": "clustering_vs_rfm",
    },
    "prediccion": {nombre: nombre for nombre in prediccion.TABLAS},
}
TAREAS = list(SALIDAS) + ["graficos", "todo"]
COLUMNAS_PERSONALES = ["nombre", "cliente"]


def leer_argumentos(argumentos=None):
    parser = argparse.ArgumentParser(description="Sneaker Factory · análisis por consola de los CSV de Acceso a Datos")
    parser.add_argument("--modo", choices=list(config.ORIGENES), default="real", help="real (CSV de ACC) o sintetico")
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
    return parser.parse_args(argumentos)


def construir_filtros(args):
    filtros = {
        "desde": args.desde,
        "hasta": args.hasta,
        "modelos": args.modelos,
        "tallas": args.tallas,
        "tipos": args.tipos,
        "estados": args.estados,
        "clientes": args.clientes,
    }
    return {clave: valor for clave, valor in filtros.items() if valor}


def preparar_para_csv(df, origen, generado, filtros):
    if not isinstance(df.index, pd.RangeIndex):
        df = df.reset_index()
    df = df.drop(columns=[c for c in COLUMNAS_PERSONALES if c in df.columns])
    return df.assign(origen=origen, generado=generado, filtros=visualizaciones.texto_filtros(filtros))


def guardar_csv(tablas, carpeta, origen, generado, filtros):
    carpeta.mkdir(parents=True, exist_ok=True)
    rutas = []
    for nombre, df in tablas.items():
        ruta = carpeta / f"{nombre}.csv"
        preparar_para_csv(df, origen, generado, filtros).to_csv(ruta, index=False, encoding="utf-8")
        rutas.append(ruta)
    return rutas


def main(argumentos=None):
    args = leer_argumentos(argumentos)
    inicio = time.perf_counter()
    generado = datetime.now().strftime(config.FORMATO_FECHA)
    origen = config.ORIGENES[args.modo]
    entrada = args.entrada or config.CARPETAS_ENTRADA[args.modo]
    salida = args.salida / args.modo
    filtros = construir_filtros(args)

    print(f"Sneaker Factory · {origen}")
    print(f"Entrada: {entrada}")
    print(f"Salida:  {salida}")
    print(f"Filtros: {visualizaciones.texto_filtros(filtros)}")

    resultado = pipeline.ejecutar_pipeline(entrada, origen)
    calidad = {
        "resumen_calidad": resultado["resumen_calidad"],
        "incidencias": resultado["incidencias"],
        "manifiesto_origen": resultado["manifiesto"],
    }
    rutas = guardar_csv(calidad, salida, origen, generado, {})
    print(f"\nEstado de los datos: {resultado['estado']}")
    print(resultado["resumen_calidad"].to_string(index=False))

    if not resultado["publicable"]:
        bloqueantes = resultado["incidencias"][resultado["incidencias"]["gravedad"] == "bloqueante"]
        print("\nNO se publican resultados. Motivos:")
        print(bloqueantes[["tabla", "registro", "regla"]].to_string(index=False))
        pipeline.registrar_log(f"modo={args.modo} | entrada={entrada} | estado={resultado['estado']} | "
                               f"bloqueantes={len(bloqueantes)} | sin publicar", carpeta=args.logs)
        return 1

    resultados = analiticas.calcular_todo(resultado, filtros)
    tareas = list(SALIDAS) if args.tarea == "todo" else [args.tarea] if args.tarea in SALIDAS else []
    for tarea in tareas:
        tablas = {nombre: resultados[clave] for nombre, clave in SALIDAS[tarea].items()}
        rutas += guardar_csv(tablas, salida, origen, generado, filtros)

    pngs = []
    if args.tarea in ("graficos", "todo"):
        pngs = visualizaciones.guardar_figuras(visualizaciones.todas_las_figuras(resultados, origen), salida / "graficos")

    segundos = time.perf_counter() - inicio
    filas = int(resultado["resumen_calidad"]["filas_validas"].sum())
    print("\nIndicadores:")
    print(resultados["kpis"][["indicador", "valor", "unidad"]].to_string(index=False))
    print(f"\nGenerados {len(rutas)} CSV y {len(pngs)} PNG en {salida} ({segundos:.1f} s)")
    pipeline.registrar_log(f"modo={args.modo} | entrada={entrada} | estado={resultado['estado']} | filas_validas={filas} | "
                           f"tarea={args.tarea} | filtros={visualizaciones.texto_filtros(filtros)} | "
                           f"csv={len(rutas)} | png={len(pngs)} | {segundos:.1f} s", carpeta=args.logs)
    return 0


if __name__ == "__main__":
    sys.exit(main())
