"""Pruebas de las verificaciones estructurales nuevas de la placa de
cimentación: punzonamiento con momento (γv), transferencia de carga
(aplastamiento + dowels), longitud de desarrollo y control de fisuración /
cuantía en las franjas."""
from __future__ import annotations

from retaining_wall.core.placa import disenar_placa


def _client():
    try:
        import app as _appmod
    except ModuleNotFoundError:
        import os
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "python"))
        import app as _appmod
    return _appmod.app.test_client()


def _cols(mx=0.0):
    return [
        {"x": 0, "y": 0, "P": 400, "c1": 0.5, "c2": 0.5, "Mx": mx},
        {"x": 5, "y": 0, "P": 500, "c1": 0.5, "c2": 0.5},
        {"x": 0, "y": 5, "P": 500, "c1": 0.5, "c2": 0.5},
        {"x": 5, "y": 5, "P": 600, "c1": 0.5, "c2": 0.5, "Mx": mx},
    ]


# --------------------------------------------------------------------------
# Punzonamiento con transferencia de momento
# --------------------------------------------------------------------------
def test_punzonamiento_con_momento_presente():
    r = disenar_placa(columnas=_cols(mx=60), q_adm=250)
    pc = r["estructural"]["punz_critico"]
    assert "cumple_momento" in pc and "vu_total_kPa" in pc
    assert pc["vu_momento_kPa"] > 0
    assert 0.0 < pc["gamma_v_x"] < 1.0


def test_momento_aumenta_el_cortante_de_punzonamiento():
    sin = disenar_placa(columnas=_cols(mx=0), q_adm=250, h=0.6)
    con = disenar_placa(columnas=_cols(mx=120), q_adm=250, h=0.6)
    # localiza la columna con momento (col 1) en ambas
    p_sin = sin["estructural"]["punzonamiento"][0]
    p_con = con["estructural"]["punzonamiento"][0]
    assert p_con["vu_total_kPa"] > p_sin["vu_total_kPa"]


def test_auto_espesor_cumple_punzonamiento_con_momento():
    r = disenar_placa(columnas=_cols(mx=80), q_adm=250)
    for p in r["estructural"]["punzonamiento"]:
        assert p["cumple_momento"]


# --------------------------------------------------------------------------
# Transferencia de carga (aplastamiento + dowels)
# --------------------------------------------------------------------------
def test_transferencia_por_columna():
    r = disenar_placa(columnas=_cols(), q_adm=250, fc_columna=28)
    e = r["estructural"]
    assert "transferencia" in e and len(e["transferencia"]) == 4
    tc = e["transf_critica"]
    assert tc["n_dowels"] >= 4 and tc["sqrt_A2A1"] <= 2.0 + 1e-9
    assert "cumple_transferencia" in e


# --------------------------------------------------------------------------
# Longitud de desarrollo + fisuración + cuantía en las franjas
# --------------------------------------------------------------------------
def test_franjas_incluyen_ld_fisuracion_cuantia():
    r = disenar_placa(columnas=_cols(), q_adm=250)
    ai = r["estructural"]["franja_x"]["acero_inferior"]
    assert "desarrollo" in ai and ai["desarrollo"]["ld_m"] > 0
    assert "fisuracion" in ai and "cuantia" in ai
    assert ai["fisuracion"]["cumple"]  # se autocorrige la separación


# --------------------------------------------------------------------------
# API
# --------------------------------------------------------------------------
def test_api_placa_incluye_verificaciones_estructurales():
    cl = _client()
    r = cl.post("/api/placa", json=dict(
        columnas=_cols(mx=60), q_adm=250, fc_columna=28)).get_json()
    assert r["ok"]
    e = r["estructural"]
    assert "transferencia" in e and "cumple_transferencia" in e
    assert e["punz_critico"].get("cumple_momento") is not None
