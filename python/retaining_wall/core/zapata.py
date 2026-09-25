"""Diseño de zapata aislada rectangular (NSR-10 / ACI 318).

Incluye:
  - Dimensionamiento geotécnico (área por capacidad portante admisible,
    presiones de contacto con momento opcional).
  - Diseño estructural: cortante por punzonamiento (dos vías), cortante en
    una vía (viga ancha) y flexión en ambas direcciones, con dimensionamiento
    automático del espesor.

Unidades SI internas: m, kN, kN·m, kPa (= kN/m²), MPa, kN/m³.
"""
from __future__ import annotations

import math

PHI_FLEX = 0.90
PHI_CORTE = 0.75


def _redondea_arriba(x: float, paso: float = 0.05) -> float:
    return math.ceil(x / paso - 1e-9) * paso


def _area_barra(db_m: float) -> float:
    """Área de una barra (m²) a partir del diámetro en metros."""
    return math.pi * db_m ** 2 / 4.0


def _alpha_s(posicion: str) -> float:
    return {"interior": 40.0, "borde": 30.0, "esquina": 20.0}.get(posicion, 40.0)


def _cortante_dos_vias(B, L, h, c1, c2, qu, sqrt_fc, rec, db, posicion):
    """Punzonamiento alrededor de la columna, sección crítica a d/2."""
    d = max(0.05, h - rec - db)
    A = B * L
    bo = 2.0 * (c1 + d) + 2.0 * (c2 + d)
    area_interna = (c1 + d) * (c2 + d)
    Vu = qu * (A - area_interna)                      # kN
    beta_c = max(c1, c2) / min(c1, c2)
    alfa = _alpha_s(posicion)
    # vc (MPa) = mínimo de las tres expresiones (NSR-10 C.11.11.2 / ACI)
    vc1 = 0.33 * sqrt_fc
    vc2 = 0.17 * (1.0 + 2.0 / beta_c) * sqrt_fc
    vc3 = 0.083 * (alfa * d / bo + 2.0) * sqrt_fc
    vc = min(vc1, vc2, vc3)                            # MPa
    phiVc = PHI_CORTE * vc * 1000.0 * bo * d           # kN  (MPa·1000 = kN/m²)
    return {
        "d_m": round(d, 4), "b0_m": round(bo, 4),
        "vc_MPa": round(vc, 3), "Vu_kN": round(Vu, 1),
        "phiVc_kN": round(phiVc, 1),
        "ratio": round(Vu / phiVc, 3) if phiVc > 0 else None,
        "cumple": Vu <= phiVc,
    }


def _cortante_una_via(b_ancho, claro_libre, qu, d, sqrt_fc):
    """Cortante en una vía (viga ancha), sección crítica a 'd' de la cara.
    claro_libre = volado desde la cara de la columna en la dirección analizada."""
    dist = claro_libre - d
    Vu = qu * b_ancho * max(0.0, dist)                 # kN
    phiVc = PHI_CORTE * 0.17 * sqrt_fc * 1000.0 * b_ancho * d   # kN
    return {
        "Vu_kN": round(Vu, 1), "phiVc_kN": round(phiVc, 1),
        "ratio": round(Vu / phiVc, 3) if phiVc > 0 else None,
        "cumple": Vu <= phiVc,
    }


def _flexion(b_ancho, volado, qu, d, fc, fy, rec, db, h):
    """Flexión en la cara de la columna. Devuelve acero requerido y barras.
    b_ancho = ancho de diseño (perpendicular al volado); volado = brazo."""
    Mu = qu * b_ancho * volado ** 2 / 2.0              # kN·m
    fy_k = fy * 1000.0                                 # kPa
    fc_k = fc * 1000.0
    # As por iteración (As = Mu / (phi·fy·(d - a/2)))
    As = Mu / (PHI_FLEX * fy_k * 0.95 * d) if d > 0 else 0.0
    for _ in range(30):
        a = As * fy_k / (0.85 * fc_k * b_ancho) if b_ancho > 0 else 0.0
        nuevo = Mu / (PHI_FLEX * fy_k * (d - a / 2.0)) if (d - a / 2.0) > 0 else As
        if abs(nuevo - As) < 1e-7:
            As = nuevo
            break
        As = nuevo
    As_req = max(As, 0.0)
    As_min = 0.0018 * b_ancho * h                      # retracción y temperatura
    As_final = max(As_req, As_min)
    ab = _area_barra(db)
    n = max(2, math.ceil(As_final / ab)) if ab > 0 else 0
    sep = (b_ancho - 2 * rec) / (n - 1) if n > 1 else 0.0
    return {
        "Mu_kNm": round(Mu, 1),
        "As_req_cm2": round(As_req * 1e4, 2),
        "As_min_cm2": round(As_min * 1e4, 2),
        "As_cm2": round(As_final * 1e4, 2),
        "gobierna_minimo": As_min >= As_req,
        "n_barras": n, "db_mm": round(db * 1000.0, 1),
        "sep_cm": round(sep * 100.0, 1),
    }


def _auto_h(B, L, c1, c2, qu, sqrt_fc, rec, db, posicion):
    """Menor espesor (paso 0.05 m) que satisface punzonamiento y cortante en una vía."""
    h = 0.20
    for _ in range(300):
        cdv = _cortante_dos_vias(B, L, h, c1, c2, qu, sqrt_fc, rec, db, posicion)
        d = cdv["d_m"]
        cuvL = _cortante_una_via(B, (L - c2) / 2.0, qu, d, sqrt_fc)
        cuvB = _cortante_una_via(L, (B - c1) / 2.0, qu, d, sqrt_fc)
        if cdv["cumple"] and cuvL["cumple"] and cuvB["cumple"]:
            return round(h, 3)
        h += 0.05
    return round(h, 3)


def disenar_zapata(*, c1, c2, P_servicio, M_servicio=0.0, My_servicio=0.0, q_adm,
                   fc=21.0, fy=420.0, recubrimiento=0.075, db=0.01905,
                   B=0.0, L=0.0, h=0.0, Df=1.5,
                   gamma_suelo=18.0, gamma_concreto=24.0,
                   Pu=0.0, factor_carga=1.5, posicion="interior",
                   relacion_LB=1.0) -> dict:
    """Diseña (o verifica) una zapata aislada rectangular.

    Momentos de servicio:
        M_servicio  (Mx): flexiona en la dirección de L → excentricidad e_L en L.
        My_servicio (My): flexiona en la dirección de B → excentricidad e_B en B.
    Con My=0 el comportamiento es el uniaxial de siempre (incluida la
    redistribución triangular para e>L/6). Con My≠0 se usa la distribución
    biaxial lineal de las 4 esquinas y se avisa si hay despegue (q_min<0).

    ``relacion_LB`` (L/B) permite una planta rectangular en el auto-dimensionado
    (1.0 = cuadrada, comportamiento previo). Ver módulo para unidades.
    """
    sqrt_fc = math.sqrt(fc)
    avisos = []
    relacion_LB = relacion_LB if relacion_LB and relacion_LB > 0 else 1.0
    biaxial = abs(My_servicio) > 1e-9

    # ---------- Carga última ----------
    Pu = (factor_carga * P_servicio) if (not Pu or Pu <= 0) else Pu

    # ---------- Dimensionamiento geotécnico + estructural (acoplado) ----------
    auto_dim = (not B or B <= 0 or not L or L <= 0)

    def pesos_y_presiones(B_, L_, h_):
        A_ = B_ * L_
        Wz = gamma_concreto * A_ * h_
        Ws = gamma_suelo * A_ * max(0.0, Df - h_)
        Pt = P_servicio + Wz + Ws
        eL = (M_servicio / Pt) if Pt else 0.0     # excentricidad en L
        eB = (My_servicio / Pt) if Pt else 0.0    # excentricidad en B
        qun = Pt / A_
        if biaxial:
            # Distribución lineal biaxial (4 esquinas): q = P/A·(1 ± 6eL/L ± 6eB/B)
            fL = 6.0 * abs(eL) / L_
            fB = 6.0 * abs(eB) / B_
            qmx = qun * (1.0 + fL + fB)
            qmn = qun * (1.0 - fL - fB)
            e_ = math.hypot(eL, eB)
        elif M_servicio and abs(eL) > 1e-9:
            e_ = eL
            if abs(eL) <= L_ / 6.0 + 1e-9:
                qmx = qun * (1.0 + 6.0 * abs(eL) / L_)
                qmn = qun * (1.0 - 6.0 * abs(eL) / L_)
            else:
                qmx = (2.0 * Pt / (3.0 * B_ * (L_ / 2.0 - abs(eL)))
                       if (L_ / 2.0 - abs(eL)) > 0 else float("inf"))
                qmn = 0.0
        else:
            e_ = 0.0
            qmx = qmn = qun
        return A_, Pt, e_, qun, qmx, qmn

    def _plan_rect(A_req_):
        """B×L rectangular a partir del área requerida y la relación L/B."""
        B_ = _redondea_arriba(math.sqrt(A_req_ / relacion_LB), 0.05)
        L_ = _redondea_arriba(B_ * relacion_LB, 0.05)
        return B_, L_

    if auto_dim:
        # Iterar: área por presión NETA (descontando peso propio y sobrecarga) ↔ espesor por cortante
        h = 0.40
        for _ in range(25):
            q_net = q_adm - gamma_concreto * h - gamma_suelo * max(0.0, Df - h)
            q_net = max(q_net, 0.05 * q_adm)
            A_req = P_servicio / q_net
            B, L = _plan_rect(A_req)
            h_new = _auto_h(B, L, c1, c2, Pu / (B * L), sqrt_fc, recubrimiento, db, posicion)
            if abs(h_new - h) < 0.03:
                h = h_new
                break
            h = h_new
        # Si hay momento/peso que excede la admisible, crecer la planta (manteniendo L/B)
        for _ in range(150):
            _, _, _, _, qmx_t, _ = pesos_y_presiones(B, L, h)
            if qmx_t <= q_adm * 1.001 or B > 25:
                break
            B = round(B + 0.05, 3)
            L = round(B * relacion_LB, 3)
        h = _auto_h(B, L, c1, c2, Pu / (B * L), sqrt_fc, recubrimiento, db, posicion)
        q_net_f = max(q_adm - gamma_concreto * h - gamma_suelo * max(0.0, Df - h), 0.05 * q_adm)
        A_req = P_servicio / q_net_f
    else:
        A_req = P_servicio / q_adm
        if not h or h <= 0:
            h = _auto_h(B, L, c1, c2, Pu / (B * L), sqrt_fc, recubrimiento, db, posicion)

    h = round(h, 3)
    A, P_total, e, q_unif, q_max, q_min = pesos_y_presiones(B, L, h)
    qu = Pu / A

    cumple_geo = (q_max <= q_adm * 1.001) and (q_min >= -1e-6)
    if q_max > q_adm * 1.001:
        avisos.append("La presión de contacto supera la admisible: aumenta B×L o q_adm.")
    if q_min < -1e-6:
        avisos.append("Hay despegue del suelo (q_mín < 0): la resultante sale del "
                      "núcleo central. Aumenta la planta o añade viga de rigidez.")

    # ---------- Chequeos de cortante (finales) ----------
    cdv = _cortante_dos_vias(B, L, h, c1, c2, qu, sqrt_fc, recubrimiento, db, posicion)
    d = cdv["d_m"]
    cuv_L = _cortante_una_via(B, (L - c2) / 2.0, qu, d, sqrt_fc)
    cuv_B = _cortante_una_via(L, (B - c1) / 2.0, qu, d, sqrt_fc)
    if not (cdv["cumple"] and cuv_L["cumple"] and cuv_B["cumple"]):
        avisos.append("El cortante no cumple con el espesor dado: aumenta h.")

    # ---------- Flexión (ambas direcciones) ----------
    # Dirección L: volado (L - c2)/2, acero repartido en el ancho B.
    flex_L = _flexion(B, (L - c2) / 2.0, qu, d, fc, fy, recubrimiento, db, h)
    # Dirección B: volado (B - c1)/2, acero repartido en el ancho L.
    flex_B = _flexion(L, (B - c1) / 2.0, qu, d, fc, fy, recubrimiento, db, h)

    if M_servicio and abs(e) > 1e-9:
        avisos.append("Diseño estructural con presión uniforme equivalente; "
                      "para excentricidades grandes verifica con la distribución trapezoidal.")

    return {
        "geometria": {
            "B_m": round(B, 3), "L_m": round(L, 3), "h_m": h, "d_m": round(d, 4),
            "c1_m": c1, "c2_m": c2, "area_m2": round(A, 3),
            "volumen_concreto_m3": round(A * h, 3),
            "auto_dimensionada": auto_dim,
        },
        "geotecnico": {
            "A_req_m2": round(A_req, 3), "q_adm_kPa": round(q_adm, 1),
            "P_total_servicio_kN": round(P_total, 1),
            "q_uniforme_kPa": round(q_unif, 1),
            "q_max_kPa": round(q_max, 1), "q_min_kPa": round(q_min, 1),
            "excentricidad_m": round(e, 4),
            "ratio": round(q_max / q_adm, 3) if q_adm > 0 else None,
            "cumple": cumple_geo,
        },
        "estructural": {
            "Pu_kN": round(Pu, 1), "qu_kPa": round(qu, 1),
            "factor_carga": factor_carga,
            "h_m": h, "d_m": round(d, 4),
            "punzonamiento": cdv,
            "una_via_L": cuv_L,
            "una_via_B": cuv_B,
            "flexion_L": flex_L,
            "flexion_B": flex_B,
            "cumple_cortante": cdv["cumple"] and cuv_L["cumple"] and cuv_B["cumple"],
        },
        "avisos": avisos,
    }
