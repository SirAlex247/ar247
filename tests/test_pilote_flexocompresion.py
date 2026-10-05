"""Pruebas de flexo-compresión (P-M), esbeltez, tracción y confinamiento del
pilote circular."""
from __future__ import annotations

import math

from retaining_wall.core.pilote_flexocompresion import (
    amplificacion_momento, capacidad_traccion, carga_lateral,
    confinamiento_sismico, cortante_circular, diagrama_interaccion,
    distribucion_grupo, layout_grupo, verificar_flexocompresion)
from retaining_wall.core.pilote import disenar_pilote_estructural


def _client():
    try:
        import app as _appmod
    except ModuleNotFoundError:
        import os
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "python"))
        import app as _appmod
    return _appmod.app.test_client()


def _diag():
    return diagrama_interaccion(D=0.5, fc=28, fy=420, n_barras=8,
                                db_long=19.05, recubrimiento=0.075,
                                db_trans=9.53, espiral=True)


# --------------------------------------------------------------------------
# 1. Diagrama de interacción
# --------------------------------------------------------------------------
def test_diagrama_tiene_forma_de_interaccion():
    d = _diag()
    assert d["phiPn_max_kN"] > 0
    # φTn = 0.9·fy·Ast
    Ast = d["Ast_cm2"] / 1e4
    assert math.isclose(d["phiTn_kN"], 0.9 * 420 * 1000 * Ast, rel_tol=1e-3)
    # El φMn máximo (balanceado) es positivo y ocurre a compresión intermedia.
    mmax = max(p["phiMn_kNm"] for p in d["puntos"])
    assert mmax > 0
    # La compresión pura da φMn ~ 0.
    assert min(abs(p["phiMn_kNm"]) for p in d["puntos"]) < mmax * 0.2


def test_verificar_dentro_y_fuera():
    d = _diag()
    dentro = verificar_flexocompresion(d, 1500, 50)
    fuera = verificar_flexocompresion(d, 500, 400)
    assert dentro["cumple"] and dentro["ratio_interaccion"] <= 1.0
    assert (not fuera["cumple"]) and fuera["ratio_interaccion"] > 1.0


def test_mayor_momento_sube_la_relacion():
    d = _diag()
    r1 = verificar_flexocompresion(d, 1000, 40)["ratio_interaccion"]
    r2 = verificar_flexocompresion(d, 1000, 120)["ratio_interaccion"]
    assert r2 > r1


# --------------------------------------------------------------------------
# 2. Esbeltez
# --------------------------------------------------------------------------
def test_pilote_corto_no_amplifica():
    r = amplificacion_momento(Pu=1500, M2=80, D=0.5, fc=28, Lu=0.0)
    assert not r["es_esbelto"] and r["delta_ns"] == 1.0 and r["Mc_kNm"] == 80


def test_pilote_esbelto_amplifica_momento():
    r = amplificacion_momento(Pu=1200, M2=80, D=0.4, fc=28, Lu=6.0)
    assert r["es_esbelto"] and r["delta_ns"] > 1.0 and r["Mc_kNm"] > 80


# --------------------------------------------------------------------------
# 3. Tracción
# --------------------------------------------------------------------------
def test_capacidad_traccion():
    t = capacidad_traccion(Ast=20e-4, fy=420, Tu=300)
    assert math.isclose(t["phiTn_kN"], 0.9 * 420 * 1000 * 20e-4, rel_tol=1e-6)
    assert t["aplica"] and t["cumple"]
    assert not capacidad_traccion(Ast=20e-4, fy=420, Tu=0)["aplica"]


# --------------------------------------------------------------------------
# 4. Confinamiento sísmico
# --------------------------------------------------------------------------
def test_confinamiento_espiral_usa_maximo():
    c = confinamiento_sismico(D=0.5, fc=28, fy=420, db_long=19.05,
                              recubrimiento=0.075, db_trans=9.53,
                              espiral=True, Lu=6.0)
    assert c["longitud_confinamiento_m"] >= 0.5
    assert c["rho_s_confinamiento"] >= 0.12 * (28 / 420) - 1e-6


# --------------------------------------------------------------------------
# Integración con el diseño y la API
# --------------------------------------------------------------------------
def test_auto_diametro_considera_flexocompresion():
    sin = disenar_pilote_estructural(P_servicio=1500, f_s=60, q_p=2500,
                                     fc=28, fy=420, cuantia=0.01)
    con = disenar_pilote_estructural(P_servicio=1500, f_s=60, q_p=2500,
                                     fc=28, fy=420, cuantia=0.01,
                                     M_servicio=60, Lu_libre=6.0)
    # con momento + longitud libre el diámetro crece
    assert con["diseno"]["D_m"] >= sin["diseno"]["D_m"]
    assert con["estructural"]["flexocompresion"]["cumple"]


def test_api_pilote_diseno_incluye_flexocompresion():
    cl = _client()
    r = cl.post("/api/pilote_diseno", json=dict(
        P_servicio=1500, f_s=60, q_p=2500, fc=28, fy=420, cuantia=0.01,
        M_servicio=60, T_servicio=100, Lu_libre=6.0)).get_json()
    e = r["estructural"]
    assert "flexocompresion" in e and "esbeltez" in e
    assert "traccion" in e and "confinamiento_sismico" in e
    assert len(e["diagrama_interaccion"]["puntos"]) > 10


# --------------------------------------------------------------------------
# Grupo (cabezal rígido)
# --------------------------------------------------------------------------
def test_layout_grupo_centrado():
    co = layout_grupo(4, 1.5)
    assert len(co) == 4
    assert abs(sum(x for x, _ in co)) < 1e-9   # centrado en x
    assert abs(sum(y for _, y in co)) < 1e-9   # centrado en y


def test_distribucion_grupo_pmax_pmin_y_traccion():
    co = layout_grupo(4, 1.5)
    d = distribucion_grupo(P=1600, Mx=200, My=0, coords=co)
    assert d["P_max_kN"] > d["P_min_kN"]
    # con un momento grande aparece tracción (P_min < 0)
    d2 = distribucion_grupo(P=200, Mx=800, My=0, coords=co)
    assert d2["hay_traccion"]


# --------------------------------------------------------------------------
# Carga lateral (Broms / longitud característica)
# --------------------------------------------------------------------------
def test_carga_lateral_arena_mmax_escala_con_H():
    l1 = carga_lateral(H=100, D=0.5, fc=28, tipo="nh", nh=6000)
    l2 = carga_lateral(H=200, D=0.5, fc=28, tipo="nh", nh=6000)
    assert l2["Mmax_kNm"] > l1["Mmax_kNm"]
    assert l1["long_caracteristica_m"] > 0
    assert not carga_lateral(H=0, D=0.5, fc=28)["aplica"]


def test_carga_lateral_arcilla_distinta_de_arena():
    la = carga_lateral(H=150, D=0.5, fc=28, tipo="nh", nh=6000)
    lc = carga_lateral(H=150, D=0.5, fc=28, tipo="k", k=15000)
    assert la["long_caracteristica_m"] != lc["long_caracteristica_m"]


# --------------------------------------------------------------------------
# Cortante de la sección circular
# --------------------------------------------------------------------------
def test_cortante_circular_refuerzo_aumenta_capacidad():
    sin = cortante_circular(Vu=80, D=0.5, fc=28, fy=420, db_trans=9.53,
                            recubrimiento=0.075, espiral=True, s_trans=0.0)
    con = cortante_circular(Vu=80, D=0.5, fc=28, fy=420, db_trans=9.53,
                            recubrimiento=0.075, espiral=True, s_trans=0.10)
    assert con["phiVn_kN"] > sin["phiVn_kN"]


def test_api_pilote_grupo_lateral_cortante():
    cl = _client()
    r = cl.post("/api/pilote_diseno", json=dict(
        P_servicio=1600, f_s=60, q_p=2500, fc=28, fy=420, cuantia=0.01,
        Mx_servicio=200, My_servicio=80, H_servicio=120, s_grupo=1.5,
        tipo_reaccion="nh", nh_suelo=6000)).get_json()
    e = r["estructural"]
    assert "grupo" in e and "carga_lateral" in e and "cortante" in e
    assert e["carga_lateral"]["aplica"]
    assert e["cortante"]["Vu_kN"] > 0
    # el momento de flexo-compresión viene de la carga lateral
    assert e["flexocompresion"]["Mu_kNm"] > 0
