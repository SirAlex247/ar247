"""Pruebas de caracterización del pipeline completo de muros.

Congelan las salidas ACTUALES del motor para los payloads canónicos, de modo
que cualquier cambio futuro que altere un resultado numérico dispare un fallo
visible (regresión). Los valores se capturaron con ``tests/_capture.py`` sobre
la versión validada del motor. Si un cambio de fórmula es intencional, hay que
actualizar estos valores conscientemente.

NOTA sobre tolerancias: se usan tolerancias absolutas pequeñas; el objetivo es
detectar cambios reales de comportamiento, no ruido de coma flotante.
"""
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


def _aprox(a, b, tol):
    assert abs(a - b) <= tol, f"esperado {b} ± {tol}, obtenido {a}"


def _verif(res):
    return {v["nombre"]: v for v in res["verificaciones_raw"]}


# ═══════════════════════════ VOLADIZO ════════════════════════════════════
def test_voladizo_totales_y_presiones():
    r = app.ejecutar_analisis(MURO_VOLADIZO)
    _aprox(r["totales"]["SV"], 439.90, 0.05)
    _aprox(r["totales"]["SMR"], 1089.35, 0.10)
    _aprox(r["totales"]["SMo"], 319.03, 0.10)
    _aprox(r["presiones_raw"]["q_puntera_kPa"], 151.03, 0.05)
    _aprox(r["presiones_raw"]["q_talon_kPa"], 68.92, 0.05)
    _aprox(r["presiones_raw"]["e_m"], 0.2489, 0.001)
    _aprox(r["presiones_raw"]["B_prima_m"], 3.502, 0.005)


def test_voladizo_factores_de_seguridad():
    v = _verif(app.ejecutar_analisis(MURO_VOLADIZO))
    _aprox(v["Factor de Seguridad al Volcamiento"]["valor"], 3.415, 0.005)
    _aprox(v["Factor de Seguridad al Deslizamiento"]["valor"], 3.186, 0.005)
    # FS de capacidad con inclinación de carga por empuje ACTUANTE (sin restar
    # el pasivo). Ver fix: la resta de Pp inflaba q_u de forma no conservadora.
    _aprox(v["FS por Capacidad de Carga"]["valor"], 3.939, 0.02)
    _aprox(v["Excentricidad |e| ≤ B/6"]["valor"], 0.249, 0.002)
    assert all(x["estado"] == "CUMPLE" for x in v.values())


def test_voladizo_diseno_estructural():
    r = app.ejecutar_analisis(MURO_VOLADIZO)
    dis = {d["nombre"]: d for d in r["diseno_raw"]}
    _aprox(dis["Vástago"]["Mu_kNm"], 374.87, 0.10)
    _aprox(dis["Vástago"]["As_mm2_por_m"], 2396.2, 1.0)
    _aprox(dis["Punta"]["Mu_kNm"], 85.71, 0.10)
    _aprox(dis["Talón"]["Mu_kNm"], 70.72, 0.10)
    assert all(d["estado"] == "OK" for d in r["diseno_raw"])
    assert "APROBADO" in r["resultado_global"]["estado"]


def test_voladizo_genera_imagenes():
    r = app.ejecutar_analisis(MURO_VOLADIZO)
    for k in ("imagen_muro_raw", "imagen_muro_nombres_raw",
              "imagen_muro_cotas_raw", "imagen_empujes_raw",
              "imagen_esfuerzos_zapata_raw"):
        assert r[k] and len(r[k]) > 100      # base64 no vacío


# ═══════════════════════════ GRAVEDAD ════════════════════════════════════
def test_gravedad_totales_y_verificaciones():
    r = app.ejecutar_analisis(MURO_GRAVEDAD)
    _aprox(r["totales_momentos"]["FS_volcamiento"], 2.047, 0.005)
    v = _verif(r)
    _aprox(v["Factor de Seguridad al Deslizamiento"]["valor"], 2.628, 0.005)
    # FS de capacidad sobre el q_máx REDISTRIBUIDO (Meyerhof) y con inclinación
    # de carga por empuje actuante (sin restar pasivo).
    _aprox(v["FS por Capacidad de Carga"]["valor"], 2.435, 0.02)


def test_gravedad_no_genera_combinaciones_ELU():
    """Los muros de gravedad no se diseñan por flexión → sin combinaciones
    últimas; solo se conservan las de servicio para verificar presiones."""
    r = app.ejecutar_analisis(MURO_GRAVEDAD)
    assert len(r["combinaciones_elu"]) == 0
    assert len(r["combinaciones_els"]) == 2
    assert r["diseno_raw"] == []


def test_gravedad_excentricidad_fuera_del_nucleo_redistribuye():
    """Con e > B/6 la resultante cae fuera del núcleo central. El motor
    redistribuye a un diagrama triangular (Meyerhof): la presión en el extremo
    en tracción se acota a 0 (NO negativa) y aparece un pico q_máx sobre una
    longitud de contacto reducida. Se verifica además el equilibrio de fuerzas
    (volumen del triángulo = ΣV).
    """
    r = app.ejecutar_analisis(MURO_GRAVEDAD)
    pr = r["presiones_raw"]
    v = _verif(r)
    assert v["Excentricidad |e| ≤ B/6"]["estado"] == "NO CUMPLE"
    assert pr["redistribuido"] is True
    # Ya NO hay tracción: el extremo del talón queda en 0, no negativo.
    assert pr["q_talon_kPa"] == 0.0
    assert pr["q_max_kPa"] > pr["q_puntera_kPa"] - 1e-9 and pr["q_max_kPa"] > 0
    # Equilibrio: 0.5 · q_máx · L_contacto = ΣV
    L = 3.0 * (pr["B_m"] / 2.0 - abs(pr["e_m"]))
    _aprox(0.5 * pr["q_max_kPa"] * L, pr["SV_kN"], 0.5)
