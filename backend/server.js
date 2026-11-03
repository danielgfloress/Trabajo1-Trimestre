import express from "express";
import cors from "cors";
import { pool } from "./db.js";

const app = express();
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
             m.altura_perfil, a.color_base, SUM(a.stock_disponible) AS stock_total
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
             m.altura_perfil, m.admite_custom, a.color_base,
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

app.listen(PUERTO, () => {
  console.log(`API escuchando en el puerto ${PUERTO}`);
});
