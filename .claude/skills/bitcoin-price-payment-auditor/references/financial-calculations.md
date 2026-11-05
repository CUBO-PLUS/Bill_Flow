# Reglas financieras y modelo de datos

## Fórmulas (`precios_btc.convertir`, Decimal, ROUND_HALF_UP)
```
neto_usd   = round2(total_usd / 1.13)         # IVA 13 % incluido en el total
iva_usd    = total_usd - neto_usd              # suman exacto
total_btc  = round8(total_usd / precio_btc)
neto_btc   = round8(neto_usd  / precio_btc)
iva_btc    = total_btc - neto_btc              # suman exacto
total_sats = total_btc * 100_000_000           # entero exacto (btc ya tiene 8 decimales)
```
Redondeo al satoshi más cercano (half-up). Se redondea una vez por magnitud y los residuos se asignan por diferencia para que neto+IVA = total en USD, BTC y sats. IVA 13 % solo cuando corresponda a la operación (constante `IVA_DIVISOR`).

## Tablas
`venta_bitcoin` (1:1 con `venta`, `ON DELETE CASCADE`): heredadas `venta_id, fecha_hora, total_usd, iva_usd, neto_usd, precio_btc_usd, total_btc, total_sats, neto_btc, estado(pendiente|pagada|rechazada), id_pago UNIQUE`; añadidas `fuente_precio, fecha_precio (UTC), iva_btc, cotizacion_id`. (Se eliminaron por decisión del usuario `metodo_pago`, `fecha_vencimiento`, `fecha_confirmacion`, `tasa_confirmacion` y la tabla `evento_pago_btc`.)
- `cotizacion_btc` (append-only): precio exacto como texto, fuente, `tipo_precio`, `precision`, bid/ask, `consultado_utc`, `validacion`, `url`, `respuesta` cruda; `tipo` = `registro` | `confirmacion` (precio al confirmar, separado).
- `auditoria_btc` (append-only): hallazgos guardados con `--guardar`.
- Triggers: pago `pagada` inmutable; `precio_btc_usd/total_usd/total_btc/total_sats/fecha_hora/id_pago` no se sobrescriben; `cotizacion_btc` y `auditoria_btc` (append-only) rechazan UPDATE/DELETE. Una corrección autorizada exige eliminar/recrear el trigger conscientemente: no hacerlo sin permiso del usuario.
- `estado` no tiene valor "vencida": la auditoría marca como `PENDIENTE_VENCIDO` los pendientes con más de `BTC_QUOTE_TTL_MIN` minutos.

## Fechas
`venta*.fecha_hora` = local sin zona; `fecha_precio`, `consultado_utc` = UTC `YYYY-MM-DDTHH:MM:SSZ`. Cambiar de servidor/zona exige ajustar `BTC_LOCAL_TZ`.

## Variables de entorno
`DB_PATH`, `BTC_LOCAL_TZ` (America/El_Salvador), `BTC_QUOTE_TTL_MIN` (15). `BTC_USD_RATE` ya **no** se usa.
