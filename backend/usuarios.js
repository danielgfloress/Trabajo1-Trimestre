import express from "express";
import { pool } from "./db.js";
import { autenticar, requierePermiso, conUsuario } from "./auth.js";
import { registrarActividad, clasificarError } from "./actividad.js";
import { escribirUsuariosJson, sincronizarUsuariosJson } from "./exportaciones.js";

const router = express.Router();

const CONSULTA_USUARIO = `
    SELECT u.id_usuario, u.username, r.nombre_rol, u.activo, u.fecha_creacion
    FROM usuarios u
    JOIN roles r ON u.id_rol = r.id_rol
`;

// Tras un cambio confirmado (COMMIT) se regenera usuarios_sneaker.json.
// Si la regeneración fallara, el cambio en la base de datos ya está hecho y el
// JSON anterior se conserva intacto; se avisa en la respuesta y en la consola.
async function actualizarJson() {
    try {
        const { usuarios } = await sincronizarUsuariosJson();
        return { json_actualizado: true, usuarios_en_json: usuarios };
    } catch (error) {
        console.error("No se pudo actualizar usuarios_sneaker.json:", error.message);
        return { json_actualizado: false };
    }
}

function responderError(req, res, error, mensaje, accion, extra = {}) {
    let { estado, resultado, mensaje: mensajeBd } = clasificarError(error);
    if (error.code === "23505") mensajeBd = "Ya existe un usuario con ese nombre";
    registrarActividad(req.usuario, accion, resultado, { ...extra, motivo: mensajeBd || "error interno" });
    if (estado === 500) {
        console.error(error);
        return res.status(500).json({ error: mensaje });
    }
    res.status(estado).json({ error: mensajeBd });
}

// ---------------------------------------------------------------------
// Exportar usuarios a JSON. Requiere USUARIOS_EXPORTAR: lo comprueba la API
// (requierePermiso) y lo vuelve a comprobar PostgreSQL (fn_exportar_usuarios).
// Va antes del router.use de abajo para no exigir también USUARIOS_GESTIONAR.
// ---------------------------------------------------------------------
router.get("/exportar", autenticar, requierePermiso("USUARIOS_EXPORTAR"), async (req, res) => {
    try {
        const resultado = await pool.query("SELECT fn_exportar_usuarios($1) AS usuarios", [req.usuario.id_usuario]);
        const { usuarios } = escribirUsuariosJson(resultado.rows[0].usuarios);
        registrarActividad(req.usuario, "EXPORTAR_USUARIOS_JSON", "CORRECTO", { usuarios, fichero: "usuarios_sneaker.json" });
        res.json({ fichero: "usuarios_sneaker.json", usuarios });
    } catch (error) {
        responderError(req, res, error, "Error al exportar los usuarios", "EXPORTAR_USUARIOS_JSON");
    }
});

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

// Matriz de permisos: una fila por rol y operación.
router.get("/permisos", async (req, res) => {
    try {
        const resultado = await pool.query(`
            SELECT r.nombre_rol, pr.operacion, pr.permitido
            FROM permisos_rol pr JOIN roles r ON r.id_rol = pr.id_rol
            ORDER BY r.id_rol, pr.operacion
        `);
        res.json(resultado.rows);
    } catch (error) {
        console.error(error);
        res.status(500).json({ error: "Error al consultar los permisos" });
    }
});

// Crear un usuario. La contraseña se cifra con bcrypt en PostgreSQL (fn_crear_usuario)
// y el trigger trg_permisos_usuarios vuelve a comprobar USUARIOS_GESTIONAR.
router.post("/", async (req, res) => {
    const username = String(req.body?.username || "").trim().toLowerCase();
    const contrasena = String(req.body?.contrasena || "");
    const rol = String(req.body?.rol || "").trim().toUpperCase();
    if (!username || !contrasena || !rol) {
        registrarActividad(req.usuario, "CREAR_USUARIO", "RECHAZADO", { motivo: "faltan datos" });
        return res.status(400).json({ error: "Indica el nombre de usuario, la contraseña y el rol" });
    }
    if (rol === "USUARIO") {
        registrarActividad(req.usuario, "CREAR_USUARIO", "RECHAZADO", { motivo: "las cuentas de cliente se crean con el registro" });
        return res.status(400).json({ error: "Las cuentas de cliente se crean desde el registro de la web" });
    }
    try {
        const id = await conUsuario(req.usuario.id_usuario, async (cliente) => {
            const nuevo = await cliente.query("SELECT fn_crear_usuario($1, $2, $3) AS id", [username, contrasena, rol]);
            return nuevo.rows[0].id;
        });
        const sincronizacion = await actualizarJson();
        registrarActividad(req.usuario, "CREAR_USUARIO", "CORRECTO", { usuario_creado: username, rol_asignado: rol });
        res.status(201).json({ ...(await buscarUsuario(id)), ...sincronizacion });
    } catch (error) {
        responderError(req, res, error, "Error al crear el usuario", "CREAR_USUARIO", { usuario_creado: username });
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

        await conUsuario(req.usuario.id_usuario, (cliente) =>
            cliente.query("UPDATE usuarios SET id_rol = $1 WHERE id_usuario = $2", [rol.rows[0].id_rol, id]));
        const sincronizacion = await actualizarJson();
        registrarActividad(req.usuario, "CAMBIAR_ROL", "CORRECTO", { usuario_afectado: id, rol_nuevo: nuevoRol });
        res.json({ ...(await buscarUsuario(id)), ...sincronizacion });
    } catch (error) {
        responderError(req, res, error, "Error al cambiar el rol", "CAMBIAR_ROL", { usuario_afectado: id });
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

        await conUsuario(req.usuario.id_usuario, (cliente) =>
            cliente.query("UPDATE usuarios SET activo = NOT activo WHERE id_usuario = $1", [id]));
        const sincronizacion = await actualizarJson();
        const actualizado = await buscarUsuario(id);
        registrarActividad(req.usuario, actualizado.activo ? "ACTIVAR_USUARIO" : "DESACTIVAR_USUARIO", "CORRECTO", { usuario_afectado: id });
        res.json({ ...actualizado, ...sincronizacion });
    } catch (error) {
        responderError(req, res, error, "Error al cambiar el estado", "BLOQUEAR_USUARIO", { usuario_afectado: id });
    }
});

// Conceder o quitar un permiso a un rol. PostgreSQL impide quitar permisos al ADMIN.
router.put("/permisos", async (req, res) => {
    const rol = String(req.body?.rol || "").trim().toUpperCase();
    const operacion = String(req.body?.operacion || "").trim().toUpperCase();
    const permitido = req.body?.permitido;
    if (!rol || !operacion || typeof permitido !== "boolean") {
        return res.status(400).json({ error: "Indica el rol, la operación y si se permite (true o false)" });
    }
    try {
        const cambio = await conUsuario(req.usuario.id_usuario, (cliente) => cliente.query(`
            UPDATE permisos_rol SET permitido = $3
            WHERE id_rol = (SELECT id_rol FROM roles WHERE nombre_rol = $1) AND operacion = $2
            RETURNING operacion, permitido`, [rol, operacion, permitido]));
        if (cambio.rows.length === 0) {
            return res.status(404).json({ error: "Ese rol u operación no existe" });
        }
        registrarActividad(req.usuario, "CAMBIAR_PERMISO", "CORRECTO", { rol, operacion, permitido });
        res.json({ rol, ...cambio.rows[0] });
    } catch (error) {
        responderError(req, res, error, "Error al cambiar el permiso", "CAMBIAR_PERMISO", { rol, operacion });
    }
});

export default router;
