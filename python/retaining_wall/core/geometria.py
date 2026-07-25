"""
Descomposición geométrica del muro para cálculo de pesos y momentos.

El muro se descompone en polígonos simples (rectángulos y triángulos):
    1. Zapata.
    2. Vástago rectangular (ancho = b_corona).
    3. Vástago trapezoidal (cuña de acartelamiento, si b_base_vast > b_corona).
    4. Suelo sobre el talón (rectángulo).
    5. Suelo sobre el talón (triángulo por inclinación α del relleno).
    6. Suelo sobre la puntera (si existe, hasta la profundidad D - e_zapata).

Para cada sección se calcula el área, el peso por metro lineal de muro y el
brazo de momento respecto al punto C (borde exterior de la puntera, coincidente
con el origen del sistema local).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from ..models.muro import MuroContencion


# =============================================================================
# Estructura de resultados
# =============================================================================
@dataclass(frozen=True)
class SeccionGeometrica:
    """Sección discreta del muro para integración de pesos y momentos.

    Attributes:
        id:        Identificador numérico de la sección.
        nombre:    Etiqueta legible.
        material:  "concreto", "suelo_relleno" o "suelo_cimentacion".
        area:      Área transversal en m².
        peso:      Peso por metro lineal en kN/m.
        x_cg:      Coordenada x del centroide (desde C) en m.
        y_cg:      Coordenada y del centroide (desde base zapata) en m.
    """

    id: int
    nombre: str
    material: Literal["concreto", "suelo_relleno", "suelo_cimentacion"]
    area: float
    peso: float
    x_cg: float
    y_cg: float

    @property
    def momento_respecto_C(self) -> float:
        """Momento del peso respecto a la puntera C (kN·m/m). Positivo estabiliza."""
        return self.peso * self.x_cg


# =============================================================================
# Calculadora de geometría
# =============================================================================
class CalculadoraGeometria:
    """Descompone el muro en secciones para integración."""

    def __init__(self, muro: MuroContencion) -> None:
        self.muro = muro

    # ------------------------------------------------------------------
    # Altura efectiva H' para Rankine (plano vertical por el talón)
    # ------------------------------------------------------------------
    def altura_efectiva_rankine(self) -> float:
        """Altura H' sobre la cual actúa la presión activa de Rankine.

        H' = H_suelo + b_talon · tan(α)

        donde H_suelo = H_relleno_ef + e_zapata (altura del terreno retenido
        desde la base de la zapata).

        Returns:
            Altura H' en metros.
        """
        g = self.muro.geometria
        alpha_rad = math.radians(self.muro.condiciones.alpha)
        return g.H_suelo + g.b_talon * math.tan(alpha_rad)

    # ------------------------------------------------------------------
    # Descomposición en secciones
    # ------------------------------------------------------------------
    def descomponer(self) -> list[SeccionGeometrica]:
        """Descompone el muro en secciones elementales con sus centroides.

        Returns:
            Lista de secciones (concreto y suelos) con áreas, pesos y brazos.
        """
        secciones: list[SeccionGeometrica] = []
        secciones.extend(self._secciones_concreto())
        secciones.extend(self._secciones_suelo_relleno())
        return secciones

    # ------------------------------------------------------------------
    # --- Cuerpos de concreto ---
    # ------------------------------------------------------------------
    def _secciones_concreto(self) -> list[SeccionGeometrica]:
        g = self.muro.geometria
        gc = self.muro.concreto.gamma
        s: list[SeccionGeometrica] = []

        # Sección 1: zapata (rectángulo completo)
        area_z = g.B * g.e_zapata
        s.append(
            SeccionGeometrica(
                id=1,
                nombre="Zapata",
                material="concreto",
                area=area_z,
                peso=area_z * gc,
                x_cg=g.B / 2.0,
                y_cg=g.e_zapata / 2.0,
            )
        )

        # -- Vástago: se descompone como rectángulo central (ancho = b_corona)
        # + cuña de acartelamiento frontal (a_frontal_ef) + cuña de
        # acartelamiento posterior (a_posterior_ef). Soporta acartelamiento en
        # una o en ambas caras de forma independiente. Cuando una de las cuñas
        # es cero se reduce exactamente al caso clásico de un solo lado.
        af = g.a_frontal_ef
        ap = g.a_posterior_ef
        H = g.H_vastago
        y_cg_rect = g.e_zapata + H / 2.0
        y_cg_tri  = g.e_zapata + H / 3.0

        # Sección 2: rectángulo central, arranca tras la cuña frontal
        x_rect_ini = g.b_puntera + af
        area_vr = g.b_corona * H
        s.append(
            SeccionGeometrica(
                id=2,
                nombre="Vástago (rectangular)",
                material="concreto",
                area=area_vr,
                peso=area_vr * gc,
                x_cg=x_rect_ini + g.b_corona / 2.0,
                y_cg=y_cg_rect,
            )
        )

        # Sección 3: cuña de acartelamiento FRONTAL (triángulo recto).
        # Vértices: (b_puntera, e_zap), (b_puntera+af, e_zap), (b_puntera+af, tope)
        # → centroide x = b_puntera + (2/3)·af
        if af > 1e-9:
            area_vf = 0.5 * af * H
            s.append(
                SeccionGeometrica(
                    id=3,
                    nombre="Vástago (acartelamiento frontal)",
                    material="concreto",
                    area=area_vf,
                    peso=area_vf * gc,
                    x_cg=g.b_puntera + (2.0 / 3.0) * af,
                    y_cg=y_cg_tri,
                )
            )

        # Sección 4: cuña de acartelamiento POSTERIOR (triángulo recto).
        # Base entre x = b_puntera+af+b_corona y x = b_puntera+b_base_vast,
        # vértice superior en la cara del rectángulo → centroide x = base + ap/3
        if ap > 1e-9:
            x_post_base = g.b_puntera + af + g.b_corona
            area_vp = 0.5 * ap * H
            s.append(
                SeccionGeometrica(
                    id=4,
                    nombre="Vástago (acartelamiento posterior)",
                    material="concreto",
                    area=area_vp,
                    peso=area_vp * gc,
                    x_cg=x_post_base + ap / 3.0,
                    y_cg=y_cg_tri,
                )
            )

        # Sección 7: Diente de cortante (rectángulo bajo la zapata, y<0)
        if g.tiene_diente:
            area_d = g.b_diente * g.h_diente
            x_cg_d = g.x_diente_ef + g.b_diente / 2.0
            y_cg_d = -g.h_diente / 2.0     # por debajo de la base de la zapata
            s.append(
                SeccionGeometrica(
                    id=7,
                    nombre="Diente de cortante",
                    material="concreto",
                    area=area_d,
                    peso=area_d * gc,
                    x_cg=x_cg_d,
                    y_cg=y_cg_d,
                )
            )
        return s

    # ------------------------------------------------------------------
    # --- Suelo sobre el talón ---
    # ------------------------------------------------------------------
    def _secciones_suelo_relleno(self) -> list[SeccionGeometrica]:
        g = self.muro.geometria
        gamma_s = self.muro.suelo_relleno.gamma
        alpha_rad = math.radians(self.muro.condiciones.alpha)
        s: list[SeccionGeometrica] = []

        if g.b_talon <= 0:
            return s

        # Rectángulo de suelo sobre el talón, de altura H_relleno_ef
        H_rel = g.H_relleno_ef
        area_sr = g.b_talon * H_rel
        x_cg_sr = g.x_fin_vastago + g.b_talon / 2.0
        y_cg_sr = g.e_zapata + H_rel / 2.0
        s.append(
            SeccionGeometrica(
                id=4,
                nombre="Suelo sobre talón (rect.)",
                material="suelo_relleno",
                area=area_sr,
                peso=area_sr * gamma_s,
                x_cg=x_cg_sr,
                y_cg=y_cg_sr,
            )
        )

        # Triángulo de suelo sobre el talón cuando α > 0
        if self.muro.condiciones.alpha > 0.0:
            h_triangulo = g.b_talon * math.tan(alpha_rad)
            area_st = 0.5 * g.b_talon * h_triangulo
            x_cg_st = g.x_fin_vastago + (2.0 / 3.0) * g.b_talon
            y_cg_st = g.e_zapata + H_rel + h_triangulo / 3.0
            s.append(
                SeccionGeometrica(
                    id=5,
                    nombre="Suelo sobre talón (triang.)",
                    material="suelo_relleno",
                    area=area_st,
                    peso=area_st * gamma_s,
                    x_cg=x_cg_st,
                    y_cg=y_cg_st,
                )
            )
        return s

    # ------------------------------------------------------------------
    # Consolidación
    # ------------------------------------------------------------------
    def peso_total_vertical(self) -> float:
        """Suma de pesos verticales de concreto + suelo sobre el talón (kN/m)."""
        return sum(sec.peso for sec in self.descomponer())

    def momento_estabilizador(self) -> float:
        """Momento estabilizador (kN·m/m) aportado por los pesos propios."""
        return sum(sec.momento_respecto_C for sec in self.descomponer())


# =============================================================================
# Ejemplo de uso
# =============================================================================
if __name__ == "__main__":
    from ..models.material import MaterialesComunes
    from ..models.muro import CondicionesCarga, GeometriaMuro, MuroContencion
    from ..models.suelo import Suelo

    geo = GeometriaMuro(
        H_vastago=6.00, e_zapata=0.70,
        b_puntera=0.70, b_talon=2.60,
        b_corona=0.50, b_base_vast=0.70, D=1.50,
    )
    muro = MuroContencion(
        geometria=geo,
        suelo_relleno=Suelo(gamma=18.0, phi=30.0, nombre="Relleno"),
        suelo_cimentacion=Suelo(gamma=19.0, phi=20.0, cohesion=40.0, nombre="Cim."),
        concreto=MaterialesComunes.concreto_21(),
        acero=MaterialesComunes.acero_420(),
        condiciones=CondicionesCarga(alpha=10.0),
    )

    calc = CalculadoraGeometria(muro)
    print(f"H' = {calc.altura_efectiva_rankine():.3f} m")
    print(f"ΣV (peso) = {calc.peso_total_vertical():.2f} kN/m")
    print(f"ΣMR      = {calc.momento_estabilizador():.2f} kN·m/m")
    for sec in calc.descomponer():
        print(f"  [{sec.id}] {sec.nombre:<30s} W={sec.peso:8.2f} kN/m  "
              f"x_cg={sec.x_cg:.3f} m  M={sec.momento_respecto_C:8.2f} kN·m/m")
