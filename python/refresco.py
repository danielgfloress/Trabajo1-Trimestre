import hashlib
import time
from datetime import datetime
from pathlib import Path

import analiticas
import config
import pipeline


def huella(carpeta):
    resumen = hashlib.md5()
    for archivo in config.ARCHIVOS.values():
        ruta = Path(carpeta) / archivo
        resumen.update(archivo.encode())
        resumen.update(ruta.read_bytes() if ruta.exists() else b"<sin fichero>")
    return resumen.hexdigest()


def motivo_de(resultado):
    bloqueantes = resultado["incidencias"]
    bloqueantes = bloqueantes[bloqueantes["gravedad"] == "bloqueante"]
    return "; ".join(f"{fila.tabla} {fila.registro}: {fila.regla}" for fila in bloqueantes.head(5).itertuples())


def ciclo(carpeta, origen, filtros, anterior=None, carpeta_logs=config.CARPETA_LOGS):
    publicacion_anterior = anterior["publicacion"] if anterior else None
    anterior_correcto = anterior is not None and anterior["estado"] in ("correcto", "sin cambios")
    comprobacion = datetime.now()
    inicio = time.perf_counter()
    huella_antes = huella(carpeta)
    resultado = pipeline.ejecutar_pipeline(carpeta, origen)
    huella_despues = huella(carpeta)

    publicacion = None
    if huella_antes != huella_despues:
        estado = "error de carga"
        motivo = "los CSV cambiaron mientras se leían (exportación en curso); se reintenta en el siguiente ciclo"
    elif resultado["estado"] == "error de carga":
        estado = "error de carga"
        motivo = motivo_de(resultado)
    elif not resultado["publicable"]:
        estado = "datos inválidos"
        motivo = motivo_de(resultado)
    else:
        resultados = analiticas.calcular_todo(resultado, filtros)
        estado = "sin cambios" if anterior_correcto and anterior["huella"] == huella_antes else "correcto"
        motivo = "mismos CSV que en el ciclo anterior; se ha recalculado igualmente" if estado == "sin cambios" else ""
        publicacion = {
            "huella": huella_antes,
            "hora": comprobacion,
            "resultado": resultado,
            "resultados": resultados,
            "filtros": filtros,
            "filas_validas": int(resultado["resumen_calidad"]["filas_validas"].sum()),
        }

    segundos = time.perf_counter() - inicio
    filas = int(resultado["resumen_calidad"]["filas_validas"].sum())
    pipeline.registrar_log(
        f"origen={origen} | estado={estado} | filas_validas={filas} | {segundos:.2f} s | huella={huella_antes[:8]}"
        + (f" | {motivo}" if motivo else ""),
        archivo="refresco.log", carpeta=carpeta_logs)

    return {
        "estado": estado,
        "motivo": motivo,
        "hora_comprobacion": comprobacion,
        "segundos": segundos,
        "resultado": resultado,
        "huella": huella_antes,
        "publicacion": publicacion or publicacion_anterior,
        "desactualizado": publicacion is None and publicacion_anterior is not None,
    }
