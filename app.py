import calendar
import json
import os
import re
import threading
from datetime import datetime, timedelta
from decimal import Decimal
import sqlite3
from functools import wraps

from flask import (Flask, Response, abort, flash, g, jsonify, redirect, render_template, request,
                   session, url_for)
import bitcoin
import dte as dte_mod
import firmar as firmar_mod
import esquema
from menu_en import MENU_EN
import recibo_pdf
import precios_btc
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "demo-change-key")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("DB_PATH", os.path.join(BASE_DIR, "restaurante.db"))
FIRMADOR_NIT      = os.environ.get("FIRMADOR_NIT",      "06082504011025")
FIRMADOR_PASSWORD = os.environ.get("FIRMADOR_PASSWORD", "test123")
SCHEMA_PATH = os.path.join(BASE_DIR, "restaurante_db.sql")

# Customer tax data (CCF): NOT stored in the database (it would show up in the
# diagram / Data screen). It is saved in a local file ignored by git.
CLIENTES_ENV = os.path.join(BASE_DIR, ".env.clientes")
_env_lock = threading.Lock()


def validar_datos_fiscales(form):
    """Returns (data, error) with the NIT, NRC, name and address from the form."""
    dui = re.sub(r"[\s-]", "", form.get("cf_dui", ""))
    nit = re.sub(r"[\s-]", "", form.get("cf_nit", ""))
    nrc = re.sub(r"[\s-]", "", form.get("cf_nrc", ""))
    nombre = form.get("cf_nombre", "").strip()
    direccion = form.get("cf_direccion", "").strip()
    if dui:  # with a DUI the NIT is not requested
        if not (dui.isdigit() and len(dui) == 9):
            return None, "The DUI must have 9 digits."
        nit = ""
    elif not (nit.isdigit() and len(nit) == 14):
        return None, "The NIT must have 14 digits."
    if not (nrc.isdigit() and 1 <= len(nrc) <= 8):
        return None, "The NRC must contain digits only (max. 8)."
    if not nombre or not direccion:
        return None, "Customer name and address are required."
    return {"dui": dui, "nit": nit, "nrc": nrc, "nombre": nombre, "direccion": direccion}, None


def guardar_datos_fiscales(venta_id, datos):
    """Appends one JSON line per sale to .env.clientes (permissions 600)."""
    linea = json.dumps({"venta_id": venta_id, **datos}, ensure_ascii=False)
    with _env_lock:
        fd = os.open(CLIENTES_ENV, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        with os.fdopen(fd, "a", encoding="utf-8") as f:
            f.write(linea + "\n")


ROL_ASISTENTE = "Cashier Assistant"
ROL_ADMIN = "Administrator"

# True  = "Administrator" can be chosen at sign-up (for the demo).
# False = sign-up only creates "Cashier Assistant" users.
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
    """Old databases: renames the 'Contador' role to 'Administrador' (the CHECK forces rebuilding the table)."""
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
    """Adds 'Bitcoin Lightning' (same code 11 as Bitcoin): drops the UNIQUE on forma_pago.codigo."""
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
    db.execute("INSERT OR IGNORE INTO platillo (categoria_id, nombre, precio_desde) VALUES (6, 'Pear', 1.00)")
    db.commit()


def migrar_jws(db):
    """Adds a jws column to venta to store the signed JWS (idempotent)."""
    cols = [r[1] for r in db.execute("PRAGMA table_info(venta)").fetchall()]
    if "jws" not in cols:
        db.execute("ALTER TABLE venta ADD COLUMN jws TEXT")
        db.commit()


# Spanish catalog labels -> English (display names only; codes and ids do not change).
CATALOGOS_EN = [
    ("categoria_menu", "nombre", [("Desayunos", "Breakfast"), ("Aperitivos & Ensaladas", "Appetizers & Salads"),
        ("Hamburguesas & Sandwiches", "Burgers & Sandwiches"), ("Cuchillo & Tenedor", "Knife & Fork"),
        ("Bebidas & Postres", "Drinks & Desserts")]),
    ("tipo_cliente", "documento", [("Factura", "Invoice"), ("Comprobante de Crédito Fiscal", "Tax Credit Voucher"),
        ("Factura de exportación", "Export Invoice")]),
    ("forma_pago", "nombre", [("Efectivo", "Cash"), ("Tarjeta débito", "Debit card"),
        ("Tarjeta crédito", "Credit card"), ("Cheque", "Check"), ("Transferencia", "Bank transfer"),
        ("Vales o cupones", "Vouchers or coupons"), ("Dinero electrónico", "Electronic money"),
        ("Monedero electrónico", "Electronic wallet"),
        ("Certificado o tarjeta de regalo", "Gift certificate or card"),
        ("Otras criptomonedas", "Other cryptocurrencies"), ("Otros", "Other")]),
    ("DTE_State", "descripcion", [("Recibos emitidos", "Receipts issued"), ("DTE emitidos", "DTEs issued"),
        ("DTE firmado por comerciante", "DTE signed by merchant"), ("DTE mandados a Hacienda", "DTEs sent to Hacienda"),
        ("DTE con sello de confirmación de Hacienda", "DTE with Hacienda confirmation seal")]),
]


def migrar_catalogos_ingles(db):
    """Renames Spanish catalog labels and the roles to English (idempotent)."""
    for tabla, col, pares in CATALOGOS_EN:
        for es, en in pares:
            db.execute("UPDATE %s SET %s = ? WHERE %s = ?" % (tabla, col, col), (en, es))
    fila = db.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='rol'").fetchone()
    if fila and "'Administrador'" in fila[0]:  # the CHECK forces rebuilding the table
        db.commit()
        db.execute("PRAGMA foreign_keys = OFF")
        db.executescript("""
            BEGIN;
            CREATE TABLE rol_nueva (
                id      INTEGER PRIMARY KEY,
                nombre  TEXT NOT NULL UNIQUE
                        CHECK (nombre IN ('Cashier Assistant', 'Administrator'))
            );
            INSERT INTO rol_nueva (id, nombre)
                SELECT id, CASE nombre WHEN 'Asistente de caja' THEN 'Cashier Assistant'
                                       WHEN 'Administrador' THEN 'Administrator' ELSE nombre END FROM rol;
            DROP TABLE rol;
            ALTER TABLE rol_nueva RENAME TO rol;
            COMMIT;
        """)
        db.execute("PRAGMA foreign_keys = ON")
    # Menu items: one-time translation (PRAGMA user_version marks it as done)
    if db.execute("PRAGMA user_version").fetchone()[0] < 1:
        for pid, (nombre, desc) in MENU_EN.items():
            db.execute("UPDATE platillo SET nombre = ?, descripcion = ? WHERE id = ?", (nombre, desc, pid))
        db.execute("PRAGMA user_version = 1")
    db.commit()


def init_db():
    """Creates the database from restaurante_db.sql the first time."""
    db = sqlite3.connect(DB_PATH)
    existe = db.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='venta'"
    ).fetchone()
    if not existe:
        with open(SCHEMA_PATH, encoding="utf-8") as f:
            db.executescript(f.read())
    migrar_rol_administrador(db)
    migrar_lightning(db)
    migrar_catalogos_ingles(db)
    # Bitcoin payments: tables, traceability columns and triggers (idempotent)
    db.row_factory = sqlite3.Row
    bitcoin.migrar(db)
    dte_mod.migrar(db)
    migrar_jws(db)
    db.close()


init_db()


def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        # If the session belongs to a user that no longer exists, it is invalidated.
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
            flash("Only administrators can do that.")
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
            flash("Enter a username and a password.")
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
                flash("User created. You can now log in.")
                return redirect(url_for("login"))
            except sqlite3.IntegrityError:
                flash("That username already exists.")

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
        flash("Incorrect username or password.")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


VENTAS_SQL = """
    SELECT v.id, v.fecha_hora, v.cliente_nombre, tc.documento,
           fp.nombre AS forma_pago, e.nombre_usuario AS empleado,
           ed.paso, ed.nombre AS estado, t.total_usd,
           vb.estado AS btc_estado, vb.id_pago AS btc_id_pago, v.jws
    FROM venta v
    JOIN tipo_cliente tc ON tc.id = v.tipo_cliente_id
    JOIN forma_pago fp ON fp.id = v.forma_pago_id
    LEFT JOIN empleado e ON e.id = v.empleado_id
    LEFT JOIN DTE_State ed ON ed.id = v.estado_dte_id
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


RANGOS = {"hoy": "Today", "semana": "This week", "mes": "This month"}


def _rango_fechas(rango):
    """(start, end) as datetime; end is exclusive. Week = Monday to today; month = day 1 to today."""
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
    """Daily close data for Today / Week / Month."""
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

    # Time series: by hour (today) or by day (week / month), filling gaps with 0
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


@app.route("/bitcoin")
@login_required
@admin_required
def bitcoin_detalle():
    """Bitcoin payment details (venta_bitcoin table) by day, week or month. Read-only."""
    rango = request.args.get("rango", "hoy")
    if rango not in RANGOS:
        rango = "hoy"
    ini, fin = _rango_fechas(rango)
    db = get_db()
    pagos = [dict(r) for r in db.execute(
        "SELECT vb.*, e.nombre_usuario AS empleado FROM venta_bitcoin vb "
        "LEFT JOIN empleado e ON e.id = vb.empleado_id "
        "WHERE vb.fecha_hora >= ? AND vb.fecha_hora < ? ORDER BY vb.id DESC",
        (ini.strftime("%Y-%m-%d %H:%M:%S"), fin.strftime("%Y-%m-%d %H:%M:%S")))]

    def dec(x):
        return Decimal(str(x or 0))

    resumen = {"pagos": len(pagos), "sats": 0, "btc": Decimal("0"), "usd": Decimal("0"),
               "neto": Decimal("0"), "iva": Decimal("0"),
               "sats_pagado": 0, "usd_pagado": Decimal("0"),
               "sats_pendiente": 0, "usd_pendiente": Decimal("0"),
               "estados": {"pendiente": 0, "pagada": 0, "rechazada": 0}}
    for p in pagos:
        usd, neto, iva = dec(p["total_usd"]), dec(p["neto_usd"]), dec(p["iva_usd"])
        sats = p["total_sats"] or 0
        resumen["sats"] += sats
        resumen["btc"] += dec(p["total_btc"])
        resumen["usd"] += usd
        resumen["neto"] += neto
        resumen["iva"] += iva
        resumen["estados"][p["estado"]] = resumen["estados"].get(p["estado"], 0) + 1
        if p["estado"] == "pagada":
            resumen["sats_pagado"] += sats
            resumen["usd_pagado"] += usd
        elif p["estado"] == "pendiente":
            resumen["sats_pendiente"] += sats
            resumen["usd_pendiente"] += usd
        p["pct_neto"] = float(neto / usd * 100) if usd else 0.0
        p["pct_iva"] = 100.0 - p["pct_neto"]
        p["consulta"] = (p["fecha_precio"] or "")[:16].replace("T", " ") or "—"
    resumen["pct_pagado"] = float(resumen["usd_pagado"] / resumen["usd"] * 100) if resumen["usd"] else 0.0
    return render_template("bitcoin.html", pagos=pagos, r=resumen, rango=rango,
                           periodo=RANGOS[rango],
                           desde=ini.strftime("%d/%m/%Y"),
                           hasta=(fin - timedelta(days=1)).strftime("%d/%m/%Y"))


def _firmar_pendientes(db):
    """Signs every DTE with paso>=3 that has no JWS yet. Individual errors are silenced."""
    pendientes = db.execute(
        "SELECT v.id FROM venta v JOIN DTE_State d ON d.id = v.estado_dte_id "
        "WHERE d.paso >= 3 AND (v.jws IS NULL OR v.jws = '')"
    ).fetchall()
    firmados = 0
    for row in pendientes:
        try:
            dte_json = dte_mod.construir_dte(db, row["id"])
            if dte_json is None:
                continue
            resp = firmar_mod.firmar(dte_json, nit=FIRMADOR_NIT, password=FIRMADOR_PASSWORD)
            jws  = firmar_mod.jws_de_respuesta(resp)
            db.execute("UPDATE venta SET jws = ? WHERE id = ?", (jws, row["id"]))
            firmados += 1
        except Exception:
            continue
    if firmados:
        db.commit()
    return firmados


@app.route("/dte")
@login_required
@admin_required
def dte_lista():
    db = get_db()
    _firmar_pendientes(db)
    ventas = db.execute(VENTAS_SQL + " ORDER BY v.id DESC").fetchall()
    return render_template("dte_ventas.html", ventas=ventas)


@app.route("/ventas/firmar-pendientes", methods=["POST"])
@login_required
@admin_required
def firmar_pendientes():
    n = _firmar_pendientes(get_db())
    flash("%d DTE(s) signed automatically." % n if n else "There were no DTEs pending signature.")
    return redirect(url_for("panel"))


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
    """Visual view of the real database (schema, PK/FK and rows), always up to date."""
    return render_template("data.html", lucid_url=esquema.lucid_url())


@app.route("/data/json")
@login_required
@admin_required
def data_json():
    """Schema + all rows (the Data screen polls this every few seconds)."""
    entidades, relaciones = esquema.leer_esquema(get_db(), con_filas=500)
    return jsonify(entidades=entidades, relaciones=relaciones)


# Suggested dishes when there are no sales yet to tell which ones are frequent.
FRECUENTES_DEFAULT = [15, 83, 3, 2, 85, 82]


@app.route("/ventas/nueva", methods=["GET", "POST"])
@login_required
def nueva_venta():
    db = get_db()
    if request.method == "POST":
        # items arrives as "platillo_id:quantity,platillo_id:quantity"
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
            flash("Add at least one dish and check the sale details.")
            return redirect(url_for("nueva_venta"))

        fiscales = None
        tipo = db.execute("SELECT codigo FROM tipo_cliente WHERE id = ?", (tipo_id,)).fetchone()
        if tipo and tipo["codigo"] == "03":  # Tax Credit Voucher (Comprobante de Crédito Fiscal)
            fiscales, error = validar_datos_fiscales(request.form)
            if error:
                flash(error)
                return redirect(url_for("nueva_venta"))

        precios = {r["id"]: r["precio_desde"] for r in db.execute(
            "SELECT id, precio_desde FROM platillo WHERE id IN (%s)" % ",".join("?" * len(items)),
            list(items))}
        if len(precios) != len(items):
            flash("One of the dishes is not valid.")
            return redirect(url_for("nueva_venta"))

        total = sum(precios[pid] * cant for pid, cant in items.items())
        es_btc = db.execute("SELECT 1 FROM forma_pago WHERE id = ? AND codigo = '11'",
                            (pago_id,)).fetchone()
        cotizacion = None
        if es_btc:
            try:  # without a valid quote the sale and the charge are NOT created
                cotizacion = precios_btc.obtener_cotizacion()
            except precios_btc.CotizacionNoDisponible:
                flash("No BTC/USD price is available (Coinbase and Kraken failed). "
                      "The sale was not recorded; try again or use another payment method.")
                return redirect(url_for("nueva_venta"))

        try:
            cur = db.execute(
                "INSERT INTO venta (fecha_hora, tipo_cliente_id, forma_pago_id, "
                "empleado_id, estado_dte_id) VALUES (datetime('now','localtime'), ?, ?, ?, "
                "(SELECT id FROM DTE_State WHERE paso = 1))",
                (tipo_id, pago_id, session["user_id"]),
            )
            db.executemany(
                "INSERT INTO detalle_venta (venta_id, platillo_id, cantidad, precio_unitario) "
                "VALUES (?, ?, ?, ?)",
                [(cur.lastrowid, pid, cant, precios[pid]) for pid, cant in items.items()],
            )
            # DTE codigoGeneracion: created with the sale (unique, uppercase UUID, stored once)
            dte_mod.obtener_codigo_generacion(db, cur.lastrowid, tipo["codigo"])
            msg = "Sale #%04d recorded." % cur.lastrowid
            if es_btc:
                id_pago = bitcoin.registrar_pendiente(
                    db, cur.lastrowid, session["user_id"], total, cotizacion)
                msg += " Bitcoin payment PENDING, id_pago: %s (BTC/USD %s via %s)." % (
                    id_pago, cotizacion.precio, cotizacion.fuente)
            db.commit()
            if fiscales:
                guardar_datos_fiscales(cur.lastrowid, fiscales)
            flash(msg)
        except sqlite3.IntegrityError:
            db.rollback()
            flash("Invalid document type or payment method.")
        return redirect(url_for("nueva_venta"))

    categorias = [dict(r) for r in db.execute("SELECT id, nombre FROM categoria_menu ORDER BY id")]
    platillos = [dict(r) for r in db.execute(
        "SELECT id, categoria_id, nombre, precio_desde FROM platillo ORDER BY id")]
    mango = db.execute("SELECT id FROM platillo WHERE nombre = 'Pear'").fetchone()
    frecuentes = ([mango["id"]] if mango else []) + list(FRECUENTES_DEFAULT)
    return render_template(
        "registrar_venta.html", categorias=categorias, platillos=platillos,
        frecuentes=frecuentes,
        tipos=[dict(r) for r in db.execute("SELECT id, codigo, documento FROM tipo_cliente ORDER BY id")],
        pagos=[dict(r) for r in db.execute("SELECT id, nombre FROM forma_pago ORDER BY (nombre = 'Bitcoin Lightning') DESC, id")],
        ahora=datetime.now().strftime("%d/%m/%Y %H:%M"),
    )


@app.route("/ventas/<int:vid>/firmar", methods=["POST"])
@login_required
@admin_required
def firmar_venta(vid):
    db = get_db()
    venta = db.execute(
        "SELECT ed.paso FROM venta v LEFT JOIN DTE_State ed ON ed.id = v.estado_dte_id WHERE v.id = ?",
        (vid,)).fetchone()
    if venta is None:
        abort(404)
    if (venta["paso"] or 0) != 2:
        flash("Only DTEs in 'DTE Done' status can be signed.")
        return redirect(url_for("panel"))
    dte_json = dte_mod.construir_dte(db, vid)
    if dte_json is None:
        flash("Could not build the DTE for sale #%04d." % vid)
        return redirect(url_for("panel"))
    try:
        resp = firmar_mod.firmar(dte_json, nit=FIRMADOR_NIT, password=FIRMADOR_PASSWORD)
        jws  = firmar_mod.jws_de_respuesta(resp)
    except Exception as exc:
        flash("Error signing DTE #%04d: %s" % (vid, exc))
        return redirect(url_for("panel"))
    db.execute(
        "UPDATE venta SET jws = ?, estado_dte_id = (SELECT id FROM DTE_State WHERE paso = 3) WHERE id = ?",
        (jws, vid))
    db.commit()
    flash("DTE #%04d signed successfully (JWS generated)." % vid)
    return redirect(url_for("panel"))


@app.route("/dte/<int:vid>/jws")
@login_required
@admin_required
def dte_jws(vid):
    row = get_db().execute("SELECT jws FROM venta WHERE id = ?", (vid,)).fetchone()
    if row is None or not row["jws"]:
        abort(404)
    codigo = get_db().execute(
        "SELECT codigo_generacion FROM dte_codigo WHERE venta_id = ? LIMIT 1", (vid,)).fetchone()
    cg = codigo["codigo_generacion"] if codigo else "%04d" % vid
    filename = "%s.json" % cg
    body = json.dumps({"status": "OK", "body": row["jws"], "codigoGeneracion": cg},
                      ensure_ascii=False, indent=2)
    return Response(body, mimetype="application/json",
                    headers={"Content-Disposition": "attachment; filename=%s" % filename})


@app.route("/ventas/<int:vid>/avanzar", methods=["POST"])
@login_required
@admin_required
def avanzar_venta(vid):
    db = get_db()
    db.execute(
        """UPDATE venta SET estado_dte_id = (
               SELECT id FROM DTE_State WHERE paso =
                 COALESCE((SELECT paso FROM DTE_State WHERE id = venta.estado_dte_id), 0) + 1)
           WHERE id = ? AND COALESCE(
                 (SELECT paso FROM DTE_State WHERE id = venta.estado_dte_id), 0) < 5""",
        (vid,),
    )
    db.commit()
    flash("Sale: DTE status updated.")
    return redirect(url_for("panel"))


IVA_TASA = Decimal("0.13")
PAGO_CUENTA_TASA = Decimal("0.0175")


def _datos_tributarios(periodo, db):
    """Computes all tax data for the given month (periodo='YYYY-MM')."""
    try:
        año, mes = int(periodo[:4]), int(periodo[5:7])
    except (ValueError, IndexError):
        año, mes = datetime.now().year, datetime.now().month
    ultimo_dia = calendar.monthrange(año, mes)[1]
    ini = "%04d-%02d-01 00:00:00" % (año, mes)
    fin = "%04d-%02d-%02d 23:59:59" % (año, mes, ultimo_dia)

    ventas = [dict(r) for r in db.execute("""
        SELECT v.id, v.fecha_hora, tc.codigo AS tipo_doc, tc.documento,
               fp.nombre AS pago, t.total_usd, dc.codigo_generacion
        FROM venta v
        JOIN tipo_cliente tc ON tc.id = v.tipo_cliente_id
        JOIN forma_pago fp ON fp.id = v.forma_pago_id
        LEFT JOIN v_venta_total t ON t.venta_id = v.id
        LEFT JOIN dte_codigo dc ON dc.venta_id = v.id
        WHERE v.fecha_hora >= ? AND v.fecha_hora <= ?
        ORDER BY v.fecha_hora
    """, (ini, fin)).fetchall()]

    cf, ccf, expo = [], [], []
    for v in ventas:
        total = Decimal(str(v["total_usd"] or 0))
        neto = (total / (1 + IVA_TASA)).quantize(Decimal("0.01"))
        iva  = (total - neto).quantize(Decimal("0.01"))
        v["total_d"] = total
        v["neto_d"]  = neto
        v["iva_d"]   = iva
        if v["tipo_doc"] == "03":
            ccf.append(v)
        elif v["tipo_doc"] == "11":
            expo.append(v)
        else:
            cf.append(v)

    def sumar(lst, campo):
        return sum(v[campo] for v in lst)

    total_cf   = sumar(cf,   "total_d")
    neto_cf    = sumar(cf,   "neto_d")
    iva_cf     = sumar(cf,   "iva_d")
    total_ccf  = sumar(ccf,  "total_d")
    neto_ccf   = sumar(ccf,  "neto_d")
    iva_ccf    = sumar(ccf,  "iva_d")
    total_expo = sumar(expo, "total_d")

    debito_fiscal = iva_cf + iva_ccf
    total_gravadas_neto = neto_cf + neto_ccf
    total_ventas = total_cf + total_ccf + total_expo

    # F-14: 1.75 % advance payment on gross sales (gross income of the month)
    pago_cuenta = (total_ventas * PAGO_CUENTA_TASA).quantize(Decimal("0.01"))

    return {
        "periodo": "%04d-%02d" % (año, mes),
        "año": año, "mes": mes,
        "mes_nombre": ["", "January", "February", "March", "April", "May", "June",
                       "July", "August", "September", "October", "November", "December"][mes],
        "ini": ini[:10], "fin": fin[:10],
        "cf":   cf,   "total_cf":   total_cf,   "neto_cf":   neto_cf,   "iva_cf":   iva_cf,
        "ccf":  ccf,  "total_ccf":  total_ccf,  "neto_ccf":  neto_ccf,  "iva_ccf":  iva_ccf,
        "expo": expo, "total_expo": total_expo,
        "total_gravadas_neto": total_gravadas_neto,
        "debito_fiscal": debito_fiscal,
        "total_ventas": total_ventas,
        "pago_cuenta": pago_cuenta,
    }


@app.route("/f07")
@login_required
@admin_required
def f07():
    periodo = request.args.get("periodo", datetime.now().strftime("%Y-%m"))
    d = _datos_tributarios(periodo, get_db())
    return render_template("f07.html", d=d)


@app.route("/f07/csv")
@login_required
@admin_required
def f07_csv():
    periodo = request.args.get("periodo", datetime.now().strftime("%Y-%m"))
    d = _datos_tributarios(periodo, get_db())
    rows = ["Sales Ledger - Final Consumers"]
    rows.append("#,Date,DTE Code,Document,Payment Method,Total incl. VAT,Net,VAT 13%")
    for i, v in enumerate(d["cf"], 1):
        rows.append("%d,%s,%s,%s,%s,%.2f,%.2f,%.2f" % (
            i, (v["fecha_hora"] or "")[:10],
            v["codigo_generacion"] or ("#%04d" % v["id"]),
            v["documento"], v["pago"],
            float(v["total_d"]), float(v["neto_d"]), float(v["iva_d"])))
    rows.append("TOTALS,,,,,$%.2f,$%.2f,$%.2f" % (
        float(d["total_cf"]), float(d["neto_cf"]), float(d["iva_cf"])))
    rows.append("")
    rows.append("Sales Ledger - Taxpayers (CCF)")
    rows.append("#,Date,DTE Code,Document,Payment Method,Total incl. VAT,Net,VAT 13%")
    for i, v in enumerate(d["ccf"], 1):
        rows.append("%d,%s,%s,%s,%s,%.2f,%.2f,%.2f" % (
            i, (v["fecha_hora"] or "")[:10],
            v["codigo_generacion"] or ("#%04d" % v["id"]),
            v["documento"], v["pago"],
            float(v["total_d"]), float(v["neto_d"]), float(v["iva_d"])))
    rows.append("TOTALS,,,,,$%.2f,$%.2f,$%.2f" % (
        float(d["total_ccf"]), float(d["neto_ccf"]), float(d["iva_ccf"])))
    rows.append("")
    rows.append("Anexo F-07")
    rows.append("Box,Description,Value")
    rows.append("1,Net sales CF (excl. VAT),%.2f" % float(d["neto_cf"]))
    rows.append("2,Net sales CCF (excl. VAT),%.2f" % float(d["neto_ccf"]))
    rows.append("3,Total net taxable sales,%.2f" % float(d["total_gravadas_neto"]))
    rows.append("5,VAT payable CF (13%%),%.2f" % float(d["iva_cf"]))
    rows.append("6,VAT payable CCF (13%%),%.2f" % float(d["iva_ccf"]))
    rows.append("7,Total VAT payable,%.2f" % float(d["debito_fiscal"]))
    rows.append("9,VAT due (no input tax credit),%.2f" % float(d["debito_fiscal"]))
    csv_text = "\n".join(rows)
    filename = "F07_%s.csv" % d["periodo"]
    return Response(csv_text, mimetype="text/csv; charset=utf-8",
                    headers={"Content-Disposition": "attachment; filename=%s" % filename})


@app.route("/f14")
@login_required
@admin_required
def f14():
    periodo = request.args.get("periodo", datetime.now().strftime("%Y-%m"))
    d = _datos_tributarios(periodo, get_db())
    return render_template("f14.html", d=d)


@app.route("/f14/csv")
@login_required
@admin_required
def f14_csv():
    periodo = request.args.get("periodo", datetime.now().strftime("%Y-%m"))
    d = _datos_tributarios(periodo, get_db())
    rows = ["F-14 Base - Advance Payment"]
    rows.append("Box,Description,Value")
    rows.append("1,Final consumer sales income,%.2f" % float(d["total_cf"]))
    rows.append("2,Taxpayer (CCF) sales income,%.2f" % float(d["total_ccf"]))
    if d["total_expo"] > 0:
        rows.append("3,Export income,%.2f" % float(d["total_expo"]))
    rows.append("4,Total gross income for the period,%.2f" % float(d["total_ventas"]))
    rows.append("5,Advance payment rate,1.75%")
    rows.append("6,Advance payment for the month,%.2f" % float(d["pago_cuenta"]))
    rows.append("7,Income tax withholdings received,enter manually")
    rows.append("8,VAT perceptions received,enter manually")
    rows.append("9,Total payable on F-14,%.2f" % float(d["pago_cuenta"]))
    rows.append("")
    rows.append("Sales detail for the period")
    rows.append("#,Date,Document,Payment Method,Total,Advance Payment (1.75%)")
    todas = sorted(d["cf"] + d["ccf"] + d["expo"], key=lambda v: v["fecha_hora"] or "")
    for i, v in enumerate(todas, 1):
        rows.append("%d,%s,%s,%s,%.2f,%.4f" % (
            i, (v["fecha_hora"] or "")[:10],
            v["documento"], v["pago"],
            float(v["total_d"]), float(v["total_d"]) * 0.0175))
    rows.append("TOTALS,,,,$%.2f,$%.2f" % (float(d["total_ventas"]), float(d["pago_cuenta"])))
    csv_text = "\n".join(rows)
    filename = "F14_%s.csv" % d["periodo"]
    return Response(csv_text, mimetype="text/csv; charset=utf-8",
                    headers={"Content-Disposition": "attachment; filename=%s" % filename})


if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=int(os.environ.get("PORT", 5001)))
