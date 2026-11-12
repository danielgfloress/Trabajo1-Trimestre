const ROLES_PANEL = ["ADMIN", "COMERCIAL"];
const SEGUNDOS_REFRESCO = 60;
const ESTADOS = [
    { clave: "BORRADOR", nombre: "Borradores" },
    { clave: "CONFIRMADO", nombre: "Confirmados" },
    { clave: "ENTREGADO", nombre: "Entregados" },
    { clave: "CANCELADO", nombre: "Cancelados" }
];
const NOMBRE_ESTADO = { BORRADOR: "Borrador", CONFIRMADO: "Confirmado", ENTREGADO: "Entregado", CANCELADO: "Cancelado" };
const NOMBRE_TIPO = { ESTANDAR: "Estándar", CUSTOM: "Custom" };

const euros = new Intl.NumberFormat("es-ES", { style: "currency", currency: "EUR" });
const numero = new Intl.NumberFormat("es-ES");
const porcentaje = new Intl.NumberFormat("es-ES", { style: "percent", maximumFractionDigits: 1 });
const fecha = new Intl.DateTimeFormat("es-ES", { day: "2-digit", month: "2-digit", year: "numeric" });
const hora = new Intl.DateTimeFormat("es-ES", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
const nombreMes = new Intl.DateTimeFormat("es-ES", { month: "short", year: "numeric" });

const sesionPanel = obtenerSesion();
let usuarios = [];
let inventario = [];

if (!sesionPanel) {
    location.href = "login.html";
} else if (!ROLES_PANEL.includes(sesionPanel.rol)) {
    location.href = "../index.html";
} else {
    iniciarPanel();
}

function iniciarPanel() {
    const esAdmin = sesionPanel.rol === "ADMIN";
    document.getElementById("panel-usuario").textContent = `${sesionPanel.username} · ${esAdmin ? "Administración" : "Comercial"}`;
    document.getElementById("panel-salir").addEventListener("click", () => {
        cerrarSesion();
        location.href = "../index.html";
    });
    document.getElementById("panel-actualizar").addEventListener("click", actualizarTodo);
    window.addEventListener("hashchange", mostrarSeccion);
    document.getElementById("stock-filtro-modelo").addEventListener("change", pintarStock);
    document.getElementById("stock-solo-reponer").addEventListener("click", cambiarSoloReponer);

    if (esAdmin) {
        document.getElementById("enlace-usuarios").hidden = false;
        document.getElementById("usuarios-filtro-rol").addEventListener("change", pintarUsuarios);
        document.getElementById("usuarios-filtro-estado").addEventListener("change", pintarUsuarios);
        cargarUsuarios();
    }

    mostrarSeccion();
    cargarResumen();
    cargarStock();
    setInterval(() => {
        cargarResumen();
        cargarStock();
    }, SEGUNDOS_REFRESCO * 1000);
}

function seccionesDisponibles() {
    return [...document.querySelectorAll(".panel__enlace[data-seccion]")]
        .filter((enlace) => !enlace.hidden)
        .map((enlace) => enlace.dataset.seccion);
}

function mostrarSeccion() {
    const disponibles = seccionesDisponibles();
    const pedida = location.hash.slice(1);
    const actual = disponibles.includes(pedida) ? pedida : disponibles[0];

    document.querySelectorAll(".panel__seccion").forEach((seccion) => {
        seccion.hidden = seccion.id !== actual;
        if (seccion.id === actual) {
            document.getElementById("panel-titulo").textContent = seccion.dataset.titulo;
        }
    });
    document.querySelectorAll(".panel__enlace[data-seccion]").forEach((enlace) => {
        const activo = enlace.dataset.seccion === actual;
        enlace.classList.toggle("panel__enlace--activo", activo);
        if (activo) {
            enlace.setAttribute("aria-current", "page");
        } else {
            enlace.removeAttribute("aria-current");
        }
    });
}

function actualizarTodo() {
    cargarResumen();
    cargarStock();
    if (sesionPanel.rol === "ADMIN") {
        cargarUsuarios();
    }
}

function crear(etiqueta, clase, texto) {
    const elemento = document.createElement(etiqueta);
    if (clase) {
        elemento.className = clase;
    }
    if (texto !== undefined) {
        elemento.textContent = texto;
    }
    return elemento;
}

function fila(celdas) {
    const tr = document.createElement("tr");
    celdas.forEach(({ texto, clase, nodo }) => {
        const td = crear("td", clase, nodo ? undefined : texto);
        if (nodo) {
            td.append(nodo);
        }
        tr.append(td);
    });
    return tr;
}

function filaVacia(columnas, texto) {
    const tr = document.createElement("tr");
    const td = crear("td", "sin-resultados", texto);
    td.colSpan = columnas;
    tr.append(td);
    return tr;
}

function pintarTarjetas(contenedor, tarjetas) {
    contenedor.replaceChildren(...tarjetas.map(({ etiqueta, valor, nota }) => {
        const tarjeta = crear("div", "tarjeta");
        tarjeta.append(crear("p", "tarjeta__etiqueta", etiqueta), crear("p", "tarjeta__valor", valor));
        if (nota) {
            tarjeta.append(crear("p", "tarjeta__nota", nota));
        }
        return tarjeta;
    }));
}

function pintarBarras(lista, filas, textoVacio) {
    if (filas.length === 0) {
        lista.replaceChildren(crear("li", "sin-resultados", textoVacio));
        return;
    }
    const maximo = Math.max(...filas.map((f) => f.valor), 1);
    lista.replaceChildren(...filas.map(({ nombre, valor, texto }) => {
        const elemento = crear("li", "barras__fila");
        const pista = crear("div", "barras__pista");
        const relleno = crear("div", "barras__relleno");
        relleno.style.width = `${(valor / maximo) * 100}%`;
        pista.append(relleno);
        const etiqueta = crear("span", "barras__nombre", nombre);
        etiqueta.title = nombre;
        elemento.append(etiqueta, pista, crear("span", "barras__valor", texto));
        return elemento;
    }));
}

function etiquetaEstado(texto, apagada) {
    return crear("span", apagada ? "etiqueta etiqueta--apagada" : "etiqueta", texto);
}

function textoMes(mes) {
    const [anio, numeroMes] = mes.split("-").map(Number);
    return nombreMes.format(new Date(anio, numeroMes - 1, 1));
}

async function pedir(ruta, opciones) {
    const respuesta = await fetchConSesion(ruta, opciones);
    if (respuesta.status === 401) {
        location.href = "login.html";
        throw new Error("La sesión ha caducado");
    }
    const datos = await respuesta.json().catch(() => ({}));
    if (!respuesta.ok) {
        throw new Error(datos.error || `La API respondió con el código ${respuesta.status}`);
    }
    return datos;
}

async function cargarResumen() {
    const estado = document.getElementById("panel-estado");
    try {
        const datos = await pedir("/panel/resumen");
        pintarResumen(datos);
        estado.textContent = `Actualizado a las ${hora.format(new Date(datos.generado))} · se actualiza solo cada ${SEGUNDOS_REFRESCO} s y al pulsar «Actualizar».`;
    } catch (error) {
        estado.textContent = `No se han podido cargar los datos: ${error.message}`;
    }
}

function pintarResumen(datos) {
    const t = datos.totales;
    const ingresos = Number(t.ingresos);
    const validos = Number(t.pedidos_validos);
    const pares = Number(t.pares);

    pintarTarjetas(document.getElementById("panel-kpis"), [
        { etiqueta: "Ingresos válidos", valor: euros.format(ingresos), nota: "Pedidos confirmados y entregados" },
        { etiqueta: "Pedidos válidos", valor: numero.format(validos), nota: `De ${numero.format(Number(t.pedidos_totales))} pedidos en total` },
        { etiqueta: "Pares vendidos", valor: numero.format(pares), nota: validos ? `${numero.format(pares / validos)} pares por pedido` : "Sin ventas" },
        { etiqueta: "Ticket medio", valor: validos ? euros.format(ingresos / validos) : "—", nota: "Ingresos ÷ pedidos válidos" }
    ]);

    const porEstado = Object.fromEntries(datos.estados.map((e) => [e.estado, Number(e.pedidos)]));
    pintarTarjetas(document.getElementById("panel-estados"), [
        ...ESTADOS.map(({ clave, nombre }) => ({ etiqueta: nombre, valor: numero.format(porEstado[clave] || 0) })),
        {
            etiqueta: "Peso de D3 Custom",
            valor: ingresos ? porcentaje.format(Number(t.ingresos_custom) / ingresos) : "—",
            nota: `${numero.format(Number(t.pedidos_custom))} pedidos · ${numero.format(Number(t.pares_custom))} pares · de los ingresos válidos`
        }
    ]);

    pintarBarras(document.getElementById("panel-meses"), datos.meses.map((m) => ({
        nombre: textoMes(m.mes),
        valor: Number(m.ingresos),
        texto: euros.format(Number(m.ingresos))
    })), "Todavía no hay ventas válidas.");

    pintarBarras(document.getElementById("panel-modelos"), datos.modelos.map((m) => ({
        nombre: `${m.codigo_modelo} · ${m.nombre}`,
        valor: Number(m.pares),
        texto: `${numero.format(Number(m.pares))} pares`
    })), "Todavía no hay ventas válidas.");

    const ultimos = document.getElementById("panel-ultimos");
    ultimos.replaceChildren(...(datos.ultimos.length ? datos.ultimos.map((p) => fila([
        { texto: p.ref_odoo },
        { texto: fecha.format(new Date(p.fecha_pedido)) },
        { texto: p.cliente },
        { texto: NOMBRE_TIPO[p.tipo] || p.tipo },
        { nodo: etiquetaEstado(NOMBRE_ESTADO[p.estado] || p.estado, !["CONFIRMADO", "ENTREGADO"].includes(p.estado)) },
        { texto: numero.format(Number(p.pares)), clase: "tabla__numero" },
        { texto: euros.format(Number(p.importe_total)), clase: "tabla__numero" }
    ])) : [filaVacia(7, "Todavía no hay pedidos.")]));
}

async function cargarStock() {
    try {
        inventario = await pedir("/panel/stock");
        const filtro = document.getElementById("stock-filtro-modelo");
        const elegido = filtro.value;
        const modelos = new Map(inventario.map((s) => [s.codigo_modelo, `${s.codigo_modelo} · ${s.nombre}`]));
        filtro.replaceChildren(crear("option", null, "Todos los modelos"),
            ...[...modelos].sort((a, b) => a[0].localeCompare(b[0])).map(([codigo, nombre]) => {
                const opcion = crear("option", null, nombre);
                opcion.value = codigo;
                return opcion;
            }));
        filtro.firstChild.value = "";
        filtro.value = modelos.has(elegido) ? elegido : "";
        document.getElementById("stock-mensaje").textContent = "";
        pintarStock();
    } catch (error) {
        document.getElementById("stock-mensaje").textContent = `No se ha podido cargar el stock: ${error.message}`;
    }
}

function cambiarSoloReponer() {
    const boton = document.getElementById("stock-solo-reponer");
    const activo = boton.getAttribute("aria-pressed") !== "true";
    boton.setAttribute("aria-pressed", String(activo));
    boton.classList.toggle("filtro--activo", activo);
    pintarStock();
}

function pintarStock() {
    const modelo = document.getElementById("stock-filtro-modelo").value;
    const soloReponer = document.getElementById("stock-solo-reponer").getAttribute("aria-pressed") === "true";
    const reponer = inventario.filter((s) => s.reponer);

    pintarTarjetas(document.getElementById("stock-resumen"), [
        { etiqueta: "Pares en almacén", valor: numero.format(inventario.reduce((total, s) => total + s.stock_disponible, 0)) },
        { etiqueta: "Variantes", valor: numero.format(inventario.length), nota: "Modelo, color y talla" },
        {
            etiqueta: "Para reponer",
            valor: numero.format(reponer.length),
            nota: reponer.length ? "Stock igual o por debajo del mínimo" : "Todo por encima del mínimo"
        }
    ]);
    document.getElementById("stock-resumen").lastChild.classList.toggle("tarjeta--alerta", reponer.length > 0);

    const visibles = inventario.filter((s) => (!modelo || s.codigo_modelo === modelo) && (!soloReponer || s.reponer));
    const tabla = document.getElementById("panel-stock");
    if (visibles.length === 0) {
        tabla.replaceChildren(filaVacia(6, soloReponer ? "Nada que reponer con estos filtros." : "Ningún resultado."));
        return;
    }
    tabla.replaceChildren(...visibles.map((s) => {
        const estado = crear("span", s.reponer ? "etiqueta etiqueta--alerta" : "etiqueta etiqueta--apagada",
            s.reponer ? "Reponer" : "Correcto");
        const tr = fila([
            { texto: `${s.codigo_modelo} · ${s.nombre}` },
            { texto: s.color_base },
            { texto: s.talla, clase: "tabla__numero" },
            { texto: numero.format(s.stock_disponible), clase: "tabla__numero" },
            { texto: numero.format(s.stock_minimo), clase: "tabla__numero" },
            { nodo: estado }
        ]);
        if (s.reponer) {
            tr.className = "tabla__fila--alerta";
        }
        return tr;
    }));
}

function mensajeUsuarios(texto) {
    document.getElementById("usuarios-mensaje").textContent = texto;
}

async function cargarUsuarios() {
    try {
        const [lista, roles] = await Promise.all([pedir("/usuarios"), pedir("/usuarios/roles")]);
        usuarios = lista;
        const filtroRol = document.getElementById("usuarios-filtro-rol");
        filtroRol.replaceChildren(crear("option", null, "Todos los roles"),
            ...roles.map((r) => {
                const opcion = crear("option", null, r.nombre_rol);
                opcion.value = r.nombre_rol;
                return opcion;
            }));
        filtroRol.firstChild.value = "";
        filtroRol.dataset.roles = JSON.stringify(roles.map((r) => r.nombre_rol));
        pintarUsuarios();
    } catch (error) {
        mensajeUsuarios(`No se han podido cargar los usuarios: ${error.message}`);
    }
}

function pintarUsuarios() {
    const roles = JSON.parse(document.getElementById("usuarios-filtro-rol").dataset.roles || "[]");
    const rolElegido = document.getElementById("usuarios-filtro-rol").value;
    const estadoElegido = document.getElementById("usuarios-filtro-estado").value;

    pintarTarjetas(document.getElementById("usuarios-resumen"), [
        { etiqueta: "Usuarios", valor: numero.format(usuarios.length) },
        { etiqueta: "Activos", valor: numero.format(usuarios.filter((u) => u.activo).length) },
        { etiqueta: "Bloqueados", valor: numero.format(usuarios.filter((u) => !u.activo).length) },
        { etiqueta: "Administradores", valor: numero.format(usuarios.filter((u) => u.nombre_rol === "ADMIN").length) }
    ]);

    const visibles = usuarios.filter((u) =>
        (!rolElegido || u.nombre_rol === rolElegido) &&
        (!estadoElegido || (estadoElegido === "activo") === u.activo));

    const tabla = document.getElementById("usuarios-tabla");
    tabla.replaceChildren(...(visibles.length ? visibles.map((u) => filaUsuario(u, roles)) : [filaVacia(5, "Ningún usuario coincide con los filtros.")]));
}

function filaUsuario(usuario, roles) {
    const esYo = usuario.username === sesionPanel.username;

    const selector = crear("select", "filtro-select");
    selector.setAttribute("aria-label", `Rol de ${usuario.username}`);
    roles.forEach((rol) => {
        const opcion = crear("option", null, rol);
        opcion.value = rol;
        opcion.selected = rol === usuario.nombre_rol;
        selector.append(opcion);
    });
    selector.disabled = esYo;
    selector.addEventListener("change", () => cambiarRol(usuario, selector));

    const boton = crear("button", "filtro", usuario.activo ? "Bloquear" : "Desbloquear");
    boton.type = "button";
    boton.disabled = esYo;
    boton.addEventListener("click", () => cambiarEstado(usuario, boton));

    const acciones = crear("div", "tabla__acciones");
    acciones.append(esYo ? crear("span", "nota", "Tu cuenta") : boton);

    return fila([
        { texto: usuario.username },
        { nodo: selector },
        { nodo: etiquetaEstado(usuario.activo ? "Activo" : "Bloqueado", !usuario.activo) },
        { texto: usuario.fecha_creacion ? fecha.format(new Date(usuario.fecha_creacion)) : "—" },
        { nodo: acciones }
    ]);
}

function reemplazarUsuario(actualizado) {
    usuarios = usuarios.map((u) => (u.id_usuario === actualizado.id_usuario ? actualizado : u));
    pintarUsuarios();
}

async function cambiarRol(usuario, selector) {
    selector.disabled = true;
    try {
        const actualizado = await pedir(`/usuarios/${usuario.id_usuario}/rol`, {
            method: "PUT",
            body: JSON.stringify({ nuevoRol: selector.value })
        });
        reemplazarUsuario(actualizado);
        mensajeUsuarios(`${actualizado.username} ahora tiene el rol ${actualizado.nombre_rol}.`);
    } catch (error) {
        selector.value = usuario.nombre_rol;
        selector.disabled = false;
        mensajeUsuarios(`No se ha cambiado el rol: ${error.message}`);
    }
}

async function cambiarEstado(usuario, boton) {
    boton.disabled = true;
    try {
        const actualizado = await pedir(`/usuarios/${usuario.id_usuario}/bloquear`, { method: "PUT" });
        reemplazarUsuario(actualizado);
        mensajeUsuarios(`${actualizado.username} está ${actualizado.activo ? "activo" : "bloqueado"}.`);
    } catch (error) {
        boton.disabled = false;
        mensajeUsuarios(`No se ha cambiado el acceso: ${error.message}`);
    }
}
