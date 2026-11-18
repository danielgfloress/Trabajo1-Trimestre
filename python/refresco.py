# Refresco del dashboard: cada 60 segundos se vuelven a leer, validar y calcular los CSV.
import hashlib
import time
from datetime import datetime
from pathlib import Path

import analiticas
import config
import pipeline


# Huella (hash MD5) del contenido de los 5 CSV.
# Si un CSV cambia, aunque sea un solo número, la huella cambia.
def huella(carpeta):
    resumen = hashlib.md5()
    for archivo in config.ARCHIVOS.values():
        ruta = Path(carpeta) / archivo
        resumen.update(archivo.encode())
        if ruta.exists():
            resumen.update(ruta.read_bytes())
        else:
            resumen.update(b"<sin fichero>")
    return resumen.hexdigest()


# Texto con los primeros errores bloqueantes, para enseñarlo en pantalla
def motivo_de(resultado):
    incidencias = resultado["incidencias"]
    bloqueantes = incidencias[incidencias["gravedad"] == "bloqueante"]
    partes = []
    for _, fila in bloqueantes.head(5).iterrows():
        partes.append(f"{fila['tabla']} {fila['registro']}: {fila['regla']}")
    return "; ".join(partes)


# Un ciclo de refresco (el dashboard lo ejecuta cada 60 s).
# Lee, valida y recalcula todo, y decide el estado:
#   correcto        → datos nuevos y válidos, se publican
#   sin cambios     → los CSV son los mismos que antes; se recalcula igual
#   datos inválidos → hay errores bloqueantes, no se publica
#   error de carga  → falta un CSV o se estaba exportando en ese momento
def ciclo(carpeta, origen, filtros, anterior=None, carpeta_logs=config.CARPETA_LOGS):
    # Lo que se publicó en el ciclo anterior (si lo hubo) y si ese ciclo fue bien
    publicacion_anterior = None
    anterior_correcto = False
    if anterior is not None:
        publicacion_anterior = anterior["publicacion"]
        anterior_correcto = anterior["estado"] in ("correcto", "sin cambios")

    comprobacion = datetime.now()
    inicio = time.perf_counter()

    # Huella antes y después de leer: si cambia, los CSV se estaban exportando justo en ese momento
    huella_antes = huella(carpeta)
    resultado = pipeline.ejecutar_pipeline(carpeta, origen)
    huella_despues = huella(carpeta)

    publicacion = None
    motivo = ""
    if huella_antes != huella_despues:
        # Exportación en curso: no se publica y se reintenta en el siguiente ciclo
        estado = "error de carga"
        motivo = "los CSV cambiaron mientras se leían (exportación en curso); se reintenta en el siguiente ciclo"
    elif resultado["estado"] == "error de carga":
        # Falta un CSV o no se puede leer
        estado = "error de carga"
        motivo = motivo_de(resultado)
    elif not resultado["publicable"]:
        # Hay errores bloqueantes en los datos
        estado = "datos inválidos"
        motivo = motivo_de(resultado)
    else:
        # Datos válidos: se recalcula todo, aunque los CSV no hayan cambiado
        resultados = analiticas.calcular_todo(resultado, filtros)
        if anterior_correcto and anterior["huella"] == huella_antes:
            estado = "sin cambios"
            motivo = "mismos CSV que en el ciclo anterior; se ha recalculado igualmente"
        else:
            estado = "correcto"
        # Todo lo que se enseña en pantalla sale de esta publicación (una sola versión de los datos)
        publicacion = {
            "huella": huella_antes,
            "hora": comprobacion,
            "resultado": resultado,
            "resultados": resultados,
            "filtros": filtros,
            "filas_validas": int(resultado["resumen_calidad"]["filas_validas"].sum()),
        }

    segundos = time.perf_counter() - inicio

    # Una línea en logs/refresco.log por cada ciclo
    filas = int(resultado["resumen_calidad"]["filas_validas"].sum())
    texto = f"origen={origen} | estado={estado} | filas_validas={filas} | {segundos:.2f} s | huella={huella_antes[:8]}"
    if motivo:
        texto += f" | {motivo}"
    pipeline.registrar_log(texto, archivo="refresco.log", carpeta=carpeta_logs)

    # Si este ciclo ha fallado, se sigue enseñando el último resultado válido y se marca como DESACTUALIZADO
    desactualizado = False
    if publicacion is None and publicacion_anterior is not None:
        publicacion = publicacion_anterior
        desactualizado = True

    return {
        "estado": estado,
        "motivo": motivo,
        "hora_comprobacion": comprobacion,
        "segundos": segundos,
        "resultado": resultado,
        "huella": huella_antes,
        "publicacion": publicacion,
        "desactualizado": desactualizado,
    }
