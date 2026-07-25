"""Caracterización de los módulos pilote / zapata / dado (camino real de la app).

Verifican (a) que cada endpoint corre end-to-end y devuelve la estructura
esperada, (b) identidades físicas comprobables, y (c) valores congelados que
detectan regresiones. Baseline capturado con ``tests/_capture.py``.
"""
try:
    import app
except ModuleNotFoundError:
    import os, sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "python"))
    import app

try:
    from tests.fixtures import PILOTE, ZAPATA, DADO
except ModuleNotFoundError:
    from fixtures import PILOTE, ZAPATA, DADO


def _aprox(a, b, tol):
    assert abs(a - b) <= tol, f"esperado {b} ± {tol}, obtenido {a}"


# ═══════════════════════════ PILOTE ══════════════════════════════════════
def test_pilote_estructura_y_capacidad():
    r = app.construir_pilote_desde_datos(PILOTE)
    assert {"geometria", "capacidad", "estructural"} <= set(r.keys())
    cap = r["capacidad"]
    _aprox(cap["Q_punta_kN"], 141.4, 0.5)
    _aprox(cap["Q_fuste_kN"], 454.7, 0.5)
    _aprox(cap["Q_limite_kN"], 596.0, 1.0)
    _aprox(cap["Q_adm_kN"], 198.7, 0.5)


def test_pilote_identidad_Q_admisible():
    """Q_adm = Q_límite / FS (y Q_límite = Q_punta + Q_fuste)."""
    cap = app.construir_pilote_desde_datos(PILOTE)["capacidad"]
    _aprox(cap["Q_limite_kN"], cap["Q_punta_kN"] + cap["Q_fuste_kN"], 1.0)
    _aprox(cap["Q_adm_kN"], cap["Q_limite_kN"] / cap["FS"], 0.5)


# ═══════════════════════════ ZAPATA ══════════════════════════════════════
def test_zapata_estructura_y_geometria():
    r = app.construir_zapata_desde_datos(ZAPATA)
    assert {"geometria", "geotecnico", "estructural"} <= set(r.keys())
    g = r["geometria"]
    _aprox(g["B_m"], 1.9, 0.01)
    _aprox(g["L_m"], 1.9, 0.01)
    _aprox(g["area_m2"], g["B_m"] * g["L_m"], 1e-6)   # identidad de área


def test_zapata_peralte_util_menor_que_altura():
    g = app.construir_zapata_desde_datos(ZAPATA)["geometria"]
    assert 0.0 < g["d_m"] < g["h_m"]                  # d = h - recubrimiento - db/2


# ═══════════════════════════ DADO ════════════════════════════════════════
def test_dado_estructura_y_cumple():
    r = app.construir_dado_desde_datos(DADO)
    assert {"geometria", "cargas", "estructural", "cumple"} <= set(r.keys())
    assert r["cumple"] is True
    g = r["geometria"]
    _aprox(g["Bx_m"], 2.05, 0.01)
    _aprox(g["Ly_m"], 2.05, 0.01)
    _aprox(g["d_m"], 0.806, 0.005)


def test_dado_area_consistente():
    g = app.construir_dado_desde_datos(DADO)["geometria"]
    _aprox(g["area_m2"], g["Bx_m"] * g["Ly_m"], 1e-3)
