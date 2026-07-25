"""
Cálculo de presiones laterales de tierra sobre muros de contención.

Métodos implementados:
    - Rankine (activo y pasivo) con relleno inclinado.
    - Coulomb (activo) con fricción muro-suelo y muro inclinado.
    - Mononobe-Okabe para condición sísmica (pseudoestática).
    - Empuje por sobrecarga uniforme.

Todas las fuerzas se entregan POR METRO LINEAL de muro (kN/m) y actúan a
través del centroide del diagrama de presión.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from ..utils.validaciones import (
    ParametroSueloInvalidoError,
    validar_angulo_friccion,
    validar_angulo_talud,
    validar_positivo,
    validar_rango,
)


# =============================================================================
# Resultado: empuje y su línea de acción
# =============================================================================
@dataclass(frozen=True)
class Empuje:
    """Resultado de un cálculo de empuje.

    Attributes:
        magnitud:  Magnitud total del empuje (kN/m de muro).
        componente_h: Componente horizontal (kN/m).
        componente_v: Componente vertical (kN/m).
        y_aplicacion: Altura del punto de aplicación medida desde la base de
            la zapata (m).
        coeficiente:  Coeficiente adimensional empleado (Ka, Kp, Kae, etc.).
        metodo:       Nombre del método utilizado.
    """

    magnitud: float
    componente_h: float
    componente_v: float
    y_aplicacion: float
    coeficiente: float
    metodo: str


# =============================================================================
# Calculador principal
# =============================================================================
class EmpujeSuelo:
    """Calculadora de empujes laterales de tierra."""

    # ------------------------------------------------------------------
    # Coeficientes de presión
    # ------------------------------------------------------------------
    @staticmethod
    def calcular_ka_rankine(phi_grados: float, alpha_grados: float = 0.0) -> float:
        """Coeficiente de presión activa de Rankine con relleno inclinado.

        .. math::
            K_a = \\cos\\alpha \\cdot
                  \\frac{\\cos\\alpha - \\sqrt{\\cos^2\\alpha - \\cos^2\\varphi}}
                        {\\cos\\alpha + \\sqrt{\\cos^2\\alpha - \\cos^2\\varphi}}

        Args:
            phi_grados: Ángulo de fricción interna (°).
            alpha_grados: Inclinación del relleno (°), debe ser menor que φ.

        Returns:
            Ka adimensional.

        Raises:
            ParametroSueloInvalidoError: Si α >= φ.
        """
        validar_angulo_friccion(phi_grados)
        validar_angulo_talud(alpha_grados, phi_grados)

        phi = math.radians(phi_grados)
        alpha = math.radians(alpha_grados)

        if alpha_grados == 0.0:
            return math.tan(math.pi / 4 - phi / 2) ** 2

        cos_a = math.cos(alpha)
        cos_p = math.cos(phi)
        raiz = math.sqrt(cos_a ** 2 - cos_p ** 2)
        return cos_a * (cos_a - raiz) / (cos_a + raiz)

    @staticmethod
    def calcular_kp_rankine(phi_grados: float) -> float:
        """Coeficiente de presión pasiva de Rankine (relleno horizontal).

        Kp = tan²(45° + φ/2)
        """
        validar_angulo_friccion(phi_grados)
        phi = math.radians(phi_grados)
        return math.tan(math.pi / 4 + phi / 2) ** 2

    @staticmethod
    def calcular_ka_coulomb(
        phi_grados: float,
        delta_grados: float,
        beta_grados: float = 90.0,
        alpha_grados: float = 0.0,
    ) -> float:
        """Coeficiente activo de Coulomb.

        Args:
            phi_grados: Ángulo de fricción del suelo (°).
            delta_grados: Ángulo de fricción muro-suelo δ (°).
            beta_grados: Ángulo entre la cara posterior del muro y la
                horizontal (°). 90° = muro vertical.
            alpha_grados: Inclinación del relleno (°).

        Returns:
            Ka (Coulomb) adimensional.
        """
        validar_angulo_friccion(phi_grados)
        validar_rango(delta_grados, 0.0, phi_grados, "delta")
        validar_rango(beta_grados, 60.0, 120.0, "beta")
        validar_rango(alpha_grados, 0.0, phi_grados - 0.001, "alpha", inclusivo=True)

        phi = math.radians(phi_grados)
        delta = math.radians(delta_grados)
        beta = math.radians(beta_grados)
        alpha = math.radians(alpha_grados)

        numerador = math.sin(beta + phi) ** 2

        aux = math.sin(phi + delta) * math.sin(phi - alpha) / (
            math.sin(beta - delta) * math.sin(beta + alpha)
        )
        denominador = (
            math.sin(beta) ** 2
            * math.sin(beta - delta)
            * (1.0 + math.sqrt(aux)) ** 2
        )
        return numerador / denominador

    # ------------------------------------------------------------------
    # Mononobe-Okabe (empuje activo sísmico)
    # ------------------------------------------------------------------
    @staticmethod
    def calcular_kae_mononobe_okabe(
        phi_grados: float,
        delta_grados: float,
        beta_grados: float,
        alpha_grados: float,
        kh: float,
        kv: float,
    ) -> float:
        """Coeficiente de empuje activo sísmico (Mononobe-Okabe).

        Args:
            phi_grados: φ (°).
            delta_grados: δ (°).
            beta_grados: Inclinación cara posterior (°).
            alpha_grados: Inclinación del relleno (°).
            kh: Coeficiente sísmico horizontal.
            kv: Coeficiente sísmico vertical.

        Returns:
            Kae adimensional.
        """
        if kh < 0 or kv < 0:
            raise ValueError("kh y kv deben ser >= 0.")
        theta = math.atan(kh / (1.0 - kv))
        theta_grados = math.degrees(theta)

        if phi_grados - alpha_grados - theta_grados < 0:
            raise ParametroSueloInvalidoError(
                "Kae indefinido: (φ - α - θ) debe ser positivo."
            )

        phi = math.radians(phi_grados)
        delta = math.radians(delta_grados)
        beta = math.radians(beta_grados)
        alpha = math.radians(alpha_grados)

        numerador = math.cos(phi - theta - (math.pi / 2 - beta)) ** 2

        aux = (
            math.sin(phi + delta) * math.sin(phi - theta - alpha)
            / (math.cos(theta + (math.pi / 2 - beta) + delta)
               * math.cos(alpha - (math.pi / 2 - beta)))
        )
        denominador = (
            math.cos(theta) * math.cos(math.pi / 2 - beta) ** 2
            * math.cos(theta + (math.pi / 2 - beta) + delta)
            * (1.0 + math.sqrt(max(aux, 0.0))) ** 2
        )
        return numerador / denominador

    # ------------------------------------------------------------------
    # Empujes (fuerzas)
    # ------------------------------------------------------------------
    @staticmethod
    def calcular_empuje_activo_rankine(
        gamma: float,
        H: float,
        phi_grados: float,
        alpha_grados: float = 0.0,
        cohesion: float = 0.0,
    ) -> Empuje:
        """Fuerza activa de Rankine (kN/m) y su punto de aplicación.

        Para relleno con cohesión c' > 0 se aplica la fórmula completa de
        Rankine con grieta de tracción:

        .. math::
            \\sigma_a' = \\gamma z K_a - 2c'\\sqrt{K_a}

        La integración entre 0 y H da:

        .. math::
            P_a = \\tfrac{1}{2}\\gamma H^2 K_a - 2c'H\\sqrt{K_a}

        En el caso c'=0 la expresión se reduce a la triangular típica.

        Args:
            gamma: Peso específico del relleno (kN/m³).
            H: Altura sobre la que actúa el empuje (m). Debe ser H' si α > 0.
            phi_grados: φ del relleno (°).
            alpha_grados: Inclinación del relleno (°).
            cohesion: c' del relleno (kPa). Por defecto 0 (suelo granular).

        Returns:
            ``Empuje`` con magnitud, componentes y línea de acción.
        """
        validar_positivo(H, "H")
        Ka = EmpujeSuelo.calcular_ka_rankine(phi_grados, alpha_grados)
        # Fórmula con cohesión (Eq. 7.10 Braja Das). Si la fuerza neta resulta
        # negativa por mucha cohesión + poca H, se acota a 0 (no hay empuje
        # neto contra el muro).
        Pa = 0.5 * gamma * H ** 2 * Ka - 2.0 * cohesion * H * math.sqrt(Ka)
        Pa = max(0.0, Pa)
        alpha_rad = math.radians(alpha_grados)
        Ph = Pa * math.cos(alpha_rad)
        Pv = Pa * math.sin(alpha_rad)
        return Empuje(
            magnitud=Pa,
            componente_h=Ph,
            componente_v=Pv,
            y_aplicacion=H / 3.0,
            coeficiente=Ka,
            metodo="Rankine activo",
        )

    @staticmethod
    def calcular_empuje_pasivo_rankine(
        gamma: float,
        H: float,
        phi_grados: float,
        cohesion: float = 0.0,
    ) -> Empuje:
        """Fuerza pasiva de Rankine (kN/m).

        .. math::
            P_p = \\tfrac{1}{2} K_p \\gamma H^2 + 2 c' \\sqrt{K_p}\\, H
        """
        validar_positivo(H, "H")
        Kp = EmpujeSuelo.calcular_kp_rankine(phi_grados)
        Pp = 0.5 * Kp * gamma * H ** 2 + 2.0 * cohesion * math.sqrt(Kp) * H
        # Posición resultante (aprox. tercio para componente triangular;
        # se toma y = H/3 como simplificación habitual en diseño)
        return Empuje(
            magnitud=Pp,
            componente_h=Pp,
            componente_v=0.0,
            y_aplicacion=H / 3.0,
            coeficiente=Kp,
            metodo="Rankine pasivo",
        )

    @staticmethod
    def calcular_empuje_activo_coulomb(
        gamma: float,
        H: float,
        phi_grados: float,
        delta_grados: float,
        beta_grados: float = 90.0,
        alpha_grados: float = 0.0,
    ) -> Empuje:
        """Fuerza activa de Coulomb (kN/m).

        En la teoría de Coulomb, Pa actúa con un ángulo δ respecto a la
        NORMAL de la cara posterior del muro. Si la cara posterior está
        inclinada (β ≠ 90°), la cara forma un ángulo (90° − β) con la
        vertical, y por tanto Pa forma un ángulo total respecto a la
        horizontal de:

            θ = (90° − β) + δ                 (β medido desde la horizontal)

        Esto es lo que reporta Braja Das en el Ej. 8.2: β=75°, δ=21.33°
        → θ = 15° + 21.33° = 36.33°  → Ph = Pa·cos(36.33°), Pv = Pa·sen(36.33°).

        El parámetro α (inclinación del relleno) afecta a Ka pero NO al
        ángulo de aplicación de la fuerza respecto al muro — la fuerza
        sigue siendo perpendicular a la cara más δ.
        """
        validar_positivo(H, "H")
        Ka = EmpujeSuelo.calcular_ka_coulomb(phi_grados, delta_grados,
                                             beta_grados, alpha_grados)
        Pa = 0.5 * gamma * H ** 2 * Ka

        # Ángulo con la horizontal: (90° − β) inclinación de la cara, + δ
        # rotación adicional por la fricción suelo-muro.
        angulo = math.radians((90.0 - beta_grados) + delta_grados)
        Ph = Pa * math.cos(angulo)
        Pv = Pa * math.sin(angulo)
        return Empuje(
            magnitud=Pa,
            componente_h=Ph,
            componente_v=Pv,
            y_aplicacion=H / 3.0,
            coeficiente=Ka,
            metodo="Coulomb activo",
        )

    @staticmethod
    def calcular_empuje_sismico(
        gamma: float,
        H: float,
        phi_grados: float,
        delta_grados: float,
        beta_grados: float,
        alpha_grados: float,
        kh: float,
        kv: float = 0.0,
    ) -> Empuje:
        """Fuerza activa sísmica por Mononobe-Okabe (kN/m).

        El punto de aplicación recomendado es a 0.6·H desde la base
        (Seed-Whitman) para la porción de incremento sísmico; aquí se
        retorna la resultante total aplicada a y = H/2 como aproximación
        conservadora para diseño simplificado.
        """
        validar_positivo(H, "H")
        Kae = EmpujeSuelo.calcular_kae_mononobe_okabe(
            phi_grados, delta_grados, beta_grados, alpha_grados, kh, kv
        )
        Pae = 0.5 * gamma * H ** 2 * (1.0 - kv) * Kae
        angulo = math.radians(delta_grados + alpha_grados)
        Ph = Pae * math.cos(angulo)
        Pv = Pae * math.sin(angulo)
        return Empuje(
            magnitud=Pae,
            componente_h=Ph,
            componente_v=Pv,
            y_aplicacion=H / 2.0,
            coeficiente=Kae,
            metodo="Mononobe-Okabe",
        )

    # ------------------------------------------------------------------
    # Empuje por sobrecarga uniforme sobre el relleno
    # ------------------------------------------------------------------
    @staticmethod
    def calcular_empuje_sobrecarga(
        q: float,
        H: float,
        phi_grados: float,
        alpha_grados: float = 0.0,
    ) -> Empuje:
        """Empuje por sobrecarga uniforme q (kPa) sobre el relleno.

        P_sc = Ka · q · H   actuando a y = H/2 (distribución rectangular).
        """
        validar_positivo(q, "q", permitir_cero=True)
        validar_positivo(H, "H")
        Ka = EmpujeSuelo.calcular_ka_rankine(phi_grados, alpha_grados)
        P = Ka * q * H
        alpha_rad = math.radians(alpha_grados)
        Ph = P * math.cos(alpha_rad)
        Pv = P * math.sin(alpha_rad)
        return Empuje(
            magnitud=P,
            componente_h=Ph,
            componente_v=Pv,
            y_aplicacion=H / 2.0,
            coeficiente=Ka,
            metodo="Sobrecarga uniforme",
        )


# =============================================================================
# Ejemplo de uso
# =============================================================================
if __name__ == "__main__":
    Ka = EmpujeSuelo.calcular_ka_rankine(30.0, 10.0)
    # Fórmula cerrada de Rankine con talud (φ=30°, α=10°) = 0.3495.
    # (El valor 0.3532 que a veces se cita proviene de tablas con otra
    #  aproximación; la fórmula exacta implementada aquí da 0.3495.)
    print(f"Ka (φ=30°, α=10°) = {Ka:.4f}")   # esperado 0.3495

    e = EmpujeSuelo.calcular_empuje_activo_rankine(
        gamma=18.0, H=7.158, phi_grados=30.0, alpha_grados=10.0
    )
    print(f"Pa = {e.magnitud:.2f} kN/m, Ph = {e.componente_h:.2f}, Pv = {e.componente_v:.2f}")
