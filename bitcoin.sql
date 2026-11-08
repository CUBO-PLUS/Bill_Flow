-- Bitcoin payments. Always applied at startup (IF NOT EXISTS), also on already-created databases.
CREATE TABLE IF NOT EXISTS venta_bitcoin (
    id                 INTEGER PRIMARY KEY,
    venta_id           INTEGER NOT NULL UNIQUE,      -- FK -> venta.id
    fecha_hora         TEXT NOT NULL,                -- when it was recorded
    empleado_id        INTEGER,                      -- "Recorded by"
    total_usd          REAL NOT NULL,                -- Sale total (VAT included)
    iva_usd            REAL NOT NULL,                -- 13% VAT = total - total/1.13
    neto_usd           REAL NOT NULL,                -- Net excl. VAT = total/1.13
    precio_btc_usd     REAL NOT NULL CHECK (precio_btc_usd > 0),  -- rate at the time of recording
    total_btc          REAL NOT NULL,
    total_sats         INTEGER NOT NULL,
    neto_btc           REAL NOT NULL,
    estado             TEXT NOT NULL DEFAULT 'pendiente'
                       CHECK (estado IN ('pendiente', 'pagada', 'rechazada')),
    id_pago            TEXT NOT NULL UNIQUE,         -- code carried by the confirmation JSON
    FOREIGN KEY (venta_id)    REFERENCES venta(id) ON DELETE CASCADE,
    FOREIGN KEY (empleado_id) REFERENCES empleado(id)
);

-- ---------------------------------------------------------------------------
-- Traceability (bitcoin-price-payment-auditor skill). APPEND-ONLY tables:
-- the triggers block UPDATE and DELETE, so a quote is never overwritten.
-- The new venta_bitcoin columns are added in bitcoin.migrar().
-- ---------------------------------------------------------------------------

-- Immutable copy of every quote fetched (exact price as decimal TEXT).
CREATE TABLE IF NOT EXISTS cotizacion_btc (
    id              INTEGER PRIMARY KEY,
    tipo            TEXT NOT NULL CHECK (tipo IN ('registro', 'confirmacion')),
    venta_id        INTEGER NOT NULL,
    id_pago         TEXT NOT NULL,
    precio_btc_usd  TEXT NOT NULL,        -- Exact Decimal
    fuente          TEXT NOT NULL,        -- coinbase | kraken | coingecko
    tipo_precio     TEXT NOT NULL,        -- spot | ultimo_negociado | ...
    precision       TEXT NOT NULL,        -- exacta_al_consultar | aproximada_vela_1m
    bid             TEXT,
    ask             TEXT,
    consultado_utc  TEXT NOT NULL,        -- actual instant of the query (ISO UTC)
    validacion      TEXT,
    url             TEXT,
    respuesta       TEXT,                 -- raw JSON from the source
    FOREIGN KEY (venta_id) REFERENCES venta(id)
);
CREATE INDEX IF NOT EXISTS ix_cotizacion_btc_pago ON cotizacion_btc (id_pago, tipo);

-- Audit findings saved with audit_transactions.py --guardar.
CREATE TABLE IF NOT EXISTS auditoria_btc (
    id              INTEGER PRIMARY KEY,
    ejecutada_utc   TEXT NOT NULL,
    venta_id        INTEGER,
    id_pago         TEXT,
    codigo          TEXT NOT NULL,
    severidad       TEXT NOT NULL CHECK (severidad IN ('ALTA', 'MEDIA', 'BAJA', 'INFO')),
    detalle         TEXT NOT NULL,
    datos_json      TEXT
);

CREATE TRIGGER IF NOT EXISTS cotizacion_btc_no_update BEFORE UPDATE ON cotizacion_btc
BEGIN SELECT RAISE(ABORT, 'cotizacion_btc is immutable'); END;
CREATE TRIGGER IF NOT EXISTS cotizacion_btc_no_delete BEFORE DELETE ON cotizacion_btc
BEGIN SELECT RAISE(ABORT, 'cotizacion_btc is immutable'); END;
CREATE TRIGGER IF NOT EXISTS auditoria_btc_no_update BEFORE UPDATE ON auditoria_btc
BEGIN SELECT RAISE(ABORT, 'auditoria_btc is immutable'); END;
CREATE TRIGGER IF NOT EXISTS auditoria_btc_no_delete BEFORE DELETE ON auditoria_btc
BEGIN SELECT RAISE(ABORT, 'auditoria_btc is immutable'); END;
