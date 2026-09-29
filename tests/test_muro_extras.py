"""Pruebas de las capacidades nuevas del muro: nivel freático (empuje efectivo
+ hidrostático), diente/llave de cortante (empuje pasivo adicional), carga
lineal (Boussinesq) y estabilidad global (método de dovelas)."""
from __future__ import annotations

import math

from retaining_wall.core.empujes import EmpujeSuelo


def _muro_para_global(**over):
    """Construye un MuroContencion mínimo para probar la estabilidad global."""
    from retaining_wall.models.muro import (
        MuroContencion, GeometriaMuro, CondicionesCarga)
    from retaining_wall.models.suelo import Suelo
    from retaining_wall.models.material import Concreto, AceroRefuerzo
    g = GeometriaMuro(H_vastago=6.0, e_zapata=0.7, b_puntera=0.9, b_talon=2.6,
                      b_corona=0.3, b_base_vast=0.5, D=1.5, H_relleno=6.0)
    rel = Suelo(gamma=18.0, phi=over.get("phi_rel", 34.0),
                cohesion=over.get("c_rel", 0.0), gamma_sat=20.0)
    cim = Suelo(gamma=19.0, phi=over.get("phi_cim", 20.0),
                cohesion=over.get("c_cim", 40.0))
    cond = CondicionesCarga(alpha=over.get("alpha", 10.0),
                            sobrecarga=over.get("q", 0.0),
                            nivel_freatico_H=over.get("nf", None))
    return MuroContencion(geometria=g, suelo_relleno=rel, suelo_cimentacion=cim,
                          concreto=Concreto(fc=21.0), acero=AceroRefuerzo(fy=420.0),
                          condiciones=cond)


def _client():
    try:
        import app as _appmod
    except ModuleNotFoundError:
        import os
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "python"))
        import app as _appmod
    return _appmod.app.test_client()


_GEO = dict(tipo_muro="voladizo", H_vastago=6.0, e_zapata=0.7, b_puntera=0.9,
            b_talon=2.6, b_corona=0.3, b_base_vast=0.5, D=1.5, H_relleno=6.0,
            relleno_gamma=18.0, relleno_phi=34.0, relleno_cohesion=0.0,
            relleno_gamma_sat=20.0, ciment_gamma=19.0, ciment_phi=20.0,
            ciment_cohesion=40.0, concreto_fc=21.0, concreto_gamma=24.0,
            acero_fy=420.0, alpha=10.0, sobrecarga=0.0, metodo_empuje="rankine",
            norma="NSR10")


# --------------------------------------------------------------------------
# Nivel freático — método de empuje
# --------------------------------------------------------------------------
def test_empuje_con_agua_suma_componentes():
    r = EmpujeSuelo.calcular_empuje_activo_con_agua(
        gamma=18.0, gamma_sat=20.0, H=6.0, phi_grados=34.0, h_agua=6.0)
    tierra_h = r["efectivo"].componente_h
    agua_h = r["agua"].componente_h
    assert math.isclose(r["detalle"]["P_total_kN"], tierra_h + agua_h, rel_tol=1e-3)
    # Con N.F. lleno, el agua domina el empuje total
    assert agua_h > tierra_h


def test_empuje_con_agua_mayor_que_seco():
    seco = EmpujeSuelo.calcular_empuje_activo_rankine(
        gamma=18.0, H=6.0, phi_grados=34.0)
    con_agua = EmpujeSuelo.calcular_empuje_activo_con_agua(
        gamma=18.0, gamma_sat=20.0, H=6.0, phi_grados=34.0, h_agua=6.0)
    total_agua = con_agua["efectivo"].componente_h + con_agua["agua"].componente_h
    # El N.F. lleno debe aumentar mucho el empuje total (~2×)
    assert total_agua > 1.8 * seco.componente_h


def test_empuje_sin_agua_equivale_al_seco():
    # h_agua = 0 → debe reducirse al empuje activo seco (sin componente de agua)
    r = EmpujeSuelo.calcular_empuje_activo_con_agua(
        gamma=18.0, gamma_sat=20.0, H=6.0, phi_grados=34.0, h_agua=0.0)
    seco = EmpujeSuelo.calcular_empuje_activo_rankine(gamma=18.0, H=6.0, phi_grados=34.0)
    assert math.isclose(r["efectivo"].componente_h, seco.componente_h, rel_tol=1e-6)
    assert r["agua"].componente_h == 0.0


# --------------------------------------------------------------------------
# Nivel freático — integración por la API
# --------------------------------------------------------------------------
def test_api_muro_nivel_freatico_aumenta_empuje():
    cl = _client()
    seco = cl.post("/api/analizar", json=_GEO).get_json()
    mojado = cl.post("/api/analizar", json={**_GEO, "nivel_freatico_H": 6.0}).get_json()
    assert seco["ok"] and mojado["ok"]
    assert mojado["totales"]["SH_empuje"] > seco["totales"]["SH_empuje"] * 1.5
    # el muro seco pasa; con N.F. a toda altura falla
    assert "APROBADO" in seco["resultado_global"]["estado"]
    assert "NO APROBADO" in mojado["resultado_global"]["estado"]


def test_api_muro_gamma_sat_influye():
    cl = _client()
    liviano = cl.post("/api/analizar", json={**_GEO, "nivel_freatico_H": 4.0,
                                             "relleno_gamma_sat": 19.0}).get_json()
    pesado = cl.post("/api/analizar", json={**_GEO, "nivel_freatico_H": 4.0,
                                            "relleno_gamma_sat": 22.0}).get_json()
    # mayor γ_sat → mayor γ' → mayor empuje efectivo bajo el N.F.
    assert pesado["totales"]["SH_empuje"] > liviano["totales"]["SH_empuje"]


# --------------------------------------------------------------------------
# Diente / llave de cortante
# --------------------------------------------------------------------------
def _fs_desliz(resp):
    for row in resp["verificaciones"]:
        if "Deslizamiento" in row[0] or "deslizamiento" in row[0].lower():
            return float(row[1])
    raise AssertionError("no se encontró la verificación de deslizamiento")


def test_api_muro_diente_mejora_deslizamiento():
    cl = _client()
    sin = cl.post("/api/analizar", json=_GEO).get_json()
    con = cl.post("/api/analizar", json={**_GEO, "h_diente": 0.6, "b_diente": 0.4}).get_json()
    assert sin["ok"] and con["ok"]
    # el diente aumenta el empuje pasivo → mayor FS al deslizamiento
    assert _fs_desliz(con) > _fs_desliz(sin)


# --------------------------------------------------------------------------
# Carga lineal (Boussinesq)
# --------------------------------------------------------------------------
def test_empuje_linea_positivo_y_nulo():
    e = EmpujeSuelo.calcular_empuje_linea(q_l=50.0, a=1.0, H=6.0)
    assert e.componente_h > 0.0
    assert 0.0 <= e.y_aplicacion <= 6.0
    # sin carga → empuje nulo
    e0 = EmpujeSuelo.calcular_empuje_linea(q_l=0.0, a=1.0, H=6.0)
    assert e0.componente_h == 0.0


def test_empuje_linea_mas_cerca_mayor_empuje():
    cerca = EmpujeSuelo.calcular_empuje_linea(q_l=50.0, a=0.6, H=6.0)
    lejos = EmpujeSuelo.calcular_empuje_linea(q_l=50.0, a=3.0, H=6.0)
    # una carga más próxima al muro produce mayor empuje resultante
    assert cerca.componente_h > lejos.componente_h


def test_api_muro_carga_lineal_aumenta_empuje():
    cl = _client()
    sin = cl.post("/api/analizar", json=_GEO).get_json()
    con = cl.post("/api/analizar", json={**_GEO, "carga_lineal": 10.0,
                                         "carga_lineal_dist": 1.0}).get_json()
    assert sin["ok"] and con["ok"]
    # la carga lineal añade empuje horizontal → mayor SH_empuje
    assert con["totales"]["SH_empuje"] > sin["totales"]["SH_empuje"]


# --------------------------------------------------------------------------
# Estabilidad global (método de dovelas)
# --------------------------------------------------------------------------
def test_global_phi0_fellenius_igual_bishop():
    """Con φ=0 los métodos Fellenius y Bishop deben coincidir exactamente."""
    from retaining_wall.core.estabilidad_global import EstabilidadGlobalMuro
    m = _muro_para_global(phi_rel=0.001, c_rel=60.0, phi_cim=0.001, c_cim=80.0,
                          alpha=0.0)
    an = EstabilidadGlobalMuro(m)
    r = an.analizar_circulo(1.0, 12.0, 13.0)
    assert r is not None
    assert math.isclose(r["FS_fellenius"], r["FS_bishop"], rel_tol=1e-3)


def test_global_cohesion_lineal_con_phi0():
    """Con φ=0, FS es proporcional a la cohesión (duplicar c → duplicar FS)."""
    from retaining_wall.core.estabilidad_global import EstabilidadGlobalMuro
    m1 = _muro_para_global(phi_rel=0.001, c_rel=60.0, phi_cim=0.001, c_cim=80.0)
    m2 = _muro_para_global(phi_rel=0.001, c_rel=120.0, phi_cim=0.001, c_cim=160.0)
    r1 = EstabilidadGlobalMuro(m1).analizar_circulo(1.0, 12.0, 13.0)
    r2 = EstabilidadGlobalMuro(m2).analizar_circulo(1.0, 12.0, 13.0)
    assert math.isclose(r2["FS_fellenius"] / r1["FS_fellenius"], 2.0, rel_tol=1e-2)


def test_global_bishop_mayor_o_igual_que_fellenius():
    """Bishop simplificado es menos conservador que Fellenius (FS_B ≥ FS_F)."""
    from retaining_wall.core.estabilidad_global import EstabilidadGlobalMuro
    r = EstabilidadGlobalMuro(_muro_para_global()).buscar_critico("bishop")
    assert r.FS_bishop >= r.FS_fellenius - 1e-6


def test_global_cohesion_aumenta_FS():
    from retaining_wall.core.estabilidad_global import EstabilidadGlobalMuro
    baja = EstabilidadGlobalMuro(_muro_para_global(c_cim=10.0)).buscar_critico()
    alta = EstabilidadGlobalMuro(_muro_para_global(c_cim=80.0)).buscar_critico()
    assert alta.FS_min > baja.FS_min


def test_global_agua_reduce_FS():
    from retaining_wall.core.estabilidad_global import EstabilidadGlobalMuro
    seco = EstabilidadGlobalMuro(_muro_para_global(c_cim=15.0)).buscar_critico()
    mojado = EstabilidadGlobalMuro(
        _muro_para_global(c_cim=15.0, nf=6.0)).buscar_critico()
    assert mojado.FS_min < seco.FS_min
    assert mojado.incluye_agua


def test_api_estabilidad_global_presente():
    cl = _client()
    r = cl.post("/api/analizar", json=_GEO).get_json()
    assert r["ok"]
    eg = r["estabilidad_global"]
    assert eg["disponible"]
    assert eg["metodo"] == "bishop"
    assert 0.3 < eg["FS_min"] < 10.0
    assert eg["circulo"]["n_dovelas"] > 5
    assert eg["imagen_raw"]         # se generó el diagrama


def test_api_estabilidad_global_agua_reduce_FS():
    cl = _client()
    seco = cl.post("/api/analizar",
                   json={**_GEO, "ciment_cohesion": 15.0}).get_json()
    mojado = cl.post("/api/analizar",
                     json={**_GEO, "ciment_cohesion": 15.0,
                           "nivel_freatico_H": 6.0}).get_json()
    assert (mojado["estabilidad_global"]["FS_min"]
            < seco["estabilidad_global"]["FS_min"])


# --------------------------------------------------------------------------
# Muro con contrafuertes
# --------------------------------------------------------------------------
def test_contrafuertes_diseno_basico():
    from retaining_wall.core.contrafuertes import DisenadorContrafuertes
    m = _muro_para_global(alpha=0.0, q=12.0)
    d = DisenadorContrafuertes(m, separacion=3.0,
                               espesor_contrafuerte=0.4).disenar()
    assert d.Ka > 0
    assert d.pantalla["As_req_mm2_m"] >= d.pantalla["As_min_mm2_m"] > 0
    assert d.talon["Mu_kNm_m"] > 0
    assert d.contrafuerte["Mu_kNm"] > 0
    assert d.contrafuerte["As_req_mm2"] > 0


def test_contrafuertes_separacion_aumenta_momento():
    from retaining_wall.core.contrafuertes import DisenadorContrafuertes
    m = _muro_para_global(alpha=0.0, q=0.0)
    corta = DisenadorContrafuertes(m, 2.5, 0.4).disenar()
    larga = DisenadorContrafuertes(m, 4.0, 0.4).disenar()
    # M = w·s²/10 → mayor separación, mayor momento en la pantalla
    assert larga.pantalla["Mu_kNm_m"] > corta.pantalla["Mu_kNm_m"]


def test_api_contrafuertes_seccion_presente():
    cl = _client()
    r = cl.post("/api/analizar", json={
        **_GEO, "tipo_muro": "contrafuertes",
        "contrafuerte_sep": 3.0, "contrafuerte_espesor": 0.4}).get_json()
    assert r["ok"]
    assert r["tipo_muro"] == "contrafuertes"
    cf = r["contrafuertes"]
    assert cf["disponible"]
    assert len(cf["tabla_rows"]) == 3


def test_contrafuertes_estabilidad_externa_igual_voladizo():
    """Con la misma geometría, la estabilidad externa del muro con
    contrafuertes coincide con la del voladizo equivalente."""
    cl = _client()
    vol = cl.post("/api/analizar", json=_GEO).get_json()
    con = cl.post("/api/analizar",
                  json={**_GEO, "tipo_muro": "contrafuertes"}).get_json()
    assert math.isclose(vol["totales"]["SH_empuje"],
                        con["totales"]["SH_empuje"], rel_tol=1e-6)
    assert math.isclose(vol["totales_momentos"]["FS_volcamiento"],
                        con["totales_momentos"]["FS_volcamiento"], rel_tol=1e-6)
