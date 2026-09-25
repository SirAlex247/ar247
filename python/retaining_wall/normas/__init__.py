"""Paquete de normas de diseño.

Cada norma expone sus factores de carga y de resistencia y los criterios de
aceptación, de manera que un mismo módulo de cálculo (muros, zapatas, pilotes,
dados, caissons…) pueda diseñarse por la norma que elija el usuario.

Normas soportadas:
    - NSR-10  (Reglamento Colombiano de Construcción Sismo Resistente).
      El flujo NSR-10 histórico de la app usa esfuerzos admisibles (FS) para la
      estabilidad geotécnica; sus parámetros viven en ``core/estabilidad.py`` y
      ``core/combinaciones.py``.
    - CCP-14  (Norma Colombiana de Diseño de Puentes LRFD-CCP-14, basada en
      AASHTO LRFD). Diseño por estados límite: efectos de carga mayorados frente
      a resistencias afectadas por φ. Ver ``normas/ccp14.py``.

El identificador de norma que viaja en el payload de la app es la cadena
``"NSR10"`` (por defecto) o ``"CCP14"``.
"""
from __future__ import annotations

NORMA_NSR10 = "NSR10"
NORMA_CCP14 = "CCP14"

NORMAS_SOPORTADAS = (NORMA_NSR10, NORMA_CCP14)


def normalizar_norma(valor: str | None) -> str:
    """Normaliza el identificador de norma recibido del payload.

    Acepta variantes comunes ("nsr-10", "ccp 14", "aashto", …) y devuelve
    ``"NSR10"`` o ``"CCP14"``. Cualquier valor no reconocido cae en NSR-10
    (comportamiento histórico por defecto).
    """
    if not valor:
        return NORMA_NSR10
    v = str(valor).strip().upper().replace("-", "").replace(" ", "").replace("_", "")
    if v in ("CCP14", "CCP", "AASHTO", "LRFD", "LRFDCCP14"):
        return NORMA_CCP14
    return NORMA_NSR10
