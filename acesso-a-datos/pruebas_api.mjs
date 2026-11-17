import fs from "fs";
import path from "path";
import { execSync } from "child_process";

const API = process.env.API_URL || "http://localhost:3000/api";
const SALIDAS = process.env.SALIDAS || process.env.SALIDAS_DIR || path.resolve("salidas");
const TXT = path.join(SALIDAS, "actividad_sneaker.txt");
const JSONF = path.join(SALIDAS, "usuarios_sneaker.json");

let sql, cerrarSql = async () => { };
if (process.env.DB_HOST && !process.env.PSQL) {
  const pg = (await import("pg")).default;
  const pool = new pg.Pool({
    host: process.env.DB_HOST, port: Number(process.env.DB_PORT), user: process.env.DB_USER,
    password: process.env.DB_PASSWORD, database: process.env.DB_NAME
  });
  sql = async (q) => {
    const r = await pool.query(q);
    const ultimo = Array.isArray(r) ? r[r.length - 1] : r;
    return (ultimo.rows || []).map((fila) => Object.values(fila).map((v) => (v === null ? "" : String(v))).join("|")).join("\n");
  };
  cerrarSql = async () => { await pool.end?.(); };
} else {
  const PSQL = process.env.PSQL || "docker exec -i d3kicks-db psql -U d3kicks -d d3kicks";
  sql = async (q) => execSync(`${PSQL} -At -F "|"`, { input: q + ";\n" }).toString().trim();
}
const lineas = () => (fs.existsSync(TXT) ? fs.readFileSync(TXT, "utf8").trimEnd().split("\n") : []);

// Usuarios con los que se hacen las pruebas
const temporales = !(process.env.CLAVE_ADMIN && process.env.CLAVE_COMERCIAL && process.env.CLAVE_LAURA);
const CUENTAS = temporales
  ? { admin: ["prueba_admin", "Prueba.Api.1"], comercial1: ["prueba_comercial", "Prueba.Api.2"], "laura.martin@example.com": ["prueba_cliente", "Prueba.Api.3"] }
  : { admin: ["admin", process.env.CLAVE_ADMIN], comercial1: ["comercial1", process.env.CLAVE_COMERCIAL], "laura.martin@example.com": ["laura.martin@example.com", process.env.CLAVE_LAURA] };
if (temporales) {
  await sql(`SELECT fn_crear_usuario('prueba_admin', 'Prueba.Api.1', 'ADMIN') WHERE NOT EXISTS (SELECT 1 FROM usuarios WHERE username = 'prueba_admin');
             SELECT fn_crear_usuario('prueba_comercial', 'Prueba.Api.2', 'COMERCIAL') WHERE NOT EXISTS (SELECT 1 FROM usuarios WHERE username = 'prueba_comercial');
             SELECT fn_crear_usuario('prueba_cliente', 'Prueba.Api.3', 'USUARIO', (SELECT id_cliente FROM clientes WHERE codigo_odoo = 'CLI006')) WHERE NOT EXISTS (SELECT 1 FROM usuarios WHERE username = 'prueba_cliente')`);
}
const out = [];
const log = (...a) => { const t = a.join(" "); out.push(t); console.log(t); };

async function api(metodo, ruta, token, cuerpo) {
  const r = await fetch(API + ruta, { method: metodo, headers: { "Content-Type": "application/json", ...(token ? { Authorization: "Bearer " + token } : {}) }, body: cuerpo ? JSON.stringify(cuerpo) : undefined });
  const texto = await r.text();
  let datos; try { datos = JSON.parse(texto); } catch { datos = texto; }
  return { status: r.status, datos };
}
function nuevaLinea(antes, etiqueta) {
  const ahora = lineas();
  const nuevas = ahora.slice(antes);
  log(`   TXT +${nuevas.length} (${etiqueta}): ${nuevas.join("\n                ")}`);
  return ahora.length;
}

let n = lineas().length;
log("== Inicio de sesión por rol (3.8) ==");
const tok = {};
for (const u of ["admin", "comercial1", "laura.martin@example.com"]) {
  const r = await api("POST", "/login", null, { usuario: CUENTAS[u][0], contrasena: CUENTAS[u][1] });
  tok[u] = r.datos.token; log(` ${CUENTAS[u][0]}: HTTP ${r.status} rol=${r.datos.usuario?.rol}`);
  n = nuevaLinea(n, "login");
}
let r = await api("POST", "/login", null, { usuario: CUENTAS.comercial1[0], contrasena: "mala" });
log(` comercial1 con contraseña errónea: HTTP ${r.status} ${r.datos.error}`); n = nuevaLinea(n, "login fallido");

log("\n== Prueba G / E: tres consultas sucesivas (comercial1) ==");
r = await api("GET", "/pedidos/buscar", tok.comercial1);
log(` sin filtros: HTTP ${r.status}, ${r.datos.total} pedidos; SQL directo: ${await sql("select count(*) from pedidos")}`); n = nuevaLinea(n, "consulta 1");
r = await api("GET", "/pedidos/buscar?cliente=Halcones&estado=entregado", tok.comercial1);
log(` cliente=Halcones + estado=ENTREGADO: ${r.datos.total} -> ${r.datos.pedidos.map(p => p.ref_odoo).join(", ")}; SQL: ${await sql("select string_agg(ref_odoo, ', ' order by ref_odoo) from pedidos p join clientes c using(id_cliente) where c.nombre ilike '%Halcones%' and estado='ENTREGADO'")}`); n = nuevaLinea(n, "consulta 2");
r = await api("GET", "/pedidos/buscar?cliente=Nadie&modelo=Runner", tok.comercial1);
log(` sin coincidencias: total=${r.datos.total}, mensaje="${r.datos.mensaje}"`); n = nuevaLinea(n, "consulta 3");
r = await api("GET", "/pedidos/buscar?desde=2026-09-01&hasta=2026-10-31&estado=CONFIRMADO", tok.comercial1);
log(` periodo sep-oct + CONFIRMADO: ${r.datos.pedidos.map(p => p.ref_odoo).join(", ")}`); n = nuevaLinea(n, "consulta 4");
r = await api("GET", "/pedidos/buscar", tok.comercial1);
log(` limpiar filtros (sin filtros otra vez): ${r.datos.total} pedidos`); n = nuevaLinea(n, "limpiar");
r = await api("GET", "/pedidos/buscar?estado=PERDIDO", tok.comercial1);
log(` consulta incorrecta (estado inexistente): HTTP ${r.status} ${r.datos.error}`); n = nuevaLinea(n, "incorrecta");
r = await api("GET", "/pedidos/buscar?desde=17/11/2026", tok.comercial1);
log(` fecha mal escrita: HTTP ${r.status} ${r.datos.error}`); n = nuevaLinea(n, "fecha mal");

log("\n== Prueba F: perfil restringido ==");
r = await api("GET", "/pedidos/buscar", tok["laura.martin@example.com"]);
log(` laura sin filtros: ${r.datos.total} pedidos (${r.datos.pedidos.map(p => p.ref_odoo + " " + p.cliente).join("; ")})`); n = nuevaLinea(n, "laura busca");
r = await api("GET", "/pedidos/buscar?cliente=Halcones", tok["laura.martin@example.com"]);
log(` laura pide pedidos de Club Halcones: ${r.datos.total} (${r.datos.mensaje})`); n = nuevaLinea(n, "laura otro cliente");
r = await api("GET", "/panel/indicadores", tok["laura.martin@example.com"]);
log(` laura pide indicadores: HTTP ${r.status} ${r.datos.error}`); n = nuevaLinea(n, "laura indicadores");
r = await api("GET", "/usuarios/exportar", tok.comercial1);
log(` comercial1 exporta usuarios: HTTP ${r.status} ${r.datos.error}`); n = nuevaLinea(n, "comercial exportar");

log("\n== Prueba H: pedido desde la aplicación y error forzado ==");
const logAntes = Number(await sql("select count(*) from log_eventos"));
const stockAntes = await sql("select stock_disponible from almacen a join modelos m using(id_modelo) where codigo_modelo='D3-001' and talla=40");
r = await api("POST", "/pedidos", tok["laura.martin@example.com"], { lineas: [{ codigo_modelo: "D3-001", talla: 40, cantidad: 2 }, { codigo_modelo: "D3-001", talla: 41, cantidad: 1 }] });
const ref = r.datos.ref_odoo;
log(` laura crea pedido: HTTP ${r.status} ${JSON.stringify(r.datos)}`); n = nuevaLinea(n, "crear pedido");
log(` tablas: ${await sql(`select ref_odoo||' '||estado||' '||importe_total from pedidos where ref_odoo='${ref}'`)}; líneas: ${await sql(`select string_agg(a.talla||'x'||l.cantidad||'='||l.subtotal_linea, ', ') from lineas_pedido l join pedidos p using(id_pedido) join almacen a using(id_almacen) where ref_odoo='${ref}'`)}`);
log(` stock Runner X 40: ${stockAntes} -> ${await sql("select stock_disponible from almacen a join modelos m using(id_modelo) where codigo_modelo='D3-001' and talla=40")}`);
log(` log_eventos nuevos: ${Number(await sql("select count(*) from log_eventos")) - logAntes}`);
log(await sql(`select '   ' || to_char(fecha_hora,'YYYY-MM-DD HH24:MI:SS') || ' | ' || coalesce(u.username,'-') || ' | ' || accion || ' | ' || resumen_cambios from log_eventos l left join usuarios u using(id_usuario) where id_evento > ${logAntes} order by id_evento`));
r = await api("GET", `/pedidos/buscar?estado=CONFIRMADO`, tok["laura.martin@example.com"]);
log(` consulta visual de laura (CONFIRMADO): ${r.datos.pedidos.map(p => p.ref_odoo).join(", ")}`); n = nuevaLinea(n, "buscar tras crear");
const logAntes2 = Number(await sql("select count(*) from log_eventos")); const pedAntes = await sql("select count(*) from pedidos");
r = await api("POST", "/pedidos", tok["laura.martin@example.com"], { lineas: [{ codigo_modelo: "D3-001", talla: 41, cantidad: 1 }, { codigo_modelo: "ADI-002", talla: 45, cantidad: 50 }] });
log(` error forzado (50 pares sin stock): HTTP ${r.status} ${r.datos.error}`); n = nuevaLinea(n, "error forzado");
log(` pedidos ${pedAntes} -> ${await sql("select count(*) from pedidos")}, log_eventos +${Number(await sql("select count(*) from log_eventos")) - logAntes2}`);
r = await api("PUT", `/pedidos/${ref}/estado`, tok["laura.martin@example.com"], { estado: "CANCELADO" });
log(` laura intenta cancelar ${ref}: HTTP ${r.status} ${r.datos.error}`); n = nuevaLinea(n, "cancelar denegado");
r = await api("PUT", `/pedidos/${ref}/estado`, tok.comercial1, { estado: "CANCELADO" });
log(` comercial1 cancela ${ref}: HTTP ${r.status} estado=${r.datos.estado}; stock Runner X 40 = ${await sql("select stock_disponible from almacen a join modelos m using(id_modelo) where codigo_modelo='D3-001' and talla=40")}`); n = nuevaLinea(n, "cancelar");
log(await sql(`select '   ' || to_char(fecha_hora,'YYYY-MM-DD HH24:MI:SS') || ' | ' || coalesce(u.username,'-') || ' | ' || accion || ' | ' || resumen_cambios from log_eventos l left join usuarios u using(id_usuario) order by id_evento desc limit 1`));

log("\n== Prueba I: usuarios y JSON ==");
r = await api("GET", "/usuarios/exportar", tok.admin);
log(` admin exporta: HTTP ${r.status} ${JSON.stringify(r.datos)}`); n = nuevaLinea(n, "exportar");
r = await api("POST", "/usuarios", tok.admin, { username: "almacen1", contrasena: "Almacen.2026", rol: "COMERCIAL" });
const idNuevo = r.datos.id_usuario;
log(` admin crea almacen1: HTTP ${r.status} id=${idNuevo} json_actualizado=${r.datos.json_actualizado}`); n = nuevaLinea(n, "crear usuario");
let js = JSON.parse(fs.readFileSync(JSONF, "utf8"));
log(` JSON: ${js.length} usuarios -> ${js.map(u => u.username + (u.activo ? "" : " (inactivo)")).join(", ")}`);
r = await api("PUT", `/usuarios/${idNuevo}/bloquear`, tok.admin);
log(` admin desactiva almacen1: HTTP ${r.status} activo=${r.datos.activo}`); n = nuevaLinea(n, "desactivar");
js = JSON.parse(fs.readFileSync(JSONF, "utf8"));
log(` JSON: ${js.length} usuarios -> ${js.map(u => u.username + (u.activo ? "" : " (inactivo)")).join(", ")}`);
log(` ¿contiene password/hash? ${/password|hash|\$2[aby]\$/.test(fs.readFileSync(JSONF, "utf8")) ? "SÍ" : "no"}`);
r = await api("POST", "/login", null, { usuario: "almacen1", contrasena: "Almacen.2026" });
log(` almacen1 desactivado intenta entrar: HTTP ${r.status}`); n = nuevaLinea(n, "login inactivo");
r = await api("POST", "/usuarios", tok.admin, { username: "almacen1", contrasena: "Otra.2026x", rol: "COMERCIAL" });
log(` crear de nuevo almacen1: HTTP ${r.status} ${r.datos.error}`); n = nuevaLinea(n, "duplicado");
r = await api("POST", "/usuarios", tok.comercial1, { username: "intruso", contrasena: "Intruso.2026", rol: "ADMIN" });
log(` comercial1 intenta crear un usuario: HTTP ${r.status} ${r.datos.error}; existe 'intruso' en BD: ${await sql("select count(*) from usuarios where username='intruso'")}`); n = nuevaLinea(n, "crear denegado");
r = await api("PUT", "/usuarios/permisos", tok.admin, { rol: "COMERCIAL", operacion: "AUDITORIA_VER", permitido: true });
log(` admin concede AUDITORIA_VER a COMERCIAL: HTTP ${r.status} ${JSON.stringify(r.datos)}`); n = nuevaLinea(n, "permiso");
r = await api("PUT", "/usuarios/permisos", tok.admin, { rol: "COMERCIAL", operacion: "AUDITORIA_VER", permitido: false });
log(` y se lo vuelve a quitar: HTTP ${r.status}`); n = nuevaLinea(n, "permiso");
r = await api("PUT", "/usuarios/permisos", tok.admin, { rol: "ADMIN", operacion: "USUARIOS_GESTIONAR", permitido: false });
log(` admin intenta quitarse USUARIOS_GESTIONAR: HTTP ${r.status} ${r.datos.error}`); n = nuevaLinea(n, "permiso admin");
log(await sql(`select '   ' || to_char(fecha_hora,'YYYY-MM-DD HH24:MI:SS') || ' | ' || coalesce(u.username,'-') || ' | ' || accion || ' | ' || resumen_cambios from log_eventos l left join usuarios u using(id_usuario) where tabla_afectada in ('usuarios','permisos_rol') and id_usuario is not null order by id_evento`));

log("\n== Prueba J: indicadores, stock bajo y CSV ==");
r = await api("GET", "/panel/indicadores", tok.comercial1);
log(` indicadores API: ${JSON.stringify(r.datos)}`); n = nuevaLinea(n, "indicadores");
log(` SQL directo: pedidos=${await sql("select count(*) from pedidos")} validos=${await sql("select count(*) from pedidos where estado in ('CONFIRMADO','ENTREGADO')")} pares=${await sql("select sum(cantidad) from lineas_pedido l join pedidos p using(id_pedido) where estado in ('CONFIRMADO','ENTREGADO')")} importe=${await sql("select sum(importe_total) from pedidos where estado in ('CONFIRMADO','ENTREGADO')")}`);
r = await api("GET", "/panel/stock-bajo?umbral=10", tok.comercial1);
log(` stock bajo umbral 10: ${r.datos.total} filas -> ${r.datos.filas.map(f => `${f.modelo} ${f.talla} (${f.stock_disponible})`).join("; ")}`); n = nuevaLinea(n, "stock bajo");
r = await api("GET", "/panel/stock-bajo", tok.comercial1);
log(` stock bajo con el mínimo de cada talla: ${r.datos.total} filas`); n = nuevaLinea(n, "stock bajo min");
const vista = await api("GET", "/pedidos/buscar?estado=ENTREGADO&desde=2026-06-01", tok.comercial1);
const csv = await fetch(API + "/pedidos/buscar?estado=ENTREGADO&desde=2026-06-01&formato=csv", { headers: { Authorization: "Bearer " + tok.comercial1 } });
const csvTexto = await csv.text();
log(` CSV: HTTP ${csv.status} ${csv.headers.get("content-type")}`); n = nuevaLinea(n, "csv");
log(csvTexto.trimEnd().split("\n").map(l => "   " + l).join("\n"));
const filasCsv = csvTexto.trimEnd().split("\n").slice(1).map(l => l.split(",")[0]);
log(` filas CSV = ${filasCsv.length}, filas consulta = ${vista.datos.total}, mismas referencias: ${JSON.stringify(filasCsv) === JSON.stringify(vista.datos.pedidos.map(p => p.ref_odoo))}`);

fs.writeFileSync(path.join(SALIDAS, "resultado_pruebas_api.txt"), out.join("\n") + "\n");
await cerrarSql();
