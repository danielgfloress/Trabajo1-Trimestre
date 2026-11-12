const parametros = new URLSearchParams(window.location.search);
const id = parametros.get("id");
let productoActual = null;
let stockPorTalla = {};

document.getElementById("form-cesta").addEventListener("submit", anadirProducto);
document.getElementById("talla").addEventListener("change", actualizarCantidades);

cargarProducto();

async function cargarProducto() {
    if (!id) {
        mostrarError("No se ha indicado ningún producto.");
        return;
    }
    try {
        const respuesta = await fetch(API + "/productos/" + encodeURIComponent(id));
        if (respuesta.status === 404) {
            mostrarError("No hemos encontrado este producto.");
            return;
        }
        if (!respuesta.ok) {
            throw new Error("La API respondió con el código " + respuesta.status);
        }
        const producto = await respuesta.json();
        mostrarProducto(producto);
    } catch (error) {
        console.error(error);
        mostrarError("No se ha podido conectar con el servidor. Inténtalo más tarde.");
    }
}

function formatearMarca(marca) {
    return marca.toLowerCase().replace(/\b\w/g, (letra) => letra.toUpperCase());
}

function mostrarProducto(p) {
    productoActual = p;
    const precio = Number(p.precio_base).toLocaleString("es-ES", { style: "currency", currency: "EUR" });
    const marca = formatearMarca(p.marca);
    const nombreCompleto = marca + " " + p.nombre;
    const nombreConColor = nombreCompleto + " en " + p.color_base.toLowerCase();

    document.title = nombreCompleto + " · D3 Kicks";
    document.querySelector('meta[name="description"]').setAttribute("content", nombreConColor + ".");

    const foto = document.getElementById("producto-foto");
    foto.src = "../" + p.imagen;
    foto.alt = nombreConColor;

    document.getElementById("migas-nombre").textContent = p.nombre;
    document.getElementById("producto-marca").textContent = marca + " · " + p.categoria;
    document.getElementById("producto-nombre").textContent = p.nombre;
    document.getElementById("producto-color").textContent = p.color_base;
    document.getElementById("producto-precio").textContent = precio;
    document.getElementById("producto-descripcion").textContent = p.descripcion;

    document.getElementById("detalle-marca").textContent = marca;
    document.getElementById("detalle-modelo").textContent = p.nombre;
    document.getElementById("detalle-color").textContent = p.color_base;
    document.getElementById("detalle-categoria").textContent = p.categoria;

    mostrarTallas(p.tallas);
}

function mostrarTallas(tallas) {
    const select = document.getElementById("talla");
    select.innerHTML = "";

    stockPorTalla = {};
    for (const t of tallas) {
        stockPorTalla[t.talla] = t.stock;
        const opcion = document.createElement("option");
        opcion.value = t.talla;
        opcion.textContent = t.stock > 0 ? t.talla : t.talla + " (agotada)";
        opcion.disabled = t.stock === 0;
        if (t.talla === 42 && t.stock > 0) {
            opcion.selected = true;
        }
        select.appendChild(opcion);
    }
    actualizarCantidades();
}

function disponibleParaAnadir(talla) {
    const stock = stockPorTalla[talla] || 0;
    const enCesta = cantidadEnCesta(productoActual.codigo_modelo, talla);
    return Math.max(0, Math.min(stock, MAXIMO_POR_TALLA) - enCesta);
}

function actualizarCantidades() {
    if (!productoActual) {
        return;
    }
    const talla = Number(document.getElementById("talla").value);
    const maximo = disponibleParaAnadir(talla);
    const cantidad = document.getElementById("cantidad");
    cantidad.innerHTML = "";
    for (let n = 1; n <= Math.max(maximo, 1); n++) {
        const opcion = document.createElement("option");
        opcion.value = n;
        opcion.textContent = n;
        cantidad.appendChild(opcion);
    }
    const personal = esPersonalInterno();
    cantidad.disabled = maximo === 0 || personal;
    document.getElementById("boton-cesta").disabled = maximo === 0 || personal;
    if (personal) {
        document.getElementById("cesta-aviso").textContent =
            "Las cuentas de gestión no hacen pedidos. Para comprar, entra con una cuenta de cliente.";
    } else {
        document.getElementById("cesta-aviso").textContent = maximo === 0 && talla
            ? "Ya tienes en la cesta todos los pares disponibles de esta talla."
            : "";
    }
}

function anadirProducto(evento) {
    evento.preventDefault();
    const talla = Number(document.getElementById("talla").value);
    const cantidad = Number(document.getElementById("cantidad").value);
    if (!productoActual || !talla || cantidad > disponibleParaAnadir(talla)) {
        return;
    }
    anadirACesta(productoActual, talla, cantidad);
    actualizarCantidades();

    const aviso = document.getElementById("cesta-aviso");
    const enlace = document.createElement("a");
    enlace.href = "cesta.html";
    enlace.className = "enlace-destacado";
    enlace.textContent = "Ver la cesta";
    aviso.replaceChildren(`Añadido a la cesta: ${cantidad} ${cantidad === 1 ? "par" : "pares"} de la talla ${talla}. `, enlace);
}

function mostrarError(mensaje) {
    document.title = "Producto no encontrado · D3 Kicks";
    document.getElementById("migas-nombre").textContent = "Producto no encontrado";
    document.getElementById("producto-error-texto").textContent = mensaje;

    document.getElementById("producto-ficha").remove();
    document.getElementById("producto-error").hidden = false;
}
