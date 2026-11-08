import express from "express";
import cors from "cors";
import { pool } from "./db.js";
import { crearToken, autenticar } from "./auth.js";

const app = express();
app.use(cors());
const PUERTO = 3000;

app.use(cors());
app.use(express.json());

app.get("/api/salud", (req, res) => {
  res.json({ estado: "ok", mensaje: "La API de D3 Kicks funciona" });
});

app.get("/api/productos", async (req, res) => {
  try {
    const resultado = await pool.query(`
      SELECT m.codigo_modelo, m.marca, m.nombre, m.categoria, m.precio_base,
             m.altura_perfil, m.imagen, m.descripcion, a.color_base,
             SUM(a.stock_disponible) AS stock_total
      FROM modelos m
      JOIN almacen a ON a.id_modelo = m.id_modelo
      WHERE m.activo
      GROUP BY m.id_modelo, a.color_base
      ORDER BY m.codigo_modelo
    `);
    res.json(resultado.rows);
  } catch (error) {
    console.error(error);
    res.status(500).json({ error: "Error al consultar los productos" });
  }
});

app.get("/api/productos/:codigo", async (req, res) => {
  try {
    const { codigo } = req.params;
    const resultado = await pool.query(`
      SELECT m.codigo_modelo, m.marca, m.nombre, m.categoria, m.precio_base,
             m.altura_perfil, m.admite_custom, m.imagen, m.descripcion, a.color_base,
             json_agg(json_build_object('talla', a.talla, 'stock', a.stock_disponible)
                      ORDER BY a.talla) AS tallas
      FROM modelos m
      JOIN almacen a ON a.id_modelo = m.id_modelo
      WHERE m.codigo_modelo = $1 AND m.activo
      GROUP BY m.id_modelo, a.color_base
    `, [codigo]);

    if (resultado.rows.length === 0) {
      return res.status(404).json({ error: "Producto no encontrado" });
    }
    res.json(resultado.rows[0]);
  } catch (error) {
    console.error(error);
    res.status(500).json({ error: "Error al consultar el producto" });
  }
});

app.post("/api/login", async (req, res) => {
  try {
    const { usuario, contrasena } = req.body;
    if (!usuario || !contrasena) {
      return res.status(400).json({ error: "Escribe tu usuario y tu contraseña" });
    }

    const resultado = await pool.query(
      "SELECT * FROM fn_login($1, $2)",
      [usuario.trim().toLowerCase(), contrasena]
    );
    if (resultado.rows.length === 0) {
      return res.status(401).json({ error: "Usuario o contraseña incorrectos" });
    }

    const encontrado = resultado.rows[0];
    res.json({
      token: crearToken(encontrado),
      usuario: { username: encontrado.username, rol: encontrado.rol }
    });
  } catch (error) {
    console.error(error);
    res.status(500).json({ error: "Error al iniciar sesión" });
  }
});

app.post("/api/registro", async (req, res) => {
  const { nombre, email, contrasena } = req.body;

  if (!nombre || !email || !contrasena) {
    return res.status(400).json({ error: "Rellena todos los campos" });
  }
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    return res.status(400).json({ error: "El correo electrónico no es válido" });
  }
  if (contrasena.length < 8) {
    return res.status(400).json({ error: "La contraseña tiene que tener al menos 8 caracteres" });
  }

  const correo = email.trim().toLowerCase();
  const cliente = await pool.connect();
  try {
    await cliente.query("BEGIN");

    const nuevoCliente = await cliente.query(
      `INSERT INTO clientes (nombre, persona_contacto, tipo_cliente, email)
       VALUES ($1, $1, 'PARTICULAR', $2)
       RETURNING id_cliente`,
      [nombre.trim(), correo]
    );

    await cliente.query(
      `INSERT INTO usuarios (username, password_hash, id_rol, id_cliente)
       VALUES ($1, crypt($2, gen_salt('bf', 10)),
               (SELECT id_rol FROM roles WHERE nombre_rol = 'USUARIO'), $3)`,
      [correo, contrasena, nuevoCliente.rows[0].id_cliente]
    );

    await cliente.query("COMMIT");
    res.status(201).json({ mensaje: "Cuenta creada" });
  } catch (error) {
    await cliente.query("ROLLBACK");
    if (error.code === "23505") {
      return res.status(409).json({ error: "Ya hay una cuenta con ese correo" });
    }
    console.error(error);
    res.status(500).json({ error: "Error al crear la cuenta" });
  } finally {
    cliente.release();
  }
});

app.get("/api/yo", autenticar, async (req, res) => {
  try {
    const resultado = await pool.query(
      `SELECT pr.operacion
       FROM usuarios u
       JOIN permisos_rol pr ON pr.id_rol = u.id_rol
       WHERE u.id_usuario = $1 AND u.activo AND pr.permitido
       ORDER BY pr.operacion`,
      [req.usuario.id_usuario]
    );
    res.json({
      username: req.usuario.username,
      rol: req.usuario.rol,
      permisos: resultado.rows.map((fila) => fila.operacion)
    });
  } catch (error) {
    console.error(error);
    res.status(500).json({ error: "Error al consultar el usuario" });
  }
});

app.get("/api/usuarios", autenticar, async (req, res) => {
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

app.listen(PUERTO, () => {
  console.log(`API escuchando en el puerto ${PUERTO}`);
});
