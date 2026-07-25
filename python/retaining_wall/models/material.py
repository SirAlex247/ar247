"""
Modelos de datos de materiales estructurales conforme a NSR-10.

Incluye:
    - Concreto estructural (NSR-10 Título C, Capítulo C.8)
    - Acero de refuerzo (NSR-10 C.3.5)
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import ClassVar

from ..utils.validaciones import (
    MaterialInvalidoError,
    validar_fc,
    validar_fy,
    validar_positivo,
)


@dataclass(frozen=True)
class Concreto:
    """Propiedades del concreto estructural según NSR-10.

    Attributes:
        fc: Resistencia especificada a compresión a los 28 días, en MPa.
        gamma: Peso específico, en kN/m³ (por defecto concreto reforzado normal).
        lambda_factor: Factor de modificación por peso del concreto (NSR-10 C.8.6.1).
            1.00 para concreto normal; 0.75 para concreto liviano total.
    """

    fc: float                       # MPa
    gamma: float = 24.0             # kN/m³  (NSR-10 B.3.2, concreto reforzado normal)
    lambda_factor: float = 1.0

    # --- Constantes NSR-10 ---
    CONCRETO_SIMPLE_GAMMA: ClassVar[float] = 23.0   # kN/m³
    CONCRETO_REFORZADO_GAMMA: ClassVar[float] = 24.0

    def __post_init__(self) -> None:
        validar_fc(self.fc)
        validar_positivo(self.gamma, "gamma_concreto")
        if not (0.75 <= self.lambda_factor <= 1.0):
            raise MaterialInvalidoError(
                f"lambda_factor debe estar en [0.75, 1.0], recibido: {self.lambda_factor}"
            )

    # ------------------------------------------------------------------
    # Propiedades derivadas
    # ------------------------------------------------------------------
    @property
    def Ec(self) -> float:
        """Módulo de elasticidad del concreto (MPa) según NSR-10 C.8.5.1.

        Ec = 4700 · √(f'c)  para concreto de peso normal.
        """
        return 4700.0 * math.sqrt(self.fc)

    @property
    def fr(self) -> float:
        """Módulo de rotura (MPa) según NSR-10 C.9.5.2.3.

        fr = 0.62 · λ · √(f'c)
        """
        return 0.62 * self.lambda_factor * math.sqrt(self.fc)

    @property
    def beta1(self) -> float:
        """Factor β₁ del bloque equivalente de Whitney (NSR-10 C.10.2.7.3)."""
        if self.fc <= 28.0:
            return 0.85
        return max(0.65, 0.85 - 0.05 * (self.fc - 28.0) / 7.0)

    def __repr__(self) -> str:
        return f"Concreto(f'c={self.fc} MPa, γ={self.gamma} kN/m³)"


@dataclass(frozen=True)
class AceroRefuerzo:
    """Propiedades del acero de refuerzo corrugado según NSR-10.

    Attributes:
        fy: Esfuerzo de fluencia especificado, en MPa (usualmente 420 MPa).
        Es: Módulo de elasticidad, en MPa (NSR-10 C.8.5.2 = 200 000 MPa).
    """

    fy: float                       # MPa
    Es: float = 200_000.0           # MPa  (NSR-10 C.8.5.2)

    def __post_init__(self) -> None:
        validar_fy(self.fy)
        validar_positivo(self.Es, "Es")

    @property
    def epsilon_y(self) -> float:
        """Deformación unitaria de fluencia εy = fy/Es."""
        return self.fy / self.Es

    def __repr__(self) -> str:
        return f"AceroRefuerzo(fy={self.fy} MPa)"


# =============================================================================
# Fábricas de materiales comunes en Colombia (NSR-10)
# =============================================================================
class MaterialesComunes:
    """Catálogo de materiales típicos en el medio colombiano."""

    @staticmethod
    def concreto_21() -> Concreto:
        """Concreto f'c = 21 MPa (uso común para muros)."""
        return Concreto(fc=21.0)

    @staticmethod
    def concreto_28() -> Concreto:
        """Concreto f'c = 28 MPa."""
        return Concreto(fc=28.0)

    @staticmethod
    def concreto_35() -> Concreto:
        """Concreto f'c = 35 MPa."""
        return Concreto(fc=35.0)

    @staticmethod
    def acero_420() -> AceroRefuerzo:
        """Acero corrugado fy = 420 MPa (denominación NSR-10)."""
        return AceroRefuerzo(fy=420.0)
