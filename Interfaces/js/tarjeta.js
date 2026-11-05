function formatearMarca(marca) {
    return marca.toLowerCase().replace(/\b\w/g, (letra) => letra.toUpperCase());
}

function crearElemento(etiqueta, clase, texto) {
    const elemento = document.createElement(etiqueta);
    elemento.className = clase;
    if (texto !== undefined) {
        elemento.textContent = texto;
    }
    return elemento;
}

function crearTarjeta(p, raiz) {
    const marca = formatearMarca(p.marca);
    const precio = Number(p.precio_base).toLocaleString("es-ES", { style: "currency", currency: "EUR" });

    const li = crearElemento("li", "producto");
    li.dataset.categoria = p.categoria;

    const enlace = crearElemento("a", "producto__enlace");
    enlace.href = raiz + "paginas/producto.html?id=" + encodeURIComponent(p.codigo_modelo);

    const foto = crearElemento("img", "producto__foto");
    foto.src = raiz + p.imagen;
    foto.alt = marca + " " + p.nombre + " en " + p.color_base.toLowerCase();

    enlace.appendChild(foto);
    enlace.appendChild(crearElemento("p", "producto__marca", marca));
    enlace.appendChild(crearElemento("h3", "producto__nombre", p.nombre));
    enlace.appendChild(crearElemento("p", "producto__color", p.color_base));
    enlace.appendChild(crearElemento("p", "producto__precio", precio));

    li.appendChild(enlace);
    return li;
}
