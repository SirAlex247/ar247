"""
Diseño estructural específico de un MURO CON CONTRAFUERTES (counterfort wall).

La estabilidad externa (volcamiento, deslizamiento, capacidad de carga,
excentricidad y estabilidad global) es idéntica a la de un muro en voladizo de
la misma geometría, porque el conjunto muro + zapata retiene el mismo relleno y
tiene el mismo peso y ancho de base. Lo que cambia es el COMPORTAMIENTO
ESTRUCTURAL:

* La **pantalla** (vástago) deja de trabajar como voladizo vertical y pasa a
  flexionar HORIZONTALMENTE como una losa continua apoyada en los contrafuertes,
  separados una distancia ``s``. El momento de diseño se toma como
  ``M = w·s²/10`` (coeficiente de losa continua, ACI/NSR-10 C.8.3).

* El **talón** flexiona también horizontalmente entre contrafuertes bajo la
  carga neta descendente (peso del relleno + sobrecarga − reacción del suelo).

* El **contrafuerte** trabaja como una viga T (con la pantalla de ala) en
  voladizo, empotrada en la zapata, que recoge el empuje del relleno sobre su
  ancho tributario ``s`` y lo transmite a la cimentación. El acero principal de
  tracción se coloca en la cara posterior inclinada.

* Tirantes (ties): acero que "cose" la pantalla y el talón a los contrafuertes,
  dimensionado por la reacción de cada losa sobre el contrafuerte.

Referencias: Das, "Principios de Ingeniería de Cimentaciones" §8.11; NSR-10
Título C (flexión C.10, cortante C.11).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from ..models.muro import MuroContencion
from .diseno_estructural import DisenoSeccion
from .empujes import EmpujeSuelo


# Factor de carga para el empuje de tierra (categoría H, NSR-10 ELU: 1.6).
FACTOR_EMPUJE = 1.6


@dataclass
class DisenoContrafuertes:
    """Resultado del diseño estructural de un muro con contrafuertes."""
    separacion: float                 # s, centro a centro (m)
    espesor_contrafuerte: float       # t (m)
    H_relleno: float                  # altura de relleno retenida (m)
    Ka: float
    p_base: float                     # presión lateral en la base (kPa, servicio)
    pantalla: dict = field(default_factory=dict)
    talon: dict = field(default_factory=dict)
    contrafuerte: dict = field(default_factory=dict)
    tirantes: dict = field(default_factory=dict)
    notas: list[str] = field(default_factory=list)

    @property
    def cumple(self) -> bool:
        return (self.pantalla.get("cumple", False)
                and self.talon.get("cumple", False)
                and self.contrafuerte.get("cumple", False))


class DisenadorContrafuertes:
    """Diseña los elementos de un muro con contrafuertes."""

    def __init__(self, muro: MuroContencion, separacion: float,
                 espesor_contrafuerte: float, *,
                 metodo_empuje: str = "rankine",
                 recubrimiento: float = 0.075) -> None:
        self.muro = muro
        self.g = muro.geometria
        self.s = float(separacion)
        self.t_cf = float(espesor_contrafuerte)
        self.rec = recubrimiento
        self.metodo = metodo_empuje

    def disenar(self) -> DisenoContrafuertes:
        g = self.g
        rel = self.muro.suelo_relleno
        cond = self.muro.condiciones
        concreto = self.muro.concreto
        acero = self.muro.acero
        fy = acero.fy

        # Coeficiente de empuje activo (Rankine con talud).
        Ka = EmpujeSuelo.calcular_ka_rankine(rel.phi, cond.alpha)
        gamma = rel.gamma
        q = cond.sobrecarga
        H = g.H_relleno_ef                 # altura de relleno sobre la zapata
        H_stem = g.H_vastago

        # Presiones laterales (servicio): triangular (tierra) + uniforme (sobrec.)
        p_base = Ka * (gamma * H + q)      # kPa en la base de la pantalla
        notas: list[str] = []

        # ── PANTALLA: losa horizontal continua entre contrafuertes ──────────
        # Franja de 1 m de altura en la base (máx. presión). b = 1 m (altura),
        # h = espesor de la pantalla en la base.
        w_pant = p_base                    # kN/m sobre franja de 1 m de altura
        Mu_pant = FACTOR_EMPUJE * w_pant * self.s ** 2 / 10.0   # kN·m/m
        h_pant = g.b_base_vast
        fx_p = DisenoSeccion.disenar_flexion(
            Mu=Mu_pant, b=1.0, h=h_pant, concreto=concreto, acero=acero,
            recubrimiento=self.rec, nombre="Pantalla (flexión horizontal)")
        vx_p = DisenoSeccion.verificar_cortante(
            Vu=FACTOR_EMPUJE * w_pant * self.s / 2.0, b=1.0, h=h_pant,
            concreto=concreto, recubrimiento=self.rec)
        pantalla = {
            "descripcion": "Losa vertical con flexión horizontal (M = w·s²/10)",
            "espesor_m": h_pant, "d_m": fx_p.d,
            "w_kN_m": w_pant, "Mu_kNm_m": Mu_pant,
            "As_req_mm2_m": fx_p.As_requerido, "As_min_mm2_m": fx_p.As_minimo,
            "Vu_kN_m": vx_p.Vu, "phiVc_kN_m": vx_p.phi_Vc,
            "cumple": fx_p.cumple and vx_p.cumple,
        }

        # ── TALÓN: losa horizontal continua bajo carga descendente neta ─────
        # Carga neta conservadora = peso del relleno sobre el talón + sobrecarga
        # (se desprecia la reacción del suelo hacia arriba → del lado seguro).
        w_talon = gamma * H + q
        Mu_talon = FACTOR_EMPUJE * w_talon * self.s ** 2 / 10.0
        h_talon = g.e_zapata
        fx_t = DisenoSeccion.disenar_flexion(
            Mu=Mu_talon, b=1.0, h=h_talon, concreto=concreto, acero=acero,
            recubrimiento=self.rec, nombre="Talón (flexión horizontal)")
        vx_t = DisenoSeccion.verificar_cortante(
            Vu=FACTOR_EMPUJE * w_talon * self.s / 2.0, b=1.0, h=h_talon,
            concreto=concreto, recubrimiento=self.rec)
        talon = {
            "descripcion": "Losa de talón con flexión horizontal (M = w·s²/10)",
            "espesor_m": h_talon, "d_m": fx_t.d,
            "w_kN_m": w_talon, "Mu_kNm_m": Mu_talon,
            "As_req_mm2_m": fx_t.As_requerido, "As_min_mm2_m": fx_t.As_minimo,
            "Vu_kN_m": vx_t.Vu, "phiVc_kN_m": vx_t.phi_Vc,
            "cumple": fx_t.cumple and vx_t.cumple,
        }

        # ── CONTRAFUERTE: viga T en voladizo empotrada en la zapata ─────────
        # Empuje total sobre el ancho tributario s (triangular + sobrecarga).
        P_tierra = 0.5 * Ka * gamma * H_stem ** 2 * self.s     # kN
        P_sobrec = Ka * q * H_stem * self.s                    # kN
        P_total = P_tierra + P_sobrec
        # Punto de aplicación desde la base.
        if P_total > 0:
            y_bar = (P_tierra * (H_stem / 3.0) + P_sobrec * (H_stem / 2.0)) / P_total
        else:
            y_bar = H_stem / 3.0
        Mu_cf = FACTOR_EMPUJE * P_total * y_bar                # kN·m
        # Peralte efectivo del contrafuerte en la base ≈ longitud del talón
        # (el acero de tracción va en la cara posterior inclinada).
        d_cf = max(0.10, g.b_talon - self.rec)
        # Acero principal por brazo de palanca (jd ≈ 0.9 d).
        jd = 0.9 * d_cf
        As_cf = (Mu_cf * 1e6) / (DisenoSeccion.PHI_FLEXION * fy * jd * 1000.0)  # mm²
        # Cuantía mínima como viga (1.4/fy·b_w·d y √fc/(4fy)·b_w·d).
        bw_mm = self.t_cf * 1000.0
        d_mm = d_cf * 1000.0
        As_min_cf = max(1.4 / fy, math.sqrt(concreto.fc) / (4.0 * fy)) * bw_mm * d_mm
        As_cf_adopt = max(As_cf, As_min_cf)
        # Cortante en la base del contrafuerte.
        Vu_cf = FACTOR_EMPUJE * P_total
        Vc_cf = 0.17 * concreto.lambda_factor * math.sqrt(concreto.fc) * bw_mm * d_mm / 1000.0
        phiVc_cf = DisenoSeccion.PHI_CORTANTE * Vc_cf
        cumple_cf = As_cf != float("inf") and (As_cf_adopt >= As_min_cf)
        if Vu_cf > phiVc_cf:
            notas.append("El contrafuerte requiere estribos por cortante "
                         f"(Vu={Vu_cf:.0f} kN > φVc={phiVc_cf:.0f} kN).")
        contrafuerte = {
            "descripcion": "Viga T en voladizo empotrada en la zapata",
            "P_total_kN": P_total, "y_aplicacion_m": y_bar,
            "Mu_kNm": Mu_cf, "d_m": d_cf, "bw_m": self.t_cf,
            "As_req_mm2": As_cf_adopt, "As_min_mm2": As_min_cf,
            "Vu_kN": Vu_cf, "phiVc_kN": phiVc_cf,
            "requiere_estribos": Vu_cf > phiVc_cf,
            "cumple": cumple_cf,
        }

        # ── TIRANTES (ties) que unen pantalla y talón al contrafuerte ───────
        # Pantalla→contrafuerte: tracción horizontal por metro de altura = p·s.
        As_tie_pant = (FACTOR_EMPUJE * p_base * self.s) * 1e3 / (DisenoSeccion.PHI_FLEXION * fy)  # mm²/m
        # Talón→contrafuerte: tracción vertical por metro de longitud = w·s.
        As_tie_talon = (FACTOR_EMPUJE * w_talon * self.s) * 1e3 / (DisenoSeccion.PHI_FLEXION * fy)  # mm²/m
        tirantes = {
            "pantalla_As_mm2_m": As_tie_pant,
            "talon_As_mm2_m": As_tie_talon,
            "descripcion": "Acero que ancla la pantalla y el talón a los contrafuertes",
        }

        # Recomendación de separación (Das): 0.3H a 0.7H.
        s_min, s_max = 0.3 * g.H_total, 0.7 * g.H_total
        if not (s_min <= self.s <= s_max):
            notas.append(
                f"La separación s={self.s:.2f} m está fuera del rango recomendado "
                f"({s_min:.2f}–{s_max:.2f} m ≈ 0.3H–0.7H).")

        return DisenoContrafuertes(
            separacion=self.s, espesor_contrafuerte=self.t_cf,
            H_relleno=H, Ka=Ka, p_base=p_base,
            pantalla=pantalla, talon=talon, contrafuerte=contrafuerte,
            tirantes=tirantes, notas=notas)
