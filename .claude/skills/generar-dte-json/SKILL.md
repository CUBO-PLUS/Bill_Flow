---
name: generar-dte-json
description: Generates the DTE JSON (invoice 01, CCF 03, export 11) of a sale from restaurante.db, ready to sign and send to Hacienda, plus its PDF receipt. Use when asked for the DTE/JSON/receipt of a sale or when changing issuer data or payment rules.
---

# DTE per sale

- `dte_plantilla.json`: fixed data (Hacienda issuer, environment, version). Edit the company here.
- `dte.py <venta_id> [-o f.json]`: fills in receiver, items, totals, 13 % VAT, payments, `numeroControl` and
  `codigoGeneracion` (UPPERCASE UUID v4, stored once in the `dte_codigo` table; each DTE has its own) from SQLite; the CCF NIT/NRC come from `.env.clientes`.
- Payment rule: in 01 and 11 the codes 11 (Bitcoin) and 12 (crypto) are not valid → 99 is used and the real detail goes
  in `apendice`. In 03, 11 and 12 are valid.
- `recibo_pdf.py`: PDF of the DTE laid out like the Hacienda model (reportlab). Its QR encodes the official
  `https://admin.factura.gob.sv/consultaPublica?ambiente=..&codGen=..&fechaEmi=..` URL (override with `DTE_CONSULTA_URL`);
  the seal shows `responseMH.selloRecibido` or "Pendiente de recepción".
- App (admin): **DTE details** button → `/dte` → *Detail* → Receipt PDF / Download DTE.
- The JSON is UNSIGNED (`ambiente` "00" for testing; use "01" in production). Still missing: signing, and filling in
  `responseMH` with Hacienda's response.
