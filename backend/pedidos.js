import express from "express";
import { pool } from "./db.js";
import { autenticar, conUsuario } from "./auth.js";

const router = express.Router();

const MAXIMO_LINEAS = 30;
const MAXIMO_PARES_LINEA = 50;

router.use(autenticar);

async function clienteDelUsuario(idUsuario) {
    const resultado = await pool.query("SELECT id_cliente FROM usuarios WHERE id_usuario = $1 AND activo", [idUsuario]);
    return resultado.rows[0]?.id_cliente ?? null;
}

function agruparLineas(lineas) {
    const agrupadas = new Map();
    for (const linea of lineas) {
        const codigo = String(linea.codigo_modelo || "").trim();
        const talla = Number(linea.talla);
        const cantidad = Number(linea.cantidad);
        if (!codigo || !Number.isInteger(talla) || !Number.isInteger(cantidad) || cantidad < 1) {
            return null;
        }
        const clave = `${codigo}|${talla}`;
        const anterior = agrupadas.get(clave);
        agrupadas.set(clave, { codigo, talla, cantidad: (anterior?.cantidad || 0) + cantidad });
    }
    return [...agrupadas.values()];
}

router.post("/", async (req, res) => {
    const lineas = Array.isArray(req.body.lineas) ? agruparLineas(req.body.lineas) : null;
    if (!lineas || lineas.length === 0) {
        return res.status(400).json({ error: "La cesta está vacía o tiene datos no válidos" });
    }
    if (lineas.length > MAXIMO_LINEAS || lineas.some((l) => l.cantidad > MAXIMO_PARES_LINEA)) {
        return res.status(400).json({ error: `Como máximo ${MAXIMO_LINEAS} líneas y ${MAXIMO_PARES_LINEA} pares por talla` });
    }

    try {
        const idCliente = await clienteDelUsuario(req.usuario.id_usuario);
        if (!idCliente) {
            return res.status(403).json({ error: "Solo las cuentas de cliente pueden hacer pedidos" });
        }

        const pedido = await conUsuario(req.usuario.id_usuario, async (cliente) => {
            await cliente.query("SELECT pg_advisory_xact_lock(hashtext('ref_odoo'))");
            const referencia = await cliente.query(`
                SELECT 'SO' || lpad((COALESCE(MAX(substring(ref_odoo FROM 3)::INTEGER), 0) + 1)::TEXT, 3, '0') AS ref
                FROM pedidos
                WHERE ref_odoo ~ '^SO[0-9]+$'
            `);
            const ref = referencia.rows[0].ref;

            const nuevo = await cliente.query(
                `INSERT INTO pedidos (ref_odoo, id_cliente, id_usuario, tipo)
                 VALUES ($1, $2, $3, 'ESTANDAR')
                 RETURNING id_pedido`,
                [ref, idCliente, req.usuario.id_usuario]
            );
            const idPedido = nuevo.rows[0].id_pedido;

            for (const linea of lineas) {
                const almacen = await cliente.query(
                    `SELECT a.id_almacen
                     FROM almacen a
                     JOIN modelos m ON m.id_modelo = a.id_modelo
                     WHERE m.codigo_modelo = $1 AND a.talla = $2 AND m.activo`,
                    [linea.codigo, linea.talla]
                );
                if (almacen.rows.length === 0) {
                    const error = new Error(`El modelo ${linea.codigo} en talla ${linea.talla} no está disponible`);
                    error.esDelCliente = true;
                    throw error;
                }
                await cliente.query(
                    `INSERT INTO lineas_pedido (id_pedido, id_almacen, cantidad, precio_unitario)
                     VALUES ($1, $2, $3, 0)`,
                    [idPedido, almacen.rows[0].id_almacen, linea.cantidad]
                );
            }

            await cliente.query("UPDATE pedidos SET estado = 'CONFIRMADO' WHERE id_pedido = $1", [idPedido]);
            const resumen = await cliente.query(
                `SELECT p.ref_odoo, p.estado, p.importe_total, SUM(l.cantidad) AS pares
                 FROM pedidos p JOIN lineas_pedido l ON l.id_pedido = p.id_pedido
                 WHERE p.id_pedido = $1
                 GROUP BY p.id_pedido`,
                [idPedido]
            );
            return resumen.rows[0];
        });

        res.status(201).json(pedido);
    } catch (error) {
        if (error.esDelCliente || error.code === "P0001") {
            return res.status(409).json({ error: error.message });
        }
        console.error(error);
        res.status(500).json({ error: "Error al registrar el pedido" });
    }
});

router.get("/mios", async (req, res) => {
    try {
        const idCliente = await clienteDelUsuario(req.usuario.id_usuario);
        if (!idCliente) {
            return res.json([]);
        }
        const resultado = await pool.query(`
            SELECT p.ref_odoo, p.fecha_pedido, p.tipo, p.estado, p.importe_total,
                   COALESCE(SUM(l.cantidad), 0) AS pares
            FROM pedidos p
            LEFT JOIN lineas_pedido l ON l.id_pedido = p.id_pedido
            WHERE p.id_cliente = $1
            GROUP BY p.id_pedido
            ORDER BY p.fecha_pedido DESC
        `, [idCliente]);
        res.json(resultado.rows);
    } catch (error) {
        console.error(error);
        res.status(500).json({ error: "Error al consultar tus pedidos" });
    }
});

export default router;
