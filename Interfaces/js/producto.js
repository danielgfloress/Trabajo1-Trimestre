// Dirección de la API (Docker la publica en el puerto 3000)
const API = "http://localhost:3000/api";

// 1. Leer el id de la dirección: producto.html?id=NIK-011
const parametros = new URLSearchParams(window.location.search);
const id = parametros.get("id");

cargarProducto();

// 2. Pedir el producto a la API
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

// En la base de datos las marcas están en mayúsculas: NIKE -> Nike, NEW BALANCE -> New Balance
function formatearMarca(marca) {
    return marca.toLowerCase().replace(/\b\w/g, (letra) => letra.toUpperCase());
}

// 3. Pintar el producto en la página
function mostrarProducto(p) {
    // pg devuelve los NUMERIC como texto: se pasa a número antes de formatear
    const precio = Number(p.precio_base).toLocaleString("es-ES", { style: "currency", currency: "EUR" });
    const marca = formatearMarca(p.marca);
    const nombreCompleto = marca + " " + p.nombre;
    const nombreConColor = nombreCompleto + " en " + p.color_base.toLowerCase();

    // Pestaña del navegador y descripción para buscadores
    document.title = nombreCompleto + " · D3 Kicks";
    document.querySelector('meta[name="description"]').setAttribute("content", nombreConColor + ".");

    // Foto: las rutas de la base de datos empiezan en Interfaces/, y esta página está en paginas/
    const foto = document.getElementById("producto-foto");
    foto.src = "../" + p.imagen;
    foto.alt = nombreConColor;

    // Textos (siempre con textContent, nunca con innerHTML)
    document.getElementById("migas-nombre").textContent = p.nombre;
    document.getElementById("producto-marca").textContent = marca + " · " + p.categoria;
    document.getElementById("producto-nombre").textContent = p.nombre;
    document.getElementById("producto-color").textContent = p.color_base;
    document.getElementById("producto-precio").textContent = precio;
    document.getElementById("producto-descripcion").textContent = p.descripcion;

    // Tabla de detalles
    document.getElementById("detalle-marca").textContent = marca;
    document.getElementById("detalle-modelo").textContent = p.nombre;
    document.getElementById("detalle-color").textContent = p.color_base;
    document.getElementById("detalle-categoria").textContent = p.categoria;

    mostrarTallas(p.tallas);
}

// 4. Rellenar el desplegable con el stock real de cada talla
function mostrarTallas(tallas) {
    const select = document.getElementById("talla");
    select.innerHTML = "";

    for (const t of tallas) {
        const opcion = document.createElement("option");
        opcion.value = t.talla;
        opcion.textContent = t.stock > 0 ? t.talla : t.talla + " (agotada)";
        opcion.disabled = t.stock === 0;
        if (t.talla === 42 && t.stock > 0) {
            opcion.selected = true;
        }
        select.appendChild(opcion);
    }
}

function mostrarError(mensaje) {
    document.title = "Producto no encontrado · D3 Kicks";
    document.getElementById("migas-nombre").textContent = "Producto no encontrado";
    document.getElementById("producto-error-texto").textContent = mensaje;

    // La ficha se borra en vez de ocultarse: .ficha tiene display: grid en el CSS
    // y eso le gana al atributo hidden, así que se seguiría viendo vacía.
    document.getElementById("producto-ficha").remove();
    document.getElementById("producto-error").hidden = false;
}
