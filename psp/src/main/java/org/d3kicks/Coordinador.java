package org.d3kicks;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.time.LocalTime;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.concurrent.TimeUnit;

public class Coordinador {

    static final String JAVA = Path.of(System.getProperty("java.home"), "bin", "java").toString();
    static final String FICHA_POR_DEFECTO = "entrada/ficha_SO003.csv";
    static final Path SALIDA = Path.of("salida");
    static final Path LOG = SALIDA.resolve("procesamiento.log");
    static final int TIMEOUT_MS = 10000;
    static final int MAXIMO_ERRORES_LOG = 20;

    record Resultado(int codigo, List<String> salida, List<String> errores) {
    }

    static String etiqueta;

    public static void main(String[] args) throws Exception {

        Path ficha = Path.of(args.length > 0 ? args[0] : FICHA_POR_DEFECTO);
        etiqueta = ficha.getFileName().toString();
        Files.createDirectories(SALIDA);

        log("INICIO Coordinador PID=" + ProcessHandle.current().pid() + " ficha=" + ficha);

        if (!Files.exists(ficha)) {
            log("ERROR No existe la ficha " + ficha);
            System.exit(2);
        }

        String contenido = Files.readString(ficha, StandardCharsets.UTF_8);

        Resultado validacion = lanzar("Validador", contenido);
        if (validacion == null) {
            log("FIN Ficha rechazada: no se lanzan más procesos");
            System.exit(1);
        }
        String[] cabecera = validacion.salida().get(0).split(";");
        etiqueta = cabecera[2];
        log("Ficha válida: " + cabecera[1] + " tallas");
        String fichaValidada = unirLineas(validacion.salida().subList(1, validacion.salida().size()));

        Resultado tallas = lanzar("AgrupadorTallas", fichaValidada);
        if (tallas == null) {
            log("FIN Pedido procesado con errores");
            System.exit(1);
        }
        String resumen = tallas.salida().get(0);
        guardarResumen(resumen);

        Resultado hoja = lanzar("FichaTaller", resumen + "\n" + fichaValidada);
        if (hoja == null) {
            log("FIN Pedido procesado con errores");
            System.exit(1);
        }
        log("GUARDADO " + hoja.salida().get(0).split(";")[1]);

        log("FIN Pedido procesado correctamente");
    }

    static Resultado lanzar(String clase, String entrada) throws Exception {

        ProcessBuilder pb = new ProcessBuilder(
                JAVA,
                "-cp",
                System.getProperty("java.class.path"),
                Coordinador.class.getPackageName() + "." + clase
        );

        Process proceso = pb.start();
        log("LANZADO " + clase + " PID=" + proceso.pid());

        List<String> salida = Collections.synchronizedList(new ArrayList<>());
        List<String> errores = Collections.synchronizedList(new ArrayList<>());
        Thread escritor = new Thread(() -> escribir(proceso.getOutputStream(), entrada));
        Thread lectorSalida = new Thread(() -> leer(proceso.getInputStream(), salida));
        Thread lectorErrores = new Thread(() -> leer(proceso.getErrorStream(), errores));
        escritor.start();
        lectorSalida.start();
        lectorErrores.start();

        boolean terminado = proceso.waitFor(TIMEOUT_MS, TimeUnit.MILLISECONDS);
        if (!terminado) {
            proceso.destroyForcibly();
            log("TIMEOUT " + clase + " ha superado " + TIMEOUT_MS + " ms y se ha cancelado");
            return null;
        }

        escritor.join();
        lectorSalida.join();
        lectorErrores.join();

        for (String error : errores.subList(0, Math.min(errores.size(), MAXIMO_ERRORES_LOG))) {
            log("   " + clase + " -> " + error);
        }
        if (errores.size() > MAXIMO_ERRORES_LOG) {
            log("   " + clase + " -> … y " + (errores.size() - MAXIMO_ERRORES_LOG) + " errores más (" + errores.size() + " en total)");
        }

        int codigo = proceso.exitValue();
        log("TERMINA " + clase + " código=" + codigo);

        if (codigo != 0) {
            return null;
        }
        if (salida.isEmpty() || !salida.get(0).startsWith("OK;")) {
            log("   Respuesta no válida de " + clase + ": " + (salida.isEmpty() ? "vacía" : salida.get(0)));
            return null;
        }

        log("   " + clase + " -> " + salida.get(0) + (salida.size() > 1 ? " (+" + (salida.size() - 1) + " líneas de datos)" : ""));
        return new Resultado(codigo, salida, errores);
    }

    static void escribir(OutputStream destino, String texto) {
        try (destino) {
            destino.write(texto.getBytes(StandardCharsets.UTF_8));
        } catch (IOException e) {
            return;
        }
    }

    static void leer(InputStream origen, List<String> lineas) {
        try (BufferedReader lector = new BufferedReader(new InputStreamReader(origen, StandardCharsets.UTF_8))) {
            String linea;
            while ((linea = lector.readLine()) != null) {
                lineas.add(linea);
            }
        } catch (IOException e) {
            return;
        }
    }

    static String unirLineas(List<String> lineas) {
        return String.join("\n", lineas) + "\n";
    }

    static void guardarResumen(String resumen) throws IOException {
        String[] partes = resumen.split(";");
        StringBuilder csv = new StringBuilder("talla,pares\n");
        for (int i = 2; i < partes.length; i++) {
            csv.append(partes[i].replace("=", ",")).append("\n");
        }
        csv.append("TOTAL,").append(partes[1]).append("\n");

        Path ruta = SALIDA.resolve("resumen_tallas_" + etiqueta + ".csv");
        Files.writeString(ruta, csv, StandardCharsets.UTF_8);
        log("Total de pares: " + partes[1]);
        log("GUARDADO " + ruta);
    }

    static synchronized void log(String mensaje) throws IOException {
        String texto = "[" + LocalTime.now().withNano(0) + "] [" + etiqueta + "] " + mensaje;
        System.out.println(texto);
        Files.writeString(LOG, texto + System.lineSeparator(), StandardCharsets.UTF_8,
                StandardOpenOption.CREATE, StandardOpenOption.APPEND);
    }
}
