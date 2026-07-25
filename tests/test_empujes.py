"""Pruebas analíticas del motor de empujes (retaining_wall/core/empujes.py).

Todas las aserciones se contrastan contra la fórmula cerrada o contra un valor
de mano verificable — NO contra la propia salida del programa. Correr con:

    pytest tests/test_empujes.py
    # o de forma autónoma:
    python tests/run_all.py
"""
import math

try:
    from retaining_wall.core.empujes import EmpujeSuelo as E
    from retaining_wall.utils.validaciones import ParametroSueloInvalidoError
except ModuleNotFoundError:  # ejecución directa sin conftest
    import os, sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "python"))
    from retaining_wall.core.empujes import EmpujeSuelo as E
    from retaining_wall.utils.validaciones import ParametroSueloInvalidoError

TOL = 1e-4


def _ka_rankine_cerrada(phi_deg, alpha_deg):
    """Fórmula cerrada de Rankine con talud (independiente del código)."""
    phi = math.radians(phi_deg); a = math.radians(alpha_deg)
    if alpha_deg == 0.0:
        return math.tan(math.pi / 4 - phi / 2) ** 2
    ca, cp = math.cos(a), math.cos(phi)
    raiz = math.sqrt(ca ** 2 - cp ** 2)
    return ca * (ca - raiz) / (ca + raiz)


# ─────────────────────────── Coeficientes ───────────────────────────────
def test_ka_rankine_horizontal_es_tan2():
    for phi in (20, 25, 30, 34, 40):
        esperado = math.tan(math.radians(45 - phi / 2)) ** 2
        assert abs(E.calcular_ka_rankine(phi, 0.0) - esperado) < TOL


def test_ka_rankine_con_talud_formula_cerrada():
    # φ=30, α=10 → 0.3495 (fórmula cerrada de Rankine, verificada a mano)
    assert abs(E.calcular_ka_rankine(30, 10) - 0.34953) < 1e-4
    for phi, a in ((34, 10), (35, 15), (40, 20)):
        assert abs(E.calcular_ka_rankine(phi, a) - _ka_rankine_cerrada(phi, a)) < TOL


def test_kp_rankine():
    assert abs(E.calcular_kp_rankine(20) - 2.0396) < 1e-3
    assert abs(E.calcular_kp_rankine(30) - 3.0) < 1e-3
    # Ka·Kp = 1 para relleno horizontal
    assert abs(E.calcular_ka_rankine(30, 0) * E.calcular_kp_rankine(30) - 1.0) < TOL


def test_coulomb_se_reduce_a_rankine():
    """Coulomb con δ=0, muro vertical (β=90) y relleno horizontal (α=0)
    debe coincidir con Rankine horizontal."""
    for phi in (25, 30, 35):
        kc = E.calcular_ka_coulomb(phi, 0.0, 90.0, 0.0)
        kr = E.calcular_ka_rankine(phi, 0.0)
        assert abs(kc - kr) < TOL


def test_mononobe_okabe_reduce_a_coulomb_sin_sismo():
    """Kae con kh=kv=0 debe coincidir con Ka de Coulomb."""
    for phi in (28, 30, 34):
        kae = E.calcular_kae_mononobe_okabe(phi, 0.0, 90.0, 0.0, kh=0.0, kv=0.0)
        kc = E.calcular_ka_coulomb(phi, 0.0, 90.0, 0.0)
        assert abs(kae - kc) < 1e-3


def test_mononobe_okabe_crece_con_kh():
    base = E.calcular_kae_mononobe_okabe(30, 15, 90, 0, kh=0.0, kv=0.0)
    for kh in (0.05, 0.10, 0.20):
        assert E.calcular_kae_mononobe_okabe(30, 15, 90, 0, kh=kh, kv=0.0) > base


# ─────────────────────────── Fuerzas ────────────────────────────────────
def test_empuje_activo_magnitud_y_componentes():
    g, H, phi, a = 18.0, 6.0, 30.0, 10.0
    e = E.calcular_empuje_activo_rankine(g, H, phi, a)
    Ka = E.calcular_ka_rankine(phi, a)
    assert abs(e.magnitud - 0.5 * g * H ** 2 * Ka) < 1e-6
    assert abs(e.componente_h - e.magnitud * math.cos(math.radians(a))) < 1e-9
    assert abs(e.componente_v - e.magnitud * math.sin(math.radians(a))) < 1e-9
    assert abs(e.y_aplicacion - H / 3.0) < 1e-9   # triangular → tercio inferior


def test_empuje_activo_con_cohesion_reduce_y_acota_a_cero():
    # c' grande + H pequeño → empuje neto acotado a 0 (grieta de tracción)
    e = E.calcular_empuje_activo_rankine(18.0, 1.0, 30.0, 0.0, cohesion=100.0)
    assert e.magnitud == 0.0
    # Con cohesión moderada, el empuje baja respecto al granular
    sin_c = E.calcular_empuje_activo_rankine(18.0, 6.0, 30.0, 0.0, cohesion=0.0)
    con_c = E.calcular_empuje_activo_rankine(18.0, 6.0, 30.0, 0.0, cohesion=10.0)
    assert con_c.magnitud < sin_c.magnitud


def test_empuje_pasivo_formula():
    g, H, phi, c = 19.0, 1.5, 20.0, 40.0
    e = E.calcular_empuje_pasivo_rankine(g, H, phi, c)
    Kp = E.calcular_kp_rankine(phi)
    esperado = 0.5 * Kp * g * H ** 2 + 2.0 * c * math.sqrt(Kp) * H
    assert abs(e.magnitud - esperado) < 1e-6


def test_empuje_sobrecarga_rectangular():
    q, H, phi = 15.0, 6.0, 30.0
    e = E.calcular_empuje_sobrecarga(q, H, phi, 0.0)
    Ka = E.calcular_ka_rankine(phi, 0.0)
    assert abs(e.magnitud - Ka * q * H) < 1e-6
    assert abs(e.y_aplicacion - H / 2.0) < 1e-9   # rectangular → mitad de la altura


# ─────────────────────────── Validaciones ───────────────────────────────
def test_talud_mayor_que_phi_lanza_error():
    err = False
    try:
        E.calcular_ka_rankine(30, 35)      # α > φ es indefinido
    except Exception as ex:
        err = isinstance(ex, ParametroSueloInvalidoError) or "α" in str(ex) or "alpha" in str(ex).lower()
    assert err
