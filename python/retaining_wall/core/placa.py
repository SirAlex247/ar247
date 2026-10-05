"""Diseño de placa / losa de cimentación maciza (*mat foundation*) por el
método rígido convencional (NSR-10 / ACI 318; Bowles cap. 10, Das cap. 5).

La losa se supone RÍGIDA: la presión de contacto varía linealmente y se obtiene
por flexión biaxial de la sección de la losa,

        q(x, y) = R/A ± (R·e_x)·x'/I_y ± (R·e_y)·y'/I_x,

con R la resultante de las cargas de columna, (e_x, e_y) su excentricidad
respecto al centroide de la losa e (I_x, I_y) los momentos de inercia de la
planta. El diseño estructural:

  - Punzonamiento (dos vías) en CADA columna (sección crítica a d/2).
  - Flexión por el MÉTODO DE LAS FRANJAS: la losa se idealiza como una viga
    ancha en cada dirección, cargada hacia arriba por la reacción del suelo y
    hacia abajo por las columnas; el diagrama de momentos da el acero inferior
    (M⁺) y superior (M⁻). También se verifica el cortante como viga ancha.

Unidades SI internas: m, kN, kN·m, kPa (= kN/m²), MPa, kN/m³.
"""
from __future__ import annotations

import math

from .zapata import (
    PHI_CORTE,
    PHI_FLEX,  # noqa: F401  (reexport de conveniencia)
    _area_barra,  # noqa: F401
    _longitud_desarrollo,
    _redondea_arriba,
    _transferencia_carga,
)
from .zapatas_tipos import _As_de_Mu, _punz_columna, _punz_columna_momento


# ===========================================================================
# Preparación de la geometría (lista de columnas + tamaño de la losa)
# ===========================================================================
def _prepara_columnas(columnas, B, L, voladizo, factor_carga):
    """Normaliza la lista de columnas y, si ``B``/``L`` no se dan, dimensiona la
    losa por los extremos de las columnas más un voladizo perimetral.

    Cada columna: {x, y, P (servicio), Pu (opc.), c1, c2}. Las posiciones se
    reubican para que la losa ocupe [0, B] × [0, L]."""
    cols = []
    for c in columnas:
        P = float(c.get("P", c.get("P_servicio", 0.0)) or 0.0)
        Pu = float(c.get("Pu", 0.0) or 0.0) or factor_carga * P
        Mx = float(c.get("Mx", 0.0) or 0.0)
        My = float(c.get("My", 0.0) or 0.0)
        cols.append({
            "x": float(c.get("x", 0.0) or 0.0),
            "y": float(c.get("y", 0.0) or 0.0),
            "P": P, "Pu": Pu,
            "c1": float(c.get("c1", 0.40) or 0.40),
            "c2": float(c.get("c2", 0.40) or 0.40),
            "Mx": Mx, "My": My,
            "Mux": float(c.get("Mux", 0.0) or 0.0) or factor_carga * abs(Mx),
            "Muy": float(c.get("Muy", 0.0) or 0.0) or factor_carga * abs(My),
        })
    xs = [c["x"] for c in cols]
    ys = [c["y"] for c in cols]
    auto = (not B or B <= 0 or not L or L <= 0)
    if auto:
        xmin, xmax = min(xs), max(xs)
        ymin, ymax = min(ys), max(ys)
        B = round((xmax - xmin) + 2.0 * voladizo, 3)
        L = round((ymax - ymin) + 2.0 * voladizo, 3)
        for c in cols:
            c["x"] = round(c["x"] - xmin + voladizo, 4)
            c["y"] = round(c["y"] - ymin + voladizo, 4)
    return cols, round(B, 3), round(L, 3), auto


def _presiones(cols, B, L, load_key="P", extra_uniforme=0.0):
    """Presiones en las 4 esquinas por el método rígido (flexión biaxial).

    ``load_key`` = 'P' (servicio) o 'Pu' (mayorado). ``extra_uniforme`` es una
    presión uniforme adicional (peso propio + sobrecarga de suelo), centrada."""
    A = B * L
    R = sum(c[load_key] for c in cols)
    if R <= 0 or A <= 0:
        return {"A": A, "R": 0.0, "xbar": B / 2.0, "ybar": L / 2.0,
                "ex": 0.0, "ey": 0.0, "q_max": 0.0, "q_min": 0.0,
                "q_prom": extra_uniforme, "esquinas": {}, "q_func": lambda x, y: extra_uniforme}
    xbar = sum(c[load_key] * c["x"] for c in cols) / R
    ybar = sum(c[load_key] * c["y"] for c in cols) / R
    ex = xbar - B / 2.0
    ey = ybar - L / 2.0
    Iy = L * B ** 3 / 12.0        # inercia para e_x (flexión respecto al eje y)
    Ix = B * L ** 3 / 12.0        # inercia para e_y (flexión respecto al eje x)
    Rt = R + extra_uniforme * A

    def q(x, y):
        return (Rt / A
                + (R * ex) * (x - B / 2.0) / Iy
                + (R * ey) * (y - L / 2.0) / Ix)

    esquinas = {
        "q_00": q(0.0, 0.0), "q_B0": q(B, 0.0),
        "q_0L": q(0.0, L), "q_BL": q(B, L),
    }
    qs = list(esquinas.values())
    return {"A": A, "R": R, "xbar": xbar, "ybar": ybar, "ex": ex, "ey": ey,
            "q_max": max(qs), "q_min": min(qs), "q_prom": Rt / A,
            "esquinas": esquinas, "q_func": q}


def _posicion_punz(x, y, c1, c2, d, B, L):
    """Clasifica la columna para α_s del punzonamiento según cuántos bordes de
    la losa cortan su perímetro crítico (a d/2 de la cara)."""
    borde_x = min(x, B - x) < (c1 / 2.0 + d / 2.0) - 1e-9
    borde_y = min(y, L - y) < (c2 / 2.0 + d / 2.0) - 1e-9
    return {0: "interior", 1: "borde", 2: "esquina"}[int(borde_x) + int(borde_y)]


# ===========================================================================
# Franja de diseño (viga ancha en una dirección)
# ===========================================================================
def _franja(cols, key, longitud, ancho, Ru, d, fc, fy, rec, db, h, sqrt_fc):
    """Momentos y cortante de la losa idealizada como viga ancha en una
    dirección. ``key`` = 'x' o 'y'; ``longitud`` = luz de la franja; ``ancho`` =
    ancho tributario (toda la losa). Reacción del suelo hacia arriba
    w = Ru/longitud; cargas de columna hacia abajo en su proyección."""
    w = Ru / longitud if longitud > 0 else 0.0
    pts = sorted((c[key], c["Pu"]) for c in cols)

    def M(s):
        m = w * s * s / 2.0
        for si, Pui in pts:
            if s > si:
                m -= Pui * (s - si)
        return m

    def V(s):
        v = w * s
        for si, Pui in pts:
            if s > si:
                v -= Pui
        return v

    N = 400
    M_pos = M_neg = 0.0
    s_pos = s_neg = 0.0
    for i in range(N + 1):
        s = longitud * i / N
        m = M(s)
        if m > M_pos:
            M_pos, s_pos = m, s
        if m < M_neg:
            M_neg, s_neg = m, s
    Vmax = 0.0
    for si, _ in pts:
        Vmax = max(Vmax, abs(V(si - 1e-6)), abs(V(si + 1e-6)))

    As_inf = _As_de_Mu(M_pos, ancho, d, fc, fy, rec, db, h)      # M⁺ → acero inferior
    As_sup = _As_de_Mu(-M_neg, ancho, d, fc, fy, rec, db, h)     # M⁻ → acero superior
    # Longitud de desarrollo: disponible ≈ media luz de la franja (barras corren
    # de un apoyo a otro; el punto crítico está entre columnas).
    ld = _longitud_desarrollo(db, fc, fy, longitud / 2.0, rec)
    As_inf["desarrollo"] = ld
    As_sup["desarrollo"] = ld
    phiVc = PHI_CORTE * 0.17 * sqrt_fc * 1000.0 * ancho * d
    return {
        "eje": key, "w_kN_m": round(w, 1), "longitud_m": round(longitud, 3),
        "ancho_m": round(ancho, 3),
        "M_pos_kNm": round(M_pos, 1), "s_M_pos_m": round(s_pos, 3),
        "M_neg_kNm": round(M_neg, 1), "s_M_neg_m": round(s_neg, 3),
        "V_max_kN": round(Vmax, 1), "phiVc_kN": round(phiVc, 1),
        "cumple_cortante": Vmax <= phiVc,
        "acero_inferior": As_inf, "acero_superior": As_sup,
    }


def _punz_todas(cols, qfun_u, h, sqrt_fc, rec, db, B, L):
    """Punzonamiento (con transferencia de momento γv) de todas las columnas;
    devuelve (lista, todas_cumplen)."""
    d = max(0.05, h - rec - db)
    res = []
    ok = True
    for i, c in enumerate(cols):
        qu_loc = max(0.0, qfun_u(c["x"], c["y"]))
        pos = _posicion_punz(c["x"], c["y"], c["c1"], c["c2"], d, B, L)
        p = _punz_columna_momento(c["Pu"], qu_loc, c["c1"], c["c2"], h, sqrt_fc,
                                  rec, db, pos, c.get("Mux", 0.0), c.get("Muy", 0.0))
        p["columna"] = i + 1
        p["posicion"] = pos
        res.append(p)
        ok = ok and p["cumple_momento"]
    return res, ok


def _transferencia_todas(cols, h, B, L, fc, fc_col, fy, rec, db_dowel):
    """Transferencia de carga columna→losa (aplastamiento + dowels) por columna
    (NSR-10 C.15.8). Devuelve (lista, todas_cumplen)."""
    res = []
    ok = True
    for i, c in enumerate(cols):
        t = _transferencia_carga(c["Pu"], c["c1"], c["c2"], h, B, L, fc, fc_col,
                                 fy, rec, db_dowel)
        t["columna"] = i + 1
        res.append(t)
        ok = ok and t["cumple_aplastamiento"] and t["cumple_dowels"]
    return res, ok


# ===========================================================================
# Diseño principal
# ===========================================================================
def disenar_placa(*, columnas, q_adm, B=0.0, L=0.0, h=0.0,
                  fc=21.0, fy=420.0, recubrimiento=0.075, db=0.01905,
                  Df=1.5, gamma_suelo=18.0, gamma_concreto=24.0,
                  factor_carga=1.5, voladizo=0.5,
                  fc_columna=0.0, db_dowel=0.0) -> dict:
    """Diseña (o verifica) una placa/losa de cimentación maciza rígida.

    ``columnas``: lista de dicts {x, y, P, Pu?, c1, c2} (posiciones en m, cargas
    en kN). Si ``B``/``L`` no se dan, la planta se dimensiona por los extremos
    de las columnas más ``voladizo`` perimetral.
    """
    sqrt_fc = math.sqrt(fc)
    avisos = []
    if not columnas:
        raise ValueError("Debes definir al menos una columna sobre la placa.")
    cols, B, L, auto = _prepara_columnas(columnas, B, L, voladizo, factor_carga)
    A = B * L
    Ru = sum(c["Pu"] for c in cols)
    R = sum(c["P"] for c in cols)

    # --- Espesor: dado o automático (punzonamiento de todas + cortante franjas) ---
    def _cumple_todo(hh):
        d = max(0.05, hh - recubrimiento - db)
        qfun_u = _presiones(cols, B, L, "Pu")["q_func"]
        _, ok_p = _punz_todas(cols, qfun_u, hh, sqrt_fc, recubrimiento, db, B, L)
        fx = _franja(cols, "x", B, L, Ru, d, fc, fy, recubrimiento, db, hh, sqrt_fc)
        fy_ = _franja(cols, "y", L, B, Ru, d, fc, fy, recubrimiento, db, hh, sqrt_fc)
        return ok_p and fx["cumple_cortante"] and fy_["cumple_cortante"]

    if h and h > 0:
        h = round(h, 3)
    else:
        h = 0.30
        for _ in range(300):
            if _cumple_todo(h):
                break
            h += 0.05
        h = round(h, 3)
    d = max(0.05, h - recubrimiento - db)

    # --- Geotecnia (servicio, con peso propio + sobrecarga como uniforme) ---
    peso_area = gamma_concreto * h + gamma_suelo * max(0.0, Df - h)
    pg = _presiones(cols, B, L, "P", extra_uniforme=peso_area)
    q_max, q_min = pg["q_max"], pg["q_min"]
    cumple_geo = (q_max <= q_adm * 1.001) and (q_min >= -1e-6)
    if q_max > q_adm * 1.001:
        avisos.append("La presión máxima de contacto supera la admisible: "
                      "aumenta B×L (o el voladizo) o mejora q_adm.")
    if q_min < -1e-6:
        avisos.append("Hay despegue del suelo (q_mín < 0): la resultante de las "
                      "cargas sale del núcleo central. Recentra las columnas o "
                      "amplía la losa.")

    # --- Estructural ---
    qfun_u = _presiones(cols, B, L, "Pu")["q_func"]
    punz, ok_punz = _punz_todas(cols, qfun_u, h, sqrt_fc, recubrimiento, db, B, L)
    idx_punz = max(range(len(punz)),
                   key=lambda i: punz[i].get("ratio_momento") or punz[i]["ratio"] or 0.0)
    franja_x = _franja(cols, "x", B, L, Ru, d, fc, fy, recubrimiento, db, h, sqrt_fc)
    franja_y = _franja(cols, "y", L, B, Ru, d, fc, fy, recubrimiento, db, h, sqrt_fc)
    cumple_cort = ok_punz and franja_x["cumple_cortante"] and franja_y["cumple_cortante"]
    if not cumple_cort:
        avisos.append("El cortante (punzonamiento con momento o viga ancha) no "
                      "cumple con el espesor: aumenta h.")

    # --- Transferencia de carga columna→losa (aplastamiento + dowels, C.15.8) ---
    fc_col = fc_columna if (fc_columna and fc_columna > 0) else fc
    db_dow = db_dowel if (db_dowel and db_dowel > 0) else db
    transferencia, ok_transf = _transferencia_todas(
        cols, h, B, L, fc, fc_col, fy, recubrimiento, db_dow)
    idx_transf = max(range(len(transferencia)),
                     key=lambda i: transferencia[i]["ratio"] or 0.0)
    if not ok_transf:
        avisos.append("La transferencia de carga columna-losa (aplastamiento o "
                      "dowels) no cumple en alguna columna: revisa f'c o los dowels.")
    # ℓd de las franjas
    if (franja_x["acero_inferior"]["desarrollo"]["requiere_gancho"]
            or franja_y["acero_inferior"]["desarrollo"]["requiere_gancho"]):
        avisos.append("Alguna barra de flexión de las franjas no desarrolla su "
                      "longitud disponible: usa gancho o barras de menor diámetro.")

    if abs(pg["ex"]) > B / 6.0 or abs(pg["ey"]) > L / 6.0:
        avisos.append("La excentricidad de las cargas excede el núcleo central "
                      "(e > B/6 o L/6); el método de las franjas con presión "
                      "uniforme es aproximado, verifica con la presión trapezoidal.")
    avisos.append("Método rígido convencional: válido si la losa es rígida frente "
                  "al suelo (K_r > 0.5, Bowles). Para losas flexibles o cargas muy "
                  "irregulares usa un análisis sobre resortes (Winkler) o EF.")

    qu_prom = Ru / A if A else 0.0
    return {
        "tipo": "placa",
        "geometria": {
            "B_m": B, "L_m": L, "h_m": h, "d_m": round(d, 4),
            "area_m2": round(A, 3), "volumen_concreto_m3": round(A * h, 3),
            "voladizo_m": round(voladizo, 3), "n_columnas": len(cols),
            "auto_dimensionada": auto,
            "columnas": [{"x_m": round(c["x"], 3), "y_m": round(c["y"], 3),
                          "P_kN": round(c["P"], 1), "Pu_kN": round(c["Pu"], 1),
                          "c1_m": c["c1"], "c2_m": c["c2"]} for c in cols],
        },
        "geotecnico": {
            "q_adm_kPa": round(q_adm, 1), "R_servicio_kN": round(R, 1),
            "P_total_servicio_kN": round(R + peso_area * A, 1),
            "x_centroide_carga_m": round(pg["xbar"], 3),
            "y_centroide_carga_m": round(pg["ybar"], 3),
            "e_x_m": round(pg["ex"], 4), "e_y_m": round(pg["ey"], 4),
            "q_prom_kPa": round(pg["q_prom"], 1),
            "q_max_kPa": round(q_max, 1), "q_min_kPa": round(q_min, 1),
            "esquinas_kPa": {k: round(v, 1) for k, v in pg["esquinas"].items()},
            "ratio": round(q_max / q_adm, 3) if q_adm > 0 else None,
            "cumple": cumple_geo,
        },
        "estructural": {
            "Ru_kN": round(Ru, 1), "qu_prom_kPa": round(qu_prom, 1),
            "factor_carga": factor_carga, "h_m": h, "d_m": round(d, 4),
            "punzonamiento": punz,
            "punz_critico": punz[idx_punz],
            "transferencia": transferencia,
            "transf_critica": transferencia[idx_transf],
            "franja_x": franja_x, "franja_y": franja_y,
            "cumple_cortante": cumple_cort,
            "cumple_transferencia": ok_transf,
        },
        "avisos": avisos,
    }


# ===========================================================================
# Utilidad: construir una malla regular de columnas
# ===========================================================================
def malla_columnas(*, nx, ny, sx, sy, P, c1=0.40, c2=0.40, Pu=0.0,
                   factor_carga=1.5, Mx=0.0, My=0.0):
    """Genera una malla regular ``nx × ny`` de columnas igualmente espaciadas
    (``sx``, ``sy``) con la misma carga ``P`` (y momento por columna ``Mx``/``My``
    opcional). Devuelve la lista de columnas."""
    nx = max(1, int(nx))
    ny = max(1, int(ny))
    cols = []
    for j in range(ny):
        for i in range(nx):
            cols.append({"x": i * sx, "y": j * sy, "P": P,
                         "Pu": Pu or factor_carga * P, "c1": c1, "c2": c2,
                         "Mx": Mx, "My": My})
    return cols
