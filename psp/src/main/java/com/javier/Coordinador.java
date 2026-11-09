package com.javier;

import java.io.BufferedReader;
import java.io.FileWriter;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.LocalTime;
import java.util.concurrent.TimeUnit;

public class Coordinador {

    static final String JAVA = Path.of(
            System.getProperty("java.home"),
            "bin",
            "java"
    ).toString();

    static final int TIMEOUT_MS = 10000;

    public static void main(String[] args) throws Exception {

        String ficha = args.length > 0 ? args[0] : "entrada/ficha_SO024.csv";

        Files.createDirectories(Path.of("salida"));

        log("INICIO Coordinador PID=" + ProcessHandle.current().pid() + " ficha=" + ficha);

        if (!Files.exists(Path.of(ficha))) {
            log("ERROR No existe la ficha " + ficha);
            System.exit(2);
        }

        String validacion = lanzar("Validador", ficha);
        if (validacion == null) {
            log("FIN Ficha rechazada: no se lanzan más procesos");
            System.exit(1);
        }

        String tallas = lanzar("AgrupadorTallas", ficha);
        if (tallas != null) {
            String[] partes = tallas.split(";");
            log("Total de pares: " + partes[1]);

            String csv = "talla,pares\n";
            for (int i = 2; i < partes.length; i++) {
                csv += partes[i].replace("=", ",") + "\n";
            }
            csv += "TOTAL," + partes[1] + "\n";
            Files.writeString(Path.of("salida", "resumen_tallas.csv"), csv);
            log("GUARDADO salida/resumen_tallas.csv");
        }

        String hoja = lanzar("FichaTaller", ficha);
        if (hoja != null) {
            log("GUARDADO " + hoja.split(";")[1]);
        }

        if (tallas != null && hoja != null) {
            log("FIN Pedido procesado correctamente");
        } else {
            log("FIN Pedido procesado con errores");
            System.exit(1);
        }
    }

    static String lanzar(String clase, String ficha) throws Exception {

        ProcessBuilder pb = new ProcessBuilder(
                JAVA,
                "-cp",
                System.getProperty("java.class.path"),
                "com.javier." + clase,
                ficha
        );

        Process proceso = pb.start();
        log("LANZADO " + clase + " PID=" + proceso.pid());

        boolean terminado = proceso.waitFor(TIMEOUT_MS, TimeUnit.MILLISECONDS);

        if (!terminado) {
            proceso.destroyForcibly();
            log("TIMEOUT " + clase + " ha superado " + TIMEOUT_MS + " ms y se ha cancelado");
            return null;
        }

        BufferedReader salidaHijo = proceso.inputReader();
        BufferedReader errorHijo = proceso.errorReader();

        String salida = salidaHijo.readLine();
        String linea;
        while ((linea = errorHijo.readLine()) != null) {
            if (linea.startsWith("ERROR;")) {
                log("   " + clase + " -> " + linea);
            }
        }

        salidaHijo.close();
        errorHijo.close();

        int codigo = proceso.exitValue();
        log("TERMINA " + clase + " código=" + codigo);

        if (codigo != 0) {
            return null;
        }

        if (salida == null || !salida.startsWith("OK;")) {
            log("   Respuesta no válida de " + clase + ": " + salida);
            return null;
        }

        log("   " + clase + " -> " + salida);
        return salida;
    }

    static void log(String mensaje) throws Exception {
        String texto = "[" + LocalTime.now().withNano(0) + "] " + mensaje;
        System.out.println(texto);

        FileWriter fichero = new FileWriter("salida/procesamiento.log", true);
        fichero.write(texto + "\n");
        fichero.close();
    }
}