"""Diseño de cimentaciones para maquinaria dinámica (ACI 351.3R).

Bloque rígido de concreto sobre el suelo, analizado por el método de los
parámetros concentrados (semiespacio elástico, Richart–Hall–Woods 1970, que
adopta ACI 351.3R Cap. 4). Se resuelven los cuatro modos desacoplados:

    vertical (z), horizontal (x), cabeceo/rocking (ψ) y torsión/yaw (θ).

Para cada modo se calcula el radio equivalente r₀, la rigidez del resorte del
suelo k, la relación de masa/inercia B, el amortiguamiento geométrico D, la
frecuencia natural fₙ y —bajo la fuerza de desbalance de la máquina— la
amplitud de vibración en régimen permanente. Verificaciones:

  - Resonancia: la frecuencia de operación f debe alejarse de fₙ
    (f/fₙ ≤ 0.8 «sub-sintonizada» o ≥ 1.2 «sobre-sintonizada»).
  - Amplitud: la amplitud pico ≤ amplitud admisible (severidad de vibración).
  - Presión estática de contacto ≤ q_adm.

Unidades internas de la dinámica: SI base (N, kg, m, Pa, s, Hz). Las entradas de
la app llegan en kN/kPa/MPa/m y se convierten en la frontera.
"""
from __future__ import annotations

import math

G_ACEL = 9.80665  # m/s²


# ---------------------------------------------------------------------------
# Un modo (traslación o rotación)
# ---------------------------------------------------------------------------
def _modo_traslacion(nombre, k, m, D, F0, f_op):
    """Modo de traslación: fₙ, relación de frecuencias y amplitud permanente.

    Excitación armónica de amplitud constante F0 (N) — para desbalance
    rotatorio, F0 = m_e·e·ω². Amplitud = (F0/k)·1/√((1−r²)²+(2Dr)²)."""
    wn = math.sqrt(k / m) if m > 0 else 0.0
    fn = wn / (2.0 * math.pi)
    r = (f_op / fn) if fn > 0 else 0.0
    denom = math.sqrt((1.0 - r ** 2) ** 2 + (2.0 * D * r) ** 2)
    amp = (F0 / k) / denom if (k > 0 and denom > 0) else 0.0
    Md = (1.0 / denom) if denom > 0 else 0.0
    return {
        "nombre": nombre, "k": k, "fn_Hz": round(fn, 3),
        "amortiguamiento_D": round(D, 4), "razon_frec": round(r, 3),
        "amplificacion": round(Md, 3), "amplitud_m": amp,
        "amplitud_um": round(amp * 1e6, 3),
    }


def _modo_rotacion(nombre, k, I, D, M0, f_op, brazo=0.0):
    """Modo de rotación (cabeceo/torsión): amplitud angular y, si ``brazo``>0,
    el desplazamiento horizontal en la parte alta = φ·brazo."""
    wn = math.sqrt(k / I) if I > 0 else 0.0
    fn = wn / (2.0 * math.pi)
    r = (f_op / fn) if fn > 0 else 0.0
    denom = math.sqrt((1.0 - r ** 2) ** 2 + (2.0 * D * r) ** 2)
    phi = (M0 / k) / denom if (k > 0 and denom > 0) else 0.0     # rad
    amp = phi * brazo if brazo > 0 else phi
    Md = (1.0 / denom) if denom > 0 else 0.0
    return {
        "nombre": nombre, "k": k, "fn_Hz": round(fn, 3),
        "amortiguamiento_D": round(D, 4), "razon_frec": round(r, 3),
        "amplificacion": round(Md, 3),
        "amplitud_ang_rad": phi, "amplitud_m": amp,
        "amplitud_um": round(amp * 1e6, 3),
    }


def _estado_resonancia(r, banda=0.2):
    """Clasifica la separación de la frecuencia de operación respecto a fₙ."""
    if r <= (1.0 - banda):
        return "sub-sintonizada", True
    if r >= (1.0 + banda):
        return "sobre-sintonizada", True
    return "EN RESONANCIA", False


# ---------------------------------------------------------------------------
# Diseño estructural del bloque (concreto/acero): rigidez, fuerza dinámica de
# diseño, pernos de anclaje y refuerzo mínimo. (El soporte dinámico y las
# propiedades del suelo son inputs; aquí se dimensiona el hormigón y el acero.)
# ---------------------------------------------------------------------------
def _diseno_estructural_bloque(*, B, L, h, hcg, F0_N, W_total_kN, fc, fy,
                               factor_fatiga, n_pernos, db_perno_mm, fy_perno,
                               embed_perno, sep_pernos, db_ref_mm, recubrimiento):
    """Diseño estructural del bloque de cimentación: validación de bloque rígido
    (ACI 351.3R), fuerza dinámica de diseño con factor de fatiga, pernos de
    anclaje (ACI 318-19 Cap. 17, preinstalados) y refuerzo mínimo cada cara."""
    av = []
    Lmax = max(B, L)

    # (1) Rigidez del bloque — valida el método de parámetros concentrados.
    h_min = 0.60
    h_rec = max(h_min, 0.20 * Lmax)
    cumple_rigidez = h >= h_min - 1e-9
    rigido = h >= 0.20 * Lmax - 1e-9
    if not cumple_rigidez:
        av.append(f"Espesor del bloque h = {h:.2f} m < 0.60 m mínimo (ACI 351.3R): auméntalo.")
    elif not rigido:
        av.append(f"Verifica la rigidez del bloque: h = {h:.2f} m < 0.20·L_máx = "
                  f"{0.20*Lmax:.2f} m; el método de parámetros concentrados supone bloque rígido.")
    rigidez = {"h_m": round(h, 3), "h_min_m": h_min, "h_recomendado_m": round(h_rec, 2),
               "relacion_h_Lmax": round(h / Lmax, 3) if Lmax > 0 else None,
               "rigido": rigido, "cumple": cumple_rigidez}

    # (2) Fuerza dinámica de diseño (factor de fatiga sobre el desbalance, ACI 351.3R).
    F_din_N = factor_fatiga * F0_N
    M_din_N = F_din_N * hcg                              # momento de vuelco de diseño
    fuerza_diseno = {"factor_fatiga": factor_fatiga,
                     "F0_kN": round(F0_N / 1000.0, 2),
                     "F_dinamica_diseno_kN": round(F_din_N / 1000.0, 2),
                     "M_vuelco_diseno_kNm": round(M_din_N / 1000.0, 2)}

    # (3) Pernos de anclaje (ACI 318-19 Cap. 17, anclaje preinstalado / cast-in).
    pernos = {"aplica": False}
    if n_pernos and n_pernos >= 2 and db_perno_mm > 0:
        n = int(n_pernos)
        s = sep_pernos if sep_pernos > 0 else 0.7 * B   # brazo del grupo de pernos
        n_t = max(1, n // 2)                            # pernos del lado en tracción
        W_N = W_total_kN * 1000.0
        T_vuelco = (M_din_N / s) / n_t if s > 0 else 0.0
        T_vert = F_din_N / n
        T_estab = W_N / n                               # estabilizante (peso muerto)
        T_bolt = max(0.0, T_vuelco + T_vert - T_estab)  # N por perno
        V_bolt = F_din_N / n                            # cortante por perno (N)
        Ab = math.pi * (db_perno_mm / 1000.0) ** 2 / 4.0            # m²
        Ase = 0.75 * Ab                                 # área efectiva (roscado)
        futa = min(1.25 * fy_perno, 860.0) * 1000.0     # kPa
        phiNsa = 0.75 * Ase * futa * 1000.0             # N (φ=0.75 tracción acero dúctil)
        phiVsa = 0.65 * 0.6 * Ase * futa * 1000.0       # N (φ=0.65 cortante acero)
        hef_mm = (embed_perno if embed_perno > 0 else 12.0 * db_perno_mm / 1000.0) * 1000.0
        Nb = 10.0 * math.sqrt(fc) * hef_mm ** 1.5       # N (kc=10 cast-in, SI)
        phiNcb = 0.70 * Nb                              # N (perno aislado, sin reducción borde/grupo)
        rt = T_bolt / phiNsa if phiNsa > 0 else 0.0
        rv = V_bolt / phiVsa if phiVsa > 0 else 0.0
        inter = rt ** (5.0 / 3.0) + rv ** (5.0 / 3.0)
        cumple_acero = inter <= 1.0 + 1e-6
        cumple_breakout = T_bolt <= phiNcb + 1e-6
        pernos = {"aplica": True, "n": n, "db_mm": round(db_perno_mm, 1),
                  "brazo_m": round(s, 3), "hef_m": round(hef_mm / 1000.0, 3),
                  "T_perno_kN": round(T_bolt / 1000.0, 2), "V_perno_kN": round(V_bolt / 1000.0, 2),
                  "phiNsa_kN": round(phiNsa / 1000.0, 1), "phiVsa_kN": round(phiVsa / 1000.0, 1),
                  "phiNcb_kN": round(phiNcb / 1000.0, 1), "interaccion": round(inter, 3),
                  "cumple_acero": cumple_acero, "cumple_breakout": cumple_breakout,
                  "cumple": cumple_acero and cumple_breakout}
        if not cumple_acero:
            av.append("Pernos de anclaje: no cumplen la interacción tracción-cortante del acero; "
                      "aumenta el Ø o el número de pernos.")
        if not cumple_breakout:
            av.append("Pernos de anclaje: la rotura del concreto (breakout) no cumple; aumenta la "
                      "longitud embebida h_ef o f'c (verifica también borde/grupo).")
    cumple_pernos = (not pernos["aplica"]) or pernos["cumple"]

    # (4) Refuerzo mínimo del bloque (retracción-temperatura, cada cara/dirección).
    rho_st = 0.0018
    ab = math.pi * (db_ref_mm / 1000.0) ** 2 / 4.0      # m²

    def _malla(perp_w):
        As_total = rho_st * perp_w * h                  # m² (toda la sección)
        As_face = As_total / 2.0
        n_face = max(2, math.ceil(As_face / ab)) if ab > 0 else 0
        sep = (perp_w / n_face) if n_face > 0 else 0.0
        if sep > 0.30:                                  # máx 300 mm → añade barras
            n_face = max(n_face, math.ceil(perp_w / 0.30))
            sep = perp_w / n_face
        return {"As_cara_cm2": round(As_face * 1e4, 1), "n_barras_cara": int(n_face),
                "sep_cm": round(sep * 100, 1)}

    masa_ac = rho_st * (L * h) * B * 7850.0 + rho_st * (B * h) * L * 7850.0   # kg
    vol = B * L * h
    refuerzo = {"db_mm": round(db_ref_mm, 1), "rho": rho_st, "sep_max_cm": 30.0,
                "dir_B": _malla(L), "dir_L": _malla(B),
                "acero_kg_m3": round(masa_ac / vol, 1) if vol > 0 else 0.0,
                "recubrimiento_m": round(recubrimiento, 3)}

    cumple_estr = cumple_rigidez and cumple_pernos
    return {
        "rigidez": rigidez, "fuerza_diseno": fuerza_diseno,
        "pernos": pernos, "refuerzo": refuerzo,
        "cumple_rigidez": cumple_rigidez, "cumple_pernos": cumple_pernos,
        "cumple": cumple_estr,
    }, av


# ---------------------------------------------------------------------------
# Diseño principal
# ---------------------------------------------------------------------------
def disenar_maquina(*, B, L, h, peso_maquina, rpm,
                    F0=0.0, masa_excentrica_e=0.0,
                    hcg_maquina=0.0, torque_dinamico=0.0,
                    G_suelo=0.0, Vs=0.0, nu=0.33, gamma_suelo=18.0,
                    gamma_concreto=24.0, q_adm=0.0,
                    amplitud_admisible_um=50.0,
                    fc=21.0, fy=420.0, factor_fatiga=2.0,
                    n_pernos=0, db_perno=0.0, fy_perno=250.0,
                    embed_perno=0.0, sep_pernos=0.0,
                    db_refuerzo=19.05, recubrimiento=0.075) -> dict:
    """Analiza un bloque de cimentación de máquina (ACI 351.3R, método de
    parámetros concentrados).

    Entradas (unidades de la app): B, L, h, hcg (m); peso_maquina (kN); rpm;
    F0 (kN, fuerza de desbalance a la velocidad de operación) o
    masa_excentrica_e (kg·m, → F0 = m_e·e·ω²); G_suelo (MPa) o Vs (m/s);
    gamma_* (kN/m³); q_adm (kPa); amplitud_admisible (µm).
    """
    avisos = []
    # --- Propiedades del suelo (SI base) ---
    rho = gamma_suelo * 1000.0 / G_ACEL                    # kg/m³
    if G_suelo and G_suelo > 0:
        G = G_suelo * 1e6                                  # MPa → Pa
        Vs = math.sqrt(G / rho) if rho > 0 else 0.0
    elif Vs and Vs > 0:
        G = rho * Vs ** 2
    else:
        raise ValueError("Define el módulo de corte G del suelo o la velocidad de onda Vs.")

    # --- Masas ---
    peso_bloque = gamma_concreto * B * L * h               # kN
    W_total = peso_bloque + peso_maquina                   # kN
    m_bloque = peso_bloque * 1000.0 / G_ACEL               # kg
    m_maq = peso_maquina * 1000.0 / G_ACEL                 # kg
    m = m_bloque + m_maq                                   # kg

    # --- Excitación ---
    w_op = 2.0 * math.pi * rpm / 60.0                      # rad/s
    f_op = rpm / 60.0                                      # Hz
    if masa_excentrica_e and masa_excentrica_e > 0:
        F0_N = masa_excentrica_e * w_op ** 2               # N
    else:
        F0_N = F0 * 1000.0                                 # kN → N
    hcg = hcg_maquina if hcg_maquina > 0 else h            # brazo del CG de la máquina
    if not (hcg_maquina and hcg_maquina > 0):
        avisos.append("No se indicó la altura del CG de la máquina; se usó el tope del "
                      "bloque (h). Como la máquina queda por encima, especifícala para no "
                      "subestimar el cabeceo.")

    # --- Momentos de inercia de masa (base del bloque) ---
    # Cabeceo (rocking) en el plano x-z, respecto al eje y en la base.
    I_bloque_psi = (1.0 / 12.0) * m_bloque * (B ** 2 + h ** 2) + m_bloque * (h / 2.0) ** 2
    I_maq_psi = m_maq * hcg ** 2
    I_psi = I_bloque_psi + I_maq_psi
    # Torsión (yaw) respecto al eje vertical z.
    I_theta = (1.0 / 12.0) * m_bloque * (B ** 2 + L ** 2)

    # --- Radios equivalentes ---
    A = B * L
    r0_tr = math.sqrt(A / math.pi)                         # traslación
    r0_psi = (L * B ** 3 / (3.0 * math.pi)) ** 0.25        # cabeceo (eje y)
    r0_theta = (B * L * (B ** 2 + L ** 2) / (6.0 * math.pi)) ** 0.25  # torsión

    # --- Rigideces del semiespacio (Richart) ---
    kz = 4.0 * G * r0_tr / (1.0 - nu)
    kx = 32.0 * (1.0 - nu) * G * r0_tr / (7.0 - 8.0 * nu)
    kpsi = 8.0 * G * r0_psi ** 3 / (3.0 * (1.0 - nu))
    ktheta = 16.0 * G * r0_theta ** 3 / 3.0

    # --- Relaciones de masa/inercia y amortiguamiento ---
    Bz = (1.0 - nu) / 4.0 * m / (rho * r0_tr ** 3)
    Dz = 0.425 / math.sqrt(Bz) if Bz > 0 else 0.0
    Bx = (7.0 - 8.0 * nu) / (32.0 * (1.0 - nu)) * m / (rho * r0_tr ** 3)
    Dx = 0.288 / math.sqrt(Bx) if Bx > 0 else 0.0
    Bpsi = 3.0 * (1.0 - nu) / 8.0 * I_psi / (rho * r0_psi ** 5)
    Dpsi = 0.15 / ((1.0 + Bpsi) * math.sqrt(Bpsi)) if Bpsi > 0 else 0.0
    Btheta = I_theta / (rho * r0_theta ** 5)
    Dtheta = 0.50 / (1.0 + 2.0 * Btheta)               # Btheta ≥ 0 siempre (1+2Btheta > 0)

    # --- Modos ---
    modo_z = _modo_traslacion("Vertical (z)", kz, m, Dz, F0_N, f_op)
    modo_x = _modo_traslacion("Horizontal (x)", kx, m, Dx, F0_N, f_op)
    M0_psi = F0_N * hcg                                    # momento de cabeceo
    modo_psi = _modo_rotacion("Cabeceo (ψ)", kpsi, I_psi, Dpsi, M0_psi, f_op, brazo=hcg)
    modo_theta = _modo_rotacion("Torsión (θ)", ktheta, I_theta, Dtheta,
                                torque_dinamico * 1000.0, f_op,
                                brazo=math.hypot(B, L) / 2.0)
    modos = [modo_z, modo_x, modo_psi, modo_theta]

    # ¿qué modos están excitados? El desbalance rotatorio F0 excita traslación y
    # cabeceo; la torsión solo si hay torque dinámico. Un modo NO excitado se
    # informa (fₙ), pero no descalifica el diseño por resonancia.
    excitados = [F0_N > 0, F0_N > 0, F0_N > 0, torque_dinamico > 0]

    # extras por modo
    for md, rr, exc in zip(modos, (r0_tr, r0_tr, r0_psi, r0_theta), excitados):
        md["r0_m"] = round(rr, 3)
        estado, ok = _estado_resonancia(md["razon_frec"])
        md["estado_resonancia"] = estado if exc else estado + " (sin excitación)"
        md["separado"] = ok
        md["excitado"] = bool(exc)
        md["amplitud_ok"] = md["amplitud_um"] <= amplitud_admisible_um + 1e-9

    # --- Verificaciones globales (solo modos excitados gobiernan) ---
    sep_ok = all(md["separado"] for md in modos if md["excitado"])
    amp_ok = all(md["amplitud_ok"] for md in modos if md["amplitud_um"] > 0)
    if not sep_ok:
        for md in modos:
            if md["excitado"] and not md["separado"]:
                avisos.append(f"Modo {md['nombre']}: f/fₙ = {md['razon_frec']} está en la banda "
                              "de resonancia (0.8–1.2). Cambia la masa/rigidez del bloque.")
    amp_max = max((md["amplitud_um"] for md in modos), default=0.0)
    if not amp_ok:
        avisos.append(f"La amplitud de vibración ({amp_max:.1f} µm) supera la admisible "
                      f"({amplitud_admisible_um:.0f} µm): aumenta la masa del bloque o mejora el suelo.")

    # regla de masa ACI 351.3R: bloque ≥ 2–3× (rotativas) / 3–5× (alternativas) el peso de la máquina
    rel_masa = peso_bloque / peso_maquina if peso_maquina > 0 else 0.0
    if rel_masa < 2.0:
        avisos.append(f"El bloque pesa {rel_masa:.1f}× la máquina; ACI 351.3R recomienda ≥ 2–3× "
                      "(rotativas) o ≥ 3–5× (alternativas).")

    # --- Presión de contacto estática ---
    q_est = W_total / A                                    # kPa (kN/m²)
    cumple_suelo = True
    if q_adm and q_adm > 0:
        cumple_suelo = q_est <= q_adm * 1.001
        if not cumple_suelo:
            avisos.append("La presión estática supera la admisible: aumenta B×L.")

    # --- Diseño estructural del bloque (concreto/acero) ---
    estr, av_estr = _diseno_estructural_bloque(
        B=B, L=L, h=h, hcg=hcg, F0_N=F0_N, W_total_kN=W_total, fc=fc, fy=fy,
        factor_fatiga=factor_fatiga, n_pernos=n_pernos, db_perno_mm=db_perno,
        fy_perno=fy_perno, embed_perno=embed_perno, sep_pernos=sep_pernos,
        db_ref_mm=db_refuerzo, recubrimiento=recubrimiento)
    avisos += av_estr

    cumple = sep_ok and amp_ok and cumple_suelo and estr["cumple"]

    return {
        "tipo": "maquina",
        "geometria": {"B_m": round(B, 3), "L_m": round(L, 3), "h_m": round(h, 3),
                      "area_m2": round(A, 3), "hcg_maquina_m": round(hcg, 3),
                      "volumen_concreto_m3": round(B * L * h, 3)},
        "masas": {"peso_bloque_kN": round(peso_bloque, 1), "peso_maquina_kN": round(peso_maquina, 1),
                  "peso_total_kN": round(W_total, 1), "masa_total_kg": round(m, 1),
                  "relacion_masa_bloque_maquina": round(rel_masa, 2),
                  "I_cabeceo_kgm2": round(I_psi, 1), "I_torsion_kgm2": round(I_theta, 1)},
        "suelo": {"G_MPa": round(G / 1e6, 1), "Vs_m_s": round(Vs, 1), "nu": nu,
                  "rho_kg_m3": round(rho, 1)},
        "excitacion": {"rpm": round(rpm, 1), "f_operacion_Hz": round(f_op, 3),
                       "omega_rad_s": round(w_op, 2), "F0_kN": round(F0_N / 1000.0, 2)},
        "modos": modos,
        "amplitud_admisible_um": amplitud_admisible_um,
        "amplitud_max_um": round(amp_max, 3),
        "geotecnico": {"q_estatica_kPa": round(q_est, 1),
                       "q_adm_kPa": round(q_adm, 1) if q_adm else None,
                       "ratio": round(q_est / q_adm, 3) if q_adm else None,
                       "cumple": cumple_suelo},
        "estructural": estr,
        "resonancia_ok": sep_ok, "amplitud_ok": amp_ok,
        "cumple": cumple, "avisos": avisos,
    }
