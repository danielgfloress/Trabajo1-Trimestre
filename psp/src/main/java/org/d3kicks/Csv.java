package org.d3kicks;

import java.io.BufferedReader;
import java.io.FileDescriptor;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStreamReader;
import java.io.PrintStream;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;

public final class Csv {

    public static final String CABECERA = "ref_odoo,cliente,modelo,color,diseno,texto_bordado,talla,cantidad";
    public static final int COLUMNAS = 8;

    private Csv() {
    }

    public static void usarUtf8() {
        System.setOut(new PrintStream(new FileOutputStream(FileDescriptor.out), true, StandardCharsets.UTF_8));
        System.setErr(new PrintStream(new FileOutputStream(FileDescriptor.err), true, StandardCharsets.UTF_8));
    }

    public static List<String> leerEntrada() throws IOException {
        BufferedReader lector = new BufferedReader(new InputStreamReader(System.in, StandardCharsets.UTF_8));
        List<String> lineas = new ArrayList<>();
        String linea;
        while ((linea = lector.readLine()) != null) {
            if (lineas.isEmpty() && linea.startsWith("﻿")) {
                linea = linea.substring(1);
            }
            if (!linea.isBlank()) {
                lineas.add(linea);
            }
        }
        return lineas;
    }

    public static List<String> separar(String linea) {
        List<String> campos = new ArrayList<>();
        StringBuilder actual = new StringBuilder();
        boolean entreComillas = false;

        for (int i = 0; i < linea.length(); i++) {
            char c = linea.charAt(i);
            if (entreComillas) {
                if (c == '"' && i + 1 < linea.length() && linea.charAt(i + 1) == '"') {
                    actual.append('"');
                    i++;
                } else if (c == '"') {
                    entreComillas = false;
                } else {
                    actual.append(c);
                }
            } else if (c == '"') {
                entreComillas = true;
            } else if (c == ',') {
                campos.add(actual.toString().trim());
                actual.setLength(0);
            } else {
                actual.append(c);
            }
        }
        campos.add(actual.toString().trim());
        return campos;
    }

    public static String unir(List<String> campos) {
        List<String> escritos = new ArrayList<>();
        for (String campo : campos) {
            if (campo.contains(",") || campo.contains("\"")) {
                escritos.add("\"" + campo.replace("\"", "\"\"") + "\"");
            } else {
                escritos.add(campo);
            }
        }
        return String.join(",", escritos);
    }
}
