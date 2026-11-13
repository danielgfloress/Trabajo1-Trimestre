const eurosCustom = new Intl.NumberFormat("es-ES", { style: "currency", currency: "EUR" });
const MODELO_POR_DEFECTO = "D3-001";
const MINIMO_PARES = 20;

const formularioCustom = document.getElementById("custom-formulario");
const selectModelo = document.getElementById("id_modelo");
const casillasTallas = [...document.querySelectorAll(".rejilla-tallas__cantidad")];
const botonEnviar = document.getElementById("custom-enviar");

formularioCustom.addEventListener("submit", enviarSolicitud);
for (const casilla of casillasTallas) {
    casilla.addEventListener("input", pintarPares);
}
document.getElementById("fecha_objetivo").min = new Date().toISOString().slice(0, 10);
avisarSesion();
pintarPares();
cargarModelos();

function nombreMarcaCustom(marca) {
    return marca.toLowerCase().replace(/\b\w/g, (letra) => letra.toUpperCase());
}

function mensajeCustom(texto) {
    document.getElementById("custom-mensaje").textContent = texto;
}

function avisarSesion() {
    const sesion = obtenerSesion();
    const aviso = document.getElementById("custom-sesion");
    if (!sesion) {
        aviso.textContent = "Para enviar la solicitud tienes que iniciar sesión con tu cuenta de cliente.";
        aviso.hidden = false;
    } else if (esPersonalInterno(sesion)) {
        aviso.textContent = "Has entrado como personal de D3 Kicks: los pedidos Custom solo los pueden hacer los clientes.";
        aviso.hidden = false;
    }
}

function paresIndicados() {
    return casillasTallas.reduce((total, casilla) => total + (Number(casilla.value) || 0), 0);
}

function pintarPares() {
    const pares = paresIndicados();
    const faltan = MINIMO_PARES - pares;
    document.getElementById("custom-pares").textContent = faltan > 0
        ? `Llevas ${pares} ${pares === 1 ? "par" : "pares"}: faltan ${faltan} para el mínimo de ${MINIMO_PARES}.`
        : `Llevas ${pares} pares.`;
}

async function cargarModelos() {
    try {
        const respuesta = await fetch(API + "/productos");
        if (!respuesta.ok) {
            throw new Error(`La API respondió con el código ${respuesta.status}`);
        }
        const productos = await respuesta.json();
        const vistos = new Set();
        const opciones = [];
        for (const producto of productos) {
            if (vistos.has(producto.codigo_modelo)) {
                continue;
            }
            vistos.add(producto.codigo_modelo);
            const opcion = document.createElement("option");
            opcion.value = producto.codigo_modelo;
            opcion.textContent = `${nombreMarcaCustom(producto.marca)} ${producto.nombre} · ${producto.color_base} · ${eurosCustom.format(Number(producto.precio_base))}`;
            opcion.selected = producto.codigo_modelo === MODELO_POR_DEFECTO;
            opciones.push(opcion);
        }
        selectModelo.replaceChildren(...opciones);
        selectModelo.disabled = false;
    } catch (error) {
        selectModelo.replaceChildren(new Option("No se han podido cargar los modelos", ""));
        mensajeCustom(`No se han podido cargar los modelos: ${error.message}`);
    }
}

function irAlLoginCustom() {
    location.href = "login.html?volver=custom.html";
}

async function enviarSolicitud(evento) {
    evento.preventDefault();
    mensajeCustom("");

    if (!obtenerSesion()) {
        irAlLoginCustom();
        return;
    }
    const pares = paresIndicados();
    if (pares < MINIMO_PARES) {
        mensajeCustom(`El pedido mínimo es de ${MINIMO_PARES} pares y has indicado ${pares}.`);
        return;
    }

    const datos = new FormData(formularioCustom);
    const cuerpo = {
        codigo_modelo: datos.get("id_modelo"),
        nombre_club: datos.get("nombre_club"),
        persona_contacto: datos.get("persona_contacto"),
        email: datos.get("email"),
        telefono: datos.get("telefono"),
        color_principal: datos.get("color_principal"),
        color_secundario: datos.get("color_secundario"),
        texto_lateral: datos.get("texto_lateral"),
        escudo: datos.get("escudo") === "si",
        notas_diseno: datos.get("notas_diseno"),
        fecha_objetivo: datos.get("fecha_objetivo"),
        tallas: casillasTallas.map((casilla) => ({
            talla: Number(casilla.id.replace("talla_", "")),
            cantidad: Number(casilla.value) || 0
        }))
    };

    botonEnviar.disabled = true;
    botonEnviar.textContent = "Enviando…";

    try {
        const respuesta = await fetchConSesion("/pedidos/custom", { method: "POST", body: JSON.stringify(cuerpo) });
        if (respuesta.status === 401) {
            irAlLoginCustom();
            return;
        }
        const resultado = await respuesta.json().catch(() => ({}));
        if (!respuesta.ok) {
            throw new Error(resultado.error || `La API respondió con el código ${respuesta.status}`);
        }

        formularioCustom.hidden = true;
        document.getElementById("custom-hecho").hidden = false;
        document.getElementById("custom-hecho-titulo").textContent = `Pedido Custom ${resultado.ref_odoo} confirmado`;
        document.getElementById("custom-hecho-texto").textContent =
            `${resultado.pares} pares por ${eurosCustom.format(Number(resultado.importe_total))}, con el recargo del diseño incluido. ` +
            "Es un pedido simulado: no se ha cobrado nada y las zapatillas ya se han reservado en el almacén.";
        document.getElementById("custom-hecho").scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (error) {
        mensajeCustom(`No se ha podido enviar el pedido: ${error.message}`);
    } finally {
        botonEnviar.disabled = false;
        botonEnviar.textContent = "Enviar pedido";
    }
}
