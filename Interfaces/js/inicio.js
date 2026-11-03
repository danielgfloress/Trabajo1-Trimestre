const DESTACADOS = ["D3-001", "JOR-005", "NIK-010", "NIK-008"];

const destacados = document.getElementById("destacados");
const estadoDestacados = document.getElementById("destacados-estado");

cargarDestacados();

async function cargarDestacados() {
    try {
        const respuesta = await fetch(API + "/productos");
        if (!respuesta.ok) {
            throw new Error("La API respondió con el código " + respuesta.status);
        }
        const productos = await respuesta.json();

        for (const codigo of DESTACADOS) {
            const producto = productos.find((p) => p.codigo_modelo === codigo);
            if (producto) {
                destacados.appendChild(crearTarjeta(producto, ""));
            }
        }

        estadoDestacados.hidden = true;
    } catch (error) {
        console.error(error);
        estadoDestacados.textContent = "No se han podido cargar los productos. Inténtalo más tarde.";
    }
}
