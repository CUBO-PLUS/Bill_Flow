"""BTC/USD prices and financial conversions (standard library only).

- Decimal arithmetic (never float).
- Primary source Coinbase, fallback Kraken (validated), cross-check CoinGecko.
- Coinbase Exchange 1-minute historical candles (APPROXIMATE reconstruction).
- Conversion of the sale's local time to UTC.

This module is used by the backend (bitcoin.py / app.py) and the tools of the skill
.claude/skills/bitcoin-price-payment-auditor. It does not write to the database.
"""
import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from zoneinfo import ZoneInfo

IVA_DIVISOR = Decimal("1.13")          # 13 % VAT included in the price
SATS_POR_BTC = Decimal(100_000_000)
CENT = Decimal("0.01")
OCHO = Decimal("0.00000001")
UA = "registro-usuarios-btc/1.0"
TIMEOUT = 5
MAX_SPREAD = Decimal("0.01")           # Kraken: maximum accepted (ask-bid)/bid
MAX_DESVIO_CONTRASTE = Decimal("0.02")  # Kraken vs CoinGecko maximum accepted
TZ_LOCAL = os.environ.get("BTC_LOCAL_TZ", "America/El_Salvador")
TTL_MINUTOS = int(os.environ.get("BTC_QUOTE_TTL_MIN", "15"))

URL_COINBASE_SPOT = "https://api.coinbase.com/v2/prices/BTC-USD/spot"
URL_COINBASE_VELAS = "https://api.exchange.coinbase.com/products/BTC-USD/candles"
URL_KRAKEN = "https://api.kraken.com/0/public/Ticker?pair=XBTUSD"
URL_COINGECKO = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd"


class CotizacionNoDisponible(Exception):
    """No source returned a valid price: a charge must NOT be generated."""


class PrecioInvalido(ValueError):
    pass


# ---------------------------------------------------------------- HTTP

def http_get(url, timeout=TIMEOUT):
    """GET -> JSON. Replaced in tests (the internet is not called)."""
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


# ---------------------------------------------------------------- time

def utc_ahora():
    return datetime.now(timezone.utc)


def iso_utc(dt):
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_utc(texto):
    return datetime.strptime(texto, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def local_a_utc(texto, tz=None):
    """'2026-11-04 13:23:35' (local time without zone) -> UTC datetime.
    If the text carries an offset/Z, that offset is respected."""
    t = texto.strip().replace("T", " ")
    if t.endswith("Z"):
        t = t[:-1] + "+00:00"
    dt = datetime.fromisoformat(t)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo(tz or TZ_LOCAL))
    return dt.astimezone(timezone.utc)


# ---------------------------------------------------------------- money

def dec(valor):
    """Converts to Decimal without going through the binary float representation."""
    try:
        d = valor if isinstance(valor, Decimal) else Decimal(str(valor))
    except InvalidOperation:
        raise PrecioInvalido("not a number: %r" % (valor,))
    if not d.is_finite():
        raise PrecioInvalido("not finite: %r" % (valor,))
    return d


def validar_precio(valor):
    d = dec(valor)
    if d <= 0:
        raise PrecioInvalido("the price must be > 0: %s" % d)
    return d


def convertir(total_usd, precio_btc_usd):
    """USD (IVA incluido) -> neto/IVA -> BTC -> satoshis. Returns Decimals/int.

    Redondeo (ROUND_HALF_UP):
      neto_usd = round2(total/1.13);  iva_usd  = total - neto_usd      (suman exacto)
      total_btc = round8(total_usd/precio); total_sats = total_btc*1e8  (entero exacto)
      neto_btc  = round8(neto_usd/precio);  iva_btc = total_btc - neto_btc (suman exacto)
    """
    total = dec(total_usd).quantize(CENT, ROUND_HALF_UP)
    precio = validar_precio(precio_btc_usd)
    neto = (total / IVA_DIVISOR).quantize(CENT, ROUND_HALF_UP)
    iva = total - neto
    total_btc = (total / precio).quantize(OCHO, ROUND_HALF_UP)
    neto_btc = (neto / precio).quantize(OCHO, ROUND_HALF_UP)
    return {
        "total_usd": total, "neto_usd": neto, "iva_usd": iva,
        "precio_btc_usd": precio,
        "total_btc": total_btc, "neto_btc": neto_btc, "iva_btc": total_btc - neto_btc,
        "total_sats": int(total_btc * SATS_POR_BTC),
    }


def sats_a_btc(sats):
    return (Decimal(int(sats)) / SATS_POR_BTC).quantize(OCHO)


def btc_a_usd(btc, precio):
    return (dec(btc) * validar_precio(precio)).quantize(CENT, ROUND_HALF_UP)


def diferencia_pct(original, referencia):
    """(original - reference) / reference * 100, to 4 decimal places."""
    ref = validar_precio(referencia)
    return ((dec(original) - ref) / ref * 100).quantize(Decimal("0.0001"), ROUND_HALF_UP)


# ---------------------------------------------------------------- quotes

@dataclass(frozen=True)
class Cotizacion:
    precio: Decimal
    fuente: str            # coinbase | kraken | coingecko
    tipo_precio: str       # spot | ultimo_negociado | vela_cierre
    precision: str         # exacta_al_consultar | aproximada_vela_1m
    consultado_utc: str    # actual moment of the query (ISO UTC)
    url: str
    bid: Decimal = None
    ask: Decimal = None
    validacion: str = ""
    respuesta: str = ""    # raw JSON from the source (evidence)


def _coinbase_spot(get):
    r = get(URL_COINBASE_SPOT)
    d = r["data"]
    if d.get("base") != "BTC" or d.get("currency") != "USD":
        raise PrecioInvalido("unexpected pair: %s-%s" % (d.get("base"), d.get("currency")))
    return Cotizacion(validar_precio(d["amount"]), "coinbase", "spot", "exacta_al_consultar",
                      iso_utc(utc_ahora()), URL_COINBASE_SPOT, validacion="estructura y precio>0",
                      respuesta=json.dumps(r, sort_keys=True))


def _kraken(get):
    r = get(URL_KRAKEN)
    if r.get("error"):
        raise PrecioInvalido("Kraken error: %s" % r["error"])
    t = next(iter(r["result"].values()))
    ultimo, bid, ask = validar_precio(t["c"][0]), validar_precio(t["b"][0]), validar_precio(t["a"][0])
    if ask < bid or (ask - bid) / bid > MAX_SPREAD:
        raise PrecioInvalido("invalid spread bid=%s ask=%s" % (bid, ask))
    return Cotizacion(ultimo, "kraken", "ultimo_negociado", "exacta_al_consultar",
                      iso_utc(utc_ahora()), URL_KRAKEN, bid, ask,
                      "estructura, precio>0, spread<=1%", json.dumps(r, sort_keys=True))


def _coingecko(get):
    r = get(URL_COINGECKO)
    return Cotizacion(validar_precio(r["bitcoin"]["usd"]), "coingecko", "spot_agregado",
                      "exacta_al_consultar", iso_utc(utc_ahora()), URL_COINGECKO,
                      validacion="estructura y precio>0", respuesta=json.dumps(r, sort_keys=True))


FUENTES = {"coinbase": _coinbase_spot, "kraken": _kraken, "coingecko": _coingecko}


def consultar(fuente, get=None):
    return FUENTES[fuente](get or http_get)


def obtener_cotizacion(get=None):
    """Coinbase; if it fails, validated Kraken (cross-checked against CoinGecko if it responds).
    If none is valid it raises CotizacionNoDisponible: the charge is NOT generated."""
    get = get or http_get
    errores = []
    try:
        return _coinbase_spot(get)
    except Exception as e:  # network, JSON, structure, price
        errores.append("coinbase: %s" % e)
    try:
        k = _kraken(get)
        try:
            ref = _coingecko(get).precio
        except Exception:
            ref = None
        if ref is None:
            nota = "sin contraste (coingecko no disponible)"
        else:
            desvio = abs(k.precio - ref) / ref
            if desvio > MAX_DESVIO_CONTRASTE:
                raise PrecioInvalido("Kraken %s differs %.2f%% from CoinGecko %s" % (k.precio, desvio * 100, ref))
            nota = "contrastado con coingecko (desvío %.3f%%)" % (desvio * 100)
        return Cotizacion(**{**k.__dict__, "validacion": k.validacion + "; " + nota})
    except Exception as e:
        errores.append("kraken: %s" % e)
    raise CotizacionNoDisponible("; ".join(errores))


# ---------------------------------------------------------------- historical

def precio_historico(momento_utc, get=None):
    """Coinbase 1-minute candle that CONTAINS the given instant.

    This is an APPROXIMATE reconstruction: the candle does not prove the price at a specific second.
    Referencia = cierre de la vela. Devuelve None si Coinbase no tiene esa vela.
    Coinbase candle format: [time, low, high, open, close, volume]."""
    get = get or http_get
    ini = momento_utc.astimezone(timezone.utc).replace(second=0, microsecond=0)
    fin = ini + timedelta(seconds=59)
    url = "%s?granularity=60&start=%s&end=%s" % (URL_COINBASE_VELAS, iso_utc(ini), iso_utc(fin))
    velas = get(url)
    for v in velas:
        if int(v[0]) == int(ini.timestamp()):
            return {
                "fuente": "coinbase", "tipo_precio": "vela_cierre", "precision": "aproximada_vela_1m",
                "vela_inicio_utc": iso_utc(ini), "momento_consultado_utc": iso_utc(momento_utc),
                "low": dec(v[1]), "high": dec(v[2]), "open": dec(v[3]), "close": validar_precio(v[4]),
                "volumen": dec(v[5]), "url": url,
                "metodologia": "cierre de la vela de 1 min que contiene el instante; "
                               "el cierre ocurre hasta 59 s después del instante",
            }
    return None
