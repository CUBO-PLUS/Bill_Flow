#!/usr/bin/env python3
"""Auditoría de pagos Bitcoin. NUNCA modifica venta, venta_bitcoin ni cotizacion_btc.

  python3 audit_transactions.py                  # auditoría completa (consulta velas a Coinbase)
  python3 audit_transactions.py --offline        # sin red: solo controles internos
  python3 audit_transactions.py --venta 3 --json
  python3 audit_transactions.py --out reporte.md # guarda el reporte en un archivo
  python3 audit_transactions.py --guardar        # además registra hallazgos en auditoria_btc (append-only)

Códigos: SIN_FUENTE, PRECIO_DIFIERE_HISTORICO, PRECIO_FUERA_DE_VELA, NO_VERIFICABLE, CALCULO_INCORRECTO,
TOTAL_DIFIERE_DETALLE, FECHA_INCONSISTENTE, PENDIENTE_VENCIDO (por antigüedad > BTC_QUOTE_TTL_MIN),
POSIBLE_DUPLICADO, ESQUEMA_ANTIGUO.
Exit code: 0 sin hallazgos ALTA/MEDIA, 1 con ellos, 2 error.
"""
import argparse
import json
import sqlite3
import sys
import time
from datetime import timedelta
from decimal import Decimal

import _comun
import precios_btc as pb

SEV_ORDEN = {"ALTA": 0, "MEDIA": 1, "BAJA": 2, "INFO": 3}


def _cols(db, tabla):
    return {r[1] for r in db.execute('PRAGMA table_info("%s")' % tabla)}


def _tabla(db, nombre):
    return bool(db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (nombre,)).fetchone())


def auditar(db, offline=False, umbral_pct=Decimal("1"), venta=None, get=None, tz=None, ahora=None,
            pausa=0.15):
    """Devuelve (filas_por_venta, hallazgos). db con row_factory=sqlite3.Row."""
    ahora = ahora or pb.utc_ahora()
    hallazgos, filas = [], []
    cols = _cols(db, "venta_bitcoin")
    nuevo = "fuente_precio" in cols

    def h(sev, cod, fila, detalle, **datos):
        hallazgos.append({"severidad": sev, "codigo": cod, "venta_id": fila["venta_id"] if fila else None,
                          "id_pago": fila["id_pago"] if fila else None, "detalle": detalle, "datos": datos})

    if not nuevo:
        h("MEDIA", "ESQUEMA_ANTIGUO", None, "venta_bitcoin aún no tiene las columnas de trazabilidad "
          "(arranca la app para migrar). Todo se audita como 'sin fuente documentada'.")

    q = ("SELECT vb.*, v.fecha_hora AS venta_fecha, t.total_usd AS detalle_total_usd, "
         "v.empleado_id AS venta_empleado FROM venta_bitcoin vb JOIN venta v ON v.id = vb.venta_id "
         "LEFT JOIN v_venta_total t ON t.venta_id = vb.venta_id")
    args = ()
    if venta:
        q += " WHERE vb.venta_id = ?"
        args = (venta,)
    registros = db.execute(q + " ORDER BY vb.venta_id", args).fetchall()

    for r in registros:
        d = dict(r)
        fila = {"venta_id": r["venta_id"], "id_pago": r["id_pago"], "estado": r["estado"],
                "fecha_local": r["fecha_hora"], "total_usd": r["total_usd"],
                "precio_original": r["precio_btc_usd"], "btc_original": r["total_btc"],
                "sats_original": r["total_sats"], "fuente_original": d.get("fuente_precio"),
                "verificabilidad": "no_verificable"}

        # 1. fuente documentada
        if not d.get("fuente_precio") or not d.get("fecha_precio"):
            h("MEDIA", "SIN_FUENTE", r, "El precio %s no tiene fuente ni instante de consulta documentados."
              % r["precio_btc_usd"])
        else:
            fila["verificabilidad"] = "exacto_registrado"

        # 2. recálculo con el precio guardado
        try:
            c = pb.convertir(r["total_usd"], pb.dec(r["precio_btc_usd"]))
            difs = []
            if c["total_sats"] != r["total_sats"]:
                difs.append("sats guardados %d vs recalculados %d" % (r["total_sats"], c["total_sats"]))
            for campo in ("total_btc", "neto_btc", "neto_usd", "iva_usd"):
                if abs(pb.dec(r[campo]) - c[campo]) > Decimal("0.00000001"):
                    difs.append("%s guardado %s vs %s" % (campo, r[campo], c[campo]))
            if difs:
                h("ALTA", "CALCULO_INCORRECTO", r, "; ".join(difs))
        except pb.PrecioInvalido as e:
            h("ALTA", "CALCULO_INCORRECTO", r, "precio inválido: %s" % e)

        # 3. importe vs detalle de la venta
        if r["detalle_total_usd"] is not None and abs(pb.dec(r["detalle_total_usd"]) - pb.dec(r["total_usd"])) > pb.CENT:
            h("ALTA", "TOTAL_DIFIERE_DETALLE", r, "total cobrado %.2f vs detalle de venta %.2f"
              % (r["total_usd"], r["detalle_total_usd"]))

        # 4. fechas
        utc = None
        try:
            utc = pb.local_a_utc(r["fecha_hora"], tz)
            fila["fecha_utc"] = pb.iso_utc(utc)
            if r["venta_fecha"] and abs(pb.local_a_utc(r["venta_fecha"], tz) - utc) > timedelta(minutes=5):
                h("MEDIA", "FECHA_INCONSISTENTE", r, "fecha de venta %s vs cobro %s difieren >5 min"
                  % (r["venta_fecha"], r["fecha_hora"]))
            if d.get("fecha_precio") and abs(pb.parse_utc(d["fecha_precio"]) - utc) > timedelta(minutes=5):
                h("MEDIA", "FECHA_INCONSISTENTE", r, "fecha_precio %s lejos de la fecha del cobro %s"
                  % (d["fecha_precio"], r["fecha_hora"]))
        except ValueError as e:
            h("MEDIA", "FECHA_INCONSISTENTE", r, "fecha ilegible: %s" % e)

        # 5. pendientes vencidos
        if r["estado"] == "pendiente" and utc and ahora - utc > timedelta(minutes=pb.TTL_MINUTOS):
            h("BAJA", "PENDIENTE_VENCIDO", r, "pendiente hace %d min (> %d min de vigencia de cotización)"
              % ((ahora - utc).total_seconds() // 60, pb.TTL_MINUTOS))

        # 6. histórico (aproximado)
        if not offline and utc:
            try:
                time.sleep(pausa)
                hist = pb.precio_historico(utc, get)
            except Exception as e:
                hist = None
                h("INFO", "NO_VERIFICABLE", r, "Coinbase no respondió: %s" % e)
            if hist is None:
                if fila["verificabilidad"] == "no_verificable":
                    h("MEDIA", "NO_VERIFICABLE", r, "sin fuente propia ni vela histórica disponible")
            else:
                orig = pb.dec(r["precio_btc_usd"])
                dif = pb.diferencia_pct(orig, hist["close"])
                rec = pb.convertir(r["total_usd"], hist["close"])
                fila.update({
                    "vela_utc": hist["vela_inicio_utc"], "hist_open": hist["open"], "hist_high": hist["high"],
                    "hist_low": hist["low"], "hist_close": hist["close"], "dif_pct": dif,
                    "btc_reconstruido": rec["total_btc"], "sats_reconstruidos": rec["total_sats"],
                    "dif_sats": r["total_sats"] - rec["total_sats"],
                    "dentro_rango_vela": hist["low"] <= orig <= hist["high"]})
                if fila["verificabilidad"] == "no_verificable":
                    fila["verificabilidad"] = "aproximado_vela"
                if not fila["dentro_rango_vela"] and abs(dif) > umbral_pct:
                    sev = "ALTA" if abs(dif) > 5 else "MEDIA"
                    h(sev, "PRECIO_DIFIERE_HISTORICO", r,
                      "original %s vs cierre de vela %s: %s %% (%+d sats). Referencia APROXIMADA (vela 1 min)."
                      % (orig, hist["close"], dif, fila["dif_sats"]), vela=hist["vela_inicio_utc"])
        filas.append(fila)

    # 7. duplicados y eventos
    for a in registros:
        for b in registros:
            if a["venta_id"] < b["venta_id"] and a["total_usd"] == b["total_usd"] \
               and a["venta_empleado"] == b["venta_empleado"]:
                try:
                    if abs(pb.local_a_utc(a["fecha_hora"], tz) - pb.local_a_utc(b["fecha_hora"], tz)) <= timedelta(seconds=120):
                        h("BAJA", "POSIBLE_DUPLICADO", a, "ventas %d y %d: mismo monto y empleado en <2 min"
                          % (a["venta_id"], b["venta_id"]))
                except ValueError:
                    pass
    hallazgos.sort(key=lambda x: (SEV_ORDEN[x["severidad"]], x["venta_id"] or 0))
    return filas, hallazgos


def reporte_texto(filas, hallazgos):
    out = ["# Auditoría Bitcoin  (%s UTC)" % pb.iso_utc(pb.utc_ahora()), "",
           "## Comparativo por venta (histórico = APROXIMADO, cierre de vela de 1 min)", "",
           "| Venta | Estado | Fecha local | USD | Precio orig. | Fuente | Cierre vela | Dif % | BTC orig. | BTC reconst. | Sats orig. | Sats reconst. | Δ sats | Verificabilidad |",
           "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for f in filas:
        out.append("| %s |" % " | ".join(str(f.get(k, "-")) for k in (
            "venta_id", "estado", "fecha_local", "total_usd", "precio_original", "fuente_original",
            "hist_close", "dif_pct", "btc_original", "btc_reconstruido", "sats_original",
            "sats_reconstruidos", "dif_sats", "verificabilidad")))
    out += ["", "## Hallazgos (%d)" % len(hallazgos), ""]
    out += ["- [%s] %s venta=%s %s: %s" % (x["severidad"], x["codigo"], x["venta_id"], x["id_pago"] or "", x["detalle"])
            for x in hallazgos] or ["- Sin hallazgos."]
    out += ["", "Este reporte no modifica ningún registro. Cualquier corrección requiere autorización expresa."]
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--db", default=_comun.DB_DEFECTO)
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--venta", type=int)
    ap.add_argument("--umbral-pct", type=Decimal, default=Decimal("1"))
    ap.add_argument("--tz", default=pb.TZ_LOCAL)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--out")
    ap.add_argument("--guardar", action="store_true", help="registra hallazgos en auditoria_btc")
    a = ap.parse_args()

    try:
        db = sqlite3.connect("file:%s?mode=%s" % (a.db, "rw" if a.guardar else "ro"), uri=True)
    except sqlite3.Error as e:
        print("No se pudo abrir la base:", e, file=sys.stderr)
        return 2
    db.row_factory = sqlite3.Row
    filas, hall = auditar(db, a.offline, a.umbral_pct, a.venta, tz=a.tz)

    if a.guardar:
        if not _tabla(db, "auditoria_btc"):
            print("auditoria_btc no existe: arranca la app para migrar el esquema.", file=sys.stderr)
            return 2
        ts = pb.iso_utc(pb.utc_ahora())
        db.executemany("INSERT INTO auditoria_btc (ejecutada_utc, venta_id, id_pago, codigo, severidad, detalle, datos_json)"
                       " VALUES (?, ?, ?, ?, ?, ?, ?)",
                       [(ts, x["venta_id"], x["id_pago"], x["codigo"], x["severidad"], x["detalle"],
                         json.dumps(x["datos"], default=str)) for x in hall])
        db.commit()
    db.close()

    texto = json.dumps({"ventas": filas, "hallazgos": hall}, indent=1, default=str) if a.json \
        else reporte_texto(filas, hall)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            f.write(texto)
        print("Reporte guardado en", a.out)
    else:
        print(texto)
    return 1 if any(x["severidad"] in ("ALTA", "MEDIA") for x in hall) else 0


if __name__ == "__main__":
    sys.exit(main())
