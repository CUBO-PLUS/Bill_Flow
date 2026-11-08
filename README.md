# Demo: restaurant, sales and DTE (Flask + SQLite)

Uses the schema in `restaurante_db.sql` (dishes, sales, line items, document type, payment method, DTE status, roles and employees).

- **Sign-up**: username and password (stored in the `empleado` table). Choose the role: *Cashier Assistant* or *Administrator*.
- **Cashier Assistant**: records sales (dish, quantity, document type, payment method) and only sees their own.
- **Administrator**: sees employees and all sales, and advances the DTE status (step 1 to 5).

## Installation (in the VS Code terminal, one line at a time)

```bash
python3 -m venv venv
```

```bash
source venv/bin/activate
```

```bash
pip install -r requirements.txt
```

## Running

```bash
python app.py
```

Open http://localhost:5000

## Configuration

In `app.py`:

- `PERMITIR_REGISTRO_ADMIN = True` lets users pick "Administrator" at sign-up (for the demo).
- Set it to `False` if you want sign-up to only create Cashier Assistants.

Data is stored in `restaurante.db` (SQLite), which is created automatically from `restaurante_db.sql` the first time. To reset the demo, delete that file.

## Security note

Passwords are stored as hashes (scrypt with salt), not as plain text. This demo has no HTTPS or CSRF protection, so do not expose it to the internet as-is.

## Data (database diagram)

- The **Administrator** dashboard has a green **Data** button (top right). It opens `/data`: the real schema of `restaurante.db` (tables, primary keys PK, foreign keys FK, row counts and latest rows). It refreshes by itself when users or sales are added.
- `python esquema.py` prints the schema as JSON (`lucid_create_erd` format).
- Project skill: `.claude/skills/actualizar-lucid-erd` → with Claude Code and the Lucid MCP it redraws the ERD in Lucid and saves the link in `lucid_erd.json` (the Data button shows it).

### Lucid requirement

To use the skill and open the diagram you must be **able to sign in to Lucid with your email** (a lucid.app account) and have the **Lucid** connector authorized in Claude (claude.ai → Connectors). Without that account/authorization the skill cannot create or update the diagram.

## Bitcoin payments (traceability)

- When **Bitcoin** is chosen, BTC/USD is queried (Coinbase → validated Kraken) and an immutable copy is stored in `cotizacion_btc` with source, UTC time and raw response. If there is no valid price, **the sale is not created**. The fixed `BTC_USD_RATE` rate no longer exists.
- A pending payment is considered expired after `BTC_QUOTE_TTL_MIN` minutes (15). Time zone of the sales: `BTC_LOCAL_TZ` (America/El_Salvador).
- Claude Code skill: `.claude/skills/bitcoin-price-payment-auditor` (audit: `python3 .claude/skills/bitcoin-price-payment-auditor/scripts/audit_transactions.py`).
- Tests: `python3 -m unittest discover -s .claude/skills/bitcoin-price-payment-auditor/tests -v`
