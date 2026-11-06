document.addEventListener("DOMContentLoaded", async () => {
    const contenedor = document.getElementById("contenedor-usuarios");

    try {
        const sesionString = localStorage.getItem("usuario") || sessionStorage.getItem("usuario");
        if (!sesionString) throw new Error("No hay sesión guardada en el navegador");

        const sesion = JSON.parse(sesionString);
        const token = sesion.token;

        const respuesta = await fetch(API + "/usuarios", {
            method: "GET",
            headers: {
                "Authorization": `Bearer ${token}`
            }
        });

        const datos = await respuesta.json();

        if (!respuesta.ok) {
            throw new Error(datos.error || "Error desconocido del servidor");
        }

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
            const estado = u.activo ? '<span style="color: #4ade80;">Activo</span>' : '<span style="color: #f87171;">Inactivo</span>';
            html += `
                <tr style="border-bottom: 1px solid #333;">
                    <td style="padding: 10px;"><strong>${u.username}</strong></td>
                    <td style="padding: 10px;">${u.id_rol}</td>
                    <td style="padding: 10px;">${estado}</td>
                    <td style="padding: 10px;">
                        <button class="boton boton--pequeno" style="padding: 5px 10px; font-size: 0.8rem;">Editar</button>
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