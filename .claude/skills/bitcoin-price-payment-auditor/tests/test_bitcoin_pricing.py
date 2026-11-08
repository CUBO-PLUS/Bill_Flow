"""Pruebas del módulo Bitcoin. Sin internet ni dependencias:  python3 -m unittest discover -s <esta carpeta> -v
(Toda la red se simula con funciones `get` falsas.)"""
import sqlite3
import sys
import unittest
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parents[3]
sys.path[:0] = [str(RAIZ), str(AQUI.parent / "scripts")]

import audit_transactions as audit  # noqa: E402
import bitcoin  # noqa: E402
import precios_btc as pb  # noqa: E402

D = Decimal


# ---------------------------------------------------------------- simulación de red
def coinbase_ok(precio="80131.51"):
    return {"data": {"amount": precio, "base": "BTC", "currency": "USD"}}


def kraken_ok(last="80100.0", bid="80099.9", ask="80100.1"):
    return {"error": [], "result": {"XXBTZUSD": {"a": [ask, "1", "1"], "b": [bid, "1", "1"], "c": [last, "0.1"]}}}


def gecko(p=80100):
    return {"bitcoin": {"usd": p}}


def fake_get(coinbase=None, kraken=None, coingecko=None, velas=None):
    """Cada argumento: dict de respuesta, o Exception para simular caída; None = no disponible."""
    def get(url, timeout=5):
        if "candles" in url:
            r = velas
        elif "coinbase.com/v2" in url:
            r = coinbase
        elif "kraken" in url:
            r = kraken
        else:
            r = coingecko
        if r is None or isinstance(r, Exception):
            raise r or OSError("API no disponible")
        if callable(r):
            return r(url)
        return r
    return get


# Velas reales de Coinbase (consultadas 2026-11-04): [time, low, high, open, close, volume]
VELAS = {
    "2026-11-04T19:23:00Z": [[1793820180, 80122.69, 80151.73, 80151.73, 80131.51, 2.86014378]],
    "2026-11-04T19:24:00Z": [[1793820240, 80100.01, 80131.51, 80131.51, 80107.11, 2.06184983]],
}


def velas_reales(url):
    inicio = url.split("start=")[1].split("&")[0]
    return VELAS.get(inicio, [])


# ---------------------------------------------------------------- base de prueba
def base_prueba():
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.executescript((RAIZ / "restaurante_db.sql").read_text(encoding="utf-8"))
    db.execute("INSERT INTO empleado (id, rol_id, nombre_usuario) VALUES (1, 1, 'caja_prueba')")
    db.execute("PRAGMA foreign_keys = ON")
    bitcoin.migrar(db)
    return db


def insertar_legado(db, vid, fecha, total, sats, btc, neto, iva_neto, id_pago):
    """Registros ORIGINALES (sin fuente): como las ventas 3 y 4 de la base real."""
    db.execute("INSERT INTO venta (id, fecha_hora, tipo_cliente_id, forma_pago_id, empleado_id, estado_dte_id, "
               "precio_btc_usd) VALUES (?, ?, 1, 10, 1, 1, 100000)", (vid, fecha))
    db.execute("INSERT INTO detalle_venta (venta_id, platillo_id, cantidad, precio_unitario) VALUES (?, 1, 1, ?)",
               (vid, total))
    db.execute("INSERT INTO venta_bitcoin (venta_id, fecha_hora, empleado_id, total_usd, iva_usd, neto_usd, "
               "precio_btc_usd, total_btc, total_sats, neto_btc, estado, id_pago) "
               "VALUES (?, ?, 1, ?, ?, ?, 100000, ?, ?, ?, 'pendiente', ?)",
               (vid, fecha, total, iva_neto[1], iva_neto[0], btc, sats, neto, id_pago))
    db.commit()


def legado_3_y_4(db):
    insertar_legado(db, 3, "2026-11-04 13:23:35", 12.0, 12000, 0.00012, 0.0001062, (10.62, 1.38), "BTC-113AD48D")
    insertar_legado(db, 4, "2026-11-04 13:24:17", 24.0, 24000, 0.00024, 0.0002124, (21.24, 2.76), "BTC-0D7BB46E")


def venta_nueva(db, vid=10, total=12.0, precio="80000", get=None):
    db.execute("INSERT INTO venta (id, fecha_hora, tipo_cliente_id, forma_pago_id, empleado_id, estado_dte_id) "
               "VALUES (?, datetime('now','localtime'), 1, 10, 1, 1)", (vid,))
    cot = pb.obtener_cotizacion(get or fake_get(coinbase=coinbase_ok(precio)))
    id_pago = bitcoin.registrar_pendiente(db, vid, 1, total, cot)
    db.commit()
    return id_pago, cot


def pago_json(db, _id, **cambios):
    r = db.execute("SELECT total_sats, total_usd FROM venta_bitcoin WHERE id_pago = ?", (_id,)).fetchone()
    p = {"id_pago": _id, "monto_sats": r["total_sats"], "monto_usd": r["total_usd"]}
    p.update(cambios)
    return p


# ---------------------------------------------------------------- conversión
class TestConversion(unittest.TestCase):
    def test_usd_btc_sats_venta_3(self):
        c = pb.convertir("12.00", 100000)
        self.assertEqual((c["neto_usd"], c["iva_usd"]), (D("10.62"), D("1.38")))
        self.assertEqual(c["total_btc"], D("0.00012000"))
        self.assertEqual(c["total_sats"], 12000)

    def test_iva_y_btc_suman_exacto(self):
        for total in ("0.01", "1.99", "7.77", "123.45", "999.99"):
            c = pb.convertir(total, "80131.51")
            self.assertEqual(c["neto_usd"] + c["iva_usd"], c["total_usd"])
            self.assertEqual(c["neto_btc"] + c["iva_btc"], c["total_btc"])
            self.assertEqual(Decimal(c["total_sats"]), c["total_btc"] * 10**8)

    def test_btc_a_satoshis(self):
        self.assertEqual(pb.convertir("12", "80131.51")["total_sats"], 14975)
        self.assertEqual(pb.sats_a_btc(14975), D("0.00014975"))

    def test_sin_perdida_binaria(self):
        # con float 0.1+0.2 != 0.3; con Decimal el total se conserva
        self.assertEqual(pb.convertir(0.1 + 0.2, 100000)["total_usd"], D("0.30"))

    def test_redondeo_half_up(self):
        self.assertEqual(pb.convertir("0.05", 3)["total_btc"], D("0.01666667"))
        self.assertEqual(pb.convertir("1.00", 1)["neto_usd"], D("0.88"))  # 0.8849.. -> 0.88

    def test_precio_invalido(self):
        for malo in (0, -1, "abc", "NaN", "Infinity", None):
            with self.assertRaises(pb.PrecioInvalido):
                pb.convertir(10, malo)

    def test_diferencia_pct(self):
        self.assertEqual(pb.diferencia_pct(100000, "80131.51"), D("24.7949"))


class TestFechasUTC(unittest.TestCase):
    def test_local_a_utc_el_salvador(self):
        self.assertEqual(pb.iso_utc(pb.local_a_utc("2026-11-04 13:23:35", "America/El_Salvador")),
                         "2026-11-04T19:23:35Z")

    def test_respeta_offset_explicito(self):
        self.assertEqual(pb.iso_utc(pb.local_a_utc("2026-11-04T19:23:35Z", "America/El_Salvador")),
                         "2026-11-04T19:23:35Z")
        self.assertEqual(pb.iso_utc(pb.local_a_utc("2026-11-04 13:23:35-06:00")), "2026-11-04T19:23:35Z")

    def test_cruce_de_dia(self):
        self.assertEqual(pb.iso_utc(pb.local_a_utc("2026-11-04 20:00:00", "America/El_Salvador")),
                         "2026-11-05T02:00:00Z")


# ---------------------------------------------------------------- fuentes
class TestFuentes(unittest.TestCase):
    def test_coinbase_principal(self):
        c = pb.obtener_cotizacion(fake_get(coinbase=coinbase_ok("80010.775"), kraken=kraken_ok()))
        self.assertEqual((c.fuente, c.tipo_precio, c.precio), ("coinbase", "spot", D("80010.775")))

    def test_respaldo_kraken_validado(self):
        c = pb.obtener_cotizacion(fake_get(coinbase=OSError("caído"), kraken=kraken_ok(), coingecko=gecko(80100)))
        self.assertEqual((c.fuente, c.tipo_precio, c.precio), ("kraken", "ultimo_negociado", D("80100.0")))
        self.assertIn("contrastado", c.validacion)

    def test_kraken_sin_coingecko_se_documenta(self):
        c = pb.obtener_cotizacion(fake_get(coinbase=OSError(), kraken=kraken_ok(), coingecko=OSError()))
        self.assertIn("sin contraste", c.validacion)

    def test_coinbase_basura_cae_a_kraken(self):
        for malo in ({"data": {"amount": "abc", "base": "BTC", "currency": "USD"}},
                     {"data": {"amount": "-5", "base": "BTC", "currency": "USD"}},
                     {"data": {"amount": "0", "base": "BTC", "currency": "USD"}},
                     {"data": {"amount": "80000", "base": "ETH", "currency": "USD"}}, {"x": 1}):
            c = pb.obtener_cotizacion(fake_get(coinbase=malo, kraken=kraken_ok()))
            self.assertEqual(c.fuente, "kraken")

    def test_kraken_spread_invalido_rechazado(self):
        with self.assertRaises(pb.CotizacionNoDisponible):
            pb.obtener_cotizacion(fake_get(coinbase=OSError(), kraken=kraken_ok(bid="70000", ask="80000")))

    def test_kraken_contradice_coingecko_rechazado(self):
        with self.assertRaises(pb.CotizacionNoDisponible):
            pb.obtener_cotizacion(fake_get(coinbase=OSError(), kraken=kraken_ok("80100"), coingecko=gecko(60000)))

    def test_kraken_error_de_api(self):
        with self.assertRaises(pb.CotizacionNoDisponible):
            pb.obtener_cotizacion(fake_get(coinbase=OSError(), kraken={"error": ["EQuery:Unknown asset pair"]}))

    def test_api_no_disponible_no_hay_cotizacion(self):
        with self.assertRaises(pb.CotizacionNoDisponible) as cm:
            pb.obtener_cotizacion(fake_get())
        self.assertIn("coinbase", str(cm.exception))
        self.assertIn("kraken", str(cm.exception))


class TestHistorico(unittest.TestCase):
    def test_vela_de_venta_3(self):
        utc = pb.local_a_utc("2026-11-04 13:23:35", "America/El_Salvador")
        r = pb.precio_historico(utc, fake_get(velas=velas_reales))
        self.assertEqual(r["close"], D("80131.51"))
        self.assertEqual(r["precision"], "aproximada_vela_1m")
        self.assertEqual(r["vela_inicio_utc"], "2026-11-04T19:23:00Z")
        self.assertIn("start=2026-11-04T19:23:00Z&end=2026-11-04T19:23:59Z", r["url"])

    def test_vela_de_venta_4(self):
        r = pb.precio_historico(pb.local_a_utc("2026-11-04 13:24:17", "America/El_Salvador"),
                                fake_get(velas=velas_reales))
        self.assertEqual(r["close"], D("80107.11"))

    def test_sin_vela_devuelve_none_no_inventa(self):
        self.assertIsNone(pb.precio_historico(pb.utc_ahora(), fake_get(velas=[])))

    def test_vela_de_otro_minuto_se_ignora(self):
        self.assertIsNone(pb.precio_historico(
            pb.local_a_utc("2026-11-04 13:23:35", "America/El_Salvador"),
            fake_get(velas=[[1793820240, 1, 2, 1, 2, 1]])))


# ---------------------------------------------------------------- registro y confirmación
class TestRegistro(unittest.TestCase):
    def setUp(self):
        self.db = base_prueba()
        self.addCleanup(self.db.close)

    def test_nueva_venta_guarda_todo(self):
        id_pago, cot = venta_nueva(self.db, total=12.0, precio="80000")
        r = self.db.execute("SELECT * FROM venta_bitcoin WHERE id_pago = ?", (id_pago,)).fetchone()
        self.assertEqual((r["fuente_precio"], r["fecha_precio"]), ("coinbase", cot.consultado_utc))
        self.assertEqual((r["total_sats"], r["total_btc"], r["neto_usd"], r["iva_usd"], r["iva_btc"]),
                         (15000, 0.00015, 10.62, 1.38, 0.00001725))
        q = self.db.execute("SELECT * FROM cotizacion_btc WHERE id = ?", (r["cotizacion_id"],)).fetchone()
        self.assertEqual((q["tipo"], q["precio_btc_usd"], q["fuente"], q["id_pago"]),
                         ("registro", "80000", "coinbase", id_pago))
        self.assertIn('"amount"', q["respuesta"])
        self.assertEqual(self.db.execute("SELECT precio_btc_usd FROM venta WHERE id=10").fetchone()[0], 80000)

    def test_cotizacion_inmutable(self):
        venta_nueva(self.db)
        with self.assertRaises(sqlite3.DatabaseError):
            self.db.execute("UPDATE cotizacion_btc SET precio_btc_usd = '1'")
        with self.assertRaises(sqlite3.DatabaseError):
            self.db.execute("DELETE FROM cotizacion_btc")

    def test_no_se_sobrescribe_precio_original(self):
        id_pago, _ = venta_nueva(self.db)
        for col, val in (("precio_btc_usd", 1), ("total_sats", 1), ("total_usd", 1), ("fecha_hora", "x")):
            with self.assertRaises(sqlite3.DatabaseError):
                self.db.execute("UPDATE venta_bitcoin SET %s = ? WHERE id_pago = ?" % col, (val, id_pago))

    def test_migracion_idempotente_y_no_toca_legado(self):
        legado_3_y_4(self.db)
        antes = [tuple(r) for r in self.db.execute("SELECT * FROM venta_bitcoin ORDER BY id")]
        bitcoin.migrar(self.db)
        bitcoin.migrar(self.db)
        self.assertEqual(antes, [tuple(r) for r in self.db.execute("SELECT * FROM venta_bitcoin ORDER BY id")])

    def test_sin_cotizacion_no_hay_cobro(self):
        with self.assertRaises(pb.CotizacionNoDisponible):
            pb.obtener_cotizacion(fake_get())
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM venta_bitcoin").fetchone()[0], 0)


class TestConfirmacion(unittest.TestCase):
    def setUp(self):
        self.db = base_prueba()
        self.addCleanup(self.db.close)
        self.id_pago, _ = venta_nueva(self.db, vid=10, total=12.0, precio="80000")
        self.get = fake_get(coinbase=coinbase_ok("80500"))

    def estado(self):
        return self.db.execute("SELECT estado FROM venta_bitcoin").fetchone()[0]

    def test_confirmacion_ok_guarda_precio_aparte(self):
        ok, msg = bitcoin.confirmar(self.db, pago_json(self.db, self.id_pago), get=self.get)
        self.assertTrue(ok, msg)
        r = self.db.execute("SELECT * FROM venta_bitcoin WHERE id_pago = ?", (self.id_pago,)).fetchone()
        self.assertEqual((r["estado"], r["precio_btc_usd"]), ("pagada", 80000.0))
        q = self.db.execute("SELECT precio_btc_usd FROM cotizacion_btc WHERE tipo='confirmacion'").fetchone()
        self.assertEqual(q[0], "80500")  # el precio de registro no cambió

    def test_confirma_aunque_no_haya_precio(self):
        ok, _ = bitcoin.confirmar(self.db, pago_json(self.db, self.id_pago), get=fake_get())
        self.assertTrue(ok)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM cotizacion_btc WHERE tipo='confirmacion'").fetchone()[0], 0)

    def test_pago_repetido(self):
        p = pago_json(self.db, self.id_pago)
        self.assertTrue(bitcoin.confirmar(self.db, p, get=self.get)[0])
        ok, msg = bitcoin.confirmar(self.db, p, get=self.get)
        self.assertFalse(ok)
        self.assertIn("already", msg)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM cotizacion_btc WHERE tipo='confirmacion'").fetchone()[0], 1)

    def test_monto_insuficiente(self):
        ok, msg = bitcoin.confirmar(self.db, pago_json(self.db, self.id_pago, monto_sats=14000), get=self.get)
        self.assertFalse(ok)
        self.assertIn("insufficient", msg)
        self.assertEqual(self.estado(), "pendiente")

    def test_monto_excesivo(self):
        ok, msg = bitcoin.confirmar(self.db, pago_json(self.db, self.id_pago, monto_sats=16000, monto_usd=13), get=self.get)
        self.assertFalse(ok)
        self.assertIn("excessive", msg)
        self.assertEqual(self.estado(), "pendiente")

    def test_usd_no_coincide(self):
        ok, _ = bitcoin.confirmar(self.db, pago_json(self.db, self.id_pago, monto_usd=11.0), get=self.get)
        self.assertFalse(ok)
        self.assertEqual(self.estado(), "pendiente")

    def test_id_desconocido_y_json_incompleto(self):
        self.assertFalse(bitcoin.confirmar(self.db, pago_json(self.db, self.id_pago, id_pago="BTC-NOPE"))[0])
        self.assertFalse(bitcoin.confirmar(self.db, {"id_pago": self.id_pago})[0])

    def test_pago_confirmado_es_inmutable(self):
        bitcoin.confirmar(self.db, pago_json(self.db, self.id_pago), get=self.get)
        with self.assertRaises(sqlite3.DatabaseError):
            self.db.execute("UPDATE venta_bitcoin SET estado = 'pendiente'")


# ---------------------------------------------------------------- auditoría
class TestAuditoria(unittest.TestCase):
    def setUp(self):
        self.db = base_prueba()
        self.addCleanup(self.db.close)
        legado_3_y_4(self.db)
        self.get = fake_get(velas=velas_reales)

    def correr(self, **kw):
        return audit.auditar(self.db, get=self.get, pausa=0, tz="America/El_Salvador", **kw)

    def codigos(self, hall, venta=None):
        return {h["codigo"] for h in hall if venta is None or h["venta_id"] == venta}

    def test_ventas_3_y_4_reconstruidas(self):
        filas, hall = self.correr()
        f3, f4 = filas
        self.assertEqual((f3["fecha_utc"], f3["hist_close"], f3["sats_reconstruidos"], f3["dif_sats"]),
                         ("2026-11-04T19:23:35Z", D("80131.51"), 14975, 12000 - 14975))
        self.assertEqual((f4["fecha_utc"], f4["hist_close"], f4["sats_reconstruidos"], f4["dif_sats"]),
                         ("2026-11-04T19:24:17Z", D("80107.11"), 29960, 24000 - 29960))
        self.assertEqual((f3["dif_pct"], f4["dif_pct"]), (D("24.7949"), D("24.8329")))
        self.assertEqual(f3["verificabilidad"], "aproximado_vela")
        self.assertFalse(f3["dentro_rango_vela"])
        for v in (3, 4):
            self.assertLessEqual({"SIN_FUENTE", "PRECIO_DIFIERE_HISTORICO"}, self.codigos(hall, v))

    def test_originales_correctos_internamente(self):
        _, hall = self.correr(offline=True)
        self.assertNotIn("CALCULO_INCORRECTO", self.codigos(hall))

    def test_auditoria_no_modifica_la_base(self):
        antes = "\n".join(self.db.iterdump())
        self.correr()
        self.assertEqual(antes, "\n".join(self.db.iterdump()))

    def test_api_no_disponible_no_inventa(self):
        self.get = fake_get(velas=OSError("caído"))
        filas, hall = self.correr()
        self.assertEqual(filas[0]["verificabilidad"], "no_verificable")
        self.assertNotIn("hist_close", filas[0])
        self.assertIn("NO_VERIFICABLE", self.codigos(hall))

    def test_sin_vela_es_no_verificable(self):
        self.get = fake_get(velas=[])
        filas, _ = self.correr()
        self.assertEqual(filas[0]["verificabilidad"], "no_verificable")

    def test_calculo_incorrecto_y_total_distinto(self):
        self.db.execute("DROP TRIGGER venta_bitcoin_cotizacion_fija")  # solo para fabricar el dato malo
        self.db.execute("UPDATE venta_bitcoin SET total_sats = 11000 WHERE venta_id = 3")
        self.db.execute("UPDATE detalle_venta SET precio_unitario = 13 WHERE venta_id = 4")
        _, hall = self.correr(offline=True)
        self.assertIn("CALCULO_INCORRECTO", self.codigos(hall, 3))
        self.assertIn("TOTAL_DIFIERE_DETALLE", self.codigos(hall, 4))

    def test_nueva_venta_con_fuente_no_marca_sin_fuente(self):
        id_pago, _ = venta_nueva(self.db, vid=20)
        _, hall = audit.auditar(self.db, offline=True, tz="America/El_Salvador")
        self.assertNotIn(id_pago, [h["id_pago"] for h in hall if h["codigo"] == "SIN_FUENTE"])

    def test_posible_duplicado(self):
        insertar_legado(self.db, 5, "2026-11-04 13:24:30", 24.0, 24000, 0.00024, 0.0002124, (21.24, 2.76), "BTC-DUP")
        _, hall = audit.auditar(self.db, offline=True, tz="America/El_Salvador")
        self.assertIn("POSIBLE_DUPLICADO", self.codigos(hall))

    def test_pendiente_vencido_por_antiguedad(self):
        tarde = pb.utc_ahora() + timedelta(hours=1)
        _, hall = audit.auditar(self.db, offline=True, ahora=tarde, tz="America/El_Salvador")
        self.assertIn("PENDIENTE_VENCIDO", self.codigos(hall, 3))

    def test_esquema_antiguo_se_detecta(self):
        db = sqlite3.connect(":memory:")
        db.row_factory = sqlite3.Row
        db.executescript((RAIZ / "restaurante_db.sql").read_text(encoding="utf-8"))
        db.executescript("CREATE TABLE venta_bitcoin (id INTEGER PRIMARY KEY, venta_id INTEGER, fecha_hora TEXT, "
                         "empleado_id INTEGER, total_usd REAL, iva_usd REAL, neto_usd REAL, precio_btc_usd REAL, "
                         "total_btc REAL, total_sats INTEGER, neto_btc REAL, estado TEXT, id_pago TEXT);")
        self.addCleanup(db.close)
        _, hall = audit.auditar(db, offline=True)
        self.assertIn("ESQUEMA_ANTIGUO", {h["codigo"] for h in hall})


if __name__ == "__main__":
    unittest.main(verbosity=2)
