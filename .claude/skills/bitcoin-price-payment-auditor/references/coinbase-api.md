# Coinbase (fuente principal)

Docs: https://docs.cdp.coinbase.com/coinbase-app/docs/api-prices · https://docs.cdp.coinbase.com/exchange/reference/exchangerestapi_getproductcandles

## Spot — `GET https://api.coinbase.com/v2/prices/BTC-USD/spot`
Respuesta verificada: `{"data":{"amount":"80010.775","base":"BTC","currency":"USD"}}`. `amount` es **string** → `Decimal`, nunca float. Sin timestamp: el instante es el de la consulta (se registra `consultado_utc`). Validar `base=BTC`, `currency=USD`, precio > 0 y finito.

## Velas — `GET https://api.exchange.coinbase.com/products/BTC-USD/candles`
Parámetros: `granularity=60` (segundos), `start`, `end` (ISO 8601 UTC). Enviar un `User-Agent`. Respuesta: arreglo de `[time, low, high, open, close, volume]` (OJO: **low antes que high; open antes que close**), `time` = epoch UTC del inicio de la vela, más reciente primero. Si no hubo operaciones puede faltar la vela → "sin dato", no interpolar. Límite máx. 300 velas por petición; el endpoint público tiene límite de tasa (≈10 req/s): pausar al auditar muchas ventas. Pedir `start=minuto:00` y `end=minuto:59` devuelve solo la vela buscada.

## No son equivalentes
| Valor | Significado | Uso |
|---|---|---|
| spot | precio de referencia de Coinbase en ese momento | precio de cotización (fuente principal) |
| bid | mayor precio de compra en el libro | lo que recibirías al vender |
| ask | menor precio de venta en el libro | lo que pagarías al comprar |
| último negociado | precio de la última operación | referencia Kraken (`c`) |
| open / close | primer / último precio negociado en el minuto | cierre = referencia aproximada histórica |
| high / low | extremos del minuto | comprobar si un precio original era plausible |

Una vela de 1 min **no prueba** el precio de un segundo concreto; el cierre ocurre hasta 59 s después del instante de la venta.
