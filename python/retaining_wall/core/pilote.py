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
                               N_min=1, N_max=80,
                               norma="NSR10", tipo_suelo="arena",
                               M_servicio=0.0, Mu=0.0,
                               T_servicio=0.0, Tu=0.0,
                               Lu_libre=0.0, k_pandeo=1.0,
                               disipacion="DMO",
                               Mx_servicio=0.0, My_servicio=0.0, H_servicio=0.0,
                               s_grupo=0.0, tipo_reaccion="nh",
                               nh_suelo=0.0, k_suelo=0.0,
                               cabeza_pilote="libre",
                               gamma_lat=0.0, cu_lat=0.0, eps50=0.01, phi_lat=0.0,
                               fs_negativa=0.0, L_downdrag=0.0) -> dict:
    """Diseña pilotes a partir de la carga y de los parámetros geotécnicos.

    Datos de entrada (geotecnia del estudio de suelos):
      f_s  = fricción lateral unitaria última (kPa)
      q_p  = resistencia de punta unitaria última (kPa)
      FS   = factor de seguridad geotécnico (solo NSR-10)

    ``norma`` selecciona el tratamiento de seguridad geotécnico:
      - NSR-10 (esfuerzos admisibles): Q_adm = Q_últ/FS ≥ P_servicio.
      - CCP-14 (LRFD, Sección 10.7/10.8): R_r = φ_s·Q_fuste + φ_p·Q_punta ≥ P_u,
        con φ según el material (``tipo_suelo`` arena/arcilla, Tabla 10.5.5.2.4-1).
    El pilote se verifica como columna corta a compresión (φP_n,máx).
    """
    from ..normas import NORMA_CCP14, normalizar_norma
    norma = normalizar_norma(norma)
    ccp = (norma == NORMA_CCP14)
    _ts = "arcilla" if str(tipo_suelo).lower().startswith(("arc", "clay", "cohes")) else "arena"
    phi_s_geo = 0.55 if _ts == "arena" else 0.45      # φ fricción (drilled shaft)
    phi_p_geo = 0.50 if _ts == "arena" else 0.40      # φ punta

    Pu_total = Pu if (Pu and Pu > 0) else factor_carga * P_servicio
    espiral = str(tipo_refuerzo).startswith(("espiral", "zuncho"))
    phi = 0.75 if (espiral or ccp) else 0.65          # CCP-14 axial φ=0.75
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
        A_tip = math.pi * Dd ** 2 / 4.0
        per = math.pi * Dd
        if ccp:
            # LRFD: R_r = φ_p·q_p·A + φ_s·f_s·per·L ≥ P_u/n
            dem = Pu_total / n
            cap_tip = phi_p_geo * q_p * A_tip
            cap_skin_unit = phi_s_geo * f_s * per
        else:
            # ASD: Q_últ = q_p·A + f_s·per·L ≥ (P_serv/n)·FS
            dem = (P_servicio / n) * FS
            cap_tip = q_p * A_tip
            cap_skin_unit = f_s * per
        if cap_skin_unit <= 1e-9:
            return L_min if cap_tip >= dem else None
        return max((dem - cap_tip) / cap_skin_unit, L_min)

    # Momentos y cargas por pilote (para flexo-compresión / esbeltez).
    from .pilote_flexocompresion import (
        amplificacion_momento, capacidad_traccion, carga_lateral,
        confinamiento_sismico, cortante_circular, diagrama_interaccion,
        distribucion_grupo, layout_grupo, verificar_flexocompresion)
    # Momento y tracción DIRECTOS por pilote (aplicados en la cabeza).
    Mu_pila_dir = Mu if (Mu and Mu > 0) else factor_carga * abs(M_servicio)
    Tu_pila_dir = Tu if (Tu and Tu > 0) else factor_carga * abs(T_servicio)
    # Cargas mayoradas del grupo (columna sobre el cabezal).
    Mux_u = factor_carga * abs(Mx_servicio)
    Muy_u = factor_carga * abs(My_servicio)
    Hu_total = factor_carga * abs(H_servicio)

    _tipo_py = "arcilla" if (tipo_reaccion == "k" or cu_lat > 0) else "arena"
    _hay_datos_py = (gamma_lat > 0 and ((_tipo_py == "arcilla" and cu_lat > 0)
                     or (_tipo_py == "arena" and (nh_suelo > 0 or phi_lat > 0))))
    Qn_downdrag = 0.0

    def _cargas_diseno(Dd_, n_):
        """Combina la carga axial uniforme, la distribución biaxial del grupo, la
        carga lateral (p-y no lineal, o Broms) y el downdrag en (Pu, Mu, Tu, V)."""
        s_ = s_grupo if (s_grupo and s_grupo > 0) else 3.0 * Dd_
        coords = layout_grupo(n_, s_)
        dist = distribucion_grupo(P=Pu_total, Mx=Mux_u, My=Muy_u, coords=coords)
        Pu_ax = Pu_total / n_
        Pu_des = max(Pu_ax, dist["P_max_kN"])
        # Downdrag: se suma a la carga axial.
        Qn = 0.0
        if fs_negativa > 1e-9 and L_downdrag > 1e-9:
            Qn = fs_negativa * math.pi * Dd_ * L_downdrag
            Pu_des += factor_carga * Qn
        Hu_p = Hu_total / n_
        lat = carga_lateral(H=Hu_p, D=Dd_, fc=fc, recubrimiento=recubrimiento,
                            tipo=tipo_reaccion, nh=nh_suelo, k=k_suelo,
                            cabeza=cabeza_pilote)
        Mu_lat = lat["Mmax_kNm"]
        # Momento del análisis p-y no lineal (si hay datos de suelo).
        if Hu_p > 1e-9 and _hay_datos_py:
            try:
                from .pilote_py import analisis_py as _apy
                Ec_ = 4700.0 * math.sqrt(fc) * 1000.0
                EI_ = 0.5 * Ec_ * math.pi * Dd_ ** 4 / 64.0
                pyr = _apy(EI=EI_, L=min(L_max, 20.0), D=Dd_, H=Hu_p,
                           M0=Mu_pila_dir, cabeza=cabeza_pilote, tipo=_tipo_py,
                           gamma=gamma_lat, cu=cu_lat if cu_lat > 0 else 50.0,
                           eps50=eps50, phi=phi_lat if phi_lat > 0 else 32.0,
                           nh=nh_suelo if nh_suelo > 0 else 5000.0, n_nodos=40)
                if pyr.get("aplica"):
                    Mu_lat = max(Mu_lat, pyr["Mmax_kNm"])
            except Exception:
                pass
        Mu_des = max(Mu_pila_dir, Mu_lat)
        Tu_des = max(Tu_pila_dir, max(0.0, -dist["P_min_kN"]))
        return {"Pu": Pu_des, "Mu": Mu_des, "Tu": Tu_des, "V": Hu_p,
                "dist": dist, "lat": lat, "s": s_}

    def _flexo_ok(Dd_, n_, Ag_):
        """¿El punto (Pu, Mc) cae dentro del diagrama P-M para este D?"""
        if ab <= 0:
            return True
        cd = _cargas_diseno(Dd_, n_)
        if cd["Mu"] <= 1e-9:
            return True
        nb = max(4, math.ceil((rho * Ag_) / ab))
        diag = diagrama_interaccion(
            D=Dd_, fc=fc, fy=fy, n_barras=nb, db_long=db_long * 1000.0,
            recubrimiento=recubrimiento, db_trans=db_trans * 1000.0, espiral=espiral)
        esb = amplificacion_momento(Pu=cd["Pu"], M2=cd["Mu"], D=Dd_, fc=fc,
                                    Lu=Lu_libre, k=k_pandeo, fy=fy)
        return verificar_flexocompresion(diag, cd["Pu"], esb["Mc_kNm"])["cumple"]

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
        # Acepta el D si cumple axial, geotecnia y flexo-compresión (si hay momento).
        if (L is not None and L <= L_max and phiPn >= Pu_total / n - 1e-6
                and _flexo_ok(Dd, n, Ag)):
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
    Pserv_pile = P_servicio / n
    Pu_pile = Pu_total / n
    if ccp:
        R_r = phi_p_geo * Qtip + phi_s_geo * Qskin      # resistencia factorada / pilote
        cumple_geo = R_r >= Pu_pile - 1e-6
    else:
        Qadm = Qult / FS
        cumple_geo = Qadm >= Pserv_pile - 1e-6

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
    if not cumple_geo:
        avisos.append("Capacidad geotécnica por pilote insuficiente: aumenta L, D o el N° de pilotes.")
    if not cumple_estr:
        avisos.append("Capacidad estructural por pilote insuficiente: aumenta D o la cuantía.")

    # ── Grupo + carga lateral + flexo-compresión + esbeltez + tracción + cortante ──
    cd = _cargas_diseno(Dd, n)
    Pu_des, Mu_des, Tu_des, V_pila = cd["Pu"], cd["Mu"], cd["Tu"], cd["V"]
    grupo = cd["dist"]
    lateral = cd["lat"]

    # Rigidez a flexión (para p-y, Davisson).
    Ec_kPa = 4700.0 * math.sqrt(fc) * 1000.0
    Ig = math.pi * Dd ** 4 / 64.0
    EI = 0.5 * Ec_kPa * Ig

    # Análisis lateral no lineal por curvas p-y (si hay H y datos de suelo).
    from .pilote_py import analisis_py
    from .pilote_flexocompresion import friccion_negativa, pandeo_davisson
    py = {"aplica": False}
    _tipo_py = "arcilla" if (tipo_reaccion == "k" or cu_lat > 0) else "arena"
    _hay_datos_py = (gamma_lat > 0 and ((_tipo_py == "arcilla" and cu_lat > 0)
                     or (_tipo_py == "arena" and (nh_suelo > 0 or phi_lat > 0))))
    if Hu_total > 1e-9 and _hay_datos_py:
        try:
            py = analisis_py(
                EI=EI, L=L, D=Dd, H=Hu_total / n, M0=Mu_pila_dir,
                cabeza=cabeza_pilote, tipo=_tipo_py, gamma=gamma_lat,
                cu=cu_lat if cu_lat > 0 else 50.0, eps50=eps50,
                phi=phi_lat if phi_lat > 0 else 32.0,
                nh=nh_suelo if nh_suelo > 0 else 5000.0)
            if py.get("aplica"):
                # el momento del análisis no lineal reemplaza el estimado de Broms
                Mu_des = max(Mu_pila_dir, py["Mmax_kNm"])
        except Exception:
            py = {"aplica": False}

    # Fricción negativa (downdrag): ya está incluida en Pu_des por _cargas_diseno.
    downdrag = friccion_negativa(D=Dd, fs_neg=fs_negativa, L_downdrag=L_downdrag,
                                 P_servicio=Pu_pile)

    # Pandeo del pilote parcialmente embebido (Davisson).
    davisson = pandeo_davisson(
        Pu=Pu_des, EI=EI, Lu=Lu_libre, tipo=tipo_reaccion,
        nh=nh_suelo, k=k_suelo, beta=max(1.0, k_pandeo))

    diagrama = diagrama_interaccion(
        D=Dd, fc=fc, fy=fy, n_barras=n_barras,
        db_long=db_long * 1000.0, recubrimiento=recubrimiento,
        db_trans=db_trans * 1000.0, espiral=espiral)

    # Esbeltez: amplifica el momento de diseño antes de verificar el diagrama.
    esbeltez = amplificacion_momento(
        Pu=Pu_des, M2=Mu_des, D=Dd, fc=fc, Lu=Lu_libre, k=k_pandeo, fy=fy)
    Mc_pila = esbeltez["Mc_kNm"]
    flexocomp = verificar_flexocompresion(diagrama, Pu_des, Mc_pila)
    traccion = capacidad_traccion(Ast=Ast_real, fy=fy, Tu=Tu_des)
    # Cortante del pilote (usa el paso del refuerzo transversal como cortante).
    s_trans = (transversal.get("paso_m", 0.0) if espiral
               else transversal.get("sep_max_m", 0.0))
    cortante = cortante_circular(
        Vu=V_pila, D=Dd, fc=fc, fy=fy, db_trans=db_trans * 1000.0,
        recubrimiento=recubrimiento, espiral=espiral, s_trans=s_trans)
    confinamiento = confinamiento_sismico(
        D=Dd, fc=fc, fy=fy, db_long=db_long * 1000.0,
        recubrimiento=recubrimiento, db_trans=db_trans * 1000.0,
        espiral=espiral, Lu=Lu_libre, disipacion=disipacion)

    if Mu_des > 0 and not flexocomp["cumple"]:
        avisos.append("El punto (Pu, Mu) cae fuera del diagrama de interacción "
                      "P-M: aumenta D, la cuantía o reduce el momento.")
    if esbeltez.get("inestable"):
        avisos.append("Pilote inestable por esbeltez (Pu > 0.75·Pc): reduce la "
                      "longitud libre Lu, aumenta D o arriostra el pilote.")
    elif esbeltez["es_esbelto"]:
        avisos.append(f"Pilote esbelto (kLu/r = {esbeltez['esbeltez_klu_r']} > "
                      f"{esbeltez['limite']:.0f}): momento amplificado por δ_ns = "
                      f"{esbeltez['delta_ns']}.")
    if grupo.get("hay_traccion"):
        avisos.append(f"El momento del grupo genera TRACCIÓN en pilotes de borde "
                      f"(P_mín = {grupo['P_min_kN']:.0f} kN): verifica el arranque "
                      "y la conexión al cabezal.")
    if traccion["aplica"] and not traccion["cumple"]:
        avisos.append("La capacidad estructural a tracción (arranque) es "
                      "insuficiente: aumenta el acero longitudinal.")
    if not cortante["cumple"]:
        avisos.append("El cortante del pilote excede φVn: aumenta D o cierra el "
                      "paso del refuerzo transversal.")
    if davisson.get("aplica") and not davisson["cumple"]:
        avisos.append(f"Pandeo (Davisson): Pu = {Pu_des:.0f} kN > Padm = "
                      f"{davisson['Padm_kN']:.0f} kN (Pcr = {davisson['Pcr_kN']:.0f} "
                      "kN): aumenta D o reduce la longitud libre.")
    if downdrag.get("aplica"):
        avisos.append(f"Fricción negativa (downdrag): Qn = {downdrag['Qn_kN']:.0f} "
                      "kN se suma a la carga axial del pilote (plano neutro a "
                      f"{downdrag['plano_neutro_m']:.1f} m).")
    if py.get("aplica"):
        avisos.append(f"Análisis p-y no lineal: Mmax = {py['Mmax_kNm']:.0f} kN·m a "
                      f"{py['z_Mmax_m']:.1f} m; refuerzo longitudinal recomendado "
                      f"hasta ≈ {py['z_refuerzo_m']:.1f} m de profundidad.")
    cumple_flexocomp = flexocomp["cumple"] if Mu_des > 0 else True
    cumple_traccion = traccion["cumple"] if traccion["aplica"] else True
    cumple_cortante = cortante["cumple"]
    cumple_pandeo = davisson["cumple"] if davisson.get("aplica") else True

    geotecnia = {
        "norma": norma, "tipo_suelo": _ts,
        "f_s_kPa": round(f_s, 1), "q_p_kPa": round(q_p, 1),
        "Qpunta_kN": round(Qtip, 1), "Qfuste_kN": round(Qskin, 1),
        "Qult_kN": round(Qult, 1),
        "Pserv_pilote_kN": round(Pserv_pile, 1), "Pu_pilote_kN": round(Pu_pile, 1),
        "cumple": cumple_geo,
    }
    if ccp:
        geotecnia.update({
            "metodo": "CCP-14 / AASHTO LRFD",
            "phi_fuste": phi_s_geo, "phi_punta": phi_p_geo,
            "R_r_kN": round(R_r, 1),
            "ratio": round(Pu_pile / R_r, 3) if R_r > 0 else None,
            "CDR": round(R_r / Pu_pile, 3) if Pu_pile > 0 else None,
        })
    else:
        geotecnia.update({
            "metodo": "NSR-10 (esfuerzos admisibles)", "FS": FS,
            "Qadm_kN": round(Qadm, 1),
            "ratio": round(Pserv_pile / Qadm, 3) if Qadm > 0 else None,
        })

    return {
        "norma": norma,
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
            "grupo": grupo,
            "carga_lateral": lateral,
            "analisis_py": py,
            "pandeo_davisson": davisson,
            "downdrag": downdrag,
            "flexocompresion": flexocomp,
            "diagrama_interaccion": diagrama,
            "esbeltez": esbeltez,
            "traccion": traccion,
            "cortante": cortante,
            "confinamiento_sismico": confinamiento,
            "cumple_flexocompresion": cumple_flexocomp,
            "cumple_traccion": cumple_traccion,
            "cumple_cortante": cumple_cortante,
            "cumple_pandeo": cumple_pandeo,
        },
        "geotecnia": geotecnia,
        "cargas": {"P_servicio_kN": round(P_servicio, 1), "Pu_kN": round(Pu_total, 1),
                   "factor_carga": factor_carga,
                   "Mu_pilote_kNm": round(Mu_des, 1),
                   "Tu_pilote_kN": round(Tu_des, 1),
                   "V_pilote_kN": round(V_pila, 1),
                   "Lu_libre_m": round(Lu_libre, 2),
                   "Mx_grupo_kNm": round(Mux_u, 1), "My_grupo_kNm": round(Muy_u, 1),
                   "H_grupo_kN": round(Hu_total, 1)},
        "cumple": (cumple_estr and cumple_geo and cumple_flexocomp
                   and cumple_traccion and cumple_cortante and cumple_pandeo),
        "avisos": avisos,
    }
