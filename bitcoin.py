"""Pagos con Bitcoin: cotización trazable al registrar y confirmación auditable.

Reglas (ver .claude/skills/bitcoin-price-payment-auditor):
- Cada cobro guarda una copia INMUTABLE de la cotización (tabla cotizacion_btc) con fuente,
  instante UTC y respuesta cruda. Sin cotización válida no se crea el cobro.
- Dinero con Decimal (precios_btc.convertir).
- El precio vigente al confirmar se guarda aparte (cotizacion_btc.tipo = 'confirmacion').
"""
import os
import secrets

import precios_btc as pb

# Columnas agregadas a venta_bitcoin (las filas históricas quedan con NULL: no se inventan datos).
COLUMNAS_NUEVAS = {
    "fuente_precio": "TEXT",
    "fecha_precio": "TEXT",          # instante UTC de la consulta del precio
    "iva_btc": "REAL",
    "cotizacion_id": "INTEGER",      # -> cotizacion_btc.id (copia inmutable)
}

TRIGGERS = """
CREATE TRIGGER IF NOT EXISTS venta_bitcoin_pagada_inmutable BEFORE UPDATE ON venta_bitcoin
WHEN OLD.estado = 'pagada'
BEGIN SELECT RAISE(ABORT, 'pago confirmado: no se puede modificar'); END;
CREATE TRIGGER IF NOT EXISTS venta_bitcoin_cotizacion_fija BEFORE UPDATE ON venta_bitcoin
WHEN NEW.precio_btc_usd IS NOT OLD.precio_btc_usd OR NEW.total_usd IS NOT OLD.total_usd
  OR NEW.total_btc IS NOT OLD.total_btc OR NEW.total_sats IS NOT OLD.total_sats
  OR NEW.fecha_hora IS NOT OLD.fecha_hora OR NEW.id_pago IS NOT OLD.id_pago
BEGIN SELECT RAISE(ABORT, 'la cotización original no se sobrescribe'); END;
"""


def migrar(db):
    """Idempotente: crea tablas, agrega columnas nuevas y triggers. No toca filas existentes."""
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "bitcoin.sql"), encoding="utf-8") as f:
        db.executescript(f.read())
    existentes = {r[1] for r in db.execute("PRAGMA table_info(venta_bitcoin)")}
    for col, tipo in COLUMNAS_NUEVAS.items():
        if col not in existentes:
            db.execute("ALTER TABLE venta_bitcoin ADD COLUMN %s %s" % (col, tipo))
    db.executescript(TRIGGERS)
    db.commit()


def calcular(total_usd, precio):
    """El precio ya incluye IVA. Devuelve Decimals (ver precios_btc.convertir)."""
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


def registrar_pendiente(db, venta_id, empleado_id, total_usd, cotizacion):
    """Crea el cobro pendiente con la cotización YA consultada (precios_btc.obtener_cotizacion).
    No hace commit. Devuelve id_pago."""
    c = pb.convertir(total_usd, cotizacion.precio)
    id_pago = "BTC-" + secrets.token_hex(4).upper()
    cot_id = _guardar_cotizacion(db, "registro", venta_id, id_pago, cotizacion)
    db.execute(
        "INSERT INTO venta_bitcoin (venta_id, fecha_hora, empleado_id, total_usd, iva_usd, "
        "neto_usd, precio_btc_usd, total_btc, total_sats, neto_btc, estado, id_pago, "
        "fuente_precio, fecha_precio, iva_btc, cotizacion_id) "
        "VALUES (?, datetime('now','localtime'), ?, ?, ?, ?, ?, ?, ?, ?, 'pendiente', ?, ?, ?, ?, ?)",
        (venta_id, empleado_id, float(c["total_usd"]), float(c["iva_usd"]), float(c["neto_usd"]),
         float(c["precio_btc_usd"]), float(c["total_btc"]), c["total_sats"], float(c["neto_btc"]),
         id_pago, cotizacion.fuente, cotizacion.consultado_utc, float(c["iva_btc"]), cot_id))
    db.execute("UPDATE venta SET precio_btc_usd = ? WHERE id = ?", (float(c["precio_btc_usd"]), venta_id))
    return id_pago


def confirmar(db, pago, get=None):
    """Valida el JSON (id_pago, monto_sats, monto_usd) contra la venta pendiente. Devuelve (ok, mensaje).
    Un pago ya confirmado o con monto distinto NO se confirma."""
    faltan = [k for k in ("id_pago", "monto_sats", "monto_usd") if k not in pago]
    if faltan:
        return False, "JSON incompleto, faltan: " + ", ".join(faltan)

    id_pago = str(pago["id_pago"])
    row = db.execute("SELECT * FROM venta_bitcoin WHERE id_pago = ?", (id_pago,)).fetchone()
    if not row:
        return False, "No existe ninguna venta con id_pago %s." % id_pago
    if row["estado"] != "pendiente":
        return False, "La venta #%d ya está '%s', no se puede confirmar." % (row["venta_id"], row["estado"])

    try:
        sats, usd = int(pago["monto_sats"]), pb.dec(pago["monto_usd"])
    except (TypeError, ValueError):
        return False, "monto_sats o monto_usd no son números válidos."

    esperado_usd = pb.dec(row["total_usd"])
    errores = []
    if sats != row["total_sats"]:
        errores.append("sats: esperado %d, recibido %d (%s)" % (
            row["total_sats"], sats, "insuficiente" if sats < row["total_sats"] else "excesivo"))
    if abs(usd - esperado_usd) > pb.CENT:
        errores.append("USD: esperado %.2f, recibido %.2f" % (esperado_usd, usd))
    if errores:
        return False, "El monto NO coincide (%s). La venta #%d sigue pendiente." % (
            "; ".join(errores), row["venta_id"])

    # Precio vigente AHORA, guardado aparte (si no hay fuente, el pago igual se confirma).
    try:
        _guardar_cotizacion(db, "confirmacion", row["venta_id"], id_pago, pb.obtener_cotizacion(get))
    except pb.CotizacionNoDisponible:
        pass
    db.execute("UPDATE venta_bitcoin SET estado = 'pagada' WHERE id = ?", (row["id"],))
    db.commit()
    return True, "Venta #%d pagada (id_pago %s, %d sats)." % (row["venta_id"], id_pago, sats)
