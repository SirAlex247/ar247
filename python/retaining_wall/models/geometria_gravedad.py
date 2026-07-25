"""Geometría de muro de gravedad (trapezoidal).

Un muro de gravedad es un bloque macizo (concreto, mampostería) que resiste
los empujes por su propio peso. A diferencia del muro en voladizo, no tiene
un vástago delgado y un talón largo; es un cuerpo trapezoidal sólido apoyado
sobre una zapata más ancha.

Convención de ejes (igual que voladizo):
    - Origen en el borde exterior inferior de la puntera (punto C de Das).
    - Eje x positivo hacia el talón.
    - Eje y positivo hacia arriba.

Geometría parametrizada (sigue Fig. 8.13 de Braja Das, Ej. 8.2):

       │←─b_corona─→│
       │            │
       │            │\\         ← cara posterior inclinada (β°)
       │            │  \\
       │  cuerpo    │    \\        H_muro
       │            │      \\
       │            │        \\
       │/-----------│---------\\
       /                       \\
      /  acartelado frontal    │
     /  (a_frontal × H_muro)   │
    │                          │
    │←------ B_zapata ---------│   e_zapata
    └──────────────────────────┘
    C (puntera)

Áreas que componen el cuerpo (excluida la zapata):
    1) Trapecio principal de cara posterior (entre vertical y β):
       triángulo de catetos (a_post × H_muro) donde
       a_post = H_muro / tan(β)  (β medido desde la horizontal en cara post.)
    2) Rectángulo central de ancho b_corona × H_muro
    3) Acartelado frontal: triángulo de catetos a_frontal × H_muro
La zapata es un rectángulo B_zapata × e_zapata.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from ..utils.validaciones import validar_positivo, validar_rango
from ..utils.validaciones import GeometriaInvalidaError


@dataclass
class GeometriaMuroGravedad:
    """Geometría de un muro de gravedad trapezoidal con zapata.

    Attributes:
        H_muro:         Altura del cuerpo del muro (sobre la zapata), m.
        e_zapata:       Espesor de la zapata, m.
        b_corona:       Ancho de la corona (parte superior del cuerpo), m.
        a_frontal:      Acartelamiento frontal (offset horizontal entre la
                        corona y el pie del cuerpo en la cara frontal), m.
                        En el ejemplo de Das: 0.27 m.
        a_posterior:    Acartelamiento posterior (offset horizontal entre la
                        corona y el pie del cuerpo en la cara posterior), m.
                        En el ejemplo de Das: 1.53 m, que da β = atan(5.7/1.53) = 75°.
        b_puntera:      Distancia desde la puntera (C) hasta el pie frontal del
                        cuerpo (en la base del cuerpo, sobre la zapata), m.
        b_talon:        Distancia desde el pie posterior del cuerpo hasta el
                        borde del talón de la zapata, m. Suele ser pequeña en
                        muros de gravedad (Das ej. 8.2 = 0.3 m).
        D:              Profundidad de desplante (m).

    Notes:
        - Ancho total de la zapata: B = b_puntera + a_frontal + b_corona +
          a_posterior + b_talon
        - Altura total del muro hasta la base de la zapata:
          H_total = H_muro + e_zapata
        - Altura efectiva para empuje activo (H'):  H' = H_muro + e_zapata
          (igual que voladizo si no hay relleno inclinado adicional).
    """

    H_muro: float
    e_zapata: float
    b_corona: float
    a_frontal: float
    a_posterior: float
    b_puntera: float
    b_talon: float
    D: float

    def __post_init__(self) -> None:
        validar_positivo(self.H_muro, "H_muro")
        validar_positivo(self.e_zapata, "e_zapata")
        validar_positivo(self.b_corona, "b_corona")
        validar_positivo(self.a_frontal, "a_frontal", permitir_cero=True)
        validar_positivo(self.a_posterior, "a_posterior", permitir_cero=True)
        validar_positivo(self.b_puntera, "b_puntera", permitir_cero=True)
        validar_positivo(self.b_talon, "b_talon", permitir_cero=True)
        validar_positivo(self.D, "D")
        if self.b_corona < 0.30:
            raise GeometriaInvalidaError(
                f"b_corona = {self.b_corona:.2f} m es menor que el mínimo "
                f"constructivo (0.30 m)."
            )

    # ------------------------------------------------------------------
    # Magnitudes derivadas
    # ------------------------------------------------------------------
    @property
    def H_total(self) -> float:
        """Altura total del muro (cuerpo + zapata), m."""
        return self.H_muro + self.e_zapata

    @property
    def B(self) -> float:
        """Ancho total de la zapata, m."""
        return (self.b_puntera + self.a_frontal + self.b_corona
                + self.a_posterior + self.b_talon)

    @property
    def beta_grados(self) -> float:
        """Ángulo β de la cara posterior medido desde la horizontal (°).

        Si a_posterior = 0 → cara posterior vertical, β = 90°.
        En Das Ej. 8.2: a_posterior = 1.53 m, H_muro = 5.7 m  →  β ≈ 75°.
        Pero el cuerpo tiene también la zapata; β se mide desde la zapata.
        Aquí lo calculamos como atan2(H_muro, a_posterior) — eso es lo que
        Coulomb necesita.
        """
        if self.a_posterior == 0.0:
            return 90.0
        return math.degrees(math.atan2(self.H_muro, self.a_posterior))

    @property
    def H_prima(self) -> float:
        """Altura sobre la cual actúa el empuje activo, en m.

        Para un muro de gravedad, el empuje actúa sobre la cara posterior
        del cuerpo + el espesor de la zapata. La altura total para Pa es
        H' = H_muro + e_zapata = H_total.
        """
        return self.H_total

    # Compatibilidad con AnalisisEstabilidad (que verifica si el muro tiene
    # diente de cortante). Los muros de gravedad tradicionales no llevan
    # diente — en el futuro se puede extender el modelo si hace falta.
    @property
    def tiene_diente(self) -> bool:
        return False

    @property
    def h_diente(self) -> float:
        return 0.0

    @property
    def b_diente(self) -> float:
        return 0.0

    @property
    def x_diente_ef(self) -> float:
        return 0.0

    # ------------------------------------------------------------------
    # Vértices del cuerpo (sin zapata) y de la zapata
    # ------------------------------------------------------------------
    def vertices_cuerpo(self) -> list[tuple[float, float]]:
        """Polígono del cuerpo trapezoidal sobre la zapata. CCW desde el
        pie frontal."""
        # Coordenadas (x medido desde la puntera C, y medido desde la
        # base de la zapata).
        y_base = self.e_zapata          # apoyado sobre la zapata
        y_top  = self.e_zapata + self.H_muro
        # Pie frontal (esquina inferior izquierda del cuerpo)
        x_pie_front = self.b_puntera
        # Pie posterior (esquina inferior derecha del cuerpo)
        x_pie_post  = self.b_puntera + self.a_frontal + self.b_corona + self.a_posterior
        # Corona (parte superior — solo b_corona)
        x_cor_izq   = self.b_puntera + self.a_frontal
        x_cor_der   = x_cor_izq + self.b_corona
        return [
            (x_pie_front, y_base),
            (x_pie_post,  y_base),
            (x_cor_der,   y_top),
            (x_cor_izq,   y_top),
        ]

    def vertices_zapata(self) -> list[tuple[float, float]]:
        """Polígono de la zapata (rectángulo)."""
        return [
            (0.0,       0.0),
            (self.B,    0.0),
            (self.B,    self.e_zapata),
            (0.0,       self.e_zapata),
        ]

    # ------------------------------------------------------------------
    # Áreas y centroides de las secciones (para cálculo de pesos)
    # ------------------------------------------------------------------
    def secciones_concreto(self) -> list[dict]:
        """Devuelve las secciones que forman el cuerpo + zapata para cálculo
        de pesos y centroides. Cada dict tiene:
            {nombre, area (m²), x_centroide (m), y_centroide (m)}
        Las áreas son por metro lineal de muro (perpendicular al plano).
        """
        secs = []
        H = self.H_muro
        ef = self.a_frontal
        ep = self.a_posterior
        bc = self.b_corona

        # 1) Acartelado frontal: triángulo recto con catetos (a_frontal, H_muro)
        #    Vértices: (b_puntera, e_zap), (b_puntera+ef, e_zap), (b_puntera+ef, e_zap+H)
        if ef > 0:
            x_cent = self.b_puntera + 2.0/3.0 * ef
            y_cent = self.e_zapata + H/3.0
            secs.append({
                "nombre": "Cuerpo — acartelado frontal",
                "area":   0.5 * ef * H,
                "x_centroide": x_cent,
                "y_centroide": y_cent,
            })

        # 2) Rectángulo central: ancho b_corona, altura H_muro
        if bc > 0:
            x_cent = self.b_puntera + ef + bc/2.0
            y_cent = self.e_zapata + H/2.0
            secs.append({
                "nombre": "Cuerpo — rectángulo central",
                "area":   bc * H,
                "x_centroide": x_cent,
                "y_centroide": y_cent,
            })

        # 3) Acartelado posterior: triángulo recto con catetos (a_posterior, H_muro)
        #    Vértices: (b_p+ef+bc, e_z), (b_p+ef+bc+ep, e_z), (b_p+ef+bc, e_z+H)
        #    Centroide x = b_p + ef + bc + a_post/3 (más cerca de la cara vertical)
        if ep > 0:
            x_cent = self.b_puntera + ef + bc + ep/3.0
            y_cent = self.e_zapata + H/3.0
            secs.append({
                "nombre": "Cuerpo — acartelado posterior",
                "area":   0.5 * ep * H,
                "x_centroide": x_cent,
                "y_centroide": y_cent,
            })

        # 4) Zapata
        secs.append({
            "nombre": "Zapata",
            "area":   self.B * self.e_zapata,
            "x_centroide": self.B / 2.0,
            "y_centroide": self.e_zapata / 2.0,
        })
        return secs

    def secciones_suelo_sobre_talon(self) -> list[dict]:
        """Suelo apoyado sobre el talón (a la derecha del pie posterior del
        cuerpo) — solo si b_talon > 0.

        En muros de gravedad típicos b_talon es pequeño o 0 y este peso es
        despreciable. Si b_talon > 0, se considera un rectángulo de suelo
        de ancho b_talon × altura H_muro encima del talón.
        """
        if self.b_talon <= 0:
            return []
        x_pie_post = self.b_puntera + self.a_frontal + self.b_corona + self.a_posterior
        x_cent = x_pie_post + self.b_talon / 2.0
        y_cent = self.e_zapata + self.H_muro / 2.0
        return [{
            "nombre": "Suelo sobre talón",
            "area":   self.b_talon * self.H_muro,
            "x_centroide": x_cent,
            "y_centroide": y_cent,
        }]
