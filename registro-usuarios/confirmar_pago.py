#!/usr/bin/env python3
"""Confirma un pago Bitcoin leyendo un JSON. Funciona sin internet.

  python confirmar_pago.py pago_ejemplo.json   -> confirma la venta
  python confirmar_pago.py --pendientes        -> lista las ventas pendientes y su id_pago
"""
import json
import os
import sqlite3
import sys

from bitcoin import confirmar

DB_PATH = os.environ.get("DB_PATH", os.path.join(os.path.dirname(os.path.abspath(__file__)), "restaurante.db"))


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row

    if sys.argv[1] == "--pendientes":
        filas = db.execute("SELECT * FROM venta_bitcoin WHERE estado = 'pendiente' ORDER BY id").fetchall()
        if not filas:
            print("No hay pagos pendientes.")
        for r in filas:
            print("venta #%d  id_pago=%s  $%.2f  %d sats  tasa=%.2f" % (
                r["venta_id"], r["id_pago"], r["total_usd"], r["total_sats"], r["precio_btc_usd"]))
        return 0

    try:
        with open(sys.argv[1], encoding="utf-8") as f:
            pago = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print("ERROR: no se pudo leer el JSON:", e)
        return 1

    ok, msg = confirmar(db, pago)
    print(("OK: " if ok else "ERROR: ") + msg)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
