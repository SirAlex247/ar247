"""Validación contra los ejemplos de Braja M. Das
(*Fundamentos de ingeniería de cimentaciones*, cap. 8).

Estas pruebas comparan contra una FUENTE EXTERNA independiente (los resultados
publicados en el libro), no contra la salida del propio programa. Geometrías y
datos tomados directamente de las figuras 8.12 (Ej. 8.1) y 8.13 (Ej. 8.2).

Sobre las tolerancias del Ej. 8.1: Das toma Ka = 0.3532 de la tabla 7.1,
mientras que la fórmula cerrada de Rankine con talud da 0.3495 (~1% menor).
Por eso los FS del programa quedan ~1% por encima de los del libro (el propio
libro y el README documentan esta diferencia). Las tolerancias lo contemplan.
"""
try:
    import app
except ModuleNotFoundError:
    import os, sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "python"))
    import app


def _verif(r):
    return {x["nombre"]: x for x in r["verificaciones_raw"]}


def _fs(r, prefijo):
    return next(x["valor"] for x in r["verificaciones_raw"]
               if x["nombre"].startswith(prefijo))


def _rel(app_val, das_val):
    return abs(app_val - das_val) / abs(das_val)


# ═══════════════════════ Ejemplo 8.1 — Voladizo (Fig. 8.12) ══════════════
# Vástago 6 m, zapata 0.7 m, puntera 0.7 m, talón 2.6 m, corona 0.5 m,
# base vástago 0.7 m (B = 4.0 m), D = 1.5 m, relleno inclinado α = 10°.
DAS_8_1 = {
    "tipo_muro": "voladizo",
    "H_vastago": 6.0, "e_zapata": 0.7, "b_puntera": 0.7, "b_talon": 2.6,
    "b_corona": 0.5, "b_base_vast": 0.7, "D": 1.5, "H_relleno": 6.0,
    "cara_posterior_vertical": True,
    "relleno_gamma": 18.0, "relleno_phi": 30.0, "relleno_cohesion": 0.0,
    "ciment_gamma": 19.0, "ciment_phi": 20.0, "ciment_cohesion": 40.0,
    "concreto_fc": 21.0, "concreto_gamma": 23.58, "acero_fy": 420.0,
    "alpha": 10.0, "sobrecarga": 0.0, "metodo_empuje": "rankine",
}


def test_das_8_1_factores_de_seguridad():
    r = app.ejecutar_analisis(DAS_8_1)
    assert _rel(_fs(r, "Factor de Seguridad al Volcamiento"), 2.95) < 0.03
    assert _rel(_fs(r, "Factor de Seguridad al Deslizamiento"), 2.70) < 0.03
    # Das obtiene FS(capacidad) = 2.98; el programa ~3.0 (misma diferencia de Ka).
    assert _rel(_fs(r, "FS por Capacidad de Carga"), 2.98) < 0.05


def test_das_8_1_presiones_y_excentricidad():
    r = app.ejecutar_analisis(DAS_8_1)
    pr = r["presiones_raw"]
    assert abs(pr["e_m"] - 0.411) < 0.02
    assert abs(pr["q_puntera_kPa"] - 190.2) < 4.0     # q en la puntera (pie)
    assert abs(pr["q_talon_kPa"] - 45.13) < 4.0


# ═══════════════════════ Ejemplo 8.2 — Gravedad (Fig. 8.13) ══════════════
# Cuerpo 5.7 m, zapata 0.8 m, corona 0.6 m, acartelado frontal 0.27 m,
# acartelado posterior 1.53 m (β = 75°), puntera 0.8 m, talón 0.3 m
# (B = 3.5 m), D = 1.5 m, Coulomb con δ' = 2/3·φ'₁.
DAS_8_2 = {
    "tipo_muro": "gravedad",
    "H_muro": 5.7, "e_zapata": 0.8, "b_corona": 0.6,
    "a_frontal": 0.27, "a_posterior": 1.53,
    "b_puntera": 0.8, "b_talon": 0.3, "D": 1.5,
    "relleno_gamma": 18.5, "relleno_phi": 32.0, "relleno_cohesion": 0.0,
    "ciment_gamma": 18.0, "ciment_phi": 24.0, "ciment_cohesion": 30.0,
    "concreto_fc": 21.0, "concreto_gamma": 23.58, "acero_fy": 420.0,
    "alpha": 0.0, "sobrecarga": 0.0, "metodo_empuje": "coulomb",
}


def test_das_8_2_factores_de_seguridad():
    r = app.ejecutar_analisis(DAS_8_2)
    assert abs(r["totales_momentos"]["FS_volcamiento"] - 2.67) < 0.03
    assert abs(_fs(r, "Factor de Seguridad al Deslizamiento") - 2.84) < 0.03


def test_das_8_2_presiones_y_excentricidad():
    r = app.ejecutar_analisis(DAS_8_2)
    pr = r["presiones_raw"]
    assert abs(pr["e_m"] - 0.483) < 0.02
    assert abs(pr["q_puntera_kPa"] - 188.43) < 3.0
    assert abs(pr["q_talon_kPa"] - 17.73) < 3.0


def test_das_8_2_beta_geometria_75_grados():
    """La cara posterior batida debe dar β ≈ 75° (atan(5.7/1.53))."""
    muro, _ = app.construir_muro_desde_datos(DAS_8_2)
    assert abs(muro.geometria.beta_grados - 75.0) < 0.5
