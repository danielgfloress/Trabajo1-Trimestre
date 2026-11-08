document.addEventListener("DOMContentLoaded", async () => {
    const contenedor = document.getElementById("contenedor-usuarios");

    try {
        const sesionString = localStorage.getItem("d3_sesion") || sessionStorage.getItem("d3_sesion");
        if (!sesionString) throw new Error("No hay sesión guardada en el navegador");

        const sesion = JSON.parse(sesionString);

        // Forzamos la URL completa a tu API (puerto 3000)
        const respuesta = await fetch("http://localhost:3000/api/usuarios", {
            method: "GET",
            headers: {
                "Authorization": `Bearer ${sesion.token}`
            }
        });

        // PRIMERO comprobamos si hay error, ANTES de procesar los datos
        if (!respuesta.ok) {
            const textoHTML = await respuesta.text(); // Leemos el HTML de error del servidor
            console.error("El servidor devolvió:", textoHTML);
            throw new Error(`El backend devolvió un error ${respuesta.status}. Comprueba si la ruta existe en server.js.`);
        }

        const datos = await respuesta.json(); // Ahora sí es seguro convertir a JSON

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
                        <button class="boton boton--pequeno" onclick="cambiarEstado(${u.id_usuario}, ${!u.activo})" style="padding: 5px 10px; font-size: 0.8rem; background-color: ${u.activo ? '#ef4444' : '#10b981'};">
                            ${textoBotonEstado}
                        </button>
                    </td>
                </tr>
            `;
        });

        html += `</tbody></table>`;
        contenedor.innerHTML = html;

    } catch (error) {
        contenedor.innerHTML = `<p class="formulario__error" style="display: block;">Error real: ${error.message}</p>`;
    }
});