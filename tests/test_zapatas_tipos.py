"""Pruebas de los tipos de zapata (aislada biaxial/rectangular, combinada,
esquinera, triangular) y del despachador ``disenar_zapata_tipo``.

El diseño de la aislada cuadrada/concéntrica no debe cambiar (no-regresión):
lo cubren test_modulos; aquí se validan las variantes nuevas.
"""
from __future__ import annotations

import math

from retaining_wall.core.zapata import disenar_zapata
from retaining_wall.core.zapatas_tipos import (
    disenar_combinada,
    disenar_esquinera,
    disenar_triangular,
    disenar_zapata_tipo,
)


# --------------------------------------------------------------------------
# Aislada extendida
# --------------------------------------------------------------------------
def test_aislada_concentrica_sigue_cuadrada():
    r = disenar_zapata(c1=0.4, c2=0.4, P_servicio=600, q_adm=200, Pu=840)
    g = r["geometria"]
    assert math.isclose(g["B_m"], g["L_m"])           # cuadrada
    assert r["geotecnico"]["cumple"]
    assert r["estructural"]["cumple_cortante"]


def test_aislada_rectangular_relacion_LB():
    r = disenar_zapata(c1=0.4, c2=0.4, P_servicio=600, q_adm=200, Pu=840,
                       relacion_LB=1.5)
    g = r["geometria"]
    assert g["L_m"] > g["B_m"]
    assert abs(g["L_m"] / g["B_m"] - 1.5) < 0.15      # ~1.5 (redondeo a 0.05)


def test_aislada_biaxial_presiones_esquina():
    r = disenar_zapata(c1=0.5, c2=0.5, P_servicio=800, M_servicio=120,
                       My_servicio=60, q_adm=220, Pu=1120)
    geo = r["geotecnico"]
    # Biaxial: q_max > q_uniforme > q_min y todo positivo (sin despegue aquí)
    assert geo["q_max_kPa"] > geo["q_uniforme_kPa"] > geo["q_min_kPa"]
    assert geo["q_min_kPa"] >= 0.0
    assert geo["excentricidad_m"] > 0.0


def test_aislada_biaxial_despegue_avisa():
    # Momentos grandes con planta fija pequeña → q_min < 0 → aviso de despegue
    r = disenar_zapata(c1=0.4, c2=0.4, P_servicio=400, M_servicio=300,
                       My_servicio=200, q_adm=200, B=2.0, L=2.0, h=0.5)
    assert r["geotecnico"]["q_min_kPa"] < 0.0
    assert any("despegue" in a.lower() for a in r["avisos"])


# --------------------------------------------------------------------------
# Combinada
# --------------------------------------------------------------------------
def test_combinada_geometria_y_centrado():
    r = disenar_combinada(c1a=0.4, c2a=0.4, P1_servicio=700,
                          c1b=0.5, c2b=0.5, P2_servicio=900,
                          separacion=4.5, q_adm=200)
    g = r["geometria"]
    # Medianería izquierda: columna 1 a c1a/2 del borde
    assert math.isclose(g["x1_col_m"], 0.4 / 2.0, abs_tol=1e-6)
    assert math.isclose(g["x2_col_m"] - g["x1_col_m"], 4.5, abs_tol=1e-6)
    # Casi centrada (excentricidad pequeña)
    assert abs(r["geotecnico"]["excentricidad_m"]) < 0.05
    assert r["geotecnico"]["cumple"]


def test_combinada_momentos_signo():
    r = disenar_combinada(c1a=0.4, c2a=0.4, P1_servicio=700,
                          c1b=0.5, c2b=0.5, P2_servicio=900,
                          separacion=4.5, q_adm=200)
    e = r["estructural"]
    # Entre columnas hay momento negativo grande (tracción arriba → acero sup.)
    assert e["M_neg_kNm"] < 0
    assert e["flexion_long_superior"]["As_cm2"] > 0
    assert e["flexion_long_inferior"]["As_cm2"] > 0
    assert "punzonamiento_col1" in e and "punzonamiento_col2" in e


# --------------------------------------------------------------------------
# Esquinera
# --------------------------------------------------------------------------
def test_esquinera_con_viga_es_uniforme():
    r = disenar_esquinera(c1=0.4, c2=0.4, P_servicio=600, q_adm=200,
                          viga_centradora=True)
    assert r["tipo"] == "esquinera"
    # Presión ~uniforme (q_max ≈ q_uniforme)
    geo = r["geotecnico"]
    assert math.isclose(geo["q_max_kPa"], geo["q_uniforme_kPa"], rel_tol=0.02)
    assert any("centradora" in a.lower() for a in r["avisos"])


def test_esquinera_sin_viga_avisa_despegue():
    r = disenar_esquinera(c1=0.4, c2=0.4, P_servicio=600, q_adm=200,
                          viga_centradora=False)
    assert r["geotecnico"]["q_min_kPa"] < 0.0     # despegue por la esquina
    assert r["esquinera"]["viga_centradora"] is False
    assert any("esquina" in a.lower() for a in r["avisos"])


# --------------------------------------------------------------------------
# Triangular
# --------------------------------------------------------------------------
def test_triangular_area_y_presion():
    r = disenar_triangular(c1=0.4, c2=0.4, P_servicio=500, q_adm=200)
    g = r["geometria"]
    # (valores redondeados a 3 decimales → tolerancia acorde)
    assert math.isclose(g["area_m2"], 0.5 * g["base_m"] * g["altura_m"], rel_tol=2e-3)
    assert r["geotecnico"]["q_uniforme_kPa"] <= 200 * 1.001
    assert r["estructural"]["cumple_cortante"]


# --------------------------------------------------------------------------
# Despachador
# --------------------------------------------------------------------------
def test_dispatcher_tipos_consolidados():
    base = {"c1": 0.4, "c2": 0.4, "P_servicio": 600, "q_adm": 200}
    # Los variantes de aislada se consolidan en tipo "aislada" con forma/carga.
    assert disenar_zapata_tipo("aislada", base)["tipo"] == "aislada"
    r_conc = disenar_zapata_tipo("aislada", base)
    assert r_conc["forma"] == "cuadrada" and r_conc["carga"] == "concéntrica"
    r_exc = disenar_zapata_tipo("aislada", {**base, "M_servicio": 40})
    assert r_exc["carga"] == "excéntrica"
    # forma rectangular (por campo o por alias antiguo)
    assert disenar_zapata_tipo("aislada", {**base, "forma": "rectangular"})["forma"] == "rectangular"
    assert disenar_zapata_tipo("rectangular", base)["forma"] == "rectangular"     # alias
    assert disenar_zapata_tipo("concentrica", base)["tipo"] == "aislada"          # alias
    # Conectada / medianera (antes "esquinera")
    con = disenar_zapata_tipo("conectada", {**base, "viga_centradora": True})
    assert con["tipo"] == "conectada"
    assert math.isclose(con["geotecnico"]["q_max_kPa"], con["geotecnico"]["q_uniforme_kPa"], rel_tol=0.02)
    # Combinada y triangular
    comb = disenar_zapata_tipo("combinada", {
        "c1a": 0.4, "c2a": 0.4, "P1_servicio": 700,
        "c1b": 0.4, "c2b": 0.4, "P2_servicio": 700, "separacion": 4.0, "q_adm": 200})
    assert comb["tipo"] == "combinada"
    assert disenar_zapata_tipo("triangular", base)["tipo"] == "triangular"
    # tipo desconocido → aislada
    assert disenar_zapata_tipo("loquesea", base)["tipo"] == "aislada"
