import express from "express";
import { pool } from "./db.js";
import { autenticar, requierePermiso } from "./auth.js";

const router = express.Router();

const CONSULTA_USUARIO = `
    SELECT u.id_usuario, u.username, r.nombre_rol, u.activo, u.fecha_creacion
    FROM usuarios u
    JOIN roles r ON u.id_rol = r.id_rol
`;

router.use(autenticar, requierePermiso("USUARIOS_GESTIONAR"));

async function buscarUsuario(id) {
    const resultado = await pool.query(`${CONSULTA_USUARIO} WHERE u.id_usuario = $1`, [id]);
    return resultado.rows[0];
}

async function quedanOtrosAdmins(id) {
    const resultado = await pool.query(`
        SELECT COUNT(*) AS otros
        FROM usuarios u
        JOIN roles r ON u.id_rol = r.id_rol
        WHERE r.nombre_rol = 'ADMIN' AND u.activo AND u.id_usuario <> $1
    `, [id]);
    return Number(resultado.rows[0].otros) > 0;
}

function comprobarObjetivo(req, res) {
    const id = Number(req.params.id);
    if (!Number.isInteger(id)) {
        res.status(400).json({ error: "Usuario no válido" });
        return null;
    }
    if (id === req.usuario.id_usuario) {
        res.status(400).json({ error: "No puedes cambiar tu propia cuenta desde el panel" });
        return null;
    }
    return id;
}

router.get("/", async (req, res) => {
    try {
        const resultado = await pool.query(`${CONSULTA_USUARIO} ORDER BY u.id_usuario`);
        res.json(resultado.rows);
    } catch (error) {
        console.error(error);
        res.status(500).json({ error: "Error al consultar los usuarios" });
    }
});

router.get("/roles", async (req, res) => {
    try {
        const resultado = await pool.query("SELECT nombre_rol, descripcion FROM roles ORDER BY id_rol");
        res.json(resultado.rows);
    } catch (error) {
        console.error(error);
        res.status(500).json({ error: "Error al consultar los roles" });
    }
});

router.put("/:id/rol", async (req, res) => {
    const id = comprobarObjetivo(req, res);
    if (id === null) return;

    const nuevoRol = String(req.body.nuevoRol || "").trim().toUpperCase();
    try {
        const rol = await pool.query("SELECT id_rol FROM roles WHERE nombre_rol = $1", [nuevoRol]);
        if (rol.rows.length === 0) {
            return res.status(400).json({ error: "Ese rol no existe" });
        }
        const usuario = await buscarUsuario(id);
        if (!usuario) {
            return res.status(404).json({ error: "El usuario no existe" });
        }
        if (usuario.nombre_rol === "ADMIN" && nuevoRol !== "ADMIN" && usuario.activo && !(await quedanOtrosAdmins(id))) {
            return res.status(400).json({ error: "Tiene que quedar al menos un administrador activo" });
        }

        await pool.query("UPDATE usuarios SET id_rol = $1 WHERE id_usuario = $2", [rol.rows[0].id_rol, id]);
        res.json(await buscarUsuario(id));
    } catch (error) {
        console.error(error);
        res.status(500).json({ error: "Error al cambiar el rol" });
    }
});

router.put("/:id/bloquear", async (req, res) => {
    const id = comprobarObjetivo(req, res);
    if (id === null) return;

    try {
        const usuario = await buscarUsuario(id);
        if (!usuario) {
            return res.status(404).json({ error: "El usuario no existe" });
        }
        if (usuario.nombre_rol === "ADMIN" && usuario.activo && !(await quedanOtrosAdmins(id))) {
            return res.status(400).json({ error: "Tiene que quedar al menos un administrador activo" });
        }

        await pool.query("UPDATE usuarios SET activo = NOT activo WHERE id_usuario = $1", [id]);
        res.json(await buscarUsuario(id));
    } catch (error) {
        console.error(error);
        res.status(500).json({ error: "Error al cambiar el estado" });
    }
});

export default router;
