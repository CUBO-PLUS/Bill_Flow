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
    fecha_confirmacion TEXT,                         -- NULL hasta que se confirma
    tasa_confirmacion  REAL,                         -- tasa que vino en el JSON
    FOREIGN KEY (venta_id)    REFERENCES venta(id) ON DELETE CASCADE,
    FOREIGN KEY (empleado_id) REFERENCES empleado(id)
);
