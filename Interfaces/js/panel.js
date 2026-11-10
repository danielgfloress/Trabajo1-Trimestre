document.addEventListener("DOMContentLoaded", async () => {
    const contenedor = document.getElementById("contenedor-usuarios");

    try {
        // En tu código del login lo guardabas como un string directo o un JSON, 
        // comprobamos ambas formas para evitar errores.
        let token = localStorage.getItem("d3_sesion") || sessionStorage.getItem("d3_sesion");
        if (!token) throw new Error("No hay sesión guardada en el navegador");

        // Si guardaste el token como JSON (ej: { token: "..." }), lo extraemos
        if (token.startsWith("{")) {
            token = JSON.parse(token).token;
        }

        const respuesta = await fetch("http://localhost:3000/api/usuarios", {
            method: "GET",
            headers: {
                "Authorization": `Bearer ${token}`
            }
        });

        if (!respuesta.ok) {
            const textoHTML = await respuesta.text();
            console.error("El servidor devolvió:", textoHTML);
            throw new Error(`El backend devolvió un error ${respuesta.status}. Comprueba si la ruta existe en server.js.`);
        }

        const datos = await respuesta.json();

        let html = `
            <table style="width: 100%; text-align: left; border-collapse: collapse; margin-top: 20px;">
                <thead>
                    <tr style="border-bottom: 2px solid #fff;">
                        <th style="padding: 10px;">Usuario</th>
                        <th style="padding: 10px;">Rol</th>
                        <th style="padding: 10px;">Estado</th>
                        <th style="padding: 10px;">Acciones</th>
                    </tr>
                </thead>
                <tbody>
        `;

        datos.forEach(u => {
            const estado = u.activo ? '<span style="color: #4ade80;">Activo</span>' : '<span style="color: #f87171;">Bloqueado</span>';
            const textoBotonEstado = u.activo ? 'Bloquear' : 'Desbloquear';

            html += `
                <tr style="border-bottom: 1px solid #333;">
                    <td style="padding: 10px;"><strong>${u.username}</strong></td>
                    <td style="padding: 10px;">${u.nombre_rol}</td>
                    <td style="padding: 10px;">${estado}</td>
                    <td style="padding: 10px; display: flex; gap: 10px;">
                        <!-- Botón para cambiar rol -->
                        <button class="boton boton--pequeno" onclick="cambiarRol(${u.id_usuario})" style="padding: 5px 10px; font-size: 0.8rem; background-color: #3b82f6;">Rol</button>
                        
                        <!-- Botón para activar/desactivar -->
                        <button class="boton boton--pequeno" onclick="cambiarEstado(${u.id_usuario})" style="padding: 5px 10px; font-size: 0.8rem; background-color: ${u.activo ? '#ef4444' : '#10b981'};">
                            ${textoBotonEstado}
                        </button>
                    </td>
                </tr>
            `;
        });

        html += `</tbody></table>`;
        contenedor.innerHTML = html;

    } catch (error) {
        contenedor.innerHTML = `<p class="formulario__error" style="color: red; display: block;">Error real: ${error.message}</p>`;
    }
});

// FUNCIONES GLOBALES PARA LOS BOTONES
window.cambiarRol = async function (idUsuario) {
    const nuevoRol = prompt("Escribe el nuevo rol (ADMIN, COMERCIAL, o USUARIO):");
    if (!nuevoRol) return;

    let token = localStorage.getItem("d3_sesion") || sessionStorage.getItem("d3_sesion");
    if (token && token.startsWith("{")) token = JSON.parse(token).token;

    try {
        const respuesta = await fetch(`http://localhost:3000/api/usuarios/${idUsuario}/rol`, {
            method: "PUT",
            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${token}`
            },
            body: JSON.stringify({ nuevoRol: nuevoRol.trim().toUpperCase() })
        });

        if (respuesta.ok) {
            location.reload();
        } else {
            const error = await respuesta.json();
            alert("Error: " + error.error);
        }
    } catch (error) {
        console.error("Error al cambiar rol:", error);
    }
};

window.cambiarEstado = async function (idUsuario) {
    const confirmar = confirm("¿Seguro que quieres cambiar el estado de acceso de este usuario?");
    if (!confirmar) return;

    let token = localStorage.getItem("d3_sesion") || sessionStorage.getItem("d3_sesion");
    if (token && token.startsWith("{")) token = JSON.parse(token).token;

    try {
        const respuesta = await fetch(`http://localhost:3000/api/usuarios/${idUsuario}/bloquear`, {
            method: "PUT",
            headers: {
                "Authorization": `Bearer ${token}`
            }
        });

        if (respuesta.ok) {
            location.reload();
        } else {
            const error = await respuesta.json();
            alert("Error: " + error.error);
        }
    } catch (error) {
        console.error("Error al cambiar estado:", error);
    }
};