"""Pruebas de la estabilidad externa de muros por la CCP-14 (LRFD).

Verifican el mapeo de cargas a tipos AASHTO, los factores γ/φ de la norma, los
límites de excentricidad (Art. 11.6.3.3 / 11.6.5.1) y la coherencia de las
relaciones capacidad/demanda (CDR). El motor NSR-10 no se altera: sus pruebas
(test_estabilidad, test_das) siguen siendo la referencia de no-regresión.
"""
from __future__ import annotations

import math

from retaining_wall.models.material import MaterialesComunes
from retaining_wall.models.muro import CondicionesCarga, GeometriaMuro, MuroContencion
from retaining_wall.models.suelo import Suelo
from retaining_wall.core.cargas import CalculadoraCargas
from retaining_wall.core.estabilidad_ccp14 import AnalisisEstabilidadCCP14
from retaining_wall.core.diseno_estructural_ccp14 import (
    DisenadorMuroVoladizoCCP14,
    DisenoSeccionCCP14,
    PHI_CORTANTE,
    PHI_FLEXION,
)
from retaining_wall.models.material import MaterialesComunes as _MC
from retaining_wall.normas import ccp14, normalizar_norma, NORMA_CCP14, NORMA_NSR10


def _muro_demo(**cond):
    geo = GeometriaMuro(H_vastago=6.0, e_zapata=0.7, b_puntera=0.7, b_talon=2.6,
                        b_corona=0.5, b_base_vast=0.7, D=1.5)
    return MuroContencion(
        geometria=geo,
        suelo_relleno=Suelo(gamma=18.0, phi=30.0, nombre="Relleno"),
        suelo_cimentacion=Suelo(gamma=19.0, phi=20.0, cohesion=40.0, nombre="Cim"),
        concreto=MaterialesComunes.concreto_21(),
        acero=MaterialesComunes.acero_420(),
        condiciones=CondicionesCarga(**cond),
    )


# ---------------------------------------------------------------------------
def test_normalizar_norma():
    assert normalizar_norma("ccp14") == NORMA_CCP14
    assert normalizar_norma("CCP-14") == NORMA_CCP14
    assert normalizar_norma("aashto") == NORMA_CCP14
    assert normalizar_norma("nsr10") == NORMA_NSR10
    assert normalizar_norma(None) == NORMA_NSR10
    assert normalizar_norma("cualquier-cosa") == NORMA_NSR10


def test_clasificacion_aashto():
    muro = _muro_demo(alpha=10.0)
    sis = CalculadoraCargas(muro).calcular()
    tipos = {ccp14.tipo_aashto(c) for c in sis.cargas}
    # El muro con relleno inclinado genera DC, EV, EH, EH_V y EP
    assert {ccp14.DC, ccp14.EV, ccp14.EH, ccp14.EH_V, ccp14.EP} <= tipos
    # El concreto es DC y el suelo sobre el talón es EV
    for c in sis.cargas:
        if c.material == "concreto":
            assert ccp14.tipo_aashto(c) == ccp14.DC
        elif c.material in ("suelo_relleno", "suelo_cimentacion"):
            assert ccp14.tipo_aashto(c) == ccp14.EV


def test_limites_excentricidad():
    B = 4.0
    assert math.isclose(ccp14.limite_excentricidad(B), B / 3.0)
    assert math.isclose(ccp14.limite_excentricidad(B, apoyo_roca=True), 0.45 * B)
    # Sísmico: γ_EQ=0 → B/3 ; γ_EQ=1 → 0.4B ; interpola
    assert math.isclose(ccp14.limite_excentricidad(B, gamma_EQ=0.0), B / 3.0)
    assert math.isclose(ccp14.limite_excentricidad(B, gamma_EQ=1.0), 0.40 * B)
    medio = ccp14.limite_excentricidad(B, gamma_EQ=0.5)
    assert B / 3.0 < medio < 0.40 * B


def test_mayoracion_capacidad_coincide_con_calculo_manual():
    """ΣV mayorado del caso de capacidad = DC·1.25 + EV·1.35 + EH_V·1.50."""
    muro = _muro_demo(alpha=10.0)
    sis = CalculadoraCargas(muro).calcular()
    v = {ccp14.DC: 0.0, ccp14.EV: 0.0, ccp14.EH_V: 0.0}
    for c in sis.cargas:
        t = ccp14.tipo_aashto(c)
        if t in v and c.tipo.value == "vertical":
            v[t] += c.magnitud * c.sentido
    esperado = v[ccp14.DC] * 1.25 + v[ccp14.EV] * 1.35 + v[ccp14.EH_V] * 1.50

    an = AnalisisEstabilidadCCP14(muro, sis)
    r = an._factorizar(ccp14.FACTORES_RESISTENCIA_I_CAPACIDAD)
    assert math.isclose(r["SV"], esperado, rel_tol=1e-9), (r["SV"], esperado)


def test_cdr_todos_mayores_que_uno_para_muro_bien_dimensionado():
    """Un muro que pasa NSR-10 con FS≈3 debe pasar CCP-14 con CDR ≥ 1.0."""
    muro = _muro_demo(alpha=10.0)
    sis = CalculadoraCargas(muro).calcular()
    rep = AnalisisEstabilidadCCP14(muro, sis).analisis_completo()
    assert rep.excentricidad.cumple
    assert rep.deslizamiento.valor_calculado >= 1.0
    assert rep.capacidad_carga.valor_calculado >= 1.0
    assert rep.volcamiento.valor_calculado >= 1.0
    assert rep.cumple_todas


def test_capacidad_usa_phi_055_y_ancho_efectivo():
    muro = _muro_demo(alpha=10.0)
    sis = CalculadoraCargas(muro).calcular()
    an = AnalisisEstabilidadCCP14(muro, sis)
    res = an.verificar_capacidad_carga()
    d = res.detalle
    assert math.isclose(d["phi_b"], 0.55)
    # σ_v = ΣV/(B−2e) y q_R = φ_b·q_n
    assert math.isclose(d["q_R_kPa"], 0.55 * d["q_n_kPa"], rel_tol=1e-9)
    assert d["B_ef"] < muro.B


def test_deslizamiento_phi_por_tipo_de_suelo():
    # Cimentación cohesiva (c=40) → arcilla → φ_τ = 0.85
    muro_arc = _muro_demo(alpha=10.0)
    an = AnalisisEstabilidadCCP14(muro_arc, CalculadoraCargas(muro_arc).calcular())
    assert math.isclose(an.verificar_deslizamiento().detalle["phi_tau"], 0.85)
    # Cimentación granular (c=0) → arena → φ_τ = 0.80
    geo = GeometriaMuro(H_vastago=6.0, e_zapata=0.7, b_puntera=0.7, b_talon=2.6,
                        b_corona=0.5, b_base_vast=0.7, D=1.5)
    muro_arena = MuroContencion(
        geometria=geo,
        suelo_relleno=Suelo(gamma=18.0, phi=30.0, nombre="Relleno"),
        suelo_cimentacion=Suelo(gamma=19.0, phi=32.0, cohesion=0.0, nombre="Cim"),
        concreto=MaterialesComunes.concreto_21(),
        acero=MaterialesComunes.acero_420(),
        condiciones=CondicionesCarga(alpha=10.0))
    an2 = AnalisisEstabilidadCCP14(muro_arena, CalculadoraCargas(muro_arena).calcular())
    assert math.isclose(an2.verificar_deslizamiento().detalle["phi_tau"], 0.80)


def test_evento_extremo_reduce_cdr():
    """Con sismo (Evento Extremo I) las CDR gobernantes no deben ser mayores."""
    muro = _muro_demo(alpha=10.0, kh=0.15, kv=0.0)
    sis = CalculadoraCargas(muro).calcular(incluir_sismo=True)
    est = AnalisisEstabilidadCCP14(muro, sis, incluir_sismo=False)
    sis_e = CalculadoraCargas(muro).calcular(incluir_sismo=True)
    ee = AnalisisEstabilidadCCP14(muro, sis_e, incluir_sismo=True, gamma_EQ=0.5)
    # El caso sísmico agrega empuje motriz → deslizamiento no mejora
    assert (ee.verificar_deslizamiento().valor_calculado
            <= est.verificar_deslizamiento().valor_calculado + 1e-9)
    # El límite de excentricidad sísmico admitido nunca es menor que B/3
    # (el motor redondea el límite a 4 decimales → se compara con esa tolerancia).
    assert ee.verificar_excentricidad().valor_requerido >= round(muro.B / 3.0, 4) - 1e-9


# ===========================================================================
# Diseño estructural CCP-14 (Sección 5)
# ===========================================================================
def test_ccp14_factores_phi():
    assert math.isclose(PHI_FLEXION, 0.90)
    assert math.isclose(PHI_CORTANTE, 0.90)   # concreto normal (NSR-10 usa 0.75)


def test_ccp14_cortante_phi_090_y_usa_dv():
    """φV_c = 0.90·V_c y d_v = máx(0.9·d, 0.72·h)."""
    concreto = _MC.concreto_21()
    h = 0.70
    rec, phib = 0.075, 0.0191
    cort = DisenoSeccionCCP14.verificar_cortante(
        Vu=100.0, b=1.0, h=h, concreto=concreto, recubrimiento=rec, phi_barra=phib)
    assert math.isclose(cort.phi_Vc, 0.90 * cort.Vc, rel_tol=1e-9)
    d = h - rec - phib / 2.0
    dv = max(0.9 * d, 0.72 * h)
    Vc_esperado = 0.083 * 2.0 * concreto.lambda_factor * math.sqrt(concreto.fc) \
        * 1000.0 * (dv * 1000.0) / 1000.0
    assert math.isclose(cort.Vc, Vc_esperado, rel_tol=1e-9)


def test_ccp14_refuerzo_minimo_mcr():
    """Con Mu muy pequeño, controla el refuerzo mínimo mín(1.33·Mu, M_cr)."""
    concreto = _MC.concreto_21()
    acero = _MC.acero_420()
    fx = DisenoSeccionCCP14.disenar_flexion(
        Mu=5.0, b=1.0, h=0.70, concreto=concreto, acero=acero,
        recubrimiento=0.075, phi_barra=0.0191)
    # Con Mu=5, 1.33·Mu=6.65 kN·m es mucho menor que M_cr → el objetivo es 6.65
    assert any("mínimo" in o.lower() for o in fx.observaciones)
    # φMn con As adoptado desarrolla al menos min(1.33·Mu, Mcr)
    assert fx.phi_Mn >= 1.33 * 5.0 - 1e-6
    assert fx.As_adoptado > 0.0


def test_ccp14_diseno_estructural_completo():
    muro = _muro_demo(alpha=10.0)
    sis = CalculadoraCargas(muro).calcular()
    rep = DisenadorMuroVoladizoCCP14(muro).disenar(sis)
    # El vástago (empuje 1.50) tiene Mu menor que el equivalente NSR-10 (1.6)
    assert rep.vastago.flexion.Mu > 0
    assert rep.cumple_todo
    # El cortante debe cumplir con holgura (φ=0.90 y d_v)
    assert rep.vastago.cortante.cumple
    assert rep.punta.cortante.cumple
    assert rep.talon.cortante.cumple


def test_ccp14_presion_contacto_redistribuye_sin_tension():
    """Un muro con excentricidad mayorada alta no produce presiones negativas."""
    muro = _muro_demo(alpha=10.0, sobrecarga=40.0)
    sis = CalculadoraCargas(muro).calcular()
    dis = DisenadorMuroVoladizoCCP14(muro)
    SV, e = dis._estado_contacto(sis)
    # La presión evaluada en cualquier x del ancho es no negativa
    B = muro.B
    for i in range(0, 11):
        x = B * i / 10.0
        assert dis._q_contacto(x, SV, e) >= -1e-9
