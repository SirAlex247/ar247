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


def _beta1(fc: float) -> float:
    """β₁ del bloque de compresión (NSR-10 C.10.2.7.3)."""
    if fc <= 28.0:
        return 0.85
    return max(0.65, 0.85 - 0.05 * (fc - 28.0) / 7.0)


def _cuantia_maxima(As_m2, b_ancho, d, fc, fy):
    """Cuantía y cuantía máxima por ductilidad (deformación neta de tracción
    εt ≥ 0.004, sección controlada por tracción; NSR-10 C.10.3.5).

        ρ_max = 0.85·β₁·(f'c/fy)·(0.003/(0.003 + 0.004))
    """
    area = b_ancho * d
    rho = As_m2 / area if area > 0 else 0.0
    rho_max = 0.85 * _beta1(fc) * (fc / fy) * (0.003 / 0.007)
    return {
        "rho": round(rho, 5), "rho_max": round(rho_max, 5),
        "cumple": rho <= rho_max + 1e-9,
    }


def _control_fisuracion(sep_m, rec, fy):
    """Separación máxima del refuerzo por control de fisuración
    (NSR-10 C.10.6.4 / ACI 318 24.3.2):

        s_max = min(380·(280/fs) − 2.5·c_c,  300·(280/fs))

    con fs ≈ (2/3)·fy (esfuerzo de servicio) y c_c el recubrimiento libre (mm).
    """
    fs = (2.0 / 3.0) * fy               # MPa
    cc = rec * 1000.0                   # mm
    s_max = min(380.0 * (280.0 / fs) - 2.5 * cc, 300.0 * (280.0 / fs))
    s_max = max(0.0, s_max) / 1000.0    # m
    return {
        "sep_max_m": round(s_max, 3),
        "cumple": sep_m <= s_max + 1e-6,
    }


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


def _jc_c(b1, b2, d):
    """Propiedad polar Jc de la sección crítica de punzonamiento (columna
    interior, ACI 318 / NSR-10 C.11.11.7) y la distancia c al borde.

    b1 = dimensión de la sección crítica paralela a la excentricidad
    (dirección del momento), b2 = perpendicular. Jc en m⁴, c en m."""
    Jc = (d * b1 ** 3) / 6.0 + (b1 * d ** 3) / 6.0 + (d * b2 * b1 ** 2) / 2.0
    return Jc, b1 / 2.0


def _cortante_dos_vias_momento(B, L, h, c1, c2, qu, sqrt_fc, rec, db, posicion,
                               Mux=0.0, Muy=0.0):
    """Punzonamiento con transferencia de momento por cortante excéntrico.

    El esfuerzo cortante máximo en el perímetro crítico se compone del cortante
    directo más la fracción γv del momento no balanceado que se resiste por
    cortante (NSR-10 C.11.11.7 / ACI 318):

        vu = Vu/(bo·d) + γv,x·Mux·c_x/Jc_x + γv,y·Muy·c_y/Jc_y
        γf = 1/(1 + (2/3)·√(b1/b2)),  γv = 1 − γf
    """
    base = _cortante_dos_vias(B, L, h, c1, c2, qu, sqrt_fc, rec, db, posicion)
    d = base["d_m"]
    bo = base["b0_m"]
    Vu = base["Vu_kN"]
    vc_MPa = base["vc_MPa"]

    v_directo = Vu / (bo * d) if (bo * d) > 0 else 0.0          # kPa

    # Dirección x: momento Mux flexiona en la dimensión (c1+d).
    b1x, b2x = c1 + d, c2 + d
    gf_x = 1.0 / (1.0 + (2.0 / 3.0) * math.sqrt(b1x / b2x))
    gv_x = 1.0 - gf_x
    Jcx, cx = _jc_c(b1x, b2x, d)
    v_mx = gv_x * abs(Mux) * cx / Jcx if Jcx > 0 else 0.0        # kPa

    # Dirección y: momento Muy flexiona en la dimensión (c2+d).
    b1y, b2y = c2 + d, c1 + d
    gf_y = 1.0 / (1.0 + (2.0 / 3.0) * math.sqrt(b1y / b2y))
    gv_y = 1.0 - gf_y
    Jcy, cy = _jc_c(b1y, b2y, d)
    v_my = gv_y * abs(Muy) * cy / Jcy if Jcy > 0 else 0.0        # kPa

    vu_total = v_directo + v_mx + v_my                          # kPa
    phi_vc = PHI_CORTE * vc_MPa * 1000.0                        # kPa
    return {
        **base,
        "gamma_v_x": round(gv_x, 3), "gamma_v_y": round(gv_y, 3),
        "vu_directo_kPa": round(v_directo, 1),
        "vu_momento_kPa": round(v_mx + v_my, 1),
        "vu_total_kPa": round(vu_total, 1),
        "phi_vc_kPa": round(phi_vc, 1),
        "ratio_momento": round(vu_total / phi_vc, 3) if phi_vc > 0 else None,
        "cumple_momento": vu_total <= phi_vc,
    }


def _transferencia_carga(Pu, c1, c2, h, B, L, fc, fc_col, fy, rec, db_dowel):
    """Transferencia de carga columna→zapata: aplastamiento del concreto y
    dowels de conexión (NSR-10 C.15.8 / C.10.14).

    - Aplastamiento zapata: φ·(0.85·f'c·A1)·√(A2/A1), con √(A2/A1) ≤ 2.
    - Aplastamiento columna: φ·0.85·f'c_col·A1.
    - Dowels: As ≥ máx(0.005·A1, exceso/(φ·fy)); mínimo 4 barras.
    - Longitud de desarrollo a compresión de los dowels (C.12.3).
    """
    PHI_APLAST = 0.65
    A1 = c1 * c2                                    # área cargada (columna)
    # Frustum 1V:2H hasta el fondo; A2 acotada por la planta de la zapata.
    A2 = min(c1 + 4.0 * h, B) * min(c2 + 4.0 * h, L)
    raiz = min(2.0, math.sqrt(A2 / A1)) if A1 > 0 else 1.0
    phiPn_zap = PHI_APLAST * 0.85 * fc * 1000.0 * A1 * raiz      # kN
    phiPn_col = PHI_APLAST * 0.85 * fc_col * 1000.0 * A1         # kN
    phiPn = min(phiPn_zap, phiPn_col)
    cumple_aplast = Pu <= phiPn

    # Acero de dowels: el mínimo 0.005·A1 y el exceso sobre el aplastamiento.
    As_min_dow = 0.005 * A1                          # m²
    exceso = max(0.0, Pu - phiPn) / (0.9 * fy * 1000.0)  # m² (φ=0.9 compresión-tracción)
    As_dow = max(As_min_dow, exceso)
    ab = _area_barra(db_dowel)
    n_dow = max(4, math.ceil(As_dow / ab)) if ab > 0 else 4
    # Longitud de desarrollo a compresión (mm→m); mínimo 200 mm.
    fc_min = min(fc, fc_col)
    ldc = max(0.24 * fy * (db_dowel * 1000.0) / math.sqrt(fc_min),
              0.043 * fy * (db_dowel * 1000.0)) / 1000.0        # m
    ldc = max(ldc, 0.20)
    ldc_disp = max(0.0, h - rec)                     # espacio dentro de la zapata
    return {
        "A1_cm2": round(A1 * 1e4, 1), "A2_cm2": round(A2 * 1e4, 1),
        "sqrt_A2A1": round(raiz, 3),
        "Pu_kN": round(Pu, 1),
        "phiPn_zapata_kN": round(phiPn_zap, 1),
        "phiPn_columna_kN": round(phiPn_col, 1),
        "phiPn_kN": round(phiPn, 1),
        "ratio": round(Pu / phiPn, 3) if phiPn > 0 else None,
        "cumple_aplastamiento": cumple_aplast,
        "As_dowels_req_cm2": round(As_dow * 1e4, 2),
        "As_min_dowels_cm2": round(As_min_dow * 1e4, 2),
        "gobierna_minimo": As_min_dow >= exceso,
        "n_dowels": n_dow, "db_dowel_mm": round(db_dowel * 1000.0, 1),
        "ldc_dowel_m": round(ldc, 3), "ldc_disponible_m": round(ldc_disp, 3),
        "cumple_dowels": ldc <= ldc_disp + 1e-6,
    }


def _longitud_desarrollo(db, fc, fy, volado, rec):
    """Longitud de desarrollo a tracción de las barras de flexión (NSR-10
    C.12.2 simplificado) y verificación contra la longitud disponible.

    ℓd = (fy·ψt·ψe / (k·λ·√f'c))·db, con k=2.1 para db ≤ 19 mm y k=1.7 para
    db > 19 mm; ψt=ψe=λ=1.0 (barra inferior, sin recubrimiento epóxico, peso
    normal). Disponible = volado − recubrimiento lateral. Mínimo 300 mm."""
    db_mm = db * 1000.0
    k = 2.1 if db_mm <= 19.0 else 1.7
    ld = (fy / (k * math.sqrt(fc))) * db_mm          # mm
    ld = max(ld, 300.0) / 1000.0                     # m
    disp = max(0.0, volado - rec)                    # m (desde la cara al borde)
    return {
        "ld_m": round(ld, 3), "ld_disponible_m": round(disp, 3),
        "cumple": ld <= disp + 1e-6,
        "requiere_gancho": ld > disp + 1e-6,
    }


def _banda_central(As_corto_cm2, n_corto, B, L, db):
    """Distribución del refuerzo de la dirección CORTA en banda central
    (NSR-10 C.15.4.4.2 / ACI 13.3.3.3).

    Una fracción γs = 2/(β+1) del acero paralelo al lado corto se concentra en
    una banda central de ancho igual al lado corto; β = lado largo / lado corto.
    Devuelve None si la zapata es (prácticamente) cuadrada."""
    lado_corto, lado_largo = min(B, L), max(B, L)
    beta = lado_largo / lado_corto if lado_corto > 0 else 1.0
    if beta <= 1.05:
        return None
    gamma_s = 2.0 / (beta + 1.0)
    n_banda = max(1, round(n_corto * gamma_s))
    n_fuera = max(0, n_corto - n_banda)
    return {
        "beta": round(beta, 3), "gamma_s": round(gamma_s, 3),
        "ancho_banda_m": round(lado_corto, 3),
        "As_banda_cm2": round(As_corto_cm2 * gamma_s, 2),
        "n_banda": n_banda,
        "As_fuera_cm2": round(As_corto_cm2 * (1.0 - gamma_s), 2),
        "n_fuera": n_fuera,
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
    # Si la separación excede el máximo por fisuración, agrega barras.
    fis = _control_fisuracion(sep, rec, fy)
    if not fis["cumple"] and fis["sep_max_m"] > 0:
        n = max(n, math.ceil((b_ancho - 2 * rec) / fis["sep_max_m"]) + 1)
        sep = (b_ancho - 2 * rec) / (n - 1) if n > 1 else 0.0
        fis = _control_fisuracion(sep, rec, fy)
    return {
        "Mu_kNm": round(Mu, 1),
        "As_req_cm2": round(As_req * 1e4, 2),
        "As_min_cm2": round(As_min * 1e4, 2),
        "As_cm2": round(As_final * 1e4, 2),
        "gobierna_minimo": As_min >= As_req,
        "n_barras": n, "db_mm": round(db * 1000.0, 1),
        "sep_cm": round(sep * 100.0, 1),
        "fisuracion": fis,
        "cuantia": _cuantia_maxima(As_final, b_ancho, d, fc, fy),
    }


def _auto_h(B, L, c1, c2, qu, sqrt_fc, rec, db, posicion, Mux=0.0, Muy=0.0):
    """Menor espesor (paso 0.05 m) que satisface punzonamiento (incluyendo el
    cortante excéntrico por momento), cortante en una vía y flexión."""
    h = 0.20
    for _ in range(300):
        cdv = _cortante_dos_vias_momento(B, L, h, c1, c2, qu, sqrt_fc, rec, db,
                                         posicion, Mux, Muy)
        d = cdv["d_m"]
        cuvL = _cortante_una_via(B, (L - c2) / 2.0, qu, d, sqrt_fc)
        cuvB = _cortante_una_via(L, (B - c1) / 2.0, qu, d, sqrt_fc)
        if cdv["cumple_momento"] and cuvL["cumple"] and cuvB["cumple"]:
            return round(h, 3)
        h += 0.05
    return round(h, 3)


def disenar_zapata(*, c1, c2, P_servicio, M_servicio=0.0, My_servicio=0.0, q_adm,
                   fc=21.0, fy=420.0, recubrimiento=0.075, db=0.01905,
                   B=0.0, L=0.0, h=0.0, Df=1.5,
                   gamma_suelo=18.0, gamma_concreto=24.0,
                   Pu=0.0, factor_carga=1.5, posicion="interior",
                   relacion_LB=1.0, fc_columna=0.0, db_dowel=0.0) -> dict:
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
    # Momentos últimos transferidos por la columna (cortante excéntrico).
    Mux_u = factor_carga * abs(M_servicio)
    Muy_u = factor_carga * abs(My_servicio)

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
            h_new = _auto_h(B, L, c1, c2, Pu / (B * L), sqrt_fc, recubrimiento, db, posicion, Mux_u, Muy_u)
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
        h = _auto_h(B, L, c1, c2, Pu / (B * L), sqrt_fc, recubrimiento, db, posicion, Mux_u, Muy_u)
        q_net_f = max(q_adm - gamma_concreto * h - gamma_suelo * max(0.0, Df - h), 0.05 * q_adm)
        A_req = P_servicio / q_net_f
    else:
        A_req = P_servicio / q_adm
        if not h or h <= 0:
            h = _auto_h(B, L, c1, c2, Pu / (B * L), sqrt_fc, recubrimiento, db, posicion, Mux_u, Muy_u)

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
    cdv = _cortante_dos_vias_momento(B, L, h, c1, c2, qu, sqrt_fc,
                                     recubrimiento, db, posicion, Mux_u, Muy_u)
    d = cdv["d_m"]
    cuv_L = _cortante_una_via(B, (L - c2) / 2.0, qu, d, sqrt_fc)
    cuv_B = _cortante_una_via(L, (B - c1) / 2.0, qu, d, sqrt_fc)
    cumple_punz = cdv["cumple_momento"]
    if not (cumple_punz and cuv_L["cumple"] and cuv_B["cumple"]):
        avisos.append("El cortante no cumple con el espesor dado: aumenta h.")
    if cdv["cumple"] and not cdv["cumple_momento"]:
        avisos.append("El punzonamiento cumple por cortante directo pero NO al "
                      "sumar el momento transferido (cortante excéntrico γv): "
                      "aumenta h o reduce el momento.")

    # ---------- Transferencia de carga columna→zapata (aplastamiento + dowels) ----------
    fc_col = fc_columna if (fc_columna and fc_columna > 0) else fc
    db_dow = db_dowel if (db_dowel and db_dowel > 0) else db
    transferencia = _transferencia_carga(
        Pu, c1, c2, h, B, L, fc, fc_col, fy, recubrimiento, db_dow)
    if not transferencia["cumple_aplastamiento"]:
        avisos.append("El aplastamiento en la interfaz columna-zapata se excede: "
                      "los dowels toman la carga extra (revisa su cuantía) o sube f'c.")
    if not transferencia["cumple_dowels"]:
        avisos.append("La longitud de desarrollo a compresión de los dowels no "
                      "cabe en el espesor: usa barras de menor diámetro o gancho.")

    # ---------- Flexión (ambas direcciones) ----------
    # Dirección L: volado (L - c2)/2, acero repartido en el ancho B.
    flex_L = _flexion(B, (L - c2) / 2.0, qu, d, fc, fy, recubrimiento, db, h)
    # Dirección B: volado (B - c1)/2, acero repartido en el ancho L.
    flex_B = _flexion(L, (B - c1) / 2.0, qu, d, fc, fy, recubrimiento, db, h)

    # Longitud de desarrollo de las barras de flexión.
    flex_L["desarrollo"] = _longitud_desarrollo(db, fc, fy, (L - c2) / 2.0, recubrimiento)
    flex_B["desarrollo"] = _longitud_desarrollo(db, fc, fy, (B - c1) / 2.0, recubrimiento)
    if flex_L["desarrollo"]["requiere_gancho"] or flex_B["desarrollo"]["requiere_gancho"]:
        avisos.append("Alguna barra de flexión no desarrolla su longitud dentro "
                      "del volado: coloca gancho estándar o barras de menor diámetro.")
    if not (flex_L["cuantia"]["cumple"] and flex_B["cuantia"]["cumple"]):
        avisos.append("La cuantía de flexión supera la máxima por ductilidad "
                      "(εt < 0.004): aumenta el espesor h o f'c (sección "
                      "sobre-reforzada).")

    # Distribución en banda central del refuerzo de la dirección corta
    # (zapatas rectangulares, NSR-10 C.15.4.4.2). La dirección corta es la de
    # las barras paralelas al lado corto = las repartidas sobre el lado largo.
    if L >= B:   # L es el lado largo → banda aplica a flex_B (barras en dir. B)
        banda = _banda_central(flex_B["As_cm2"], flex_B["n_barras"], B, L, db)
        if banda:
            flex_B["banda_central"] = banda
    else:        # B es el lado largo → banda aplica a flex_L (barras en dir. L)
        banda = _banda_central(flex_L["As_cm2"], flex_L["n_barras"], B, L, db)
        if banda:
            flex_L["banda_central"] = banda

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
            "transferencia": transferencia,
            "cumple_cortante": cumple_punz and cuv_L["cumple"] and cuv_B["cumple"],
            "cumple_transferencia": (transferencia["cumple_aplastamiento"]
                                     and transferencia["cumple_dowels"]),
        },
        "avisos": avisos,
    }
