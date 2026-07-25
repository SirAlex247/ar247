"""
Modelo de datos para estratos de suelo (relleno y cimentación).
"""

from __future__ import annotations

from dataclasses import dataclass

from ..utils.validaciones import (
    validar_angulo_friccion,
    validar_cohesion,
    validar_peso_especifico,
)


@dataclass(frozen=True)
class Suelo:
    """Representa las propiedades geotécnicas de un suelo.

    Atributos almacenados siempre en unidades SI internas:
        gamma:    Peso específico en kN/m³.
        phi:      Ángulo de fricción interna efectivo en grados.
        cohesion: Cohesión efectiva c' en kPa (kN/m²).
        nombre:   Identificador legible (p.ej. "relleno", "cimentación").
        delta_wall: Ángulo de fricción suelo-muro, en grados (para Coulomb).
                    Si se deja en None se adopta (2/3)·φ.

    Example:
        >>> relleno = Suelo(gamma=18.0, phi=30.0, cohesion=0.0, nombre="Relleno")
    """

    gamma: float
    phi: float
    cohesion: float = 0.0
    nombre: str = "suelo"
    delta_wall: float | None = None

    def __post_init__(self) -> None:
        validar_peso_especifico(self.gamma, "gamma")
        validar_angulo_friccion(self.phi, "phi")
        validar_cohesion(self.cohesion, "cohesion")
        if self.delta_wall is not None:
            if not (0.0 <= self.delta_wall <= self.phi):
                raise ValueError(
                    f"delta_wall ({self.delta_wall}°) debe estar en [0°, phi={self.phi}°]"
                )

    # ------------------------------------------------------------------
    @property
    def delta_efectivo(self) -> float:
        """Ángulo de fricción muro-suelo efectivo (grados).

        Devuelve δ especificado, o por defecto (2/3)·φ como recomienda la
        literatura (Das, "Principios de Ingeniería de Cimentaciones").
        """
        return self.delta_wall if self.delta_wall is not None else (2.0 / 3.0) * self.phi

    @property
    def es_granular(self) -> bool:
        """True si la cohesión es nula (suelo granular)."""
        return self.cohesion == 0.0

    def __repr__(self) -> str:
        return (
            f"Suelo({self.nombre}: γ={self.gamma} kN/m³, "
            f"φ={self.phi}°, c'={self.cohesion} kPa)"
        )
