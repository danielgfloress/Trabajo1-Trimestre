# D3 Kicks · SGE · Sincronización de PostgreSQL con Odoo

Odoo 16 lleva las ventas, el inventario y la fabricación de D3 Kicks. La base de datos de PostgreSQL (`acesso-a-datos/`) es la que manda: todo lo que cambia en ella (desde la web, la API o una consulta directa) se copia a Odoo **al momento** a través de la API de Odoo (XML-RPC).

```
PostgreSQL ──trigger──▶ pg_notify('odoo') ──▶ sincronizador.py ──API XML-RPC──▶ Odoo
```

Odoo es un espejo: no escribe en PostgreSQL.

**Un Odoo para cada base de datos.** Cada persona del equipo tiene su propia base de datos PostgreSQL en su ordenador, así que cada una arranca también su propio Odoo y su sincronizador apunta a él. Si dos sincronizadores escriben en el mismo Odoo se pisan: los dos crean pedidos `SO0xx` y clientes `WEB0xx` con los mismos números pero distinto contenido, y cada uno sobrescribe el stock del otro.

## Cómo funciona

1. **En PostgreSQL**, `acesso-a-datos/06_odoo.sql` crea un trigger en `clientes`, `modelos`, `almacen` y `pedidos`. Cuando cambia una fila, envía un aviso con `pg_notify` en el canal `odoo`: `{"tabla": "pedidos", "id": 5}`.
2. **`sincronizador.py`** se queda escuchando ese canal (`LISTEN odoo`). Con cada aviso lee la fila de PostgreSQL y la crea o la actualiza en Odoo.
3. **Al arrancar** hace una pasada completa, así recupera lo que haya cambiado mientras estaba apagado.

Todas las operaciones se pueden repetir sin duplicar nada: primero se busca el registro en Odoo por su clave y solo se crea si no existe.

## Qué se copia

| PostgreSQL | Odoo | Clave para encontrarlo |
|---|---|---|
| `clientes` | Contactos (`res.partner`) | Referencia = `codigo_odoo` (`CLI001`…); los clientes registrados en la web, `WEB` + su id |
| `modelos` | Producto almacenable (`product.template`), sin impuestos | Referencia de sus variantes |
| `almacen` (talla y color) | Variante (`product.product`) con los atributos Talla y Color | Referencia = `CODIGO-TALLA-COLOR` (`ADI-010-42-Rojo y blanco`) |
| `almacen.stock_disponible` | Cantidad a mano en `WH/Stock` | La variante |
| `pedidos` y `lineas_pedido` | Pedido de venta (`sale.order`) | Número = `ref_odoo` (`SO005`) |
| `personalizaciones` (pedidos Custom) | Descripción de cada línea: nombre del diseño y texto bordado; el precio ya lleva el recargo | Las líneas de su pedido |

| Estado en PostgreSQL | En Odoo |
|---|---|
| `BORRADOR` | no se copia |
| `CONFIRMADO` | pedido de venta confirmado (se crea la entrega y, si el modelo tiene la ruta Fabricar, la orden de fabricación) |
| `ENTREGADO` | confirmado y con la entrega validada |
| `CANCELADO` | cancelado |

**Decisiones:**

- **Las líneas van sin IVA**, para que los totales de Odoo coincidan con los de PostgreSQL, la web y Python.
- **El stock de PostgreSQL manda.** PostgreSQL descuenta al confirmar y Odoo al entregar, así que después de validar una entrega se vuelve a copiar el stock de esas tallas.
- **No hay que crear pedidos a mano en Odoo con el mismo número `SO0xx`.** Los de Odoo usan su propia numeración (`S000xx`) y no chocan.

## Requisitos

- Docker, con la base de datos y la API (`docker compose up -d --build` desde la raíz).
- Un Odoo 16 con **Ventas** e **Inventario** instalados. El sincronizador activa solo las variantes de producto y crea los atributos Talla y Color.
- Python 3.12 o superior solo si se ejecuta sin Docker.

## Configuración

En el `.env` de la raíz del repositorio:

| Variable | Qué es |
|---|---|
| `ODOO_URL` | dirección de Odoo. Si Odoo está en el mismo ordenador: `http://host.docker.internal:8069` (así lo encuentra el contenedor; sin Docker, `http://localhost:8069`) |
| `ODOO_DB` | nombre de la base de datos de Odoo |
| `ODOO_USER` | usuario de Odoo (el correo con el que se entra) |
| `ODOO_KEY` | clave de API de ese usuario |
| `PG_HOST` | `localhost` (solo sin Docker; el contenedor usa `db`) |
| `PG_PORT` | `5433` (solo sin Docker; el contenedor usa `5432`) |
| `ODOO_PG_PASSWORD` | contraseña de la base de datos interna de Odoo (solo para arrancar Odoo con el `docker-compose.yml` de esta carpeta). Si Odoo ya tenía datos, tiene que ser la misma con la que se creó |

La clave de API se crea en Odoo: avatar → **Mi perfil** → **Seguridad de la cuenta** → **Nueva clave de API**.

Docker lee el `.env` solo al crear los contenedores. Después de cambiarlo hay que recrearlos con `docker compose up -d …`; `docker restart` y `docker compose restart` siguen usando los valores antiguos.

## Uso

El sincronizador es un contenedor más de Docker (`d3kicks-sincronizador`) y arranca solo con el resto, desde la raíz del repositorio:

```powershell
docker compose up -d --build
```

Al arrancar hace la pasada completa y luego se queda escuchando. Si se pierde la conexión con PostgreSQL u Odoo, lo vuelve a intentar cada 10 segundos. Si las variables `ODOO_…` del `.env` están vacías, no hace nada y se para.

| Para… | Comando |
|---|---|
| ver lo que va haciendo | `docker logs -f d3kicks-sincronizador` |
| pararlo | `docker compose stop sincronizador` |
| arrancarlo otra vez (hace una pasada completa) | `docker compose start sincronizador` |
| aplicar un cambio del `.env` | `docker compose up -d sincronizador` |

### Sin Docker (para desarrollar)

```powershell
cd SGE/odoo_d3kicks
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python sincronizador.py
```

Con `python sincronizador.py --una-vez` hace solo la pasada completa y termina. No lo ejecutes a la vez que el contenedor.

La primera pasada tarda unos minutos porque crea los 58 modelos con sus 638 variantes y su stock. Las siguientes solo cambian lo que sea distinto.

## Arrancar Odoo en tu ordenador

Esta carpeta tiene un Odoo 16 en Docker, con su propia base de datos interna (distinta de la del proyecto).

**1. Arrancarlo.** Siempre con `--env-file`, para que lea `ODOO_PG_PASSWORD` del `.env` de la raíz. Sin él, la contraseña queda vacía y Odoo no puede entrar en su base de datos:

```powershell
cd SGE/odoo_d3kicks
docker compose --env-file ../../.env up -d
```

Si se cambia el `.env`, hay que recrearlo: `docker compose --env-file ../../.env up -d --force-recreate`.

**2. Crear la base de datos** en http://localhost:8069 (solo la primera vez):

- Nombre: el mismo que `ODOO_DB` (`D3Kicks`).
- Correo y contraseña: los que se usarán para entrar; el correo va en `ODOO_USER`.
- Idioma español, país España y **sin** datos de demostración.

**3. Instalar** Ventas, Inventario y Fabricación, y crear la clave de API para `ODOO_KEY`.

**4. Rellenar el `.env`** con `ODOO_URL=http://host.docker.internal:8069`, `ODOO_DB`, `ODOO_USER` y `ODOO_KEY`, y desde la raíz ejecutar `docker compose up -d sincronizador`. En unos minutos Odoo tiene los clientes, los modelos, el stock y los pedidos.

> ⚠️ **No ejecutes nunca `docker compose down -v` en esta carpeta** ni borres sus volúmenes (`odoo_d3kicks_odoo-db-data` y `odoo_d3kicks_odoo-web-data`): se pierde todo lo hecho en Odoo, también lo que no viene de PostgreSQL (listas de materiales, rutas, órdenes de fabricación). Para pararlo basta con `docker compose stop`.
>
> Haz copias de seguridad de vez en cuando: en http://localhost:8069/web/database/manager → **Backup**, que descarga un `.zip`. Se recupera con **Restore**, marcando "This database was moved".

## Prueba de principio a fin

1. Arranca todo con `docker compose up -d --build` y deja abiertos los mensajes con `docker logs -f d3kicks-sincronizador`.
2. Entra en la web como cliente, añade unas tallas a la cesta y confirma el pedido.
3. En los mensajes sale `Pedido SO0xx: creado en Odoo` y `confirmado en Odoo`, y en **Ventas** de Odoo aparece el pedido confirmado, con el mismo total y sin IVA.
4. En **Inventario**, el stock de esas tallas es el mismo que en el panel de gestión de la web.
5. Cancela el pedido en PostgreSQL:

   ```sql
   UPDATE pedidos SET estado = 'CANCELADO' WHERE ref_odoo = 'SO0xx';
   ```

   En Odoo el pedido pasa a cancelado y el stock vuelve.

6. Haz un pedido desde **D3 Custom** (al menos 20 pares). En Odoo aparece con la descripción del diseño y el bordado en cada línea, y el precio con el recargo incluido.
