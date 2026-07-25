"""Modelo de datos para el módulo de pilotes.

Pilote de concreto vaciado in situ (perforado), de sección circular, apoyado
en un perfil de suelo estratificado. La metodología de capacidad de carga
sigue "Diseño de Pilotes" (Ing. W. Rodríguez Serquén) y Braja Das
(Fundamentos de Ingeniería de Cimentaciones):

    Q_límite = Q_punta + Q_fuste
        Arenas:   Q_p = σ'v·Nq·A_b      f = K·σ'v·tanδ
        Arcillas: Q_p = 9·c_u·A_b        f = α·c_u
    Q_adm = Q_límite / FS

Unidades internas (coherentes con el resto de la app):
    longitudes [m], pesos unitarios γ [kN/m³], esfuerzos/cohesión [kPa],
    cargas [kN], f'c y fy [MPa], diámetros de barra [mm].
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

GAMMA_W = 9.81  # peso unitario del agua, kN/m³


@dataclass
class EstratoSuelo:
    """Un estrato del perfil de suelo que atraviesa el pilote.

    Attributes:
        tipo:      'arena' o 'arcilla'.
        espesor:   espesor del estrato (m).
        gamma:     peso unitario total húmedo (kN/m³).
        gamma_sat: peso unitario saturado (kN/m³); si None se usa ``gamma``.
        phi:       ángulo de fricción interna (°) — para arenas.
        cu:        resistencia al corte no drenada (kPa) — para arcillas.
        nombre:    etiqueta opcional.
    """
    tipo: str
    espesor: float
    gamma: float
    gamma_sat: float | None = None
    phi: float = 0.0
    cu: float = 0.0
    nombre: str = ""

    def __post_init__(self) -> None:
        self.tipo = (self.tipo or "").strip().lower()
        if self.tipo not in ("arena", "arcilla"):
            raise ValueError(
                f"tipo de estrato inválido: {self.tipo!r} (use 'arena' o 'arcilla')")
        if self.espesor <= 0:
            raise ValueError("El espesor del estrato debe ser > 0.")
        if self.gamma <= 0:
            raise ValueError("El peso unitario γ debe ser > 0.")
        if self.tipo == "arena" and self.phi <= 0:
            raise ValueError("Una arena requiere φ > 0.")
        if self.tipo == "arcilla" and self.cu <= 0:
            raise ValueError("Una arcilla requiere c_u > 0.")

    @property
    def gamma_ef(self) -> float:
        """Peso unitario efectivo (saturado − agua), para tramos bajo el N.F."""
        gs = self.gamma_sat if self.gamma_sat else self.gamma
        return gs - GAMMA_W


@dataclass
class PerfilSuelo:
    """Perfil de suelo estratificado y posición del nivel freático.

    Attributes:
        estratos:        lista de EstratoSuelo de arriba hacia abajo.
        nivel_freatico:  profundidad del N.F. desde la superficie (m).
                         None = sin nivel freático (suelo seco/húmedo).
    """
    estratos: list[EstratoSuelo] = field(default_factory=list)
    nivel_freatico: float | None = None

    def __post_init__(self) -> None:
        if not self.estratos:
            raise ValueError("El perfil debe tener al menos un estrato.")

    @property
    def profundidad_total(self) -> float:
        return sum(e.espesor for e in self.estratos)

    def estrato_en(self, z: float) -> EstratoSuelo:
        """Devuelve el estrato que contiene la profundidad z (m)."""
        prof = 0.0
        for e in self.estratos:
            prof += e.espesor
            if z <= prof + 1e-9:
                return e
        return self.estratos[-1]

    def sigma_v_efectivo(self, z: float) -> float:
        """Esfuerzo vertical EFECTIVO σ'v a la profundidad z (kPa).

        Acumula γ·Δz por estrato, usando peso efectivo (γ_sat − γ_w) en los
        tramos situados por debajo del nivel freático.
        """
        if z <= 0:
            return 0.0
        nf = self.nivel_freatico
        sigma = 0.0
        prof = 0.0
        for e in self.estratos:
            top, bot = prof, prof + e.espesor
            if z <= top:
                break
            dz = min(z, bot) - top          # tramo de este estrato hasta z
            if nf is None or top >= 1e18:    # sin N.F.
                sigma += e.gamma * dz
            else:
                if top >= nf:                # todo el tramo bajo el N.F.
                    sigma += e.gamma_ef * dz
                elif bot <= nf or top + dz <= nf:  # todo el tramo sobre el N.F.
                    sigma += e.gamma * dz
                else:                        # el tramo cruza el N.F.
                    d_arriba = nf - top
                    d_abajo = dz - d_arriba
                    sigma += e.gamma * d_arriba + e.gamma_ef * d_abajo
            prof = bot
        return sigma


@dataclass
class PiloteConcreto:
    """Pilote de concreto circular vaciado in situ.

    Attributes:
        D:             diámetro (m).
        L:             longitud / profundidad de empotramiento (m).
        fc:            resistencia del concreto f'c (MPa).
        fy:            fluencia del acero (MPa).
        n_barras:      número de barras longitudinales.
        db_long:       diámetro de la barra longitudinal (mm).
        tipo_refuerzo: 'espiral' o 'estribo' (zuncho o estribos).
        db_trans:      diámetro del refuerzo transversal (mm).
        recubrimiento: recubrimiento libre al refuerzo (m).
    """
    D: float
    L: float
    fc: float = 21.0
    fy: float = 420.0
    n_barras: int = 6
    db_long: float = 19.05      # #6 (3/4")
    tipo_refuerzo: str = "espiral"
    db_trans: float = 9.53      # #3 (3/8")
    recubrimiento: float = 0.075

    def __post_init__(self) -> None:
        self.tipo_refuerzo = (self.tipo_refuerzo or "espiral").strip().lower()
        if self.D <= 0 or self.L <= 0:
            raise ValueError("D y L deben ser > 0.")
        if self.fc <= 0 or self.fy <= 0:
            raise ValueError("f'c y fy deben ser > 0.")
        if self.n_barras < 4:
            raise ValueError("Use al menos 4 barras longitudinales.")

    @property
    def area(self) -> float:
        """Área bruta de la sección, A_g (m²)."""
        return math.pi * self.D ** 2 / 4.0

    @property
    def perimetro(self) -> float:
        """Perímetro del fuste, a_s (m)."""
        return math.pi * self.D

    @property
    def Ast(self) -> float:
        """Área total del acero longitudinal (m²)."""
        return self.n_barras * math.pi * (self.db_long / 1000.0) ** 2 / 4.0

    @property
    def cuantia(self) -> float:
        """Cuantía longitudinal ρ = A_st / A_g."""
        return self.Ast / self.area

    @property
    def diametro_nucleo(self) -> float:
        """Diámetro del núcleo confinado (m), de centro a centro del zuncho."""
        return self.D - 2.0 * self.recubrimiento

    @property
    def area_nucleo(self) -> float:
        """Área del núcleo confinado A_ch (m²)."""
        return math.pi * self.diametro_nucleo ** 2 / 4.0
