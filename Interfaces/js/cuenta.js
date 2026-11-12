const eurosCuenta = new Intl.NumberFormat("es-ES", { style: "currency", currency: "EUR" });
const fechaCuenta = new Intl.DateTimeFormat("es-ES", { day: "2-digit", month: "2-digit", year: "numeric" });
const ESTADOS_CUENTA = { BORRADOR: "Borrador", CONFIRMADO: "Confirmado", ENTREGADO: "Entregado", CANCELADO: "Cancelado" };
const TIPOS_CUENTA = { ESTANDAR: "Estándar", CUSTOM: "Custom" };
const TIPOS_CLIENTE = { CLUB: "Club", EQUIPO: "Equipo", PARTICULAR: "Particular" };

const sesionCuenta = obtenerSesion();

if (!sesionCuenta) {
    location.href = "login.html?volver=cuenta.html";
} else if (esPersonalInterno(sesionCuenta)) {
    location.href = "panel.html";
} else {
    document.getElementById("cuenta-salir").addEventListener("click", () => {
        cerrarSesion();
        location.href = "../index.html";
    });
    cargarCuenta();
}

async function pedirCuenta(ruta) {
    const respuesta = await fetchConSesion(ruta);
    if (respuesta.status === 401) {
        location.href = "login.html?volver=cuenta.html";
        throw new Error("La sesión ha caducado");
    }
    const datos = await respuesta.json().catch(() => ({}));
    if (!respuesta.ok) {
        throw new Error(datos.error || `La API respondió con el código ${respuesta.status}`);
    }
    return datos;
}

async function cargarCuenta() {
    const estado = document.getElementById("cuenta-estado");
    try {
        const [yo, pedidos] = await Promise.all([pedirCuenta("/yo"), pedirCuenta("/pedidos/mios")]);
        pintarDatos(yo);
        pintarPedidos(pedidos);
        estado.hidden = true;
        document.getElementById("cuenta-contenido").hidden = false;
    } catch (error) {
        estado.textContent = `No se ha podido cargar tu cuenta: ${error.message}`;
    }
}

function pintarDatos(yo) {
    const cliente = yo.cliente || {};
    document.getElementById("cuenta-saludo").textContent = cliente.nombre
        ? `Hola, ${cliente.nombre}. Aquí tienes tus datos y tus pedidos.`
        : "Tus datos y tus pedidos en D3 Kicks.";
    document.getElementById("dato-nombre").textContent = cliente.nombre || "—";
    document.getElementById("dato-email").textContent = cliente.email || yo.username;
    document.getElementById("dato-tipo").textContent = TIPOS_CLIENTE[cliente.tipo] || "—";
    document.getElementById("dato-alta").textContent = yo.alta ? fechaCuenta.format(new Date(yo.alta)) : "—";
}

function tarjetaCuenta(etiqueta, valor) {
    const tarjeta = document.createElement("div");
    tarjeta.className = "tarjeta";
    const titulo = document.createElement("p");
    titulo.className = "tarjeta__etiqueta";
    titulo.textContent = etiqueta;
    const numero = document.createElement("p");
    numero.className = "tarjeta__valor";
    numero.textContent = valor;
    tarjeta.append(titulo, numero);
    return tarjeta;
}

function celdaCuenta(contenido, clase) {
    const td = document.createElement("td");
    if (clase) {
        td.className = clase;
    }
    td.append(contenido);
    return td;
}

function pintarPedidos(pedidos) {
    const validos = pedidos.filter((p) => ["CONFIRMADO", "ENTREGADO"].includes(p.estado));
    document.getElementById("cuenta-resumen").replaceChildren(
        tarjetaCuenta("Pedidos", String(pedidos.length)),
        tarjetaCuenta("Pares comprados", String(validos.reduce((total, p) => total + Number(p.pares), 0))),
        tarjetaCuenta("Total comprado", eurosCuenta.format(validos.reduce((total, p) => total + Number(p.importe_total), 0)))
    );

    const cuerpo = document.getElementById("cuenta-pedidos");
    if (pedidos.length === 0) {
        const fila = document.createElement("tr");
        const celda = document.createElement("td");
        celda.colSpan = 6;
        celda.className = "sin-resultados";
        const enlace = document.createElement("a");
        enlace.href = "tienda.html";
        enlace.className = "enlace-destacado";
        enlace.textContent = "Ir a la tienda";
        celda.append("Todavía no has hecho ningún pedido. ", enlace);
        fila.append(celda);
        cuerpo.replaceChildren(fila);
        return;
    }

    cuerpo.replaceChildren(...pedidos.map((p) => {
        const estado = document.createElement("span");
        estado.className = ["CONFIRMADO", "ENTREGADO"].includes(p.estado) ? "etiqueta" : "etiqueta etiqueta--apagada";
        estado.textContent = ESTADOS_CUENTA[p.estado] || p.estado;

        const fila = document.createElement("tr");
        fila.append(
            celdaCuenta(p.ref_odoo),
            celdaCuenta(fechaCuenta.format(new Date(p.fecha_pedido))),
            celdaCuenta(TIPOS_CUENTA[p.tipo] || p.tipo),
            celdaCuenta(estado),
            celdaCuenta(String(p.pares), "tabla__numero"),
            celdaCuenta(eurosCuenta.format(Number(p.importe_total)), "tabla__numero")
        );
        return fila;
    }));
}
