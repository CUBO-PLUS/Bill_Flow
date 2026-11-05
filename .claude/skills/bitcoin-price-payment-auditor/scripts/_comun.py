"""Ruta al proyecto para importar precios_btc.py (backend) desde las herramientas de la skill."""
import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[4]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))
DB_DEFECTO = os.environ.get("DB_PATH", str(RAIZ / "restaurante.db"))
