"""Pruebas del caisson / pila excavada de gran diámetro (NSR-10 y CCP-14).

Cubren capacidad axial (β/α + punta con campana), la verificación por norma
(FS de NSR-10 vs φ de CCP-14), el diseño estructural como columna y el
despachador de la API.
"""
from __future__ import annotations

import math

from retaining_wall.core.caisson import (
    alpha_pila,
    beta_pila,
    capacidad_axial_caisson,
    disenar_caisson,
)

PERFIL = [
    {"tipo": "arcilla", "espesor": 5.0, "cu": 55, "gamma": 18.0, "gamma_sat": 19.0},
    {"tipo": "arena", "espesor": 15.0, "phi": 36, "gamma": 19.0, "gamma_sat": 20.5},
]


# --------------------------------------------------------------------------
# Métodos de pila perforada
# --------------------------------------------------------------------------
def test_beta_pila_decrece_y_acota():
    assert beta_pila(0.0) == 1.2                       # tope superior
    assert beta_pila(2.0) > beta_pila(10.0)            # decrece con z
    assert beta_pila(60.0) == 0.25                     # tope inferior


def test_alpha_pila_rango():
    assert alpha_pila(30) == 0.55                      # c_u bajo
    assert alpha_pila(400) < 0.55                      # decrece con c_u alto
    assert alpha_pila(400) >= 0.45


# --------------------------------------------------------------------------
# Capacidad axial
# --------------------------------------------------------------------------
def test_capacidad_fuste_y_punta_positivos():
    cap = capacidad_axial_caisson(D=1.0, L=12.0, estratos=PERFIL, nivel_freatico=4.0)
    assert cap["Q_fuste_kN"] > 0 and cap["Q_punta_kN"] > 0
    assert math.isclose(cap["Q_ult_kN"], cap["Q_fuste_kN"] + cap["Q_punta_kN"], rel_tol=1e-6)
    assert cap["tipo_punta"] == "arena"                # el fondo cae en la arena


def test_campana_aumenta_punta_por_area():
    sin = capacidad_axial_caisson(D=1.0, L=12.0, estratos=PERFIL, nivel_freatico=4.0)
    con = capacidad_axial_caisson(D=1.0, L=12.0, estratos=PERFIL, nivel_freatico=4.0,
                                  D_campana=2.0, altura_campana=1.0)
    # q_p igual, área base ×4 → Q_punta ~ ×4
    assert con["A_base_m2"] > 3.9 * sin["A_base_m2"]
    assert con["Q_punta_kN"] > 3.5 * sin["Q_punta_kN"]


# --------------------------------------------------------------------------
# Verificación por norma
# --------------------------------------------------------------------------
def test_nsr10_qadm_es_qult_sobre_fs():
    r = disenar_caisson(D=1.2, L=14.0, estratos=PERFIL, P_servicio=2500,
                        norma="NSR10", nivel_freatico=4.0, FS=3.0)
    geo = r["geotecnico"]
    assert "NSR-10" in geo["metodo"]
    assert math.isclose(geo["Q_adm_kN"], geo["Q_ult_kN"] / 3.0, rel_tol=1e-3)
    assert geo["FS"] == 3.0


def test_ccp14_resistencia_factorada_por_estrato():
    r = disenar_caisson(D=1.2, L=14.0, estratos=PERFIL, P_servicio=2500,
                        norma="CCP14", nivel_freatico=4.0, factor_carga=1.6)
    geo = r["geotecnico"]
    assert "CCP-14" in geo["metodo"]
    # R_r con φ por estrato + φ de punta < Q_últ (los φ < 1)
    assert geo["R_r_kN"] < geo["Q_ult_kN"]
    assert math.isclose(geo["R_r_kN"], geo["R_fuste_kN"] + geo["R_punta_kN"], rel_tol=1e-6)
    assert geo["phi_punta"] == 0.50                    # punta en arena
    assert geo["Pu_demanda_kN"] > 0 and geo["CDR"] is not None


def test_norma_no_altera_capacidad_ultima():
    a = disenar_caisson(D=1.2, L=14.0, estratos=PERFIL, P_servicio=2500, norma="NSR10", nivel_freatico=4.0)
    b = disenar_caisson(D=1.2, L=14.0, estratos=PERFIL, P_servicio=2500, norma="CCP14", nivel_freatico=4.0)
    assert math.isclose(a["capacidad"]["Q_ult_kN"], b["capacidad"]["Q_ult_kN"], rel_tol=1e-9)


# --------------------------------------------------------------------------
# Estructural
# --------------------------------------------------------------------------
def test_estructural_phi_por_norma():
    base = dict(D=1.2, L=14.0, estratos=PERFIL, P_servicio=2500, nivel_freatico=4.0)
    # Estribos: NSR-10 φ=0.65 ; CCP-14 φ=0.75
    n = disenar_caisson(norma="NSR10", tipo_refuerzo="estribo", **base)["estructural"]
    c = disenar_caisson(norma="CCP14", tipo_refuerzo="estribo", **base)["estructural"]
    assert n["phi"] == 0.65 and c["phi"] == 0.75
    assert c["phiPn_kN"] > n["phiPn_kN"]               # mayor φ → mayor capacidad
    assert n["cumple"] and c["cumple"]


def test_auto_longitud_crece():
    r = disenar_caisson(D=1.2, L=0, L_auto=True, estratos=PERFIL, P_servicio=1500,
                        norma="NSR10", nivel_freatico=4.0, FS=3.0, L_max=30.0)
    assert r["geometria"]["L_m"] >= 3.0
    # con carga moderada debe encontrar una L que cumpla dentro del límite
    assert r["geotecnico"]["cumple"] or r["geometria"]["L_m"] >= 29.5


# --------------------------------------------------------------------------
# API
# --------------------------------------------------------------------------
def test_api_caisson_endpoint_ok():
    try:
        import app as _appmod
    except ModuleNotFoundError:
        import os
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "python"))
        import app as _appmod
    client = _appmod.app.test_client()
    payload = {"norma": "CCP14", "D": 1.2, "L": 14.0, "P_servicio": 2500,
               "nivel_freatico": 4.0, "factor_carga": 1.6, "fc": 28, "fy": 420,
               "D_campana": 2.4, "altura_campana": 1.2,
               "estratos": PERFIL}
    r = client.post("/api/caisson", json=payload).get_json()
    assert r["ok"] is True and r["tipo"] == "caisson" and r["norma"] == "CCP14"
    assert r["geotecnico"]["R_r_kN"] > 0
    assert "capacidad" in r and r["capacidad"]["Q_ult_kN"] > 0
