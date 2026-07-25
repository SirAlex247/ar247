"""
Cálculos de propiedades geotécnicas derivadas.

Incluye:
    - Factores de capacidad de carga (Meyerhof / Vesic).
    - Factores de profundidad, forma e inclinación de la carga (Hansen/Vesic).
    - Cálculo de capacidad de carga última de cimentaciones superficiales.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from ..utils.validaciones import validar_angulo_friccion, validar_positivo


# =============================================================================
# Factores Nc, Nq, Nγ
# =============================================================================
@dataclass(frozen=True)
class FactoresCapacidadCarga:
    """Agrupa los factores de capacidad de carga Nc, Nq, Nγ."""
    Nc: float
    Nq: float
    Ngamma: float


class PropiedadesSuelo:
    """Funciones estáticas de mecánica de suelos para el diseño de muros."""

    # ------------------------------------------------------------------
    # Factores de capacidad de carga
    # ------------------------------------------------------------------
    @staticmethod
    def factores_capacidad_carga(
        phi_grados: float,
        metodo: str = "vesic",
    ) -> FactoresCapacidadCarga:
        """Calcula Nc, Nq y Nγ.

        Args:
            phi_grados: Ángulo de fricción interna (grados).
            metodo: Expresión a utilizar para Nγ:
                - ``"vesic"``:    Nγ = 2(Nq + 1) tan φ  (recomendado por Das).
                - ``"meyerhof"``: Nγ = (Nq − 1) tan(1.4 φ).
                - ``"hansen"``:   Nγ = 1.5 (Nq − 1) tan φ.

        Returns:
            ``FactoresCapacidadCarga`` con Nc, Nq, Nγ.
        """
        validar_angulo_friccion(phi_grados)
        phi = math.radians(phi_grados)

        Nq = math.exp(math.pi * math.tan(phi)) * math.tan(math.pi / 4 + phi / 2) ** 2
        if phi_grados == 0:
            Nc = math.pi + 2.0
        else:
            Nc = (Nq - 1.0) / math.tan(phi)

        metodo = metodo.lower()
        if metodo == "vesic":
            N_gamma = 2.0 * (Nq + 1.0) * math.tan(phi)
        elif metodo == "meyerhof":
            N_gamma = (Nq - 1.0) * math.tan(math.radians(1.4 * phi_grados))
        elif metodo == "hansen":
            N_gamma = 1.5 * (Nq - 1.0) * math.tan(phi)
        else:
            raise ValueError(f"Método '{metodo}' no reconocido.")

        return FactoresCapacidadCarga(Nc=Nc, Nq=Nq, Ngamma=N_gamma)

    # ------------------------------------------------------------------
    # Factores de profundidad (Hansen)
    # ------------------------------------------------------------------
    @staticmethod
    def factores_profundidad(
        phi_grados: float,
        D: float,
        B_efectivo: float,
    ) -> tuple[float, float, float]:
        """Factores de profundidad Fcd, Fqd, Fγd según Hansen (1970).

        Args:
            phi_grados: φ en grados.
            D: Profundidad de desplante (m).
            B_efectivo: Ancho efectivo B' = B − 2e (m).

        Returns:
            (Fcd, Fqd, Fγd).
        """
        validar_positivo(B_efectivo, "B_efectivo")
        phi = math.radians(phi_grados)
        k = D / B_efectivo if D / B_efectivo <= 1.0 else math.atan(D / B_efectivo)

        Fqd = 1.0 + 2.0 * math.tan(phi) * (1.0 - math.sin(phi)) ** 2 * k
        if phi_grados == 0:
            Fcd = 1.0 + 0.4 * k
        else:
            Fcd = Fqd - (1.0 - Fqd) / (PropiedadesSuelo.factores_capacidad_carga(
                phi_grados).Nc * math.tan(phi))
        Fgd = 1.0
        return Fcd, Fqd, Fgd

    # ------------------------------------------------------------------
    # Factores de inclinación de carga (Meyerhof/Hansen)
    # ------------------------------------------------------------------
    @staticmethod
    def factores_inclinacion(
        psi_grados: float,
        phi_grados: float,
    ) -> tuple[float, float, float]:
        """Factores de inclinación Fci, Fqi, Fγi.

        Args:
            psi_grados: Ángulo ψ = atan(Ph / ΣV), en grados.
            phi_grados: φ del suelo, en grados.

        Returns:
            (Fci, Fqi, Fγi).
        """
        Fci = Fqi = (1.0 - psi_grados / 90.0) ** 2
        ratio = psi_grados / phi_grados if phi_grados > 0 else 1.0
        Fgi = max(0.0, (1.0 - ratio) ** 2)
        return Fci, Fqi, Fgi

    # ------------------------------------------------------------------
    # Capacidad de carga última (Meyerhof generalizado)
    # ------------------------------------------------------------------
    @staticmethod
    def capacidad_carga_ultima(
        c: float,
        phi_grados: float,
        gamma: float,
        D: float,
        B_efectivo: float,
        Ph: float,
        V: float,
        metodo_Ng: str = "vesic",
    ) -> dict[str, float]:
        """Capacidad de carga última ``qu`` para cimentación corrida.

        qu = c'·Nc·Fcd·Fci + q·Nq·Fqd·Fqi + 0.5·γ·B'·Nγ·Fγd·Fγi

        donde q = γ·D.

        Args:
            c: Cohesión del suelo de apoyo (kPa).
            phi_grados: Ángulo de fricción (°).
            gamma: Peso específico (kN/m³).
            D: Profundidad de desplante (m).
            B_efectivo: Ancho efectivo (m).
            Ph: Componente horizontal de la fuerza resultante (kN/m).
            V: Suma vertical ΣV (kN/m).
            metodo_Ng: Método para Nγ.

        Returns:
            Diccionario con todos los factores y el ``qu`` (kPa).
        """
        factores = PropiedadesSuelo.factores_capacidad_carga(phi_grados, metodo_Ng)
        Fcd, Fqd, Fgd = PropiedadesSuelo.factores_profundidad(phi_grados, D, B_efectivo)
        psi = math.degrees(math.atan(Ph / V)) if V > 0 else 0.0
        Fci, Fqi, Fgi = PropiedadesSuelo.factores_inclinacion(psi, phi_grados)

        q = gamma * D
        qu = (
            c * factores.Nc * Fcd * Fci
            + q * factores.Nq * Fqd * Fqi
            + 0.5 * gamma * B_efectivo * factores.Ngamma * Fgd * Fgi
        )

        return {
            "qu": qu,
            "Nc": factores.Nc, "Nq": factores.Nq, "Ngamma": factores.Ngamma,
            "Fcd": Fcd, "Fqd": Fqd, "Fgd": Fgd,
            "Fci": Fci, "Fqi": Fqi, "Fgi": Fgi,
            "psi_grados": psi,
            "q_sobrecarga": q,
        }
