"""Pruebas de la cimentación de máquina (ACI 351.3R, parámetros concentrados)."""
from __future__ import annotations

import math

from retaining_wall.core.maquinas import disenar_maquina

_BASE = dict(B=5.0, L=4.0, h=1.5, peso_maquina=120, hcg_maquina=1.8,
             G_suelo=90, nu=0.35, gamma_suelo=19, gamma_concreto=24,
             q_adm=250, amplitud_admisible_um=50)


def test_cuatro_modos_y_frecuencias_positivas():
    r = disenar_maquina(rpm=750, F0=12, **_BASE)
    assert len(r["modos"]) == 4
    nombres = [m["nombre"] for m in r["modos"]]
    assert any("Vertical" in n for n in nombres) and any("Cabeceo" in n for n in nombres)
    for m in r["modos"]:
        assert m["fn_Hz"] > 0 and m["amortiguamiento_D"] > 0


def test_G_y_Vs_equivalentes():
    a = disenar_maquina(rpm=750, F0=12, **_BASE)
    Vs = a["suelo"]["Vs_m_s"]
    base2 = {k: v for k, v in _BASE.items() if k != "G_suelo"}
    b = disenar_maquina(rpm=750, F0=12, Vs=Vs, **base2)
    assert math.isclose(a["modos"][0]["fn_Hz"], b["modos"][0]["fn_Hz"], rel_tol=1e-2)


def test_F0_directa_equivale_a_masa_excentrica():
    rpm = 900
    w = 2 * math.pi * rpm / 60.0
    F0 = 10.0                                   # kN
    me = F0 * 1000.0 / w ** 2                    # kg·m tal que m_e·e·ω² = F0
    a = disenar_maquina(rpm=rpm, F0=F0, **_BASE)
    b = disenar_maquina(rpm=rpm, masa_excentrica_e=me, **_BASE)
    assert math.isclose(a["excitacion"]["F0_kN"], b["excitacion"]["F0_kN"], rel_tol=1e-3)
    assert math.isclose(a["amplitud_max_um"], b["amplitud_max_um"], rel_tol=1e-3)


def test_resonancia_se_detecta():
    # Se busca una rpm cuya frecuencia caiga cerca de una fₙ (banda 0.8–1.2).
    r0 = disenar_maquina(rpm=100, F0=12, **_BASE)
    fn_vert = r0["modos"][0]["fn_Hz"]
    rpm_res = fn_vert * 60.0                     # f_op ≈ fn del modo vertical
    r = disenar_maquina(rpm=rpm_res, F0=12, **_BASE)
    assert r["resonancia_ok"] is False
    assert any(not m["separado"] for m in r["modos"])
    assert any("resonancia" in a.lower() for a in r["avisos"])


def test_amplificacion_en_resonancia_es_uno_sobre_2D():
    # En r ≈ 1 la amplificación dinámica vale 1/(2·D) (independiente de la carga).
    r0 = disenar_maquina(rpm=100, F0=12, **_BASE)
    fn = r0["modos"][0]["fn_Hz"]
    r = disenar_maquina(rpm=fn * 60.0, F0=12, **_BASE)
    m = r["modos"][0]
    assert abs(m["razon_frec"] - 1.0) < 0.02
    assert math.isclose(m["amplificacion"], 1.0 / (2.0 * m["amortiguamiento_D"]), rel_tol=0.05)


def test_bloque_pesado_baja_frecuencia():
    liviano = disenar_maquina(rpm=750, F0=12, **{**_BASE, "h": 1.0})
    pesado = disenar_maquina(rpm=750, F0=12, **{**_BASE, "h": 2.5})
    # más masa (mayor h) → menor frecuencia natural vertical
    assert pesado["modos"][0]["fn_Hz"] < liviano["modos"][0]["fn_Hz"]


def test_presion_estatica_y_aviso_masa():
    # máquina muy pesada frente a un bloque pequeño → rel de masa baja (aviso)
    r = disenar_maquina(rpm=750, F0=12, **{**_BASE, "peso_maquina": 400})
    assert r["masas"]["relacion_masa_bloque_maquina"] < 2.0
    assert any("bloque pesa" in a.lower() or "recomienda" in a.lower() for a in r["avisos"])
    assert r["geotecnico"]["q_estatica_kPa"] > 0


def test_bien_sintonizada_cumple():
    r = disenar_maquina(rpm=750, F0=12, **_BASE)
    assert r["resonancia_ok"] and r["amplitud_ok"] and r["geotecnico"]["cumple"]
    assert r["cumple"] is True


def test_api_maquina_endpoint_ok():
    try:
        import app as _appmod
    except ModuleNotFoundError:
        import os
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "python"))
        import app as _appmod
    client = _appmod.app.test_client()
    payload = {"B": 5, "L": 4, "h": 1.5, "peso_maquina": 120, "rpm": 750,
               "F0": 12, "hcg_maquina": 1.8, "G_suelo": 90, "nu": 0.35,
               "gamma_suelo": 19, "q_adm": 250}
    r = client.post("/api/maquina", json=payload).get_json()
    assert r["ok"] is True and r["tipo"] == "maquina"
    assert len(r["modos"]) == 4 and r["excitacion"]["f_operacion_Hz"] == 12.5
