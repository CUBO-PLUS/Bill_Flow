import os
from datetime import datetime
import sqlite3
from functools import wraps

from flask import (Flask, flash, g, redirect, render_template, request,
                   session, url_for)
import bitcoin
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "demo-cambiar-clave")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("DB_PATH", os.path.join(BASE_DIR, "restaurante.db"))
SCHEMA_PATH = os.path.join(BASE_DIR, "restaurante_db.sql")
BITCOIN_SQL_PATH = os.path.join(BASE_DIR, "bitcoin.sql")

ROL_ASISTENTE = "Asistente de caja"
ROL_CONTADOR = "Contador"

# True  = en el registro se puede elegir "Contador" (para la demo).
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


def init_db():
    """Crea la base desde restaurante_db.sql la primera vez."""
    db = sqlite3.connect(DB_PATH)
    existe = db.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='venta'"
    ).fetchone()
    if not existe:
        with open(SCHEMA_PATH, encoding="utf-8") as f:
            db.executescript(f.read())
    # Tabla de pagos Bitcoin (idempotente, también para bases ya creadas)
    with open(BITCOIN_SQL_PATH, encoding="utf-8") as f:
        db.executescript(f.read())
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
        quiere_contador = request.form.get("rol") == "contador"

        if not username or not password:
            flash("Escribe un usuario y una contraseña.")
        else:
            rol = ROL_CONTADOR if (quiere_contador and PERMITIR_REGISTRO_ADMIN) else ROL_ASISTENTE
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
            session["es_admin"] = row["rol"] == ROL_CONTADOR
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
        "contadores": sum(1 for e in empleados if e["rol"] == ROL_CONTADOR),
        "asistentes": sum(1 for e in empleados if e["rol"] == ROL_ASISTENTE),
        "ventas": len(ventas),
        "completas": sum(1 for v in ventas if v["paso"] == 5),
    }
    return render_template("dashboard.html", empleados=empleados, ventas=ventas, stats=stats)


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

        precios = {r["id"]: r["precio_desde"] for r in db.execute(
            "SELECT id, precio_desde FROM platillo WHERE id IN (%s)" % ",".join("?" * len(items)),
            list(items))}
        if len(precios) != len(items):
            flash("Algún platillo no es válido.")
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
            es_btc = db.execute("SELECT 1 FROM forma_pago WHERE id = ? AND nombre = 'Bitcoin'",
                                (pago_id,)).fetchone()
            if es_btc:
                total = sum(precios[pid] * cant for pid, cant in items.items())
                id_pago = bitcoin.registrar_pendiente(db, cur.lastrowid, session["user_id"], total)
                msg += " Pago Bitcoin PENDIENTE, id_pago: %s." % id_pago
            db.commit()
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
