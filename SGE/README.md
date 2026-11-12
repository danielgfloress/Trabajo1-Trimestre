# D3 Kicks · SGE · Sincronización de PostgreSQL con Odoo

Odoo 16 lleva las ventas, el inventario y la fabricación de D3 Kicks. La base de datos de PostgreSQL (`acesso-a-datos/`) es la que manda: todo lo que cambia en ella (desde la web, la API o una consulta directa) se copia a Odoo **al momento** a través de la API de Odoo (XML-RPC).

```
PostgreSQL ──trigger──▶ pg_notify('odoo') ──▶ sincronizador.py ──API XML-RPC──▶ Odoo
```

Odoo es un espejo: no escribe en PostgreSQL.

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
| `ODOO_URL` | dirección de Odoo, por ejemplo `http://10.7.15.236:8069` |
| `ODOO_DB` | nombre de la base de datos de Odoo |
| `ODOO_USER` | usuario de Odoo (el correo con el que se entra) |
| `ODOO_KEY` | clave de API de ese usuario |
| `PG_HOST` | `localhost` (solo sin Docker; el contenedor usa `db`) |
| `PG_PORT` | `5433` (solo sin Docker; el contenedor usa `5432`) |
| `ODOO_PG_PASSWORD` | contraseña de la base de datos interna de Odoo (solo para arrancar Odoo con el `docker-compose.yml` de esta carpeta) |

La clave de API se crea en Odoo: avatar → **Mi perfil** → **Seguridad de la cuenta** → **Nueva clave de API**.

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

## Arrancar Odoo en local (opcional)

Si no hay un Odoo en la red, esta carpeta tiene uno:

```powershell
cd SGE/odoo_d3kicks
docker compose --env-file ../../.env up -d
```

Queda en http://localhost:8069. Al crear la base de datos hay que instalar Ventas e Inventario.

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
