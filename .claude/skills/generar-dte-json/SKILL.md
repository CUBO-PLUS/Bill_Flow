---
name: generar-dte-json
description: Genera el JSON del DTE (factura 01, CCF 03, exportación 11) de una venta de restaurante.db, listo para firmar y enviar a Hacienda, y su recibo PDF. Usar al pedir el DTE/JSON/recibo de una venta o al cambiar datos del emisor o reglas de pago.
---

# DTE por venta

- `dte_plantilla.json`: datos fijos (emisor de Hacienda, ambiente, versión). Edita aquí la empresa.
- `dte.py <venta_id> [-o f.json]`: completa receptor, ítems, totales, IVA 13 %, pagos, `numeroControl` y
  `codigoGeneracion` (estable por venta) desde SQLite; NIT/NRC del CCF salen de `.env.clientes`.
- Regla de pago: en 01 y 11 los códigos 11 (Bitcoin) y 12 (cripto) no valen → se usa 99 y el detalle real va
  en `apendice`. En 03 sí valen 11 y 12.
- `recibo_pdf.py`: recibo PDF sin dependencias.
- App (admin): botón **DTE details** → `/dte` → *Detail* → Recibo PDF / Descargar DTE.
- El JSON sale SIN firma (`ambiente` "00" pruebas; poner "01" en producción). Falta: firmar, y llenar
  `responseMH` con la respuesta de Hacienda.
