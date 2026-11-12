const CLAVE_CESTA = "d3_cesta";
const MAXIMO_POR_TALLA = 10;

function obtenerCesta() {
    try {
        const guardada = JSON.parse(localStorage.getItem(CLAVE_CESTA));
        return Array.isArray(guardada) ? guardada : [];
    } catch {
        return [];
    }
}

function guardarCesta(cesta) {
    localStorage.setItem(CLAVE_CESTA, JSON.stringify(cesta));
    actualizarContadorCesta();
}

function paresEnCesta(cesta = obtenerCesta()) {
    return cesta.reduce((total, linea) => total + linea.cantidad, 0);
}

function cantidadEnCesta(codigo, talla) {
    const linea = obtenerCesta().find((l) => l.codigo_modelo === codigo && l.talla === talla);
    return linea ? linea.cantidad : 0;
}

function anadirACesta(producto, talla, cantidad) {
    const cesta = obtenerCesta();
    const linea = cesta.find((l) => l.codigo_modelo === producto.codigo_modelo && l.talla === talla);
    if (linea) {
        linea.cantidad += cantidad;
    } else {
        cesta.push({
            codigo_modelo: producto.codigo_modelo,
            marca: producto.marca,
            nombre: producto.nombre,
            color: producto.color_base,
            imagen: producto.imagen,
            precio: Number(producto.precio_base),
            talla,
            cantidad
        });
    }
    guardarCesta(cesta);
}

function actualizarContadorCesta() {
    const contador = document.getElementById("cesta-contador");
    if (!contador) {
        return;
    }
    if (esPersonalInterno()) {
        contador.parentElement.hidden = true;
        return;
    }
    const pares = paresEnCesta();
    contador.textContent = pares;
    contador.hidden = pares === 0;
    contador.parentElement.setAttribute("aria-label", pares ? `Cesta, ${pares} pares` : "Cesta vacía");
}

actualizarContadorCesta();
window.addEventListener("storage", actualizarContadorCesta);
