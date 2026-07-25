"""Cálculo de cargas para muros de gravedad (cuerpo trapezoidal).

Reusa todas las clases de ``cargas.py`` (``Carga``, ``SistemaCargas``,
``CategoriaCarga``, ``TipoCarga``) y la de empujes; sólo cambia cómo se
descompone el muro en pesos.
"""
from __future__ import annotations

import math

from ..models.muro_gravedad import MuroGravedad
from .cargas import (
    Carga, CategoriaCarga, SistemaCargas, TipoCarga,
)
from .empujes import EmpujeSuelo


class CalculadoraCargasGravedad:
    """Genera las cargas para un muro de gravedad.

    Para gravedad, el método estándar de Das (Ej. 8.2) es:
        - Empuje activo de Coulomb sobre la cara posterior inclinada.
        - Pesos del cuerpo (descompuesto en triángulos + rectángulo) y
          de la zapata.
        - El "peso del suelo arriba de la cara posterior del muro NO se
          toma en cuenta" (cita textual de Das, Ej. 8.2). Los muros de
          gravedad típicamente no tienen talón (b_talon ≈ 0).
        - Empuje pasivo frente a la puntera (resistente al deslizamiento).
    """

    def __init__(self, muro: MuroGravedad,
                 metodo_empuje: str = "coulomb"):
        """
        Args:
            muro: ``MuroGravedad`` a analizar.
            metodo_empuje: ``"coulomb"`` (recomendado para gravedad) o
                ``"rankine"`` (válido si la cara posterior es vertical y
                no se quiere considerar la fricción suelo-muro).
        """
        self.muro = muro
        self.metodo_empuje = metodo_empuje

    # ------------------------------------------------------------------
    def calcular(self, incluir_sismo: bool = False) -> SistemaCargas:
        sistema = SistemaCargas()

        # 1) Pesos propios (cuerpo + zapata)
        gamma_c = self.muro.concreto.gamma
        for sec in self.muro.geometria.secciones_concreto():
            sistema.agregar(Carga(
                nombre=f"W-{sec['nombre']}",
                magnitud=sec["area"] * gamma_c,
                tipo=TipoCarga.VERTICAL,
                categoria=CategoriaCarga.D,
                x_aplicacion=sec["x_centroide"],
                sentido=+1,
            ))

        # 2) Suelo sobre el talón.
        #
        # Importante (cita Das, Ej. 8.2): "el peso del suelo arriba de la
        # cara posterior del muro no se toma en cuenta" cuando se aplica
        # Coulomb directamente sobre la cara posterior real del muro
        # (porque esa cuña ya queda dentro del análisis de empuje).
        #
        # Solo lo incluimos si:
        #   - se usa Rankine (que opera sobre un plano vertical ficticio
        #     AB en el borde del talón, así que la cuña entre AB y la
        #     cara real del muro sí pesa físicamente sobre la zapata), Y
        #   - hay talón explícito (b_talon > 0).
        if self.metodo_empuje == "rankine":
            gamma_rel = self.muro.suelo_relleno.gamma
            for sec in self.muro.geometria.secciones_suelo_sobre_talon():
                sistema.agregar(Carga(
                    nombre=f"W-{sec['nombre']}",
                    magnitud=sec["area"] * gamma_rel,
                    tipo=TipoCarga.VERTICAL,
                    categoria=CategoriaCarga.D,
                    x_aplicacion=sec["x_centroide"],
                    sentido=+1,
                ))

        # 3) Empuje activo
        self._agregar_empuje_activo(sistema)

        # 4) Sobrecarga (presión rectangular sobre H')
        if self.muro.condiciones.sobrecarga > 0:
            self._agregar_empuje_sobrecarga(sistema)

        # 5) Empuje pasivo frente a la puntera
        self._agregar_empuje_pasivo(sistema)

        # 6) Sismo (Mononobe-Okabe), opcional
        if incluir_sismo and self.muro.condiciones.kh > 0:
            self._agregar_empuje_sismico(sistema)

        return sistema

    # ------------------------------------------------------------------
    # Helpers privados
    # ------------------------------------------------------------------
    def _agregar_empuje_activo(self, sistema: SistemaCargas) -> None:
        rel = self.muro.suelo_relleno
        cond = self.muro.condiciones
        g = self.muro.geometria
        H_prima = g.H_prima
        B = g.B

        if self.metodo_empuje == "coulomb":
            beta = g.beta_grados            # ángulo cara post. desde horizontal
            emp = EmpujeSuelo.calcular_empuje_activo_coulomb(
                gamma=rel.gamma, H=H_prima,
                phi_grados=rel.phi,
                delta_grados=rel.delta_efectivo,
                beta_grados=beta,
                alpha_grados=cond.alpha,
            )
            # En Coulomb la fuerza forma un ángulo (90 - β + δ + α) con la
            # horizontal cuando se proyecta. Para β = 90 reduce a (δ + α).
            # El método interno ya devuelve componente_h, componente_v.
        else:  # rankine — válido si cara posterior vertical
            emp = EmpujeSuelo.calcular_empuje_activo_rankine(
                gamma=rel.gamma, H=H_prima,
                phi_grados=rel.phi,
                alpha_grados=cond.alpha,
                cohesion=rel.cohesion,
            )

        # Componente horizontal — produce momento de volcamiento respecto
        # a C. y_aplicacion = H'/3.
        sistema.agregar(Carga(
            nombre="Empuje activo (horiz.)",
            magnitud=emp.componente_h,
            tipo=TipoCarga.HORIZONTAL,
            categoria=CategoriaCarga.H,
            y_aplicacion=emp.y_aplicacion,
            sentido=+1,
        ))
        # Componente vertical — el punto de aplicación depende del método:
        if emp.componente_v > 0:
            if self.metodo_empuje == "coulomb":
                # Pa actúa sobre la CARA POSTERIOR REAL del muro (cuerpo
                # solamente, NO incluye la zapata). La cara va desde
                # (x_pie_post, y=e_zapata) hasta (x_corona_der, y=H_total).
                # y_aplic = H'/3 medido desde la base de la zapata.
                x_pie_post = (g.b_puntera + g.a_frontal + g.b_corona
                              + g.a_posterior)
                x_corona_der = g.b_puntera + g.a_frontal + g.b_corona
                # Posición vertical del punto de aplicación dentro de la
                # cara del cuerpo: y_pa - e_zapata = altura por encima
                # del tope de la zapata. Si y_pa < e_zapata el punto cae
                # en la zapata y usamos x_pie_post.
                if emp.y_aplicacion <= g.e_zapata:
                    x_v = x_pie_post
                else:
                    t = (emp.y_aplicacion - g.e_zapata) / g.H_muro
                    x_v = x_pie_post + t * (x_corona_der - x_pie_post)
            else:
                # Rankine: Pv actúa sobre el plano vertical AB ficticio en
                # el borde del talón → x = B.
                x_v = B
            sistema.agregar(Carga(
                nombre="Empuje activo (vert.)",
                magnitud=emp.componente_v,
                tipo=TipoCarga.VERTICAL,
                categoria=CategoriaCarga.Hv,
                x_aplicacion=x_v,
                sentido=+1,
            ))

    def _agregar_empuje_sobrecarga(self, sistema: SistemaCargas) -> None:
        rel = self.muro.suelo_relleno
        cond = self.muro.condiciones
        g = self.muro.geometria
        # Coeficiente Ka según método elegido (consistente con activo)
        if self.metodo_empuje == "coulomb":
            Ka = EmpujeSuelo.calcular_ka_coulomb(
                phi_grados=rel.phi, delta_grados=rel.delta_efectivo,
                beta_grados=g.beta_grados, alpha_grados=cond.alpha,
            )
        else:
            Ka = EmpujeSuelo.calcular_ka_rankine(rel.phi, cond.alpha)
        H_prima = g.H_prima
        Pq = Ka * cond.sobrecarga * H_prima
        # Distribución rectangular → resultante a H'/2
        sistema.agregar(Carga(
            nombre="Empuje por sobrecarga",
            magnitud=Pq,
            tipo=TipoCarga.HORIZONTAL,
            categoria=CategoriaCarga.Lsc,
            y_aplicacion=H_prima / 2.0,
            sentido=+1,
        ))

    def _agregar_empuje_pasivo(self, sistema: SistemaCargas) -> None:
        cim = self.muro.suelo_cimentacion
        D = self.muro.geometria.D
        emp = EmpujeSuelo.calcular_empuje_pasivo_rankine(
            gamma=cim.gamma, H=D, phi_grados=cim.phi, cohesion=cim.cohesion,
        )
        sistema.agregar(Carga(
            nombre="Empuje pasivo (puntera)",
            magnitud=emp.componente_h,
            tipo=TipoCarga.HORIZONTAL,
            categoria=CategoriaCarga.H,
            y_aplicacion=emp.y_aplicacion,
            sentido=-1,
        ))

    def _agregar_empuje_sismico(self, sistema: SistemaCargas) -> None:
        rel = self.muro.suelo_relleno
        cond = self.muro.condiciones
        g = self.muro.geometria

        emp_est = EmpujeSuelo.calcular_empuje_activo_coulomb(
            gamma=rel.gamma, H=g.H_prima,
            phi_grados=rel.phi, delta_grados=rel.delta_efectivo,
            beta_grados=g.beta_grados, alpha_grados=cond.alpha,
        )
        emp_sis = EmpujeSuelo.calcular_empuje_sismico(
            gamma=rel.gamma, H=g.H_prima,
            phi_grados=rel.phi,
            delta_grados=rel.delta_efectivo,
            beta_grados=g.beta_grados,
            alpha_grados=cond.alpha,
            kh=cond.kh, kv=cond.kv,
        )
        delta_P = max(0.0, emp_sis.componente_h - emp_est.componente_h)
        sistema.agregar(Carga(
            nombre="Incremento dinámico ΔPae",
            magnitud=delta_P,
            tipo=TipoCarga.HORIZONTAL,
            categoria=CategoriaCarga.E,
            y_aplicacion=0.6 * g.H_prima,    # punto de aplicación recomendado por Das
            sentido=+1,
        ))
