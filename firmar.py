"""Firma un DTE con svfe/svfe-api-firmador (puerto 8113) y devuelve el JWS.

Uso directo:
    python3 firmar.py <venta_id>
    python3 firmar.py <venta_id> -o firmado.json

Requiere variables de entorno (o .env):
    FIRMADOR_NIT          NIT del emisor (14 dígitos)
    FIRMADOR_PASSWORD     Contraseña del certificado .crt
    FIRMADOR_URL          URL del firmador (default: http://localhost:8113)
"""
import json
import os
import sqlite3
import sys
import urllib.error
import urllib.request

import dte as dte_mod

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH  = os.environ.get("DB_PATH", os.path.join(BASE_DIR, "restaurante.db"))

FIRMADOR_URL      = os.environ.get("FIRMADOR_URL", "http://localhost:8113")
FIRMADOR_NIT      = os.environ.get("FIRMADOR_NIT", "")
FIRMADOR_PASSWORD = os.environ.get("FIRMADOR_PASSWORD", "")

ENDPOINT = FIRMADOR_URL.rstrip("/") + "/firmardocumento/"


def firmar(dte_json: dict, nit: str = "", password: str = "") -> dict:
    """
    Envía el DTE al firmador y devuelve la respuesta completa.
    La respuesta tiene la clave 'body' con el JWS (header.payload.firma).
    """
    nit      = nit or FIRMADOR_NIT
    password = password or FIRMADOR_PASSWORD
    if not nit or not password:
        raise ValueError("FIRMADOR_NIT y FIRMADOR_PASSWORD son obligatorios")

    payload = json.dumps({
        "nit":         nit,
        "activo":      True,
        "passwordPri": password,
        "dteJson":     dte_json,
    }, ensure_ascii=False).encode()

    req = urllib.request.Request(
        ENDPOINT,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        raise RuntimeError("Firmador HTTP %d: %s" % (e.code, body)) from e


def jws_de_respuesta(resp: dict) -> str:
    """Extrae el JWS de la respuesta del firmador."""
    jws = resp.get("body") or resp.get("jws") or resp.get("firma")
    if not jws:
        raise ValueError("No se encontró el JWS en la respuesta: %s" % list(resp.keys()))
    return jws


def decodificar_jws(jws: str) -> dict:
    """Decodifica la parte payload del JWS (sin verificar firma)."""
    import base64
    partes = jws.split(".")
    if len(partes) != 3:
        raise ValueError("JWS inválido: se esperan 3 partes separadas por '.'")
    padding = 4 - len(partes[1]) % 4
    payload_b64 = partes[1] + ("=" * (padding % 4))
    return json.loads(base64.urlsafe_b64decode(payload_b64).decode())


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)

    con = sqlite3.connect(DB_PATH)
    dte_mod.migrar(con)
    dte_json = dte_mod.construir_dte(con, int(sys.argv[1]))
    if dte_json is None:
        raise SystemExit("No existe esa venta")

    resp = firmar(dte_json)
    jws  = jws_de_respuesta(resp)
    print("JWS:", jws[:80], "...")

    try:
        payload = decodificar_jws(jws)
        print("Payload decodificado OK — tipoDte:", payload.get("identificacion", {}).get("tipoDte"))
    except Exception as exc:
        print("No se pudo decodificar el payload:", exc)

    resultado = {"jws": jws, "dte": dte_json, "firmador_resp": resp}
    if "-o" in sys.argv:
        out = sys.argv[sys.argv.index("-o") + 1]
        with open(out, "w", encoding="utf-8") as f:
            json.dump(resultado, f, ensure_ascii=False, indent=2)
        print("Guardado en", out)
    else:
        print(json.dumps(resultado, ensure_ascii=False, indent=2))
