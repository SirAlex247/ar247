"""Diseño estructural del muro en voladizo por la CCP-14 (Sección 5 — AASHTO LRFD).

Diferencias respecto al diseño NSR-10 (``diseno_estructural.py``):

    * Factores de resistencia (Art. 5.5.4.2.1, concreto de densidad normal):
        - Flexión (sección controlada por tracción):  φ_f = 0.90
        - Cortante:                                    φ_v = 0.90   (NSR-10: 0.75)

    * Cortante (Art. 5.8.3.3 / 5.8.3.4.1), sin refuerzo transversal:
        V_c = 0.083 · β · √f'c · b_v · d_v ,  con β = 2.0 (zapatas/muros)
        d_v = máx(0.9·d_e, 0.72·h)          (Art. 5.8.2.9)
      Las losas, zapatas y muros no requieren refuerzo transversal si
      V_u ≤ φ·V_c (Art. 5.8.2.4).

    * Refuerzo mínimo a flexión (Art. 5.7.3.3.2): el acero debe desarrollar
        M_r = φ·M_n ≥ mín(1.33·M_u , M_cr)
      con M_cr = γ3·γ1·f_r·S  (sección no preesforzada), f_r = 0.62·√f'c
      (Art. 5.4.2.6), γ1 = 1.6, γ3 = 0.67 (refuerzo A615 Grado 420), S = b·h²/6.

    * Solicitaciones mayoradas con factores LRFD (Resistencia I / Evento
      Extremo I) en lugar de γ_H = 1.6 / γ_D = 1.2:
        - Vástago: empuje activo EH·1.50 + sobrecarga LS·1.75 (+ sismo EQ·1.0).
        - Zapata:  presión de contacto y pesos mayorados (DC 1.25, EV 1.35,
          LS 1.75) del estado de capacidad (Resistencia I — máx).

Reutiliza las estructuras de salida ``DisenoFlexion/DisenoCortante/
DisenoElemento/ReporteDiseno`` de ``diseno_estructural.py`` para no romper el
frontend ni el reporte.
"""
from __future__ import annotations

import math

from ..models.muro import MuroContencion
from ..normas import ccp14
from .diseno_estructural import (
    DisenoCortante,
    DisenoElemento,
    DisenoFlexion,
    ReporteDiseno,
)
from .empujes import EmpujeSuelo
from .geometria import CalculadoraGeometria


PHI_FLEXION = 0.90
PHI_CORTANTE = 0.90          # concreto de densidad normal (Art. 5.5.4.2.1)
BETA_CORTANTE = 2.0          # procedimiento simplificado zapatas/muros (Art. 5.8.3.4.1)
GAMMA1_MCR = 1.6             # variación de fisuración por flexión (no segmental)
GAMMA3_MCR = 0.67           # f_y/f_u para refuerzo A615 Grado 420


# ===========================================================================
# Diseño de una sección rectangular por CCP-14 (Sección 5)
# ===========================================================================
class DisenoSeccionCCP14:
    """Flexión y cortante de secciones rectangulares no preesforzadas (CCP-14)."""

    @staticmethod
    def _As_para_momento(M_target_kNm: float, b_mm: float, d_mm: float,
                         fc: float, fy: float) -> float:
        """Área de acero (mm²/m) que desarrolla φ·M_n = M_target."""
        if M_target_kNm <= 0:
            return 0.0
        Rn = M_target_kNm * 1e6 / (PHI_FLEXION * b_mm * d_mm ** 2)   # MPa
        arg = 1.0 - 2.0 * Rn / (0.85 * fc)
        if arg < 0:
            return float("inf")
        rho = (0.85 * fc / fy) * (1.0 - math.sqrt(arg))
        return rho * b_mm * d_mm

    @staticmethod
    def disenar_flexion(Mu: float, b: float, h: float, concreto, acero,
                        recubrimiento: float = 0.075, phi_barra: float = 0.0191,
                        nombre: str = "Sección") -> DisenoFlexion:
        d = h - recubrimiento - phi_barra / 2.0
        if d <= 0:
            raise ValueError(f"d no positivo: h={h}, rec={recubrimiento}")
        b_mm, d_mm = b * 1000.0, d * 1000.0
        fc, fy, beta1 = concreto.fc, acero.fy, concreto.beta1
        obs: list[str] = []

        Rn = Mu * 1e6 / (PHI_FLEXION * b_mm * d_mm ** 2)             # MPa
        arg = 1.0 - 2.0 * Rn / (0.85 * fc)
        if arg < 0:
            obs.append("Sección insuficiente: aumentar h o f'c.")
            rho = float("inf")
            As_flexion = float("inf")
        else:
            rho = (0.85 * fc / fy) * (1.0 - math.sqrt(arg))
            As_flexion = rho * b_mm * d_mm

        # --- Refuerzo mínimo (Art. 5.7.3.3.2): M_r ≥ mín(1.33·Mu, M_cr) ---
        fr = 0.62 * math.sqrt(fc)                                     # módulo de rotura, MPa
        S = b_mm * (h * 1000.0) ** 2 / 6.0                            # módulo de sección, mm³
        Mcr = GAMMA3_MCR * GAMMA1_MCR * fr * S / 1e6                  # kN·m/m
        M_r_objetivo = min(1.33 * Mu, Mcr)
        As_min = DisenoSeccionCCP14._As_para_momento(M_r_objetivo, b_mm, d_mm, fc, fy)
        if As_min == float("inf"):
            As_min = 0.0

        As_adoptado = max(As_flexion, As_min) if As_flexion != float("inf") else float("inf")
        if As_min > As_flexion and As_flexion != float("inf"):
            obs.append("Controla refuerzo mínimo (Art. 5.7.3.3.2): "
                       f"M_r ≥ mín(1.33·Mu={1.33*Mu:.1f}; M_cr={Mcr:.1f}) kN·m/m.")

        # Verificación de control por tracción (φ=0.90 válido si c/d ≤ 0.375)
        if As_adoptado not in (0.0, float("inf")):
            a = As_adoptado * fy / (0.85 * fc * b_mm)
            c = a / beta1
            if c / d_mm > 0.375:
                obs.append(f"c/d={c/d_mm:.3f} > 0.375: no controlada por tracción; "
                           "revisar φ (Art. 5.7.2.1).")

        # φMn con As adoptado
        if As_adoptado in (0.0, float("inf")):
            phi_Mn = 0.0
            cumple = False
        else:
            a = As_adoptado * fy / (0.85 * fc * b_mm)
            Mn = As_adoptado * fy * (d_mm - a / 2.0)                  # N·mm
            phi_Mn = PHI_FLEXION * Mn / 1e6                           # kN·m/m
            cumple = phi_Mn >= Mu - 1e-6

        # ρ_max informativo por límite de tracción (c/d = 0.375)
        rho_max = 0.375 * beta1 * (0.85 * fc / fy) * (d_mm / d_mm)

        return DisenoFlexion(
            Mu=Mu, b=b, d=d, Rn=Rn,
            rho=rho if rho != float("inf") else 0.0,
            rho_min=(As_min / (b_mm * d_mm)) if d_mm > 0 else 0.0,
            rho_max=rho_max,
            As_requerido=As_adoptado if As_adoptado != float("inf") else 0.0,
            As_minimo=As_min,
            As_adoptado=As_adoptado if As_adoptado != float("inf") else 0.0,
            phi_Mn=phi_Mn, cumple=cumple, observaciones=obs,
        )

    @staticmethod
    def verificar_cortante(Vu: float, b: float, h: float, concreto,
                           recubrimiento: float = 0.075, phi_barra: float = 0.0191,
                           d_flexion: float | None = None) -> DisenoCortante:
        d = (d_flexion if d_flexion is not None
             else h - recubrimiento - phi_barra / 2.0)
        dv = max(0.9 * d, 0.72 * h)                                   # Art. 5.8.2.9
        b_mm, dv_mm = b * 1000.0, dv * 1000.0
        Vc_N = 0.083 * BETA_CORTANTE * concreto.lambda_factor \
            * math.sqrt(concreto.fc) * b_mm * dv_mm
        Vc = Vc_N / 1000.0                                            # kN/m
        phi_Vc = PHI_CORTANTE * Vc
        return DisenoCortante(
            Vu=Vu, Vc=Vc, phi_Vc=phi_Vc,
            requiere_estribos=Vu > phi_Vc,
            cumple=Vu <= phi_Vc,
        )


# ===========================================================================
# Diseñador del muro por CCP-14
# ===========================================================================
class DisenadorMuroVoladizoCCP14:
    """Diseño estructural por metro lineal del muro en voladizo según CCP-14."""

    def __init__(self, muro: MuroContencion, *,
                 recubrimiento_muro: float = 0.050,
                 recubrimiento_zapata: float = 0.075,
                 phi_barra_muro: float = 0.0159,
                 phi_barra_zapata: float = 0.0191,
                 metodo_empuje: str = "rankine",
                 incluir_sismo: bool = False,
                 gamma_EQ: float = 0.5) -> None:
        self.muro = muro
        self.rec_muro = recubrimiento_muro
        self.rec_zapata = recubrimiento_zapata
        self.phi_muro = phi_barra_muro
        self.phi_zapata = phi_barra_zapata
        self.metodo_empuje = metodo_empuje.lower()
        self.incluir_sismo = incluir_sismo
        self.gamma_EQ = gamma_EQ
        self._geometria = CalculadoraGeometria(muro)
        # Factores LRFD de Resistencia I (máx) para la zapata
        self.gEH = ccp14.GAMMA_P["EH_activa"][0]     # 1.50
        self.gDC = ccp14.GAMMA_P["DC"][0]            # 1.25
        self.gEV = ccp14.GAMMA_P["EV_muro"][0]       # 1.35
        self.gLS = ccp14.GAMMA_LS_RESISTENCIA        # 1.75

    # ------------------------------------------------------------------
    def _empuje_activo(self, H: float):
        rel = self.muro.suelo_relleno
        cond = self.muro.condiciones
        if self.metodo_empuje == "coulomb":
            return EmpujeSuelo.calcular_empuje_activo_coulomb(
                gamma=rel.gamma, H=H, phi_grados=rel.phi,
                delta_grados=rel.delta_efectivo, alpha_grados=cond.alpha)
        return EmpujeSuelo.calcular_empuje_activo_rankine(
            gamma=rel.gamma, H=H, phi_grados=rel.phi, alpha_grados=cond.alpha)

    # ==================================================================
    # VÁSTAGO — empuje EH·1.50 + sobrecarga LS·1.75 (+ sismo EQ·1.0)
    # ==================================================================
    def disenar_vastago(self) -> DisenoElemento:
        g = self.muro.geometria
        rel = self.muro.suelo_relleno
        cond = self.muro.condiciones
        H_prima = g.H_relleno_ef + g.b_talon * math.tan(math.radians(cond.alpha))

        emp = self._empuje_activo(H_prima)
        Ph, brazo = emp.componente_h, emp.y_aplicacion

        Ph_sc = brazo_sc = 0.0
        if cond.sobrecarga > 0:
            emp_sc = EmpujeSuelo.calcular_empuje_sobrecarga(
                q=cond.sobrecarga, H=H_prima, phi_grados=rel.phi, alpha_grados=cond.alpha)
            Ph_sc, brazo_sc = emp_sc.componente_h, emp_sc.y_aplicacion

        Mu = self.gEH * Ph * brazo + self.gLS * Ph_sc * brazo_sc
        Vu = self.gEH * Ph + self.gLS * Ph_sc

        if self.incluir_sismo and cond.kh > 0:
            emp_sis = EmpujeSuelo.calcular_empuje_sismico(
                gamma=rel.gamma, H=H_prima, phi_grados=rel.phi,
                delta_grados=rel.delta_efectivo, beta_grados=90.0,
                alpha_grados=cond.alpha, kh=cond.kh, kv=cond.kv)
            dP = max(0.0, emp_sis.componente_h - Ph)
            Mu += 1.0 * dP * emp_sis.y_aplicacion
            Vu += 1.0 * dP

        flex = DisenoSeccionCCP14.disenar_flexion(
            Mu=Mu, b=1.0, h=g.b_base_vast, concreto=self.muro.concreto,
            acero=self.muro.acero, recubrimiento=self.rec_muro,
            phi_barra=self.phi_muro, nombre="Vástago")
        cort = DisenoSeccionCCP14.verificar_cortante(
            Vu=Vu, b=1.0, h=g.b_base_vast, concreto=self.muro.concreto,
            recubrimiento=self.rec_muro, phi_barra=self.phi_muro)
        return DisenoElemento(nombre="Vástago", flexion=flex, cortante=cort)

    # ==================================================================
    # PRESIÓN DE CONTACTO MAYORADA (Resistencia I — máx) para la zapata
    # ==================================================================
    def _estado_contacto(self, sistema) -> tuple[float, float]:
        """(ΣV, e) mayorados del estado de capacidad (DC 1.25, EV 1.35, EH 1.50,
        LS 1.75), base para la presión de contacto del diseño de la zapata."""
        from .estabilidad_ccp14 import AnalisisEstabilidadCCP14
        an = AnalisisEstabilidadCCP14(self.muro, sistema)
        r = an._factorizar(ccp14.FACTORES_RESISTENCIA_I_CAPACIDAD)
        return r["SV"], r["e"]

    def _q_contacto(self, x: float, SV: float, e: float) -> float:
        """Presión de contacto mayorada en la coordenada ``x`` (desde la puntera C).

        - |e| ≤ B/6: distribución lineal (trapezoidal) q(x).
        - |e| > B/6: el suelo no toma tracción → distribución triangular sobre la
          longitud de contacto reducida L_c = 3·(B/2 − |e|); q = 0 fuera de ella.
        """
        B = self.muro.B
        if SV <= 0:
            return 0.0
        if abs(e) <= B / 6.0 + 1e-12:
            q_toe = (SV / B) * (1.0 + 6.0 * e / B)
            q_heel = (SV / B) * (1.0 - 6.0 * e / B)
            return q_toe + (q_heel - q_toe) * (x / B)
        # Redistribución triangular
        brazo = max(1e-6, B / 2.0 - abs(e))
        Lc = 3.0 * brazo
        q_max = 2.0 * SV / (3.0 * brazo)
        if e >= 0.0:                       # resultante hacia la puntera (x=0)
            return q_max * (1.0 - x / Lc) if x <= Lc else 0.0
        borde = B - Lc                     # resultante hacia el talón (x=B)
        return q_max * ((x - borde) / Lc) if x >= borde else 0.0

    # ==================================================================
    # PUNTA — voladizo frontal
    # ==================================================================
    def disenar_punta(self, SV: float, e: float) -> DisenoElemento:
        g = self.muro.geometria
        gc = self.muro.concreto.gamma
        # Presión de contacto mayorada en la puntera (x=0) y en la cara del vástago
        q1 = self._q_contacto(0.0, SV, e)
        q2 = self._q_contacto(g.b_puntera, SV, e)
        w_pp = self.gDC * gc * g.e_zapata                  # peso propio zapata (↓), DC
        qn1, qn2 = q1 - w_pp, q2 - w_pp
        L = g.b_puntera
        R = 0.5 * (qn1 + qn2) * L
        x_cg = (L * (2 * qn1 + qn2)) / (3 * (qn1 + qn2)) if (qn1 + qn2) > 0 else L / 2.0
        Mu, Vu = R * x_cg, R
        flex = DisenoSeccionCCP14.disenar_flexion(
            Mu=Mu, b=1.0, h=g.e_zapata, concreto=self.muro.concreto,
            acero=self.muro.acero, recubrimiento=self.rec_zapata,
            phi_barra=self.phi_zapata, nombre="Punta")
        cort = DisenoSeccionCCP14.verificar_cortante(
            Vu=Vu, b=1.0, h=g.e_zapata, concreto=self.muro.concreto,
            recubrimiento=self.rec_zapata, phi_barra=self.phi_zapata)
        return DisenoElemento(nombre="Punta", flexion=flex, cortante=cort)

    # ==================================================================
    # TALÓN — voladizo posterior
    # ==================================================================
    def disenar_talon(self, SV: float, e: float) -> DisenoElemento:
        g = self.muro.geometria
        gc = self.muro.concreto.gamma
        gamma_s = self.muro.suelo_relleno.gamma
        cond = self.muro.condiciones
        altura_suelo = g.H_vastago + g.b_talon * math.tan(math.radians(cond.alpha))
        w_suelo = self.gEV * gamma_s * altura_suelo        # EV
        w_pp = self.gDC * gc * g.e_zapata                  # DC
        w_sc = self.gLS * cond.sobrecarga                  # LS (sobrecarga vertical)
        w_total = w_suelo + w_pp + w_sc
        x_inicio = g.x_fin_vastago
        q_inicio = self._q_contacto(x_inicio, SV, e)       # cara posterior del vástago
        q_tal_f = self._q_contacto(g.B, SV, e)             # borde del talón (x=B)
        p1 = w_total - q_inicio
        p2 = w_total - q_tal_f
        L = g.b_talon
        R = 0.5 * (p1 + p2) * L
        x_cg = (L * (p1 + 2 * p2)) / (3 * (p1 + p2)) if (p1 + p2) > 0 else L / 2.0
        Mu, Vu = abs(R * x_cg), abs(R)
        flex = DisenoSeccionCCP14.disenar_flexion(
            Mu=Mu, b=1.0, h=g.e_zapata, concreto=self.muro.concreto,
            acero=self.muro.acero, recubrimiento=self.rec_zapata,
            phi_barra=self.phi_zapata, nombre="Talón")
        cort = DisenoSeccionCCP14.verificar_cortante(
            Vu=Vu, b=1.0, h=g.e_zapata, concreto=self.muro.concreto,
            recubrimiento=self.rec_zapata, phi_barra=self.phi_zapata)
        return DisenoElemento(nombre="Talón", flexion=flex, cortante=cort)

    # ==================================================================
    def disenar(self, sistema) -> ReporteDiseno:
        """Diseña vástago, punta y talón. ``sistema`` = SistemaCargas del muro."""
        SV, e = self._estado_contacto(sistema)
        return ReporteDiseno(
            vastago=self.disenar_vastago(),
            punta=self.disenar_punta(SV, e),
            talon=self.disenar_talon(SV, e),
        )

    # ==================================================================
    # DESGLOSE PASO A PASO (para el reporte PDF) — formato compatible
    # con diseno_estructural.detalle_diseno_estructural
    # ==================================================================
    def _pasos_cuantia(self, fx: DisenoFlexion) -> list[dict]:
        fc, fy = self.muro.concreto.fc, self.muro.acero.fy
        fr = 0.62 * math.sqrt(fc)
        return [
            {"nombre": "Peralte efectivo d = h − rec − φ/2",
             "formula": "d", "detalle": "b = 1.00 m", "valor": fx.d, "unidad": "m"},
            {"nombre": "Resistencia nominal requerida R_n = M_u/(φ·b·d²)",
             "formula": "R_n", "detalle": f"φ = {PHI_FLEXION:.2f}", "valor": fx.Rn, "unidad": "MPa"},
            {"nombre": "Módulo de rotura f_r = 0.62·√f'c (Art. 5.4.2.6)",
             "formula": "f_r", "detalle": f"√{fc:.1f}", "valor": fr, "unidad": "MPa"},
            {"nombre": "Acero requerido por flexión/mínimo (Art. 5.7.3.3.2)",
             "formula": "A_s = máx(A_s,flex ; A_s para mín(1.33·M_u, M_cr))",
             "detalle": "; ".join(fx.observaciones) if fx.observaciones else "controla flexión",
             "valor": fx.As_requerido, "unidad": "mm²/m"},
            {"nombre": "Momento resistente φ·M_n (con A_s adoptado)",
             "formula": "φ·M_n = φ·A_s·f_y·(d − a/2)",
             "detalle": f"φ = {PHI_FLEXION:.2f}", "valor": fx.phi_Mn, "unidad": "kN·m/m"},
        ]

    def detalle_diseno_estructural(self, sistema, reporte: ReporteDiseno) -> dict:
        g = self.muro.geometria
        cond = self.muro.condiciones
        rel = self.muro.suelo_relleno
        gc = self.muro.concreto.gamma
        SV, e = self._estado_contacto(sistema)
        H_prima = g.H_relleno_ef + g.b_talon * math.tan(math.radians(cond.alpha))
        emp = self._empuje_activo(H_prima)

        # Vástago
        Mu_v = reporte.vastago.flexion.Mu
        # Punta
        q1_p = self._q_contacto(0.0, SV, e)
        q2_p = self._q_contacto(g.b_puntera, SV, e)
        # Talón
        altura_suelo = g.H_vastago + g.b_talon * math.tan(math.radians(cond.alpha))

        def _bloque(elem, titulo, datos, pasos_mu):
            return {
                "titulo": titulo, "datos_entrada": datos, "pasos_mu": pasos_mu,
                "pasos_cuantia": self._pasos_cuantia(elem.flexion),
                "espesor": (g.b_base_vast if elem is reporte.vastago else g.e_zapata),
                "estado": ("CUMPLE" if (elem.flexion.cumple and elem.cortante.cumple)
                           else "REVISAR"),
            }

        return {
            "vastago": _bloque(
                reporte.vastago, "Vástago — empotramiento (CCP-14 Resistencia I)",
                [{"nombre": "H' (altura de empuje)", "valor": H_prima, "unidad": "m"},
                 {"nombre": "γ_EH (empuje activo)", "valor": self.gEH, "unidad": "-"},
                 {"nombre": "γ_LS (sobrecarga)", "valor": self.gLS, "unidad": "-"}],
                [{"nombre": "Empuje activo horizontal (EH)", "formula": "P_h",
                  "detalle": f"H' = {H_prima:.2f} m", "valor": emp.componente_h, "unidad": "kN/m"},
                 {"nombre": "M_u = γ_EH·P_h·y + γ_LS·P_sc·y_sc (+ sismo)",
                  "formula": "M_u", "detalle": f"γ_EH={self.gEH:.2f}, γ_LS={self.gLS:.2f}",
                  "valor": Mu_v, "unidad": "kN·m/m"}]),
            "punta": _bloque(
                reporte.punta, "Punta — voladizo frontal (presión mayorada)",
                [{"nombre": "L (puntera)", "valor": g.b_puntera, "unidad": "m"},
                 {"nombre": "q en puntera (mayorada)", "valor": q1_p, "unidad": "kPa"},
                 {"nombre": "q en cara del vástago (mayorada)", "valor": q2_p, "unidad": "kPa"}],
                [{"nombre": "Peso propio zapata (γ_DC)", "formula": "γ_DC·γ_c·e",
                  "detalle": f"{self.gDC:.2f}·{gc:.1f}·{g.e_zapata:.2f}",
                  "valor": self.gDC * gc * g.e_zapata, "unidad": "kPa"},
                 {"nombre": "M_u en cara del vástago", "formula": "M_u",
                  "detalle": "presión neta × brazo", "valor": reporte.punta.flexion.Mu,
                  "unidad": "kN·m/m"}]),
            "talon": _bloque(
                reporte.talon, "Talón — voladizo posterior (presión mayorada)",
                [{"nombre": "L (talón)", "valor": g.b_talon, "unidad": "m"},
                 {"nombre": "Altura de suelo", "valor": altura_suelo, "unidad": "m"},
                 {"nombre": "γ_EV (suelo) / γ_DC (concreto)", "valor": self.gEV, "unidad": "-"}],
                [{"nombre": "Peso del suelo (γ_EV)", "formula": "γ_EV·γ_s·h",
                  "detalle": f"{self.gEV:.2f}·{rel.gamma:.1f}·{altura_suelo:.2f}",
                  "valor": self.gEV * rel.gamma * altura_suelo, "unidad": "kPa"},
                 {"nombre": "M_u en cara del vástago", "formula": "M_u",
                  "detalle": "carga neta descendente × brazo", "valor": reporte.talon.flexion.Mu,
                  "unidad": "kN·m/m"}]),
        }
