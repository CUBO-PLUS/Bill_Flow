#!/usr/bin/env python3
"""Reconstruye BTC/USD histórico (vela de 1 min de Coinbase). Resultado APROXIMADO, solo lectura.

  python3 historical_prices.py --venta 3                       # lee fecha de la base
  python3 historical_prices.py --fecha "2026-11-04 13:23:35"   # hora local (BTC_LOCAL_TZ)
  python3 historical_prices.py --fecha 2026-11-04T19:23:35Z    # ya en UTC
  añadir --tz America/El_Salvador, --json
"""
import argparse
import json
import sqlite3
import sys

import _comun
import precios_btc as pb


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--venta", type=int)
    g.add_argument("--fecha")
    ap.add_argument("--tz", default=pb.TZ_LOCAL)
    ap.add_argument("--db", default=_comun.DB_DEFECTO)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    texto = a.fecha
    if a.venta:
        db = sqlite3.connect("file:%s?mode=ro" % a.db, uri=True)
        fila = db.execute("SELECT fecha_hora FROM venta WHERE id = ?", (a.venta,)).fetchone()
        if not fila or not fila[0]:
            print("La venta %s no existe o no tiene fecha." % a.venta, file=sys.stderr)
            return 2
        texto = fila[0]
    utc = pb.local_a_utc(texto, a.tz)
    print("Fecha original: %s (%s)  ->  UTC %s" % (texto, a.tz, pb.iso_utc(utc)), file=sys.stderr)
    try:
        r = pb.precio_historico(utc)
    except Exception as e:
        print("SIN DATOS: Coinbase no respondió: %s" % e, file=sys.stderr)
        return 2
    if not r:
        print("SIN DATOS: no hay vela de 1 min para ese instante (precio no verificable).", file=sys.stderr)
        return 2
    if a.json:
        print(json.dumps({k: str(v) if hasattr(v, "quantize") else v for k, v in r.items()}, indent=1))
    else:
        print("vela %s UTC  open=%s high=%s low=%s close=%s vol=%s" % (
            r["vela_inicio_utc"], r["open"], r["high"], r["low"], r["close"], r["volumen"]))
        print("Referencia (cierre): %s USD  [%s]" % (r["close"], r["precision"]))
        print("AVISO: una vela de 1 min no prueba el precio exacto del segundo de la venta.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
