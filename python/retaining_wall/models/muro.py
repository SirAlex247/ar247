"""
Modelos de geometría y del conjunto del muro de contención.

El muro se representa como la composición de:
    - Una geometría (dimensiones).
    - Dos estratos de suelo (relleno y cimentación).
    - Materiales (concreto y acero).
    - Condiciones de carga externas (sobrecarga, inclinación del relleno, sismo).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from ..utils.validaciones import (
    GeometriaInvalidaError,
    validar_positivo,
    validar_rango,
)
from .material import AceroRefuerzo, Concreto
from .suelo import Suelo


class TipoMuro(str, Enum):
    """Tipología del muro."""
    VOLADIZO = "voladizo"
    GRAVEDAD = "gravedad"
    SEMIGRAVEDAD = "semigravedad"
    CONTRAFUERTES = "contrafuertes"


# =============================================================================
# Geometría del muro en voladizo
# =============================================================================
@dataclass
class GeometriaMuro:
    """Dimensiones geométricas de un muro de contención en voladizo.

    Convención de ejes y coordenadas:
        - Origen en el borde exterior inferior de la puntera (punto C de Das).
        - Eje x positivo hacia el talón.
        - Eje y positivo hacia arriba.

    Attributes:
        H_vastago:   Altura del vástago (desde el tope de la zapata), en m.
        e_zapata:    Espesor (peralte) de la zapata, en m.
        b_puntera:   Ancho de la puntera (delante del vástago), en m.
        b_talon:     Ancho del talón (detrás del vástago), en m.
        b_corona:    Espesor del vástago en la corona (parte superior), en m.
        b_base_vast: Espesor del vástago en el arranque con la zapata, en m.
        D:           Profundidad de desplante (desde superficie del terreno
                     frontal hasta base inferior de la zapata), en m.
        H_relleno:   Altura del relleno efectivamente retenido sobre la zapata
                     (m). Si es None se usa H_vastago.
        cara_posterior_vertical: Si True, la cara trasera del vástago (la que
                     contacta al relleno) es vertical y el acartelamiento queda
                     del lado frontal (cara vista). Si False, el acartelamiento
                     queda atrás (lado del terreno, configuración tradicional).
                     Default True.
        h_diente:    Altura del diente de cortante (llave) bajo la zapata (m).
                     0 = sin diente. Default 0.
        b_diente:    Ancho del diente de cortante (m). 0 = sin diente. Default 0.
        x_diente:    Posición x del borde izquierdo del diente, medida desde
                     la puntera C (m). Si es None, se ubica bajo la puntera.
                     Default None.

    Notes:
        El ancho total de la zapata es ``B = b_puntera + b_base_vast + b_talon``.
        La altura total hasta la base de la zapata es ``H = H_vastago + e_zapata``.
    """

    H_vastago: float
    e_zapata: float
    b_puntera: float
    b_talon: float
    b_corona: float
    b_base_vast: float
    D: float
    H_relleno: float | None = None   # altura del suelo retenido (desde tope zapata);
                                     # None => igual a H_vastago (relleno a la corona)
    cara_posterior_vertical: bool = True  # True => acartelamiento al frente (cara vista);
                                          # False => acartelamiento atrás (contra terreno)
    h_diente: float = 0.0        # altura del diente de cortante (hacia abajo)
    b_diente: float = 0.0        # ancho del diente de cortante
    x_diente: float | None = None  # posición x del diente (None = bajo puntera)
    # Acartelamiento independiente del vástago. Si se especifica al menos uno,
    # definen la forma del vástago y b_base_vast = b_corona + a_frontal_v +
    # a_posterior_v. Si ambos son None, se conserva el comportamiento previo
    # (todo el batter en una cara según cara_posterior_vertical).
    a_frontal_v: float | None = None    # acartelamiento frontal (cara vista), m
    a_posterior_v: float | None = None  # acartelamiento posterior (terreno), m

    # --- Validaciones ---
    def __post_init__(self) -> None:
        # Resolver acartelamiento independiente antes de validar b_base_vast.
        if self.a_frontal_v is not None or self.a_posterior_v is not None:
            self.a_frontal_v = max(0.0, self.a_frontal_v or 0.0)
            self.a_posterior_v = max(0.0, self.a_posterior_v or 0.0)
            self.b_base_vast = self.b_corona + self.a_frontal_v + self.a_posterior_v

        validar_positivo(self.H_vastago, "H_vastago")
        validar_positivo(self.e_zapata, "e_zapata")
        validar_positivo(self.b_puntera, "b_puntera", permitir_cero=True)
        validar_positivo(self.b_talon, "b_talon")
        validar_positivo(self.b_corona, "b_corona")
        validar_positivo(self.b_base_vast, "b_base_vast")
        validar_positivo(self.D, "D")

        # Recomendaciones prácticas (Das, Fig. 8.3 / NSR-10)
        if self.b_corona < 0.30:
            raise GeometriaInvalidaError(
                "b_corona debe ser >= 0.30 m para colocación adecuada de concreto."
            )
        if self.D < 0.60:
            raise GeometriaInvalidaError(
                "D (profundidad de desplante) debe ser >= 0.60 m."
            )
        if self.e_zapata < 0.10 * (self.H_vastago + self.e_zapata):
            # Recomendación: e_zapata ≈ 0.1·H
            pass  # se permite pero podría emitirse una advertencia en niveles superiores
        if self.b_base_vast < self.b_corona:
            raise GeometriaInvalidaError(
                "El espesor en base del vástago debe ser >= b_corona."
            )
        # H_relleno entre 0 y H_vastago
        if self.H_relleno is not None:
            if self.H_relleno <= 0:
                raise GeometriaInvalidaError("H_relleno debe ser > 0.")
            if self.H_relleno > self.H_vastago:
                raise GeometriaInvalidaError(
                    f"H_relleno ({self.H_relleno} m) no puede superar "
                    f"H_vastago ({self.H_vastago} m)."
                )
        # Diente de cortante
        validar_positivo(self.h_diente, "h_diente", permitir_cero=True)
        validar_positivo(self.b_diente, "b_diente", permitir_cero=True)
        if (self.h_diente > 0) != (self.b_diente > 0):
            raise GeometriaInvalidaError(
                "h_diente y b_diente deben ser ambos > 0 o ambos = 0."
            )
        B = self.b_puntera + self.b_base_vast + self.b_talon
        if self.h_diente > 0:
            x0 = self.x_diente if self.x_diente is not None else 0.0
            if x0 < 0 or x0 + self.b_diente > B:
                raise GeometriaInvalidaError(
                    f"El diente debe estar dentro del ancho de la zapata (0 a {B:.2f} m)."
                )

    # ------------------------------------------------------------------
    # Propiedades derivadas
    # ------------------------------------------------------------------
    @property
    def H_total(self) -> float:
        """Altura total del muro (vástago + zapata), en m."""
        return self.H_vastago + self.e_zapata

    @property
    def H_relleno_ef(self) -> float:
        """Altura efectiva del relleno sobre el tope de la zapata (m).

        Si no se especificó H_relleno, se asume igual a H_vastago (el suelo
        llega hasta la corona del muro).
        """
        return self.H_relleno if self.H_relleno is not None else self.H_vastago

    @property
    def H_suelo(self) -> float:
        """Altura total del suelo retenido (desde base de zapata), en m."""
        return self.H_relleno_ef + self.e_zapata

    @property
    def B(self) -> float:
        """Ancho total de la zapata, en m."""
        return self.b_puntera + self.b_base_vast + self.b_talon

    @property
    def x_inicio_vastago(self) -> float:
        """Coordenada x del borde frontal del vástago (con respecto a C)."""
        return self.b_puntera

    @property
    def x_fin_vastago(self) -> float:
        """Coordenada x del borde trasero del vástago a nivel de la base."""
        return self.b_puntera + self.b_base_vast

    @property
    def x_cara_posterior_base(self) -> float:
        """x de la cara POSTERIOR del vástago a nivel de la base zapata."""
        return self.b_puntera + self.b_base_vast

    @property
    def a_frontal_ef(self) -> float:
        """Acartelamiento frontal efectivo del vástago (m).

        Si se especificó explícitamente, se usa. Si no, se deriva del modo
        clásico: todo el batter (b_base_vast - b_corona) va al frente cuando
        la cara posterior es vertical, o cero cuando el acartelamiento es atrás.
        """
        if self.a_frontal_v is not None:
            return self.a_frontal_v
        delta = self.b_base_vast - self.b_corona
        return delta if self.cara_posterior_vertical else 0.0

    @property
    def a_posterior_ef(self) -> float:
        """Acartelamiento posterior efectivo del vástago (m)."""
        if self.a_posterior_v is not None:
            return self.a_posterior_v
        delta = self.b_base_vast - self.b_corona
        return 0.0 if self.cara_posterior_vertical else delta

    @property
    def x_cara_posterior_corona(self) -> float:
        """x de la cara POSTERIOR del vástago a nivel de la corona.

        La corona retrocede respecto a la base posterior según el
        acartelamiento posterior efectivo.
        """
        return self.b_puntera + self.b_base_vast - self.a_posterior_ef

    @property
    def x_cara_frontal_base(self) -> float:
        """x de la cara FRONTAL del vástago a nivel de la base zapata."""
        return self.b_puntera

    @property
    def x_cara_frontal_corona(self) -> float:
        """x de la cara FRONTAL del vástago a nivel de la corona.

        La corona avanza respecto a la base frontal según el acartelamiento
        frontal efectivo.
        """
        return self.b_puntera + self.a_frontal_ef

    @property
    def tiene_diente(self) -> bool:
        return self.h_diente > 0 and self.b_diente > 0

    @property
    def x_diente_ef(self) -> float:
        """Posición x del borde izquierdo del diente (si existe)."""
        if self.x_diente is not None:
            return self.x_diente
        return 0.0  # por defecto bajo la puntera


# =============================================================================
# Condiciones externas de carga
# =============================================================================
@dataclass
class CondicionesCarga:
    """Condiciones ambientales y de solicitación externa sobre el muro.

    Attributes:
        alpha:       Inclinación del relleno (grados), medida desde la horizontal.
        sobrecarga:  Sobrecarga uniforme sobre el relleno, en kPa.
        kh:          Coeficiente sísmico horizontal (fracción de g).
        kv:          Coeficiente sísmico vertical (fracción de g).
        nivel_freatico_H: Altura del nivel freático medida desde la base
                     de la zapata (m). ``None`` si no aplica.
    """

    alpha: float = 0.0
    sobrecarga: float = 0.0
    kh: float = 0.0
    kv: float = 0.0
    nivel_freatico_H: float | None = None
    # Sobrecarga lineal (kN/m) paralela al muro, a una distancia horizontal
    # (m) de la cara posterior del vástago. Empuje por Boussinesq (muro rígido).
    carga_lineal: float = 0.0
    carga_lineal_dist: float = 0.0

    def __post_init__(self) -> None:
        validar_rango(self.alpha, 0.0, 30.0, "alpha")
        validar_positivo(self.sobrecarga, "sobrecarga", permitir_cero=True)
        validar_rango(self.kh, 0.0, 0.5, "kh")
        validar_rango(self.kv, 0.0, 0.5, "kv")
        validar_positivo(self.carga_lineal, "carga_lineal", permitir_cero=True)
        validar_positivo(self.carga_lineal_dist, "carga_lineal_dist", permitir_cero=True)


# =============================================================================
# Agregado principal: Muro de Contención
# =============================================================================
@dataclass
class MuroContencion:
    """Representación completa de un muro de contención para análisis y diseño.

    Attributes:
        geometria:         Dimensiones del muro.
        suelo_relleno:     Suelo retenido detrás del muro.
        suelo_cimentacion: Suelo de apoyo bajo la zapata.
        concreto:          Material concreto (NSR-10).
        acero:             Material acero (NSR-10).
        condiciones:       Condiciones externas (sobrecarga, inclinación, sismo).
        tipo:              Tipología del muro.
    """

    geometria: GeometriaMuro
    suelo_relleno: Suelo
    suelo_cimentacion: Suelo
    concreto: Concreto
    acero: AceroRefuerzo
    condiciones: CondicionesCarga = field(default_factory=CondicionesCarga)
    tipo: TipoMuro = TipoMuro.VOLADIZO

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
        """Devuelve una cadena legible con el resumen del muro."""
        g = self.geometria
        extras = []
        if g.cara_posterior_vertical:
            extras.append("  Acartelado: lado cara vista (cara posterior vertical)")
        else:
            extras.append("  Acartelado: lado contra terreno (cara frontal vertical)")
        if g.tiene_diente:
            extras.append(f"  Diente de cortante: h={g.h_diente:.2f} m, "
                          f"b={g.b_diente:.2f} m, x={g.x_diente_ef:.2f} m")
        extras_str = ("\n" + "\n".join(extras)) if extras else ""

        return (
            f"Muro tipo: {self.tipo.value}\n"
            f"  H_total = {g.H_total:.2f} m | B = {g.B:.2f} m | D = {g.D:.2f} m\n"
            f"  Puntera = {g.b_puntera:.2f} m, Talón = {g.b_talon:.2f} m\n"
            f"  Vástago: {g.b_corona:.2f}->{g.b_base_vast:.2f} m, H_vastago = {g.H_vastago:.2f} m\n"
            f"  H_relleno = {g.H_relleno_ef:.2f} m (suelo retenido sobre zapata)"
            f"{extras_str}\n"
            f"  {self.concreto} | {self.acero}\n"
            f"  Relleno: {self.suelo_relleno}\n"
            f"  Cimentación: {self.suelo_cimentacion}\n"
            f"  α={self.condiciones.alpha}°, q_sc={self.condiciones.sobrecarga} kPa, "
            f"kh={self.condiciones.kh}, kv={self.condiciones.kv}"
        )
