"""Cálculo de pilotes: capacidad de carga axial y diseño estructural.

Capacidad axial (Rodríguez Serquén / Das):
    Q_límite = Q_punta + Q_fuste,    Q_adm = Q_límite / FS
        Arenas:   Q_p = σ'v·Nq·A_b           f = K·σ'v·tanδ
        Arcillas: Q_p = 9·c_u·A_b             f = α·c_u
    - Nq (arenas): Meyerhof/Reissner, Nq = e^(π·tanφ)·tan²(45+φ/2).
    - Resistencia de punta en arena limitada por Meyerhof: q_l = 50·Nq·tanφ (kPa).
    - K para pilote perforado ≈ K0 = 1 − senφ ; δ = (0.5–0.8)φ.
    - Profundidad crítica ≈ 15·D (σ'v se mantiene constante a mayor profundidad).

Diseño estructural (NSR-10 / ACI 318): el pilote se verifica como columna
corta a compresión.
        φP_n,máx = φ·α·[0.85·f'c·(A_g − A_st) + fy·A_st]
        zuncho:  φ = 0.75, α = 0.85   |   estribos: φ = 0.65, α = 0.80

Unidades: m, kN, kPa, MPa, mm (coherentes con models/pilote.py).
"""
from __future__ import annotations

import math

from ..models.pilote import PiloteConcreto, PerfilSuelo, EstratoSuelo


# ----------------------------------------------------------------------------
# Factores geotécnicos
# ----------------------------------------------------------------------------
def nq_arena(phi_grados: float) -> float:
    """Factor de capacidad de carga Nq (Meyerhof/Reissner) para arenas."""
    r = math.radians(phi_grados)
    return math.exp(math.pi * math.tan(r)) * math.tan(math.radians(45 + phi_grados / 2.0)) ** 2


def alpha_arcilla(cu: float) -> float:
    """Factor de adherencia α (método α) en función de c_u (kPa).

    Aproximación práctica (API/Das): α = 1.0 para arcillas blandas
    (c_u ≤ 25 kPa), decrece linealmente hasta 0.5 para c_u ≥ 75 kPa.
    """
    if cu <= 25.0:
        return 1.0
    if cu >= 75.0:
        return 0.5
    return 1.0 - 0.5 * (cu - 25.0) / 50.0


def k_lateral(phi_grados: float, instalacion: str = "perforado") -> float:
    """Coeficiente de presión lateral K para el fuste en arenas.

    Perforado (vaciado in situ) ≈ K0 = 1 − senφ. Hincado de bajo/alto
    desplazamiento usa múltiplos de K0 (1.4·K0 / 1.8·K0).
    """
    k0 = 1.0 - math.sin(math.radians(phi_grados))
    inst = (instalacion or "perforado").lower()
    if inst.startswith("hincado_alto"):
        return 1.8 * k0
    if inst.startswith("hincado"):
        return 1.4 * k0
    return k0


# ----------------------------------------------------------------------------
# Capacidad de carga axial
# ----------------------------------------------------------------------------
def capacidad_axial(pilote: PiloteConcreto,
                    perfil: PerfilSuelo,
                    FS: float = 3.0,
                    instalacion: str = "perforado",
                    delta_factor: float = 0.6) -> dict:
    """Capacidad de carga axial del pilote.

    Returns un dict con Q_punta, Q_fuste, Q_límite, Q_adm (kN), el factor
    de seguridad y el detalle de la fricción por estrato.
    """
    D = pilote.D
    L = pilote.L
    Ab = pilote.area
    perim = pilote.perimetro
    z_critica = 15.0 * D            # profundidad crítica para σ'v en arenas

    # ---- Resistencia por fuste, integrando estrato por estrato ----
    # Cada estrato se subdivide en incrementos finos para integrar f(z)
    # correctamente (esfuerzo creciente, profundidad crítica, nivel freático).
    DZ = 0.25
    detalle = []
    Qs = 0.0
    prof = 0.0
    for e in perfil.estratos:
        top, bot = prof, prof + e.espesor
        prof = bot
        a = max(0.0, top)
        b = min(L, bot)
        if b <= a:                  # estrato fuera del empotramiento
            continue
        n_inc = max(1, int(math.ceil((b - a) / DZ)))
        paso = (b - a) / n_inc
        Qs_e = 0.0
        if e.tipo == "arena":
            K = k_lateral(e.phi, instalacion)
            tan_delta = math.tan(math.radians(delta_factor * e.phi))
        else:
            f_clay = alpha_arcilla(e.cu) * e.cu
        for i in range(n_inc):
            z = a + (i + 0.5) * paso
            if e.tipo == "arena":
                sigma = perfil.sigma_v_efectivo(min(z, z_critica))
                f = K * sigma * tan_delta
            else:
                f = f_clay
            Qs_e += f * perim * paso
        Qs += Qs_e
        f_prom = Qs_e / (perim * (b - a)) if (b - a) > 0 else 0.0
        detalle.append({
            "estrato": e.nombre or e.tipo,
            "tipo": e.tipo,
            "desde": round(a, 2), "hasta": round(b, 2),
            "f_prom_kPa": round(f_prom, 2),
            "Qs_kN": round(Qs_e, 1),
        })

    # ---- Resistencia por punta ----
    e_punta = perfil.estrato_en(L)
    if e_punta.tipo == "arena":
        sigma_p = perfil.sigma_v_efectivo(min(L, z_critica))
        Nq = nq_arena(e_punta.phi)
        qp_sin = sigma_p * Nq
        q_lim = 50.0 * Nq * math.tan(math.radians(e_punta.phi))   # límite Meyerhof
        qp = min(qp_sin, q_lim)
        punta_info = {"tipo": "arena", "sigma_v_kPa": round(sigma_p, 2),
                      "Nq": round(Nq, 2),
                      "qp_sin_limite_kPa": round(qp_sin, 1),
                      "q_limite_meyerhof_kPa": round(q_lim, 1),
                      "qp_kPa": round(qp, 1)}
    else:
        qp = 9.0 * e_punta.cu
        punta_info = {"tipo": "arcilla", "Nc": 9.0, "cu_kPa": round(e_punta.cu, 1),
                      "qp_kPa": round(qp, 1)}
    Qp = qp * Ab

    Qlim = Qp + Qs
    Qadm = Qlim / FS if FS > 0 else 0.0
    return {
        "Q_punta_kN": round(Qp, 1),
        "Q_fuste_kN": round(Qs, 1),
        "Q_limite_kN": round(Qlim, 1),
        "Q_adm_kN": round(Qadm, 1),
        "FS": FS,
        "punta": punta_info,
        "fuste_detalle": detalle,
    }


def numero_pilotes(P_servicio: float, Q_adm: float) -> int:
    """Número de pilotes requeridos para la carga de servicio (kN)."""
    if Q_adm <= 0:
        return 0
    return max(1, math.ceil(P_servicio / Q_adm))


# ----------------------------------------------------------------------------
# Diseño estructural (columna corta)
# ----------------------------------------------------------------------------
RHO_MIN_INSITU = 0.005     # cuantía mínima, pilote vaciado in situ (ACI 13.4 / NSR-10)
RHO_MAX_PRACT = 0.04       # cuantía práctica máxima (congestión)
RHO_MAX_CODE = 0.08        # cuantía máxima de código


def diseno_estructural(pilote: PiloteConcreto,
                       P_servicio: float | None = None,
                       N_pilotes: int = 1,
                       factor_carga: float = 1.5) -> dict:
    """Verificación estructural del pilote como columna corta a compresión.

    Returns dict con A_g, A_st, ρ, φP_n,máx (kN), verificación de cuantía y
    de refuerzo transversal, y comparación con la carga axial mayorada por
    pilote (si se entrega P_servicio).
    """
    Ag = pilote.area
    Ast = pilote.Ast
    rho = pilote.cuantia
    fc_kPa = pilote.fc * 1000.0
    fy_kPa = pilote.fy * 1000.0

    espiral = pilote.tipo_refuerzo.startswith("espiral") or pilote.tipo_refuerzo.startswith("zuncho")
    phi = 0.75 if espiral else 0.65
    alpha = 0.85 if espiral else 0.80

    Pn_max = 0.85 * fc_kPa * (Ag - Ast) + fy_kPa * Ast      # kN
    phiPn = phi * alpha * Pn_max                            # kN

    # Refuerzo transversal
    if espiral:
        Ach = pilote.area_nucleo
        fyt_kPa = fy_kPa
        rho_s_req = 0.45 * (Ag / Ach - 1.0) * (fc_kPa / fyt_kPa)
        Asp = math.pi * (pilote.db_trans / 1000.0) ** 2 / 4.0     # m²
        dc = pilote.diametro_nucleo
        paso = (4.0 * Asp / (dc * rho_s_req)) if rho_s_req > 0 else 0.0
        paso = min(paso, 0.075)        # paso máximo recomendado para zuncho ≈ 75 mm
        transversal = {
            "tipo": "espiral",
            "rho_s_requerida": round(rho_s_req, 4),
            "paso_m": round(paso, 3),
        }
    else:
        s_max = min(16 * pilote.db_long / 1000.0,
                    48 * pilote.db_trans / 1000.0,
                    pilote.D)
        transversal = {"tipo": "estribo", "separacion_max_m": round(s_max, 3)}

    # Verificación de cuantía
    avisos = []
    if rho < RHO_MIN_INSITU:
        avisos.append(f"ρ = {rho*100:.2f}% < ρ_mín {RHO_MIN_INSITU*100:.1f}% "
                      f"(pilote vaciado in situ).")
    if rho > RHO_MAX_CODE:
        avisos.append(f"ρ = {rho*100:.2f}% > ρ_máx de código {RHO_MAX_CODE*100:.0f}%.")
    elif rho > RHO_MAX_PRACT:
        avisos.append(f"ρ = {rho*100:.2f}% supera el {RHO_MAX_PRACT*100:.0f}% "
                      f"práctico (posible congestión).")

    res = {
        "A_g_m2": round(Ag, 4),
        "A_st_cm2": round(Ast * 1e4, 2),
        "cuantia_pct": round(rho * 100, 3),
        "phi": phi,
        "phiPn_kN": round(phiPn, 1),
        "transversal": transversal,
        "avisos": avisos,
        "cumple_cuantia": (RHO_MIN_INSITU <= rho <= RHO_MAX_CODE),
    }

    if P_servicio is not None and N_pilotes > 0:
        Pu_pila = factor_carga * P_servicio / N_pilotes
        res["Pu_por_pilote_kN"] = round(Pu_pila, 1)
        res["factor_carga"] = factor_carga
        res["cumple_estructural"] = phiPn >= Pu_pila
        res["ratio_demanda_capacidad"] = round(Pu_pila / phiPn, 3) if phiPn > 0 else None

    return res


# ----------------------------------------------------------------------------
# Análisis completo (capacidad + número de pilotes + estructural)
# ----------------------------------------------------------------------------
def analizar_pilote(pilote: PiloteConcreto,
                    perfil: PerfilSuelo,
                    P_servicio: float = 0.0,
                    FS: float = 3.0,
                    instalacion: str = "perforado",
                    delta_factor: float = 0.6,
                    factor_carga: float = 1.5) -> dict:
    """Ejecuta el análisis completo del pilote y devuelve un resultado único."""
    cap = capacidad_axial(pilote, perfil, FS=FS,
                          instalacion=instalacion, delta_factor=delta_factor)
    N = numero_pilotes(P_servicio, cap["Q_adm_kN"]) if P_servicio > 0 else 1
    est = diseno_estructural(pilote, P_servicio=(P_servicio or None),
                             N_pilotes=N, factor_carga=factor_carga)
    return {
        "geometria": {"D_m": pilote.D, "L_m": pilote.L,
                      "A_g_m2": round(pilote.area, 4),
                      "perimetro_m": round(pilote.perimetro, 3)},
        "capacidad": cap,
        "P_servicio_kN": P_servicio,
        "N_pilotes": N,
        "estructural": est,
    }


# ----------------------------------------------------------------------------
# Diseño estructural directo (geotecnia como dato de entrada)
# ----------------------------------------------------------------------------
DIAMETROS_STD = [0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.70, 0.80, 0.90, 1.00, 1.20]


def disenar_pilote_estructural(*, P_servicio, factor_carga=1.5, Pu=0.0,
                               f_s=0.0, q_p=0.0, FS=2.5,
                               fc=21.0, fy=420.0, cuantia=0.01,
                               tipo_refuerzo="espiral",
                               db_long=0.01905, db_trans=0.00953,
                               recubrimiento=0.075,
                               D=0.0, N=0, L_max=25.0, L_min=3.0,
                               N_min=1, N_max=80) -> dict:
    """Diseña pilotes a partir de la carga y de los parámetros geotécnicos.

    Datos de entrada (geotecnia del estudio de suelos):
      f_s  = fricción lateral unitaria última (kPa)
      q_p  = resistencia de punta unitaria última (kPa)
      FS   = factor de seguridad geotécnico
    Calcula: diámetro D, número de pilotes N, longitud L y acero longitudinal.
    El pilote se verifica como columna corta a compresión (φP_n,máx).
    """
    Pu_total = Pu if (Pu and Pu > 0) else factor_carga * P_servicio
    espiral = str(tipo_refuerzo).startswith(("espiral", "zuncho"))
    phi = 0.75 if espiral else 0.65
    alpha = 0.85 if espiral else 0.80
    rho = max(float(cuantia), RHO_MIN_INSITU)
    fc_k = fc * 1000.0
    fy_k = fy * 1000.0
    ab = math.pi * db_long ** 2 / 4.0
    N_obj = int(N) if N and N > 0 else 0

    def _phiPn(Dd):
        Ag = math.pi * Dd ** 2 / 4.0
        Ast = rho * Ag
        return phi * alpha * (0.85 * fc_k * (Ag - Ast) + fy_k * Ast), Ag, Ast

    def _L_geotec(Dd, n):
        Qreq = (P_servicio / n) * FS                 # capacidad última requerida por pilote
        Qtip = q_p * (math.pi * Dd ** 2 / 4.0)
        per = math.pi * Dd
        if f_s * per <= 1e-9:
            return L_min if Qtip >= Qreq else None
        return max((Qreq - Qtip) / (f_s * per), L_min)

    candidatos = [float(D)] if (D and D > 0) else DIAMETROS_STD
    elegido = None
    for Dd in candidatos:
        phiPn, Ag, Ast = _phiPn(Dd)
        if phiPn <= 0:
            continue
        if N_obj:
            n = N_obj
            if phiPn < Pu_total / n - 1e-6:
                continue                              # este D no resiste la carga por pilote
            L = _L_geotec(Dd, n)
        else:
            n = max(N_min, math.ceil(Pu_total / phiPn))
            L = _L_geotec(Dd, n)
            while (L is None or L > L_max) and n < N_max:
                n += 1
                L = _L_geotec(Dd, n)
        if L is not None and L <= L_max and phiPn >= Pu_total / n - 1e-6:
            elegido = (Dd, n, L, Ag, Ast, phiPn)
            break

    avisos = []
    if elegido is None:
        Dd = candidatos[-1]
        phiPn, Ag, Ast = _phiPn(Dd)
        n = N_obj if N_obj else max(N_min, math.ceil(Pu_total / phiPn))
        L = _L_geotec(Dd, n) or L_max
        elegido = (Dd, n, min(L, L_max), Ag, Ast, phiPn)
        avisos.append("No se alcanzó la solución dentro de los límites; revisa f_s, q_p, "
                      "L_máx o fija el diámetro/N° de pilotes.")

    Dd, n, L, Ag, Ast, phiPn = elegido
    L = math.ceil(L * 100.0) / 100.0      # redondeo hacia arriba (capacidad del lado seguro)

    # Capacidad geotécnica real con (D, L)
    Qtip = q_p * (math.pi * Dd ** 2 / 4.0)
    Qskin = f_s * (math.pi * Dd * L)
    Qult = Qtip + Qskin
    Qadm = Qult / FS
    Pserv_pile = P_servicio / n
    Pu_pile = Pu_total / n

    # Acero longitudinal
    n_barras = max(4, math.ceil(Ast / ab)) if ab > 0 else 0
    Ast_real = n_barras * ab
    rho_real = Ast_real / Ag if Ag > 0 else 0.0

    # Refuerzo transversal
    if espiral:
        dc = Dd - 2 * recubrimiento
        Ach = math.pi * dc ** 2 / 4.0
        rho_s = 0.45 * (Ag / Ach - 1.0) * (fc_k / fy_k) if Ach > 0 else 0.0
        Asp = math.pi * db_trans ** 2 / 4.0
        paso = min((4.0 * Asp / (dc * rho_s)) if rho_s > 0 else 0.075, 0.075)
        transversal = {"tipo": "espiral", "rho_s": round(rho_s, 4), "paso_m": round(paso, 3)}
    else:
        s_max = min(16 * db_long, 48 * db_trans, Dd)
        transversal = {"tipo": "estribo", "sep_max_m": round(s_max, 3)}

    if rho_real < RHO_MIN_INSITU:
        avisos.append(f"ρ = {rho_real*100:.2f}% < ρ_mín {RHO_MIN_INSITU*100:.1f}% (pilote in situ).")
    if rho_real > RHO_MAX_CODE:
        avisos.append(f"ρ = {rho_real*100:.2f}% > ρ_máx de código {RHO_MAX_CODE*100:.0f}%.")
    elif rho_real > RHO_MAX_PRACT:
        avisos.append(f"ρ = {rho_real*100:.2f}% supera el {RHO_MAX_PRACT*100:.0f}% práctico (congestión).")

    cumple_estr = phiPn >= Pu_pile - 1e-6
    cumple_geo = Qadm >= Pserv_pile - 1e-6
    if not cumple_geo:
        avisos.append("Capacidad geotécnica por pilote insuficiente: aumenta L, D o el N° de pilotes.")
    if not cumple_estr:
        avisos.append("Capacidad estructural por pilote insuficiente: aumenta D o la cuantía.")

    return {
        "diseno": {
            "D_m": round(Dd, 3), "N_pilotes": int(n), "L_m": L,
            "auto_D": not (D and D > 0), "auto_N": not N_obj,
            "volumen_concreto_m3": round(n * math.pi * Dd ** 2 / 4.0 * L, 2),
        },
        "estructural": {
            "A_g_m2": round(Ag, 4), "A_st_cm2": round(Ast_real * 1e4, 2),
            "n_barras": int(n_barras), "db_long_mm": round(db_long * 1000.0, 1),
            "cuantia_pct": round(rho_real * 100, 3), "phi": phi,
            "phiPn_kN": round(phiPn, 1), "Pu_pilote_kN": round(Pu_pile, 1),
            "ratio": round(Pu_pile / phiPn, 3) if phiPn > 0 else None,
            "transversal": transversal, "cumple": cumple_estr,
        },
        "geotecnia": {
            "f_s_kPa": round(f_s, 1), "q_p_kPa": round(q_p, 1), "FS": FS,
            "Qpunta_kN": round(Qtip, 1), "Qfuste_kN": round(Qskin, 1),
            "Qult_kN": round(Qult, 1), "Qadm_kN": round(Qadm, 1),
            "Pserv_pilote_kN": round(Pserv_pile, 1),
            "ratio": round(Pserv_pile / Qadm, 3) if Qadm > 0 else None,
            "cumple": cumple_geo,
        },
        "cargas": {"P_servicio_kN": round(P_servicio, 1), "Pu_kN": round(Pu_total, 1),
                   "factor_carga": factor_carga},
        "cumple": cumple_estr and cumple_geo,
        "avisos": avisos,
    }
