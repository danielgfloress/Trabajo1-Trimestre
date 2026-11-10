document.getElementById("form-login").addEventListener("submit", async (evento) => {
    evento.preventDefault();

    const errorParrafo = document.getElementById("login-error");
    errorParrafo.hidden = true;

    const usuario = document.getElementById("login_usuario").value;
    const contrasena = document.getElementById("login_contrasena").value;
    const recordar = document.getElementById("login_recordar").checked;

    try {
        const respuesta = await fetch(API + "/login", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ usuario, contrasena })
        });

        const datos = await respuesta.json();

        if (!respuesta.ok) {
            throw new Error(datos.error || "Error al iniciar sesión");
        }

        guardarSesion({ token: datos.token, ...datos.usuario }, recordar);

        location.href = "../index.html";

    } catch (error) {
        errorParrafo.textContent = error.message;
        errorParrafo.hidden = false;
    }
});