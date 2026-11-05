#!/usr/bin/env python3
"""Conversión USD <-> BTC <-> satoshis con Decimal (IVA 13 % incluido en el total).

  python3 convert_amount.py --usd 12 --precio 80131.51
  python3 convert_amount.py --sats 12000 --precio 80131.51
"""
import argparse
import json
import sys

import _comun  # noqa: F401
import precios_btc as pb


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--usd")
    g.add_argument("--sats", type=int)
    ap.add_argument("--precio", required=True, help="BTC/USD")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    try:
        usd = a.usd if a.usd else pb.btc_a_usd(pb.sats_a_btc(a.sats), a.precio)
        r = pb.convertir(usd, a.precio)
    except pb.PrecioInvalido as e:
        print("ERROR:", e, file=sys.stderr)
        return 2
    if a.json:
        print(json.dumps({k: str(v) for k, v in r.items()}, indent=1))
    else:
        for k, v in r.items():
            print("%-15s %s" % (k, v))
    return 0


if __name__ == "__main__":
    sys.exit(main())
