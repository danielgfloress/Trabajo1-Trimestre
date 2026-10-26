# Sneaker Factory · Modelo de datos común

> **Paso 0 del proyecto intermodular.** Este documento es el contrato que comparten todos los módulos:
> Web (Interfaces), Odoo (SGE), PSP, Acceso a Datos (ACC) y Ampliación de Python.
> Si un módulo necesita cambiar algo de aquí, se cambia **en este documento primero** y se avisa al resto.
>
> Versión 1.0 · 26/10/2026 · Todos los datos son **ficticios**.

---

## 1. Quién usa cada parte

| Sección | Web | Odoo | PSP | ACC | Python |
|---|:-:|:-:|:-:|:-:|:-:|
| 2. Identificadores | · | ✔ | ✔ | ✔ | ✔ |
| 3. Catálogo de modelos | ✔ | ✔ | · | ✔ | ✔ |
| 4. Personalización | ✔ | ✔ | ✔ | ✔ | · |
| 5. Clientes | · | ✔ | · | ✔ | ✔ |
| 6. Estados del pedido | ✔ | ✔ | · | ✔ | ✔ |
| 7. Pedidos de prueba | · | ✔ | ✔ | ✔ | ✔ |
| 8. Roles y usuarios | · | ✔ | · | ✔ | · |
| 9. Formato de ficheros | · | · | ✔ | ✔ | ✔ |

---

## 2. Identificadores comunes

Es la regla más importante: **el mismo pedido, cliente o modelo tiene el mismo código en todos los módulos.**

| Entidad | Formato | Ejemplo | En Odoo | En ACC (PostgreSQL) |
|---|---|---|---|---|
| Cliente | `CLI` + 3 dígitos | `CLI001` | Referencia interna del contacto | `clientes.codigo_odoo` |
| Modelo | `SF-` + código corto | `SF-RUNX` | Referencia interna del producto | `modelos.codigo_modelo` |
| Variante (SKU) | modelo-color-talla | `SF-RUNX-AZU-42` | Referencia interna de la variante | `codigo_modelo` + `color_base` + `talla` |
| Pedido | `SO` + 3 dígitos | `SO024` | Número del pedido de venta | `pedidos.ref_odoo` |
| Diseño Custom | `DIS-` + ref. pedido | `DIS-SO024` | Nota/descripción en la línea | `personalizaciones.nombre_diseno` |

Los `id_...` numéricos de PostgreSQL son **internos** de ACC. Para cruzar con otros módulos se usan siempre los códigos de esta tabla.

---

## 3. Catálogo de modelos

| Código | Nombre | Categoría | Precio base (€) | Admite Custom | Colores (código) |
|---|---|---|---:|:-:|---|
| `SF-RUNX` | Runner X | Running | 89.90 | Sí | Blanco (BLA), Negro (NEG), Azul (AZU) |
| `SF-STRK` | Striker Pro | Fútbol | 109.90 | Sí | Negro (NEG), Rojo (ROJ) |
| `SF-COURT` | Court Max | Baloncesto | 119.90 | Sí | Blanco (BLA), Negro (NEG) |
| `SF-PADEL` | Padel Grip | Pádel | 79.90 | Sí | Blanco (BLA), Azul (AZU) |
| `SF-TRAIL` | Trail Rock | Trail | 99.90 | No | Gris (GRI), Verde (VER) |
| `SF-URBAN` | Urban Flow | Casual | 69.90 | No | Blanco (BLA), Beige (BEI) |

- **Tallas:** numeración europea, **enteros del 36 al 46** en todos los modelos.
- **Variantes:** 6 modelos · 13 colores · 11 tallas = 143 combinaciones modelo-color-talla (filas de `almacen`).
- **Coste unitario:** no se registra. Python mostrará el margen como «NO CALCULABLE».

---

## 4. Personalización (línea Custom)

Un pedido Custom tiene **un diseño propio** del cliente. El diseño recoge:

| Campo | Obligatorio | Ejemplo |
|---|:-:|---|
| Nombre del diseño | Sí | `DIS-SO024 Halcones 2026` |
| Color primario | Sí | Azul |
| Color secundario | No | Blanco |
| Texto bordado (máx. 20 caracteres) | No | HALCONES |
| Escudo del club (nombre del fichero) | No | `escudo_halcones.png` |
| Recargo por par (€) | Sí | 15.00 |

**Precio de cada par Custom = precio base del modelo + recargo del diseño.**
Solo se pueden personalizar los modelos con «Admite Custom = Sí».

La Web debe pedir estos mismos campos en su formulario Custom, además de: modelo, color, tallas con su cantidad, fecha objetivo y datos de contacto.

---

## 5. Clientes

| Código | Nombre | Tipo |
|---|---|---|
| `CLI001` | Club Halcones | CLUB |
| `CLI002` | CD Leones del Sur | CLUB |
| `CLI003` | Pádel Norte Team | EQUIPO |
| `CLI004` | Running Crew Sur | EQUIPO |
| `CLI005` | Laura Martín Gil | PARTICULAR |
| `CLI006` | CB Torres | CLUB |

Emails y teléfonos ficticios con el formato `contacto@<nombre>.example.com` y `600 000 00X`.
**No se exportan a Python** (no los necesita).

---

## 6. Estados del pedido

| Estado | Significado | Equivalente en Odoo | ¿Mueve stock? | ¿Cuenta como venta? |
|---|---|---|---|:-:|
| `BORRADOR` | Pedido creado, pendiente de confirmar | Presupuesto | No | No (pendiente) |
| `CONFIRMADO` | Pedido aceptado | Pedido de venta | **Descuenta** al entrar | Sí |
| `ENTREGADO` | Pedido servido al cliente | Entrega validada | No | Sí |
| `CANCELADO` | Pedido anulado | Cancelado | **Restituye** si venía de CONFIRMADO | No |

**Transiciones permitidas:**

```
BORRADOR ──► CONFIRMADO ──► ENTREGADO
    │             │
    └──► CANCELADO ◄┘
```

- Un pedido `ENTREGADO` o `CANCELADO` ya no cambia de estado.
- Los pedidos **no se borran**: se cancelan (eliminación lógica).
- **Ventas válidas** = pedidos `CONFIRMADO` + `ENTREGADO`. El importe es el de sus líneas.
- **Tipo de pedido:** `ESTANDAR` o `CUSTOM`.

---

## 7. Pedidos de prueba

### 7.1 Carga inicial (los carga ACC; Odoo los replica con la misma referencia)

| Ref. | Fecha | Cliente | Tipo | Estado | Líneas (modelo · color · talla×cantidad) | Diseño |
|---|---|---|---|---|---|---|
| SO001 | 2026-06-03 | CLI002 | ESTANDAR | ENTREGADO | Striker Pro · NEG · 42×10, 43×8 | — |
| SO002 | 2026-06-12 | CLI005 | ESTANDAR | ENTREGADO | Urban Flow · BLA · 38×1 | — |
| SO003 | 2026-06-25 | CLI001 | CUSTOM | ENTREGADO | Runner X · AZU · 39×5, 40×6, 41×5 | DIS-SO003 Halcones Training (+12.00 €) |
| SO004 | 2026-07-08 | CLI004 | ESTANDAR | ENTREGADO | Runner X · NEG · 41×4 / Trail Rock · GRI · 42×3 | — |
| SO005 | 2026-07-21 | CLI003 | CUSTOM | CONFIRMADO | Padel Grip · BLA · 40×4, 42×4 | DIS-SO005 Pádel Norte 26 (+10.00 €) |
| SO006 | 2026-08-05 | CLI006 | CUSTOM | CANCELADO* | Court Max · NEG · 44×6, 45×6 | DIS-SO006 Torres Basket (+15.00 €) |
| SO007 | 2026-08-19 | CLI001 | ESTANDAR | ENTREGADO | Urban Flow · BEI · 40×2 | — |
| SO008 | 2026-09-02 | CLI002 | CUSTOM | CONFIRMADO | Striker Pro · ROJ · 41×5, 42×7, 43×6 | DIS-SO008 Leones Matchday (+12.00 €) |
| SO009 | 2026-09-16 | CLI005 | ESTANDAR | CANCELADO | Trail Rock · VER · 38×1 | — |
| SO010 | 2026-09-30 | CLI004 | ESTANDAR | CONFIRMADO | Runner X · BLA · 40×3, 42×3 | — |
| SO011 | 2026-10-14 | CLI006 | ESTANDAR | BORRADOR | Court Max · BLA · 45×5 | — |
| SO012 | 2026-10-21 | CLI003 | ESTANDAR | BORRADOR | Padel Grip · AZU · 41×2 | — |

\* SO006 se confirmó y después se canceló: sirve para demostrar la restitución de stock.

**Cobertura de requisitos:**
- 12 pedidos (ACC pide ≥ 10) repartidos de junio a octubre de 2026 → Python tiene 5 meses para evolución mensual y cohortes.
- 4 Custom (ACC pide ≥ 3); varios con varias tallas (SO003, SO006, SO008).
- Los 4 estados representados.
- CLI001, CLI002, CLI003, CLI004, CLI005 y CLI006 con 2 pedidos cada uno → Caso F de Python (cliente con varios pedidos).

### 7.2 Pedido común de la demostración: **SO024**

| Ref. | Cliente | Tipo | Modelo · color | Tallas × cantidad | Total pares | Diseño |
|---|---|---|---|---|---:|---|
| SO024 | CLI001 Club Halcones | CUSTOM | Runner X · AZU | 38×2, 39×4, 40×6, 41×7, 42×7, 43×6, 44×4, 45×2, 46×2 | **40** | DIS-SO024 Halcones 2026 · Azul/Blanco · «HALCONES» · `escudo_halcones.png` · +15.00 € |

- **No va en la carga inicial de ACC:** se crea en directo desde Java durante la defensa (requisito de ACC).
- **Odoo** lo crea con el mismo número `SO024`.
- **PSP** procesa el CSV de su ficha de fabricación.
- **Python** lo ve aparecer en el dashboard tras la nueva exportación (Casos A, C y L).
- Precio por par: 89.90 + 15.00 = 104.90 € → total 40 × 104.90 = **4 196,00 €**.

### 7.3 Stock inicial

- 20 unidades por modelo-color-talla, `stock_minimo` = 5.
- Excepciones para demostrar **stock bajo**: Court Max · BLA · 45 = 3 unidades y Trail Rock · VER · 38 = 2 unidades.
- Las cifras de stock tras la carga inicial salen de aplicar los pedidos confirmados (los calculan los triggers, no se ajustan a mano).

---

## 8. Roles y usuarios de prueba

| Rol | Responsabilidad | Usuario de prueba |
|---|---|---|
| `ADMIN` | Todo, incluida la gestión de usuarios y permisos | `admin` |
| `COMERCIAL` | Crear, consultar, confirmar y cancelar pedidos | `comercial1` |
| `ALMACEN` | Consultar stock y pedidos, marcar entregados | `almacen1` |

- Mismos perfiles que en Odoo (comercial, almacén, administración).
- Las contraseñas son ficticias, se guardan con bcrypt y **no se escriben en el repositorio**; se comunican por el medio acordado.
- La matriz de permisos detallada la define ACC en su memoria.

---

## 9. Formato de los ficheros de intercambio

### 9.1 Reglas comunes (todos los CSV)

| Aspecto | Valor |
|---|---|
| Codificación | UTF-8 sin BOM |
| Separador | coma `,` |
| Comillas | `"` solo cuando el texto contiene comas |
| Cabecera | Sí, primera fila, nombres en minúscula y con `_` |
| Decimal | punto `.` (ej. `89.90`) |
| Moneda | euros, sin símbolo |
| Fecha y hora | `YYYY-MM-DD HH:MM:SS` (ej. `2026-06-03 10:30:00`) |
| Booleanos | `true` / `false` |
| Nulos | campo vacío |
| Escritura | se genera un `.tmp` y se renombra al terminar (nunca se lee un fichero a medias) |

### 9.2 Exportaciones de ACC para Python (carpeta `exportaciones/`)

| Fichero | Columnas | Clave |
|---|---|---|
| `clientes.csv` | `id_cliente, codigo_odoo, nombre, tipo_cliente, activo` | `id_cliente` |
| `modelos.csv` | `id_modelo, codigo_modelo, nombre, categoria, precio_base, admite_custom, activo` | `id_modelo` |
| `pedidos.csv` | `id_pedido, ref_odoo, fecha_pedido, id_cliente, tipo, estado, importe_total` | `id_pedido` |
| `lineas_pedido.csv` | `id_linea, id_pedido, id_modelo, color, talla, cantidad, precio_unitario, subtotal_linea, personalizada` | `id_linea` |
| `stock.csv` | `id_modelo, color, talla, stock_disponible, stock_minimo, fecha_corte` | `id_modelo + color + talla` |

- La clave de `stock.csv` incluye el **color**: dos filas con el mismo modelo y talla pero distinto color **no** son un duplicado.
- `fecha_corte` es el momento de la exportación.
- Python **no** recibe emails, teléfonos, usuarios ni contraseñas.
- Python solo ve cambios cuando ACC **vuelve a exportar**.

### 9.3 Ficha de fabricación de ACC para PSP

Fichero `ficha_<ref>.csv` (ej. `ficha_SO024.csv`), una fila por talla:

```
ref_odoo,cliente,modelo,color,diseno,texto_bordado,talla,cantidad
SO024,Club Halcones,Runner X,Azul,DIS-SO024 Halcones 2026,HALCONES,38,2
SO024,Club Halcones,Runner X,Azul,DIS-SO024 Halcones 2026,HALCONES,39,4
...
```

El validador de PSP comprueba estas columnas, que `talla` esté entre 36 y 46 y que `cantidad` sea > 0.

---

## 10. Cambios que este contrato implica en `acesso-a-datos/d3_kicks.sql`

1. `pedidos.ref_pedido_custom` → `ref_odoo VARCHAR(20) NOT NULL UNIQUE` (todos los pedidos tienen referencia).
2. Añadir `pedidos.tipo VARCHAR(10) NOT NULL CHECK (tipo IN ('ESTANDAR','CUSTOM'))` en lugar de `es_custom`.
3. Estados: `CHECK (estado IN ('BORRADOR','CONFIRMADO','ENTREGADO','CANCELADO'))`.
4. Añadir `modelos.categoria VARCHAR(30) NOT NULL`.
5. `almacen.talla`: `CHECK (talla BETWEEN 36 AND 46)`.
6. `lineas_pedido → pedidos`: `ON DELETE RESTRICT` (no CASCADE).
7. `subtotal_linea NUMERIC(10,2) GENERATED ALWAYS AS (cantidad * precio_unitario) STORED`.
8. `log_eventos`: añadir `accion VARCHAR(60)`, `CHECK` en `operacion`, `resumen_cambios TEXT`, `fecha_hora TIMESTAMPTZ` y FK a usuarios `ON DELETE RESTRICT`.

---

## 11. Pendiente de confirmar por cada módulo

- [ ] **Odoo:** crear los 6 modelos con sus variantes, los 6 clientes y los pedidos SO001–SO012 con las mismas referencias.
- [ ] **Web:** mostrar los 6 modelos, colores y tallas 36–46; formulario Custom con los campos de la sección 4.
- [ ] **PSP:** aceptar el formato de la ficha de la sección 9.3.
- [ ] **ACC:** aplicar los cambios de la sección 10 y cargar los datos de la sección 7.
- [ ] **Python:** usar los ficheros y columnas de la sección 9.2 como contrato de entrada.
