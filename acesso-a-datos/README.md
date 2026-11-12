# D3 Kicks · Acceso a Datos · Base de datos PostgreSQL

Base de datos del proyecto. Guarda el catálogo, el stock por talla y color, los clientes, los pedidos (también los personalizados D3 Custom), los usuarios con sus permisos y un registro de auditoría. Las reglas del negocio están **dentro de la base de datos** (triggers), así que se cumplen igual desde la web, la API o una consulta directa.

La usan la API (`backend/`), y a través de ella la web, Python (mediante CSV exportados) y PSP (mediante las fichas de los pedidos Custom).

## Archivos

| Archivo | Qué hace |
|---|---|
| `d3_kicks.sql` | crea las tablas, las relaciones, el índice y la vista `vista_ventas_por_modelo` |
| `02_triggers.sql` | triggers de precios, totales, stock y auditoría |
| `03_usuarios.sql` | roles, permisos, usuarios del personal y triggers de permisos |
| `04_consultas.sql` | consultas de ejemplo para el informe (no se carga al arrancar) |
| `05_datos.sql` | datos de prueba: catálogo, stock, clientes, diseños y pedidos |
| `d3_kicks.dbm` | modelo de la base de datos para abrir con pgModeler |

## Cómo se carga

No hace falta ejecutar nada a mano. Desde la raíz del repositorio:

```powershell
docker compose up -d --build
```

La primera vez, el contenedor `d3kicks-db` ejecuta los scripts en este orden: `d3_kicks.sql` → `02_triggers.sql` → `03_usuarios.sql` → `05_datos.sql`. Los datos se quedan guardados en un volumen de Docker.

Para empezar de cero con los datos iniciales:

```powershell
docker compose down -v
docker compose up -d --build
```

Para conectarse con DBeaver, pgAdmin o cualquier cliente: `localhost`, puerto **5433**, y el usuario, la contraseña y la base de datos del `.env`.

## Tablas

| Tabla | Qué guarda |
|---|---|
| `modelos` | catálogo: código, marca, nombre, categoría, precio base, si admite personalización, perfil e imagen |
| `almacen` | stock de cada modelo por talla (36 a 46) y color, con su stock mínimo |
| `clientes` | clubes, equipos y particulares, con su código de Odoo (`CLI001`…) |
| `personalizaciones` | diseños D3 Custom: colores, texto bordado (máx. 12 caracteres), escudo y recargo por par |
| `pedidos` | cabecera del pedido: referencia de Odoo (`SO001`…), cliente, fechas, tipo, estado e importe |
| `lineas_pedido` | modelo, talla y color pedidos, cantidad, precio y diseño si es Custom |
| `roles` | `ADMIN`, `COMERCIAL` y `USUARIO` |
| `permisos_rol` | qué operaciones puede hacer cada rol |
| `usuarios` | cuentas de acceso; las de clientes van unidas a su fila de `clientes` |
| `log_eventos` | auditoría: quién cambió qué pedido o línea, cuándo, y los datos de antes y después |

```
modelos ──< almacen ──< lineas_pedido >── pedidos >── clientes
                              │               │
                    personalizaciones      usuarios >── roles ──< permisos_rol
```

## Reglas que aplica la base de datos

**Precios y totales**

- El precio de cada línea lo pone la base de datos: precio base del modelo más el recargo del diseño si es Custom. Aunque se envíe otro precio, se sustituye.
- El total del pedido se recalcula solo cada vez que cambian sus líneas y no se puede modificar a mano.

**Pedidos**

- Un pedido nace en `BORRADOR`. Los cambios de estado permitidos son:

  ```
  BORRADOR ──▶ CONFIRMADO ──▶ ENTREGADO
      │             │
      └──▶ CANCELADO ◀┘
  ```

- Al **confirmar** se comprueba que haya stock de cada talla y se descuenta. Si falta en alguna, no se confirma nada.
- Al **cancelar** un pedido confirmado, el stock vuelve al almacén.
- Las líneas solo se pueden cambiar mientras el pedido está en borrador.
- Un pedido `CUSTOM` necesita al menos **20 pares**, todas sus líneas con diseño y modelos que admitan personalización. Un pedido `ESTANDAR` no puede llevar diseño.

**Permisos y auditoría**

- Cada cambio en pedidos, líneas, modelos o stock comprueba el permiso del usuario con `fn_tiene_permiso`. La API indica quién es el usuario con `set_config('app.id_usuario', ...)`.
- Un cliente (`USUARIO`) solo puede tocar sus propios pedidos.
- Todo cambio en pedidos y líneas se apunta en `log_eventos`.
- Las contraseñas se guardan cifradas con bcrypt (`pgcrypto`) y se comprueban con `fn_login`.

## Permisos por rol

| Operación | ADMIN | COMERCIAL | USUARIO |
|---|:---:|:---:|:---:|
| `PEDIDO_CONSULTAR` | ✅ | ✅ | ✅ (los suyos) |
| `PEDIDO_CREAR` | ✅ | ✅ | ✅ |
| `PEDIDO_EDITAR` | ✅ | ✅ | ✅ |
| `PEDIDO_CONFIRMAR` | ✅ | ✅ | ✅ |
| `PEDIDO_CANCELAR` | ✅ | ✅ | ❌ |
| `PEDIDO_ENTREGAR` | ✅ | ✅ | ❌ |
| `STOCK_CONSULTAR` | ✅ | ✅ | ✅ |
| `INDICADORES_VER` | ✅ | ✅ | ❌ |
| `DATOS_EXPORTAR` | ✅ | ✅ | ❌ |
| `AUDITORIA_VER` | ✅ | ❌ | ❌ |
| `USUARIOS_GESTIONAR` | ✅ | ❌ | ❌ |
| `USUARIOS_EXPORTAR` | ✅ | ❌ | ❌ |
| `PRODUCTO_EDITAR` | ✅ | ❌ | ❌ |
| `STOCK_EDITAR` | ✅ | ❌ | ❌ |

Usuarios de prueba: `admin` (`ADMIN`), `comercial1` (`COMERCIAL`) y `laura.martin@example.com` (`USUARIO`, cliente CLI006). Las contraseñas no se escriben en el repositorio.

## Datos de prueba

Después de cargar `05_datos.sql` la base de datos tiene:

| Dato | Cantidad |
|---|---|
| Modelos | 58, todos con imagen |
| Filas de stock (modelo, talla y color) | 638 |
| Clientes | 7 (3 clubes, 2 equipos y 2 particulares) |
| Diseños Custom | 4 |
| Pedidos | 12, de SO001 a SO012 |
| Ventas válidas (confirmadas y entregadas) | 8 pedidos, 96 pares y 12.876,88 € |

| Cliente | Código | Tipo |
|---|---|---|
| Club Halcones | CLI001 | Club |
| CD Leones del Sur | CLI002 | Club |
| CB Torres | CLI003 | Club |
| Fénix Boxing Gym | CLI004 | Equipo |
| Running Crew Sur | CLI005 | Equipo |
| Laura Martín Gil | CLI006 | Particular |
| Marcos Ruiz Vega | CLI007 | Particular |

| Pedido | Cliente | Tipo | Estado | Contenido |
|---|---|---|---|---|
| SO001 | CLI002 | Estándar | Entregado | Copa Pure II League FG, 18 pares |
| SO002 | CLI006 | Estándar | Entregado | Air Force 1 Low, 1 par |
| SO003 | CLI001 | Custom | Entregado | Runner X, 20 pares, diseño Halcones Training |
| SO004 | CLI005 | Estándar | Entregado | Runner X y ZoomX Invincible 3, 7 pares |
| SO005 | CLI002 | Custom | Confirmado | Predator League FG, 20 pares, diseño Leones Matchday |
| SO006 | CLI003 | Custom | Cancelado | Team Hustle D 11, 20 pares, diseño Torres Basket |
| SO007 | CLI001 | Estándar | Entregado | Dunk Low, 2 pares |
| SO008 | CLI004 | Estándar | Confirmado | HyperKO 2 y Elite, 8 pares |
| SO009 | CLI006 | Estándar | Cancelado | 550, 1 par |
| SO010 | CLI005 | Custom | Confirmado | ZoomX Invincible 3, 20 pares, diseño Crew Sur |
| SO011 | CLI003 | Estándar | Borrador | OMN1S, 5 pares |
| SO012 | CLI007 | Estándar | Borrador | XT-6, 2 pares |

Los pedidos se cargan siguiendo el camino real (borrador → confirmado → entregado o cancelado), así que los triggers calculan los precios, descuentan el stock y dejan la auditoría igual que si se hubieran hecho a mano. Las referencias y los códigos de cliente son los mismos que en Odoo.

## Relación con los demás módulos

| Módulo | Cómo usa la base de datos |
|---|---|
| API y web | lee y escribe a través de la API (`backend/`), que se conecta como el usuario del `.env` |
| Python | `python/scripts/exportar_acc.sh` exporta las tablas a CSV en `python/entrada_acc/` |
| PSP | las fichas de `psp/entrada/` son los pedidos Custom SO003, SO005 y SO010 |
| Odoo | mismas referencias de pedido (`SO0xx`) y de cliente (`CLI0xx`) |
