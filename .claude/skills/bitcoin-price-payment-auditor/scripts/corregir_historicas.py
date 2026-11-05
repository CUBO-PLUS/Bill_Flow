#!/usr/bin/env python3
"""Corrección AUTORIZADA de las ventas históricas 3 y 4 (precio fijo 100000 -> cierre de vela Coinbase).

  python3 corregir_historicas.py            # simulación: muestra el antes/después, no escribe
  python3 corregir_historicas.py --aplicar  # respalda la base y aplica en una sola transacción

Qué hace: recalcula precio, BTC y sats con el cierre de la vela de 1 min (APROXIMADO), rellena
fuente/fecha del precio, guarda la cotización en cotizacion_btc y los valores ORIGINALES en
auditoria_btc (codigo CORRECCION_AUTORIZADA). Solo ventas pendientes de la lista; no toca pagadas.
"""
import argparse
import json
import shutil
import sqlite3
import sys

import _comun
import bitcoin
import precios_btc as pb

VENTAS = (3, 4)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--db", default=_comun.DB_DEFECTO)
    ap.add_argument("--aplicar", action="store_true")
    a = ap.parse_args()

    db = sqlite3.connect(a.db, isolation_level=None)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    if a.aplicar:
        respaldo = a.db + ".bak-" + pb.utc_ahora().strftime("%Y%m%dT%H%M%SZ")
        shutil.copy2(a.db, respaldo)
        print("Respaldo:", respaldo)
        bitcoin.migrar(db)

    plan = []
    for vid in VENTAS:
        r = db.execute("SELECT * FROM venta_bitcoin WHERE venta_id = ?", (vid,)).fetchone()
        if not r or r["estado"] != "pendiente":
            print("Venta %d: no existe o no está pendiente; se omite." % vid)
            continue
        if "fuente_precio" in r.keys() and r["fuente_precio"]:
            print("Venta %d: ya tiene fuente documentada; se omite." % vid)
            continue
        h = pb.precio_historico(pb.local_a_utc(r["fecha_hora"]))
        if not h:
            print("Venta %d: sin vela disponible; NO se corrige." % vid)
            continue
        c = pb.convertir(r["total_usd"], h["close"])
        plan.append((r, h, c))
        print("Venta %d  precio %s -> %s | BTC %s -> %s | sats %d -> %d" % (
            vid, r["precio_btc_usd"], h["close"], r["total_btc"], c["total_btc"], r["total_sats"], c["total_sats"]))

    if not a.aplicar:
        print("\nSimulación: nada escrito. Usa --aplicar para ejecutar.")
        return 0
    if not plan:
        return 1

    ts = pb.iso_utc(pb.utc_ahora())
    db.execute("BEGIN")
    try:
        for nombre in ("venta_bitcoin_cotizacion_fija", "venta_bitcoin_pagada_inmutable"):
            db.execute("DROP TRIGGER IF EXISTS " + nombre)
        for r, h, c in plan:
            original = {k: r[k] for k in ("precio_btc_usd", "total_btc", "total_sats", "neto_btc", "iva_usd", "neto_usd")}
            cur = db.execute(
                "INSERT INTO cotizacion_btc (tipo, venta_id, id_pago, precio_btc_usd, fuente, tipo_precio, precision, "
                "consultado_utc, validacion, url, respuesta) VALUES ('registro', ?, ?, ?, 'coinbase', 'vela_cierre', "
                "'aproximada_vela_1m', ?, ?, ?, ?)",
                (r["venta_id"], r["id_pago"], str(c["precio_btc_usd"]), h["vela_inicio_utc"],
                 "CORRECCION AUTORIZADA %s: cierre de vela 1 min (open %s high %s low %s); aproximado" % (
                     ts, h["open"], h["high"], h["low"]), h["url"],
                 json.dumps({k: str(v) for k, v in h.items()})))
            db.execute(
                "UPDATE venta_bitcoin SET precio_btc_usd=?, total_btc=?, total_sats=?, neto_btc=?, iva_btc=?, "
                "fuente_precio='coinbase', fecha_precio=?, cotizacion_id=? WHERE id=?",
                (float(c["precio_btc_usd"]), float(c["total_btc"]), c["total_sats"], float(c["neto_btc"]),
                 float(c["iva_btc"]), h["vela_inicio_utc"], cur.lastrowid, r["id"]))
            db.execute("UPDATE venta SET precio_btc_usd=? WHERE id=?", (float(c["precio_btc_usd"]), r["venta_id"]))
            db.execute(
                "INSERT INTO auditoria_btc (ejecutada_utc, venta_id, id_pago, codigo, severidad, detalle, datos_json) "
                "VALUES (?, ?, ?, 'CORRECCION_AUTORIZADA', 'INFO', ?, ?)",
                (ts, r["venta_id"], r["id_pago"],
                 "Precio fijo 100000 reemplazado por cierre de vela Coinbase %s (aproximado)" % c["precio_btc_usd"],
                 json.dumps({"originales": original}, default=str)))
        for stmt in bitcoin.TRIGGERS.split("END;"):  # se recrean dentro de la misma transacción
            if stmt.strip():
                db.execute(stmt + "END;")
        db.execute("COMMIT")
    except Exception:
        db.execute("ROLLBACK")
        raise
    print("Aplicado.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
