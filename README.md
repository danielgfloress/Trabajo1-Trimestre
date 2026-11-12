# D3 Kicks · Sneaker Factory

Proyecto intermodular de 2.º DAM. D3 Kicks es una tienda de zapatillas que, además de vender modelos de catálogo, fabrica pedidos personalizados para clubes y equipos (línea **D3 Custom**). Cada módulo del curso resuelve una parte del negocio y todos trabajan con los mismos datos.

```
                    ┌──────────────────────────────┐
  Interfaces (web) ─┤  API Node/Express :3000      ├─ PostgreSQL :5433 (Acceso a Datos)
                    └──────────────────────────────┘          │
                                                              ├─ CSV ─▶ Python (análisis y dashboard)
                                                              └─ ficha CSV ─▶ PSP (procesos del taller)
  PostgreSQL ── pg_notify ─▶ sincronizador.py ── API XML-RPC ─▶ Odoo (ventas, inventario y fabricación)
```

## Estructura del repositorio

| Carpeta / archivo | Módulo | Qué contiene |
|---|---|---|
| [`acesso-a-datos/`](acesso-a-datos/README.md) | Acceso a Datos | base de datos PostgreSQL: tablas, triggers, permisos, consultas y datos de prueba |
| `backend/` | Acceso a Datos / Interfaces | API REST en Node.js que conecta la web con la base de datos |
| [`Interfaces/`](Interfaces/README.md) | Desarrollo de Interfaces | web de la tienda y panel de gestión (HTML, CSS y JavaScript) |
| [`python/`](python/README.md) | Ampliación de Python | limpieza de datos, indicadores, segmentación, predicción y dashboard Streamlit |
| [`psp/`](psp/README.md) | Programación de Servicios y Procesos | aplicación Java multiproceso que prepara las fichas de taller de los pedidos Custom |
| [`SGE/`](SGE/README.md) | Sistemas de Gestión Empresarial | sincronizador que copia a Odoo cada cambio de PostgreSQL, y Odoo en Docker |
| `compose.yaml` | — | levanta la base de datos y la API con Docker |
| `.env.example` | — | plantilla de las variables de entorno |
| `.gitignore` | — | lo que no se sube al repositorio |

## Requisitos

- Docker Desktop.
- Visual Studio Code con la extensión **Live Server** (para la web).
- Python 3.12 o superior (para la parte de Python).
- JDK 21 y Maven o IntelliJ IDEA (para PSP).
- Git Bash (para exportar los CSV de Python).

## Puesta en marcha

### 1. Variables de entorno

Copia la plantilla y rellénala. El archivo `.env` **no se sube** al repositorio.

```powershell
copy .env.example .env
```

| Variable | Para qué sirve |
|---|---|
| `POSTGRES_USER` | usuario de PostgreSQL |
| `POSTGRES_PASSWORD` | contraseña de PostgreSQL |
| `POSTGRES_DB` | nombre de la base de datos |
| `JWT_SECRET` | clave con la que la API firma las sesiones (cualquier texto largo y aleatorio) |

### 2. Base de datos y API

```powershell
docker compose up -d --build
```

Arranca tres contenedores:

| Contenedor | Puerto | Qué es |
|---|---|---|
| `d3kicks-db` | 5433 | PostgreSQL 17. La primera vez ejecuta solo los scripts de `acesso-a-datos/` |
| `d3kicks-api` | 3000 | API REST. Se comprueba en http://localhost:3000/api/salud |
| `d3kicks-sincronizador` | — | copia a Odoo cada cambio de PostgreSQL (si las variables `ODOO_…` del `.env` están rellenas) |

Para volver a los datos iniciales (borra todo lo que se haya hecho desde la web):

```powershell
docker compose down -v
docker compose up -d --build
```

### 3. Web

Abre `Interfaces/index.html` con **Live Server** en VS Code. Más detalles en [`Interfaces/README.md`](Interfaces/README.md).

### 4. Python

```powershell
cd python
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
streamlit run app_dashboard.py
```

Más detalles en [`python/README.md`](python/README.md).

### 5. PSP

Abre la carpeta `psp/` en IntelliJ IDEA y ejecuta `org.d3kicks.Coordinador` con el directorio de trabajo en `psp/`. Más detalles en [`psp/README.md`](psp/README.md).

### 6. Odoo

Rellena las variables `ODOO_…` del `.env` y vuelve a ejecutar `docker compose up -d --build`. El contenedor `d3kicks-sincronizador` copia a Odoo todo lo que cambia en PostgreSQL mientras Docker esté en marcha. Para ver lo que hace:

```powershell
docker logs -f d3kicks-sincronizador
```

Más detalles en [`SGE/README.md`](SGE/README.md).

## API

Todas las rutas empiezan por `http://localhost:3000/api`. Las marcadas con 🔒 necesitan la cabecera `Authorization: Bearer <token>` que devuelve el login; la sesión dura 8 horas.

| Método y ruta | Permiso | Qué hace |
|---|---|---|
| `GET /salud` | — | comprueba que la API responde |
| `GET /productos` | — | catálogo de modelos activos |
| `GET /productos/:codigo` | — | un modelo con sus tallas, colores y stock |
| `POST /login` | — | inicia sesión con `usuario` y `contrasena` y devuelve el token |
| `POST /registro` | — | crea una cuenta de cliente con `nombre`, `email` y `contrasena` |
| `GET /yo` | 🔒 | datos del usuario conectado |
| `POST /pedidos` | 🔒 cliente | crea y confirma un pedido desde la cesta (descuenta stock) |
| `GET /pedidos/mios` | 🔒 cliente | pedidos del cliente conectado |
| `GET /panel/resumen` | 🔒 `INDICADORES_VER` | indicadores del panel de gestión |
| `GET /panel/stock` | 🔒 `STOCK_CONSULTAR` | stock de todo el almacén, primero lo que hay que reponer |
| `GET /usuarios` | 🔒 `USUARIOS_GESTIONAR` | lista de usuarios |
| `GET /usuarios/roles` | 🔒 `USUARIOS_GESTIONAR` | lista de roles |
| `PUT /usuarios/:id/rol` | 🔒 `USUARIOS_GESTIONAR` | cambia el rol de un usuario |
| `PUT /usuarios/:id/bloquear` | 🔒 `USUARIOS_GESTIONAR` | bloquea o desbloquea un usuario |

## Roles

| Rol | Quién es | Qué puede hacer |
|---|---|---|
| `ADMIN` | administración | todo, incluida la gestión de usuarios |
| `COMERCIAL` | ventas | pedidos, stock e indicadores |
| `USUARIO` | cliente registrado en la web | comprar y ver sus propios pedidos |

Los usuarios de prueba son `admin` y `comercial1` (personal) y `laura.martin@example.com` (cliente). Las contraseñas se guardan cifradas con bcrypt y no se escriben en el repositorio. La matriz completa de permisos está en [`acesso-a-datos/README.md`](acesso-a-datos/README.md).

## Qué no se sube al repositorio

Lo indica el `.gitignore` de la raíz, junto con los de `python/` y `psp/`:

- `.env`, con las contraseñas reales.
- Dependencias que se instalan solas: `node_modules/` y el entorno virtual `.venv/` de Python.
- Archivos generados al compilar o ejecutar: `target/` de Java, cachés de Python y logs.
- Configuración personal de los editores y archivos del sistema operativo.
