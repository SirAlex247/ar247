"""Pruebas de las verificaciones estructurales nuevas del dado/cabezal:
punzonamiento de la columna con momento (γv), transferencia de carga
(aplastamiento + dowels), anclaje del tensor sobre el pilote y control de
fisuración / cuantía en la flexión."""
from __future__ import annotations

from retaining_wall.core.dado import disenar_dado


def _client():
    try:
        import app as _appmod
    except ModuleNotFoundError:
        import os
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "python"))
        import app as _appmod
    return _appmod.app.test_client()


def _d(**over):
    base = dict(n_pilotes=4, Dp=0.45, c1=0.5, c2=0.5, Pu=2000,
                capacidad_pilote=800, fc=28)
    base.update(over)
    return disenar_dado(**base)


# --------------------------------------------------------------------------
# 1. Punzonamiento de la columna con momento
# --------------------------------------------------------------------------
def test_punzonamiento_columna_con_momento():
    pc = _d(Mux=150)["estructural"]["punz_columna"]
    assert "cumple_momento" in pc and pc["vu_momento_kPa"] > 0
    assert 0.0 < pc["gamma_v_x"] < 1.0


def test_momento_aumenta_el_cortante_de_punzonamiento():
    sin = _d(Mux=0, h=0.8)["estructural"]["punz_columna"]
    con = _d(Mux=250, h=0.8)["estructural"]["punz_columna"]
    assert con["vu_total_kPa"] > sin["vu_total_kPa"]


def test_auto_espesor_cumple_punz_con_momento():
    pc = _d(Mux=150)["estructural"]["punz_columna"]
    assert pc["cumple_momento"]


# --------------------------------------------------------------------------
# 2. Anclaje del tensor + 4. fisuración/cuantía
# --------------------------------------------------------------------------
def test_anclaje_tensor_presente():
    an = _d()["estructural"]["anclaje_tensor"]
    assert an["ld_m"] > 0 and an["disp_x_m"] >= 0
    assert "requiere_gancho" in an


def test_flexion_incluye_fisuracion_y_cuantia():
    fx = _d()["estructural"]["flexion_x"]
    assert "fisuracion" in fx and "cuantia" in fx
    assert fx["fisuracion"]["cumple"]
    assert 0 < fx["cuantia"]["rho"] <= fx["cuantia"]["rho_max"]


# --------------------------------------------------------------------------
# 3. Transferencia de carga
# --------------------------------------------------------------------------
def test_transferencia_presente():
    e = _d()["estructural"]
    t = e["transferencia"]
    assert t["n_dowels"] >= 4 and t["sqrt_A2A1"] <= 2.0 + 1e-9
    assert "cumple_transferencia" in e


def test_exceso_aplastamiento_lo_toman_dowels():
    # Carga alta: el aplastamiento se excede pero los dowels lo absorben y el
    # diseño sigue siendo válido si los dowels se desarrollan.
    r = _d(Pu=4500, c1=0.4, c2=0.4, capacidad_pilote=1400)
    t = r["estructural"]["transferencia"]
    assert not t["cumple_aplastamiento"]       # excedido
    assert r["estructural"]["cumple_transferencia"] == t["cumple_dowels"]


# --------------------------------------------------------------------------
# API
# --------------------------------------------------------------------------
def test_api_dado_incluye_verificaciones_estructurales():
    cl = _client()
    r = cl.post("/api/dado", json=dict(
        n_pilotes=4, Dp=0.45, c1=0.5, c2=0.5, Pu=2000, Mux=150,
        capacidad_pilote=800, fc=28, fc_columna=28)).get_json()
    assert r["ok"]
    e = r["estructural"]
    assert "transferencia" in e and "anclaje_tensor" in e
    assert e["punz_columna"].get("cumple_momento") is not None
