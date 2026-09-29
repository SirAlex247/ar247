"""Pruebas del módulo de muros de tierra armada (MSE) — método FHWA/AASHTO."""
from __future__ import annotations

import math

from retaining_wall.core.mse import DisenadorMSE, _ka_rankine


def _client():
    try:
        import app as _appmod
    except ModuleNotFoundError:
        import os
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "python"))
        import app as _appmod
    return _appmod.app.test_client()


def _mse(**over):
    base = dict(H=8.0, L=5.6, Sv=0.6, gamma_r=19.0, phi_r=34.0,
                gamma_b=18.0, phi_b=30.0, gamma_f=19.0, phi_f=30.0, c_f=5.0,
                sobrecarga=12.0, tipo_refuerzo="geosintetico", Ta=45.0)
    base.update(over)
    return DisenadorMSE(**base).disenar()


# --------------------------------------------------------------------------
# Estabilidad interna
# --------------------------------------------------------------------------
def test_numero_de_capas_y_espaciamiento():
    r = _mse(H=8.0, Sv=0.6)
    assert r.n_capas == round(8.0 / 0.6)
    assert math.isclose(r.Sv, 8.0 / r.n_capas, rel_tol=1e-6)


def test_tmax_crece_con_la_profundidad():
    r = _mse(sobrecarga=0.0)
    Ts = [c.Tmax for c in r.capas]
    assert Ts == sorted(Ts)          # monótona creciente hacia la base


def test_geosintetico_Kr_igual_Ka():
    r = _mse(tipo_refuerzo="geosintetico", phi_r=34.0)
    Ka = _ka_rankine(34.0)
    for c in r.capas:
        assert math.isclose(c.Kr, Ka, rel_tol=1e-9)


def test_metalico_Kr_decrece_con_profundidad():
    r = _mse(tipo_refuerzo="metalico")
    Ka = _ka_rankine(34.0)
    # corona: Kr/Ka ~ 1.7; base (>6 m): 1.2
    assert r.capas[0].Kr > r.capas[-1].Kr
    assert r.capas[-1].Kr <= 1.25 * Ka + 1e-6


def test_rotura_critica_en_la_base_pullout_en_la_corona():
    r = _mse(sobrecarga=0.0)
    # Tmax máximo en la base → FS_rotura mínimo cerca de la base
    assert r.resumen["capa_critica_rotura"] >= r.n_capas - 1
    # Le mínimo en la corona → arrancamiento crítico arriba
    assert r.resumen["capa_critica_pullout"] == 1


def test_Ta_mayor_aumenta_FS_rotura():
    baja = _mse(Ta=25.0)
    alta = _mse(Ta=60.0)
    assert alta.resumen["FS_rotura_min"] > baja.resumen["FS_rotura_min"]


def test_longitud_mayor_mejora_arrancamiento():
    corta = _mse(L=4.0)
    larga = _mse(L=7.0)
    assert larga.resumen["FS_pullout_min"] > corta.resumen["FS_pullout_min"]


# --------------------------------------------------------------------------
# Estabilidad externa
# --------------------------------------------------------------------------
def test_externa_longitud_mejora_deslizamiento_y_volcamiento():
    corta = _mse(L=3.5).externa
    larga = _mse(L=7.0).externa
    assert larga["FS_deslizamiento"] > corta["FS_deslizamiento"]
    assert larga["FS_volcamiento"] > corta["FS_volcamiento"]


def test_externa_excentricidad_dentro_de_L6():
    r = _mse(L=5.6)
    assert r.externa["e_m"] <= r.L / 6.0 + 1e-9 or not r.externa["cumple_excentricidad"]


# --------------------------------------------------------------------------
# API
# --------------------------------------------------------------------------
def test_api_mse_ok_y_estructura():
    cl = _client()
    r = cl.post("/api/mse", json=dict(
        H=8.0, L=5.6, Sv=0.6, gamma_r=19.0, phi_r=34.0, gamma_b=18.0, phi_b=30.0,
        gamma_f=19.0, phi_f=30.0, c_f=5.0, sobrecarga=12.0,
        tipo_refuerzo="geosintetico", Ta=45.0)).get_json()
    assert r["ok"]
    assert r["n_capas"] > 5
    assert len(r["capas"]) == r["n_capas"]
    assert r["imagen_raw"]
    assert "FS_rotura_min" in r["resumen"]


def test_api_mse_pdf_genera():
    cl = _client()
    r = cl.post("/api/mse_pdf", json=dict(
        H=7.0, L=5.0, Sv=0.6, gamma_r=19.0, phi_r=32.0, gamma_b=18.0, phi_b=30.0,
        gamma_f=19.0, phi_f=30.0, c_f=0.0, sobrecarga=10.0,
        tipo_refuerzo="metalico", Ta=55.0, proyecto="MSE test"))
    assert r.status_code == 200
    assert r.headers["Content-Type"] == "application/pdf"
    assert len(r.data) > 40000
