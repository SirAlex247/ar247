"""
Diseño estructural del muro en voladizo según NSR-10 Título C.

Componentes diseñados:
    - Vástago (cuerpo del muro): flexión y cortante en la base del vástago.
    - Zapata (losa de cimentación):
        * Punta: momento en el arranque del vástago (cara frontal).
        * Talón: momento en el arranque del vástago (cara posterior).

El diseño se realiza en ESTADO LÍMITE ÚLTIMO (ELU) usando cargas mayoradas
y coeficientes de reducción de resistencia φ del NSR-10 C.9.3.

Factores φ:
    φ_flexion = 0.90     (controlada por tracción)
    φ_cortante = 0.75

Refuerzos mínimos:
    - Muro (vástago): ρ_v,min = 0.0012 para barras ≤ No.5 y fy ≥ 420 MPa (C.14.3.2).
                      ρ_h,min = 0.0020 (C.14.3.3).
    - Zapata (temperatura/retracción):  ρ_min = 0.0018 (C.7.12.2.1).
    - Flexión:  As_min = max(1.4·b·d / fy, √f'c · b·d / (4·fy))  (C.10.5.1).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from ..models.material import AceroRefuerzo, Concreto
from ..models.muro import MuroContencion
from ..utils.validaciones import validar_positivo
from .cargas import SistemaCargas
from .empujes import EmpujeSuelo
from .geometria import CalculadoraGeometria


# =============================================================================
# Datos de salida
# =============================================================================
@dataclass
class DisenoFlexion:
    """Resultado del diseño a flexión de una sección rectangular."""
    Mu: float          # kN·m/m
    b: float           # m (ancho unitario = 1)
    d: float           # m (peralte efectivo)
    Rn: float          # MPa
    rho: float
    rho_min: float
    rho_max: float
    As_requerido: float   # mm²/m
    As_minimo: float      # mm²/m
    As_adoptado: float    # mm²/m
    phi_Mn: float         # kN·m/m (momento resistente con As adoptado)
    cumple: bool
    observaciones: list[str]


@dataclass
class DisenoCortante:
    """Resultado de la verificación a cortante."""
    Vu: float             # kN/m
    Vc: float             # kN/m (aporte concreto)
    phi_Vc: float         # kN/m
    requiere_estribos: bool
    cumple: bool


@dataclass
class DisenoElemento:
    """Diseño consolidado de un elemento (vástago, punta o talón)."""
    nombre: str
    flexion: DisenoFlexion
    cortante: DisenoCortante


@dataclass
class ReporteDiseno:
    """Consolidación del diseño estructural del muro."""
    vastago: DisenoElemento
    punta: DisenoElemento
    talon: DisenoElemento

    @property
    def cumple_todo(self) -> bool:
        return all(
            elem.flexion.cumple and elem.cortante.cumple
            for elem in (self.vastago, self.punta, self.talon)
        )

    def resumen(self) -> str:
        lineas = ["=" * 70, "DISEÑO ESTRUCTURAL NSR-10", "=" * 70]
        for el in (self.vastago, self.punta, self.talon):
            lineas += [
                f"\n[{el.nombre.upper()}]",
                f"  Flexión: Mu={el.flexion.Mu:.2f} kN·m/m  "
                f"As_req={el.flexion.As_requerido:.0f} mm²/m  "
                f"As_adop={el.flexion.As_adoptado:.0f} mm²/m  "
                f"[{'OK' if el.flexion.cumple else 'REVISAR'}]",
                f"  Cortante: Vu={el.cortante.Vu:.2f} kN/m  "
                f"φVc={el.cortante.phi_Vc:.2f} kN/m  "
                f"[{'OK' if el.cortante.cumple else 'REVISAR'}]",
            ]
        lineas.append("=" * 70)
        return "\n".join(lineas)


# =============================================================================
# Diseño a flexión / cortante (funciones de bajo nivel NSR-10)
# =============================================================================
class DisenoSeccion:
    """Diseño de secciones rectangulares reforzadas (NSR-10 C.10)."""

    PHI_FLEXION = 0.90
    PHI_CORTANTE = 0.75

    @staticmethod
    def disenar_flexion(
        Mu: float,
        b: float,
        h: float,
        concreto: Concreto,
        acero: AceroRefuerzo,
        recubrimiento: float = 0.075,
        phi_barra: float = 0.0127,   # 1/2" por defecto
        nombre: str = "Sección",
    ) -> DisenoFlexion:
        """Diseño a flexión de sección rectangular.

        Args:
            Mu: Momento último (kN·m/m).
            b:  Ancho (m), típicamente 1.0 para diseño por metro lineal.
            h:  Peralte total de la sección (m).
            concreto, acero: Materiales.
            recubrimiento: Recubrimiento libre (m).
            phi_barra: Diámetro estimado de barra longitudinal (m).

        Returns:
            ``DisenoFlexion`` con ρ, As requerido y verificación.
        """
        validar_positivo(b, "b")
        validar_positivo(h, "h")

        # Peralte efectivo d (m)
        d = h - recubrimiento - phi_barra / 2.0
        if d <= 0:
            raise ValueError(f"d no positivo: h={h}, rec={recubrimiento}")

        # Unidades: pasamos todo a N, mm, MPa
        Mu_Nmm = Mu * 1e6                   # kN·m -> N·mm
        b_mm = b * 1000.0
        d_mm = d * 1000.0
        fc = concreto.fc
        fy = acero.fy
        beta1 = concreto.beta1

        observaciones: list[str] = []

        # Resistencia nominal requerida
        Rn = Mu_Nmm / (DisenoSeccion.PHI_FLEXION * b_mm * d_mm ** 2)  # MPa

        # Cuantía requerida: ρ = (0.85·fc/fy)·[1 - √(1 - 2Rn/(0.85·fc))]
        argumento = 1.0 - 2.0 * Rn / (0.85 * fc)
        if argumento < 0:
            observaciones.append("Sección insuficiente: aumentar h o f'c.")
            rho = float("inf")
        else:
            rho = (0.85 * fc / fy) * (1.0 - math.sqrt(argumento))

        # Cuantía mínima (NSR-10 C.10.5.1)
        rho_min = max(1.4 / fy, math.sqrt(fc) / (4.0 * fy))
        # Cuantía balanceada y máxima (0.75 ρb para controlada por tracción)
        rho_b = 0.85 * beta1 * (fc / fy) * (600.0 / (600.0 + fy))
        rho_max = 0.75 * rho_b
        if rho > rho_max:
            observaciones.append(
                f"ρ={rho:.5f} > ρ_max={rho_max:.5f}: sección no controlada por tracción."
            )

        rho_adoptado = max(rho, rho_min)
        if rho_adoptado == rho_min and rho < rho_min:
            observaciones.append("Controla cuantía mínima por flexión (C.10.5.1).")

        As_req = rho_adoptado * b_mm * d_mm          # mm²/m
        As_min = rho_min * b_mm * d_mm

        # φMn con As adoptado
        a = As_req * fy / (0.85 * fc * b_mm)         # mm
        Mn_Nmm = As_req * fy * (d_mm - a / 2.0)      # N·mm
        phi_Mn = DisenoSeccion.PHI_FLEXION * Mn_Nmm / 1e6  # kN·m/m

        cumple = phi_Mn >= Mu and rho <= rho_max and rho != float("inf")

        return DisenoFlexion(
            Mu=Mu, b=b, d=d, Rn=Rn,
            rho=rho if rho != float("inf") else 0.0,
            rho_min=rho_min, rho_max=rho_max,
            As_requerido=As_req, As_minimo=As_min, As_adoptado=As_req,
            phi_Mn=phi_Mn, cumple=cumple, observaciones=observaciones,
        )

    # ------------------------------------------------------------------
    @staticmethod
    def verificar_cortante(
        Vu: float,
        b: float,
        h: float,
        concreto: Concreto,
        recubrimiento: float = 0.075,
        phi_barra: float = 0.0127,
    ) -> DisenoCortante:
        """Verificación a cortante para elemento sin refuerzo transversal.

        Aporte del concreto (NSR-10 C.11.2.1.1):
            Vc = 0.17 · λ · √f'c · b · d       (N, mm, MPa)
        Para muros y zapatas sin estribos se requiere φVc >= Vu.
        """
        d = h - recubrimiento - phi_barra / 2.0
        b_mm = b * 1000.0
        d_mm = d * 1000.0

        Vc_N = 0.17 * concreto.lambda_factor * math.sqrt(concreto.fc) * b_mm * d_mm
        Vc = Vc_N / 1000.0                                # kN/m
        phi_Vc = DisenoSeccion.PHI_CORTANTE * Vc

        return DisenoCortante(
            Vu=Vu, Vc=Vc, phi_Vc=phi_Vc,
            requiere_estribos=Vu > phi_Vc,
            cumple=Vu <= phi_Vc,
        )


# =============================================================================
# Diseño del muro completo
# =============================================================================
class DisenadorMuroVoladizo:
    """Realiza el diseño estructural por metro lineal del muro en voladizo.

    Se emplea la envolvente de momentos obtenida de la combinación ELU crítica
    suministrada por el usuario.
    """

    def __init__(
        self,
        muro: MuroContencion,
        factor_mayoracion_empuje: float = 1.6,
        factor_mayoracion_peso: float = 1.2,
        recubrimiento_muro: float = 0.050,
        recubrimiento_zapata: float = 0.075,
        phi_barra_muro: float = 0.0159,     # #5 (5/8")
        phi_barra_zapata: float = 0.0191,   # #6 (3/4")
        metodo_empuje: str = "rankine",
    ) -> None:
        self.muro = muro
        self.gamma_H = factor_mayoracion_empuje
        self.gamma_D = factor_mayoracion_peso
        self.rec_muro = recubrimiento_muro
        self.rec_zapata = recubrimiento_zapata
        self.phi_muro = phi_barra_muro
        self.phi_zapata = phi_barra_zapata
        self.metodo_empuje = metodo_empuje.lower()
        self._geometria = CalculadoraGeometria(muro)

    # ------------------------------------------------------------------
    def _empuje_activo_en_vastago(self, H_prima_vast: float):
        """Calcula el empuje activo sobre el vástago usando el mismo
        método (Rankine o Coulomb) elegido para el análisis global."""
        relleno = self.muro.suelo_relleno
        cond = self.muro.condiciones
        if self.metodo_empuje == "coulomb":
            return EmpujeSuelo.calcular_empuje_activo_coulomb(
                gamma=relleno.gamma, H=H_prima_vast,
                phi_grados=relleno.phi,
                delta_grados=relleno.delta_efectivo,
                alpha_grados=cond.alpha,
            )
        return EmpujeSuelo.calcular_empuje_activo_rankine(
            gamma=relleno.gamma, H=H_prima_vast,
            phi_grados=relleno.phi, alpha_grados=cond.alpha,
        )

    # ==================================================================
    # VÁSTAGO
    # ==================================================================
    def disenar_vastago(self) -> DisenoElemento:
        """Diseño del arranque del vástago (sección crítica)."""
        g = self.muro.geometria
        relleno = self.muro.suelo_relleno
        cond = self.muro.condiciones

        # Altura de suelo que presiona contra el vástago (desde corona hacia abajo)
        # Si H_relleno_ef < H_vastago, la parte superior queda sin presión.
        Hv = g.H_vastago
        H_empuje_vast = g.H_relleno_ef   # altura sobre la que actúa empuje en el vástago
        H_prima_vast = H_empuje_vast + g.b_talon * math.tan(math.radians(cond.alpha))

        # Empuje activo sobre el vástago (mismo método que el análisis global)
        emp = self._empuje_activo_en_vastago(H_prima_vast)
        # Fuerza horizontal y momento en arranque
        Ph = emp.componente_h
        brazo = emp.y_aplicacion   # respecto a la base del vástago

        # Por sobrecarga (si existe)
        Ph_sc = 0.0
        brazo_sc = 0.0
        if cond.sobrecarga > 0:
            emp_sc = EmpujeSuelo.calcular_empuje_sobrecarga(
                q=cond.sobrecarga, H=H_prima_vast,
                phi_grados=relleno.phi, alpha_grados=cond.alpha,
            )
            Ph_sc = emp_sc.componente_h
            brazo_sc = emp_sc.y_aplicacion

        # Mayorar (categoria H y Lsc -> factor 1.6)
        Mu = self.gamma_H * (Ph * brazo + Ph_sc * brazo_sc)
        Vu = self.gamma_H * (Ph + Ph_sc)

        # Diseño a flexión y cortante con espesor b_base_vast
        flex = DisenoSeccion.disenar_flexion(
            Mu=Mu, b=1.0, h=g.b_base_vast,
            concreto=self.muro.concreto, acero=self.muro.acero,
            recubrimiento=self.rec_muro, phi_barra=self.phi_muro,
            nombre="Vástago",
        )
        # Para cortante, sección crítica a distancia d del empotramiento (simpl.)
        cort = DisenoSeccion.verificar_cortante(
            Vu=Vu, b=1.0, h=g.b_base_vast,
            concreto=self.muro.concreto,
            recubrimiento=self.rec_muro, phi_barra=self.phi_muro,
        )
        return DisenoElemento(nombre="Vástago", flexion=flex, cortante=cort)

    # ==================================================================
    # ZAPATA: PUNTA
    # ==================================================================
    def disenar_punta(self, q_puntera: float, q_talon: float) -> DisenoElemento:
        """Diseño de la punta de la zapata.

        La punta trabaja como voladizo sometido a la presión de contacto
        (hacia arriba) menos el peso propio de la punta.

        Args:
            q_puntera: Presión en la puntera (kPa, sin mayorar).
            q_talon:   Presión en el talón (kPa, sin mayorar).
        """
        g = self.muro.geometria
        gc = self.muro.concreto.gamma

        # Presión mayorada (1.6 por tratarse de reacción del suelo -> H)
        q1 = self.gamma_H * q_puntera
        q2_base = q_talon + (q_puntera - q_talon) * (g.B - g.b_puntera) / g.B
        q2 = self.gamma_H * q2_base

        # Peso propio mayorado (1.2·D, sentido opuesto a la presión del suelo)
        w_propio = self.gamma_D * gc * g.e_zapata     # kN/m² por unidad de área

        # Momento y cortante en cara del vástago (x = b_puntera desde C)
        L = g.b_puntera
        # Presión neta varía linealmente: en puntera q_neto1, en cara vástago q_neto2
        q_neto1 = q1 - w_propio
        q_neto2 = q2 - w_propio

        # Resultante trapezoidal sobre la punta:
        R = 0.5 * (q_neto1 + q_neto2) * L                         # kN/m
        # Brazo desde el arranque del vástago (centroide trapecio):
        if (q_neto1 + q_neto2) > 0:
            x_cg = (L * (2 * q_neto1 + q_neto2)) / (3 * (q_neto1 + q_neto2))
        else:
            x_cg = L / 2.0
        Mu = R * x_cg
        Vu = R

        flex = DisenoSeccion.disenar_flexion(
            Mu=Mu, b=1.0, h=g.e_zapata,
            concreto=self.muro.concreto, acero=self.muro.acero,
            recubrimiento=self.rec_zapata, phi_barra=self.phi_zapata,
            nombre="Punta",
        )
        cort = DisenoSeccion.verificar_cortante(
            Vu=Vu, b=1.0, h=g.e_zapata,
            concreto=self.muro.concreto,
            recubrimiento=self.rec_zapata, phi_barra=self.phi_zapata,
        )
        return DisenoElemento(nombre="Punta", flexion=flex, cortante=cort)

    # ==================================================================
    # ZAPATA: TALÓN
    # ==================================================================
    def disenar_talon(self, q_puntera: float, q_talon: float) -> DisenoElemento:
        """Diseño del talón de la zapata.

        Sobre el talón actúan HACIA ABAJO:
            - Peso propio del talón (concreto).
            - Peso del suelo y sobrecarga encima.
        HACIA ARRIBA:
            - Presión de contacto del suelo de fundación.
        """
        g = self.muro.geometria
        gc = self.muro.concreto.gamma
        gamma_s = self.muro.suelo_relleno.gamma
        cond = self.muro.condiciones

        # Cargas verticales descendentes mayoradas (permanentes: 1.2)
        altura_suelo = g.H_vastago + g.b_talon * math.tan(math.radians(cond.alpha))
        w_suelo = self.gamma_D * gamma_s * altura_suelo          # kPa
        w_propio = self.gamma_D * gc * g.e_zapata                # kPa
        w_sobrecarga = 1.6 * cond.sobrecarga                     # kPa

        # Presión de reacción mayorada en los bordes del talón
        x_inicio = g.x_fin_vastago
        x_fin = g.B
        q_inicio = self._interp_presion(q_puntera, q_talon, x_inicio, g.B)
        q_fin = q_talon
        q1 = self.gamma_H * q_inicio
        q2 = self.gamma_H * q_fin

        # Presión NETA sobre el talón (descendente positiva)
        w_total = w_suelo + w_propio + w_sobrecarga
        p1 = w_total - q1                # en borde x_inicio
        p2 = w_total - q2                # en borde x_fin

        L = g.b_talon
        R = 0.5 * (p1 + p2) * L
        # Brazo al arranque del vástago (cara interna del talón)
        if (p1 + p2) > 0:
            x_cg = (L * (p1 + 2 * p2)) / (3 * (p1 + p2))
        else:
            x_cg = L / 2.0
        Mu = abs(R * x_cg)
        Vu = abs(R)

        flex = DisenoSeccion.disenar_flexion(
            Mu=Mu, b=1.0, h=g.e_zapata,
            concreto=self.muro.concreto, acero=self.muro.acero,
            recubrimiento=self.rec_zapata, phi_barra=self.phi_zapata,
            nombre="Talón",
        )
        cort = DisenoSeccion.verificar_cortante(
            Vu=Vu, b=1.0, h=g.e_zapata,
            concreto=self.muro.concreto,
            recubrimiento=self.rec_zapata, phi_barra=self.phi_zapata,
        )
        return DisenoElemento(nombre="Talón", flexion=flex, cortante=cort)

    # ==================================================================
    @staticmethod
    def _interp_presion(q_pie: float, q_tal: float, x: float, B: float) -> float:
        """Interpolación lineal de la presión entre puntera (x=0) y talón (x=B)."""
        return q_pie + (q_tal - q_pie) * x / B

    # ==================================================================
    # DESGLOSE PASO A PASO DEL DISEÑO (para reporte)
    # ==================================================================
    def detalle_diseno_estructural(
        self, q_puntera: float, q_talon: float,
        reporte: "ReporteDiseno",
    ) -> dict:
        """Devuelve los pasos intermedios del cálculo estructural de cada
        elemento: cómo se obtiene Mu y cómo se llega a la cuantía ρ y al
        acero requerido As.

        Útil para generar el reporte paso-a-paso en el PDF.  No recalcula
        el diseño en sí (se apoya en ``reporte`` ya producido); sólo
        reconstruye los valores intermedios que ``DisenoFlexion`` no
        almacena explícitamente.
        """
        g = self.muro.geometria
        cond = self.muro.condiciones
        rel = self.muro.suelo_relleno
        gc = self.muro.concreto.gamma
        fc = self.muro.concreto.fc
        fy = self.muro.acero.fy
        gH, gD = self.gamma_H, self.gamma_D

        # ----- VÁSTAGO -----
        Hv = g.H_vastago
        H_prima_vast = g.H_relleno_ef + g.b_talon * math.tan(math.radians(cond.alpha))
        emp = self._empuje_activo_en_vastago(H_prima_vast)
        Ph_v, brazo_v = emp.componente_h, emp.y_aplicacion
        Ph_sc_v = brazo_sc_v = 0.0
        if cond.sobrecarga > 0:
            emp_sc = EmpujeSuelo.calcular_empuje_sobrecarga(
                q=cond.sobrecarga, H=H_prima_vast,
                phi_grados=rel.phi, alpha_grados=cond.alpha)
            Ph_sc_v, brazo_sc_v = emp_sc.componente_h, emp_sc.y_aplicacion
        Mu_v = gH * (Ph_v * brazo_v + Ph_sc_v * brazo_sc_v)

        # ----- PUNTA -----
        q1_p = gH * q_puntera
        q2_base = q_talon + (q_puntera - q_talon) * (g.B - g.b_puntera) / g.B
        q2_p    = gH * q2_base
        w_propio_p = gD * gc * g.e_zapata
        qn1_p, qn2_p = q1_p - w_propio_p, q2_p - w_propio_p
        Lp = g.b_puntera
        Rp = 0.5 * (qn1_p + qn2_p) * Lp
        x_cg_p = (Lp * (2*qn1_p + qn2_p)) / (3*(qn1_p + qn2_p)) \
                 if (qn1_p + qn2_p) > 0 else Lp / 2.0
        Mu_p = Rp * x_cg_p

        # ----- TALÓN -----
        altura_suelo = g.H_vastago + g.b_talon * math.tan(math.radians(cond.alpha))
        w_suelo_t    = gD * rel.gamma * altura_suelo
        w_propio_t   = gD * gc * g.e_zapata
        w_sc_t       = 1.6 * cond.sobrecarga
        w_total_t    = w_suelo_t + w_propio_t + w_sc_t
        x_inicio     = g.x_fin_vastago
        q_inicio     = self._interp_presion(q_puntera, q_talon, x_inicio, g.B)
        q1_t, q2_t   = gH * q_inicio, gH * q_talon
        p1_t, p2_t   = w_total_t - q1_t, w_total_t - q2_t
        Lt = g.b_talon
        Rt = 0.5 * (p1_t + p2_t) * Lt
        x_cg_t = (Lt * (p1_t + 2*p2_t)) / (3*(p1_t + p2_t)) \
                 if (p1_t + p2_t) > 0 else Lt / 2.0
        Mu_t = abs(Rt * x_cg_t)

        # Helper: construye los "pasos" de cuantía para un DisenoFlexion
        def _pasos_cuantia(fx) -> list[dict]:
            rho_adopt = max(fx.rho, fx.rho_min)
            return [
                {"nombre": "Peralte efectivo",
                 "formula": ("d = h &minus; rec &minus; &phi;<sub>barra</sub>/2"),
                 "detalle": f"h = {fx.b*0+0:.0f}; con b = 1.00 m de ancho",
                 "valor": fx.d, "unidad": "m"},
                {"nombre": "Resistencia nominal requerida",
                 "formula": ("R<sub>n</sub> = M<sub>u</sub> / "
                             "(&phi; &middot; b &middot; d<sup>2</sup>)"),
                 "detalle": (f"{fx.Mu:.2f} / (0.90 &middot; 1.00 "
                             f"&middot; {fx.d:.2f}<sup>2</sup>)"),
                 "valor": fx.Rn, "unidad": "MPa"},
                {"nombre": "Cuantía requerida por flexión",
                 "formula": ("&rho; = (0.85&middot;f'<sub>c</sub>/f<sub>y</sub>)"
                             " &middot; [1 &minus; &radic;(1 &minus; "
                             "2&middot;R<sub>n</sub>/(0.85&middot;f'<sub>c</sub>))]"),
                 "detalle": (f"con f'<sub>c</sub> = {fc:.2f} MPa, "
                             f"f<sub>y</sub> = {fy:.2f} MPa"),
                 "valor": fx.rho, "unidad": "-"},
                {"nombre": "Cuantía mínima por flexión (C.10.5.1)",
                 "formula": ("&rho;<sub>min</sub> = max( 1.4/f<sub>y</sub>, "
                             "&radic;f'<sub>c</sub>/(4&middot;f<sub>y</sub>) )"),
                 "detalle": (f"max({1.4/fy:.5f}; "
                             f"{math.sqrt(fc)/(4*fy):.5f})"),
                 "valor": fx.rho_min, "unidad": "-"},
                {"nombre": "Cuantía máxima (0.75&middot;&rho;<sub>b</sub>)",
                 "formula": ("&rho;<sub>max</sub> = 0.75 &middot; 0.85 "
                             "&middot; &beta;<sub>1</sub> &middot; "
                             "(f'<sub>c</sub>/f<sub>y</sub>) "
                             "&middot; 600/(600+f<sub>y</sub>)"),
                 "detalle": "(límite para control por tracción)",
                 "valor": fx.rho_max, "unidad": "-"},
                {"nombre": "Cuantía adoptada",
                 "formula": ("&rho;<sub>adoptado</sub> = max(&rho;, "
                             "&rho;<sub>min</sub>)"),
                 "detalle": ("controla cuantía mínima"
                             if fx.rho < fx.rho_min
                             else "controla cuantía de flexión"),
                 "valor": rho_adopt, "unidad": "-"},
                {"nombre": "Acero requerido por metro",
                 "formula": ("A<sub>s</sub> = &rho;<sub>adoptado</sub> "
                             "&middot; b &middot; d"),
                 "detalle": (f"{rho_adopt:.5f} &middot; 1000 mm "
                             f"&middot; {fx.d*1000:.2f} mm"),
                 "valor": fx.As_requerido, "unidad": "mm&sup2;/m"},
                {"nombre": "Momento resistente &phi;M<sub>n</sub>",
                 "formula": ("&phi;M<sub>n</sub> = &phi; &middot; A<sub>s</sub> "
                             "&middot; f<sub>y</sub> &middot; (d &minus; a/2)"),
                 "detalle": "(verificación con A<sub>s</sub> adoptado)",
                 "valor": fx.phi_Mn, "unidad": "kN·m/m"},
            ]

        return {
            "vastago": {
                "titulo": "Vástago — empotramiento en la base",
                "datos_entrada": [
                    {"nombre": "H (altura del vástago)",
                     "valor": Hv, "unidad": "m"},
                    {"nombre": "H' (altura de empuje, incluye &alpha;)",
                     "valor": H_prima_vast, "unidad": "m"},
                    {"nombre": "&gamma; del relleno",
                     "valor": rel.gamma, "unidad": "kN/m&sup3;"},
                    {"nombre": "&phi; del relleno",
                     "valor": rel.phi, "unidad": "°"},
                    {"nombre": "Sobrecarga q",
                     "valor": cond.sobrecarga, "unidad": "kPa"},
                    {"nombre": "Factor de mayoración &gamma;<sub>H</sub>",
                     "valor": gH, "unidad": "-"},
                ],
                "pasos_mu": [
                    {"nombre": "Empuje activo horizontal del suelo",
                     "formula": ("P<sub>h</sub> = &frac12; &middot; &gamma; &middot; "
                                 "K<sub>a</sub> &middot; H'<sup>2</sup>  "
                                 "(Rankine, comp. horiz.)"),
                     "detalle": f"H' = {H_prima_vast:.2f} m",
                     "valor": Ph_v, "unidad": "kN/m"},
                    {"nombre": "Brazo del empuje del suelo",
                     "formula": "y = H'/3  (distribución triangular)",
                     "detalle": f"{H_prima_vast:.2f} / 3",
                     "valor": brazo_v, "unidad": "m"},
                    {"nombre": "Empuje por sobrecarga",
                     "formula": ("P<sub>h,sc</sub> = q &middot; "
                                 "K<sub>a</sub> &middot; H'"),
                     "detalle": f"q = {cond.sobrecarga:.2f} kPa",
                     "valor": Ph_sc_v, "unidad": "kN/m"},
                    {"nombre": "Brazo de la sobrecarga",
                     "formula": ("y<sub>sc</sub> = H'/2  "
                                 "(distribución rectangular)"),
                     "detalle": f"{H_prima_vast:.2f} / 2",
                     "valor": brazo_sc_v, "unidad": "m"},
                    {"nombre": "Momento último en el empotramiento",
                     "formula": ("M<sub>u</sub> = &gamma;<sub>H</sub> &middot; "
                                 "(P<sub>h</sub> &middot; y + "
                                 "P<sub>h,sc</sub> &middot; y<sub>sc</sub>)"),
                     "detalle": (f"{gH:.2f} &middot; ({Ph_v:.2f}&middot;"
                                 f"{brazo_v:.2f} + {Ph_sc_v:.2f}&middot;"
                                 f"{brazo_sc_v:.2f})"),
                     "valor": Mu_v, "unidad": "kN·m/m"},
                ],
                "pasos_cuantia": _pasos_cuantia(reporte.vastago.flexion),
                "espesor": g.b_base_vast,
                "estado": ("CUMPLE"
                           if (reporte.vastago.flexion.cumple and
                               reporte.vastago.cortante.cumple)
                           else "REVISAR"),
            },
            "punta": {
                "titulo": "Punta — voladizo frontal",
                "datos_entrada": [
                    {"nombre": "L (longitud de la puntera)",
                     "valor": Lp, "unidad": "m"},
                    {"nombre": "q<sub>puntera</sub> (presión sin mayorar)",
                     "valor": q_puntera, "unidad": "kPa"},
                    {"nombre": "q en cara del vástago (sin mayorar)",
                     "valor": q2_base, "unidad": "kPa"},
                    {"nombre": "Espesor de la zapata",
                     "valor": g.e_zapata, "unidad": "m"},
                    {"nombre": "Factores &gamma;<sub>H</sub> / &gamma;<sub>D</sub>",
                     "valor": gH, "unidad": "-"},
                ],
                "pasos_mu": [
                    {"nombre": "q mayorada en la puntera",
                     "formula": ("q<sub>1</sub> = &gamma;<sub>H</sub> "
                                 "&middot; q<sub>puntera</sub>"),
                     "detalle": f"{gH:.2f} &middot; {q_puntera:.2f}",
                     "valor": q1_p, "unidad": "kPa"},
                    {"nombre": "q mayorada en cara del vástago",
                     "formula": ("q<sub>2</sub> = &gamma;<sub>H</sub> "
                                 "&middot; q(x=b<sub>puntera</sub>)"),
                     "detalle": f"{gH:.2f} &middot; {q2_base:.2f}",
                     "valor": q2_p, "unidad": "kPa"},
                    {"nombre": "Peso propio de la zapata (mayorado)",
                     "formula": ("w<sub>pp</sub> = &gamma;<sub>D</sub> "
                                 "&middot; &gamma;<sub>c</sub> "
                                 "&middot; e<sub>zap</sub>"),
                     "detalle": (f"{gD:.2f} &middot; {gc:.2f} &middot; "
                                 f"{g.e_zapata:.2f}"),
                     "valor": w_propio_p, "unidad": "kPa"},
                    {"nombre": "Presión neta en la puntera",
                     "formula": ("q<sub>n1</sub> = q<sub>1</sub> "
                                 "&minus; w<sub>pp</sub>"),
                     "detalle": f"{q1_p:.2f} &minus; {w_propio_p:.2f}",
                     "valor": qn1_p, "unidad": "kPa"},
                    {"nombre": "Presión neta en cara del vástago",
                     "formula": ("q<sub>n2</sub> = q<sub>2</sub> "
                                 "&minus; w<sub>pp</sub>"),
                     "detalle": f"{q2_p:.2f} &minus; {w_propio_p:.2f}",
                     "valor": qn2_p, "unidad": "kPa"},
                    {"nombre": "Resultante del trapecio de presiones",
                     "formula": ("R = &frac12; &middot; (q<sub>n1</sub> + "
                                 "q<sub>n2</sub>) &middot; L"),
                     "detalle": (f"&frac12; &middot; ({qn1_p:.2f} + "
                                 f"{qn2_p:.2f}) &middot; {Lp:.2f}"),
                     "valor": Rp, "unidad": "kN/m"},
                    {"nombre": "Brazo al empotramiento (centroide trapecio)",
                     "formula": ("x&#772; = L &middot; (2&middot;q<sub>n1</sub> "
                                 "+ q<sub>n2</sub>) / "
                                 "[3&middot;(q<sub>n1</sub> + q<sub>n2</sub>)]"),
                     "detalle": "(trapecio con base mayor en la puntera)",
                     "valor": x_cg_p, "unidad": "m"},
                    {"nombre": "Momento último en cara del vástago",
                     "formula": "M<sub>u</sub> = R &middot; x&#772;",
                     "detalle": f"{Rp:.2f} &middot; {x_cg_p:.2f}",
                     "valor": Mu_p, "unidad": "kN·m/m"},
                ],
                "pasos_cuantia": _pasos_cuantia(reporte.punta.flexion),
                "espesor": g.e_zapata,
                "estado": ("CUMPLE"
                           if (reporte.punta.flexion.cumple and
                               reporte.punta.cortante.cumple)
                           else "REVISAR"),
            },
            "talon": {
                "titulo": "Talón — voladizo posterior",
                "datos_entrada": [
                    {"nombre": "L (longitud del talón)",
                     "valor": Lt, "unidad": "m"},
                    {"nombre": "Altura de suelo encima",
                     "valor": altura_suelo, "unidad": "m"},
                    {"nombre": "q en cara del vástago (sin mayorar)",
                     "valor": q_inicio, "unidad": "kPa"},
                    {"nombre": "q<sub>talón</sub> (sin mayorar)",
                     "valor": q_talon, "unidad": "kPa"},
                    {"nombre": "Espesor de la zapata",
                     "valor": g.e_zapata, "unidad": "m"},
                ],
                "pasos_mu": [
                    {"nombre": "Peso del suelo encima del talón",
                     "formula": ("w<sub>s</sub> = &gamma;<sub>D</sub> "
                                 "&middot; &gamma;<sub>s</sub> "
                                 "&middot; h<sub>suelo</sub>"),
                     "detalle": (f"{gD:.2f} &middot; {rel.gamma:.2f} "
                                 f"&middot; {altura_suelo:.2f}"),
                     "valor": w_suelo_t, "unidad": "kPa"},
                    {"nombre": "Peso propio de la zapata",
                     "formula": ("w<sub>pp</sub> = &gamma;<sub>D</sub> "
                                 "&middot; &gamma;<sub>c</sub> "
                                 "&middot; e<sub>zap</sub>"),
                     "detalle": (f"{gD:.2f} &middot; {gc:.2f} &middot; "
                                 f"{g.e_zapata:.2f}"),
                     "valor": w_propio_t, "unidad": "kPa"},
                    {"nombre": "Sobrecarga mayorada",
                     "formula": "w<sub>sc</sub> = 1.60 &middot; q<sub>sc</sub>",
                     "detalle": f"1.60 &middot; {cond.sobrecarga:.2f}",
                     "valor": w_sc_t, "unidad": "kPa"},
                    {"nombre": "Carga descendente total",
                     "formula": ("w<sub>tot</sub> = w<sub>s</sub> + "
                                 "w<sub>pp</sub> + w<sub>sc</sub>"),
                     "detalle": (f"{w_suelo_t:.2f} + {w_propio_t:.2f} + "
                                 f"{w_sc_t:.2f}"),
                     "valor": w_total_t, "unidad": "kPa"},
                    {"nombre": "q mayorada en cara del vástago",
                     "formula": ("q<sub>1</sub> = &gamma;<sub>H</sub> "
                                 "&middot; q(x=x<sub>fin-vást.</sub>)"),
                     "detalle": f"{gH:.2f} &middot; {q_inicio:.2f}",
                     "valor": q1_t, "unidad": "kPa"},
                    {"nombre": "q mayorada en el talón",
                     "formula": ("q<sub>2</sub> = &gamma;<sub>H</sub> "
                                 "&middot; q<sub>talón</sub>"),
                     "detalle": f"{gH:.2f} &middot; {q_talon:.2f}",
                     "valor": q2_t, "unidad": "kPa"},
                    {"nombre": "Presión neta en cara del vástago (↓)",
                     "formula": ("p<sub>1</sub> = w<sub>tot</sub> "
                                 "&minus; q<sub>1</sub>"),
                     "detalle": f"{w_total_t:.2f} &minus; {q1_t:.2f}",
                     "valor": p1_t, "unidad": "kPa"},
                    {"nombre": "Presión neta en el talón (↓)",
                     "formula": ("p<sub>2</sub> = w<sub>tot</sub> "
                                 "&minus; q<sub>2</sub>"),
                     "detalle": f"{w_total_t:.2f} &minus; {q2_t:.2f}",
                     "valor": p2_t, "unidad": "kPa"},
                    {"nombre": "Resultante del trapecio",
                     "formula": ("R = &frac12; &middot; (p<sub>1</sub> + "
                                 "p<sub>2</sub>) &middot; L"),
                     "detalle": (f"&frac12; &middot; ({p1_t:.2f} + "
                                 f"{p2_t:.2f}) &middot; {Lt:.2f}"),
                     "valor": Rt, "unidad": "kN/m"},
                    {"nombre": "Brazo al empotramiento",
                     "formula": ("x&#772; = L &middot; (p<sub>1</sub> + "
                                 "2&middot;p<sub>2</sub>) / "
                                 "[3&middot;(p<sub>1</sub> + p<sub>2</sub>)]"),
                     "detalle": "(trapecio con base mayor en el talón)",
                     "valor": x_cg_t, "unidad": "m"},
                    {"nombre": "Momento último en cara del vástago",
                     "formula": "M<sub>u</sub> = |R &middot; x&#772;|",
                     "detalle": f"|{Rt:.2f} &middot; {x_cg_t:.2f}|",
                     "valor": Mu_t, "unidad": "kN·m/m"},
                ],
                "pasos_cuantia": _pasos_cuantia(reporte.talon.flexion),
                "espesor": g.e_zapata,
                "estado": ("CUMPLE"
                           if (reporte.talon.flexion.cumple and
                               reporte.talon.cortante.cumple)
                           else "REVISAR"),
            },
        }

    # ==================================================================
    # DISEÑO COMPLETO
    # ==================================================================
    def disenar(self, q_puntera: float, q_talon: float) -> ReporteDiseno:
        """Ejecuta el diseño de todos los elementos.

        Args:
            q_puntera: Presión máxima bajo la zapata (kPa, característica).
            q_talon:   Presión mínima bajo la zapata (kPa, característica).
        """
        return ReporteDiseno(
            vastago=self.disenar_vastago(),
            punta=self.disenar_punta(q_puntera, q_talon),
            talon=self.disenar_talon(q_puntera, q_talon),
        )
