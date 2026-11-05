"""Recibo en PDF sin dependencias (Helvetica, una página tipo ticket)."""


def _esc(s):
    s = str(s).encode("cp1252", "replace").decode("cp1252")
    return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def recibo_pdf(dte):
    e, r, res, ident = dte["emisor"], dte["receptor"], dte["resumen"], dte["identificacion"]
    L = [("B", 13, e["nombreComercial"]), ("N", 8, e["nombre"]),
         ("N", 8, "NIT %s  NRC %s" % (e["nit"], e["nrc"])), ("N", 8, e["direccion"]["complemento"]),
         ("N", 8, "Tel. %s" % e["telefono"]), ("N", 8, "-" * 62),
         ("B", 9, "RECIBO  (no es el documento fiscal)"),
         ("N", 8, "Fecha: %s %s" % (ident["fecEmi"], ident["horEmi"])),
         ("N", 8, "Control: %s" % ident["numeroControl"]),
         ("N", 8, "Cliente: %s" % (r.get("nombre") or "Consumidor final")), ("N", 8, "-" * 62)]
    for it in dte["cuerpoDocumento"]:
        L.append(("N", 8, "%s x %s" % (it["cantidad"], it["descripcion"][:40])))
        L.append(("N", 8, "      $%.2f c/u  =  $%.2f" % (it["precioUni"], it["ventaGravada"])))
    L += [("N", 8, "-" * 62)]
    if res.get("totalIva"):
        L.append(("N", 8, "IVA incluido: $%.2f" % res["totalIva"]))
    L += [("B", 11, "TOTAL: $%.2f" % res["totalPagar"]), ("N", 8, res["totalLetras"]),
          ("N", 8, "Pago: código %s" % res["pagos"][0]["codigo"]), ("N", 8, "Gracias por su compra")]
    alto = 40 + 14 * len(L)
    y, partes = alto - 30, []
    for f, sz, t in L:
        partes.append("BT /%s %d Tf 20 %d Td (%s) Tj ET" % (f, sz, y, _esc(t)))
        y -= 14
    cont = "\n".join(partes).encode("cp1252", "replace")
    objs = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            ("<< /Type /Page /Parent 2 0 R /MediaBox [0 0 330 %d] /Contents 4 0 R /Resources << /Font "
             "<< /N 5 0 R /B 6 0 R >> >> >>" % alto).encode(),
            b"<< /Length %d >>\nstream\n" % len(cont) + cont + b"\nendstream",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>"]
    out, pos = bytearray(b"%PDF-1.4\n"), []
    for i, o in enumerate(objs, 1):
        pos.append(len(out))
        out += b"%d 0 obj\n" % i + o + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    for p in pos:
        out += b"%010d 00000 n \n" % p
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref)
    return bytes(out)
