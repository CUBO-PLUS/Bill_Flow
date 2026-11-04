"""Lógica de pagos con Bitcoin (sin internet): cálculo al registrar y confirmación."""
import os
import secrets
import sqlite3
from datetime import datetime

# Tasa BTC/USD usada al registrar la venta. Sin internet: se configura aquí o con la
# variable de entorno BTC_USD_RATE.
TASA_BTC_USD = float(os.environ.get("BTC_USD_RATE", "100000"))
IVA = 1.13
SATS_POR_BTC = 100_000_000


def calcular(total_usd, tasa):
    """El precio ya incluye IVA: neto = total / 1.13 e IVA = total - neto."""
    neto = round(total_usd / IVA, 2)
    iva = round(total_usd - neto, 2)
    total_btc = total_usd / tasa
    return {
        "total_usd": round(total_usd, 2),
        "iva_usd": iva,
        "neto_usd": neto,
        "precio_btc_usd": tasa,
        "total_btc": round(total_btc, 8),
        "total_sats": round(total_btc * SATS_POR_BTC),
        "neto_btc": round(neto / tasa, 8),
    }


def registrar_pendiente(db, venta_id, empleado_id, total_usd, tasa=None):
    """Crea la fila pendiente y guarda la tasa también en venta.precio_btc_usd. Devuelve id_pago."""
    tasa = tasa or TASA_BTC_USD
    c = calcular(total_usd, tasa)
    id_pago = "BTC-" + secrets.token_hex(4).upper()
    db.execute(
        "INSERT INTO venta_bitcoin (venta_id, fecha_hora, empleado_id, total_usd, iva_usd, "
        "neto_usd, precio_btc_usd, total_btc, total_sats, neto_btc, estado, id_pago) "
        "VALUES (?, datetime('now','localtime'), ?, ?, ?, ?, ?, ?, ?, ?, 'pendiente', ?)",
        (venta_id, empleado_id, c["total_usd"], c["iva_usd"], c["neto_usd"],
         c["precio_btc_usd"], c["total_btc"], c["total_sats"], c["neto_btc"], id_pago),
    )
    db.execute("UPDATE venta SET precio_btc_usd = ? WHERE id = ?", (tasa, venta_id))
    return id_pago


def confirmar(db, pago):
    """Valida el JSON contra la venta pendiente. Devuelve (ok, mensaje)."""
    faltan = [k for k in ("id_pago", "monto_sats", "monto_usd", "tasa", "fecha") if k not in pago]
    if faltan:
        return False, "JSON incompleto, faltan: " + ", ".join(faltan)

    row = db.execute("SELECT * FROM venta_bitcoin WHERE id_pago = ?", (pago["id_pago"],)).fetchone()
    if not row:
        return False, "No existe ninguna venta con id_pago %s." % pago["id_pago"]
    if row["estado"] != "pendiente":
        return False, "La venta #%d ya está '%s', no se puede confirmar." % (row["venta_id"], row["estado"])

    try:
        sats, usd, tasa = int(pago["monto_sats"]), float(pago["monto_usd"]), float(pago["tasa"])
    except (TypeError, ValueError):
        return False, "monto_sats, monto_usd o tasa no son números válidos."

    errores = []
    if sats != row["total_sats"]:
        errores.append("sats: esperado %d, recibido %d" % (row["total_sats"], sats))
    if abs(usd - row["total_usd"]) > 0.01:
        errores.append("USD: esperado %.2f, recibido %.2f" % (row["total_usd"], usd))
    if errores:
        return False, "El monto NO coincide (%s). La venta #%d sigue pendiente." % (
            "; ".join(errores), row["venta_id"])

    db.execute(
        "UPDATE venta_bitcoin SET estado = 'pagada', fecha_confirmacion = ?, tasa_confirmacion = ? "
        "WHERE id = ?", (str(pago["fecha"]), tasa, row["id"]))
    db.commit()
    return True, "Venta #%d pagada (id_pago %s, %d sats, tasa %.2f)." % (
        row["venta_id"], pago["id_pago"], sats, tasa)
