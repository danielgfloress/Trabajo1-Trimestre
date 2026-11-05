import jwt from "jsonwebtoken";
import { pool } from "./db.js";

const SECRETO = process.env.JWT_SECRET;

export function crearToken(usuario) {
    return jwt.sign(
        { id_usuario: usuario.id_usuario, username: usuario.username, rol: usuario.rol },
        SECRETO,
        { expiresIn: "8h" }
    );
}

export function autenticar(req, res, next) {
    const cabecera = req.headers.authorization || "";
    const token = cabecera.startsWith("Bearer ") ? cabecera.slice(7) : null;

    if (!token) {
        return res.status(401).json({ error: "Tienes que iniciar sesión" });
    }

    try {
        req.usuario = jwt.verify(token, SECRETO);
        next();
    } catch {
        res.status(401).json({ error: "La sesión no es válida o ha caducado" });
    }
}

export function requierePermiso(operacion) {
    return async (req, res, next) => {
        try {
            const resultado = await pool.query(
                "SELECT fn_tiene_permiso($1, $2) AS permitido",
                [req.usuario.id_usuario, operacion]
            );
            if (!resultado.rows[0].permitido) {
                return res.status(403).json({ error: "No tienes permiso para esta operación" });
            }
            next();
        } catch (error) {
            console.error(error);
            res.status(500).json({ error: "Error al comprobar los permisos" });
        }
    };
}

export async function conUsuario(idUsuario, trabajo) {
    const cliente = await pool.connect();
    try {
        await cliente.query("BEGIN");
        await cliente.query("SELECT set_config('app.id_usuario', $1, true)", [String(idUsuario)]);
        const resultado = await trabajo(cliente);
        await cliente.query("COMMIT");
        return resultado;
    } catch (error) {
        await cliente.query("ROLLBACK");
        throw error;
    } finally {
        cliente.release();
    }
}