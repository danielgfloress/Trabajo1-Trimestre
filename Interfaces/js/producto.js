// Rellena paginas/producto.html con el producto que llega en la dirección.
// Ejemplo: producto.html?id=NIK-001
// Los datos salen de la lista PRODUCTOS (js/productos.js), que se carga antes que este archivo.

// 1. Leer el id de la dirección
const parametros = new URLSearchParams(window.location.search);
const id = parametros.get("id");

// 2. Buscar el producto
let producto = null;
if (typeof PRODUCTOS === "undefined") {
    console.error("No se ha cargado js/productos.js: la lista PRODUCTOS no existe.");
} else if (id) {
    producto = PRODUCTOS.find((p) => p.id === id);
}

// 3. Mostrar el producto o el mensaje de error
if (producto) {
    mostrarProducto(producto);
} else {
    mostrarError();
}

function mostrarProducto(p) {
    const precio = p.precio.toLocaleString("es-ES", { style: "currency", currency: "EUR" });
    const nombreCompleto = p.marca + " " + p.nombre;
    const nombreConColor = nombreCompleto + " en " + p.color.toLowerCase();

    // Pestaña del navegador y descripción para buscadores
    document.title = nombreCompleto + " · D3 Kicks";
    document.querySelector('meta[name="description"]').setAttribute("content", nombreConColor + ".");

    // Foto: las rutas de productos.js empiezan en Interfaces/, y esta página está en paginas/
    const foto = document.getElementById("producto-foto");
    foto.src = "../" + p.imagen;
    foto.alt = nombreConColor;

    // Textos (siempre con textContent, nunca con innerHTML)
    document.getElementById("migas-nombre").textContent = p.nombre;
    document.getElementById("producto-marca").textContent = p.marca + " · " + p.categoria;
    document.getElementById("producto-nombre").textContent = p.nombre;
    document.getElementById("producto-color").textContent = p.color;
    document.getElementById("producto-precio").textContent = precio;
    document.getElementById("producto-descripcion").textContent = p.descripcion;

    // Tabla de detalles
    document.getElementById("detalle-marca").textContent = p.marca;
    document.getElementById("detalle-modelo").textContent = p.nombre;
    document.getElementById("detalle-color").textContent = p.color;
    document.getElementById("detalle-categoria").textContent = p.categoria;
}

function mostrarError() {
    document.title = "Producto no encontrado · D3 Kicks";
    document.getElementById("migas-nombre").textContent = "Producto no encontrado";

    // La ficha se borra en vez de ocultarse: .ficha tiene display: grid en el CSS
    // y eso le gana al atributo hidden, así que se seguiría viendo vacía.
    document.getElementById("producto-ficha").remove();
    document.getElementById("producto-error").hidden = false;
}
