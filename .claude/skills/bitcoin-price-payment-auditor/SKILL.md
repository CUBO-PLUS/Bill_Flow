---
name: bitcoin-price-payment-auditor
description: Consulta precios BTC/USD (Coinbase, Kraken, CoinGecko), reconstruye cotizaciones históricas, calcula conversiones USD/BTC/satoshis con IVA, gestiona registros de pagos Bitcoin (BTCPay) y audita la integridad financiera de las transacciones. Usar al pedir precio actual de BTC, auditar ventas/pagos Bitcoin, revisar cotizaciones vencidas o pagos pendientes, diagnosticar diferencias de monto, o modificar el módulo Bitcoin (bitcoin.py, venta_bitcoin).
---

# Bitcoin Price & Payment Auditor

Skill de **conocimiento y herramientas para Claude**. El backend (`precios_btc.py`, `bitcoin.py`, `app.py`) es quien registra cada cotización automáticamente; esta skill NO es parte del flujo de cobro y no debe necesitarse para que una venta guarde su precio.

## Reglas inquebrantables
1. **Nunca modificar** `venta`, `venta_bitcoin` ni pagos confirmados, ni corregir históricos, sin autorización expresa y específica del usuario (qué registros y qué valor). Las auditorías son solo lectura. Los triggers de la base ya bloquean UPDATE de precio/total/sats/id_pago y de cualquier pago `pagada`.
2. **Nunca inventar precios.** Distinguir siempre tres niveles y nombrarlos así en los reportes:
   - `exacto_registrado`: cotización guardada al cobrar (`cotizacion_btc` + `fuente_precio`).
   - `aproximado_vela`: reconstruido con vela de 1 min de Coinbase (no prueba el precio de un segundo concreto).
   - `no_verificable`: sin fuente propia ni vela.
3. **No mezclar tipos de precio**: spot, bid, ask, último negociado, open/high/low/close de vela NO son equivalentes (ver `references/coinbase-api.md`).
4. **Dinero solo con `Decimal`** (`precios_btc.convertir`). Nunca `float` en cálculos; REAL en `venta_bitcoin` es solo almacenamiento heredado.
5. **Sin cotización válida no hay cobro.** No usar precios viejos ni constantes (el antiguo 100000 fijo ya no existe).
6. Verificar endpoints/parámetros en la documentación oficial vigente antes de implementarlos; no inventarlos (BTCPay: `references/btcpay-integration.md`).

## Mapa del proyecto (verificado)
- Flask + SQLite `restaurante.db`. Hora de ventas = **hora local del servidor, sin zona guardada** (`datetime('now','localtime')`); se interpreta con `BTC_LOCAL_TZ` (por defecto `America/El_Salvador`, UTC-6 sin horario de verano). Si cambia el servidor de zona, ajustar esa variable.
- Ventas: tabla `venta` + `detalle_venta`; total = vista `v_venta_total`. Forma de pago Bitcoin = `forma_pago.id 10`.
- Backend Bitcoin: `precios_btc.py` (precios/Decimal/UTC), `bitcoin.py` (`migrar`, `registrar_pendiente`, `confirmar`), `bitcoin.sql` (tablas), `app.py` ruta `/ventas/nueva`, `confirmar_pago.py` (CLI de confirmación por JSON). No hay endpoint de webhook BTCPay todavía.
- Esquema y reglas: `references/financial-calculations.md`.

## Qué hacer según la petición
| Petición | Acción |
|---|---|
| Precio actual / comparar fuentes | `python3 scripts/get_btc_price.py` (añadir `--cotizacion` para ver lo que usaría el sistema) |
| Precio histórico de una venta | `python3 scripts/historical_prices.py --venta N` (o `--fecha`) |
| Convertir importes | `python3 scripts/convert_amount.py --usd 12 --precio 80131.51` |
| Auditar todo | `python3 scripts/audit_transactions.py` (`--offline`, `--venta N`, `--json`, `--out f.md`, `--guardar`) |
| Pendientes vencidos / duplicados / montos | auditoría completa; ver códigos en el docstring del script |
| Verificar que ventas nuevas guardan precio | auditoría + `SELECT * FROM cotizacion_btc` y comprobar `fuente_precio`, `fecha_precio` y `cotizacion_id` no nulos en ventas posteriores a la migración; correr tests |
| Mejorar el módulo Bitcoin | leer `references/`, cambiar `precios_btc.py`/`bitcoin.py`, añadir prueba, correr tests |

Rutas relativas a `.claude/skills/bitcoin-price-payment-auditor/`. Todo usa solo la biblioteca estándar.

## Cómo informar una auditoría
Tabla comparativa por venta (precio original, fuente, cierre de vela, % de diferencia, BTC y sats original vs. reconstruido) y lista de hallazgos por severidad. Explicar siempre que lo histórico es **aproximado**. Proponer correcciones como opciones y **esperar autorización**; si el usuario autoriza, hacerlas en un registro nuevo/auditable (no `UPDATE` silencioso) y guardar el motivo.

## Registro automático de cobros (contrato del backend)
En `app.py` → `precios_btc.obtener_cotizacion()` (Coinbase spot → Kraken validado, contraste CoinGecko) **antes** de crear la venta; si falla, la venta no se crea. `bitcoin.registrar_pendiente` guarda: copia inmutable en `cotizacion_btc` (precio exacto en texto, fuente, tipo, instante UTC, respuesta cruda), neto/IVA USD y BTC, sats e `id_pago`. `bitcoin.confirmar` rechaza duplicados, desconocidos y montos distintos (insuficiente/excesivo; la venta sigue pendiente) y guarda aparte el precio vigente al confirmar (`cotizacion_btc.tipo='confirmacion'`).

## Pruebas
`python3 -m unittest discover -s .claude/skills/bitcoin-price-payment-auditor/tests -v` (sin red; fixtures reales de las ventas 3 y 4). Toda función nueva de precios o dinero requiere prueba.

## Pendiente fuera del código
Instancia BTCPay Server (URL, API key, storeId, webhook + secreto) y endpoint receptor de webhooks: ver `references/btcpay-integration.md`.
