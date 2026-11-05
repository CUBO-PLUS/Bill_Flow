import json
import os
import re
import threading
from datetime import datetime, timedelta
import sqlite3
from functools import wraps

from flask import (Flask, Response, abort, flash, g, jsonify, redirect, render_template, request,
                   session, url_for)
import bitcoin
import dte as dte_mod
import esquema
import recibo_pdf
import precios_btc
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "demo-cambiar-clave")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("DB_PATH", os.path.join(BASE_DIR, "restaurante.db"))
SCHEMA_PATH = os.path.join(BASE_DIR, "restaurante_db.sql")

# Datos fiscales del cliente (CCF): NO van a la base de datos (se verían en el
# diagrama / pantalla Data). Se guardan en un archivo local ignorado por git.
CLIENTES_ENV = os.path.join(BASE_DIR, ".env.clientes")
_env_lock = threading.Lock()


def validar_datos_fiscales(form):
    """Devuelve (datos, error) con NIT, NRC, nombre y dirección del formulario."""
    dui = re.sub(r"[\s-]", "", form.get("cf_dui", ""))
    nit = re.sub(r"[\s-]", "", form.get("cf_nit", ""))
    nrc = re.sub(r"[\s-]", "", form.get("cf_nrc", ""))
    nombre = form.get("cf_nombre", "").strip()
    direccion = form.get("cf_direccion", "").strip()
    if dui:  # con DUI el NIT no se pide
        if not (dui.isdigit() and len(dui) == 9):
            return None, "El DUI debe tener 9 dígitos."
        nit = ""
    elif not (nit.isdigit() and len(nit) == 14):
        return None, "El NIT debe tener 14 dígitos."
    if not (nrc.isdigit() and 1 <= len(nrc) <= 8):
        return None, "El NRC debe tener solo dígitos (máx. 8)."
    if not nombre or not direccion:
        return None, "Nombre y dirección del cliente son obligatorios."
    return {"dui": dui, "nit": nit, "nrc": nrc, "nombre": nombre, "direccion": direccion}, None


def guardar_datos_fiscales(venta_id, datos):
    """Agrega una línea JSON por venta a .env.clientes (permisos 600)."""
    linea = json.dumps({"venta_id": venta_id, **datos}, ensure_ascii=False)
    with _env_lock:
        fd = os.open(CLIENTES_ENV, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        with os.fdopen(fd, "a", encoding="utf-8") as f:
            f.write(linea + "\n")


ROL_ASISTENTE = "Asistente de caja"
ROL_ADMIN = "Administrador"

# True  = en el registro se puede elegir "Administrador" (para la demo).
# False = el registro solo crea Asistentes de caja.
PERMITIR_REGISTRO_ADMIN = True


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def migrar_rol_administrador(db):
    """Bases viejas: renombra el rol 'Contador' a 'Administrador' (el CHECK obliga a rehacer la tabla)."""
    fila = db.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='rol'").fetchone()
    if not fila or "'Contador'" not in fila[0]:
        return
    db.execute("PRAGMA foreign_keys = OFF")
    db.executescript("""
        BEGIN;
        CREATE TABLE rol_nueva (
            id      INTEGER PRIMARY KEY,
            nombre  TEXT NOT NULL UNIQUE
                    CHECK (nombre IN ('Asistente de caja', 'Administrador'))
        );
        INSERT INTO rol_nueva (id, nombre)
            SELECT id, CASE nombre WHEN 'Contador' THEN 'Administrador' ELSE nombre END FROM rol;
        DROP TABLE rol;
        ALTER TABLE rol_nueva RENAME TO rol;
        COMMIT;
    """)
    db.execute("PRAGMA foreign_keys = ON")


def migrar_lightning(db):
    """Agrega 'Bitcoin Lightning' (mismo código 11 que Bitcoin): quita el UNIQUE de forma_pago.codigo."""
    fila = db.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='forma_pago'").fetchone()
    if fila and "codigo  TEXT NOT NULL UNIQUE" in fila[0]:
        db.execute("PRAGMA foreign_keys = OFF")
        db.executescript("""
            BEGIN;
            CREATE TABLE forma_pago_nueva (
                id      INTEGER PRIMARY KEY,
                codigo  TEXT NOT NULL,
                nombre  TEXT NOT NULL UNIQUE
            );
            INSERT INTO forma_pago_nueva SELECT id, codigo, nombre FROM forma_pago;
            DROP TABLE forma_pago;
            ALTER TABLE forma_pago_nueva RENAME TO forma_pago;
            COMMIT;
        """)
        db.execute("PRAGMA foreign_keys = ON")
    db.execute("INSERT OR IGNORE INTO forma_pago (codigo, nombre) VALUES ('11', 'Bitcoin Lightning')")
    db.commit()


def init_db():
    """Crea la base desde restaurante_db.sql la primera vez."""
    db = sqlite3.connect(DB_PATH)
    existe = db.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='venta'"
    ).fetchone()
    if not existe:
        with open(SCHEMA_PATH, encoding="utf-8") as f:
            db.executescript(f.read())
    migrar_rol_administrador(db)
    migrar_lightning(db)
    # Pagos Bitcoin: tablas, columnas de trazabilidad y triggers (idempotente)
    db.row_factory = sqlite3.Row
    bitcoin.migrar(db)
    db.close()


init_db()


def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        # Si la sesión es de un usuario que ya no existe, se invalida.
        row = get_db().execute(
            "SELECT 1 FROM empleado WHERE id = ? AND nombre_usuario = ?",
            (session["user_id"], session.get("username"))).fetchone()
        if not row:
            session.clear()
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapper


def admin_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not session.get("es_admin"):
            flash("Solo los administradores pueden hacer eso.")
            return redirect(url_for("panel"))
        return view(*args, **kwargs)
    return wrapper


@app.route("/")
def index():
    return redirect(url_for("nueva_venta"))


@app.route("/registro", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        quiere_admin = request.form.get("rol") == "admin"

        if not username or not password:
            flash("Escribe un usuario y una contraseña.")
        else:
            rol = ROL_ADMIN if (quiere_admin and PERMITIR_REGISTRO_ADMIN) else ROL_ASISTENTE
            db = get_db()
            try:
                db.execute(
                    "INSERT INTO empleado (rol_id, nombre_usuario, password_hash) "
                    "VALUES ((SELECT id FROM rol WHERE nombre = ?), ?, ?)",
                    (rol, username, generate_password_hash(password)),
                )
                db.commit()
                flash("Usuario creado. Ya puedes iniciar sesión.")
                return redirect(url_for("login"))
            except sqlite3.IntegrityError:
                flash("Ese nombre de usuario ya existe.")

    return render_template("register.html", permitir_admin=PERMITIR_REGISTRO_ADMIN)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        row = get_db().execute(
            "SELECT e.id, e.nombre_usuario, e.password_hash, r.nombre AS rol "
            "FROM empleado e JOIN rol r ON r.id = e.rol_id "
            "WHERE e.nombre_usuario = ?", (username,)
        ).fetchone()

        if row and row["password_hash"] and check_password_hash(row["password_hash"], password):
            session.clear()
            session["user_id"] = row["id"]
            session["username"] = row["nombre_usuario"]
            session["rol"] = row["rol"]
            session["es_admin"] = row["rol"] == ROL_ADMIN
            return redirect(url_for("nueva_venta"))
        flash("Usuario o contraseña incorrectos.")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


VENTAS_SQL = """
    SELECT v.id, v.fecha_hora, v.cliente_nombre, tc.documento,
           fp.nombre AS forma_pago, e.nombre_usuario AS empleado,
           ed.paso, ed.nombre AS estado, t.total_usd,
           vb.estado AS btc_estado, vb.id_pago AS btc_id_pago
    FROM venta v
    JOIN tipo_cliente tc ON tc.id = v.tipo_cliente_id
    JOIN forma_pago fp ON fp.id = v.forma_pago_id
    LEFT JOIN empleado e ON e.id = v.empleado_id
    LEFT JOIN estado_dte ed ON ed.id = v.estado_dte_id
    LEFT JOIN v_venta_total t ON t.venta_id = v.id
    LEFT JOIN venta_bitcoin vb ON vb.venta_id = v.id
"""


@app.route("/panel")
@login_required
@admin_required
def panel():
    db = get_db()
    empleados = db.execute(
        "SELECT e.id, e.nombre_usuario, r.nombre AS rol FROM empleado e "
        "JOIN rol r ON r.id = e.rol_id "
        "WHERE e.nombre_usuario IS NOT NULL AND e.nombre_usuario <> '' ORDER BY e.id"
    ).fetchall()
    ventas = db.execute(VENTAS_SQL + " ORDER BY v.id DESC").fetchall()
    stats = {
        "empleados": len(empleados),
        "administradores": sum(1 for e in empleados if e["rol"] == ROL_ADMIN),
        "asistentes": sum(1 for e in empleados if e["rol"] == ROL_ASISTENTE),
        "ventas": len(ventas),
        "completas": sum(1 for v in ventas if v["paso"] == 5),
    }
    return render_template("dashboard.html", empleados=empleados, ventas=ventas, stats=stats)


RANGOS = {"hoy": "Hoy", "semana": "Esta semana", "mes": "Este mes"}


def _rango_fechas(rango):
    """(inicio, fin) como datetime; fin exclusivo. Semana = lunes a hoy; mes = día 1 a hoy."""
    hoy = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    if rango == "semana":
        ini = hoy - timedelta(days=hoy.weekday())
    elif rango == "mes":
        ini = hoy.replace(day=1)
    else:
        ini = hoy
    return ini, hoy + timedelta(days=1)


@app.route("/cierre")
@login_required
@admin_required
def cierre():
    return render_template("cierre.html")


@app.route("/cierre/json")
@login_required
@admin_required
def cierre_json():
    """Datos del Cierre diario para Hoy / Semana / Mes."""
    rango = request.args.get("rango", "hoy")
    if rango not in RANGOS:
        rango = "hoy"
    ini, fin = _rango_fechas(rango)
    db = get_db()
    ventas = [dict(r) for r in db.execute(
        VENTAS_SQL + " WHERE v.fecha_hora >= ? AND v.fecha_hora < ? ORDER BY v.id DESC",
        (ini.strftime("%Y-%m-%d %H:%M:%S"), fin.strftime("%Y-%m-%d %H:%M:%S")))]
    ids = [v["id"] for v in ventas]
    items = {}
    if ids:
        for r in db.execute(
                "SELECT d.venta_id, p.nombre, c.nombre AS categoria, d.cantidad, d.precio_unitario "
                "FROM detalle_venta d JOIN platillo p ON p.id = d.platillo_id "
                "JOIN categoria_menu c ON c.id = p.categoria_id "
                "WHERE d.venta_id IN (%s)" % ",".join("?" * len(ids)), ids):
            items.setdefault(r["venta_id"], []).append(dict(r))

    def suma(clave):
        out = {}
        for v in ventas:
            k = v[clave] or "—"
            o = out.setdefault(k, {"nombre": k, "ventas": 0, "total": 0.0})
            o["ventas"] += 1
            o["total"] += v["total_usd"] or 0
        return sorted(out.values(), key=lambda x: -x["total"])

    platos, cats = {}, {}
    for lst in items.values():
        for it in lst:
            monto = it["cantidad"] * it["precio_unitario"]
            p = platos.setdefault(it["nombre"], {"nombre": it["nombre"], "cantidad": 0, "total": 0.0})
            p["cantidad"] += it["cantidad"]; p["total"] += monto
            c = cats.setdefault(it["categoria"], {"nombre": it["categoria"], "cantidad": 0, "total": 0.0})
            c["cantidad"] += it["cantidad"]; c["total"] += monto

    # Serie de tiempo: por hora (hoy) o por día (semana / mes), rellenando huecos con 0
    serie = []
    if rango == "hoy":
        base = {h: 0.0 for h in range(24)}
        cnt = {h: 0 for h in range(24)}
        for v in ventas:
            h = int((v["fecha_hora"] or "0000-00-00 00")[11:13])
            base[h] += v["total_usd"] or 0; cnt[h] += 1
        serie = [{"etiqueta": "%02d h" % h, "total": base[h], "ventas": cnt[h]} for h in range(24)]
    else:
        dias = (min(fin, datetime.now() + timedelta(days=1)).replace(hour=0, minute=0, second=0,
                                                                      microsecond=0) - ini).days
        por_dia = {}
        for v in ventas:
            d = (v["fecha_hora"] or "")[:10]
            t = por_dia.setdefault(d, [0.0, 0]); t[0] += v["total_usd"] or 0; t[1] += 1
        for i in range(max(dias, 1)):
            d = ini + timedelta(days=i)
            t = por_dia.get(d.strftime("%Y-%m-%d"), [0.0, 0])
            serie.append({"etiqueta": d.strftime("%d/%m"), "total": t[0], "ventas": t[1]})

    total = sum(v["total_usd"] or 0 for v in ventas)
    n_platos = sum(it["cantidad"] for lst in items.values() for it in lst)
    for v in ventas:
        v["items"] = ", ".join("%dx %s" % (i["cantidad"], i["nombre"]) for i in items.get(v["id"], []))
    return jsonify(
        rango=rango, etiqueta=RANGOS[rango],
        desde=ini.strftime("%d/%m/%Y"), hasta=(fin - timedelta(days=1)).strftime("%d/%m/%Y"),
        kpi={"ventas": len(ventas), "total": total,
             "ticket": total / len(ventas) if ventas else 0, "platos": n_platos,
             "pendientes_hacienda": sum(1 for v in ventas if (v["paso"] or 0) < 5),
             "completas": sum(1 for v in ventas if v["paso"] == 5),
             "btc_pendientes": sum(1 for v in ventas if (v["btc_estado"] or "").lower() == "pendiente")},
        serie=serie, por_pago=suma("forma_pago"), por_documento=suma("documento"),
        por_empleado=suma("empleado"), por_estado=suma("estado"),
        top_platos=sorted(platos.values(), key=lambda x: -x["cantidad"])[:8],
        por_categoria=sorted(cats.values(), key=lambda x: -x["total"]),
        recibos=ventas)


@app.route("/dte")
@login_required
@admin_required
def dte_lista():
    ventas = get_db().execute(VENTAS_SQL + " ORDER BY v.id DESC").fetchall()
    return render_template("dte_ventas.html", ventas=ventas)


def _dte_o_404(vid):
    d = dte_mod.construir_dte(get_db(), vid)
    if d is None:
        abort(404)
    return d


@app.route("/dte/<int:vid>/recibo.pdf")
@login_required
@admin_required
def dte_recibo(vid):
    pdf = recibo_pdf.recibo_pdf(_dte_o_404(vid))
    return Response(pdf, mimetype="application/pdf",
                    headers={"Content-Disposition": "inline; filename=recibo-%04d.pdf" % vid})


@app.route("/dte/<int:vid>/dte.json")
@login_required
@admin_required
def dte_json(vid):
    d = _dte_o_404(vid)
    return Response(json.dumps(d, ensure_ascii=False, indent=2), mimetype="application/json",
                    headers={"Content-Disposition": "attachment; filename=%s.json"
                             % d["identificacion"]["codigoGeneracion"]})


@app.route("/data")
@login_required
@admin_required
def data():
    """Vista visual de la base de datos real (esquema, PK/FK y filas), siempre al día."""
    return render_template("data.html", lucid_url=esquema.lucid_url())


@app.route("/data/json")
@login_required
@admin_required
def data_json():
    """Esquema + todas las filas (la pantalla Data lo consulta cada pocos segundos)."""
    entidades, relaciones = esquema.leer_esquema(get_db(), con_filas=500)
    return jsonify(entidades=entidades, relaciones=relaciones)


# Platos sugeridos si todavía no hay ventas que digan cuáles son los frecuentes.
FRECUENTES_DEFAULT = [1, 4, 5, 83, 84, 82]


@app.route("/ventas/nueva", methods=["GET", "POST"])
@login_required
def nueva_venta():
    db = get_db()
    if request.method == "POST":
        # items llega como "platillo_id:cantidad,platillo_id:cantidad"
        try:
            tipo_id = int(request.form["tipo_cliente_id"])
            pago_id = int(request.form["forma_pago_id"])
            items = {}
            for par in request.form["items"].split(","):
                pid, cant = par.split(":")
                pid, cant = int(pid), int(cant)
                if cant < 1:
                    raise ValueError
                items[pid] = items.get(pid, 0) + cant
            if not items:
                raise ValueError
        except (KeyError, ValueError):
            flash("Agrega al menos un plato y revisa los datos de la venta.")
            return redirect(url_for("nueva_venta"))

        fiscales = None
        tipo = db.execute("SELECT codigo FROM tipo_cliente WHERE id = ?", (tipo_id,)).fetchone()
        if tipo and tipo["codigo"] == "03":  # Comprobante de Crédito Fiscal
            fiscales, error = validar_datos_fiscales(request.form)
            if error:
                flash(error)
                return redirect(url_for("nueva_venta"))

        precios = {r["id"]: r["precio_desde"] for r in db.execute(
            "SELECT id, precio_desde FROM platillo WHERE id IN (%s)" % ",".join("?" * len(items)),
            list(items))}
        if len(precios) != len(items):
            flash("Algún platillo no es válido.")
            return redirect(url_for("nueva_venta"))

        total = sum(precios[pid] * cant for pid, cant in items.items())
        es_btc = db.execute("SELECT 1 FROM forma_pago WHERE id = ? AND codigo = '11'",
                            (pago_id,)).fetchone()
        cotizacion = None
        if es_btc:
            try:  # sin cotización válida NO se crea la venta ni el cobro
                cotizacion = precios_btc.obtener_cotizacion()
            except precios_btc.CotizacionNoDisponible:
                flash("No hay precio BTC/USD disponible (Coinbase y Kraken fallaron). "
                      "No se registró la venta; intenta de nuevo o usa otro método de pago.")
                return redirect(url_for("nueva_venta"))

        try:
            cur = db.execute(
                "INSERT INTO venta (fecha_hora, tipo_cliente_id, forma_pago_id, "
                "empleado_id, estado_dte_id) VALUES (datetime('now','localtime'), ?, ?, ?, "
                "(SELECT id FROM estado_dte WHERE paso = 1))",
                (tipo_id, pago_id, session["user_id"]),
            )
            db.executemany(
                "INSERT INTO detalle_venta (venta_id, platillo_id, cantidad, precio_unitario) "
                "VALUES (?, ?, ?, ?)",
                [(cur.lastrowid, pid, cant, precios[pid]) for pid, cant in items.items()],
            )
            msg = "Venta #%04d registrada." % cur.lastrowid
            if es_btc:
                id_pago = bitcoin.registrar_pendiente(
                    db, cur.lastrowid, session["user_id"], total, cotizacion)
                msg += " Pago Bitcoin PENDIENTE, id_pago: %s (BTC/USD %s vía %s)." % (
                    id_pago, cotizacion.precio, cotizacion.fuente)
            db.commit()
            if fiscales:
                guardar_datos_fiscales(cur.lastrowid, fiscales)
            flash(msg)
        except sqlite3.IntegrityError:
            db.rollback()
            flash("Tipo de documento o método de pago no válidos.")
        return redirect(url_for("nueva_venta"))

    categorias = [dict(r) for r in db.execute("SELECT id, nombre FROM categoria_menu ORDER BY id")]
    platillos = [dict(r) for r in db.execute(
        "SELECT id, categoria_id, nombre, precio_desde FROM platillo ORDER BY id")]
    frecuentes = [r["platillo_id"] for r in db.execute(
        "SELECT platillo_id FROM detalle_venta GROUP BY platillo_id "
        "ORDER BY SUM(cantidad) DESC LIMIT 6")]
    for pid in FRECUENTES_DEFAULT:
        if len(frecuentes) < 6 and pid not in frecuentes:
            frecuentes.append(pid)
    return render_template(
        "registrar_venta.html", categorias=categorias, platillos=platillos,
        frecuentes=frecuentes,
        tipos=[dict(r) for r in db.execute("SELECT id, codigo, documento FROM tipo_cliente ORDER BY id")],
        pagos=[dict(r) for r in db.execute("SELECT id, nombre FROM forma_pago ORDER BY id")],
        ahora=datetime.now().strftime("%d/%m/%Y %H:%M"),
    )


@app.route("/ventas/<int:vid>/avanzar", methods=["POST"])
@login_required
@admin_required
def avanzar_venta(vid):
    db = get_db()
    db.execute(
        """UPDATE venta SET estado_dte_id = (
               SELECT id FROM estado_dte WHERE paso =
                 COALESCE((SELECT paso FROM estado_dte WHERE id = venta.estado_dte_id), 0) + 1)
           WHERE id = ? AND COALESCE(
                 (SELECT paso FROM estado_dte WHERE id = venta.estado_dte_id), 0) < 5""",
        (vid,),
    )
    db.commit()
    flash("Venta: estado del DTE actualizado.")
    return redirect(url_for("panel"))


if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=int(os.environ.get("PORT", 5001)))
