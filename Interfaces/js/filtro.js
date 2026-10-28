const botones = document.querySelectorAll(".filtro");
const selectDeporte = document.getElementById("filtro-deporte");
const sinResultados = document.getElementById("sin-resultados");
const productos = document.querySelectorAll(".producto");
const parametros = new URLSearchParams(window.location.search);
let marcasElegidas = [];

function filtrar() {
    const deporte = selectDeporte.value;
    let visibles = 0;

    productos.forEach((producto) => {
        const marca = producto.querySelector(".producto__marca").textContent;
        const cumpleMarca = marcasElegidas.length === 0 || marcasElegidas.includes(marca);
        const cumpleDeporte = deporte === "todos" || producto.dataset.categoria === deporte;
        producto.hidden = !(cumpleMarca && cumpleDeporte);

        if (!producto.hidden) {
            visibles++;
        }
    });

    botones.forEach((boton) => {
        const marca = boton.dataset.marca;
        const activo = marca === "todas" ? marcasElegidas.length === 0 : marcasElegidas.includes(marca);
        boton.classList.toggle("filtro--activo", activo);
        boton.setAttribute("aria-pressed", activo);
    });

    selectDeporte.classList.toggle("filtro-select--activo", deporte !== "todos");
    sinResultados.hidden = visibles > 0;
}

botones.forEach((boton) => {
    boton.addEventListener("click", () => {
        const marca = boton.dataset.marca;

        if (marca === "todas") {
            marcasElegidas = [];
        } else if (marcasElegidas.includes(marca)) {
            marcasElegidas = marcasElegidas.filter((m) => m !== marca);
        } else {
            marcasElegidas.push(marca);
        }

        filtrar();
    });
});

selectDeporte.addEventListener("change", filtrar);

const marcaInicial = parametros.get("marca");
if (marcaInicial && Array.from(botones).some((boton) => boton.dataset.marca === marcaInicial)) {
    marcasElegidas.push(marcaInicial);
}

filtrar();
