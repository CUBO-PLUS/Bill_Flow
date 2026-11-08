"""PDF representation of a DTE (Documento Tributario Electrónico), laid out like the Hacienda model.

The QR encodes the official public-query URL of the Ministerio de Hacienda
(ambiente + codGen + fechaEmi). Scanning it opens the "Consulta DTE/Evento" form already filled in;
"Realizar Búsqueda" shows the DTE details *as registered at Hacienda* (only if it was really transmitted).
"""
import io
import os
from xml.sax.saxutils import escape

from reportlab.graphics import renderPDF
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Flowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

CONSULTA_URL = os.environ.get("DTE_CONSULTA_URL", "https://admin.factura.gob.sv/consultaPublica")

TIPOS_DTE = {"01": "Factura Electrónica", "03": "Comprobante de Crédito Fiscal Electrónico",
             "11": "Factura de Exportación Electrónica"}
PAGOS = {"01": "Billetes y monedas", "02": "Tarjeta Débito", "03": "Tarjeta Crédito", "04": "Cheque",
         "05": "Transferencia - Depósito Bancario", "06": "Vales o Cupones", "08": "Dinero electrónico",
         "09": "Monedero electrónico", "10": "Certificado o tarjeta de regalo", "11": "Bitcoin",
         "12": "Otras Criptomonedas", "99": "Otros (se debe indicar el medio de pago)"}
ESTABLECIMIENTOS = {"01": "Sucursal / Agencia", "02": "Casa matriz", "04": "Bodega",
                    "07": "Predio y/o patio", "20": "Otro"}
UNIDADES = {59: "Unidad", 99: "Otra"}

INK, MUTED, DARK = colors.HexColor("#111111"), colors.HexColor("#444444"), colors.HexColor("#222222")


def url_consulta(dte):
    """Official public-query URL that the QR code carries."""
    i = dte["identificacion"]
    return "%s?ambiente=%s&codGen=%s&fechaEmi=%s" % (CONSULTA_URL, i["ambiente"], i["codigoGeneracion"], i["fecEmi"])


class _Qr(Flowable):
    def __init__(self, data, size):
        super().__init__()
        self.size = size
        w = QrCodeWidget(data, barLevel="M")
        x0, y0, x1, y1 = w.getBounds()
        self.d = Drawing(size, size, transform=[size / (x1 - x0), 0, 0, size / (y1 - y0), 0, 0])
        self.d.add(w)
        self.width = self.height = size

    def draw(self):
        renderPDF.draw(self.d, self.canv, 0, 0)


def _st(name, size=8.5, bold=False, **kw):
    return ParagraphStyle(name, fontName=kw.pop("fontName", "Helvetica-Bold" if bold else "Helvetica"), fontSize=size,
                          leading=kw.pop("leading", size + 2.5), textColor=kw.pop("color", INK), **kw)


S = _st("n"); SB = _st("b", bold=True); SS = _st("s", 7.5); SH = _st("h", 7.5, True, color=colors.white, alignment=1)
SR = _st("r", alignment=TA_RIGHT); SRB = _st("rb", bold=True, alignment=TA_RIGHT)


def _p(t, style=S):
    return Paragraph(escape(str(t)) if t not in (None, "") else "", style)


def _campo(label, valor, style=S):
    """'Label: value' line with the label in bold."""
    return Paragraph("<b>%s</b> %s" % (escape(label), escape(str(valor)) if valor not in (None, "") else ""), style)


def _m(x, d=2):
    return ("%." + str(d) + "f") % (x or 0)


def _caja(cells, titulo):
    t = Table([[_p(titulo, _st("t", 9, True, alignment=1))], [cells]], colWidths=[None])
    t.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                           ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                           ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    return t


def recibo_pdf(dte):
    e, r, res, ident = dte["emisor"], dte["receptor"], dte["resumen"], dte["identificacion"]
    mh = dte.get("responseMH") or {}
    tipo = ident["tipoDte"]
    w_total = letter[0] - 28 * mm
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter, leftMargin=14 * mm, rightMargin=14 * mm,
                            topMargin=12 * mm, bottomMargin=12 * mm,
                            title="%s %s" % (TIPOS_DTE.get(tipo, "DTE"), ident["numeroControl"]),
                            author=e["nombre"])
    fl = []

    # ── Header: company name | title ─────────────────────────────────────────────────────────────
    nombre = Paragraph(escape(e.get("nombreComercial") or e["nombre"]),
                       _st("nom", 21, True, leading=24, fontName="Times-Bold"))
    titulo = [_p("DOCUMENTO TRIBUTARIO ELECTRÓNICO", _st("t1", 11, True)),
              _p(TIPOS_DTE.get(tipo, "DTE"), _st("t2", 10.5, True))]
    h = Table([[nombre, titulo]], colWidths=[w_total * .42, w_total * .58])
    h.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LINEABOVE", (0, 0), (0, 0), 3, INK),
                           ("LINEBELOW", (0, 0), (0, 0), 3, INK), ("TOPPADDING", (0, 0), (0, 0), 8),
                           ("BOTTOMPADDING", (0, 0), (0, 0), 8), ("LEFTPADDING", (0, 0), (0, 0), 0)]))
    fl += [h, Spacer(1, 8)]

    # ── Identification | QR | model ───────────────────────────────────────────────────────────────
    sello = mh.get("selloRecibido") or "Pendiente de recepción"
    ids = [_campo("Código de Generación:", ident["codigoGeneracion"], SS),
           _campo("Número de Control:", ident["numeroControl"], SS),
           _campo("Sello de Recepción:", sello, SS)]
    modelo = [_campo("Modelo de Facturación:", "Previo" if ident.get("tipoModelo") == 1 else "Diferido"),
              _campo("Tipo de Transmisión:", "Normal" if ident.get("tipoOperacion") == 1 else "Contingencia"),
              _p("Fecha y Hora de Generación:", SB),
              _p("%s %s" % (ident["fecEmi"], ident["horEmi"]))]
    top = Table([[ids, _Qr(url_consulta(dte), 31 * mm), modelo]],
                colWidths=[w_total * .47, w_total * .2, w_total * .33])
    top.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("ALIGN", (1, 0), (1, 0), "CENTER"),
                             ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
    fl += [top, Spacer(1, 8)]

    # ── Emisor / Receptor ─────────────────────────────────────────────────────────────────────────
    dir_e = (e.get("direccion") or {}).get("complemento")
    em = [_campo("Nombre o Razón Social:", e["nombre"]), _campo("NIT:", e["nit"]),
          _campo("NRC:", e["nrc"]), _campo("Actividad Económica:", e.get("descActividad")),
          _campo("Dirección:", dir_e), _campo("Correo Electrónico:", e.get("correo")),
          _campo("Número de Teléfono:", e.get("telefono")), _campo("Nombre Comercial:", e.get("nombreComercial")),
          _campo("Tipo de Establecimiento:", ESTABLECIMIENTOS.get(e.get("tipoEstablecimiento"), ""))]
    dir_r = (r.get("direccion") or {}).get("complemento") if isinstance(r.get("direccion"), dict) else r.get("direccion")
    nit_r = r.get("nit") or r.get("numDocumento")
    rc = [_campo("Nombre o Razón Social:", r.get("nombre") or ("Consumidor final" if tipo == "01" else "")),
          _campo("NRC:", r.get("nrc")), _campo("NIT:", nit_r),
          _campo("Actividad Económica:", r.get("descActividad")), _campo("Correo Electrónico:", r.get("correo")),
          _campo("Número de Teléfono:", r.get("telefono")), _campo("Dirección:", dir_r)]
    er = Table([[_caja(em, "EMISOR"), _caja(rc, "RECEPTOR")]], colWidths=[w_total * .5 - 3, w_total * .5 - 3],
               hAlign="CENTER")
    er.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("ROUNDEDCORNERS", [8, 8, 8, 8]),
                            ("BOX", (0, 0), (0, 0), .8, MUTED), ("BOX", (1, 0), (1, 0), .8, MUTED),
                            ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
    fl += [er, Spacer(1, 10)]

    # ── Items ─────────────────────────────────────────────────────────────────────────────────────
    cab = ["N°", "Código", "Cantidad", "Unidad", "Descripción", "Precio\nUnitario", "Venta\nNo Sujeta",
           "Venta\nExenta", "Venta\nGravadas"]
    filas = [[Paragraph(c.replace("\n", "<br/>"), SH) for c in cab]]
    for it in dte["cuerpoDocumento"]:
        filas.append([_p(it["numItem"]), _p(it.get("codigo")), _p("%.4f" % it["cantidad"], SR),
                      _p(UNIDADES.get(it.get("uniMedida"), "Unidad"), SS), _p(it["descripcion"]),
                      _p(_m(it["precioUni"], 6), SR), _p(_m(it.get("ventaNoSuj")), SR),
                      _p(_m(it.get("ventaExenta")), SR), _p(_m(it.get("ventaGravada")), SR)])
    cw = [.04, .08, .09, .08, .31, .1, .1, .1, .1]
    it_t = Table(filas, colWidths=[w_total * c for c in cw], repeatRows=1)
    it_t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), DARK), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                              ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                              ("LINEBELOW", (0, 1), (-1, -1), .25, colors.HexColor("#cccccc"))]))
    fl += [it_t, Spacer(1, 6)]

    # ── Totals + payment ──────────────────────────────────────────────────────────────────────────
    tot = [["Sumas de Ventas:", res.get("totalNoSuj"), res.get("totalExenta"), res.get("totalGravada")]]
    sumas = Table([[_p(tot[0][0], SB)] + [_p(_m(x), SR) for x in tot[0][1:]]],
                  colWidths=[w_total * .5 * .46] + [w_total * .5 * .18] * 3)
    sumas.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#e6e6e6"))]))

    lin = [("Sumatoria de Ventas:", res.get("subTotalVentas")),
           ("Monto global Desc., Rebajas y otros a ventas no sujetas:", res.get("descuNoSuj")),
           ("Monto global Desc., Rebajas y otros a ventas Exentas:", res.get("descuExenta")),
           ("Monto global Desc., Rebajas y otros a ventas Gravadas:", res.get("descuGravada"))]
    if tipo == "03":
        for t in (res.get("tributos") or []):
            lin.append((t["descripcion"] + ":", t["valor"]))
        lin += [("IVA Percibido:", res.get("ivaPerci1"))]
    lin += [("SubTotal:", res.get("subTotal")), ("IVA Retenido:", res.get("ivaRete1")),
            ("Retención Renta:", res.get("reteRenta")),
            ("Monto Total de la Operación:", res.get("montoTotalOperacion")),
            ("Total Otros Montos No Afectos:", res.get("totalNoGravado")),
            ("Total a Pagar:", res.get("totalPagar"))]
    tl = [[_p(a, SB), _p(("$" if i in (0, len(lin) - 1) else "") + _m(b), SRB)] for i, (a, b) in enumerate(lin)]
    totales = Table(tl, colWidths=[w_total * .5 * .74, w_total * .5 * .26])
    totales.setStyle(TableStyle([("TOPPADDING", (0, 0), (-1, -1), 1.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
                                 ("LINEBEFORE", (0, 0), (0, -1), .8, MUTED)]))

    pago = res["pagos"][0]
    obs = [a["valor"] for a in (dte.get("apendice") or []) if a.get("campo") == "pagoReal"]
    izq = [_p("Valor en Letras:", _st("vl", 9, True)), Spacer(1, 3),
           _p(res["totalLetras"], _st("vlt", 10.5, True)),
           Spacer(1, 14),
           _campo("Forma de Pago:", PAGOS.get(pago["codigo"], pago["codigo"])),
           _campo("Condición de la Operación:", "Contado" if res.get("condicionOperacion") == 1 else "Crédito"),
           _campo("Observaciones:", ("Forma de pago real: " + obs[0]) if obs else "")]
    if pago.get("referencia"):
        izq.append(_campo("Referencia de pago:", pago["referencia"]))
    pie = Table([[izq, [sumas, totales]]], colWidths=[w_total * .5, w_total * .5])
    pie.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                             ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
    fl += [pie]

    doc.build(fl)
    return buf.getvalue()
