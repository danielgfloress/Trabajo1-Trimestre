package org.d3kicks;

import java.util.List;
import java.util.TreeMap;

public class AgrupadorTallas {

    public static void main(String[] args) throws Exception {

        Csv.usarUtf8();
        List<String> lineas = Csv.leerEntrada();

        if (lineas.size() < 2 || !lineas.get(0).equals(Csv.CABECERA)) {
            System.err.println("ERROR;No se han recibido los datos validados de la ficha");
            System.exit(1);
        }

        TreeMap<Integer, Integer> paresPorTalla = new TreeMap<>();
        int total = 0;

        for (int i = 1; i < lineas.size(); i++) {
            List<String> campos = Csv.separar(lineas.get(i));
            int talla = Integer.parseInt(campos.get(6));
            int cantidad = Integer.parseInt(campos.get(7));

            paresPorTalla.merge(talla, cantidad, Integer::sum);
            total += cantidad;
        }

        StringBuilder respuesta = new StringBuilder("OK;" + total);
        for (var talla : paresPorTalla.entrySet()) {
            respuesta.append(";").append(talla.getKey()).append("=").append(talla.getValue());
        }

        System.out.println(respuesta);
    }
}
