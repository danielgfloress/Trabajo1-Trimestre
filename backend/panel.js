import express from "express";
import { pool } from "./db.js";
import { autenticar, requierePermiso } from "./auth.js";

const router = express.Router();

const VENTA_VALIDA = "p.estado IN ('CONFIRMADO', 'ENTREGADO')";

router.get("/resumen", autenticar, requierePermiso("INDICADORES_VER"), async (req, res) => {
    try {
        const [totales, estados, meses, modelos, ultimos] = await Promise.all([
            pool.query(`
                SELECT COUNT(*) AS pedidos_totales,
                       COUNT(*) FILTER (WHERE ${VENTA_VALIDA}) AS pedidos_validos,
                       COALESCE(SUM(p.importe_total) FILTER (WHERE ${VENTA_VALIDA}), 0) AS ingresos,
                       COUNT(*) FILTER (WHERE ${VENTA_VALIDA} AND p.tipo = 'CUSTOM') AS pedidos_custom,
                       COALESCE(SUM(p.importe_total) FILTER (WHERE ${VENTA_VALIDA} AND p.tipo = 'CUSTOM'), 0) AS ingresos_custom,
                       (SELECT COALESCE(SUM(l.cantidad), 0)
                        FROM lineas_pedido l JOIN pedidos p ON p.id_pedido = l.id_pedido
                        WHERE ${VENTA_VALIDA}) AS pares,
                       (SELECT COALESCE(SUM(l.cantidad), 0)
                        FROM lineas_pedido l JOIN pedidos p ON p.id_pedido = l.id_pedido
                        WHERE ${VENTA_VALIDA} AND p.tipo = 'CUSTOM') AS pares_custom
                FROM pedidos p
            `),
            pool.query(`
                SELECT p.estado, COUNT(*) AS pedidos
                FROM pedidos p
                GROUP BY p.estado
            `),
            pool.query(`
                SELECT to_char(date_trunc('month', p.fecha_pedido), 'YYYY-MM') AS mes,
                       COUNT(*) AS pedidos,
                       SUM(p.importe_total) AS ingresos
                FROM pedidos p
                WHERE ${VENTA_VALIDA}
                GROUP BY 1
                ORDER BY 1 DESC
                LIMIT 12
            `),
            pool.query(`
                SELECT m.codigo_modelo, m.marca, m.nombre,
                       SUM(l.cantidad) AS pares,
                       SUM(l.subtotal_linea) AS ingresos
                FROM lineas_pedido l
                JOIN pedidos p ON p.id_pedido = l.id_pedido
                JOIN almacen a ON a.id_almacen = l.id_almacen
                JOIN modelos m ON m.id_modelo = a.id_modelo
                WHERE ${VENTA_VALIDA}
                GROUP BY m.id_modelo
                ORDER BY pares DESC, ingresos DESC
                LIMIT 5
            `),
            pool.query(`
                SELECT p.ref_odoo, p.fecha_pedido, c.nombre AS cliente, p.tipo, p.estado, p.importe_total,
                       (SELECT COALESCE(SUM(l.cantidad), 0) FROM lineas_pedido l WHERE l.id_pedido = p.id_pedido) AS pares
                FROM pedidos p
                JOIN clientes c ON c.id_cliente = p.id_cliente
                ORDER BY p.fecha_pedido DESC, p.id_pedido DESC
                LIMIT 8
            `)
        ]);

        res.json({
            generado: new Date().toISOString(),
            totales: totales.rows[0],
            estados: estados.rows,
            meses: meses.rows.reverse(),
            modelos: modelos.rows,
            ultimos: ultimos.rows
        });
    } catch (error) {
        console.error(error);
        res.status(500).json({ error: "Error al calcular el resumen del panel" });
    }
});

router.get("/stock", autenticar, requierePermiso("STOCK_CONSULTAR"), async (req, res) => {
    try {
        const resultado = await pool.query(`
            SELECT m.codigo_modelo, m.marca, m.nombre, a.color_base, a.talla,
                   a.stock_disponible, a.stock_minimo,
                   a.stock_disponible <= a.stock_minimo AS reponer
            FROM almacen a
            JOIN modelos m ON m.id_modelo = a.id_modelo
            WHERE m.activo
            ORDER BY reponer DESC, a.stock_disponible - a.stock_minimo, m.codigo_modelo, a.color_base, a.talla
        `);
        res.json(resultado.rows);
    } catch (error) {
        console.error(error);
        res.status(500).json({ error: "Error al consultar el stock" });
    }
});

export default router;
