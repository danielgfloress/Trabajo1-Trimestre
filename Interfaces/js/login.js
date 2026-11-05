document.getElementById("form-login").addEventListener("submit", async (evento) => {
    evento.preventDefault(); // Evita que la página recargue como en los 90

    const errorParrafo = document.getElementById("login-error");
    errorParrafo.hidden = true; // Ocultamos errores anteriores por si acaso

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

        // ¡Éxito! Guardamos el token y los datos del usuario
        guardarSesion({ token: datos.token, ...datos.usuario }, recordar);

        // Redirigimos a su cuenta o al panel de admin dependiendo de su rol
        location.href = paginaDeInicio(datos.usuario.rol);

    } catch (error) {
        // Mostramos el mensaje de error en el párrafo rojo que preparaste
        errorParrafo.textContent = error.message;
        errorParrafo.hidden = false;
    }
});