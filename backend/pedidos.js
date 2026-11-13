import express from "express";
import { pool } from "./db.js";
import { autenticar, conUsuario } from "./auth.js";

const router = express.Router();

const MAXIMO_LINEAS = 30;
const MAXIMO_PARES_LINEA = 50;
const MINIMO_PARES_CUSTOM = 20;
const MAXIMO_PARES_TALLA_CUSTOM = 500;
const TALLAS = [36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46];
const RECARGO_CUSTOM = 10;
const RECARGO_CUSTOM_ESCUDO = 15;
const COLOR_HEX = /^#[0-9A-Fa-f]{6}$/;
const FECHA = /^\d{4}-\d{2}-\d{2}$/;

router.use(autenticar);

async function clienteDelUsuario(idUsuario) {
    const resultado = await pool.query("SELECT id_cliente FROM usuarios WHERE id_usuario = $1 AND activo", [idUsuario]);
    return resultado.rows[0]?.id_cliente ?? null;
}

async function siguienteReferencia(cliente) {
    await cliente.query("SELECT pg_advisory_xact_lock(hashtext('ref_odoo'))");
    const referencia = await cliente.query(`
        SELECT 'SO' || lpad((COALESCE(MAX(substring(ref_odoo FROM 3)::INTEGER), 0) + 1)::TEXT, 3, '0') AS ref
        FROM pedidos
        WHERE ref_odoo ~ '^SO[0-9]+$'
    `);
    return referencia.rows[0].ref;
}

function errorDelCliente(mensaje) {
    const error = new Error(mensaje);
    error.esDelCliente = true;
    return error;
}

async function idAlmacen(cliente, codigo, talla) {
    const almacen = await cliente.query(
        `SELECT a.id_almacen
         FROM almacen a
         JOIN modelos m ON m.id_modelo = a.id_modelo
         WHERE m.codigo_modelo = $1 AND a.talla = $2 AND m.activo`,
        [codigo, talla]
    );
    if (almacen.rows.length === 0) {
        throw errorDelCliente(`El modelo ${codigo} en talla ${talla} no está disponible`);
    }
    return almacen.rows[0].id_almacen;
}

async function resumenPedido(cliente, idPedido) {
    const resumen = await cliente.query(
        `SELECT p.ref_odoo, p.estado, p.importe_total, SUM(l.cantidad) AS pares
         FROM pedidos p JOIN lineas_pedido l ON l.id_pedido = p.id_pedido
         WHERE p.id_pedido = $1
         GROUP BY p.id_pedido`,
        [idPedido]
    );
    return resumen.rows[0];
}

function responderError(res, error, mensaje) {
    if (error.esDelCliente || error.code === "P0001" || error.code === "23514") {
        return res.status(409).json({ error: error.message });
    }
    console.error(error);
    res.status(500).json({ error: mensaje });
}

function texto(valor) {
    return typeof valor === "string" ? valor.trim() : "";
}

function leerSolicitudCustom(cuerpo) {
    const solicitud = {
        codigo: texto(cuerpo.codigo_modelo),
        club: texto(cuerpo.nombre_club),
        contacto: texto(cuerpo.persona_contacto),
        email: texto(cuerpo.email),
        telefono: texto(cuerpo.telefono),
        colorPrincipal: texto(cuerpo.color_principal),
        colorSecundario: texto(cuerpo.color_secundario),
        bordado: texto(cuerpo.texto_lateral).toUpperCase(),
        escudo: cuerpo.escudo === true,
        notas: texto(cuerpo.notas_diseno),
        fecha: texto(cuerpo.fecha_objetivo)
    };

    if (!solicitud.codigo || !solicitud.club || !solicitud.contacto || !solicitud.email) {
        return { error: "Faltan datos obligatorios: modelo, club, persona de contacto y correo" };
    }
    if (solicitud.club.length > 80) {
        return { error: "El nombre del club puede tener como máximo 80 caracteres" };
    }
    if (!COLOR_HEX.test(solicitud.colorPrincipal) || (solicitud.colorSecundario && !COLOR_HEX.test(solicitud.colorSecundario))) {
        return { error: "Los colores no son válidos" };
    }
    if (solicitud.bordado.length > 12) {
        return { error: "El nombre del lateral puede tener como máximo 12 caracteres" };
    }
    if (!FECHA.test(solicitud.fecha)) {
        return { error: "Indica la fecha en que necesitáis las zapatillas" };
    }

    const contacto = [solicitud.contacto, solicitud.email, solicitud.telefono].filter(Boolean).join(" · ");
    solicitud.notasCompletas = [solicitud.notas, `Contacto: ${contacto}`].filter(Boolean).join(" | ");
    if (solicitud.notasCompletas.length > 500) {
        return { error: "Las indicaciones del diseño son demasiado largas" };
    }

    if (!Array.isArray(cuerpo.tallas)) {
        return { error: "Indica cuántos pares necesitáis de cada talla" };
    }
    const tallas = new Map();
    for (const linea of cuerpo.tallas) {
        const talla = Number(linea?.talla);
        const cantidad = Number(linea?.cantidad);
        if (!TALLAS.includes(talla) || !Number.isInteger(cantidad) || cantidad < 0 || cantidad > MAXIMO_PARES_TALLA_CUSTOM) {
            return { error: `Cada talla admite de 0 a ${MAXIMO_PARES_TALLA_CUSTOM} pares` };
        }
        if (cantidad > 0) {
            tallas.set(talla, (tallas.get(talla) || 0) + cantidad);
        }
    }
    solicitud.tallas = [...tallas].map(([talla, cantidad]) => ({ talla, cantidad }));
    const pares = solicitud.tallas.reduce((total, linea) => total + linea.cantidad, 0);
    if (pares < MINIMO_PARES_CUSTOM) {
        return { error: `El pedido mínimo es de ${MINIMO_PARES_CUSTOM} pares y has indicado ${pares}` };
    }

    return { solicitud };
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
            const ref = await siguienteReferencia(cliente);
            const nuevo = await cliente.query(
                `INSERT INTO pedidos (ref_odoo, id_cliente, id_usuario, tipo, estado)
                 VALUES ($1, $2, $3, 'ESTANDAR', 'BORRADOR')
                 RETURNING id_pedido`,
                [ref, idCliente, req.usuario.id_usuario]
            );
            const idPedido = nuevo.rows[0].id_pedido;

            for (const linea of lineas) {
                await cliente.query(
                    `INSERT INTO lineas_pedido (id_pedido, id_almacen, cantidad, precio_unitario)
                     VALUES ($1, $2, $3, 0)`,
                    [idPedido, await idAlmacen(cliente, linea.codigo, linea.talla), linea.cantidad]
                );
            }

            await cliente.query("UPDATE pedidos SET estado = 'CONFIRMADO' WHERE id_pedido = $1", [idPedido]);
            return resumenPedido(cliente, idPedido);
        });

        res.status(201).json(pedido);
    } catch (error) {
        responderError(res, error, "Error al registrar el pedido");
    }
});

router.post("/custom", async (req, res) => {
    const { solicitud, error: errorSolicitud } = leerSolicitudCustom(req.body || {});
    if (errorSolicitud) {
        return res.status(400).json({ error: errorSolicitud });
    }

    try {
        const idCliente = await clienteDelUsuario(req.usuario.id_usuario);
        if (!idCliente) {
            return res.status(403).json({ error: "Solo las cuentas de cliente pueden hacer pedidos" });
        }

        const pedido = await conUsuario(req.usuario.id_usuario, async (cliente) => {
            const ref = await siguienteReferencia(cliente);
            const diseno = await cliente.query(
                `INSERT INTO personalizaciones
                     (nombre_diseno, color_primario, color_secundario, texto_bordado, escudo_club, notas_diseno, recargo_unitario)
                 VALUES ($1, $2, $3, $4, $5, $6, $7)
                 RETURNING id_personalizacion`,
                [
                    `DIS-${ref} ${solicitud.club}`,
                    solicitud.colorPrincipal.toUpperCase(),
                    solicitud.colorSecundario ? solicitud.colorSecundario.toUpperCase() : null,
                    solicitud.bordado || null,
                    solicitud.escudo ? `Escudo de ${solicitud.club} (pendiente de recibir)` : null,
                    solicitud.notasCompletas,
                    solicitud.escudo ? RECARGO_CUSTOM_ESCUDO : RECARGO_CUSTOM
                ]
            );
            const idPersonalizacion = diseno.rows[0].id_personalizacion;

            const nuevo = await cliente.query(
                `INSERT INTO pedidos (ref_odoo, id_cliente, id_usuario, tipo, estado, fecha_entrega_objetivo)
                 VALUES ($1, $2, $3, 'CUSTOM', 'BORRADOR', $4)
                 RETURNING id_pedido`,
                [ref, idCliente, req.usuario.id_usuario, solicitud.fecha]
            );
            const idPedido = nuevo.rows[0].id_pedido;

            for (const linea of solicitud.tallas) {
                await cliente.query(
                    `INSERT INTO lineas_pedido (id_pedido, id_almacen, id_personalizacion, cantidad, precio_unitario)
                     VALUES ($1, $2, $3, $4, 0)`,
                    [idPedido, await idAlmacen(cliente, solicitud.codigo, linea.talla), idPersonalizacion, linea.cantidad]
                );
            }

            await cliente.query("UPDATE pedidos SET estado = 'CONFIRMADO' WHERE id_pedido = $1", [idPedido]);
            return resumenPedido(cliente, idPedido);
        });

        res.status(201).json(pedido);
    } catch (error) {
        if (error.code === "23514") {
            error.message = "La fecha no puede ser anterior a hoy";
        }
        responderError(res, error, "Error al registrar el pedido Custom");
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
