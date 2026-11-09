package com.javier;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.TreeMap;

public class AgrupadorTallas {

    public static void main(String[] args) throws Exception {

        if (args.length == 0) {
            System.err.println("ERROR;Debes indicar la ruta de la ficha");
            System.exit(2);
        }

        List<String> lineas = Files.readAllLines(Path.of(args[0]));

        TreeMap<Integer, Integer> paresPorTalla = new TreeMap<>();
        int total = 0;

        for (int i = 1; i < lineas.size(); i++) {
            String[] campos = lineas.get(i).split(",");
            int talla = Integer.parseInt(campos[6]);
            int cantidad = Integer.parseInt(campos[7]);

            paresPorTalla.put(talla, paresPorTalla.getOrDefault(talla, 0) + cantidad);
            total += cantidad;
        }

        String respuesta = "OK;" + total;
        for (int talla : paresPorTalla.keySet()) {
            respuesta += ";" + talla + "=" + paresPorTalla.get(talla);
        }

        System.out.println(respuesta);
    }
}