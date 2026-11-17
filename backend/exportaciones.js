import fs from "fs";
import path from "path";
import { pool } from "./db.js";
import { CARPETA_SALIDAS } from "./actividad.js";

const FICHERO_USUARIOS = path.join(CARPETA_SALIDAS, "usuarios_sneaker.json");
const CARPETA_CSV = path.join(CARPETA_SALIDAS, "exportaciones");

// Campos públicos de cada usuario: nunca contraseñas, hashes ni tokens.
function fichaPublica(u) {
    return {
        id_usuario: u.id_usuario,
        username: u.username,
        rol: u.rol,
        activo: u.activo,
        fecha_creacion: u.fecha_creacion
    };
}

/**
 * Escribe usuarios_sneaker.json de forma segura:
 * 1) genera un fichero temporal, 2) lo vuelve a leer y comprueba que es JSON válido
 * con la misma lista, 3) sustituye el anterior con rename (operación atómica).
 * Si algo falla, el JSON anterior se queda como estaba.
 */
export function escribirUsuariosJson(lista) {
    const usuarios = lista.map(fichaPublica).sort((a, b) => a.id_usuario - b.id_usuario);
    const texto = JSON.stringify(usuarios, null, 2) + "\n";
    const temporal = FICHERO_USUARIOS + ".tmp";
    fs.mkdirSync(CARPETA_SALIDAS, { recursive: true });
    fs.writeFileSync(temporal, texto, "utf8");
    const releido = JSON.parse(fs.readFileSync(temporal, "utf8"));
    if (!Array.isArray(releido) || releido.length !== usuarios.length) {
        fs.rmSync(temporal, { force: true });
        throw new Error("El JSON generado no es válido");
    }
    fs.renameSync(temporal, FICHERO_USUARIOS);
    return { fichero: FICHERO_USUARIOS, usuarios: usuarios.length };
}

/**
 * Regenera el JSON con el estado CONFIRMADO de la base de datos. Se llama siempre
 * después del COMMIT de un cambio de usuarios, nunca dentro de la transacción,
 * así que un ROLLBACK no puede llegar a publicarse.
 */
export async function sincronizarUsuariosJson() {
    const resultado = await pool.query("SELECT fn_usuarios_json() AS usuarios");
    return escribirUsuariosJson(resultado.rows[0].usuarios);
}

// Fecha en hora local con el mismo formato que muestra PostgreSQL: AAAA-MM-DD HH:MM:SS
export function fechaLocal(d) {
    const dos = (n) => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${dos(d.getMonth() + 1)}-${dos(d.getDate())} ` +
        `${dos(d.getHours())}:${dos(d.getMinutes())}:${dos(d.getSeconds())}`;
}

function campoCsv(valor) {
    if (valor === null || valor === undefined) return "";
    const texto = valor instanceof Date ? fechaLocal(valor) : String(valor);
    return /[",\r\n]/.test(texto) ? `"${texto.replace(/"/g, '""')}"` : texto;
}

// Convierte filas a CSV (cabecera + filas, separador coma, UTF-8, saltos \n).
export function aCsv(columnas, filas) {
    const lineas = [columnas.join(",")];
    for (const fila of filas) {
        lineas.push(columnas.map((c) => campoCsv(fila[c])).join(","));
    }
    return lineas.join("\n") + "\n";
}

// Guarda una copia del CSV exportado en salidas/exportaciones/ y devuelve su ruta.
export function guardarCsv(prefijo, contenido) {
    fs.mkdirSync(CARPETA_CSV, { recursive: true });
    const marca = fechaLocal(new Date()).replace(/[-:]/g, "").replace(" ", "_");
    const fichero = path.join(CARPETA_CSV, `${prefijo}_${marca}.csv`);
    fs.writeFileSync(fichero, contenido, "utf8");
    return fichero;
}
