import fs from "fs";
import path from "path";

// Carpeta configurable para los ficheros que genera la API (TXT de actividad,
// JSON de usuarios y CSV exportados). En Docker se monta en ./salidas del repositorio.
export const CARPETA_SALIDAS = process.env.SALIDAS_DIR || path.resolve("salidas");
const FICHERO_ACTIVIDAD = path.join(CARPETA_SALIDAS, "actividad_sneaker.txt");

function fechaHora() {
    const d = new Date();
    const dos = (n) => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${dos(d.getMonth() + 1)}-${dos(d.getDate())} ` +
        `${dos(d.getHours())}:${dos(d.getMinutes())}:${dos(d.getSeconds())}`;
}

// Quita separadores y saltos de línea para que cada evento ocupe una sola línea.
function limpio(valor) {
    return String(valor).replace(/[\r\n|]+/g, " ").trim().slice(0, 120);
}

/**
 * Añade una línea a actividad_sneaker.txt (modo anexado, UTF-8).
 * Se escribe con appendFileSync: cuando la función vuelve, la línea ya está en disco.
 * Nunca se registran contraseñas, hashes, tokens ni sentencias SQL.
 *   usuario:   { id_usuario, username, rol } o null si no hay sesión
 *   accion:    p. ej. BUSCAR_PEDIDOS, CONFIRMAR_PEDIDO, INICIAR_SESION
 *   resultado: CORRECTO, RECHAZADO o ERROR
 *   extra:     datos opcionales no sensibles (pedido, filas, filtros, motivo...)
 */
export function registrarActividad(usuario, accion, resultado, extra = {}) {
    const partes = [
        fechaHora(),
        `usuario=${usuario ? `${limpio(usuario.username)} (id ${usuario.id_usuario})` : "(sin sesión)"}`,
        `rol=${usuario?.rol ?? "-"}`,
        `accion=${accion}`,
        `resultado=${resultado}`
    ];
    for (const [clave, valor] of Object.entries(extra)) {
        if (valor !== undefined && valor !== null && valor !== "") {
            partes.push(`${clave}=${limpio(valor)}`);
        }
    }
    try {
        fs.mkdirSync(CARPETA_SALIDAS, { recursive: true });
        fs.appendFileSync(FICHERO_ACTIVIDAD, partes.join(" | ") + "\n", { encoding: "utf8", flag: "a" });
    } catch (error) {
        // Un fallo del log no debe tumbar la petición, pero se deja constancia en la consola.
        console.error("No se pudo escribir en actividad_sneaker.txt:", error.message);
    }
}

// Clasifica un error de PostgreSQL para responder a la web y para el TXT.
export function clasificarError(error) {
    const conexion = ["ECONNREFUSED", "ENOTFOUND", "ETIMEDOUT", "57P01", "57P03"];
    if (conexion.includes(error.code) || String(error.code || "").startsWith("08")) {
        return { estado: 503, resultado: "ERROR", mensaje: "No se puede conectar con la base de datos" };
    }
    if (String(error.message || "").startsWith("Permiso denegado")) {
        return { estado: 403, resultado: "RECHAZADO", mensaje: error.message };
    }
    if (error.esDelCliente || error.code === "P0001" || error.code === "23514" || error.code === "23505") {
        return { estado: 409, resultado: "RECHAZADO", mensaje: error.message };
    }
    if (error.code === "22P02" || error.code === "22007" || error.code === "22008") {
        return { estado: 400, resultado: "RECHAZADO", mensaje: "Algún dato de la consulta no tiene el formato correcto" };
    }
    return { estado: 500, resultado: "ERROR", mensaje: null };
}
