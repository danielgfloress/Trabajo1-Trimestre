const eurosCesta = new Intl.NumberFormat("es-ES", { style: "currency", currency: "EUR" });

document.getElementById("cesta-pedir").addEventListener("click", hacerPedido);
window.addEventListener("storage", pintarCesta);
pintarCesta();

function nombreMarca(marca) {
    return marca.toLowerCase().replace(/\b\w/g, (letra) => letra.toUpperCase());
}

function celda(contenido, clase) {
    const td = document.createElement("td");
    if (clase) {
        td.className = clase;
    }
    td.append(contenido);
    return td;
}

function pintarCesta() {
    const cesta = obtenerCesta();
    document.getElementById("cesta-vacia").hidden = cesta.length > 0;
    document.getElementById("cesta-llena").hidden = cesta.length === 0;
    if (cesta.length === 0) {
        return;
    }

    document.getElementById("cesta-lineas").replaceChildren(...cesta.map((linea, posicion) => {
        const producto = document.createElement("div");
        producto.className = "tabla__producto";
        const foto = document.createElement("img");
        foto.className = "tabla__foto";
        foto.src = "../" + linea.imagen;
        foto.alt = "";
        const texto = document.createElement("div");
        const enlace = document.createElement("a");
        enlace.href = "producto.html?id=" + encodeURIComponent(linea.codigo_modelo);
        enlace.className = "enlace-destacado";
        enlace.textContent = `${nombreMarca(linea.marca)} ${linea.nombre}`;
        const detalle = document.createElement("span");
        detalle.className = "tabla__detalle";
        detalle.textContent = linea.color;
        texto.append(enlace, detalle);
        producto.append(foto, texto);

        const cantidad = document.createElement("select");
        cantidad.className = "filtro-select";
        cantidad.setAttribute("aria-label", `Cantidad de ${linea.nombre}, talla ${linea.talla}`);
        for (let n = 1; n <= Math.max(MAXIMO_POR_TALLA, linea.cantidad); n++) {
            const opcion = document.createElement("option");
            opcion.value = n;
            opcion.textContent = n;
            opcion.selected = n === linea.cantidad;
            cantidad.append(opcion);
        }
        cantidad.addEventListener("change", () => cambiarCantidad(posicion, Number(cantidad.value)));

        const quitar = document.createElement("button");
        quitar.type = "button";
        quitar.className = "filtro";
        quitar.textContent = "Quitar";
        quitar.addEventListener("click", () => quitarLinea(posicion));

        const fila = document.createElement("tr");
        fila.append(
            celda(producto),
            celda(String(linea.talla), "tabla__numero"),
            celda(cantidad),
            celda(eurosCesta.format(linea.precio), "tabla__numero"),
            celda(eurosCesta.format(linea.precio * linea.cantidad), "tabla__numero"),
            celda(quitar)
        );
        return fila;
    }));

    const pares = paresEnCesta(cesta);
    document.getElementById("cesta-pares").textContent = pares;
    document.getElementById("cesta-total").textContent = eurosCesta.format(
        cesta.reduce((total, linea) => total + linea.precio * linea.cantidad, 0));
}

function cambiarCantidad(posicion, cantidad) {
    const cesta = obtenerCesta();
    cesta[posicion].cantidad = cantidad;
    guardarCesta(cesta);
    mensaje("");
    pintarCesta();
}

function quitarLinea(posicion) {
    const cesta = obtenerCesta();
    cesta.splice(posicion, 1);
    guardarCesta(cesta);
    mensaje("");
    pintarCesta();
}

function mensaje(texto) {
    document.getElementById("cesta-mensaje").textContent = texto;
}

function irAlLogin() {
    location.href = "login.html?volver=cesta.html";
}

async function hacerPedido() {
    const cesta = obtenerCesta();
    if (cesta.length === 0) {
        return;
    }
    if (!obtenerSesion()) {
        irAlLogin();
        return;
    }

    const boton = document.getElementById("cesta-pedir");
    boton.disabled = true;
    boton.textContent = "Enviando…";
    mensaje("");

    try {
        const respuesta = await fetchConSesion("/pedidos", {
            method: "POST",
            body: JSON.stringify({
                lineas: cesta.map((l) => ({ codigo_modelo: l.codigo_modelo, talla: l.talla, cantidad: l.cantidad }))
            })
        });
        if (respuesta.status === 401) {
            irAlLogin();
            return;
        }
        const datos = await respuesta.json().catch(() => ({}));
        if (!respuesta.ok) {
            throw new Error(datos.error || `La API respondió con el código ${respuesta.status}`);
        }

        guardarCesta([]);
        document.getElementById("cesta-llena").hidden = true;
        document.getElementById("cesta-hecho").hidden = false;
        document.getElementById("hecho-titulo").textContent = `Pedido ${datos.ref_odoo} confirmado`;
        document.getElementById("hecho-texto").textContent =
            `${datos.pares} ${Number(datos.pares) === 1 ? "par" : "pares"} por ${eurosCesta.format(Number(datos.importe_total))}. ` +
            "Es una compra simulada: no se ha cobrado nada y las zapatillas ya se han descontado del stock.";
    } catch (error) {
        mensaje(`No se ha podido hacer el pedido: ${error.message}`);
    } finally {
        boton.disabled = false;
        boton.textContent = "Hacer pedido";
    }
}
