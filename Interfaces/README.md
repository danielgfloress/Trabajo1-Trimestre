# D3 Kicks · Interfaces · Web de la tienda y panel de gestión

Web de D3 Kicks hecha con HTML, CSS y JavaScript sin librerías. Tiene dos partes:

- **La tienda**, para los clientes: catálogo con filtros, ficha de producto, cesta, pedidos, registro y cuenta.
- **El panel de gestión**, para el personal (`ADMIN` y `COMERCIAL`): indicadores, ventas, pedidos, stock y usuarios.

Todos los datos (productos, stock, pedidos y usuarios) llegan en vivo desde PostgreSQL a través de la API (`backend/`). La web no guarda datos propios, salvo la sesión y la cesta en el navegador.

## Cómo arrancarla

1. Arranca la base de datos y la API desde la raíz del repositorio (ver el [README general](../README.md)):

   ```powershell
   docker compose up -d --build
   ```

2. Abre `Interfaces/index.html` en VS Code y pulsa **Go Live** (extensión Live Server).

La dirección de la API está en la primera línea de `js/sesion.js`: `http://localhost:3000/api`.

## Estructura

```
Interfaces/
├── index.html          página de inicio
├── paginas/            el resto de páginas
├── css/estilos.css     todos los estilos
├── js/                 un archivo por página, más los compartidos
└── img/
    ├── marca/          logo y fotos de cabecera
    └── productos/      una imagen por modelo (58)
```

## Páginas

| Página | Qué hace | Scripts |
|---|---|---|
| `index.html` | portada con modelos destacados | `sesion.js`, `cesta.js`, `tarjeta.js`, `inicio.js` |
| `paginas/tienda.html` | catálogo con filtros por marca y por deporte | `sesion.js`, `cesta.js`, `filtro.js`, `tarjeta.js`, `tienda.js` |
| `paginas/producto.html` | ficha de un modelo: color, talla, cantidad y añadir a la cesta | `sesion.js`, `cesta.js`, `producto.js` |
| `paginas/cesta.html` | cesta y confirmación del pedido | `sesion.js`, `cesta.js`, `pedido.js` |
| `paginas/cuenta.html` | datos del cliente y sus pedidos | `sesion.js`, `cesta.js`, `cuenta.js` |
| `paginas/login.html` | inicio de sesión | `sesion.js`, `login.js` |
| `paginas/registro.html` | alta de clientes | `sesion.js`, `registro.js` |
| `paginas/panel.html` | panel de gestión | `sesion.js`, `panel.js` |
| `paginas/custom.html` | línea D3 Custom para clubes y formulario para hacer un pedido Custom | `sesion.js`, `cesta.js`, `custom.js` |
| `paginas/nosotros.html` | historia de la marca | `sesion.js`, `cesta.js` |
| `paginas/contacto.html` | contacto | `sesion.js`, `cesta.js` |

`sesion.js` se carga siempre el primero, porque los demás scripts usan la dirección de la API y la sesión que define.

## Scripts compartidos

| Script | Qué hace |
|---|---|
| `sesion.js` | guarda y lee la sesión, añade el token a las peticiones (`fetchConSesion`) y pinta el menú según el rol |
| `cesta.js` | guarda la cesta en el navegador (`localStorage`, clave `d3_cesta`), con un máximo de 10 pares por talla, y muestra el contador del menú |
| `tarjeta.js` | dibuja la tarjeta de un producto (la usan la portada y la tienda) |
| `filtro.js` | filtros del catálogo por marca y por deporte |

## Qué ve cada usuario

| Usuario | Menú | Puede comprar | Panel de gestión |
|---|---|---|---|
| Sin sesión | icono de persona que lleva al login | puede llenar la cesta; al confirmar se le pide iniciar sesión y vuelve a la cesta. En D3 Custom se le avisa de que tiene que iniciar sesión | no |
| Cliente (`USUARIO`) | icono de persona que lleva a su cuenta | sí, desde la cesta y desde D3 Custom: al confirmar se crea el pedido y se descuenta el stock | no |
| `COMERCIAL` | enlace **Gestión** | no (la cesta se oculta) | Resumen, Ventas, Pedidos y Stock |
| `ADMIN` | enlace **Gestión** | no (la cesta se oculta) | todo lo anterior y Usuarios |

## Panel de gestión

Tiene una barra lateral y cada sección se abre con una dirección propia (`panel.html#stock`, por ejemplo).

| Sección | Qué muestra |
|---|---|
| Resumen | cifras de las ventas válidas (confirmadas y entregadas) y actividad por estado |
| Ventas | facturación por mes y modelos más vendidos |
| Pedidos | los 8 pedidos más recientes, en cualquier estado |
| Stock | todo el almacén; lo que está por debajo del mínimo sale arriba y en rojo; se puede filtrar por modelo o ver solo lo que hay que reponer |
| Usuarios | cambiar el rol de un usuario y bloquearlo o desbloquearlo (solo `ADMIN`) |

Si la sesión caduca o el usuario no tiene permiso, el panel lo lleva al login.

## Pedidos desde la web

### Pedido estándar (cesta)

1. El cliente añade tallas a la cesta desde la ficha del producto.
2. En la cesta pulsa **Hacer pedido**.
3. La API (`POST /api/pedidos`) crea el pedido con la siguiente referencia libre (`SO0xx`) y lo confirma.
4. Los triggers de la base de datos calculan los precios y el total y descuentan el stock. Si no hay stock suficiente, el pedido no se crea y la web muestra el motivo.
5. El pedido aparece en **Mi cuenta** y en el panel de gestión.

### Pedido D3 Custom

1. En `custom.html` el cliente rellena el formulario: datos del club, modelo base (la lista se carga desde la API), colores, nombre del lateral (máximo 12 caracteres), escudo, indicaciones, pares de cada talla y fecha en que los necesita.
2. Mientras escribe, la web le dice cuántos pares lleva y cuántos le faltan para el mínimo de **20**.
3. Al pulsar **Enviar pedido**, la API (`POST /api/pedidos/custom`) guarda el diseño en `personalizaciones` y crea el pedido `CUSTOM` con una línea por talla, y lo confirma.
4. El precio de cada par es el precio del modelo más el recargo del diseño: **10 €**, o **15 €** si lleva escudo. Los triggers comprueban el mínimo de 20 pares y el stock de cada talla y lo descuentan. Si algo falla, el pedido no se crea y la web muestra el motivo.
5. El pedido aparece en **Mi cuenta**, en el panel de gestión y, si el sincronizador está en marcha, en Odoo.

Solo los clientes pueden hacer pedidos Custom. Si entra el personal (`ADMIN` o `COMERCIAL`), la página se lo avisa.
