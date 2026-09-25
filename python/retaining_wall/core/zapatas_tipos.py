"""Diseño de zapatas por tipo (NSR-10 / ACI 318).

Amplía la zapata aislada (``zapata.disenar_zapata``) a los demás tipos:

    - aislada / concéntrica / excéntrica / cuadrada / rectangular
      → ``zapata.disenar_zapata`` (biaxial y relación L/B).
    - combinada   → dos columnas sobre una zapata rectangular; análisis de la
      zapata como viga longitudinal (momentos +/− y cortante) + flexión
      transversal bajo cada columna + punzonamiento por columna.
    - esquinera   → columna en la esquina (medianería en dos lados); se resuelve
      con presión biaxial excéntrica, con opción de viga centradora que
      "centra" la reacción para presión uniforme.
    - triangular  → zapata de planta triangular (columna en el baricentro),
      dimensionamiento geotécnico + verificación estructural simplificada.

Unidades SI internas: m, kN, kN·m, kPa (= kN/m²), MPa, kN/m³.
El despachador ``disenar_zapata_tipo`` recibe el ``tipo`` y el resto de
parámetros y devuelve un dict con la misma forma general
(``tipo``/``geometria``/``geotecnico``/``estructural``/``avisos``).
"""
from __future__ import annotations

import math

from .zapata import (
    PHI_CORTE,
    PHI_FLEX,
    _alpha_s,
    _area_barra,
    _cortante_una_via,
    _flexion,
    _redondea_arriba,
    disenar_zapata,
)


# ===========================================================================
# Helpers de bajo nivel adicionales
# ===========================================================================
def _As_de_Mu(Mu, b_ancho, d, fc, fy, rec, db, h):
    """Acero por flexión a partir de un momento último Mu (kN·m) dado.

    A diferencia de ``zapata._flexion`` (que calcula Mu de un voladizo con
    presión uniforme), aquí Mu ya viene del diagrama de la viga.
    """
    Mu = abs(Mu)
    fy_k, fc_k = fy * 1000.0, fc * 1000.0
    As = Mu / (PHI_FLEX * fy_k * 0.95 * d) if d > 0 else 0.0
    for _ in range(40):
        a = As * fy_k / (0.85 * fc_k * b_ancho) if b_ancho > 0 else 0.0
        nuevo = Mu / (PHI_FLEX * fy_k * (d - a / 2.0)) if (d - a / 2.0) > 0 else As
        if abs(nuevo - As) < 1e-8:
            As = nuevo
            break
        As = nuevo
    As_req = max(As, 0.0)
    As_min = 0.0018 * b_ancho * h
    As_fin = max(As_req, As_min)
    ab = _area_barra(db)
    n = max(2, math.ceil(As_fin / ab)) if ab > 0 else 0
    sep = (b_ancho - 2 * rec) / (n - 1) if n > 1 else 0.0
    return {
        "Mu_kNm": round(Mu, 1),
        "As_req_cm2": round(As_req * 1e4, 2),
        "As_min_cm2": round(As_min * 1e4, 2),
        "As_cm2": round(As_fin * 1e4, 2),
        "gobierna_minimo": As_min >= As_req,
        "n_barras": n, "db_mm": round(db * 1000.0, 1),
        "sep_cm": round(sep * 100.0, 1),
    }


def _punz_columna(Pu_col, qu, c1, c2, h, sqrt_fc, rec, db, posicion):
    """Punzonamiento (dos vías) alrededor de UNA columna sobre la zapata.

    Vu = Pu_col − qu·(c1+d)·(c2+d);  perímetro bo = 2(c1+d)+2(c2+d).
    """
    d = max(0.05, h - rec - db)
    a_int = (c1 + d) * (c2 + d)
    bo = 2.0 * (c1 + d) + 2.0 * (c2 + d)
    Vu = max(0.0, Pu_col - qu * a_int)
    beta_c = max(c1, c2) / min(c1, c2)
    alfa = _alpha_s(posicion)
    vc = min(0.33 * sqrt_fc,
             0.17 * (1.0 + 2.0 / beta_c) * sqrt_fc,
             0.083 * (alfa * d / bo + 2.0) * sqrt_fc)
    phiVc = PHI_CORTE * vc * 1000.0 * bo * d
    return {
        "d_m": round(d, 4), "b0_m": round(bo, 4), "vc_MPa": round(vc, 3),
        "Vu_kN": round(Vu, 1), "phiVc_kN": round(phiVc, 1),
        "ratio": round(Vu / phiVc, 3) if phiVc > 0 else None,
        "cumple": Vu <= phiVc,
    }


# ===========================================================================
# AISLADA (y sus variantes de carga/planta) — envuelve disenar_zapata
# ===========================================================================
def disenar_aislada(*, tipo="aislada", forma="cuadrada", **p) -> dict:
    """Zapata aislada bajo una columna.

    ``forma`` ∈ {cuadrada, rectangular} define la planta; los momentos
    M_servicio (Mx) y My_servicio determinan si la carga es concéntrica
    (ambos 0) o excéntrica (biaxial). No hay "tipos" separados para eso: es
    la misma zapata aislada parametrizada (Das cap. 3-4; Bowles cap. 8).
    """
    if forma == "rectangular":
        if not p.get("relacion_LB") or p.get("relacion_LB") <= 1.0:
            p["relacion_LB"] = 1.5
    else:
        forma = "cuadrada"
        p["relacion_LB"] = 1.0
    res = disenar_zapata(**p)
    res["tipo"] = "aislada"
    res["forma"] = forma
    m = abs(p.get("M_servicio", 0.0) or 0.0) + abs(p.get("My_servicio", 0.0) or 0.0)
    res["carga"] = "excéntrica" if m > 1e-9 else "concéntrica"
    return res


# ===========================================================================
# COMBINADA — dos columnas sobre una zapata rectangular (viga longitudinal)
# ===========================================================================
def disenar_combinada(*, c1a, c2a, P1_servicio, c1b, c2b, P2_servicio,
                      separacion, q_adm, medianeria_izquierda=True,
                      M1_servicio=0.0, M2_servicio=0.0,
                      fc=21.0, fy=420.0, recubrimiento=0.075, db=0.01905,
                      B=0.0, L=0.0, h=0.0, Df=1.5,
                      gamma_suelo=18.0, gamma_concreto=24.0,
                      Pu1=0.0, Pu2=0.0, factor_carga=1.5) -> dict:
    """Zapata combinada rectangular bajo dos columnas alineadas en L.

    La zapata se dibuja como una viga en la dirección L (eje de columnas) de
    ancho B. Se dimensiona para que la resultante de las cargas coincida con el
    centroide de la planta (presión uniforme). ``medianeria_izquierda`` = True
    sitúa la columna 1 en el borde (cara externa a ras del límite de propiedad).
    """
    sqrt_fc = math.sqrt(fc)
    avisos = []
    Pu1 = (factor_carga * P1_servicio) if (not Pu1 or Pu1 <= 0) else Pu1
    Pu2 = (factor_carga * P2_servicio) if (not Pu2 or Pu2 <= 0) else Pu2

    R = P1_servicio + P2_servicio
    Mtot = M1_servicio + M2_servicio
    # Posición de la resultante medida desde la columna 1 (hacia la 2)
    x_R = (P2_servicio * separacion + Mtot) / R if R else separacion / 2.0

    # Posición de la columna 1 desde el borde izquierdo
    a1 = (c1a / 2.0) if medianeria_izquierda else None

    def geometria_planta(L_):
        """Dado L, ubica columnas para que el centroide coincida con la
        resultante. Devuelve (a1, x1, x2) posiciones desde el borde izq."""
        if medianeria_izquierda:
            aa1 = c1a / 2.0
            x1_ = aa1
        else:
            # cantiléveres simétricos: centroide en L/2 = x1 + x_R → x1 = L/2 − x_R
            x1_ = L_ / 2.0 - x_R
        x2_ = x1_ + separacion
        return x1_, x2_

    # ------- Dimensionamiento -------
    auto = (not L or L <= 0)
    if auto:
        # L tal que el centroide de la planta caiga sobre la resultante.
        if medianeria_izquierda:
            # centroide L/2 = a1 + x_R  →  L = 2·(a1 + x_R)
            L = round(2.0 * (a1 + x_R), 3)
        else:
            # holgura del 15% más allá de cada columna
            L = round(separacion + x_R + (separacion - x_R) + 0.9, 3)
            L = round(max(L, separacion + 1.2), 3)
    if not h or h <= 0:
        h = 0.45
    # Ancho B por presión admisible neta (iterando con el peso propio)
    if not B or B <= 0:
        for _ in range(30):
            q_net = max(q_adm - gamma_concreto * h - gamma_suelo * max(0.0, Df - h),
                        0.05 * q_adm)
            B = _redondea_arriba(R / (q_net * L), 0.05)
            # h por cortante longitudinal (aprox: usa geometría equivalente)
            qu_tmp = (Pu1 + Pu2) / (B * L)
            h_new = _auto_h_comb(B, L, c1a, c2a, c1b, c2b, qu_tmp, sqrt_fc,
                                 recubrimiento, db, separacion, medianeria_izquierda,
                                 Pu1=Pu1, Pu2=Pu2)
            if abs(h_new - h) < 0.03:
                h = h_new
                break
            h = h_new
    L = round(L, 3); B = round(B, 3); h = round(h, 3)
    x1, x2 = geometria_planta(L)

    # ------- Geotecnia (presión de contacto) -------
    A = B * L
    Wz = gamma_concreto * A * h
    Ws = gamma_suelo * A * max(0.0, Df - h)
    Pt = R + Wz + Ws
    # excentricidad de la resultante total respecto al centroide
    x_res_total = (P1_servicio * x1 + P2_servicio * x2 + Mtot) / R if R else L / 2.0
    e = x_res_total - L / 2.0
    q_unif = Pt / A
    if abs(e) <= L / 6.0 + 1e-9:
        q_max = q_unif * (1.0 + 6.0 * abs(e) / L)
        q_min = q_unif * (1.0 - 6.0 * abs(e) / L)
    else:
        q_max = 2.0 * Pt / (3.0 * B * (L / 2.0 - abs(e))) if (L / 2.0 - abs(e)) > 0 else float("inf")
        q_min = 0.0
    cumple_geo = q_max <= q_adm * 1.001 and q_min >= -1e-6
    if q_max > q_adm * 1.001:
        avisos.append("La presión máxima supera la admisible: aumenta L o B.")
    if abs(e) > 1e-3:
        avisos.append(f"La planta no quedó perfectamente centrada (e={e:.3f} m); "
                      "ajusta L o las posiciones para presión uniforme.")

    # ------- Viga longitudinal (cargas mayoradas) -------
    d = max(0.05, h - recubrimiento - db)
    Ru = Pu1 + Pu2
    w = Ru / L                      # carga de suelo hacia ARRIBA (kN/m)

    def V(x):
        v = w * x
        if x > x1: v -= Pu1
        if x > x2: v -= Pu2
        return v

    def M(x):
        m = w * x * x / 2.0
        if x > x1: m -= Pu1 * (x - x1)
        if x > x2: m -= Pu2 * (x - x2)
        return m

    # Muestreo del diagrama para M+ (tracción abajo, cantiléveres) y M− (arriba, entre columnas)
    N = 400
    M_pos = 0.0; x_pos = 0.0
    M_neg = 0.0; x_neg = 0.0
    for i in range(N + 1):
        x = L * i / N
        m = M(x)
        if m > M_pos: M_pos, x_pos = m, x
        if m < M_neg: M_neg, x_neg = m, x
    Vmax = max(abs(V(x1 - 1e-6)), abs(V(x1 + 1e-6)),
               abs(V(x2 - 1e-6)), abs(V(x2 + 1e-6)))

    # Cortante LONGITUDINAL de la viga: si φVc_long < Vmax, crecer h.
    d_req_v = Vmax / (PHI_CORTE * 0.17 * sqrt_fc * 1000.0 * B) if B > 0 else d
    h_req_v = _redondea_arriba(d_req_v + recubrimiento + db, 0.05)
    if h_req_v > h:
        h = round(h_req_v, 3)
        d = max(0.05, h - recubrimiento - db)

    # Acero longitudinal: inferior (M+), superior (M−). Ancho = B.
    flex_inf = _As_de_Mu(M_pos, B, d, fc, fy, recubrimiento, db, h)
    flex_sup = _As_de_Mu(-M_neg, B, d, fc, fy, recubrimiento, db, h)

    # Cortante longitudinal (viga ancha) a 'd' de la cara más solicitada
    phiVc_long = PHI_CORTE * 0.17 * sqrt_fc * 1000.0 * B * d
    cumple_vlong = Vmax <= phiVc_long

    # ------- Flexión transversal bajo cada columna (banda c+d) -------
    qu = Ru / A
    def _transversal(c_col):
        banda = c_col + d
        volado = (B - c_col) / 2.0
        return _flexion(banda, volado, qu, d, fc, fy, recubrimiento, db, h)
    flex_transv_1 = _transversal(c1a)
    flex_transv_2 = _transversal(c1b)

    # ------- Punzonamiento por columna -------
    punz_1 = _punz_columna(Pu1, qu, c1a, c2a, h, sqrt_fc, recubrimiento, db,
                           "borde" if medianeria_izquierda else "interior")
    punz_2 = _punz_columna(Pu2, qu, c1b, c2b, h, sqrt_fc, recubrimiento, db, "interior")

    cumple_cort = (punz_1["cumple"] and punz_2["cumple"] and cumple_vlong)
    if not cumple_cort:
        avisos.append("El cortante (punzonamiento o viga ancha) no cumple: aumenta h.")

    return {
        "tipo": "combinada",
        "geometria": {
            "B_m": B, "L_m": L, "h_m": h, "d_m": round(d, 4),
            "area_m2": round(A, 3), "volumen_concreto_m3": round(A * h, 3),
            "x1_col_m": round(x1, 3), "x2_col_m": round(x2, 3),
            "separacion_m": round(separacion, 3),
            "medianeria_izquierda": medianeria_izquierda,
            "c1a_m": c1a, "c2a_m": c2a, "c1b_m": c1b, "c2b_m": c2b,
        },
        "geotecnico": {
            "q_adm_kPa": round(q_adm, 1), "P_total_servicio_kN": round(Pt, 1),
            "resultante_servicio_kN": round(R, 1),
            "x_resultante_m": round(x_res_total, 3), "excentricidad_m": round(e, 4),
            "q_uniforme_kPa": round(q_unif, 1),
            "q_max_kPa": round(q_max, 1), "q_min_kPa": round(q_min, 1),
            "ratio": round(q_max / q_adm, 3) if q_adm > 0 else None,
            "cumple": cumple_geo,
        },
        "estructural": {
            "qu_kPa": round(qu, 1), "Pu1_kN": round(Pu1, 1), "Pu2_kN": round(Pu2, 1),
            "factor_carga": factor_carga, "h_m": h, "d_m": round(d, 4),
            "M_pos_kNm": round(M_pos, 1), "x_M_pos_m": round(x_pos, 3),
            "M_neg_kNm": round(M_neg, 1), "x_M_neg_m": round(x_neg, 3),
            "V_max_kN": round(Vmax, 1), "phiVc_long_kN": round(phiVc_long, 1),
            "cumple_v_long": cumple_vlong,
            "flexion_long_inferior": flex_inf,
            "flexion_long_superior": flex_sup,
            "flexion_transversal_col1": flex_transv_1,
            "flexion_transversal_col2": flex_transv_2,
            "punzonamiento_col1": punz_1, "punzonamiento_col2": punz_2,
            "cumple_cortante": cumple_cort,
        },
        "avisos": avisos,
    }


def _auto_h_comb(B, L, c1a, c2a, c1b, c2b, qu, sqrt_fc, rec, db, s, mediz,
                 Pu1=None, Pu2=None):
    """Menor h (paso 0.05) que satisface el punzonamiento de ambas columnas y
    el cortante transversal (viga ancha, voladizo (B−c)/2). El cortante
    LONGITUDINAL de la viga se verifica aparte en ``disenar_combinada``."""
    h = 0.30
    if Pu1 is None:
        Pu1 = qu * B * L * 0.5
    if Pu2 is None:
        Pu2 = qu * B * L * 0.5
    for _ in range(300):
        p1 = _punz_columna(Pu1, qu, c1a, c2a, h, sqrt_fc, rec, db,
                           "borde" if mediz else "interior")
        p2 = _punz_columna(Pu2, qu, c1b, c2b, h, sqrt_fc, rec, db, "interior")
        d = p1["d_m"]
        vol_t = max((B - c1a) / 2.0, (B - c1b) / 2.0)      # voladizo transversal
        cuv = _cortante_una_via(L, vol_t, qu, d, sqrt_fc)
        if p1["cumple"] and p2["cumple"] and cuv["cumple"]:
            return round(h, 3)
        h += 0.05
    return round(h, 3)


# ===========================================================================
# ESQUINERA — columna en la esquina (medianería en dos lados)
# ===========================================================================
def disenar_esquinera(*, c1, c2, P_servicio, q_adm, M_servicio=0.0, My_servicio=0.0,
                      viga_centradora=True,
                      fc=21.0, fy=420.0, recubrimiento=0.075, db=0.01905,
                      B=0.0, L=0.0, h=0.0, Df=1.5,
                      gamma_suelo=18.0, gamma_concreto=24.0,
                      Pu=0.0, factor_carga=1.5) -> dict:
    """Zapata de esquina (columna contra dos medianeros).

    - Con ``viga_centradora=True`` se asume una viga de rigidez (centradora)
      que transfiere el momento de excentricidad a una zapata interior, de modo
      que la de esquina trabaja con presión ~uniforme (se diseña como aislada
      con voladizos asimétricos: largo hacia el interior).
    - Sin viga, la columna en la esquina genera excentricidad biaxial
      (e_L = L/2 − c1/2, e_B = B/2 − c2/2): se calculan las presiones y se
      avisa del despegue, recomendando la viga centradora.
    """
    if viga_centradora:
        # La viga centra la reacción: presión uniforme (como concéntrica).
        res = disenar_zapata(
            c1=c1, c2=c2, P_servicio=P_servicio, M_servicio=0.0, My_servicio=0.0,
            q_adm=q_adm, fc=fc, fy=fy, recubrimiento=recubrimiento, db=db,
            B=B, L=L, h=h, Df=Df, gamma_suelo=gamma_suelo,
            gamma_concreto=gamma_concreto, Pu=Pu, factor_carga=factor_carga,
            posicion="esquina")
        res["tipo"] = "esquinera"
        res.setdefault("avisos", []).insert(
            0, "Diseño con viga centradora: transfiere el momento de "
               "excentricidad a una zapata interior; la de esquina trabaja con "
               "presión uniforme. Dimensiona también la viga de rigidez.")
        res["esquinera"] = {"viga_centradora": True}
        return res

    # Sin viga: excentricidad geométrica por la columna en la esquina.
    if not B or B <= 0 or not L or L <= 0:
        # tamaño de partida por presión admisible (cuadrada) y luego se avisa
        A0 = P_servicio / max(q_adm, 1.0)
        B = L = _redondea_arriba(math.sqrt(A0) * 1.6, 0.05)  # holgado por la excentricidad
    eL = (L / 2.0 - c1 / 2.0) + (M_servicio / P_servicio if P_servicio else 0.0)
    eB = (B / 2.0 - c2 / 2.0) + (My_servicio / P_servicio if P_servicio else 0.0)
    Mx = P_servicio * eL
    My = P_servicio * eB
    res = disenar_zapata(
        c1=c1, c2=c2, P_servicio=P_servicio, M_servicio=Mx, My_servicio=My,
        q_adm=q_adm, fc=fc, fy=fy, recubrimiento=recubrimiento, db=db,
        B=B, L=L, h=h, Df=Df, gamma_suelo=gamma_suelo,
        gamma_concreto=gamma_concreto, Pu=Pu, factor_carga=factor_carga,
        posicion="esquina")
    res["tipo"] = "esquinera"
    res["esquinera"] = {"viga_centradora": False,
                        "e_L_m": round(eL, 3), "e_B_m": round(eB, 3)}
    res.setdefault("avisos", []).insert(
        0, "Columna en la esquina sin viga centradora: la excentricidad biaxial "
           "es grande y suele producir despegue del suelo. Se recomienda usar "
           "viga de rigidez (centradora) o zapata combinada.")
    return res


# ===========================================================================
# TRIANGULAR — planta triangular (columna en el baricentro)
# ===========================================================================
def disenar_triangular(*, c1, c2, P_servicio, q_adm, M_servicio=0.0,
                       base=0.0, altura=0.0,
                       fc=21.0, fy=420.0, recubrimiento=0.075, db=0.01905,
                       h=0.0, Df=1.5, gamma_suelo=18.0, gamma_concreto=24.0,
                       Pu=0.0, factor_carga=1.5, posicion="esquina") -> dict:
    """Zapata de planta triangular isósceles (columna en el baricentro).

    Área = ½·base·altura. Con la columna en el baricentro y sin momento la
    presión es uniforme q = P_total/A. El diseño estructural se hace de forma
    simplificada mediante una zapata cuadrada equivalente de la misma área
    (voladizos y cortante), con un aviso indicando la simplificación.
    """
    sqrt_fc = math.sqrt(fc)
    avisos = []
    Pu = (factor_carga * P_servicio) if (not Pu or Pu <= 0) else Pu

    auto = (not base or base <= 0 or not altura or altura <= 0)
    if auto:
        # Triángulo isósceles con altura = base (proporción sencilla)
        if not h or h <= 0:
            h = 0.40
        q_net = max(q_adm - gamma_concreto * h - gamma_suelo * max(0.0, Df - h),
                    0.05 * q_adm)
        A_req = P_servicio / q_net
        base = altura = _redondea_arriba(math.sqrt(2.0 * A_req), 0.05)
    A = 0.5 * base * altura
    if not h or h <= 0:
        h = 0.40

    Wz = gamma_concreto * A * h
    Ws = gamma_suelo * A * max(0.0, Df - h)
    Pt = P_servicio + Wz + Ws
    q_unif = Pt / A
    e = (M_servicio / Pt) if (M_servicio and Pt) else 0.0
    q_max = q_unif * (1.0 + 3.0 * abs(e) / (altura / 3.0)) if e else q_unif
    cumple_geo = q_max <= q_adm * 1.001
    if not cumple_geo:
        avisos.append("La presión supera la admisible: aumenta la base/altura.")

    # Zapata cuadrada equivalente (misma área) para el diseño estructural
    lado_eq = math.sqrt(A)
    qu = Pu / A
    d = max(0.05, h - recubrimiento - db)
    volado = (lado_eq - max(c1, c2)) / 2.0
    flex = _flexion(lado_eq, volado, qu, d, fc, fy, recubrimiento, db, h)
    cuv = _cortante_una_via(lado_eq, volado, qu, d, sqrt_fc)
    punz = _punz_columna(Pu, qu, c1, c2, h, sqrt_fc, recubrimiento, db, posicion)
    cumple_cort = cuv["cumple"] and punz["cumple"]
    if not cumple_cort:
        avisos.append("El cortante no cumple: aumenta h.")
    avisos.append("Diseño estructural aproximado con zapata cuadrada equivalente "
                  "de igual área; para geometrías triangulares críticas usa un "
                  "análisis por elementos finitos o bielas-tirantes.")

    return {
        "tipo": "triangular",
        "geometria": {
            "base_m": round(base, 3), "altura_m": round(altura, 3),
            "h_m": round(h, 3), "d_m": round(d, 4),
            "area_m2": round(A, 3), "lado_equivalente_m": round(lado_eq, 3),
            "volumen_concreto_m3": round(A * h, 3),
            "c1_m": c1, "c2_m": c2,
        },
        "geotecnico": {
            "q_adm_kPa": round(q_adm, 1), "P_total_servicio_kN": round(Pt, 1),
            "q_uniforme_kPa": round(q_unif, 1), "q_max_kPa": round(q_max, 1),
            "excentricidad_m": round(e, 4),
            "ratio": round(q_max / q_adm, 3) if q_adm > 0 else None,
            "cumple": cumple_geo,
        },
        "estructural": {
            "qu_kPa": round(qu, 1), "Pu_kN": round(Pu, 1),
            "factor_carga": factor_carga, "h_m": round(h, 3), "d_m": round(d, 4),
            "punzonamiento": punz, "una_via": cuv, "flexion": flex,
            "cumple_cortante": cumple_cort,
        },
        "avisos": avisos,
    }


# ===========================================================================
# DESPACHADOR POR TIPO
# ===========================================================================
_TIPOS_AISLADA = {"aislada", "concentrica", "excentrica", "cuadrada", "rectangular"}


def disenar_zapata_tipo(tipo: str, params: dict) -> dict:
    """Despacha al diseñador según el ``tipo`` de zapata."""
    t = (tipo or "aislada").strip().lower()

    def f(k, dv=0.0):
        v = params.get(k)
        return float(v) if v not in (None, "") else dv

    def s(k, dv=""):
        v = params.get(k)
        return str(v) if v not in (None, "") else dv

    comunes = dict(
        fc=f("fc", 21.0), fy=f("fy", 420.0),
        recubrimiento=f("recubrimiento", 0.075), db=f("db", 0.01905),
        Df=f("Df", 1.5), gamma_suelo=f("gamma_suelo", 18.0),
        gamma_concreto=f("gamma_concreto", 24.0),
        factor_carga=f("factor_carga", 1.5),
    )

    if t in _TIPOS_AISLADA:
        # Forma: alias antiguos ("rectangular"/"cuadrada") o el campo "forma".
        forma = "rectangular" if t == "rectangular" else s("forma", "cuadrada")
        return disenar_aislada(
            forma=forma, c1=f("c1", 0.40), c2=f("c2", 0.40),
            P_servicio=f("P_servicio"), M_servicio=f("M_servicio"),
            My_servicio=f("My_servicio"), q_adm=f("q_adm", 200.0),
            B=f("B"), L=f("L"), h=f("h"), Pu=f("Pu"),
            posicion=s("posicion", "interior"),
            relacion_LB=f("relacion_LB", 1.0), **comunes)

    if t in ("conectada", "esquinera", "medianera"):
        res = disenar_esquinera(
            c1=f("c1", 0.40), c2=f("c2", 0.40), P_servicio=f("P_servicio"),
            q_adm=f("q_adm", 200.0), M_servicio=f("M_servicio"),
            My_servicio=f("My_servicio"),
            viga_centradora=bool(params.get("viga_centradora", True)),
            B=f("B"), L=f("L"), h=f("h"), Pu=f("Pu"), **comunes)
        res["tipo"] = "conectada"
        return res

    if t == "combinada":
        return disenar_combinada(
            c1a=f("c1a", 0.40), c2a=f("c2a", 0.40), P1_servicio=f("P1_servicio"),
            c1b=f("c1b", 0.40), c2b=f("c2b", 0.40), P2_servicio=f("P2_servicio"),
            separacion=f("separacion", 4.0), q_adm=f("q_adm", 200.0),
            medianeria_izquierda=bool(params.get("medianeria_izquierda", True)),
            M1_servicio=f("M1_servicio"), M2_servicio=f("M2_servicio"),
            B=f("B"), L=f("L"), h=f("h"), Pu1=f("Pu1"), Pu2=f("Pu2"), **comunes)

    if t == "triangular":
        return disenar_triangular(
            c1=f("c1", 0.40), c2=f("c2", 0.40), P_servicio=f("P_servicio"),
            q_adm=f("q_adm", 200.0), M_servicio=f("M_servicio"),
            base=f("base"), altura=f("altura"), h=f("h"),
            Pu=f("Pu"), posicion=s("posicion", "esquina"), **comunes)

    # Desconocido → aislada
    return disenar_aislada(
        tipo="aislada", c1=f("c1", 0.40), c2=f("c2", 0.40),
        P_servicio=f("P_servicio"), M_servicio=f("M_servicio"),
        My_servicio=f("My_servicio"), q_adm=f("q_adm", 200.0),
        B=f("B"), L=f("L"), h=f("h"), Pu=f("Pu"),
        posicion=s("posicion", "interior"),
        relacion_LB=f("relacion_LB", 1.0), **comunes)
