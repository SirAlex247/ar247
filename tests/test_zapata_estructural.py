"""Pruebas de las verificaciones estructurales nuevas de la zapata aislada:
transferencia de carga (aplastamiento + dowels), punzonamiento con momento
(cortante excéntrico γv), longitud de desarrollo y banda central."""
from __future__ import annotations

import math

from retaining_wall.core.zapata import disenar_zapata


def _z(**over):
    base = dict(c1=0.40, c2=0.40, P_servicio=800.0, q_adm=250.0,
                fc=21.0, fy=420.0, Df=1.5, factor_carga=1.5)
    base.update(over)
    return disenar_zapata(**base)


# --------------------------------------------------------------------------
# 1. Transferencia de carga (aplastamiento + dowels)
# --------------------------------------------------------------------------
def test_transferencia_presente_y_dowels_minimos():
    e = _z()["estructural"]
    t = e["transferencia"]
    assert "phiPn_kN" in t
    # Dowels: al menos 4 barras y As ≥ 0.005·A1
    assert t["n_dowels"] >= 4
    A1 = 0.40 * 0.40
    assert t["As_dowels_req_cm2"] >= 0.005 * A1 * 1e4 - 1e-6


def test_mayor_fc_columna_aumenta_aplastamiento():
    baja = _z(fc_columna=17.0)["estructural"]["transferencia"]
    alta = _z(fc_columna=35.0)["estructural"]["transferencia"]
    assert alta["phiPn_columna_kN"] > baja["phiPn_columna_kN"]


def test_sqrt_A2A1_acotado_a_2():
    t = _z()["estructural"]["transferencia"]
    assert t["sqrt_A2A1"] <= 2.0 + 1e-9


# --------------------------------------------------------------------------
# 2. Punzonamiento con transferencia de momento (γv)
# --------------------------------------------------------------------------
def test_momento_aumenta_el_cortante_de_punzonamiento():
    sin = _z(M_servicio=0.0, B=2.5, L=2.5, h=0.5)["estructural"]["punzonamiento"]
    con = _z(M_servicio=150.0, B=2.5, L=2.5, h=0.5)["estructural"]["punzonamiento"]
    assert con["vu_momento_kPa"] > 0
    assert con["vu_total_kPa"] > sin["vu_total_kPa"]
    assert 0.0 < con["gamma_v_x"] < 1.0


def test_auto_espesor_satisface_punzonamiento_con_momento():
    # La zapata auto-dimensionada debe cumplir su propio chequeo con momento.
    e = _z(M_servicio=120.0, relacion_LB=1.5)["estructural"]
    assert e["punzonamiento"]["cumple_momento"]


# --------------------------------------------------------------------------
# 3. Longitud de desarrollo del refuerzo
# --------------------------------------------------------------------------
def test_ld_presente_y_crece_con_el_diametro():
    fino = _z(db=0.0127, B=2.6, L=2.6, h=0.5)["estructural"]["flexion_L"]["desarrollo"]
    grueso = _z(db=0.0254, B=2.6, L=2.6, h=0.5)["estructural"]["flexion_L"]["desarrollo"]
    assert grueso["ld_m"] > fino["ld_m"]
    assert "cumple" in fino


# --------------------------------------------------------------------------
# 4. Distribución en banda central (zapata rectangular)
# --------------------------------------------------------------------------
def test_banda_central_en_rectangular_y_no_en_cuadrada():
    rect = _z(relacion_LB=2.0, M_servicio=0.0)["estructural"]
    banda = rect["flexion_L"].get("banda_central") or rect["flexion_B"].get("banda_central")
    assert banda is not None
    # γs = 2/(β+1) (gamma_s viene redondeado a 3 decimales)
    assert math.isclose(banda["gamma_s"], 2.0 / (banda["beta"] + 1.0), abs_tol=1e-3)
    assert banda["n_banda"] + banda["n_fuera"] > 0

    cuad = _z(relacion_LB=1.0)["estructural"]
    assert cuad["flexion_L"].get("banda_central") is None
    assert cuad["flexion_B"].get("banda_central") is None


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


def test_api_zapata_incluye_verificaciones_estructurales():
    cl = _client()
    r = cl.post("/api/zapata", json=dict(
        tipo="rectangular", c1=0.40, c2=0.40, P_servicio=800.0, M_servicio=120.0,
        q_adm=250.0, fc=21.0, fy=420.0, relacion_LB=1.5, fc_columna=28.0)).get_json()
    e = r["estructural"]
    assert "transferencia" in e
    assert "cumple_transferencia" in e
    assert e["punzonamiento"].get("cumple_momento") is not None
    assert e["flexion_L"]["desarrollo"]["ld_m"] > 0


# --------------------------------------------------------------------------
# B. Control de fisuración y cuantía máxima
# --------------------------------------------------------------------------
def test_fisuracion_y_cuantia_presentes():
    fL = _z()["estructural"]["flexion_L"]
    assert "fisuracion" in fL and "cuantia" in fL
    # tras la autocorrección, la separación cumple el máximo
    assert fL["fisuracion"]["cumple"]
    assert fL["sep_cm"] / 100.0 <= fL["fisuracion"]["sep_max_m"] + 1e-6


def test_cuantia_no_supera_la_maxima_en_caso_normal():
    c = _z()["estructural"]["flexion_L"]["cuantia"]
    assert 0 < c["rho"] <= c["rho_max"]


def test_fisuracion_agrega_barras_si_hace_falta():
    # Sección ancha con acero mínimo: la separación podría exceder el máximo y
    # debe autocorregirse agregando barras (siempre cumple al final).
    e = _z(B=3.0, L=3.0, h=0.35)["estructural"]
    assert e["flexion_L"]["fisuracion"]["cumple"]


# --------------------------------------------------------------------------
# A. Extensión a combinada y triangular
# --------------------------------------------------------------------------
def test_combinada_incluye_transferencia_y_punz_momento():
    from retaining_wall.core.zapatas_tipos import disenar_zapata_tipo
    r = disenar_zapata_tipo("combinada", dict(
        c1a=0.4, c2a=0.4, P1_servicio=600, c1b=0.4, c2b=0.4, P2_servicio=800,
        separacion=4.5, q_adm=250, M1_servicio=80, fc_columna=28))
    e = r["estructural"]
    assert "transferencia_col1" in e and "transferencia_col2" in e
    assert e["punzonamiento_col1"].get("cumple_momento") is not None
    assert e["flexion_transversal_col1"]["desarrollo"]["ld_m"] > 0
    assert "cuantia" in e["flexion_long_inferior"]


def test_triangular_incluye_transferencia_y_punz_momento():
    from retaining_wall.core.zapatas_tipos import disenar_zapata_tipo
    r = disenar_zapata_tipo("triangular", dict(
        c1=0.4, c2=0.4, P_servicio=500, q_adm=250, M_servicio=40, fc_columna=28))
    e = r["estructural"]
    assert "transferencia" in e
    assert e["punzonamiento"].get("cumple_momento") is not None
    assert "cuantia" in e["flexion"] and "fisuracion" in e["flexion"]
