# BTCPay Server (Greenfield API)

Docs oficiales: https://docs.btcpayserver.org/ · esquema OpenAPI (fuente verificada): `BTCPayServer/wwwroot/swagger/v1/swagger.template.invoices.json` y `...webhooks.json` en https://github.com/btcpayserver/btcpayserver. **Estado:** el repositorio NO tiene aún integración con BTCPay (la confirmación actual es por JSON con `confirmar_pago.py`). Antes de implementar, releer la documentación vigente y el swagger de *tu* versión de servidor (`https://<tu-btcpay>/docs`).

## Endpoints (verificados en el swagger)
- Crear factura: `POST /api/v1/stores/{storeId}/invoices`. Cuerpo: `amount` (string decimal), `currency` (p. ej. `USD`), `metadata` (guardar `id_pago`/`venta_id`), `checkout`: `paymentMethods` (ids como `BTC` y `BTC-LightningNetwork` según el swagger; el id exacto depende de la versión y de la tienda — confirmarlo en tu instancia), `defaultPaymentMethod`, `expirationMinutes` (defecto de tienda 15), `monitoringMinutes`, `speedPolicy`.
- Leer factura: `GET /api/v1/invoices/{invoiceId}`; métodos de pago/destinos/`rate`/`due`/`totalPaid`: `GET /api/v1/invoices/{invoiceId}/payment-methods`.
- Estados de factura: `New`, `Processing`, `Expired`, `Invalid`, `Settled`. Marcar manualmente: `POST /api/v1/invoices/{id}/status` (`Invalid|Settled`) — acción sensible, solo con autorización.
- Webhooks: `POST /api/v1/stores/{storeId}/webhooks` (`url`, `secret`, `authorizedEvents`, `automaticRedelivery`). Eventos de factura: `InvoiceCreated`, `InvoiceReceivedPayment`, `InvoiceProcessing`, `InvoiceExpired`, `InvoiceSettled`, `InvoiceInvalid`, `InvoicePaymentSettled`.
- Autenticación: API key de Greenfield con permisos mínimos para crear/ver facturas y gestionar webhooks (nombres exactos y esquema de cabecera: confirmar en https://docs.btcpayserver.org/API/Greenfield/v1/ — no verificados aquí); nunca guardarla en el repositorio ni en la base.

## Webhooks: seguridad y duplicados
- Verificar la cabecera `BTCPay-Sig: sha256=HMAC_SHA256(secret, cuerpo_crudo)` con comparación en tiempo constante (`hmac.compare_digest`) **antes** de parsear el cuerpo. Rechazar con 401 si no coincide.
- Campos del evento: `deliveryId`, `webhookId`, `originalDeliveryId`, `isRedelivery`, `type`, `storeId`, `invoiceId`, `metadata`. Idempotencia: ya no existe tabla de eventos; `bitcoin.confirmar` es idempotente por estado (una venta no pendiente devuelve "ya está ..."). Al implementar el receptor, deduplicar por `deliveryId`/`originalDeliveryId` en esa capa. Una redelivery (`isRedelivery=true`) trae un `deliveryId` nuevo y `originalDeliveryId` con el original: deduplicar también por `originalDeliveryId` e `invoiceId`+estado (`confirmar` ya devuelve "duplicado" si la venta no está pendiente).
- Responder 200 rápido; BTCPay reintenta fallos.
- `InvoiceSettled` trae `overPaid` y `manuallyMarked`; `InvoiceReceivedPayment` trae `afterExpiration` y `paymentMethodId`. Pago tardío (`afterExpiration`) → no confirmar automáticamente; revisión humana.

## Mapeo al sistema
El sistema ya no guarda el método (Lightning/On-chain); si se necesita, reintroducirlo con migración. Factura → guardar `invoiceId` (en `id_pago` o columna nueva con migración idempotente en `bitcoin.migrar`). QR: usar el `paymentLink`/`destination` de `payment-methods` (BIP21 para on-chain, BOLT11 para Lightning) y generarlo en el cliente; no inventar formatos. Montos recibidos: `totalPaid` vs `amount`/`due` → si no coinciden, `confirmar` rechaza (insuficiente/excesivo) y la venta sigue pendiente hasta revisión humana.
