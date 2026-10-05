"""Pruebas del análisis avanzado del pilote: solver p-y (diferencias finitas),
pandeo de Davisson y fricción negativa (downdrag)."""
from __future__ import annotations

import math

from retaining_wall.core.pilote_py import analisis_py
from retaining_wall.core.pilote_flexocompresion import (
    carga_lateral, friccion_negativa, pandeo_davisson)


def _client():
    try:
        import app as _appmod
    except ModuleNotFoundError:
        import os
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "python"))
        import app as _appmod
    return _appmod.app.test_client()


def _EI(D=0.5, fc=28):
    Ec = 4700.0 * math.sqrt(fc) * 1000.0
    return 0.5 * Ec * math.pi * D ** 4 / 64.0


# --------------------------------------------------------------------------
# 1. Solver p-y
# --------------------------------------------------------------------------
def test_py_perfiles_consistentes():
    r = analisis_py(EI=_EI(), L=15, D=0.5, H=120, tipo="arena",
                    gamma=9.0, phi=32, nh=6000, n_nodos=60)
    assert r["aplica"]
    n = len(r["z"])
    assert len(r["M_kNm"]) == n and len(r["V_kN"]) == n and len(r["y_mm"]) == n
    # Cabeza libre: momento nulo en la cabeza; cortante en la cabeza ≈ H.
    assert abs(r["M_kNm"][0]) < 1.0
    assert abs(abs(r["V_kN"][0]) - 120) < 5.0
    # El momento máximo es positivo y ocurre bajo la superficie.
    assert r["Mmax_kNm"] > 0 and r["z_Mmax_m"] > 0
    # Deflexión en la cabeza positiva (normalizada a la dirección de H).
    assert r["y0_mm"] > 0


def test_py_no_lineal_mayor_que_broms():
    py = analisis_py(EI=_EI(), L=15, D=0.5, H=150, tipo="arena",
                     gamma=9.0, phi=32, nh=6000)
    br = carga_lateral(H=150, D=0.5, fc=28, tipo="nh", nh=6000)
    # el análisis no lineal (suelo que plastifica) da mayor momento que el
    # elástico lineal de Broms
    assert py["Mmax_kNm"] > br["Mmax_kNm"]


def test_py_no_aplica_sin_carga():
    assert not analisis_py(EI=_EI(), L=15, D=0.5, H=0).get("aplica")


def test_py_longitud_refuerzo_dentro_del_pilote():
    r = analisis_py(EI=_EI(), L=15, D=0.5, H=120, tipo="arcilla",
                    gamma=8.0, cu=50, eps50=0.01)
    assert 0 < r["z_refuerzo_m"] <= 15


# --------------------------------------------------------------------------
# 2. Pandeo (Davisson)
# --------------------------------------------------------------------------
def test_davisson_pcr_y_fijacion():
    d = pandeo_davisson(Pu=1000, EI=_EI(), Lu=4.0, tipo="nh", nh=6000)
    assert d["aplica"] and d["z_fijacion_m"] > 0 and d["Pcr_kN"] > 0
    # Más longitud libre → menor Pcr.
    d2 = pandeo_davisson(Pu=1000, EI=_EI(), Lu=8.0, tipo="nh", nh=6000)
    assert d2["Pcr_kN"] < d["Pcr_kN"]


def test_davisson_no_aplica_sin_longitud_libre():
    assert not pandeo_davisson(Pu=1000, EI=_EI(), Lu=0.0, nh=6000)["aplica"]


# --------------------------------------------------------------------------
# 3. Fricción negativa (downdrag)
# --------------------------------------------------------------------------
def test_downdrag_formula():
    dd = friccion_negativa(D=0.5, fs_neg=25, L_downdrag=6, P_servicio=1000)
    assert math.isclose(dd["Qn_kN"], 25 * math.pi * 0.5 * 6, abs_tol=0.1)
    assert dd["P_con_downdrag_kN"] > 1000
    assert not friccion_negativa(D=0.5, fs_neg=0, L_downdrag=6)["aplica"]


# --------------------------------------------------------------------------
# Integración con la API
# --------------------------------------------------------------------------
def test_api_pilote_incluye_analisis_avanzado():
    cl = _client()
    r = cl.post("/api/pilote_diseno", json=dict(
        P_servicio=1600, f_s=60, q_p=2500, fc=28, fy=420, cuantia=0.01,
        H_servicio=150, tipo_reaccion="nh", nh_suelo=6000, gamma_lat=9.0,
        phi_lat=32, Lu_libre=3.0, fs_negativa=25, L_downdrag=6)).get_json()
    e = r["estructural"]
    assert e["analisis_py"]["aplica"]
    assert len(e["analisis_py"]["z"]) > 20
    assert e["pandeo_davisson"]["aplica"]
    assert e["downdrag"]["aplica"] and e["downdrag"]["Qn_kN"] > 0
    # con H el momento de flexo-compresión sale del análisis p-y
    assert e["flexocompresion"]["Mu_kNm"] > 0
