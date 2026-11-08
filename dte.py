"""Builds the DTE of a sale: dte_plantilla.json (issuer + fixed fields) + SQLite data.

UNSIGNED output: ready to hand to the electronic signer and then to Hacienda.
    python3 dte.py <venta_id> [-o archivo.json]
Types: 01 Invoice (Factura), 03 Tax Credit Voucher (Comprobante de Crédito Fiscal), 11 Export invoice (Factura de exportación).
"""
import json
import os
import sqlite3
import sys
import uuid

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("DB_PATH", os.path.join(BASE_DIR, "restaurante.db"))
PLANTILLA = os.path.join(BASE_DIR, "dte_plantilla.json")
CLIENTES_ENV = os.path.join(BASE_DIR, ".env.clientes")  # NIT/NRC/name/address (CCF), kept outside the DB
IVA = 0.13
NS = uuid.UUID("6f1c1c3e-5a0e-4b8e-9a43-0d1e5b7a2c11")

# Schemas 01 and 11 (v1) only accept payment codes <= 10 and 99; 03 (v3) accepts 11 and 12.
PAGOS_NO_VALIDOS_FE = {"11", "12"}

_U = ["", "UN", "DOS", "TRES", "CUATRO", "CINCO", "SEIS", "SIETE", "OCHO", "NUEVE", "DIEZ", "ONCE", "DOCE",
      "TRECE", "CATORCE", "QUINCE", "DIECISEIS", "DIECISIETE", "DIECIOCHO", "DIECINUEVE", "VEINTE",
      "VEINTIUN", "VEINTIDOS", "VEINTITRES", "VEINTICUATRO", "VEINTICINCO", "VEINTISEIS", "VEINTISIETE",
      "VEINTIOCHO", "VEINTINUEVE"]
_D = ["", "", "", "TREINTA", "CUARENTA", "CINCUENTA", "SESENTA", "SETENTA", "OCHENTA", "NOVENTA"]
_C = ["", "CIENTO", "DOSCIENTOS", "TRESCIENTOS", "CUATROCIENTOS", "QUINIENTOS", "SEISCIENTOS",
      "SETECIENTOS", "OCHOCIENTOS", "NOVECIENTOS"]


def _letras(n):
    if n < 30:
        return _U[n] if n else "CERO"
    if n < 100:
        return _D[n // 10] + (" Y " + _U[n % 10] if n % 10 else "")
    if n == 100:
        return "CIEN"
    if n < 1000:
        return (_C[n // 100] + " " + (_letras(n % 100) if n % 100 else "")).strip()
    if n < 1_000_000:
        m = "MIL" if n // 1000 == 1 else _letras(n // 1000) + " MIL"
        return (m + " " + (_letras(n % 1000) if n % 1000 else "")).strip()
    m = "UN MILLON" if n // 1_000_000 == 1 else _letras(n // 1_000_000) + " MILLONES"
    return (m + " " + (_letras(n % 1_000_000) if n % 1_000_000 else "")).strip()


def total_letras(total):
    ent, cent = divmod(round(total * 100), 100)
    return "%s CON %02d/100 DÓLARES" % (_letras(ent), cent)


def datos_fiscales(venta_id):
    """Last line of .env.clientes for that sale (or None)."""
    res = None
    try:
        with open(CLIENTES_ENV, encoding="utf-8") as f:
            for linea in f:
                try:
                    d = json.loads(linea)
                except ValueError:
                    continue
                if d.get("venta_id") == venta_id:
                    res = d
    except OSError:
        pass
    return res


def codigo_pago(tipo_dte, codigo):
    """Validates the payment code against the document type; if invalid, uses 99 (Others)."""
    if tipo_dte in ("01", "11") and codigo in PAGOS_NO_VALIDOS_FE:
        return "99"
    return codigo


# codigoGeneracion: UPPERCASE UUID, different for each DTE and stored only once in dte_codigo.
# Sales that already existed keep the code they had (uuid5 per sale) so nothing changes.
SQL_DTE_CODIGO = """
CREATE TABLE IF NOT EXISTS dte_codigo (
    venta_id          INTEGER NOT NULL,
    tipo_dte          TEXT NOT NULL,
    codigo_generacion TEXT NOT NULL UNIQUE
                      CHECK (length(codigo_generacion) = 36 AND codigo_generacion = upper(codigo_generacion)),
    creado_utc        TEXT NOT NULL,
    PRIMARY KEY (venta_id, tipo_dte),
    FOREIGN KEY (venta_id) REFERENCES venta(id)
);
CREATE TRIGGER IF NOT EXISTS dte_codigo_no_update BEFORE UPDATE ON dte_codigo
BEGIN SELECT RAISE(ABORT, 'codigoGeneracion is immutable'); END;
CREATE TRIGGER IF NOT EXISTS dte_codigo_no_delete BEFORE DELETE ON dte_codigo
BEGIN SELECT RAISE(ABORT, 'codigoGeneracion is immutable'); END;
"""


def _codigo_legado(venta_id):
    return str(uuid.uuid5(NS, "venta-%d" % venta_id)).upper()


def migrar(db):
    """Idempotent: creates dte_codigo and assigns a code to sales that do not have one yet."""
    db.executescript(SQL_DTE_CODIGO)
    pendientes = db.execute(
        "SELECT v.id, t.codigo FROM venta v JOIN tipo_cliente t ON t.id = v.tipo_cliente_id "
        "WHERE NOT EXISTS (SELECT 1 FROM dte_codigo d WHERE d.venta_id = v.id AND d.tipo_dte = t.codigo)"
    ).fetchall()
    for vid, tipo in pendientes:
        db.execute("INSERT INTO dte_codigo (venta_id, tipo_dte, codigo_generacion, creado_utc) "
                   "VALUES (?, ?, ?, datetime('now'))", (vid, tipo, _codigo_legado(vid)))
    db.commit()


def obtener_codigo_generacion(db, venta_id, tipo_dte):
    """codigoGeneracion of the DTE for that sale and type. The first time it creates an UPPERCASE UUID v4 and stores it.
    Does not commit the transaction: the caller commits."""
    fila = db.execute("SELECT codigo_generacion FROM dte_codigo WHERE venta_id = ? AND tipo_dte = ?",
                      (venta_id, tipo_dte)).fetchone()
    if fila:
        return fila[0]
    codigo = str(uuid.uuid4()).upper()
    db.execute("INSERT INTO dte_codigo (venta_id, tipo_dte, codigo_generacion, creado_utc) "
               "VALUES (?, ?, ?, datetime('now'))", (venta_id, tipo_dte, codigo))
    return codigo


def construir_dte(db, venta_id):
    db.row_factory = sqlite3.Row
    v = db.execute("""SELECT v.*, t.codigo AS tipo_dte, fp.codigo AS pago_cod, fp.nombre AS pago_nombre,
                             vb.id_pago AS btc_id_pago
                      FROM venta v JOIN tipo_cliente t ON t.id = v.tipo_cliente_id
                      JOIN forma_pago fp ON fp.id = v.forma_pago_id
                      LEFT JOIN venta_bitcoin vb ON vb.venta_id = v.id
                      WHERE v.id = ?""", (venta_id,)).fetchone()
    if v is None:
        return None
    filas = db.execute("""SELECT d.platillo_id, d.cantidad, d.precio_unitario, p.nombre
                          FROM detalle_venta d JOIN platillo p ON p.id = d.platillo_id
                          WHERE d.venta_id = ? ORDER BY d.id""", (venta_id,)).fetchall()
    tipo = v["tipo_dte"]
    dte = json.load(open(PLANTILLA, encoding="utf-8"))
    codigo = obtener_codigo_generacion(db, venta_id, tipo)
    db.commit()
    partes = (v["fecha_hora"] or "").split(" ")
    dte["identificacion"].update(
        tipoDte=tipo, fecEmi=partes[0], horEmi=partes[-1],
        codigoGeneracion=codigo,
        numeroControl="DTE-%s-S001P001-%015d" % (tipo, venta_id))
    if tipo == "03":
        dte["identificacion"]["version"] = 3
    dte["identificacion"]["tipoDte"] = tipo

    fis = datos_fiscales(venta_id) or {}
    rec = dte["receptor"]
    if tipo == "03":
        rec = {"nit": fis.get("nit") or fis.get("dui"), "nrc": fis.get("nrc"), "nombre": fis.get("nombre"),
               "codActividad": None, "descActividad": None, "nombreComercial": None,
               "direccion": {"departamento": "06", "municipio": "14", "complemento": fis.get("direccion")},
               "telefono": None, "correo": None}
    else:
        rec["nombre"] = v["cliente_nombre"]
    dte["receptor"] = rec

    items, suma = [], 0.0
    for i, f in enumerate(filas, 1):
        bruto = round(f["cantidad"] * f["precio_unitario"], 2)  # menu prices include VAT
        it = {"numItem": i, "tipoItem": 1, "numeroDocumento": None, "cantidad": f["cantidad"],
              "codigo": str(f["platillo_id"]), "codTributo": None, "uniMedida": 59,
              "descripcion": f["nombre"], "montoDescu": 0, "ventaNoSuj": 0, "ventaExenta": 0}
        if tipo == "03":
            neto = round(f["precio_unitario"] / (1 + IVA), 8)
            gravada = round(f["cantidad"] * neto, 2)
            it.update(precioUni=neto, ventaGravada=gravada, tributos=["20"], psv=0, noGravado=0)
            suma += gravada
        elif tipo == "11":  # export: 0 % rate
            it.update(precioUni=f["precio_unitario"], ventaGravada=bruto, tributos=None, noGravado=0)
            suma += bruto
        else:
            it.update(precioUni=f["precio_unitario"], ventaGravada=bruto, tributos=None, psv=0, noGravado=0,
                      ivaItem=round(bruto / (1 + IVA) * IVA, 2))
            suma += bruto
        items.append(it)
    suma = round(suma, 2)
    dte["cuerpoDocumento"] = items

    if tipo == "03":
        iva = round(suma * IVA, 2)
        total = round(suma + iva, 2)
        trib = [{"codigo": "20", "descripcion": "Impuesto al Valor Agregado 13%", "valor": iva}]
    elif tipo == "11":
        iva, total, trib = 0, suma, None
    else:
        total = suma
        iva, trib = round(suma / (1 + IVA) * IVA, 2), None

    r = {"totalNoSuj": 0, "totalExenta": 0, "totalGravada": suma, "subTotalVentas": suma,
         "descuNoSuj": 0, "descuExenta": 0, "descuGravada": 0, "porcentajeDescuento": 0, "totalDescu": 0,
         "tributos": trib, "subTotal": suma, "ivaRete1": 0, "reteRenta": 0,
         "montoTotalOperacion": total, "totalNoGravado": 0, "totalPagar": total,
         "totalLetras": total_letras(total), "saldoFavor": 0, "condicionOperacion": 1,
         "pagos": [{"codigo": codigo_pago(tipo, v["pago_cod"]), "montoPago": total,
                    "referencia": v["btc_id_pago"], "plazo": None, "periodo": None}],
         "numPagoElectronico": None}
    if tipo == "03":
        r["ivaPerci1"] = 0
    elif tipo == "01":
        r["totalIva"] = iva
    dte["resumen"] = r

    if r["pagos"][0]["codigo"] != v["pago_cod"]:  # actual payment detail (attestation)
        dte["apendice"] = [{"campo": "pagoReal", "etiqueta": "Forma de pago real",
                            "valor": "%s (%s)" % (v["pago_nombre"], v["pago_cod"])}]
    return dte


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    con = sqlite3.connect(DB_PATH)
    migrar(con)
    d = construir_dte(con, int(sys.argv[1]))
    if d is None:
        raise SystemExit("That sale does not exist")
    txt = json.dumps(d, ensure_ascii=False, indent=2)
    if "-o" in sys.argv:
        open(sys.argv[sys.argv.index("-o") + 1], "w", encoding="utf-8").write(txt + "\n")
    else:
        print(txt)
