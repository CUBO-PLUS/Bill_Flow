# Demo: restaurant, sales and DTE (Flask + SQLite)

Uses the schema in `restaurante_db.sql` (dishes, sales, line items, document type, payment method, DTE status, roles and employees).

- **Sign-up**: username and password (stored in the `empleado` table). Choose the role: *Cashier Assistant* or *Administrator*.
- **Cashier Assistant**: records sales (dish, quantity, document type, payment method) and only sees their own.
- **Administrator**: sees employees and all sales, and advances the DTE status (step 1 to 5).

## Installation (in the VS Code terminal, one line at a time)

En macOS y Linux la mayoría de los comandos de Git y Python son idénticos a los de Windows, pero cambian dos cosas principales:

Las rutas usan barras diagonales (/ en lugar de \).

La forma de activar el entorno virtual es diferente.

Aquí tienes la guía adaptada para poner en tu README.md dividida claramente por sistema operativo para que cualquier persona pueda instalar el proyecto por primera vez.

Markdown

## 🚀 Guía de Instalación y Ejecución

Sigue las instrucciones según el sistema operativo de tu computadora.

---

### 🪟 Opción A: Windows (PowerShell)

Abre **PowerShell** y ejecuta un bloque a la vez:

#### 1. Instalar Python y Git (omite si ya los tienes)
```powershell
winget install -e --id Python.Python.3.12
winget install -e --id Git.Git
(Si los acabas de instalar, cierra y vuelve a abrir PowerShell).

2. Ir al Escritorio y clonar el repositorio
PowerShell

if (Test-Path "$HOME\OneDrive\Desktop") { cd "$HOME\OneDrive\Desktop" } elseif (Test-Path "$HOME\Desktop") { cd "$HOME\Desktop" } else { New-Item -ItemType Directory -Path "$HOME\Desktop" -Force; cd "$HOME\Desktop" }
git clone [https://github.com/CUBO-PLUS/Bill_Flow.git](https://github.com/CUBO-PLUS/Bill_Flow.git)
cd Bill_Flow
3. Crear el entorno virtual
PowerShell

python -m venv venv
4. Autorizar scripts y activar el entorno virtual
PowerShell

Set-ExecutionPolicy -Scope CurrentUser RemoteSigned -Force
.\venv\Scripts\Activate.ps1
(Verifica que aparezca (venv) al inicio de la línea de comandos).

5. Instalar dependencias
PowerShell

pip install -r requirements.txt tzdata
6. Iniciar la aplicación
PowerShell

python app.py
🍎 Opción B: macOS / 🐧 Linux (Terminal)
Abre la Terminal (Cmd + Espacio y busca Terminal en Mac) y ejecuta:

1. Ir al Escritorio y clonar el proyecto
Bash

cd ~/Desktop
git clone [https://github.com/CUBO-PLUS/Bill_Flow.git](https://github.com/CUBO-PLUS/Bill_Flow.git)
cd Bill_Flow
2. Crear el entorno virtual
Bash

python3 -m venv venv
3. Activar el entorno virtual
Bash

source venv/bin/activate
(Verifica que aparezca (venv) al inicio de la terminal).

4. Instalar dependencias
Bash

pip install -r requirements.txt
5. Iniciar la aplicación
Bash

python3 app.py
🌐 Abrir en el Navegador
Una vez que veas el mensaje del servidor corriendo en la consola (en cualquier sistema), abre tu navegador de preferencia ingresando a:

👉 http://localhost:5001


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
