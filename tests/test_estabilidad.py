"""Identidades de equilibrio y propiedades de monotonicidad de la estabilidad.

Se ejecuta el CAMINO REAL de la app (``app.ejecutar_analisis``) y se verifica
que los resultados cumplen relaciones físicas exactas y tendencias esperadas.
No se congelan magnitudes aquí (eso es test_pipeline_muro.py); se comprueban
invariantes que deben cumplirse para CUALQUIER geometría válida.
"""
import copy

try:
    import app
except ModuleNotFoundError:
    import os, sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "python"))
    import app

try:
    from tests.fixtures import MURO_VOLADIZO, MURO_GRAVEDAD
except ModuleNotFoundError:
    from fixtures import MURO_VOLADIZO, MURO_GRAVEDAD


def _run(**overrides):
    d = copy.deepcopy(MURO_VOLADIZO)
    d.update(overrides)
    return app.ejecutar_analisis(d)


def _B(res):
    return res["muro_resumen_raw"]["B_total_m"]


# ─────────────────────────── Identidades exactas ────────────────────────
def test_presiones_lineales_desde_SV_y_e():
    r = _run()
    SV = r["presiones_raw"]["SV_kN"]      # crudo: totales["SV"] viene redondeado
    B = _B(r)
    e = r["presiones_raw"]["e_m"]
    q_p = (SV / B) * (1.0 + 6.0 * e / B)
    q_t = (SV / B) * (1.0 - 6.0 * e / B)
    assert abs(r["presiones_raw"]["q_puntera_kPa"] - q_p) < 1e-6
    assert abs(r["presiones_raw"]["q_talon_kPa"] - q_t) < 1e-6


def test_ancho_efectivo_B_prima():
    r = _run()
    B = _B(r)
    e = r["presiones_raw"]["e_m"]
    assert abs(r["presiones_raw"]["B_prima_m"] - (B - 2.0 * abs(e))) < 1e-6


def test_presion_media_identidad():
    """(q_puntera + q_talón)/2 = ΣV/B (media del diagrama trapezoidal)."""
    r = _run()
    SV = r["presiones_raw"]["SV_kN"]; B = _B(r)
    media = 0.5 * (r["presiones_raw"]["q_puntera_kPa"] + r["presiones_raw"]["q_talon_kPa"])
    assert abs(media - SV / B) < 1e-6


def test_fs_volcamiento_es_cociente_de_momentos():
    r = _run()
    SMR = r["totales"]["SMR"]; SMo = r["totales"]["SMo"]
    assert abs(r["totales_momentos"]["FS_volcamiento"] - SMR / SMo) < 1e-3


def test_caso_bien_planteado_sin_tension():
    """En un muro que aprueba, |e| ≤ B/6 y no hay presiones de tracción."""
    r = _run()
    B = _B(r)
    e = r["presiones_raw"]["e_m"]
    assert abs(e) <= B / 6.0 + 1e-9
    assert r["presiones_raw"]["q_talon_kPa"] >= 0.0
    assert r["presiones_raw"]["q_puntera_kPa"] >= r["presiones_raw"]["q_talon_kPa"]


# ─────────────────────────── Monotonicidad ──────────────────────────────
def test_mas_sobrecarga_reduce_FS_volcamiento():
    base = _run(sobrecarga=0.0)["totales_momentos"]["FS_volcamiento"]
    alta = _run(sobrecarga=25.0)["totales_momentos"]["FS_volcamiento"]
    assert alta < base


def test_muro_mas_alto_reduce_FS_volcamiento():
    bajo = _run(H_vastago=6.0, H_relleno=6.0)["totales_momentos"]["FS_volcamiento"]
    alto = _run(H_vastago=8.0, H_relleno=8.0)["totales_momentos"]["FS_volcamiento"]
    assert alto < bajo


def test_talon_mas_ancho_aumenta_FS_volcamiento():
    angosto = _run(b_talon=2.6)["totales_momentos"]["FS_volcamiento"]
    ancho = _run(b_talon=3.6)["totales_momentos"]["FS_volcamiento"]
    assert ancho > angosto


def test_cohesion_cimentacion_aumenta_FS_deslizamiento():
    def fs_desl(res):
        return next(v["valor"] for v in res["verificaciones_raw"]
                    if v["nombre"].startswith("Factor de Seguridad al Desl"))
    poca = fs_desl(_run(ciment_cohesion=0.0))
    mucha = fs_desl(_run(ciment_cohesion=60.0))
    assert mucha > poca


# ───────────── Redistribución de presiones (Meyerhof, e > B/6) ───────────
def test_dentro_del_nucleo_no_redistribuye():
    """Caso bien planteado (|e| ≤ B/6): distribución lineal, sin redistribuir."""
    r = _run()
    assert r["presiones_raw"]["redistribuido"] is False


def test_meyerhof_redistribucion_formula_y_equilibrio():
    """Fuera del núcleo (|e| > B/6): q_máx = 2ΣV/(3·(B/2−|e|)), extremo opuesto
    en 0 (sin tracción) y equilibrio de fuerzas 0.5·q_máx·L = ΣV."""
    r = app.ejecutar_analisis(MURO_GRAVEDAD)
    pr = r["presiones_raw"]
    B, e, SV = pr["B_m"], pr["e_m"], pr["SV_kN"]
    assert abs(e) > B / 6.0                       # efectivamente fuera del núcleo
    assert pr["redistribuido"] is True
    brazo = B / 2.0 - abs(e)
    assert abs(pr["q_max_kPa"] - 2.0 * SV / (3.0 * brazo)) < 1e-6   # Meyerhof exacto
    assert min(pr["q_puntera_kPa"], pr["q_talon_kPa"]) == 0.0        # sin tracción
    assert abs(0.5 * pr["q_max_kPa"] * (3.0 * brazo) - SV) < 1e-6    # equilibrio
