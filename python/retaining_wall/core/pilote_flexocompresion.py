"""
Verificaciones estructurales avanzadas del pilote circular (NSR-10 / ACI 318):

1. **Flexo-compresión** — diagrama de interacción P-M de la sección circular
   (compatibilidad de deformaciones, ε_cu = 0.003, bloque de Whitney sobre el
   segmento circular comprimido, φ variable según ε_t).
2. **Esbeltez / pandeo** — amplificación de momento δ_ns por longitud no
   soportada (C.10.10.6): Mc = δ_ns·M2, δ_ns = C_m/(1 − Pu/(0.75·Pc)).
3. **Tracción / arranque (uplift)** — capacidad estructural φT = 0.9·fy·A_st.
4. **Confinamiento sísmico** — zona de rótula plástica en la cabeza (longitud y
   paso del refuerzo transversal, C.21).

Unidades: fuerzas kN, momentos kN·m, longitudes m, esfuerzos kPa.
"""
from __future__ import annotations

import math

ES_KPA = 200_000_000.0     # módulo de elasticidad del acero (kPa) = 200 GPa
ECU = 0.003                # deformación última del concreto


def _beta1(fc: float) -> float:
    if fc <= 28.0:
        return 0.85
    return max(0.65, 0.85 - 0.05 * (fc - 28.0) / 7.0)


def _seg_circular(R: float, a: float, n: int = 80) -> tuple[float, float]:
    """Área (m²) y centroide (m, desde el centro, + hacia la fibra comprimida)
    del segmento circular comprimido de altura ``a`` medida desde el borde
    superior del círculo de radio ``R``."""
    if a <= 0:
        return 0.0, R
    a = min(a, 2.0 * R)
    y_lo = R - a
    A = 0.0
    My = 0.0
    dy = (R - y_lo) / n
    for i in range(n):
        y = y_lo + (i + 0.5) * dy
        w = 2.0 * math.sqrt(max(0.0, R * R - y * y))
        A += w * dy
        My += w * y * dy
    yc = My / A if A > 1e-12 else R
    return A, yc


def diagrama_interaccion(*, D, fc, fy, n_barras, db_long, recubrimiento,
                         db_trans, espiral, n_puntos=40) -> dict:
    """Diagrama de interacción φPn–φMn de la sección circular con barras
    distribuidas en el perímetro. Devuelve los puntos y capacidades clave."""
    R = D / 2.0
    Ag = math.pi * R * R
    ab = math.pi * (db_long / 1000.0) ** 2 / 4.0        # área de una barra (m²)
    Ast = n_barras * ab
    r_s = R - recubrimiento - (db_trans / 1000.0) - (db_long / 1000.0) / 2.0
    r_s = max(r_s, 0.05 * R)
    fc_k = fc * 1000.0
    fy_k = fy * 1000.0
    b1 = _beta1(fc)

    bars_y = [r_s * math.cos(2.0 * math.pi * i / n_barras) for i in range(n_barras)]
    y_bot = min(bars_y)

    alpha_pn = 0.85 if espiral else 0.80
    phi_c = 0.75 if espiral else 0.65
    Pn_max = 0.85 * fc_k * (Ag - Ast) + fy_k * Ast
    phiPn_max = phi_c * alpha_pn * Pn_max
    phiTn = 0.9 * fy_k * Ast                             # tracción pura (magnitud)

    puntos = []
    for k in range(n_puntos):
        c = D * (0.05 + (2.6 - 0.05) * k / (n_puntos - 1))   # eje neutro
        a = min(b1 * c, 2.0 * R)
        Aseg, yc = _seg_circular(R, a)
        Cc = 0.85 * fc_k * Aseg
        Pn = Cc
        Mn = Cc * yc
        y_na = R - c
        for y in bars_y:
            eps = ECU * (y - y_na) / c if c > 1e-9 else 0.0
            fs = max(-fy_k, min(fy_k, ES_KPA * eps))
            Fs = ab * fs
            if eps > 0 and y >= (R - a):                 # resta concreto desplazado
                Fs -= ab * 0.85 * fc_k
            Pn += Fs
            Mn += Fs * y
        # Deformación neta de tracción (barra más traccionada) y φ variable.
        et = ECU * (y_na - y_bot) / c if c > 1e-9 else 0.005
        if et <= 0.002:
            phi = phi_c
        elif et >= 0.005:
            phi = 0.9
        else:
            phi = phi_c + (0.9 - phi_c) * (et - 0.002) / 0.003
        phiPn = min(phi * Pn, phiPn_max)
        puntos.append({"phiPn_kN": round(phiPn, 1), "phiMn_kNm": round(phi * Mn, 1),
                       "phi": round(phi, 3)})
    # Asegura el punto de compresión pura al tope.
    puntos.append({"phiPn_kN": round(phiPn_max, 1), "phiMn_kNm": 0.0, "phi": phi_c})
    puntos.sort(key=lambda p: p["phiPn_kN"])
    return {
        "puntos": puntos, "phiPn_max_kN": round(phiPn_max, 1),
        "phiTn_kN": round(phiTn, 1), "Ast_cm2": round(Ast * 1e4, 2),
        "n_barras": n_barras, "espiral": espiral,
    }


def verificar_flexocompresion(diag: dict, Pu: float, Mu: float) -> dict:
    """Verifica el punto (Pu, Mu) contra el diagrama: φMn disponible a P=Pu y
    la relación de interacción Mu/φMn."""
    pts = diag["puntos"]
    phiPn_max = diag["phiPn_max_kN"]
    # φMn capacidad interpolando en los tramos que contienen Pu (toma el mayor).
    phiMn_cap = 0.0
    for i in range(len(pts) - 1):
        p0, p1 = pts[i], pts[i + 1]
        lo, hi = p0["phiPn_kN"], p1["phiPn_kN"]
        if min(lo, hi) - 1e-6 <= Pu <= max(lo, hi) + 1e-6 and abs(hi - lo) > 1e-9:
            t = (Pu - lo) / (hi - lo)
            m = p0["phiMn_kNm"] + t * (p1["phiMn_kNm"] - p0["phiMn_kNm"])
            phiMn_cap = max(phiMn_cap, m)
    ratio = (abs(Mu) / phiMn_cap) if phiMn_cap > 1e-6 else (999.0 if abs(Mu) > 0 else 0.0)
    cumple = (Pu <= phiPn_max + 1e-6) and (abs(Mu) <= phiMn_cap + 1e-6)
    return {
        "Pu_kN": round(Pu, 1), "Mu_kNm": round(abs(Mu), 1),
        "phiMn_disponible_kNm": round(phiMn_cap, 1),
        "phiPn_max_kN": phiPn_max,
        "ratio_interaccion": round(ratio, 3),
        "cumple": cumple,
    }


def amplificacion_momento(*, Pu, M2, D, fc, Lu, k=1.0, Cm=1.0,
                          Ast=0.0, fy=420.0, beta_dns=0.6) -> dict:
    """Esbeltez y amplificación de momento (columna arriostrada, C.10.10.6).

    δ_ns = C_m / (1 − Pu/(0.75·Pc)) ≥ 1.0,  Pc = π²·EI/(k·Lu)²,
    EI = 0.4·Ec·Ig/(1+β_dns),  Ec = 4700·√f'c (MPa).
    ``Lu`` = longitud no soportada del pilote (tramo libre en agua, socavación o
    suelo muy blando). Con Lu ≈ 0 el pilote no es esbelto."""
    r = 0.25 * D                        # radio de giro de sección circular
    esbeltez = (k * Lu / r) if r > 0 else 0.0
    # Límite de columna corta (arriostrada, sin doble curvatura → 34).
    limite = 34.0
    es_esbelto = esbeltez > limite and Lu > 1e-6
    if not es_esbelto:
        return {
            "Lu_m": round(Lu, 2), "k": k, "esbeltez_klu_r": round(esbeltez, 1),
            "limite": limite, "es_esbelto": False, "delta_ns": 1.0,
            "Mc_kNm": round(abs(M2), 1),
        }
    Ec = 4700.0 * math.sqrt(fc) * 1000.0        # kPa
    Ig = math.pi * D ** 4 / 64.0
    EI = 0.4 * Ec * Ig / (1.0 + beta_dns)
    Pc = math.pi ** 2 * EI / (k * Lu) ** 2       # kN
    denom = 1.0 - Pu / (0.75 * Pc) if Pc > 0 else -1.0
    if denom <= 0:
        delta = 5.0                              # inestable: satura y avisa
        inestable = True
    else:
        delta = max(1.0, Cm / denom)
        inestable = False
    Mc = delta * abs(M2)
    return {
        "Lu_m": round(Lu, 2), "k": k, "esbeltez_klu_r": round(esbeltez, 1),
        "limite": limite, "es_esbelto": True,
        "Pc_kN": round(Pc, 1), "delta_ns": round(delta, 3),
        "Mc_kNm": round(Mc, 1), "inestable": inestable,
    }


def capacidad_traccion(*, Ast, fy, Tu=0.0) -> dict:
    """Capacidad estructural a tracción (arranque): φT = 0.9·fy·A_st."""
    phiTn = 0.9 * fy * 1000.0 * Ast              # kN
    ratio = (Tu / phiTn) if phiTn > 0 else None
    return {
        "phiTn_kN": round(phiTn, 1), "Tu_kN": round(Tu, 1),
        "ratio": round(ratio, 3) if ratio is not None else None,
        "cumple": (Tu <= phiTn + 1e-6),
        "aplica": Tu > 1e-6,
    }


def layout_grupo(n: int, s: float) -> list[tuple[float, float]]:
    """Coordenadas (x, y) de ``n`` pilotes en una malla rectangular centrada en
    el baricentro, con espaciamiento ``s`` (m)."""
    n = max(1, int(n))
    if n == 1:
        return [(0.0, 0.0)]
    filas = max(1, round(math.sqrt(n)))
    cols = math.ceil(n / filas)
    coords = []
    for r in range(filas):
        for c in range(cols):
            if len(coords) < n:
                coords.append((c * s, r * s))
    # Centrar en el baricentro
    cx = sum(x for x, _ in coords) / n
    cy = sum(y for _, y in coords) / n
    return [(x - cx, y - cy) for x, y in coords]


def distribucion_grupo(*, P, Mx, My, coords) -> dict:
    """Distribución de la carga axial a los pilotes de un cabezal rígido
    (biaxial):  P_i = P/n + Mx·y_i/I_x + My·x_i/I_y,  I_x = Σy_i², I_y = Σx_i².

    Devuelve la carga máxima y mínima por pilote (P_min < 0 ⇒ tracción)."""
    n = len(coords)
    if n == 0:
        return {"n": 0, "P_max_kN": P, "P_min_kN": P, "hay_traccion": False}
    Ix = sum(y * y for _, y in coords)
    Iy = sum(x * x for x, _ in coords)
    cargas = []
    for x, y in coords:
        Pi = P / n
        if Ix > 1e-9:
            Pi += Mx * y / Ix
        if Iy > 1e-9:
            Pi += My * x / Iy
        cargas.append(Pi)
    Pmax, Pmin = max(cargas), min(cargas)
    return {
        "n": n, "coords": coords,
        "Ix": round(Ix, 4), "Iy": round(Iy, 4),
        "P_max_kN": round(Pmax, 1), "P_min_kN": round(Pmin, 1),
        "hay_traccion": Pmin < -1e-6,
        "cargas_kN": [round(c, 1) for c in cargas],
    }


def carga_lateral(*, H, D, fc, recubrimiento=0.075, tipo="nh", nh=0.0, k=0.0,
                  cabeza="libre") -> dict:
    """Análisis de carga lateral por el método de la longitud característica
    (Matlock-Reese / Davisson).

    - Arena (módulo que crece con z, ``nh`` en kN/m³):
        T = (EI/nh)^(1/5),  Mmax = 0.77·H·T,  y0 = 2.43·H·T³/EI (cabeza libre).
    - Arcilla (módulo constante, ``k`` = kh en kN/m³):
        R = (EI/k)^(1/4),  Mmax = 0.74·H·R,  y0 = 1.3·H·R³/EI (cabeza libre).
    Con cabeza fija (empotrada en el cabezal) el momento en la cabeza domina y se
    reduce el coeficiente. EI = 0.5·Ec·Ig (rigidez efectiva a flexión)."""
    if H <= 1e-9:
        return {"aplica": False, "Mmax_kNm": 0.0, "y0_mm": 0.0}
    Ec = 4700.0 * math.sqrt(fc) * 1000.0            # kPa
    Ig = math.pi * D ** 4 / 64.0
    EI = 0.5 * Ec * Ig                              # kN·m²
    fija = str(cabeza).startswith("fij")
    if tipo == "k" and k > 0:
        Rc = (EI / k) ** 0.25
        cM = 0.55 if fija else 0.74
        Mmax = cM * H * Rc
        y0 = (0.9 if fija else 1.3) * H * Rc ** 3 / EI
        longitud = Rc
        etiqueta = "R (arcilla, k const.)"
    else:
        nh_ = nh if nh > 0 else 5000.0              # valor típico si falta
        T = (EI / nh_) ** 0.2
        cM = 0.60 if fija else 0.77
        Mmax = cM * H * T
        y0 = (0.93 if fija else 2.43) * H * T ** 3 / EI
        longitud = T
        etiqueta = "T (arena, nh)"
    return {
        "aplica": True, "cabeza": "fija" if fija else "libre",
        "EI_kNm2": round(EI, 1), "long_caracteristica_m": round(longitud, 3),
        "etiqueta": etiqueta,
        "Mmax_kNm": round(Mmax, 1), "y0_mm": round(y0 * 1000.0, 2),
        "H_kN": round(H, 1),
    }


def cortante_circular(*, Vu, D, fc, fy, db_trans, recubrimiento, espiral,
                      s_trans=0.0) -> dict:
    """Cortante de la sección circular (ACI 22.5): bw = D, d = 0.8·D.
    Vc = 0.17·√f'c·bw·d;  si Vu > φVc, aporta el refuerzo transversal
    (espiral/estribos) como cortante Vs = A_v·fyt·d/s."""
    bw = D
    d = 0.8 * D
    Vc = 0.17 * math.sqrt(fc) * 1000.0 * bw * d      # kN
    phiVc = 0.75 * Vc
    Asp = math.pi * (db_trans / 1000.0) ** 2 / 4.0
    Av = 2.0 * Asp if espiral else 2.0 * Asp         # dos ramas
    Vs = 0.0
    phiVn = phiVc
    if s_trans > 1e-6:
        Vs = Av * fy * 1000.0 * d / s_trans
        phiVn = 0.75 * (Vc + Vs)
    return {
        "Vu_kN": round(Vu, 1), "d_m": round(d, 3),
        "phiVc_kN": round(phiVc, 1), "Vs_kN": round(Vs, 1),
        "phiVn_kN": round(phiVn, 1),
        "requiere_refuerzo": Vu > phiVc + 1e-6,
        "cumple": Vu <= phiVn + 1e-6,
    }


def pandeo_davisson(*, Pu, EI, Lu, tipo="nh", nh=0.0, k=0.0, beta=1.0,
                    FS=2.5) -> dict:
    """Pandeo de un pilote parcialmente embebido (Davisson & Robinson, 1965).

    Se reemplaza el tramo embebido por una profundidad a la fijación z_f y se
    evalúa la carga crítica de Euler de la columna equivalente de longitud
    L_e = L_u + z_f:

        arena (n_h):  z_f = 1.8·T,  T = (EI/n_h)^(1/5)
        arcilla (k):  z_f = 1.4·R,  R = (EI/k)^(1/4)
        P_cr = π²·EI / (β·L_e)²

    ``beta`` = factor de longitud efectiva (1.0 biempotrado equivalente, 2.0
    cabeza libre). Se compara P_u con P_cr/FS."""
    if tipo == "k" and k > 0:
        Rc = (EI / k) ** 0.25
        zf = 1.4 * Rc
    else:
        nh_ = nh if nh > 0 else 5000.0
        T = (EI / nh_) ** 0.2
        zf = 1.8 * T
    Le = Lu + zf
    Pcr = math.pi ** 2 * EI / (beta * Le) ** 2 if Le > 0 else float("inf")
    Padm = Pcr / FS
    return {
        "z_fijacion_m": round(zf, 3), "Le_m": round(Le, 3),
        "Pcr_kN": round(Pcr, 1), "Padm_kN": round(Padm, 1),
        "ratio": round(Pu / Padm, 3) if Padm > 0 else None,
        "cumple": Pu <= Padm + 1e-6,
        "aplica": Lu > 1e-6,
    }


def friccion_negativa(*, D, fs_neg, L_downdrag, P_servicio=0.0) -> dict:
    """Fricción negativa / downdrag: cuando el suelo blando consolida, arrastra
    el pilote hacia abajo y suma carga axial.

        Q_n = f_s,neg · (π·D) · L_downdrag

    El plano neutro se sitúa (de forma simplificada) al final del estrato que
    consolida; por encima, el pilote soporta P + Q_n."""
    if fs_neg <= 1e-9 or L_downdrag <= 1e-9:
        return {"aplica": False, "Qn_kN": 0.0}
    Qn = fs_neg * math.pi * D * L_downdrag
    return {
        "aplica": True, "Qn_kN": round(Qn, 1),
        "plano_neutro_m": round(L_downdrag, 2),
        "P_con_downdrag_kN": round(P_servicio + Qn, 1),
    }


def confinamiento_sismico(*, D, fc, fy, db_long, recubrimiento, db_trans,
                          espiral, Lu=0.0, disipacion="DMO") -> dict:
    """Confinamiento de la zona de rótula plástica en la cabeza del pilote
    (NSR-10 C.21). Longitud de confinamiento y paso del refuerzo transversal.

    - Espiral: ρ_s = máx[0.45·(Ag/Ach−1)·f'c/fyt, 0.12·f'c/fyt].
    - Estribos: s ≤ mín(6·d_b, D/4, 100 mm) en la zona de confinamiento.
    """
    R = D / 2.0
    Ag = math.pi * R * R
    dc = D - 2.0 * recubrimiento
    Ach = math.pi * dc ** 2 / 4.0
    fc_k, fyt_k = fc * 1000.0, fy * 1000.0
    lo = max(D, Lu / 6.0, 0.45)                  # longitud de confinamiento (m)
    if espiral:
        rho_s = max(0.45 * (Ag / Ach - 1.0) * (fc_k / fyt_k),
                    0.12 * (fc_k / fyt_k)) if Ach > 0 else 0.0
        Asp = math.pi * (db_trans / 1000.0) ** 2 / 4.0
        paso = (4.0 * Asp / (dc * rho_s)) if rho_s > 0 else 0.075
        paso = min(paso, 0.075)
        detalle = {"tipo": "espiral", "rho_s_confinamiento": round(rho_s, 4),
                   "paso_confinado_m": round(paso, 3)}
    else:
        s = min(6.0 * db_long / 1000.0, D / 4.0, 0.10)
        detalle = {"tipo": "estribo", "sep_confinada_m": round(s, 3)}
    return {
        "longitud_confinamiento_m": round(lo, 2),
        "disipacion": disipacion, **detalle,
    }
