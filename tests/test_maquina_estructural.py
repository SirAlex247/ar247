"""Pruebas del diseño ESTRUCTURAL del bloque de cimentación de máquina:
validación de bloque rígido (ACI 351.3R), fuerza dinámica de diseño con factor
de fatiga, pernos de anclaje (ACI 318-19 Cap. 17) y refuerzo mínimo cada cara.
El análisis dinámico y las propiedades del suelo siguen siendo inputs."""
from __future__ import annotations

from retaining_wall.core.maquinas import disenar_maquina

_BASE = dict(B=5.0, L=4.0, h=1.5, peso_maquina=120, hcg_maquina=1.8,
             G_suelo=90, nu=0.35, gamma_suelo=19, gamma_concreto=24,
             q_adm=250, amplitud_admisible_um=50)


def _client():
    try:
        import app as _appmod
    except ModuleNotFoundError:
        import os
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "python"))
        import app as _appmod
    return _appmod.app.test_client()


# --------------------------------------------------------------------------
# Retrocompatibilidad: el caso bien sintonizado sigue cumpliendo
# --------------------------------------------------------------------------
def test_base_sigue_cumpliendo_con_estructural():
    r = disenar_maquina(rpm=750, F0=12, **_BASE)
    assert r["cumple"] is True
    assert "estructural" in r
    assert r["estructural"]["cumple_rigidez"] and r["estructural"]["cumple_pernos"]


# --------------------------------------------------------------------------
# 1. Bloque rígido
# --------------------------------------------------------------------------
def test_bloque_delgado_no_cumple_rigidez():
    r = disenar_maquina(rpm=750, F0=12, **{**_BASE, "h": 0.5})
    assert r["estructural"]["cumple_rigidez"] is False
    assert r["cumple"] is False
    assert any("espesor" in a.lower() or "0.60" in a for a in r["avisos"])


def test_bloque_rigido_ok():
    e = disenar_maquina(rpm=750, F0=12, **_BASE)["estructural"]
    assert e["rigidez"]["rigido"] and e["rigidez"]["cumple"]


# --------------------------------------------------------------------------
# 2. Fuerza dinámica de diseño (factor de fatiga)
# --------------------------------------------------------------------------
def test_factor_fatiga_amplifica_fuerza():
    e = disenar_maquina(rpm=750, F0=10, factor_fatiga=2.0, **_BASE)["estructural"]
    fd = e["fuerza_diseno"]
    assert abs(fd["F_dinamica_diseno_kN"] - 2.0 * fd["F0_kN"]) < 1e-6
    assert fd["M_vuelco_diseno_kNm"] > 0


# --------------------------------------------------------------------------
# 3. Pernos de anclaje
# --------------------------------------------------------------------------
def test_pernos_no_aplica_sin_datos():
    e = disenar_maquina(rpm=750, F0=12, **_BASE)["estructural"]
    assert e["pernos"]["aplica"] is False
    assert e["cumple_pernos"] is True


def test_pernos_con_traccion_neta():
    # Bloque ligero + desbalance alto y CG alto → vuelco genera tracción neta.
    r = disenar_maquina(rpm=750, F0=60, hcg_maquina=2.0,
                        n_pernos=4, db_perno=25, fy_perno=250, embed_perno=0.5,
                        sep_pernos=1.75,
                        B=2.5, L=2.5, h=0.6, peso_maquina=30,
                        G_suelo=90, nu=0.35, gamma_suelo=19, gamma_concreto=24,
                        q_adm=400, amplitud_admisible_um=200)
    p = r["estructural"]["pernos"]
    assert p["aplica"] and p["T_perno_kN"] > 0
    assert p["phiNsa_kN"] > 0 and p["phiVsa_kN"] > 0 and p["phiNcb_kN"] > 0
    assert 0.0 <= p["interaccion"]
    assert "cumple" in p


def test_pernos_pequenos_fallan_interaccion():
    # Pernos muy delgados bajo gran tracción → no cumplen el acero.
    r = disenar_maquina(rpm=750, F0=80, hcg_maquina=2.5,
                        n_pernos=4, db_perno=12, fy_perno=250, embed_perno=0.5,
                        sep_pernos=1.6,
                        B=2.2, L=2.2, h=0.6, peso_maquina=20,
                        G_suelo=90, nu=0.35, gamma_suelo=19, gamma_concreto=24,
                        q_adm=600, amplitud_admisible_um=500)
    p = r["estructural"]["pernos"]
    assert p["T_perno_kN"] > 0
    assert (p["cumple_acero"] is False) or (p["cumple_breakout"] is False)
    assert r["cumple"] is False


# --------------------------------------------------------------------------
# 4. Refuerzo mínimo
# --------------------------------------------------------------------------
def test_refuerzo_minimo_presente():
    rf = disenar_maquina(rpm=750, F0=12, **_BASE)["estructural"]["refuerzo"]
    assert rf["dir_B"]["n_barras_cara"] >= 2 and rf["dir_L"]["n_barras_cara"] >= 2
    assert rf["dir_B"]["sep_cm"] <= 30.0 + 1e-6
    assert 20.0 <= rf["acero_kg_m3"] <= 40.0        # ~28 kg/m³ con ρ=0.0018


# --------------------------------------------------------------------------
# API
# --------------------------------------------------------------------------
def test_api_maquina_incluye_estructural():
    cl = _client()
    r = cl.post("/api/maquina", json=dict(
        B=5, L=4, h=1.5, peso_maquina=120, rpm=750, F0=12, hcg_maquina=1.8,
        G_suelo=90, nu=0.35, gamma_suelo=19, q_adm=250,
        n_pernos=8, db_perno=32, fy_perno=250, embed_perno=0.6, sep_pernos=3.5,
    )).get_json()
    assert r["ok"]
    e = r["estructural"]
    assert "rigidez" in e and "pernos" in e and "refuerzo" in e
    assert e["pernos"]["aplica"] is True
