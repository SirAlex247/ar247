"""
Parámetros sísmicos según NSR-10 para diseño de muros de contención.

Aa : Coeficiente de aceleración horizontal pico efectiva (A.2.2).
Av : Coeficiente de velocidad horizontal pico efectiva (A.2.2).
Fa : Coeficiente de amplificación por efecto de sitio en zona de periodos cortos.
Fv : Coeficiente de amplificación por efecto de sitio en zona de periodos intermedios.

Coeficientes sísmicos para diseño de muros (A.10):
    Caso 1 (acepta desplazamiento - Richards-Elms):
        kh = Fa · Aa / 2
        kv = 0
    Caso 2 (no acepta desplazamiento):
        kh = kv = 0.6 · Fa · Aa

Tipos de perfil de suelo NSR-10 A.2.4:
    A : Roca dura
    B : Roca
    C : Suelo muy denso o roca blanda
    D : Suelo rígido  (más común en Colombia)
    E : Suelo blando
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class TipoSueloNSR10(str, Enum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    E = "E"


# -----------------------------------------------------------------------------
# Tablas Fa y Fv (NSR-10 Tabla A.2.4-3 y A.2.4-4)
# -----------------------------------------------------------------------------
# Fa como función de Aa y tipo de perfil
_TABLA_FA = {
    TipoSueloNSR10.A: {0.1: 0.8, 0.2: 0.8, 0.3: 0.8, 0.4: 0.8, 0.5: 0.8},
    TipoSueloNSR10.B: {0.1: 1.0, 0.2: 1.0, 0.3: 1.0, 0.4: 1.0, 0.5: 1.0},
    TipoSueloNSR10.C: {0.1: 1.2, 0.2: 1.2, 0.3: 1.1, 0.4: 1.0, 0.5: 1.0},
    TipoSueloNSR10.D: {0.1: 1.6, 0.2: 1.4, 0.3: 1.2, 0.4: 1.1, 0.5: 1.0},
    TipoSueloNSR10.E: {0.1: 2.5, 0.2: 1.7, 0.3: 1.2, 0.4: 0.9, 0.5: 0.9},
}

# Fv como función de Av y tipo de perfil
_TABLA_FV = {
    TipoSueloNSR10.A: {0.1: 0.8, 0.2: 0.8, 0.3: 0.8, 0.4: 0.8, 0.5: 0.8},
    TipoSueloNSR10.B: {0.1: 1.0, 0.2: 1.0, 0.3: 1.0, 0.4: 1.0, 0.5: 1.0},
    TipoSueloNSR10.C: {0.1: 1.7, 0.2: 1.6, 0.3: 1.5, 0.4: 1.4, 0.5: 1.3},
    TipoSueloNSR10.D: {0.1: 2.4, 0.2: 2.0, 0.3: 1.8, 0.4: 1.6, 0.5: 1.5},
    TipoSueloNSR10.E: {0.1: 3.5, 0.2: 3.2, 0.3: 2.8, 0.4: 2.4, 0.5: 2.4},
}


def _interpolar(tabla: dict[float, float], valor: float) -> float:
    """Interpolación lineal en tabla de valores ordenados."""
    claves = sorted(tabla.keys())
    if valor <= claves[0]:
        return tabla[claves[0]]
    if valor >= claves[-1]:
        return tabla[claves[-1]]
    for i in range(len(claves) - 1):
        if claves[i] <= valor <= claves[i + 1]:
            x0, x1 = claves[i], claves[i + 1]
            y0, y1 = tabla[x0], tabla[x1]
            return y0 + (y1 - y0) * (valor - x0) / (x1 - x0)
    return tabla[claves[-1]]


def calcular_Fa(Aa: float, tipo_suelo: TipoSueloNSR10 | str) -> float:
    """Calcula Fa por interpolación en Tabla A.2.4-3 NSR-10."""
    t = TipoSueloNSR10(tipo_suelo)
    return _interpolar(_TABLA_FA[t], Aa)


def calcular_Fv(Av: float, tipo_suelo: TipoSueloNSR10 | str) -> float:
    """Calcula Fv por interpolación en Tabla A.2.4-4 NSR-10."""
    t = TipoSueloNSR10(tipo_suelo)
    return _interpolar(_TABLA_FV[t], Av)


# -----------------------------------------------------------------------------
# Coeficientes sísmicos kh, kv para muros
# -----------------------------------------------------------------------------
@dataclass(frozen=True)
class ParametrosSismicosNSR10:
    """Parámetros sísmicos del proyecto según NSR-10."""
    Aa: float                              # g
    Av: float                              # g
    tipo_suelo: TipoSueloNSR10             # perfil de sitio
    permite_desplazamiento: bool = True    # True -> kh = Fa·Aa/2

    def __post_init__(self) -> None:
        if not (0.0 <= self.Aa <= 0.5):
            raise ValueError(f"Aa fuera de rango NSR-10 [0, 0.5]: {self.Aa}")
        if not (0.0 <= self.Av <= 0.5):
            raise ValueError(f"Av fuera de rango NSR-10 [0, 0.5]: {self.Av}")

    @property
    def Fa(self) -> float:
        return calcular_Fa(self.Aa, self.tipo_suelo)

    @property
    def Fv(self) -> float:
        return calcular_Fv(self.Av, self.tipo_suelo)

    @property
    def A_max(self) -> float:
        """Aceleración máxima efectiva A_max = Fa·Aa (g)."""
        return self.Fa * self.Aa

    @property
    def kh(self) -> float:
        """Coeficiente sísmico horizontal para el muro."""
        if self.permite_desplazamiento:
            return self.A_max / 2.0
        return 0.6 * self.A_max

    @property
    def kv(self) -> float:
        """Coeficiente sísmico vertical (normalmente 0)."""
        if self.permite_desplazamiento:
            return 0.0
        return 0.6 * self.A_max

    def resumen(self, norma: str = "NSR10") -> dict:
        """Dict con los parámetros sísmicos para reportar en tablas.

        La nomenclatura se adapta a la norma:
          - NSR-10: Aa, Av, Fa, Fv, A_max = Fa·Aa (Título A).
          - CCP-14 (LRFD-AASHTO, Art. 3.10): los mismos valores calculados se
            presentan como PGA, Fpga y As = Fpga·PGA (no se listan Av/Fv, que
            son del espectro y no intervienen en el análisis Mononobe-Okabe del
            muro). El coeficiente pico se toma de la misma zonación sísmica.
        """
        v = str(norma or "").upper().replace("-", "")
        if v in ("CCP14", "CCP", "AASHTO", "LRFD", "LRFDCCP14"):
            return {
                "PGA (coef. de aceleración pico del terreno)": self.Aa,
                "Clase de sitio": self.tipo_suelo.value,
                "Fpga (factor de sitio para PGA)": round(self.Fa, 3),
                "As = Fpga·PGA (g)": round(self.A_max, 3),
                "kh (horizontal)": round(self.kh, 4),
                "kv (vertical)": round(self.kv, 4),
                "Método": ("Desplazamiento admisible — kh = As/2 (Richards-Elms)"
                           if self.permite_desplazamiento
                           else "Sin desplazamiento — kh = 0.6·As"),
            }
        return {
            "Aa": self.Aa,
            "Av": self.Av,
            "Tipo de suelo": self.tipo_suelo.value,
            "Fa": round(self.Fa, 3),
            "Fv": round(self.Fv, 3),
            "A_max = Fa·Aa (g)": round(self.A_max, 3),
            "kh (horizontal)": round(self.kh, 4),
            "kv (vertical)": round(self.kv, 4),
            "Método": ("Richards-Elms (con desplazamiento)"
                       if self.permite_desplazamiento
                       else "Sin desplazamiento (conservador)"),
        }
