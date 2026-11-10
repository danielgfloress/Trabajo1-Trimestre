import express from "express";
import { pool } from "./db.js";
import { autenticar } from "./auth.js";

const router = express.Router();

router.get("/", autenticar, async (req, res) => {
    const rolUsuario = req.usuario.rol || req.usuario.id_rol;

    if (rolUsuario !== 'ADMIN') {
        return res.status(403).json({ error: `Acceso denegado. Tu rol detectado es: ${rolUsuario}` });
    }

    try {
        const resultado = await pool.query(`
            SELECT u.id_usuario, u.username, r.nombre_rol, u.activo 
            FROM usuarios u
            JOIN roles r ON u.id_rol = r.id_rol
            ORDER BY u.id_usuario
        `);
        res.json(resultado.rows);
    } catch (error) {
        console.error("Error SQL:", error);
        res.status(500).json({ error: "Error en la consulta SQL. Revisa la terminal de Docker." });
    }
});

router.put("/:id/rol", autenticar, async (req, res) => {
    const rolUsuario = req.usuario.rol || req.usuario.id_rol;
    if (rolUsuario !== 'ADMIN') return res.status(403).json({ error: "Acceso denegado" });

    const { id } = req.params;
    const { nuevoRol } = req.body;

    try {
        await pool.query(`
            UPDATE usuarios 
            SET id_rol = (SELECT id_rol FROM roles WHERE nombre_rol = $1)
            WHERE id_usuario = $2
        `, [nuevoRol.toUpperCase(), id]);
        res.json({ mensaje: "Rol actualizado correctamente" });
    } catch (error) {
        console.error("Error al cambiar rol:", error);
        res.status(500).json({ error: "Error en la base de datos al cambiar el rol" });
    }
});

router.put("/:id/bloquear", autenticar, async (req, res) => {
    const rolUsuario = req.usuario.rol || req.usuario.id_rol;
    if (rolUsuario !== 'ADMIN') return res.status(403).json({ error: "Acceso denegado" });

    const { id } = req.params;

    try {
        await pool.query(`
            UPDATE usuarios 
            SET activo = NOT activo 
            WHERE id_usuario = $1
        `, [id]);
        res.json({ mensaje: "Estado del usuario actualizado" });
    } catch (error) {
        console.error("Error al bloquear usuario:", error);
        res.status(500).json({ error: "Error en la base de datos al cambiar el estado" });
    }
});

export default router;