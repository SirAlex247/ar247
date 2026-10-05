"""Pruebas de las verificaciones estructurales avanzadas del caisson / pila
excavada: flexocompresión (diagrama P-M), análisis lateral no lineal p-y,
amplificación de momento por esbeltez, cortante en sección circular,
confinamiento sísmico y pandeo de Davisson.  Todo es diseño ESTRUCTURAL
(hormigón/acero); la capacidad geotécnica del suelo sigue siendo input."""
from __future__ import annotations

from retaining_wall.core.caisson import disenar_caisson


_SUELO = [{"tipo": "arcilla", "espesor": 8, "cu": 75, "gamma": 18},
          {"tipo": "arena", "espesor": 22, "phi": 34, "gamma": 19}]


def _d(**over):
    base = dict(D=1.2, L=18, estratos=_SUELO, P_servicio=3000, norma="NSR10",
                cuantia=0.015)
    base.update(over)
    return disenar_caisson(**base)


def _client():
    try:
        import app as _appmod
    except ModuleNotFoundError:
        import os
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "python"))
        import app as _appmod
    return _appmod.app.test_client()


# --------------------------------------------------------------------------
# 1. Flexocompresión (diagrama P-M)
# --------------------------------------------------------------------------
def test_diagrama_interaccion_presente():
    e = _d()["estructural"]
    diag = e["diagrama_interaccion"]
    assert diag["puntos"] and diag["phiPn_max_kN"] > 0
    assert "flexocompresion" in e


def test_axial_puro_sin_momento_cumple_flexo():
    # Sin momento ni lateral, el punto (Pu, 0) cae dentro del diagrama.
    e = _d(Pu=3500)["estructural"]
    assert e["flexocompresion"]["cumple"]
    assert e["Mu_diseno_kNm"] == 0.0


def test_momento_reduce_margen_flexocompresion():
    sin = _d(Pu=4000, Mu=0)["estructural"]["flexocompresion"]
    con = _d(Pu=4000, Mu=500)["estructural"]["flexocompresion"]
    assert con["ratio_interaccion"] > sin["ratio_interaccion"]


# --------------------------------------------------------------------------
# 2. Análisis lateral p-y
# --------------------------------------------------------------------------
def test_lateral_py_se_activa_con_H():
    e = _d(Pu=4000, Hu=300, Mu=100)["estructural"]
    py = e["analisis_py"]
    assert py.get("aplica")
    assert py["Mmax_kNm"] >= 100.0          # al menos el momento aplicado en cabeza
    assert py["y0_mm"] > 0
    # El momento de diseño toma el máximo del análisis no lineal.
    assert e["Mu_diseno_kNm"] >= py["Mmax_kNm"] - 1e-6


def test_sin_carga_lateral_no_hay_py():
    e = _d()["estructural"]
    assert e["analisis_py"].get("aplica") is False


# --------------------------------------------------------------------------
# 3. Esbeltez (amplificación de momento)
# --------------------------------------------------------------------------
def test_esbeltez_amplifica_con_tramo_libre():
    # Fuste delgado y tramo libre largo → esbelto; δ_ns > 1.
    e = _d(D=0.6, L=12, estratos=[{"tipo": "arena", "espesor": 30, "phi": 36, "gamma": 20}],
           P_servicio=600, Pu=1200, Mu=80, Lu_libre=8.0, cuantia=0.02)["estructural"]
    assert e["esbeltez"]["es_esbelto"]
    assert e["esbeltez"]["delta_ns"] > 1.0


def test_sin_tramo_libre_no_es_esbelto():
    e = _d(Pu=3500, Mu=100)["estructural"]
    assert e["esbeltez"]["es_esbelto"] is False
    assert e["esbeltez"]["delta_ns"] == 1.0


# --------------------------------------------------------------------------
# 4. Cortante circular
# --------------------------------------------------------------------------
def test_cortante_circular_presente():
    e = _d(Pu=4000, Hu=250)["estructural"]
    cv = e["cortante"]
    assert cv["d_m"] > 0 and cv["phiVn_kN"] > 0
    assert e["Vu_diseno_kN"] > 0


# --------------------------------------------------------------------------
# 5. Confinamiento sísmico y pandeo Davisson
# --------------------------------------------------------------------------
def test_confinamiento_presente():
    cf = _d()["estructural"]["confinamiento"]
    assert cf["longitud_confinamiento_m"] > 0


def test_davisson_falla_en_fuste_esbelto_cargado():
    e = _d(D=0.6, L=12, estratos=[{"tipo": "arena", "espesor": 30, "phi": 36, "gamma": 20}],
           P_servicio=600, Pu=1500, Lu_libre=8.0, nh_suelo=8000,
           tipo_reaccion="nh", cuantia=0.02)["estructural"]
    assert e["davisson"]["aplica"]
    assert not e["davisson"]["cumple"]


# --------------------------------------------------------------------------
# Retrocompatibilidad: el caso axial clásico mantiene sus claves
# --------------------------------------------------------------------------
def test_retrocompatibilidad_axial():
    r = _d(Pu=3500)
    e = r["estructural"]
    assert "phiPn_kN" in e and "n_barras" in e and "transversal" in e


# --------------------------------------------------------------------------
# API
# --------------------------------------------------------------------------
def test_api_caisson_incluye_flexocompresion():
    cl = _client()
    r = cl.post("/api/caisson", json=dict(
        D=1.2, L=18, P_servicio=3000, Pu=4000, Mu=300, Hu=250,
        norma="NSR10", cuantia=0.015,
        estratos=[{"tipo": "arcilla", "espesor": 8, "cu": 75, "gamma": 18},
                  {"tipo": "arena", "espesor": 22, "phi": 34, "gamma": 19}],
    )).get_json()
    assert r["ok"]
    e = r["estructural"]
    assert "flexocompresion" in e and "cortante" in e and "analisis_py" in e
