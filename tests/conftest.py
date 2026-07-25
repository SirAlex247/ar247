"""Configuración compartida para la suite de pruebas de CimX.

- Añade ``python/`` al ``sys.path`` para poder importar ``app`` y el paquete
  ``retaining_wall`` sin instalar nada.
- Fuerza el backend ``Agg`` de matplotlib para que la generación de figuras
  (dibujo del muro, diagramas) funcione sin entorno gráfico.

Funciona tanto bajo pytest (autodescubre este archivo) como con el runner
autónomo ``run_all.py`` (que lo importa explícitamente).
"""
from __future__ import annotations

import os
import sys

# ── Backend no interactivo de matplotlib (antes de importar pyplot) ──────
os.environ.setdefault("MPLBACKEND", "Agg")
try:
    import matplotlib
    matplotlib.use("Agg")
except Exception:
    pass

# ── Hacer importable el backend Python de la app ─────────────────────────
_PYTHON_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "python")
)
if _PYTHON_DIR not in sys.path:
    sys.path.insert(0, _PYTHON_DIR)
