-- Pagos con Bitcoin. Se aplica siempre al arrancar (IF NOT EXISTS), también en bases ya creadas.
CREATE TABLE IF NOT EXISTS venta_bitcoin (
    id                 INTEGER PRIMARY KEY,
    venta_id           INTEGER NOT NULL UNIQUE,      -- FK -> venta.id
    fecha_hora         TEXT NOT NULL,                -- cuándo se registró
    empleado_id        INTEGER,                      -- "Registrado por"
    total_usd          REAL NOT NULL,                -- Total venta (IVA incluido)
    iva_usd            REAL NOT NULL,                -- IVA 13% = total - total/1.13
    neto_usd           REAL NOT NULL,                -- Neto sin IVA = total/1.13
    precio_btc_usd     REAL NOT NULL CHECK (precio_btc_usd > 0),  -- tasa al momento del registro
    total_btc          REAL NOT NULL,
    total_sats         INTEGER NOT NULL,
    neto_btc           REAL NOT NULL,
    estado             TEXT NOT NULL DEFAULT 'pendiente'
                       CHECK (estado IN ('pendiente', 'pagada', 'rechazada')),
    id_pago            TEXT NOT NULL UNIQUE,         -- código que trae el JSON de confirmación
    FOREIGN KEY (venta_id)    REFERENCES venta(id) ON DELETE CASCADE,
    FOREIGN KEY (empleado_id) REFERENCES empleado(id)
);

-- ---------------------------------------------------------------------------
-- Trazabilidad (skill bitcoin-price-payment-auditor). Tablas APPEND-ONLY:
-- los triggers impiden UPDATE y DELETE, así nunca se sobrescribe una cotización.
-- Las columnas nuevas de venta_bitcoin se agregan en bitcoin.migrar().
-- ---------------------------------------------------------------------------

-- Copia inmutable de cada cotización consultada (precio exacto como TEXT decimal).
CREATE TABLE IF NOT EXISTS cotizacion_btc (
    id              INTEGER PRIMARY KEY,
    tipo            TEXT NOT NULL CHECK (tipo IN ('registro', 'confirmacion')),
    venta_id        INTEGER NOT NULL,
    id_pago         TEXT NOT NULL,
    precio_btc_usd  TEXT NOT NULL,        -- Decimal exacto
    fuente          TEXT NOT NULL,        -- coinbase | kraken | coingecko
    tipo_precio     TEXT NOT NULL,        -- spot | ultimo_negociado | ...
    precision       TEXT NOT NULL,        -- exacta_al_consultar | aproximada_vela_1m
    bid             TEXT,
    ask             TEXT,
    consultado_utc  TEXT NOT NULL,        -- instante real de la consulta (ISO UTC)
    validacion      TEXT,
    url             TEXT,
    respuesta       TEXT,                 -- JSON crudo de la fuente
    FOREIGN KEY (venta_id) REFERENCES venta(id)
);
CREATE INDEX IF NOT EXISTS ix_cotizacion_btc_pago ON cotizacion_btc (id_pago, tipo);

-- Hallazgos de auditorías guardadas con audit_transactions.py --guardar.
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
BEGIN SELECT RAISE(ABORT, 'cotizacion_btc es inmutable'); END;
CREATE TRIGGER IF NOT EXISTS cotizacion_btc_no_delete BEFORE DELETE ON cotizacion_btc
BEGIN SELECT RAISE(ABORT, 'cotizacion_btc es inmutable'); END;
CREATE TRIGGER IF NOT EXISTS auditoria_btc_no_update BEFORE UPDATE ON auditoria_btc
BEGIN SELECT RAISE(ABORT, 'auditoria_btc es inmutable'); END;
CREATE TRIGGER IF NOT EXISTS auditoria_btc_no_delete BEFORE DELETE ON auditoria_btc
BEGIN SELECT RAISE(ABORT, 'auditoria_btc es inmutable'); END;
