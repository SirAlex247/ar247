"""
Módulo de manejo y conversión de unidades.

El sistema interno trabaja en unidades SI de ingeniería estructural:
    - Longitud: metros (m)
    - Fuerza:   kilonewtons (kN)
    - Presión/Esfuerzo: kilopascales (kPa) [= kN/m²]
    - Peso específico: kN/m³
    - Esfuerzo de materiales: megapascales (MPa)
    - Momento: kN·m

Todas las entradas del usuario se convierten al sistema interno mediante
las funciones `a_SI_*`. Las salidas se pueden exportar a otras unidades con
las funciones `desde_SI_*`.
"""

from __future__ import annotations

from enum import Enum
from typing import Final


# =============================================================================
# Enumeraciones de unidades admitidas
# =============================================================================
class UnidadLongitud(str, Enum):
    M = "m"
    CM = "cm"
    MM = "mm"


class UnidadFuerza(str, Enum):
    KN = "kN"
    N = "N"
    TON = "tonf"   # tonelada-fuerza (métrica)
    KGF = "kgf"


class UnidadPresion(str, Enum):
    KPA = "kPa"
    PA = "Pa"
    MPA = "MPa"
    KGF_CM2 = "kgf/cm2"
    TON_M2 = "tonf/m2"


class UnidadPesoEspecifico(str, Enum):
    KN_M3 = "kN/m3"
    KGF_M3 = "kgf/m3"
    TON_M3 = "tonf/m3"


class UnidadAngulo(str, Enum):
    GRADOS = "deg"
    RADIANES = "rad"


# =============================================================================
# Factores de conversión (unidad origen -> unidad SI interna)
# =============================================================================
_LONGITUD_A_M: Final[dict[UnidadLongitud, float]] = {
    UnidadLongitud.M: 1.0,
    UnidadLongitud.CM: 1e-2,
    UnidadLongitud.MM: 1e-3,
}

_FUERZA_A_KN: Final[dict[UnidadFuerza, float]] = {
    UnidadFuerza.KN: 1.0,
    UnidadFuerza.N: 1e-3,
    UnidadFuerza.TON: 9.80665,      # 1 tonf = 9.80665 kN
    UnidadFuerza.KGF: 9.80665e-3,
}

_PRESION_A_KPA: Final[dict[UnidadPresion, float]] = {
    UnidadPresion.KPA: 1.0,
    UnidadPresion.PA: 1e-3,
    UnidadPresion.MPA: 1e3,
    UnidadPresion.KGF_CM2: 98.0665,
    UnidadPresion.TON_M2: 9.80665,
}

_PESO_ESP_A_KN_M3: Final[dict[UnidadPesoEspecifico, float]] = {
    UnidadPesoEspecifico.KN_M3: 1.0,
    UnidadPesoEspecifico.KGF_M3: 9.80665e-3,
    UnidadPesoEspecifico.TON_M3: 9.80665,
}


# =============================================================================
# API de conversión: A unidades SI
# =============================================================================
def a_SI_longitud(valor: float, unidad: UnidadLongitud | str = UnidadLongitud.M) -> float:
    """Convierte una longitud a metros.

    Args:
        valor: Valor numérico de la longitud.
        unidad: Unidad de origen. Acepta la enumeración o su literal de cadena.

    Returns:
        Longitud equivalente en metros.
    """
    u = UnidadLongitud(unidad)
    return valor * _LONGITUD_A_M[u]


def a_SI_fuerza(valor: float, unidad: UnidadFuerza | str = UnidadFuerza.KN) -> float:
    """Convierte una fuerza a kilonewtons."""
    u = UnidadFuerza(unidad)
    return valor * _FUERZA_A_KN[u]


def a_SI_presion(valor: float, unidad: UnidadPresion | str = UnidadPresion.KPA) -> float:
    """Convierte una presión o esfuerzo a kilopascales (kN/m²)."""
    u = UnidadPresion(unidad)
    return valor * _PRESION_A_KPA[u]


def a_SI_peso_especifico(
    valor: float,
    unidad: UnidadPesoEspecifico | str = UnidadPesoEspecifico.KN_M3,
) -> float:
    """Convierte un peso específico a kN/m³."""
    u = UnidadPesoEspecifico(unidad)
    return valor * _PESO_ESP_A_KN_M3[u]


def a_SI_angulo(valor: float, unidad: UnidadAngulo | str = UnidadAngulo.GRADOS) -> float:
    """Convierte un ángulo a radianes (unidad interna para trigonometría)."""
    import math
    u = UnidadAngulo(unidad)
    return math.radians(valor) if u == UnidadAngulo.GRADOS else valor


# =============================================================================
# API de conversión: DESDE unidades SI (para reportes)
# =============================================================================
def desde_SI_longitud(valor_m: float, unidad: UnidadLongitud | str) -> float:
    """Convierte desde metros a la unidad destino."""
    u = UnidadLongitud(unidad)
    return valor_m / _LONGITUD_A_M[u]


def desde_SI_fuerza(valor_kn: float, unidad: UnidadFuerza | str) -> float:
    """Convierte desde kN a la unidad destino."""
    u = UnidadFuerza(unidad)
    return valor_kn / _FUERZA_A_KN[u]


def desde_SI_presion(valor_kpa: float, unidad: UnidadPresion | str) -> float:
    """Convierte desde kPa a la unidad destino."""
    u = UnidadPresion(unidad)
    return valor_kpa / _PRESION_A_KPA[u]


def desde_SI_angulo(valor_rad: float, unidad: UnidadAngulo | str) -> float:
    """Convierte desde radianes a la unidad destino."""
    import math
    u = UnidadAngulo(unidad)
    return math.degrees(valor_rad) if u == UnidadAngulo.GRADOS else valor_rad


# =============================================================================
# Utilidad: fábrica desde diccionario de usuario
# =============================================================================
def convertir(valor: float, unidad_origen: str, tipo: str) -> float:
    """Convierte un valor dado al sistema interno según el tipo de magnitud.

    Args:
        valor: Número a convertir.
        unidad_origen: Símbolo de la unidad (p.ej. ``"cm"``, ``"MPa"``).
        tipo: Tipo de magnitud: ``"longitud"``, ``"fuerza"``, ``"presion"``,
            ``"peso_especifico"`` o ``"angulo"``.

    Returns:
        Valor en unidades SI internas.

    Raises:
        ValueError: Si el tipo no está soportado o la unidad es inválida.
    """
    dispatcher = {
        "longitud": (a_SI_longitud, UnidadLongitud),
        "fuerza": (a_SI_fuerza, UnidadFuerza),
        "presion": (a_SI_presion, UnidadPresion),
        "peso_especifico": (a_SI_peso_especifico, UnidadPesoEspecifico),
        "angulo": (a_SI_angulo, UnidadAngulo),
    }
    if tipo not in dispatcher:
        raise ValueError(f"Tipo de magnitud no soportado: {tipo!r}")
    func, enum_cls = dispatcher[tipo]
    return func(valor, enum_cls(unidad_origen))
