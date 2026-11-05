#!/usr/bin/env python3
"""Consulta BTC/USD en Coinbase, Kraken y CoinGecko y compara. Solo lectura, no escribe en la base.

  python3 get_btc_price.py                  # las tres fuentes + discrepancias
  python3 get_btc_price.py --fuente coinbase
  python3 get_btc_price.py --cotizacion     # lo que usaría el sistema (Coinbase -> Kraken validado)
  python3 get_btc_price.py --json
"""
import argparse
import json
import sys

import _comun  # noqa: F401
import precios_btc as pb


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--fuente", choices=sorted(pb.FUENTES))
    ap.add_argument("--cotizacion", action="store_true", help="aplica la política real de obtención")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    if a.cotizacion:
        try:
            cots = {"elegida": pb.obtener_cotizacion()}
        except pb.CotizacionNoDisponible as e:
            print("SIN COTIZACION: %s" % e, file=sys.stderr)
            return 2
    else:
        cots = {}
        for f in ([a.fuente] if a.fuente else sorted(pb.FUENTES)):
            try:
                cots[f] = pb.consultar(f)
            except Exception as e:
                cots[f] = e

    ok = {k: c for k, c in cots.items() if not isinstance(c, Exception)}
    if a.json:
        print(json.dumps({k: ({**c.__dict__, "precio": str(c.precio), "bid": c.bid and str(c.bid),
                                "ask": c.ask and str(c.ask), "respuesta": None}
                               if k in ok else {"error": str(c)}) for k, c in cots.items()},
                         indent=1, default=str))
    else:
        for k, c in cots.items():
            if k in ok:
                extra = "  bid=%s ask=%s" % (c.bid, c.ask) if c.bid else ""
                print("%-10s %12s USD  (%s, %s) %s%s" % (c.fuente, c.precio, c.tipo_precio,
                                                       c.consultado_utc, c.validacion, extra))
            else:
                print("%-10s ERROR: %s" % (k, c))
        if "coinbase" in ok:
            for k, c in ok.items():
                if k != "coinbase":
                    print("  %s vs coinbase: %s %%" % (k, pb.diferencia_pct(c.precio, ok["coinbase"].precio)))
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
