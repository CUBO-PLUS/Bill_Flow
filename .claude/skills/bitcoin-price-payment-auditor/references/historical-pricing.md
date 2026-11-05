# Reconstrucción de precios históricos

1. Tomar `venta.fecha_hora` (hora local del servidor, sin zona). 2. Zona = `BTC_LOCAL_TZ` (por defecto `America/El_Salvador`, UTC-6). 3. Convertir a UTC (`precios_btc.local_a_utc`; respeta offsets explícitos). 4. Pedir a Coinbase la vela de 1 min que contiene el instante. 5. Referencia = **cierre** de la vela. 6. Registrar fuente, vela, metodología y precisión. 7. Comparar con el precio almacenado: `% = (original − hist) / hist × 100`. 8. Reconstruir BTC y sats con `convertir(total_usd, cierre)`. 9. Indicar también si el precio original cae dentro de [low, high] de la vela.

Clasificación obligatoria: `exacto_registrado` / `aproximado_vela` / `no_verificable`. Sin vela o con la API caída → `no_verificable`; jamás interpolar ni rellenar.

## Caso de referencia (consultado 2026-11-04, hora local UTC-6)
| Venta | Hora local | UTC | Cierre vela | Original | Dif. | Sats orig → reconst. |
|---|---|---|---|---|---|---|
| 3 | 13:23:35 | 19:23:35 | 80 131.51 | 100 000 | +24.79 % | 12 000 → 14 975 |
| 4 | 13:24:17 | 19:24:17 | 80 107.11 | 100 000 | +24.83 % | 24 000 → 29 960 |
El 100 000 original estaba fuera del rango high-low de ambas velas: era una tasa fija de demostración, no una cotización de mercado. Un cliente que hubiera pagado 12 000 sats habría pagado ≈ 9.61 USD en vez de 12.
