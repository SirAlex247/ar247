"""Pruebas del módulo de muros anclados (presiones aparentes FHWA/Terzaghi-Peck)."""
from __future__ import annotations

import math

from retaining_wall.core.muro_anclado import DisenadorMuroAnclado


def _client():
    try:
        import app as _appmod
    except ModuleNotFoundError:
        import os
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "python"))
        import app as _appmod
    return _appmod.app.test_client()


def _anc(**over):
    base = dict(H=12.0, gamma=19.0, phi=32.0, n_anclajes=3, z_primero=2.0, sv=3.5,
                inclinacion=15.0, sh=2.5, sobrecarga=12.0, tipo_suelo="arena",
                tau_bond=250.0, d_bulbo=0.15)
    base.update(over)
    return DisenadorMuroAnclado(**base).disenar()


# --------------------------------------------------------------------------
# Envolvente y balance de fuerzas
# --------------------------------------------------------------------------
def test_balance_de_fuerzas():
    """La suma de las cargas de anclaje y la reacción de base iguala el empuje
    total de la envolvente (partición del área tributaria)."""
    r = _anc()
    suma = sum(a.Th for a in r.anclajes) + r.reaccion_base
    assert math.isclose(suma, r.empuje_total, rel_tol=1e-2)


def test_p_max_crece_con_H():
    baja = _anc(H=8.0)
    alta = _anc(H=16.0)
    assert alta.p_max > baja.p_max


def test_numero_de_anclajes_respetado():
    r = _anc(n_anclajes=4, z_primero=1.5, sv=2.5)
    assert r.n_anclajes == 4
    assert len(r.anclajes) == 4


def test_bulbo_crece_con_la_carga():
    """Mayor separación horizontal → mayor fuerza por anclaje → bulbo más largo."""
    corto = _anc(sh=2.0)
    largo = _anc(sh=3.5)
    assert (max(a.Lb for a in largo.anclajes)
            > max(a.Lb for a in corto.anclajes))


def test_mayor_tau_reduce_bulbo():
    debil = _anc(tau_bond=120.0)
    fuerte = _anc(tau_bond=400.0)
    assert (max(a.Lb for a in fuerte.anclajes)
            < max(a.Lb for a in debil.anclajes))


def test_longitud_libre_supera_la_cuna():
    r = _anc(inclinacion=0.0)   # anclajes horizontales: Lf ≈ dist. a la cuña
    for a in r.anclajes:
        dist_cuna = (r.H - a.z) * math.tan(math.radians(45 - 32 / 2.0))
        assert a.Lf >= dist_cuna - 1e-6


def test_arcilla_y_arena_dan_Ka_distinto():
    arena = _anc(tipo_suelo="arena")
    arcilla = _anc(tipo_suelo="arcilla", Su=40.0, phi=0.0)
    assert not math.isclose(arena.Ka, arcilla.Ka, rel_tol=1e-3)


# --------------------------------------------------------------------------
# API
# --------------------------------------------------------------------------
def test_api_anclado_ok_y_estructura():
    cl = _client()
    r = cl.post("/api/muro_anclado", json=dict(
        H=12.0, gamma=19.0, phi=32.0, n_anclajes=3, z_primero=2.0, sv=3.5,
        inclinacion=15.0, sh=2.5, sobrecarga=12.0, tipo_suelo="arena",
        tau_bond=250.0, d_bulbo=0.15)).get_json()
    assert r["ok"]
    assert r["n_anclajes"] == 3
    assert len(r["anclajes"]) == 3
    assert r["imagen_raw"]
    assert r["resumen"]["p_max_kPa"] > 0


def test_api_anclado_pdf_genera():
    cl = _client()
    r = cl.post("/api/muro_anclado_pdf", json=dict(
        H=10.0, gamma=18.0, phi=30.0, n_anclajes=2, z_primero=2.0, sv=3.5,
        tipo_suelo="arena", tau_bond=250.0, d_bulbo=0.15, proyecto="Anclado test"))
    assert r.status_code == 200
    assert r.headers["Content-Type"] == "application/pdf"
    assert len(r.data) > 40000
