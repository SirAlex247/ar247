"""Pruebas de la norma elegible (NSR-10 ↔ CCP-14) en pilotes y dados.

  - Pilote: tratamiento geotécnico ASD (Q_adm/FS) vs LRFD (R_r=φ·Q) y φ
    estructural por norma.
  - Dado: φ de cortante (0.75 vs 0.90), peralte de cortante dv y refuerzo
    mínimo por Mcr (CCP-14).
"""
from __future__ import annotations

import math

from retaining_wall.core.pilote import disenar_pilote_estructural
from retaining_wall.core.dado import disenar_dado


# --------------------------------------------------------------------------
# Pilotes
# --------------------------------------------------------------------------
_PIL = dict(P_servicio=1200, f_s=60, q_p=3000, D=0.5, fc=28, fy=420, cuantia=0.01)


def test_pilote_nsr10_qadm_fs():
    r = disenar_pilote_estructural(norma="NSR10", FS=2.5, **_PIL)
    g = r["geotecnia"]
    assert r["norma"] == "NSR10" and "NSR-10" in g["metodo"]
    assert math.isclose(g["Qadm_kN"], g["Qult_kN"] / 2.5, rel_tol=1e-3)
    assert "R_r_kN" not in g


def test_pilote_ccp14_resistencia_factorada():
    r = disenar_pilote_estructural(norma="CCP14", tipo_suelo="arena", factor_carga=1.6, **_PIL)
    g = r["geotecnia"]
    assert r["norma"] == "CCP14" and g["phi_fuste"] == 0.55 and g["phi_punta"] == 0.50
    esperado = g["phi_punta"] * g["Qpunta_kN"] + g["phi_fuste"] * g["Qfuste_kN"]
    assert math.isclose(g["R_r_kN"], esperado, rel_tol=1e-3)
    assert g["CDR"] is not None


def test_pilote_ccp14_arcilla_phi_menores():
    r = disenar_pilote_estructural(norma="CCP14", tipo_suelo="arcilla", **_PIL)
    assert r["geotecnia"]["phi_fuste"] == 0.45 and r["geotecnia"]["phi_punta"] == 0.40


def test_pilote_phi_estructural_por_norma():
    n = disenar_pilote_estructural(norma="NSR10", tipo_refuerzo="estribo", **_PIL)
    c = disenar_pilote_estructural(norma="CCP14", tipo_refuerzo="estribo", **_PIL)
    assert n["estructural"]["phi"] == 0.65     # ACI estribos
    assert c["estructural"]["phi"] == 0.75     # AASHTO axial


# --------------------------------------------------------------------------
# Dados
# --------------------------------------------------------------------------
_DADO = dict(n_pilotes=4, Dp=0.45, c1=0.5, c2=0.5, Pu=4000, s=1.35, fc=28,
             fy=420, capacidad_pilote=1200, h=0.90)   # h fijo → comparar φ/dv


def test_dado_phi_corte_por_norma():
    n = disenar_dado(norma="NSR10", **_DADO)
    c = disenar_dado(norma="CCP14", **_DADO)
    assert n["estructural"]["phi_corte"] == 0.75
    assert c["estructural"]["phi_corte"] == 0.90


def test_dado_ccp_peralte_cortante_dv():
    c = disenar_dado(norma="CCP14", **_DADO)
    e = c["estructural"]
    d, h = e["d_m"], e["h_m"]
    assert math.isclose(e["dv_m"], max(0.9 * d, 0.72 * h), rel_tol=1e-6)
    # NSR usa d (dv == d)
    n = disenar_dado(norma="NSR10", **_DADO)
    assert math.isclose(n["estructural"]["dv_m"], n["estructural"]["d_m"], rel_tol=1e-6)


def test_dado_punz_vc_cap_igual():
    # El tope de v_c en dos vías es 0.33·√f'c en ambas normas (área cuadrada).
    n = disenar_dado(norma="NSR10", **_DADO)
    c = disenar_dado(norma="CCP14", **_DADO)
    tope = round(0.33 * math.sqrt(28), 3)
    assert n["estructural"]["punz_columna"]["vc_MPa"] == tope
    assert c["estructural"]["punz_columna"]["vc_MPa"] == tope


def test_dado_ccp_min_reinf_por_mcr():
    # En CCP-14 el mínimo se calcula por Mcr (no por 0.0018·b·h).
    c = disenar_dado(norma="CCP14", **_DADO)
    n = disenar_dado(norma="NSR10", **_DADO)
    fx_c = c["estructural"]["flexion_x"]
    fx_n = n["estructural"]["flexion_x"]
    # los mínimos difieren entre normas (criterios distintos)
    assert fx_c["As_min_cm2"] != fx_n["As_min_cm2"]
    assert c["cumple"] and n["cumple"]


# --------------------------------------------------------------------------
# API
# --------------------------------------------------------------------------
def _client():
    try:
        import app as _appmod
    except ModuleNotFoundError:
        import os
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "python"))
        import app as _appmod
    return _appmod.app.test_client()


def test_api_pilote_diseno_norma_ccp14():
    r = _client().post("/api/pilote_diseno", json={
        "norma": "CCP14", "tipo_suelo": "arena", "P_servicio": 1200,
        "f_s": 60, "q_p": 3000, "D": 0.5, "fc": 28, "fy": 420, "factor_carga": 1.6,
    }).get_json()
    assert r["ok"] is True and r["norma"] == "CCP14"
    assert "R_r_kN" in r["geotecnia"]


def test_api_dado_norma_ccp14():
    r = _client().post("/api/dado", json={
        "norma": "CCP14", "n_pilotes": 4, "Dp": 0.45, "c1": 0.5, "c2": 0.5,
        "Pu": 4000, "s": 1.35, "fc": 28, "fy": 420, "capacidad_pilote": 1200,
    }).get_json()
    assert r["ok"] is True and r["norma"] == "CCP14"
    assert r["estructural"]["phi_corte"] == 0.90
