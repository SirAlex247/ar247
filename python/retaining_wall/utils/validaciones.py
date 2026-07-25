"""
Módulo de validación de datos de entrada.

Provee excepciones específicas del dominio y funciones reutilizables para
validar parámetros geométricos, geotécnicos y de materiales antes de su uso
en los algoritmos de cálculo.
"""

from __future__ import annotations

from typing import Any, Iterable


# =============================================================================
# Excepciones del dominio
# =============================================================================
class ValidacionError(ValueError):
    """Excepción base para errores de validación de entrada."""


class GeometriaInvalidaError(ValidacionError):
    """Geometría del muro inconsistente o fuera de rango razonable."""


class ParametroSueloInvalidoError(ValidacionError):
    """Parámetros geotécnicos inválidos."""


class MaterialInvalidoError(ValidacionError):
    """Propiedades de material (concreto/acero) fuera de rango."""


# =============================================================================
# Validadores genéricos
# =============================================================================
def validar_positivo(valor: float, nombre: str, permitir_cero: bool = False) -> float:
    """Valida que un valor sea estrictamente positivo (o no-negativo).

    Args:
        valor: Valor a validar.
        nombre: Nombre legible del parámetro (para el mensaje de error).
        permitir_cero: Si ``True``, se admite el valor cero.

    Returns:
        El mismo valor, si la validación pasa.

    Raises:
        ValidacionError: Si el valor no cumple.
    """
    if permitir_cero:
        if valor < 0:
            raise ValidacionError(f"{nombre} debe ser >= 0, recibido: {valor}")
    else:
        if valor <= 0:
            raise ValidacionError(f"{nombre} debe ser > 0, recibido: {valor}")
    return float(valor)


def validar_rango(
    valor: float,
    minimo: float,
    maximo: float,
    nombre: str,
    inclusivo: bool = True,
) -> float:
    """Valida que ``valor`` esté en el intervalo dado.

    Args:
        valor: Valor a validar.
        minimo: Límite inferior.
        maximo: Límite superior.
        nombre: Nombre legible del parámetro.
        inclusivo: Si ``True`` admite los extremos.

    Returns:
        El valor validado.

    Raises:
        ValidacionError: Si el valor está fuera de rango.
    """
    if inclusivo:
        ok = minimo <= valor <= maximo
    else:
        ok = minimo < valor < maximo
    if not ok:
        limites = f"[{minimo}, {maximo}]" if inclusivo else f"({minimo}, {maximo})"
        raise ValidacionError(f"{nombre} debe estar en {limites}, recibido: {valor}")
    return float(valor)


def validar_no_nulo(valor: Any, nombre: str) -> Any:
    """Valida que un objeto no sea ``None``."""
    if valor is None:
        raise ValidacionError(f"{nombre} no puede ser None")
    return valor


def validar_tipo(valor: Any, tipos: type | tuple[type, ...], nombre: str) -> Any:
    """Valida que ``valor`` sea instancia de ``tipos``."""
    if not isinstance(valor, tipos):
        esperados = tipos if isinstance(tipos, tuple) else (tipos,)
        nombres = ", ".join(t.__name__ for t in esperados)
        raise ValidacionError(
            f"{nombre} debe ser de tipo {nombres}, recibido: {type(valor).__name__}"
        )
    return valor


# =============================================================================
# Validadores específicos de ingeniería geotécnica / estructural
# =============================================================================
def validar_angulo_friccion(phi_grados: float, nombre: str = "phi") -> float:
    """Valida el ángulo de fricción interna del suelo (0° < φ < 45°).

    Args:
        phi_grados: Ángulo de fricción en grados sexagesimales.
        nombre: Nombre del parámetro para mensajes de error.

    Returns:
        El ángulo validado.

    Raises:
        ParametroSueloInvalidoError: Si está fuera del rango físico razonable.
    """
    if not (0.0 < phi_grados < 45.0):
        raise ParametroSueloInvalidoError(
            f"{nombre} debe estar en (0°, 45°), recibido: {phi_grados}°"
        )
    return float(phi_grados)


def validar_angulo_talud(alpha_grados: float, phi_grados: float) -> float:
    """Valida la inclinación del relleno respecto al ángulo de fricción.

    La teoría de Rankine requiere α < φ para obtener coeficientes reales.

    Args:
        alpha_grados: Inclinación del relleno (grados).
        phi_grados: Ángulo de fricción del suelo retenido (grados).

    Returns:
        El ángulo α validado.

    Raises:
        ParametroSueloInvalidoError: Si α < 0 o α >= φ.
    """
    if alpha_grados < 0:
        raise ParametroSueloInvalidoError(
            f"alpha debe ser >= 0°, recibido: {alpha_grados}°"
        )
    if alpha_grados >= phi_grados:
        raise ParametroSueloInvalidoError(
            f"alpha ({alpha_grados}°) debe ser menor que phi ({phi_grados}°) "
            "para validez de Rankine."
        )
    return float(alpha_grados)


def validar_cohesion(c: float, nombre: str = "c") -> float:
    """Valida cohesión (kPa), debe ser no negativa."""
    return validar_positivo(c, nombre, permitir_cero=True)


def validar_peso_especifico(gamma: float, nombre: str = "gamma") -> float:
    """Valida peso específico (kN/m³): debe ser positivo. Sin cota superior:
    el usuario es responsable de ingresar valores físicamente sensatos."""
    return validar_positivo(gamma, nombre, permitir_cero=False)


def validar_fc(fc_mpa: float) -> float:
    """Valida la resistencia a compresión del concreto f'c (MPa).

    NSR-10 C.1.1.1 exige f'c mínimo de 17 MPa para concreto estructural.
    """
    if fc_mpa < 17.0:
        raise MaterialInvalidoError(
            f"f'c minimo por NSR-10 es 17 MPa, recibido: {fc_mpa} MPa"
        )
    if fc_mpa > 70.0:
        raise MaterialInvalidoError(
            f"f'c > 70 MPa requiere consideraciones especiales; recibido: {fc_mpa} MPa"
        )
    return float(fc_mpa)


def validar_fy(fy_mpa: float) -> float:
    """Valida la resistencia a la fluencia del acero de refuerzo (MPa).

    NSR-10 C.3.5.3 limita fy a 550 MPa para diseño convencional.
    """
    if not (240.0 <= fy_mpa <= 550.0):
        raise MaterialInvalidoError(
            f"fy debe estar en [240, 550] MPa (NSR-10 C.3.5.3), recibido: {fy_mpa} MPa"
        )
    return float(fy_mpa)


def validar_recubrimiento(r_mm: float) -> float:
    """Valida el recubrimiento libre de refuerzo (mm)."""
    return validar_rango(r_mm, 20.0, 150.0, "recubrimiento")


def validar_coleccion_no_vacia(coleccion: Iterable[Any], nombre: str) -> Iterable[Any]:
    """Valida que una colección no esté vacía."""
    items = list(coleccion)
    if not items:
        raise ValidacionError(f"{nombre} no puede estar vacío.")
    return items
