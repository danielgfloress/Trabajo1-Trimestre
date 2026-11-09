package com.javier;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;

public class FichaTaller {

    public static void main(String[] args) throws Exception {

        if (args.length == 0) {
            System.err.println("ERROR;Debes indicar la ruta de la ficha");
            System.exit(2);
        }

        List<String> lineas = Files.readAllLines(Path.of(args[0]));

        String[] datos = lineas.get(1).split(",");

        List<String> hoja = new ArrayList<>();
        hoja.add("FICHA DE TALLER - D3 KICKS");
        hoja.add("Pedido: " + datos[0]);
        hoja.add("Cliente: " + datos[1]);
        hoja.add("Modelo: " + datos[2] + " " + datos[3]);
        hoja.add("Diseño: " + datos[4]);
        hoja.add("Texto bordado: " + datos[5]);
        hoja.add("");
        hoja.add("Tallas:");

        int total = 0;
        for (int i = 1; i < lineas.size(); i++) {
            String[] campos = lineas.get(i).split(",");
            hoja.add("Talla " + campos[6] + ": " + campos[7] + " pares");
            total += Integer.parseInt(campos[7]);
        }

        hoja.add("");
        hoja.add("Total: " + total + " pares");

        Path ruta = Path.of("salida", "ficha_taller_" + datos[0] + ".txt");
        Files.write(ruta, hoja);

        System.out.println("OK;" + ruta);
    }
}