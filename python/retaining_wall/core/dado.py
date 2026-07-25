"""Diseño de dado / cabezal de pilotes (encepado) — NSR-10 / ACI 318.

El dado es el bloque de concreto que recibe la columna y reparte su carga a un
grupo de 1 a 6 pilotes. Se verifica (Ref. "Guía para el diseño de pilotes",
R. Urbina, cap. 9; NSR-10 Título C):

  1. Clasificación rígido/flexible (m ≤ 1.5·H → rígido).
  2. Reacciones en los pilotes (carga axial + momentos biaxiales).
  3. Capacidad de cada pilote (R_i ≤ capacidad del pilote).
  4. Punzonamiento (dos vías) alrededor de la columna y de los pilotes.
  5. Cortante por flexión (una vía) a 'd' de la cara de la columna.
  6. Flexión en la cara de la columna (acero por el método seccional).
  7. Método de bielas (puntal-tensor) para encepados rígidos.
  8. Longitud de anclaje (desarrollo) de las barras de la columna en el dado.

Unidades SI internas: m, kN, kN·m, kPa (= kN/m²), MPa.
"""
from __future__ import annotations

import math

PHI_FLEX = 0.90
PHI_CORTE = 0.75


def _area_barra(db_m: float) -> float:
    return math.pi * db_m ** 2 / 4.0


def _redondea_arriba(x: float, paso: float = 0.05) -> float:
    return math.ceil(x / paso - 1e-9) * paso


def _alpha_s(posicion: str) -> float:
    return {"interior": 40.0, "borde": 30.0, "esquina": 20.0}.get(posicion, 40.0)


# ----------------------------------------------------------------------------
# Geometría del grupo de pilotes
# ----------------------------------------------------------------------------
def geometria_grupo(n: int, s: float, e: float, Dp: float):
    """Coordenadas (x, y) de los pilotes y dimensiones del dado.

    s = separación entre ejes de pilotes; e = distancia del eje del pilote
    perimetral al borde del dado. Devuelve (coords, forma, Bx, Ly, area, vertices).
    """
    if n == 1:
        coords = [(0.0, 0.0)]; forma = "rect"
    elif n == 2:
        coords = [(-s / 2, 0.0), (s / 2, 0.0)]; forma = "rect"
    elif n == 3:
        R = s / math.sqrt(3.0)
        coords = [(0.0, R), (-s / 2, -R / 2), (s / 2, -R / 2)]; forma = "tri"
    elif n == 4:
        coords = [(-s / 2, -s / 2), (s / 2, -s / 2), (-s / 2, s / 2), (s / 2, s / 2)]; forma = "rect"
    elif n == 5:
        coords = [(-s / 2, -s / 2), (s / 2, -s / 2), (-s / 2, s / 2), (s / 2, s / 2), (0.0, 0.0)]; forma = "rect"
    elif n == 6:
        coords = [(-s / 2, -s), (s / 2, -s), (-s / 2, 0.0), (s / 2, 0.0), (-s / 2, s), (s / 2, s)]; forma = "rect"
    else:
        raise ValueError("n_pilotes debe estar entre 1 y 6")

    xs = [c[0] for c in coords]; ys = [c[1] for c in coords]
    vertices = None
    if forma == "rect":
        Bx = max((max(xs) - min(xs)) + 2 * e, Dp + 0.30)
        Ly = max((max(ys) - min(ys)) + 2 * e, Dp + 0.30)
        area = Bx * Ly
    else:  # triángulo equilátero
        R = s / math.sqrt(3.0)
        inradio = R / 2.0 + e
        lado = 2.0 * math.sqrt(3.0) * inradio
        Rc = lado / math.sqrt(3.0)
        vertices = [(Rc * math.cos(math.radians(a)), Rc * math.sin(math.radians(a)))
                    for a in (90.0, 210.0, 330.0)]
        vx = [v[0] for v in vertices]; vy = [v[1] for v in vertices]
        Bx = max(vx) - min(vx)
        Ly = max(vy) - min(vy)
        area = math.sqrt(3.0) / 4.0 * lado ** 2
    return coords, forma, Bx, Ly, area, vertices


# ----------------------------------------------------------------------------
# Reacciones en los pilotes
# ----------------------------------------------------------------------------
def reacciones(coords, P, Mux=0.0, Muy=0.0):
    """R_i = P/n + Muy·x_i/Σx² + Mux·y_i/Σy².  (Mux flexiona en y; Muy en x.)"""
    n = len(coords)
    sx2 = sum(c[0] ** 2 for c in coords)
    sy2 = sum(c[1] ** 2 for c in coords)
    R = []
    for (x, y) in coords:
        r = P / n
        if sx2 > 1e-9:
            r += Muy * x / sx2
        if sy2 > 1e-9:
            r += Mux * y / sy2
        R.append(r)
    return R


# ----------------------------------------------------------------------------
# Punzonamiento (dos vías)
# ----------------------------------------------------------------------------
def _punz_columna(coords, R, c1, c2, d, sqrt_fc, P_col, posicion):
    bo = 2.0 * (c1 + d) + 2.0 * (c2 + d)
    hx = (c1 + d) / 2.0; hy = (c2 + d) / 2.0
    R_int = sum(r for (x, y), r in zip(coords, R) if abs(x) <= hx and abs(y) <= hy)
    Vu = P_col - R_int
    beta_c = max(c1, c2) / min(c1, c2)
    alfa = _alpha_s(posicion)
    vc = min(0.33 * sqrt_fc,
             0.17 * (1.0 + 2.0 / beta_c) * sqrt_fc,
             0.083 * (alfa * d / bo + 2.0) * sqrt_fc)
    phiVc = PHI_CORTE * vc * 1000.0 * bo * d
    return {"b0_m": round(bo, 4), "vc_MPa": round(vc, 3), "Vu_kN": round(Vu, 1),
            "phiVc_kN": round(phiVc, 1),
            "ratio": round(Vu / phiVc, 3) if phiVc > 0 else None,
            "cumple": Vu <= phiVc}


def _punz_pilote(Dp, d, sqrt_fc, R_max):
    bo = math.pi * (Dp + d)
    vc = min(0.33 * sqrt_fc, 0.083 * (40.0 * d / bo + 2.0) * sqrt_fc)
    phiVc = PHI_CORTE * vc * 1000.0 * bo * d
    return {"b0_m": round(bo, 4), "vc_MPa": round(vc, 3), "Vu_kN": round(R_max, 1),
            "phiVc_kN": round(phiVc, 1),
            "ratio": round(R_max / phiVc, 3) if phiVc > 0 else None,
            "cumple": R_max <= phiVc}


# ----------------------------------------------------------------------------
# Cortante en una vía y flexión (método seccional, por dirección)
# ----------------------------------------------------------------------------
def _suma_lado(coords, R, eje, limite):
    """Σ reacciones del lado más cargado más allá de |coord_eje| > limite."""
    idx = 0 if eje == "x" else 1
    pos = sum(r for c, r in zip(coords, R) if c[idx] > limite)
    neg = sum(r for c, r in zip(coords, R) if c[idx] < -limite)
    if pos >= neg:
        brazo = sum(r * (c[idx] - limite) for c, r in zip(coords, R) if c[idx] > limite)
        return pos, brazo
    else:
        brazo = sum(r * (-c[idx] - limite) for c, r in zip(coords, R) if c[idx] < -limite)
        return neg, brazo


def _cortante_una_via(coords, R, eje, c_cara, d, b_ancho, sqrt_fc):
    """Sección crítica a 'd' de la cara de la columna (a c/2 + d del centro)."""
    Vu, _ = _suma_lado(coords, R, eje, c_cara / 2.0 + d)
    phiVc = PHI_CORTE * 0.17 * sqrt_fc * 1000.0 * b_ancho * d
    return {"Vu_kN": round(Vu, 1), "phiVc_kN": round(phiVc, 1),
            "ratio": round(Vu / phiVc, 3) if phiVc > 0 else None,
            "cumple": Vu <= phiVc}


def _flexion(coords, R, eje, c_cara, d, b_ancho, fc, fy, rec, db, h):
    """Momento en la cara de la columna; acero repartido en b_ancho."""
    _, Mu = _suma_lado(coords, R, eje, c_cara / 2.0)         # kN·m
    Mu = max(Mu, 0.0)
    fy_k = fy * 1000.0; fc_k = fc * 1000.0
    As = Mu / (PHI_FLEX * fy_k * 0.95 * d) if d > 0 else 0.0
    for _ in range(30):
        a = As * fy_k / (0.85 * fc_k * b_ancho) if b_ancho > 0 else 0.0
        nuevo = Mu / (PHI_FLEX * fy_k * (d - a / 2.0)) if (d - a / 2.0) > 0 else As
        if abs(nuevo - As) < 1e-7:
            As = nuevo; break
        As = nuevo
    As_req = max(As, 0.0)
    As_min = 0.0018 * b_ancho * h
    As_fin = max(As_req, As_min)
    ab = _area_barra(db)
    nb = max(2, math.ceil(As_fin / ab)) if ab > 0 else 0
    sep = (b_ancho - 2 * rec) / (nb - 1) if nb > 1 else 0.0
    return {"Mu_kNm": round(Mu, 1), "As_req_cm2": round(As_req * 1e4, 2),
            "As_min_cm2": round(As_min * 1e4, 2), "As_cm2": round(As_fin * 1e4, 2),
            "gobierna_minimo": As_min >= As_req, "n_barras": nb,
            "db_mm": round(db * 1000.0, 1), "sep_cm": round(sep * 100.0, 1)}


# ----------------------------------------------------------------------------
# Método de bielas (puntal-tensor) — acero de tracción inferior
# ----------------------------------------------------------------------------
def _biela(coords, R, forma, c1, c2, d, fy, db):
    """Fuerza de tracción del tensor inferior y acero, por el método de bielas.
    Brazo interno Z = 0.875·d; el puntal entra a la columna a ~0.35·c."""
    z = 0.875 * d
    fy_k = fy * 1000.0
    ab = _area_barra(db)

    def tie(eje, c_dim):
        idx = 0 if eje == "x" else 1
        T = 0.0
        for c, r in zip(coords, R):
            run = abs(c[idx]) - 0.35 * c_dim
            if c[idx] > 1e-6 and run > 0:
                T += r * run / z
        As = T / (PHI_FLEX * fy_k) if T > 0 else 0.0
        nb = max(2, math.ceil(As / ab)) if (ab > 0 and As > 0) else 0
        return {"T_kN": round(T, 1), "As_cm2": round(As * 1e4, 2), "n_barras": nb}

    if forma == "tri":
        # Encepado triangular: tensor por arista (equilibrio radial en el nudo).
        R_prom = sum(R) / len(R)
        Rc = max(math.hypot(*c) for c in coords)         # circunradio de pilotes
        run = max(Rc - 0.35 * max(c1, c2), 0.0)
        T = R_prom * run / (z * math.sqrt(3.0))
        As = T / (PHI_FLEX * fy_k) if T > 0 else 0.0
        nb = max(2, math.ceil(As / ab)) if (ab > 0 and As > 0) else 0
        return {"tipo": "triangular", "arista": {"T_kN": round(T, 1),
                "As_cm2": round(As * 1e4, 2), "n_barras": nb}}
    return {"tipo": "rectangular", "x": tie("x", c1), "y": tie("y", c2)}


# ----------------------------------------------------------------------------
# Longitud de desarrollo a compresión (anclaje de barras de columna)
# ----------------------------------------------------------------------------
def _ldc(db, fy, fc):
    """NSR-10 C.25.4.9 (SI): ℓdc = máx(0.24·fy/√f'c·db, 0.043·fy·db, 0.20 m)."""
    sqrt_fc = math.sqrt(fc)
    l1 = 0.24 * fy / sqrt_fc * db
    l2 = 0.043 * fy * db
    return round(max(l1, l2, 0.20), 3)


# ----------------------------------------------------------------------------
# Función principal
# ----------------------------------------------------------------------------
def disenar_dado(*, n_pilotes, Dp, c1, c2, Pu, Mux=0.0, Muy=0.0,
                 s=0.0, e=0.0, h=0.0, fc=21.0, fy=420.0,
                 recubrimiento=0.075, db=0.01905, db_col=0.01905,
                 capacidad_pilote=0.0, gamma_concreto=24.0,
                 factor_peso=1.2, posicion="interior", metodo="ambos") -> dict:
    """Diseña (o verifica) un dado/cabezal sobre n_pilotes (1..6).

    metodo: acero inferior por 'flexion' (método seccional), 'bielas'
    (puntal-tensor) o 'ambos' (se adopta el mayor). Por defecto 'ambos'.
    """
    metodo = (metodo or "ambos").lower()
    if metodo not in ("flexion", "bielas", "ambos"):
        metodo = "ambos"
    sqrt_fc = math.sqrt(fc)
    avisos = []
    n = int(n_pilotes)

    if s <= 0:
        s = 3.0 * Dp
    if s < 2.5 * Dp - 1e-6 and n > 1:
        avisos.append("La separación entre pilotes es menor que 2.5·D; se recomienda s ≥ 3·D.")
    if e <= 0:
        e = max(0.40, 0.5 * Dp + 0.15)

    coords, forma, Bx, Ly, area, vertices = geometria_grupo(n, s, e, Dp)

    # ---- Espesor: estimación automática si no se da ----
    auto_h = (not h or h <= 0)
    if auto_h:
        h = max(0.40, round(0.5 * Dp + 0.30, 2))
        for _ in range(80):
            d_ = max(0.05, h - recubrimiento - db)
            R_ = reacciones(coords, Pu, Mux, Muy)
            pc = _punz_columna(coords, R_, c1, c2, d_, sqrt_fc, Pu, posicion)
            pp = _punz_pilote(Dp, d_, sqrt_fc, max(R_))
            cvx = _cortante_una_via(coords, R_, "x", c1, d_, Ly, sqrt_fc)
            cvy = _cortante_una_via(coords, R_, "y", c2, d_, Bx, sqrt_fc)
            if pc["cumple"] and pp["cumple"] and cvx["cumple"] and cvy["cumple"]:
                break
            h = round(h + 0.05, 3)
    h = round(h, 3)
    d = round(max(0.05, h - recubrimiento - db), 4)

    # ---- Reacciones (carga de columna para el diseño del dado) ----
    R = reacciones(coords, Pu, Mux, Muy)
    Wcap = gamma_concreto * area * h
    R_total = [r + factor_peso * Wcap / n for r in R]    # + peso del dado (para el pilote)
    Pmax = max(R_total); Pmin = min(R_total)

    cumple_pilote = True
    if capacidad_pilote and capacidad_pilote > 0:
        cumple_pilote = Pmax <= capacidad_pilote * 1.001
        if not cumple_pilote:
            avisos.append("La reacción máxima de pilote supera su capacidad: aumenta el "
                          "número/diámetro de pilotes o reduce la carga.")
    if Pmin < -1e-6:
        avisos.append("Un pilote queda en tracción (R < 0): se requiere conexión a tracción "
                      "o revisar la excentricidad de la carga.")

    # ---- Chequeos estructurales ----
    pc = _punz_columna(coords, R, c1, c2, d, sqrt_fc, Pu, posicion)
    pp = _punz_pilote(Dp, d, sqrt_fc, max(R))
    cvx = _cortante_una_via(coords, R, "x", c1, d, Ly, sqrt_fc)
    cvy = _cortante_una_via(coords, R, "y", c2, d, Bx, sqrt_fc)
    fx = _flexion(coords, R, "x", c1, d, Ly, fc, fy, recubrimiento, db, h)
    fy_ = _flexion(coords, R, "y", c2, d, Bx, fc, fy, recubrimiento, db, h)
    biela = _biela(coords, R, forma, c1, c2, d, fy, db)
    ldc = _ldc(db_col, fy, fc)

    # ---- Acero inferior gobernante según el método elegido ----
    if biela["tipo"] == "triangular":
        bxa = bya = biela["arista"]["As_cm2"]
    else:
        bxa, bya = biela["x"]["As_cm2"], biela["y"]["As_cm2"]

    def _as_dir(flex, biela_as):
        if metodo == "flexion":
            return flex["As_cm2"]
        if metodo == "bielas":
            return biela_as
        return max(flex["As_cm2"], biela_as)

    as_x_rec = _as_dir(fx, bxa)
    as_y_rec = _as_dir(fy_, bya)

    cumple_cortante = pc["cumple"] and pp["cumple"] and cvx["cumple"] and cvy["cumple"]
    if not cumple_cortante:
        avisos.append("El cortante/punzonamiento no cumple con el espesor dado: aumenta h.")

    # ---- Clasificación rígido / flexible ----
    m_vol = max(max(abs(c[0]) for c in coords) - c1 / 2.0,
                max(abs(c[1]) for c in coords) - c2 / 2.0, 0.0)
    rigido = m_vol <= 1.5 * h
    clasificacion = "rígido" if rigido else "flexible"
    if rigido and metodo == "flexion":
        avisos.append("Encepado RÍGIDO (m ≤ 1.5·H): es una región D; se recomienda verificar también "
                      "el método de bielas (puntal-tensor).")
    elif rigido:
        avisos.append("Encepado RÍGIDO (m ≤ 1.5·H): el acero inferior se gobierna por el método de "
                      "bielas (puntal-tensor).")

    cumple = cumple_pilote and cumple_cortante

    return {
        "geometria": {
            "n_pilotes": n, "Dp_m": round(Dp, 3), "s_m": round(s, 3), "e_m": round(e, 3),
            "forma": forma, "Bx_m": round(Bx, 3), "Ly_m": round(Ly, 3),
            "h_m": h, "d_m": d, "c1_m": c1, "c2_m": c2,
            "area_m2": round(area, 3), "volumen_concreto_m3": round(area * h, 3),
            "coords": [[round(x, 3), round(y, 3)] for (x, y) in coords],
            "vertices": [[round(x, 3), round(y, 3)] for (x, y) in vertices] if vertices else None,
            "auto_dimensionada": auto_h, "clasificacion": clasificacion, "m_voladizo_m": round(m_vol, 3),
        },
        "cargas": {
            "Pu_kN": round(Pu, 1), "Mux_kNm": round(Mux, 1), "Muy_kNm": round(Muy, 1),
            "Wdado_kN": round(Wcap, 1),
            "reacciones_kN": [round(r, 1) for r in R_total],
            "Pmax_kN": round(Pmax, 1), "Pmin_kN": round(Pmin, 1),
            "capacidad_pilote_kN": round(capacidad_pilote, 1) if capacidad_pilote else None,
            "ratio_pilote": round(Pmax / capacidad_pilote, 3) if capacidad_pilote else None,
            "cumple_pilote": cumple_pilote,
        },
        "estructural": {
            "h_m": h, "d_m": d, "punz_columna": pc, "punz_pilote": pp,
            "cortante_x": cvx, "cortante_y": cvy, "flexion_x": fx, "flexion_y": fy_,
            "biela": biela, "ldc_columna_m": ldc, "metodo": metodo,
            "as_x_rec_cm2": round(as_x_rec, 2), "as_y_rec_cm2": round(as_y_rec, 2),
            "cumple_cortante": cumple_cortante,
        },
        "cumple": cumple,
        "avisos": avisos,
    }
