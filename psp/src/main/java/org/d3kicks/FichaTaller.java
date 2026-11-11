package org.d3kicks;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.List;

public class FichaTaller {

    public static void main(String[] args) throws Exception {

        Csv.usarUtf8();
        List<String> lineas = Csv.leerEntrada();

        if (lineas.size() < 3 || !lineas.get(0).startsWith("OK;") || !lineas.get(1).equals(Csv.CABECERA)) {
            System.err.println("ERROR;Se esperaba el resumen de tallas seguido de la ficha validada");
            System.exit(1);
        }

        String[] resumen = lineas.get(0).split(";");
        List<String> datos = Csv.separar(lineas.get(2));
        String ref = datos.get(0);

        List<String> hoja = new ArrayList<>();
        hoja.add("FICHA DE TALLER - D3 KICKS");
        hoja.add("Generada: " + LocalDateTime.now().withNano(0).format(DateTimeFormatter.ofPattern("dd/MM/yyyy HH:mm:ss")));
        hoja.add("");
        hoja.add("Pedido: " + ref);
        hoja.add("Cliente: " + datos.get(1));
        hoja.add("Modelo: " + datos.get(2) + " (" + datos.get(3) + ")");
        hoja.add("Diseño: " + datos.get(4));
        hoja.add("Texto bordado: " + (datos.get(5).isEmpty() ? "sin texto" : datos.get(5)));
        hoja.add("");
        hoja.add("Tallas:");
        for (int i = 2; i < resumen.length; i++) {
            String[] talla = resumen[i].split("=");
            hoja.add("  Talla " + talla[0] + ": " + talla[1] + " pares");
        }
        hoja.add("");
        hoja.add("Total: " + resumen[1] + " pares");

        Path ruta = Path.of("salida", "ficha_taller_" + ref + ".txt");
        Files.write(ruta, hoja, StandardCharsets.UTF_8);

        System.out.println("OK;" + ruta);
    }
}
