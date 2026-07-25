"""Modelo del muro de gravedad (entidad raíz)."""
from __future__ import annotations

from dataclasses import dataclass, field

from .geometria_gravedad import GeometriaMuroGravedad
from .material import AceroRefuerzo, Concreto
from .muro import CondicionesCarga, TipoMuro
from .suelo import Suelo


@dataclass
class MuroGravedad:
    """Muro de retención de gravedad (cuerpo trapezoidal macizo).

    A diferencia del muro voladizo, no resiste por flexión sino por su
    propio peso. Comparte con el voladizo:
        - Modelos de suelo (relleno + cimentación)
        - Modelos de materiales (concreto + acero — el acero es para casos
          de gravedad armada, opcional)
        - Condiciones de carga (sobrecarga, sismo, inclinación del relleno)
        - Sistema de verificación de estabilidad
    """

    geometria: GeometriaMuroGravedad
    suelo_relleno: Suelo
    suelo_cimentacion: Suelo
    concreto: Concreto
    acero: AceroRefuerzo
    condiciones: CondicionesCarga = field(default_factory=CondicionesCarga)
    tipo: TipoMuro = TipoMuro.GRAVEDAD

    # ------------------------------------------------------------------
    # Accesos rápidos
    # ------------------------------------------------------------------
    @property
    def H(self) -> float:
        """Altura total del muro (m)."""
        return self.geometria.H_total

    @property
    def B(self) -> float:
        """Ancho total de la zapata (m)."""
        return self.geometria.B

    def resumen(self) -> str:
        g = self.geometria
        return (
            f"Muro tipo: {self.tipo.value} (gravedad)\n"
            f"  H_total = {g.H_total:.2f} m | B = {g.B:.2f} m | D = {g.D:.2f} m\n"
            f"  Cuerpo: corona = {g.b_corona:.2f} m, "
            f"acartelado frontal = {g.a_frontal:.2f} m, "
            f"acartelado posterior = {g.a_posterior:.2f} m\n"
            f"  β cara posterior ≈ {g.beta_grados:.1f}°\n"
            f"  Puntera = {g.b_puntera:.2f} m, Talón = {g.b_talon:.2f} m\n"
            f"  {self.concreto} | {self.acero}\n"
            f"  Relleno: {self.suelo_relleno}\n"
            f"  Cimentación: {self.suelo_cimentacion}\n"
            f"  α={self.condiciones.alpha}°, q_sc={self.condiciones.sobrecarga} kPa, "
            f"kh={self.condiciones.kh}, kv={self.condiciones.kv}"
        )
