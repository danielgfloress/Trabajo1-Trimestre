# D3 Kicks · PSP · Procesador de pedidos Custom

Aplicación Java independiente (no se conecta a la web, la API, la base de datos ni Odoo) que procesa la ficha de un pedido **D3 Custom** repartiendo el trabajo entre **varios procesos**. Un proceso padre lanza tres procesos hijos con `ProcessBuilder`, les pasa los datos por **stdin**, recoge su **stdout** y su **stderr** por separado, controla los **códigos de salida** y un **tiempo máximo**, y deja todo registrado por referencia de pedido.

Es un subsistema auxiliar: no sustituye a Odoo (ventas, fabricación y stock siguen allí). Genera los documentos para el taller.

## Requisitos

- JDK 21 (el código también compila con JDK 17).
- IntelliJ IDEA o cualquier IDE con Maven. No usa librerías externas.

## Estructura

```
psp/
├── entrada/
│   ├── ficha_SO003.csv          pedidos Custom reales del proyecto (datos de 05_datos.sql)
│   ├── ficha_SO005.csv
│   ├── ficha_SO010.csv
│   └── pruebas/                 fichas para demostrar validaciones y casos límite
├── salida/                      se crea al ejecutar: fichas de taller, resúmenes y log
├── src/main/java/org/d3kicks/
│   ├── Coordinador.java         proceso padre
│   ├── Validador.java           hijo 1
│   ├── AgrupadorTallas.java     hijo 2
│   ├── FichaTaller.java         hijo 3
│   └── Csv.java                 lectura y escritura de CSV común a todos
└── pom.xml
```

## Cómo ejecutarlo

**IntelliJ:** abrir la carpeta `psp`, ejecutar `org.d3kicks.Coordinador`. El directorio de trabajo debe ser la carpeta `psp`. Sin argumentos procesa `entrada/ficha_SO003.csv`; para otra ficha, ponerla en *Program arguments* (por ejemplo `entrada/ficha_SO010.csv`).

**Consola**, desde la carpeta `psp`:

```powershell
javac -encoding UTF-8 -d target/classes src/main/java/org/d3kicks/*.java
java -cp target/classes org.d3kicks.Coordinador entrada/ficha_SO003.csv
```

## Flujo entre procesos

```
                    lee la ficha
Coordinador ───────────────────────┐
     │                             │ stdin: ficha CSV
     │                             ▼
     │                        Validador ──stdout──▶ OK;filas;ref + ficha normalizada
     │                                             (stderr: ERROR;… por cada fallo)
     │ stdin: ficha normalizada
     ├────────────────────────▶ AgrupadorTallas ──stdout──▶ OK;total;talla=pares;…
     │
     │ stdin: resumen + ficha normalizada
     └────────────────────────▶ FichaTaller ──stdout──▶ OK;ruta  (escribe la ficha de taller)
```

Cada proceso trabaja con lo que devuelve el anterior: el agrupador recibe la ficha ya validada y ordenada, y la ficha de taller recibe el resumen del agrupador. Si el validador rechaza la ficha, no se lanza ningún proceso más.

| Proceso | Entrada (stdin) | Salida (stdout) | Errores (stderr) |
|---|---|---|---|
| `Validador` | la ficha CSV tal cual | `OK;<tallas>;<ref>` y la ficha normalizada | `ERROR;Fila N: …` por cada problema |
| `AgrupadorTallas` | la ficha normalizada | `OK;<total>;38=2;39=4;…` | `ERROR;…` |
| `FichaTaller` | el resumen y la ficha normalizada | `OK;salida/ficha_taller_<ref>.txt` | `ERROR;…` |

**Cómo se evita el bloqueo.** El padre escribe en el stdin del hijo y lee su stdout y su stderr **cada uno en un hilo, a la vez**, mientras espera con `waitFor(10 s)`. Si esperase primero y leyese después, un hijo que escribe mucho llenaría la tubería y se quedarían esperándose el uno al otro. La prueba `entrada/pruebas/ficha_grande.csv` (3.000 errores) lo demuestra: se rechaza en menos de un segundo, sin agotar el tiempo.

**Tiempo máximo.** Si un hijo tarda más de 10 s, se cancela con `destroyForcibly()` y queda en el log como `TIMEOUT`.

**Codificación.** Todos los procesos leen y escriben en UTF-8 (`Csv.usarUtf8()`), para que las tildes lleguen bien entre procesos también en Windows.

## Validaciones

- Cabecera exacta del contrato: `ref_odoo,cliente,modelo,color,diseno,texto_bordado,talla,cantidad`.
- 8 columnas por fila. Se admiten campos entre comillas con comas dentro, el BOM que añade Excel, espacios sobrantes y líneas vacías.
- Referencia con formato `SO` + número; cliente, modelo, color y diseño no vacíos.
- Texto bordado de 12 caracteres como máximo (igual que en la base de datos).
- Talla entera entre 36 y 46, sin repetir. Cantidad entera mayor que 0.
- Todas las filas del mismo pedido, cliente, modelo, color, diseño y texto.
- Al menos 20 pares en total (regla de los pedidos Custom).

## Códigos de salida

| Código | Significado |
|---|---|
| 0 | pedido procesado correctamente |
| 1 | ficha rechazada por el validador, o error en un proceso hijo |
| 2 | no existe la ficha indicada |

## Ficheros de salida y registro

- `salida/ficha_taller_<ref>.txt`: hoja para el taller con cliente, modelo, diseño, texto y pares por talla.
- `salida/resumen_tallas_<ref>.csv`: pares por talla y total.
- `salida/procesamiento.log`: registro que se acumula entre ejecuciones. Cada línea lleva la hora y la **referencia del pedido** (`[SO003]`), así que se puede seguir un pedido concreto. Antes de validar se usa el nombre del fichero. Recoge el PID de cada proceso, sus respuestas, sus errores y su código de salida.

## Pruebas

| Ficha | Resultado esperado | Código |
|---|---|---|
| `ficha_SO003.csv`, `ficha_SO005.csv`, `ficha_SO010.csv` | procesadas: ficha de taller y resumen | 0 |
| `pruebas/ficha_coma.csv` | aceptada: el diseño lleva una coma entre comillas | 0 |
| `pruebas/ficha_excel_bom.csv` | aceptada: guardada desde Excel (BOM y saltos de línea de Windows) | 0 |
| `pruebas/ficha_mala.csv` | rechazada: talla 52 y cantidad 0 | 1 |
| `pruebas/ficha_pedidos_mezclados.csv` | rechazada: filas de SO003 y SO005 en la misma ficha | 1 |
| `pruebas/ficha_pocos_pares.csv` | rechazada: 5 pares, menos de 20 | 1 |
| `pruebas/ficha_talla_repetida.csv` | rechazada: la talla 40 aparece dos veces | 1 |
| `pruebas/ficha_texto_largo.csv` | rechazada: texto bordado de más de 12 caracteres | 1 |
| `pruebas/ficha_vacia.csv` | rechazada: fichero vacío | 1 |
| `pruebas/ficha_grande.csv` | rechazada en menos de 1 s con 3.000 errores, sin bloqueo | 1 |
| `entrada/no_existe.csv` | no se lanza ningún proceso | 2 |

## Datos y relación con el proyecto

Las fichas de `entrada/` son los pedidos Custom reales del proyecto (mismas referencias, clientes, modelos y diseños que `acesso-a-datos/05_datos.sql` y Odoo): **SO003** (Club Halcones, Runner X, 20 pares), **SO005** (CD Leones del Sur, Predator League FG, 20 pares) y **SO010** (Running Crew Sur, ZoomX Invincible 3, 20 pares). SO006 no se incluye porque está cancelado.

El formato es el de la ficha de fabricación acordada con Acceso a Datos (cabecera `ref_odoo,cliente,modelo,color,diseno,texto_bordado,talla,cantidad`). Las fichas se han escrito con los datos de la base de datos; que Acceso a Datos las exporte directamente desde PostgreSQL queda pendiente en esa parte.
