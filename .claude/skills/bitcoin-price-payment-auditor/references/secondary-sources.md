# Kraken (respaldo) y CoinGecko (contraste)

## Kraken — `GET https://api.kraken.com/0/public/Ticker?pair=XBTUSD`
Docs: https://docs.kraken.com/api/docs/rest-api/get-ticker-information
Verificado: `{"error":[],"result":{"XXBTZUSD":{"a":[ask,lotes,lotes],"b":[bid,...],"c":[último,volumen],"v":..,"p":..,"t":..,"l":..,"h":..,"o":apertura_del_día}}}`. La clave del par es `XXBTZUSD` (no `XBTUSD`): tomar el primer valor de `result`. `error` debe ser `[]`. El sistema usa `c[0]` (**último negociado**, no spot) y guarda bid/ask.
Validación antes de usarlo como respaldo (en `precios_btc._kraken`): precios > 0, `ask ≥ bid`, spread ≤ 1 %; y si CoinGecko responde, desvío ≤ 2 %. Si CoinGecko no responde se acepta y se documenta "sin contraste".

## CoinGecko — `GET https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd`
Docs: https://docs.coingecko.com/reference/simple-price
Respuesta: `{"bitcoin":{"usd":80000}}`. Es un agregado, a veces redondeado y con caché: **solo para contraste**, nunca como precio de cobro.
