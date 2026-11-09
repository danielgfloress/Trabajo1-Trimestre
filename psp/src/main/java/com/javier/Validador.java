package com.javier;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;

public class Validador {

    static final String CABECERA = "ref_odoo,cliente,modelo,color,diseno,texto_bordado,talla,cantidad";

    public static void main(String[] args) throws Exception {

        if (args.length == 0) {
            System.err.println("ERROR;Debes indicar la ruta de la ficha");
            System.exit(2);
        }

        Path ficha = Path.of(args[0]);
        if (!Files.exists(ficha)) {
            System.err.println("ERROR;No existe la ficha " + args[0]);
            System.exit(2);
        }

        List<String> lineas = Files.readAllLines(ficha);

        if (lineas.size() < 2) {
            System.err.println("ERROR;La ficha está vacía");
            System.exit(1);
        }

        if (!lineas.get(0).equals(CABECERA)) {
            System.err.println("ERROR;La cabecera no es la del contrato");
            System.exit(1);
        }

        int errores = 0;

        for (int i = 1; i < lineas.size(); i++) {

            String[] campos = lineas.get(i).split(",");

            if (campos.length != 8) {
                System.err.println("ERROR;Fila " + (i + 1) + ": tiene " + campos.length + " columnas y deben ser 8");
                errores++;
                continue;
            }

            try {
                int talla = Integer.parseInt(campos[6]);
                int cantidad = Integer.parseInt(campos[7]);

                if (talla < 36 || talla > 46) {
                    System.err.println("ERROR;Fila " + (i + 1) + ": talla " + talla + " fuera de 36-46");
                    errores++;
                }

                if (cantidad <= 0) {
                    System.err.println("ERROR;Fila " + (i + 1) + ": cantidad " + cantidad + " no es mayor que 0");
                    errores++;
                }

            } catch (NumberFormatException e) {
                System.err.println("ERROR;Fila " + (i + 1) + ": la talla o la cantidad no es un número");
                errores++;
            }
        }

        if (errores > 0) {
            System.exit(1);
        }

        System.out.println("OK;" + (lineas.size() - 1));
    }
}