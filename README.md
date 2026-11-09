# Bill_Flow: It is a bussiness demo where you can register a sell and get the DTE with " el sello de recepcion" from Hacienda in a second integrating Bitcoin (Flask + SQLite) 

A demo system for a restaurant that records sales (it can be implemented in any business), stores the data required for the DTE, and keeps a traceable record of Bitcoin payments.

It uses the schema in `restaurante_db.sql` (dishes, sales, sale lines, document type, payment method, DTE status, roles and employees).

## What you can do

- **Sign up** with a username and password, and choose your role.
- **Record sales** with dish, quantity, document type and payment method (including Bitcoin).
- **Advance the DTE status** (from step 1 to 5) as an administrator.
- **View the database** from the **Data** button in the administrator panel.

## Roles

- **Cashier Assistant:** records sales and only sees their own sales.
- **Administrator:** sees all employees and all sales, and advances the DTE status.

## Business model

Bill_Flow is not sold as a one-time license. It is offered as a service with four components:

- **System installation:** initial setup of the system for the business.
- **Per-query fee:** a charge for each query the system processes.
- **Modifications:** changes requested by the business owner, or changes required when DTE laws are reformed.
- **3-year contract:** each client signs a three-year agreement.

---

## Before you start

You need:

- **Python 3.12** (or later)
- **Git** (or download the project as a ZIP, see below)
- **An internet connection** (to query the Bitcoin price)

Open **one terminal** and follow the steps for your operating system. Run **one command at a time** and wait for it to finish before running the next.

---

## 🪟 Windows (PowerShell)

### 1. Open PowerShell

Press the **Start** key, type `PowerShell` and press **Enter**.

### 2. Install Python and Git

Skip this step if you already have them. Run these two commands, one at a time:

```powershell
winget install -e --id Python.Python.3.12
```

```powershell
winget install -e --id Git.Git
```

When it finishes, **close PowerShell and open it again**. Then verify:

```powershell
python --version
```

```powershell
git --version
```

### 3. Go to the Desktop and download the project

```powershell
if (Test-Path "$HOME\OneDrive\Desktop") { cd "$HOME\OneDrive\Desktop" } elseif (Test-Path "$HOME\Desktop") { cd "$HOME\Desktop" } else { New-Item -ItemType Directory -Path "$HOME\Desktop" -Force; cd "$HOME\Desktop" }
```

```powershell
git clone https://github.com/CUBO-PLUS/Bill_Flow.git
```

```powershell
cd Bill_Flow
```

> **Without Git:** open https://github.com/CUBO-PLUS/Bill_Flow, click **Code → Download ZIP**, extract the file to your Desktop, and open the `Bill_Flow` folder in PowerShell.

### 4. Create the virtual environment

```powershell
python -m venv venv
```

### 5. Allow scripts and activate the virtual environment

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned -Force
```

```powershell
.\venv\Scripts\Activate.ps1
```

Check that **`(venv)`** appears at the start of the line.

### 6. Install the dependencies

```powershell
pip install -r requirements.txt tzdata
```

> On Windows, the `tzdata` package is needed to handle time zones.

### 7. Start the application

```powershell
python app.py
```

When you see that the server is running, continue with **Open the application**.

---

## 🍎 macOS (Terminal)

### 1. Open Terminal

Press **Cmd + Space**, type `Terminal` and press **Enter**.

### 2. Check Python and Git

Run:

```bash
python3 --version
```

If you do not see version 3.12 or later, install Python from https://www.python.org/downloads/ (or with Homebrew: `brew install python@3.12`).

```bash
git --version
```

If Git is not installed, macOS will offer to install the **Command Line Tools**. Accept and wait for it to finish.

### 3. Go to the Desktop and download the project

```bash
cd ~/Desktop
```

```bash
git clone https://github.com/CUBO-PLUS/Bill_Flow.git
```

```bash
cd Bill_Flow
```

> **Without Git:** open https://github.com/CUBO-PLUS/Bill_Flow, click **Code → Download ZIP**, extract the file to your Desktop, and go into the folder with `cd ~/Desktop/Bill_Flow`.

### 4. Create the virtual environment

```bash
python3 -m venv venv
```

### 5. Activate the virtual environment

```bash
source venv/bin/activate
```

Check that **`(venv)`** appears at the start of the line.

### 6. Install the dependencies

```bash
pip install -r requirements.txt
```

### 7. Start the application

```bash
python3 app.py
```

When you see that the server is running, continue with **Open the application**.

---

## 🐧 Linux (Ubuntu / Debian)

### 1. Open Terminal and install Python and Git

Skip this step if you already have them.

```bash
sudo apt update
```

```bash
sudo apt install -y python3 python3-venv git
```

### 2. Download the project

```bash
cd ~/Desktop
```

```bash
git clone https://github.com/CUBO-PLUS/Bill_Flow.git
```

```bash
cd Bill_Flow
```

> If you do not have a `Desktop` folder, use `cd ~` instead of `cd ~/Desktop`.

### 3. Create and activate the virtual environment

```bash
python3 -m venv venv
```

```bash
source venv/bin/activate
```

Check that **`(venv)`** appears at the start of the line.

### 4. Install the dependencies

```bash
pip install -r requirements.txt
```

### 5. Start the application

```bash
python3 app.py
```

---

## 🌐 Open the application

With the server running, open your browser and go to:

👉 **http://localhost:5001**

---

## First use (demo)

1. **Sign up:** choose a username, a password and your role.
2. **If you are a cashier:** record a sale by choosing a dish, quantity, document type and payment method. You will only see your own sales.
3. **If you are an administrator:** you will see all employees and all sales. From here you advance the DTE status (step 1 to 5).
4. **Data button (green, top right):** opens `/data`, showing the real schema of `restaurante.db`: tables, primary keys (PK), foreign keys (FK), row counts and latest rows. It refreshes automatically when users or sales are added.

---

## Bitcoin payments

- When you choose **Bitcoin**, the app queries the BTC/USD price (Coinbase, validated against Kraken) and stores an immutable copy in the `cotizacion_btc` table, with the source, the UTC time and the original response.
- **If there is no valid price, the sale is not created.** Check your internet connection if this happens.
- A pending payment expires after **15 minutes** (`BTC_QUOTE_TTL_MIN`).
- Sales use the **America/El_Salvador** time zone (`BTC_LOCAL_TZ`).

### Audit Bitcoin payments

With the virtual environment activated, run:

```bash
python3 .claude/skills/bitcoin-price-payment-auditor/scripts/audit_transactions.py
```

On Windows, use `python` instead of `python3`.

---

## Configuration

In `app.py`:

- `PERMITIR_REGISTRO_ADMIN = True` lets users choose **Administrator** when signing up (for the demo).
- Set it to `False` if you want sign-up to create only Cashier Assistants.

Data is stored in `restaurante.db` (SQLite). That database is created automatically from `restaurante_db.sql` the first time you run the app.

### Reset the demo (delete all data)

1. Stop the server with **Ctrl + C**.
2. Delete the `restaurante.db` file:
   - Windows: `del restaurante.db`
   - macOS / Linux: `rm restaurante.db`
3. Start again with `python app.py` (Windows) or `python3 app.py` (macOS / Linux).

---

## Database diagram (Lucid)

- `python esquema.py` prints the schema as JSON (`lucid_create_erd` format).
- Project skill: `.claude/skills/actualizar-lucid-erd`. With Claude Code and the Lucid connector, it redraws the ERD in Lucid and saves the link in `lucid_erd.json` (the **Data** button shows it).

**Requirement:** to use the skill you need a Lucid account (lucid.app) with your email, and the **Lucid** connector authorized in Claude (claude.ai → Connectors). Without these, the diagram cannot be created or updated.

---

## Tests

With the virtual environment activated:

```bash
python3 -m unittest discover -s .claude/skills/bitcoin-price-payment-auditor/tests -v
```

On Windows, use `python` instead of `python3`.

---

## Stop and exit

- To stop the server: **Ctrl + C** in the terminal.
- To leave the virtual environment: `deactivate`.

### Coming back another day

**Windows (PowerShell):**

```powershell
cd "$HOME\Desktop\Bill_Flow"
```

```powershell
.\venv\Scripts\Activate.ps1
```

```powershell
python app.py
```

**macOS / Linux:**

```bash
cd ~/Desktop/Bill_Flow
```

```bash
source venv/bin/activate
```

```bash
python3 app.py
```

---

## Troubleshooting

| Problem | Solution |
|---|---|
| Windows: `python` is not recognized | Close and reopen PowerShell. If it still fails, reinstall Python and check **Add python.exe to PATH**. |
| Windows: "running scripts is disabled" | Run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned -Force` first, then activate the environment. |
| macOS: `command not found: python3` | Install Python from python.org and reopen Terminal. |
| `(venv)` does not appear | Run the activation command for your system again. |
| `requirements.txt` not found | Make sure you are inside the `Bill_Flow` folder (use `dir` on Windows or `ls` on macOS / Linux). |
| Port 5001 is already in use | Stop the other running instance of the app with Ctrl + C, or close the program using that port. |
| The Bitcoin sale is not created | Check your internet connection. Without a valid price from Coinbase or Kraken, the sale is not recorded. |

---

## Security

Passwords are stored as hashes (scrypt with salt), not as plain text. This demo **has no HTTPS or CSRF protection**, so do not expose it to the internet as it is.
