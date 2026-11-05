const API = "http://localhost:3000/api";
const CLAVE_SESION = "d3_sesion";

function obtenerSesion() {
    try {
        const guardada = localStorage.getItem(CLAVE_SESION) || sessionStorage.getItem(CLAVE_SESION);
        return guardada ? JSON.parse(guardada) : null;
    } catch {
        return null;
    }
}

function guardarSesion(sesion, recordar) {
    const almacen = recordar ? localStorage : sessionStorage;
    almacen.setItem(CLAVE_SESION, JSON.stringify(sesion));
}

function cerrarSesion() {
    localStorage.removeItem(CLAVE_SESION);
    sessionStorage.removeItem(CLAVE_SESION);
}

function paginaDeInicio(rol) {
    return rol === "USUARIO" ? "cuenta.html" : "panel.html";
}

async function fetchConSesion(ruta, opciones = {}) {
    const sesion = obtenerSesion();
    const cabeceras = { "Content-Type": "application/json", ...(opciones.headers || {}) };
    if (sesion) {
        cabeceras.Authorization = "Bearer " + sesion.token;
    }

    const respuesta = await fetch(API + ruta, { ...opciones, headers: cabeceras });
    if (respuesta.status === 401 && sesion) {
        cerrarSesion();
    }
    return respuesta;
}

function actualizarMenu() {
    const enlace = document.querySelector(".menu__icono");
    const sesion = obtenerSesion();
    if (!enlace || !sesion) {
        return;
    }

    const carpeta = location.pathname.includes("/paginas/") ? "" : "paginas/";
    enlace.href = carpeta + paginaDeInicio(sesion.rol);
    enlace.lastChild.textContent = sesion.username;
    enlace.setAttribute("aria-label", "Mi cuenta");
    enlace.title = "Mi cuenta";

    const salir = document.createElement("a");
    salir.href = "#";
    salir.className = "menu__enlace";
    salir.textContent = "Cerrar sesión";
    salir.addEventListener("click", (evento) => {
        evento.preventDefault();
        cerrarSesion();
        location.href = (carpeta === "" ? "../" : "") + "index.html";
    });
    enlace.after(salir);
}

actualizarMenu();