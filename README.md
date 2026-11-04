# Demo: restaurante, ventas y DTE (Flask + SQLite)

Usa el esquema de `restaurante_db.sql` (platillos, ventas, detalle, tipo de documento, forma de pago, estado del DTE, roles y empleados).

- **Registro**: usuario y contraseña (se guardan en la tabla `empleado`). Se elige el rol: *Asistente de caja* o *Contador*.
- **Asistente de caja**: registra ventas (platillo, cantidad, tipo de documento, forma de pago) y ve solo las suyas.
- **Contador**: ve empleados y todas las ventas, y avanza el estado del DTE (paso 1 a 5).

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

- `PERMITIR_REGISTRO_ADMIN = True` deja elegir "Contador" en el registro (para la demo).
- Pon `False` si quieres que el registro solo cree Asistentes de caja.

Los datos se guardan en `restaurante.db` (SQLite), que se crea solo desde `restaurante_db.sql` la primera vez. Para reiniciar la demo, borra ese archivo.

## Nota de seguridad

Las contraseñas se guardan como hash (scrypt con sal), no en texto plano. Esta demo no tiene HTTPS ni protección CSRF, así que no la publiques en internet tal cual.
