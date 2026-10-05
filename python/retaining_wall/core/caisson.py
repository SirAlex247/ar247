"""Diseño de caissons / pilas excavadas de gran diámetro (*drilled shafts*).

Capacidad axial por los métodos de pilas perforadas de O'Neill & Reese (FHWA),
que son los que adopta la CCP-14 / AASHTO LRFD (Sección 10.8):

    Arenas   → fricción β:   f_s = β·σ'_v,  β = 1.5 − 0.245·√z  (0.25 ≤ β ≤ 1.2)
               punta:        q_p = σ'_v·N_q (Meyerhof), con tope por asentamiento.
    Arcillas → fricción α:   f_s = α·c_u,   α ≈ 0.55 (0.45 para c_u altos)
               punta:        q_p = N_c·c_u,  N_c = 9.

Se excluye de la fricción el metro y medio superior y la zona inferior (1 diámetro,
más la campana si existe), según O'Neill & Reese. La punta puede acampanarse
(campana de diámetro D_b > D del fuste) para aumentar el apoyo.

Diseño por la norma seleccionada:
    - NSR-10  (esfuerzos de trabajo): Q_adm = Q_últ / FS ≥ P_servicio.
    - CCP-14  (LRFD, Tabla 10.5.5.2.4-1): R_r = φ_qs·Q_s + φ_qp·Q_p ≥ P_u.
Estructural: la pila se verifica como columna a compresión (φP_n), con φ y α de
la norma correspondiente.

Unidades SI internas: m, kN, kPa, MPa, kN/m³.
"""
from __future__ import annotations

import math

from ..normas import NORMA_CCP14, NORMA_NSR10, normalizar_norma
from .pilote import nq_arena

PA = 101.325  # presión atmosférica (kPa), para normalizar c_u

# Factores de resistencia de pilas perforadas — CCP-14 / AASHTO Tabla 10.5.5.2.4-1
PHI_CCP14 = {
    "arena": {"fuste": 0.55, "punta": 0.50},    # β-method / O'Neill & Reese
    "arcilla": {"fuste": 0.45, "punta": 0.40},  # α-method / total stress
}
# Factores de seguridad NSR-10 (Título H) — esfuerzos admisibles
FS_NSR10_DEFECTO = 3.0

# Estructural
RHO_MIN = 0.005      # cuantía mínima pila vaciada in situ (AASHTO 5.10.8 / NSR-10)
RHO_MAX_CODE = 0.08
RHO_MAX_PRACT = 0.04


# ---------------------------------------------------------------------------
# Perfil de suelo (esfuerzo vertical efectivo)
# ---------------------------------------------------------------------------
def _normaliza_estratos(estratos):
    out = []
    for e in estratos:
        tipo = str(e.get("tipo", "arena")).lower()
        tipo = "arcilla" if tipo.startswith(("arc", "clay", "cohes")) else "arena"
        # ``gamma`` es el peso unitario total in-situ del estrato. Si no se da
        # ``gamma_sat`` aparte (la app captura un solo γ por estrato), se asume
        # γ_sat = γ; para estratos bajo el nivel freático conviene ingresar el
        # peso unitario saturado, ya que abajo del N.F. se usa (γ_sat − γ_w).
        out.append({
            "tipo": tipo,
            "espesor": float(e.get("espesor", 0.0) or 0.0),
            "phi": float(e.get("phi", 30.0) or 30.0),
            "cu": float(e.get("cu", 50.0) or 50.0),
            "gamma": float(e.get("gamma", 18.0) or 18.0),
            "gamma_sat": float(e.get("gamma_sat", e.get("gamma", 18.0)) or 18.0),
            "nombre": e.get("nombre", ""),
        })
    return out


def _perfil_sigma(estratos, nivel_freatico, z_max, gamma_w=9.81, paso=0.25):
    """Precalcula σ'_v(z) UNA sola vez (O(n)) y devuelve un lookup O(1) por
    interpolación lineal. Evita reintegrar el perfil en cada incremento de la
    integración del fuste (antes O(n²))."""
    n = int(math.ceil(max(z_max, paso) / paso)) + 1
    sig = [0.0] * (n + 1)
    acc = 0.0
    for i in range(n):
        zc = (i + 0.5) * paso
        e = _estrato_en(estratos, zc)
        gam = e["gamma"] if zc <= nivel_freatico else e["gamma_sat"] - gamma_w
        acc += gam * paso
        sig[i + 1] = acc

    def sv(z):
        if z <= 0:
            return 0.0
        k = z / paso
        i = int(k)
        if i + 1 >= len(sig):
            return sig[-1]
        return sig[i] + (k - i) * (sig[i + 1] - sig[i])
    return sv


def _estrato_en(estratos, z):
    prof = 0.0
    for e in estratos:
        prof += e["espesor"]
        if z <= prof + 1e-9:
            return e
    return estratos[-1]


# ---------------------------------------------------------------------------
# Métodos de pila perforada (O'Neill & Reese / FHWA)
# ---------------------------------------------------------------------------
def alpha_pila(cu):
    """Adherencia α para pilas perforadas en arcilla (O'Neill & Reese)."""
    r = cu / PA
    if r <= 1.5:
        return 0.55
    return max(0.45, 0.55 - 0.1 * (r - 1.5))


def beta_pila(z):
    """Coeficiente β para pilas perforadas en arena (O'Neill & Reese, FHWA).

    β = 1.5 − 0.245·√z (z en m), acotado a [0.25, 1.2]."""
    return min(1.2, max(0.25, 1.5 - 0.245 * math.sqrt(max(0.0, z))))


# ---------------------------------------------------------------------------
# Capacidad axial
# ---------------------------------------------------------------------------
def capacidad_axial_caisson(*, D, L, estratos, nivel_freatico=100.0,
                            D_campana=0.0, altura_campana=0.0,
                            q_punta_limite=2900.0):
    """Capacidad última de la pila: fricción de fuste (β/α) + punta (con campana).

    Devuelve Q_fuste, Q_punta, Q_ult (kN) y el detalle por estrato.
    """
    estratos = _normaliza_estratos(estratos)
    perim = math.pi * D
    acampanada = D_campana and D_campana > D
    D_base = D_campana if acampanada else D
    A_base = math.pi * D_base ** 2 / 4.0
    _sv = _perfil_sigma(estratos, nivel_freatico, L + 1.0)   # σ'_v(z) precalculado

    # Zonas excluidas de la fricción (O'Neill & Reese)
    z_top = 1.5
    z_bot_excl = (altura_campana + D) if acampanada else D
    z_fondo = L - z_bot_excl

    DZ = 0.25
    Qs = 0.0
    detalle = []
    prof = 0.0
    for e in estratos:
        top, bot = prof, prof + e["espesor"]
        prof = bot
        a = max(top, z_top)
        b = min(bot, L, z_fondo)
        if b <= a:
            continue
        n_inc = max(1, int(math.ceil((b - a) / DZ)))
        paso = (b - a) / n_inc
        Qs_e = 0.0
        for i in range(n_inc):
            z = a + (i + 0.5) * paso
            sv = _sv(z)
            if e["tipo"] == "arena":
                f = beta_pila(z) * sv
            else:
                f = alpha_pila(e["cu"]) * e["cu"]
            Qs_e += f * perim * paso
        Qs += Qs_e
        detalle.append({
            "estrato": e["nombre"] or e["tipo"], "tipo": e["tipo"],
            "desde": round(a, 2), "hasta": round(b, 2),
            "f_prom_kPa": round(Qs_e / (perim * (b - a)), 2) if (b - a) > 0 else 0.0,
            "Qs_kN": round(Qs_e, 1),
        })

    # Punta
    ep = _estrato_en(estratos, L)
    if ep["tipo"] == "arena":
        sv_p = _sv(L)
        Nq = nq_arena(ep["phi"])
        qp = min(sv_p * Nq, q_punta_limite)
        punta = {"tipo": "arena", "sigma_v_kPa": round(sv_p, 1), "Nq": round(Nq, 2),
                 "qp_kPa": round(qp, 1), "limite_kPa": q_punta_limite}
    else:
        qp = 9.0 * ep["cu"]
        punta = {"tipo": "arcilla", "Nc": 9.0, "cu_kPa": round(ep["cu"], 1),
                 "qp_kPa": round(qp, 1)}
    Qp = qp * A_base

    return {
        "Q_fuste_kN": round(Qs, 1), "Q_punta_kN": round(Qp, 1),
        "Q_ult_kN": round(Qs + Qp, 1),
        "D_base_m": round(D_base, 3), "A_base_m2": round(A_base, 4),
        "acampanada": bool(acampanada),
        "punta": punta, "fuste_detalle": detalle,
        "tipo_punta": ep["tipo"],
        "tipo_fuste_predominante": _predominante(detalle),
    }


def _predominante(detalle):
    if not detalle:
        return "arena"
    ar = sum(d["Qs_kN"] for d in detalle if d["tipo"] == "arena")
    ac = sum(d["Qs_kN"] for d in detalle if d["tipo"] == "arcilla")
    return "arcilla" if ac > ar else "arena"


# ---------------------------------------------------------------------------
# Diseño estructural (columna a compresión)
# ---------------------------------------------------------------------------
def _estructural(*, D, fc, fy, cuantia, tipo_refuerzo, db_long, db_trans,
                 recubrimiento, Pu, norma):
    Ag = math.pi * D ** 2 / 4.0
    rho = max(float(cuantia), RHO_MIN)
    Ast = rho * Ag
    fc_k, fy_k = fc * 1000.0, fy * 1000.0
    espiral = str(tipo_refuerzo).startswith(("espiral", "zuncho"))
    # α del término de compresión (igual en NSR-10 y AASHTO)
    alpha = 0.85 if espiral else 0.80
    # φ axial: NSR-10 C.10 (0.75/0.65) · CCP-14/AASHTO 5.5.4.2 (0.75)
    if norma == NORMA_CCP14:
        phi = 0.75
    else:
        phi = 0.75 if espiral else 0.65
    Pn_max = 0.85 * fc_k * (Ag - Ast) + fy_k * Ast
    phiPn = phi * alpha * Pn_max

    ab = math.pi * db_long ** 2 / 4.0
    n_barras = max(6 if espiral else 4, math.ceil(Ast / ab)) if ab > 0 else 0
    Ast_real = n_barras * ab
    rho_real = Ast_real / Ag if Ag > 0 else 0.0

    if espiral:
        dc = D - 2 * recubrimiento
        Ach = math.pi * dc ** 2 / 4.0
        rho_s = 0.45 * (Ag / Ach - 1.0) * (fc_k / fy_k) if Ach > 0 else 0.0
        Asp = math.pi * db_trans ** 2 / 4.0
        paso = min((4.0 * Asp / (dc * rho_s)) if rho_s > 0 else 0.075, 0.075)
        transversal = {"tipo": "espiral", "rho_s": round(rho_s, 4), "paso_m": round(paso, 3)}
    else:
        s_max = min(16 * db_long, 48 * db_trans, D)
        transversal = {"tipo": "estribo", "sep_max_m": round(s_max, 3)}

    avisos = []
    if rho_real < RHO_MIN:
        avisos.append(f"ρ = {rho_real*100:.2f}% < ρ_mín {RHO_MIN*100:.1f}% (pila in situ).")
    if rho_real > RHO_MAX_CODE:
        avisos.append(f"ρ = {rho_real*100:.2f}% > ρ_máx de código {RHO_MAX_CODE*100:.0f}%.")
    elif rho_real > RHO_MAX_PRACT:
        avisos.append(f"ρ = {rho_real*100:.2f}% supera el {RHO_MAX_PRACT*100:.0f}% práctico (congestión).")

    cumple = phiPn >= Pu - 1e-6
    return {
        "A_g_m2": round(Ag, 4), "A_st_cm2": round(Ast_real * 1e4, 2),
        "n_barras": int(n_barras), "db_long_mm": round(db_long * 1000.0, 1),
        "cuantia_pct": round(rho_real * 100, 3), "phi": phi, "alpha": alpha,
        "phiPn_kN": round(phiPn, 1), "Pu_kN": round(Pu, 1),
        "ratio": round(Pu / phiPn, 3) if phiPn > 0 else None,
        "transversal": transversal, "cumple": cumple, "avisos": avisos,
    }, cumple, avisos


# ---------------------------------------------------------------------------
# Diseño estructural avanzado: flexocompresión, lateral p-y, esbeltez, cortante
# ---------------------------------------------------------------------------
def _flexo_lateral(*, D, fc, fy, est, espiral, db_long, db_trans, recubrimiento,
                   Pu, Mu, Hu, Lu_libre, k_pandeo, disipacion, estratos, L,
                   cabeza, gamma_lat, cu_lat, phi_lat, nh_suelo, k_suelo,
                   tipo_reaccion, eps50):
    """Verificación del fuste del caisson como columna de hormigón: diagrama de
    interacción P-M, análisis lateral no lineal p-y, amplificación de momento por
    esbeltez (tramo libre por socavación/agua), cortante en sección circular,
    confinamiento sísmico y pandeo de Davisson. Reutiliza los módulos de pilotes.

    El suelo lateral para el p-y lo gobierna, por defecto, el estrato más
    superficial (los primeros diámetros); se puede sobrescribir con ``*_lat``.
    """
    from .pilote_flexocompresion import (
        amplificacion_momento, confinamiento_sismico, cortante_circular,
        diagrama_interaccion, pandeo_davisson, verificar_flexocompresion)

    n_barras = int(est["n_barras"])
    Ec = 4700.0 * math.sqrt(fc) * 1000.0            # kPa
    Ig = math.pi * D ** 4 / 64.0
    EI = 0.5 * Ec * Ig                              # rigidez fisurada (p-y/Davisson)

    # Suelo lateral: por defecto lo gobierna el estrato superficial.
    top = estratos[0] if estratos else {"tipo": "arena", "gamma": 18.0,
                                         "cu": 50.0, "phi": 30.0}
    tipo_py = "arcilla" if (tipo_reaccion == "k" or cu_lat > 0
                            or top["tipo"] == "arcilla") else "arena"
    g_lat = gamma_lat if gamma_lat > 0 else max(top["gamma"] - 9.81, 3.0)
    cu_ = cu_lat if cu_lat > 0 else top["cu"]
    phi_ = phi_lat if phi_lat > 0 else top["phi"]

    # Análisis lateral no lineal p-y (si hay carga/momento horizontal factorado).
    py = {"aplica": False}
    Mu_base, Vu_base = abs(Mu), abs(Hu)
    if Hu > 1e-9 or abs(Mu) > 1e-9:
        try:
            from .pilote_py import analisis_py
            py = analisis_py(EI=EI, L=min(L, 25.0), D=D, H=max(Hu, 0.0),
                             M0=Mu, cabeza=cabeza, tipo=tipo_py, gamma=g_lat,
                             cu=cu_ if cu_ > 0 else 50.0, eps50=eps50,
                             phi=phi_ if phi_ > 0 else 32.0,
                             nh=nh_suelo if nh_suelo > 0 else 5000.0)
            if py.get("aplica"):
                Mu_base = max(Mu_base, py["Mmax_kNm"])
                Vu_base = max(Vu_base, py["Vmax_kN"])
        except Exception:
            py = {"aplica": False}

    # Diagrama de interacción P-M de la sección circular.
    diag = diagrama_interaccion(D=D, fc=fc, fy=fy, n_barras=n_barras,
                                db_long=db_long * 1000.0, recubrimiento=recubrimiento,
                                db_trans=db_trans * 1000.0, espiral=espiral)
    # Esbeltez: amplifica el momento antes de verificar el diagrama.
    esbeltez = amplificacion_momento(Pu=Pu, M2=Mu_base, D=D, fc=fc,
                                     Lu=Lu_libre, k=k_pandeo, fy=fy)
    Mc = esbeltez["Mc_kNm"]
    flexocomp = verificar_flexocompresion(diag, Pu, Mc)

    tr = est.get("transversal", {})
    s_trans = (tr.get("paso_m") or tr.get("sep_max_m") or 0.0)
    cortante = cortante_circular(Vu=Vu_base, D=D, fc=fc, fy=fy,
                                 db_trans=db_trans * 1000.0,
                                 recubrimiento=recubrimiento, espiral=espiral,
                                 s_trans=s_trans)
    confinamiento = confinamiento_sismico(D=D, fc=fc, fy=fy,
                                          db_long=db_long * 1000.0,
                                          recubrimiento=recubrimiento,
                                          db_trans=db_trans * 1000.0,
                                          espiral=espiral, Lu=Lu_libre,
                                          disipacion=disipacion)
    davisson = pandeo_davisson(Pu=Pu, EI=EI, Lu=Lu_libre, tipo=tipo_reaccion,
                               nh=nh_suelo, k=k_suelo, beta=max(1.0, k_pandeo))

    return {
        "Mu_diseno_kNm": round(Mu_base, 1), "Vu_diseno_kN": round(Vu_base, 1),
        "EI_kNm2": round(EI, 1),
        "diagrama_interaccion": diag, "flexocompresion": flexocomp,
        "esbeltez": esbeltez, "cortante": cortante,
        "confinamiento": confinamiento, "analisis_py": py, "davisson": davisson,
    }


# ---------------------------------------------------------------------------
# Diseño principal (norma elegible)
# ---------------------------------------------------------------------------
def disenar_caisson(*, D, L, estratos, P_servicio, norma="NSR10",
                    nivel_freatico=100.0, D_campana=0.0, altura_campana=0.0,
                    FS=0.0, Pu=0.0, factor_carga=1.6,
                    fc=21.0, fy=420.0, cuantia=0.01, tipo_refuerzo="espiral",
                    db_long=0.0254, db_trans=0.00953, recubrimiento=0.075,
                    L_auto=False, L_max=40.0,
                    Mu=0.0, Hu=0.0, Lu_libre=0.0, k_pandeo=2.0,
                    disipacion="DMO", cabeza="libre",
                    gamma_lat=0.0, cu_lat=0.0, phi_lat=0.0,
                    nh_suelo=0.0, k_suelo=0.0, tipo_reaccion="nh",
                    eps50=0.01) -> dict:
    """Diseña (o verifica) un caisson por la norma elegida (NSR-10 o CCP-14)."""
    norma = normalizar_norma(norma)
    avisos = []
    estratos_n = _normaliza_estratos(estratos)

    # Empotramiento automático: crecer L hasta cubrir la carga
    if L_auto or not L or L <= 0:
        L = max(3.0, float(L) if L else 3.0)
        for _ in range(400):
            cap = capacidad_axial_caisson(
                D=D, L=L, estratos=estratos_n, nivel_freatico=nivel_freatico,
                D_campana=D_campana, altura_campana=altura_campana)
            if _cumple_geo(cap, norma, P_servicio, FS, factor_carga, Pu)[0] or L >= L_max:
                break
            L += 0.5
        L = round(L, 2)

    cap = capacidad_axial_caisson(
        D=D, L=L, estratos=estratos_n, nivel_freatico=nivel_freatico,
        D_campana=D_campana, altura_campana=altura_campana)

    cumple_geo, geo = _cumple_geo(cap, norma, P_servicio, FS, factor_carga, Pu)
    if not cumple_geo:
        avisos.append("La capacidad geotécnica es insuficiente: aumenta L, D, "
                      "usa campana o revisa el perfil de suelo.")

    # Carga última para el estructural
    Pu_est = Pu if (Pu and Pu > 0) else (
        factor_carga * P_servicio if norma == NORMA_CCP14 else 1.5 * P_servicio)
    est, cumple_est, av_est = _estructural(
        D=D, fc=fc, fy=fy, cuantia=cuantia, tipo_refuerzo=tipo_refuerzo,
        db_long=db_long, db_trans=db_trans, recubrimiento=recubrimiento,
        Pu=Pu_est, norma=norma)
    avisos += av_est
    if not cumple_est:
        avisos.append("La capacidad estructural (columna) es insuficiente: aumenta D o la cuantía.")

    # Flexocompresión (P-M), lateral p-y, esbeltez, cortante circular, confinamiento.
    espiral = str(tipo_refuerzo).startswith(("espiral", "zuncho"))
    flexo = _flexo_lateral(
        D=D, fc=fc, fy=fy, est=est, espiral=espiral, db_long=db_long,
        db_trans=db_trans, recubrimiento=recubrimiento, Pu=Pu_est, Mu=Mu, Hu=Hu,
        Lu_libre=Lu_libre, k_pandeo=k_pandeo, disipacion=disipacion,
        estratos=estratos_n, L=L, cabeza=cabeza, gamma_lat=gamma_lat,
        cu_lat=cu_lat, phi_lat=phi_lat, nh_suelo=nh_suelo, k_suelo=k_suelo,
        tipo_reaccion=tipo_reaccion, eps50=eps50)
    est.update(flexo)
    cumple_flexo = (flexo["flexocompresion"]["cumple"] and flexo["cortante"]["cumple"]
                    and flexo["davisson"]["cumple"])
    if flexo["Mu_diseno_kNm"] > 0 and not flexo["flexocompresion"]["cumple"]:
        avisos.append("El punto (Pu, Mu) cae fuera del diagrama de interacción P-M: "
                      "aumenta D, la cuantía o reduce el momento/carga lateral.")
    if not flexo["cortante"]["cumple"]:
        avisos.append("El cortante supera φVn de la sección circular: cierra el paso "
                      "del refuerzo transversal (espiral/estribos) o aumenta D.")
    if flexo["esbeltez"].get("inestable"):
        avisos.append("Fuste inestable por esbeltez (Pu > 0.75·Pc): reduce el tramo "
                      "libre Lu, aumenta D o arriostra el caisson.")
    elif flexo["esbeltez"]["es_esbelto"]:
        avisos.append(f"Fuste esbelto (kLu/r = {flexo['esbeltez']['esbeltez_klu_r']} > "
                      f"{flexo['esbeltez']['limite']:.0f}): momento amplificado por "
                      f"δ_ns = {flexo['esbeltez']['delta_ns']}.")
    if flexo["davisson"].get("aplica") and not flexo["davisson"]["cumple"]:
        avisos.append("Pandeo del fuste parcialmente embebido (Davisson): Pu supera "
                      "P_adm; reduce Lu o aumenta D.")

    # Volumen de concreto: fuste cilíndrico + campana (tronco de cono) si aplica.
    A_fuste = math.pi * D ** 2 / 4.0
    if cap["acampanada"] and altura_campana > 0:
        A_base = cap["A_base_m2"]
        vol_campana = altura_campana / 3.0 * (A_fuste + A_base + math.sqrt(A_fuste * A_base))
        volumen = A_fuste * (L - altura_campana) + vol_campana
    else:
        volumen = A_fuste * L

    return {
        "tipo": "caisson",
        "norma": norma,
        "geometria": {
            "D_m": round(D, 3), "L_m": round(L, 2),
            "D_campana_m": round(cap["D_base_m"], 3),
            "altura_campana_m": round(altura_campana, 3) if cap["acampanada"] else 0.0,
            "acampanada": cap["acampanada"],
            "A_g_m2": round(A_fuste, 4),
            "perimetro_m": round(math.pi * D, 3),
            "volumen_concreto_m3": round(volumen, 2),
        },
        "capacidad": cap,
        "geotecnico": geo,
        "estructural": est,
        "cargas": {"P_servicio_kN": round(P_servicio, 1),
                   "factor_carga": factor_carga,
                   "Pu_estructural_kN": round(Pu_est, 1),
                   "Mu_kNm": round(Mu, 1), "Hu_kN": round(Hu, 1)},
        "cumple": cumple_geo and cumple_est and cumple_flexo,
        "avisos": avisos,
    }


def _cumple_geo(cap, norma, P_servicio, FS, factor_carga, Pu):
    """Chequeo geotécnico según norma; devuelve (cumple, dict-detalle)."""
    Qs, Qp, Qult = cap["Q_fuste_kN"], cap["Q_punta_kN"], cap["Q_ult_kN"]
    if norma == NORMA_CCP14:
        # φ del fuste por estrato (según el material de cada tramo) + φ de punta.
        Rs = sum(PHI_CCP14[d["tipo"]]["fuste"] * d["Qs_kN"]
                 for d in cap["fuste_detalle"])
        tp = cap["tipo_punta"]
        phi_p = PHI_CCP14[tp]["punta"]
        Rp = phi_p * Qp
        R_r = Rs + Rp                                 # resistencia factorada
        Pu_dem = Pu if (Pu and Pu > 0) else factor_carga * P_servicio
        cumple = R_r >= Pu_dem - 1e-6
        geo = {
            "metodo": "CCP-14 / AASHTO LRFD (Sección 10.8)",
            "phi_fuste_arena": PHI_CCP14["arena"]["fuste"],
            "phi_fuste_arcilla": PHI_CCP14["arcilla"]["fuste"],
            "phi_punta": phi_p, "tipo_punta": tp,
            "Q_fuste_kN": Qs, "Q_punta_kN": Qp, "Q_ult_kN": Qult,
            "R_fuste_kN": round(Rs, 1), "R_punta_kN": round(Rp, 1),
            "R_r_kN": round(R_r, 1), "Pu_demanda_kN": round(Pu_dem, 1),
            "CDR": round(R_r / Pu_dem, 3) if Pu_dem > 0 else None,
            "ratio": round(Pu_dem / R_r, 3) if R_r > 0 else None,
            "cumple": cumple,
        }
    else:
        fs = FS if (FS and FS > 0) else FS_NSR10_DEFECTO
        Qadm = Qult / fs if fs > 0 else 0.0
        cumple = Qadm >= P_servicio - 1e-6
        geo = {
            "metodo": "NSR-10 Título H (esfuerzos admisibles)",
            "FS": fs, "Q_fuste_kN": Qs, "Q_punta_kN": Qp, "Q_ult_kN": Qult,
            "Q_adm_kN": round(Qadm, 1), "P_servicio_kN": round(P_servicio, 1),
            "ratio": round(P_servicio / Qadm, 3) if Qadm > 0 else None,
            "cumple": cumple,
        }
    return cumple, geo
