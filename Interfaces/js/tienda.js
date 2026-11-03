const galeria = document.getElementById("galeria");
const estado = document.getElementById("tienda-estado");

cargarTienda();

async function cargarTienda() {
    try {
        const respuesta = await fetch(API + "/productos");
        if (!respuesta.ok) {
            throw new Error("La API respondió con el código " + respuesta.status);
        }
        const productos = await respuesta.json();

        for (const p of productos) {
            galeria.appendChild(crearTarjeta(p, "../"));
        }

        estado.hidden = true;
        filtrar();
    } catch (error) {
        console.error(error);
        estado.textContent = "No se ha podido cargar la tienda. Inténtalo más tarde.";
    }
}
