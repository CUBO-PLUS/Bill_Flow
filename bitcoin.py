"""Bitcoin payments: traceable quote when recording and auditable confirmation.

Rules (see .claude/skills/bitcoin-price-payment-auditor):
- Each charge stores an IMMUTABLE copy of the quote (cotizacion_btc table) with source,
  UTC instant and raw response. Without a valid quote the charge is not created.
- Money uses Decimal (precios_btc.convertir).
- The price in effect at confirmation is stored separately (cotizacion_btc.tipo = 'confirmacion').
"""
import os
import secrets

import precios_btc as pb

# Columns added to venta_bitcoin (historical rows keep NULL: no data is invented).
COLUMNAS_NUEVAS = {
    "fuente_precio": "TEXT",
    "fecha_precio": "TEXT",          # UTC instant of the price query
    "iva_btc": "REAL",
    "cotizacion_id": "INTEGER",      # -> cotizacion_btc.id (immutable copy)
}

TRIGGERS = """
CREATE TRIGGER IF NOT EXISTS venta_bitcoin_pagada_inmutable BEFORE UPDATE ON venta_bitcoin
WHEN OLD.estado = 'pagada'
BEGIN SELECT RAISE(ABORT, 'payment confirmed: cannot be modified'); END;
CREATE TRIGGER IF NOT EXISTS venta_bitcoin_cotizacion_fija BEFORE UPDATE ON venta_bitcoin
WHEN NEW.precio_btc_usd IS NOT OLD.precio_btc_usd OR NEW.total_usd IS NOT OLD.total_usd
  OR NEW.total_btc IS NOT OLD.total_btc OR NEW.total_sats IS NOT OLD.total_sats
  OR NEW.fecha_hora IS NOT OLD.fecha_hora OR NEW.id_pago IS NOT OLD.id_pago
BEGIN SELECT RAISE(ABORT, 'the original quote is never overwritten'); END;
"""


def migrar(db):
    """Idempotent: creates tables, adds new columns and triggers. Does not touch existing rows."""
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "bitcoin.sql"), encoding="utf-8") as f:
        db.executescript(f.read())
    existentes = {r[1] for r in db.execute("PRAGMA table_info(venta_bitcoin)")}
    for col, tipo in COLUMNAS_NUEVAS.items():
        if col not in existentes:
            db.execute("ALTER TABLE venta_bitcoin ADD COLUMN %s %s" % (col, tipo))
    db.executescript(TRIGGERS)
    db.commit()


def calcular(total_usd, precio):
    """The price already includes VAT. Returns Decimals (see precios_btc.convertir)."""
    return pb.convertir(total_usd, precio)


def _guardar_cotizacion(db, tipo, venta_id, id_pago, cot):
    cur = db.execute(
        "INSERT INTO cotizacion_btc (tipo, venta_id, id_pago, precio_btc_usd, fuente, tipo_precio, "
        "precision, bid, ask, consultado_utc, validacion, url, respuesta) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (tipo, venta_id, id_pago, str(cot.precio), cot.fuente, cot.tipo_precio, cot.precision,
         None if cot.bid is None else str(cot.bid), None if cot.ask is None else str(cot.ask),
         cot.consultado_utc, cot.validacion, cot.url, cot.respuesta))
    return cur.lastrowid


def registrar_pendiente(db, venta_id, empleado_id, total_usd, cotizacion, pagado=False):
    """Creates the charge with the quote ALREADY fetched (precios_btc.obtener_cotizacion).
    Pending by default; with pagado=True (Lightning "Payment successful" confirmed by the cashier)
    it is created directly as 'pagada'. Does not commit. Returns id_pago."""
    c = pb.convertir(total_usd, cotizacion.precio)
    id_pago = "BTC-" + secrets.token_hex(4).upper()
    cot_id = _guardar_cotizacion(db, "registro", venta_id, id_pago, cotizacion)
    if pagado:  # the price in effect at confirmation is this same one (confirmed at the register)
        _guardar_cotizacion(db, "confirmacion", venta_id, id_pago, cotizacion)
    db.execute(
        "INSERT INTO venta_bitcoin (venta_id, fecha_hora, empleado_id, total_usd, iva_usd, "
        "neto_usd, precio_btc_usd, total_btc, total_sats, neto_btc, estado, id_pago, "
        "fuente_precio, fecha_precio, iva_btc, cotizacion_id) "
        "VALUES (?, datetime('now','localtime'), ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (venta_id, empleado_id, float(c["total_usd"]), float(c["iva_usd"]), float(c["neto_usd"]),
         float(c["precio_btc_usd"]), float(c["total_btc"]), c["total_sats"], float(c["neto_btc"]),
         "pagada" if pagado else "pendiente", id_pago, cotizacion.fuente, cotizacion.consultado_utc, float(c["iva_btc"]), cot_id))
    db.execute("UPDATE venta SET precio_btc_usd = ? WHERE id = ?", (float(c["precio_btc_usd"]), venta_id))
    return id_pago


def confirmar(db, pago, get=None):
    """Validates the JSON (id_pago, monto_sats, monto_usd) against the pending sale. Returns (ok, message).
    An already confirmed payment, or one with a different amount, is NOT confirmed."""
    faltan = [k for k in ("id_pago", "monto_sats", "monto_usd") if k not in pago]
    if faltan:
        return False, "Incomplete JSON, missing: " + ", ".join(faltan)

    id_pago = str(pago["id_pago"])
    row = db.execute("SELECT * FROM venta_bitcoin WHERE id_pago = ?", (id_pago,)).fetchone()
    if not row:
        return False, "No sale exists with id_pago %s." % id_pago
    if row["estado"] != "pendiente":
        return False, "Sale #%d is already '%s', it cannot be confirmed." % (row["venta_id"], row["estado"])

    try:
        sats, usd = int(pago["monto_sats"]), pb.dec(pago["monto_usd"])
    except (TypeError, ValueError):
        return False, "monto_sats or monto_usd are not valid numbers."

    esperado_usd = pb.dec(row["total_usd"])
    errores = []
    if sats != row["total_sats"]:
        errores.append("sats: expected %d, received %d (%s)" % (
            row["total_sats"], sats, "insufficient" if sats < row["total_sats"] else "excessive"))
    if abs(usd - esperado_usd) > pb.CENT:
        errores.append("USD: expected %.2f, received %.2f" % (esperado_usd, usd))
    if errores:
        return False, "The amount does NOT match (%s). Sale #%d remains pending." % (
            "; ".join(errores), row["venta_id"])

    # Price in effect NOW, stored separately (if there is no source, the payment is still confirmed).
    try:
        _guardar_cotizacion(db, "confirmacion", row["venta_id"], id_pago, pb.obtener_cotizacion(get))
    except pb.CotizacionNoDisponible:
        pass
    db.execute("UPDATE venta_bitcoin SET estado = 'pagada' WHERE id = ?", (row["id"],))
    db.commit()
    return True, "Sale #%d paid (id_pago %s, %d sats)." % (row["venta_id"], id_pago, sats)
