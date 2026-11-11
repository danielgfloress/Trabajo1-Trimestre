package org.d3kicks;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

public class Validador {

    static final int TALLA_MINIMA = 36;
    static final int TALLA_MAXIMA = 46;
    static final int MINIMO_PARES_CUSTOM = 20;
    static final int MAXIMO_TEXTO_BORDADO = 12;
    static final String[] NOMBRES = {"ref_odoo", "cliente", "modelo", "color", "diseno"};

    public static void main(String[] args) throws Exception {

        Csv.usarUtf8();
        List<String> lineas = Csv.leerEntrada();

        if (lineas.isEmpty()) {
            System.err.println("ERROR;La ficha está vacía");
            System.exit(1);
        }

        if (!Csv.unir(Csv.separar(lineas.get(0))).equals(Csv.CABECERA)) {
            System.err.println("ERROR;La cabecera no es la del contrato: " + Csv.CABECERA);
            System.exit(1);
        }

        if (lineas.size() < 2) {
            System.err.println("ERROR;La ficha no tiene ninguna talla");
            System.exit(1);
        }

        int errores = 0;
        List<String> referencia = null;
        Set<Integer> tallasVistas = new HashSet<>();
        List<List<String>> filas = new ArrayList<>();
        int total = 0;

        for (int i = 1; i < lineas.size(); i++) {
            int numero = i + 1;
            List<String> campos = Csv.separar(lineas.get(i));

            if (campos.size() != Csv.COLUMNAS) {
                System.err.println("ERROR;Fila " + numero + ": tiene " + campos.size() + " columnas y deben ser " + Csv.COLUMNAS);
                errores++;
                continue;
            }

            if (!campos.get(0).matches("SO\\d+")) {
                System.err.println("ERROR;Fila " + numero + ": la referencia '" + campos.get(0) + "' no tiene el formato SO + número");
                errores++;
            }
            for (int c = 1; c < NOMBRES.length; c++) {
                if (campos.get(c).isEmpty()) {
                    System.err.println("ERROR;Fila " + numero + ": falta el campo " + NOMBRES[c]);
                    errores++;
                }
            }
            if (campos.get(5).length() > MAXIMO_TEXTO_BORDADO) {
                System.err.println("ERROR;Fila " + numero + ": el texto bordado tiene más de " + MAXIMO_TEXTO_BORDADO + " caracteres");
                errores++;
            }

            if (referencia == null) {
                referencia = campos.subList(0, 6);
            } else {
                for (int c = 0; c < 6; c++) {
                    if (!campos.get(c).equals(referencia.get(c))) {
                        System.err.println("ERROR;Fila " + numero + ": " + (c < NOMBRES.length ? NOMBRES[c] : "texto_bordado")
                                + " '" + campos.get(c) + "' no coincide con la primera fila ('" + referencia.get(c) + "'): una ficha es un solo pedido");
                        errores++;
                    }
                }
            }

            try {
                int talla = Integer.parseInt(campos.get(6));
                int cantidad = Integer.parseInt(campos.get(7));

                if (talla < TALLA_MINIMA || talla > TALLA_MAXIMA) {
                    System.err.println("ERROR;Fila " + numero + ": talla " + talla + " fuera de " + TALLA_MINIMA + "-" + TALLA_MAXIMA);
                    errores++;
                } else if (!tallasVistas.add(talla)) {
                    System.err.println("ERROR;Fila " + numero + ": la talla " + talla + " está repetida");
                    errores++;
                }

                if (cantidad <= 0) {
                    System.err.println("ERROR;Fila " + numero + ": cantidad " + cantidad + " no es mayor que 0");
                    errores++;
                } else {
                    total += cantidad;
                }

                filas.add(campos);
            } catch (NumberFormatException e) {
                System.err.println("ERROR;Fila " + numero + ": la talla o la cantidad no es un número entero");
                errores++;
            }
        }

        if (errores == 0 && total < MINIMO_PARES_CUSTOM) {
            System.err.println("ERROR;Un pedido Custom necesita al menos " + MINIMO_PARES_CUSTOM + " pares y la ficha tiene " + total);
            errores++;
        }

        if (errores > 0) {
            System.exit(1);
        }

        filas.sort(Comparator.comparingInt(f -> Integer.parseInt(f.get(6))));
        StringBuilder salida = new StringBuilder();
        salida.append("OK;").append(filas.size()).append(";").append(referencia.get(0)).append("\n");
        salida.append(Csv.CABECERA).append("\n");
        for (List<String> fila : filas) {
            salida.append(Csv.unir(fila)).append("\n");
        }
        System.out.print(salida);
    }
}
