"""Pruebas de la placa / losa de cimentación maciza (método rígido).

Cubren:
  - dimensionamiento automático de la planta por la malla + voladizo,
  - presión uniforme en malla simétrica (e≈0) y gradiente biaxial con cargas
    desiguales (método rígido),
  - punzonamiento en todas las columnas y flexión por franjas,
  - detección de despegue (q_mín<0) con excentricidad grande,
  - el despachador de la API (/api/placa) y el constructor de malla.
"""
from __future__ import annotations

import math

from retaining_wall.core.placa import disenar_placa, malla_columnas


# --------------------------------------------------------------------------
# Malla y dimensionamiento
# --------------------------------------------------------------------------
def test_malla_columnas_cuenta_y_posiciones():
    cols = malla_columnas(nx=3, ny=2, sx=5.0, sy=4.0, P=800, c1=0.5, c2=0.5)
    assert len(cols) == 6
    xs = sorted({c["x"] for c in cols})
    ys = sorted({c["y"] for c in cols})
    assert xs == [0.0, 5.0, 10.0]
    assert ys == [0.0, 4.0]
    assert all(math.isclose(c["Pu"], 1.5 * 800) for c in cols)


def test_auto_dimension_por_malla_y_voladizo():
    cols = malla_columnas(nx=3, ny=3, sx=5.0, sy=5.0, P=900, c1=0.5, c2=0.5)
    r = disenar_placa(columnas=cols, q_adm=250, voladizo=0.6)
    g = r["geometria"]
    # extensión 2·5=10 + 2·0.6 = 11.2 en ambas direcciones
    assert math.isclose(g["B_m"], 11.2, abs_tol=1e-6)
    assert math.isclose(g["L_m"], 11.2, abs_tol=1e-6)
    assert g["auto_dimensionada"] is True
    assert g["n_columnas"] == 9


# --------------------------------------------------------------------------
# Geotecnia (método rígido)
# --------------------------------------------------------------------------
def test_malla_simetrica_presion_uniforme():
    cols = malla_columnas(nx=3, ny=3, sx=5.0, sy=5.0, P=900, c1=0.5, c2=0.5)
    r = disenar_placa(columnas=cols, q_adm=250, voladizo=0.6)
    geo = r["geotecnico"]
    assert abs(geo["e_x_m"]) < 1e-6 and abs(geo["e_y_m"]) < 1e-6
    # las 4 esquinas ~ iguales (uniforme)
    qs = list(geo["esquinas_kPa"].values())
    assert max(qs) - min(qs) < 0.5
    assert geo["cumple"] and geo["q_min_kPa"] >= 0.0


def test_cargas_desiguales_gradiente_biaxial():
    cols = [
        {"x": 0, "y": 0, "P": 600, "c1": 0.4, "c2": 0.4},
        {"x": 6, "y": 0, "P": 1100, "c1": 0.5, "c2": 0.5},
        {"x": 0, "y": 5, "P": 700, "c1": 0.4, "c2": 0.4},
        {"x": 6, "y": 5, "P": 1300, "c1": 0.5, "c2": 0.5},
    ]
    r = disenar_placa(columnas=cols, q_adm=220, voladizo=0.5)
    geo = r["geotecnico"]
    # el centroide se corre hacia las columnas pesadas (x y y mayores)
    assert geo["e_x_m"] > 0 and geo["e_y_m"] > 0
    assert geo["q_max_kPa"] > geo["q_prom_kPa"] > geo["q_min_kPa"]
    # la esquina cargada (x=B, y=L) es la de mayor presión
    esq = geo["esquinas_kPa"]
    assert esq["q_BL"] == max(esq.values())
    assert esq["q_00"] == min(esq.values())


def test_despegue_avisa_con_excentricidad_grande():
    # Una columna dominante muy descentrada en una losa fija pequeña → q_min<0
    cols = [
        {"x": 0.4, "y": 0.4, "P": 200, "c1": 0.4, "c2": 0.4},
        {"x": 5.6, "y": 5.6, "P": 2500, "c1": 0.6, "c2": 0.6},
    ]
    r = disenar_placa(columnas=cols, q_adm=400, B=6.0, L=6.0, h=0.6)
    assert r["geotecnico"]["q_min_kPa"] < 0.0
    assert any("despegue" in a.lower() for a in r["avisos"])


# --------------------------------------------------------------------------
# Estructural
# --------------------------------------------------------------------------
def test_punzonamiento_todas_las_columnas():
    cols = malla_columnas(nx=2, ny=2, sx=5.0, sy=5.0, P=1000, c1=0.5, c2=0.5)
    r = disenar_placa(columnas=cols, q_adm=250, voladizo=0.6)
    e = r["estructural"]
    assert len(e["punzonamiento"]) == 4
    assert all("ratio" in p for p in e["punzonamiento"])
    assert e["punz_critico"]["ratio"] == max(p["ratio"] for p in e["punzonamiento"])
    assert e["cumple_cortante"] is True


def test_flexion_franjas_estructura():
    cols = malla_columnas(nx=3, ny=3, sx=5.0, sy=5.0, P=900, c1=0.5, c2=0.5)
    r = disenar_placa(columnas=cols, q_adm=250, voladizo=0.6)
    e = r["estructural"]
    for key in ("franja_x", "franja_y"):
        fr = e[key]
        assert fr["acero_inferior"]["As_cm2"] > 0
        assert fr["acero_superior"]["As_cm2"] > 0
        assert fr["M_neg_kNm"] <= 0 <= fr["M_pos_kNm"]
    # malla simétrica → franjas X e Y equivalentes (misma luz y carga)
    assert math.isclose(e["franja_x"]["M_neg_kNm"], e["franja_y"]["M_neg_kNm"], rel_tol=1e-6)


def test_columna_unica_degenera_ok():
    r = disenar_placa(columnas=[{"x": 0, "y": 0, "P": 500, "c1": 0.4, "c2": 0.4}],
                      q_adm=200, voladizo=1.0)
    g = r["geometria"]
    # sin extensión de malla: B=L=2·voladizo
    assert math.isclose(g["B_m"], 2.0, abs_tol=1e-6)
    assert r["estructural"]["cumple_cortante"] in (True, False)  # no explota
    assert r["geotecnico"]["cumple"]


def test_espesor_dado_se_respeta():
    cols = malla_columnas(nx=2, ny=2, sx=5.0, sy=5.0, P=800, c1=0.5, c2=0.5)
    r = disenar_placa(columnas=cols, q_adm=250, voladizo=0.6, h=0.80)
    assert math.isclose(r["geometria"]["h_m"], 0.80, abs_tol=1e-6)


# --------------------------------------------------------------------------
# API
# --------------------------------------------------------------------------
def test_api_placa_endpoint_ok():
    try:
        import app as _appmod
    except ModuleNotFoundError:
        import os
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "python"))
        import app as _appmod
    client = _appmod.app.test_client()
    payload = {"nx": 3, "ny": 3, "sx": 5.0, "sy": 5.0, "P": 900,
               "c1": 0.5, "c2": 0.5, "q_adm": 250, "voladizo": 0.6, "fc": 28}
    r = client.post("/api/placa", json=payload).get_json()
    assert r["ok"] is True and r["tipo"] == "placa"
    assert r["geometria"]["n_columnas"] == 9
    assert "franja_x" in r["estructural"]
