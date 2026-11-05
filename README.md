# Demo: restaurante, ventas y DTE (Flask + SQLite)

Usa el esquema de `restaurante_db.sql` (platillos, ventas, detalle, tipo de documento, forma de pago, estado del DTE, roles y empleados).

- **Registro**: usuario y contraseña (se guardan en la tabla `empleado`). Se elige el rol: *Asistente de caja* o *Administrador*.
- **Asistente de caja**: registra ventas (platillo, cantidad, tipo de documento, forma de pago) y ve solo las suyas.
- **Administrador**: ve empleados y todas las ventas, y avanza el estado del DTE (paso 1 a 5).

## Instalación (en la terminal de VS Code, una línea a la vez)

```bash
python3 -m venv venv
```

```bash
source venv/bin/activate
```

```bash
pip install -r requirements.txt
```

## Ejecución

```bash
python app.py
```

Abre http://localhost:5000

## Configuración

En `app.py`:

- `PERMITIR_REGISTRO_ADMIN = True` deja elegir "Administrador" en el registro (para la demo).
- Pon `False` si quieres que el registro solo cree Asistentes de caja.

Los datos se guardan en `restaurante.db` (SQLite), que se crea solo desde `restaurante_db.sql` la primera vez. Para reiniciar la demo, borra ese archivo.

## Nota de seguridad

Las contraseñas se guardan como hash (scrypt con sal), no en texto plano. Esta demo no tiene HTTPS ni protección CSRF, así que no la publiques en internet tal cual.

## Data (diagrama de la base de datos)

- En el panel de **Administrador** hay un botón verde **Data** (arriba a la derecha). Abre `/data`: el esquema real de `restaurante.db` (tablas, llaves primarias PK, foráneas FK, conteo de filas y últimas filas). Se actualiza solo al agregar usuarios o ventas.
- `python esquema.py` imprime el esquema en JSON (formato `lucid_create_erd`).
- Skill del proyecto: `.claude/skills/actualizar-lucid-erd` → con Claude Code y el MCP de Lucid redibuja el ERD en Lucid y guarda el enlace en `lucid_erd.json` (el botón Data lo muestra).

### Requisito para Lucid

Para usar la skill y abrir el diagrama debes **poder ingresar a Lucid con tu email** (cuenta en lucid.app) y tener el conector **Lucid** autorizado en Claude (claude.ai → Conectores). Sin esa cuenta/autorización la skill no puede crear ni actualizar el diagrama.

## Pagos Bitcoin (trazabilidad)

- Al elegir **Bitcoin** se consulta BTC/USD (Coinbase → Kraken validado) y se guarda una copia inmutable en `cotizacion_btc` con fuente, hora UTC y respuesta cruda. Si no hay precio válido, **la venta no se crea**. Ya no existe la tasa fija `BTC_USD_RATE`.
- Un pendiente se considera vencido pasados `BTC_QUOTE_TTL_MIN` min (15). Zona horaria de las ventas: `BTC_LOCAL_TZ` (America/El_Salvador).
- Skill de Claude Code: `.claude/skills/bitcoin-price-payment-auditor` (auditoría: `python3 .claude/skills/bitcoin-price-payment-auditor/scripts/audit_transactions.py`).
- Pruebas: `python3 -m unittest discover -s .claude/skills/bitcoin-price-payment-auditor/tests -v`
