const volverRegistro = new URLSearchParams(location.search).get("volver");
const destinoValido = volverRegistro && /^[a-z-]+\.html$/.test(volverRegistro) ? volverRegistro : null;

if (destinoValido) {
    document.getElementById("enlace-login").href = "login.html?volver=" + destinoValido;
}

document.getElementById("form-registro").addEventListener("submit", async (evento) => {
    evento.preventDefault();

    const errorParrafo = document.getElementById("registro-error");
    errorParrafo.hidden = true;

    const nombre = document.getElementById("registro_nombre").value.trim();
    const email = document.getElementById("registro_email").value.trim();
    const contrasena = document.getElementById("registro_contrasena").value;
    const repetir = document.getElementById("registro_repetir").value;
    const boton = evento.submitter;

    try {
        if (contrasena !== repetir) {
            throw new Error("Las contraseñas no coinciden");
        }

        boton.disabled = true;

        const respuesta = await fetch(API + "/registro", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ nombre, email, contrasena })
        });
        const datos = await respuesta.json();
        if (!respuesta.ok) {
            throw new Error(datos.error || "Error al crear la cuenta");
        }

        const acceso = await fetch(API + "/login", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ usuario: email, contrasena })
        });
        const sesion = await acceso.json();
        if (!acceso.ok) {
            location.href = "login.html" + (destinoValido ? "?volver=" + destinoValido : "");
            return;
        }

        guardarSesion({ token: sesion.token, ...sesion.usuario }, false);
        location.href = destinoValido || "../index.html";

    } catch (error) {
        errorParrafo.textContent = error.message;
        errorParrafo.hidden = false;
        boton.disabled = false;
    }
});
