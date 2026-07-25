"""
Combinaciones de carga conforme a NSR-10 (Título B, Capítulo B.2).

Para muros de contención, las combinaciones aplicables son las del numeral
B.2.4 (método de resistencia LRFD) y B.2.3 (método de esfuerzos admisibles
para verificaciones geotécnicas de estabilidad).

Convención NSR-10 para categorías de carga usadas aquí:
    D   : carga muerta (peso propio, suelo retenido)
    L   : carga viva sobre la estructura
    H   : empuje lateral de tierra / fluidos
    Lsc : empuje por sobrecarga viva sobre el relleno
    E   : sismo
    W   : viento
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping

from .cargas import Carga, CategoriaCarga, SistemaCargas, TipoCarga


class EstadoLimite(str, Enum):
    ELU = "ELU"       # Estado límite último (diseño estructural)
    ELS = "ELS"       # Estado límite de servicio
    EGEO = "EGEO"     # Estado de verificaciones geotécnicas (sin mayorar)


# =============================================================================
# Definición de una combinación
# =============================================================================
@dataclass(frozen=True)
class CombinacionCarga:
    """Representa una combinación con factores de mayoración.

    Attributes:
        nombre:        Identificador (p.ej. "1.2D + 1.6H + 1.6Lsc").
        estado_limite: ELU, ELS o EGEO.
        factores:      Mapeo categoría -> factor. Categorías no listadas se
                       consideran con factor cero.
    """

    nombre: str
    estado_limite: EstadoLimite
    factores: Mapping[CategoriaCarga, float]

    def factor(self, categoria: CategoriaCarga) -> float:
        return float(self.factores.get(categoria, 0.0))


# =============================================================================
# Resultado de aplicar una combinación
# =============================================================================
@dataclass
class CargasFactoradas:
    """Totales ya mayorados según una combinación.

    Attributes:
        combinacion:      Combinación aplicada.
        V_total:          Suma vertical mayorada (kN/m).
        H_total:          Suma horizontal mayorada (empuje, kN/m).
        H_resistente:     Suma horizontal resistente mayorada (kN/m).
        M_estabilizador:  Momento estabilizador mayorado (kN·m/m).
        M_volcador:       Momento volcador mayorado (kN·m/m).
        cargas_detalle:   Lista de (Carga, factor) aplicados.
    """

    combinacion: CombinacionCarga
    V_total: float
    H_total: float
    H_resistente: float
    M_estabilizador: float
    M_volcador: float
    cargas_detalle: list[tuple[Carga, float]] = field(default_factory=list)


# =============================================================================
# Combinaciones NSR-10
# =============================================================================
class CombinacionesNSR10:
    """Combinaciones estándar del Reglamento NSR-10."""

    # ---------- ELU (B.2.4) ----------
    @staticmethod
    def elu() -> list[CombinacionCarga]:
        """Combinaciones para estado límite último (resistencia).

        Adaptado de NSR-10 B.2.4 para muros de contención:
            B-1 : 1.4 D + 1.4 H
            B-2 : 1.2 D + 1.6 L + 1.6 Lsc + 1.6 H
            B-5 : 1.2 D + 1.0 E + 1.0 L + 1.0 H
            B-6 : 0.9 D + 1.0 E + 0.9 H
        """
        return [
            CombinacionCarga(
                nombre="B-1: 1.4(D+H)",
                estado_limite=EstadoLimite.ELU,
                factores={
                    CategoriaCarga.D: 1.4,
                    CategoriaCarga.Hv: 1.4,
                    CategoriaCarga.H: 1.4,
                },
            ),
            CombinacionCarga(
                nombre="B-2: 1.2D + 1.6L + 1.6Lsc + 1.6H",
                estado_limite=EstadoLimite.ELU,
                factores={
                    CategoriaCarga.D: 1.2,
                    CategoriaCarga.Hv: 1.2,
                    CategoriaCarga.L: 1.6,
                    CategoriaCarga.Lsc: 1.6,
                    CategoriaCarga.H: 1.6,
                },
            ),
            CombinacionCarga(
                nombre="B-5: 1.2D + 1.0E + 1.0L + 1.0H",
                estado_limite=EstadoLimite.ELU,
                factores={
                    CategoriaCarga.D: 1.2,
                    CategoriaCarga.Hv: 1.2,
                    CategoriaCarga.L: 1.0,
                    CategoriaCarga.Lsc: 1.0,
                    CategoriaCarga.H: 1.0,
                    CategoriaCarga.E: 1.0,
                },
            ),
            CombinacionCarga(
                nombre="B-6: 0.9D + 1.0E + 0.9H",
                estado_limite=EstadoLimite.ELU,
                factores={
                    CategoriaCarga.D: 0.9,
                    CategoriaCarga.Hv: 0.9,
                    CategoriaCarga.H: 0.9,
                    CategoriaCarga.E: 1.0,
                },
            ),
        ]

    # ---------- ELS (B.2.3) ----------
    @staticmethod
    def els() -> list[CombinacionCarga]:
        """Combinaciones de servicio (deflexiones, fisuración)."""
        return [
            CombinacionCarga(
                nombre="S-1: D + H + L + Lsc",
                estado_limite=EstadoLimite.ELS,
                factores={
                    CategoriaCarga.D: 1.0,
                    CategoriaCarga.Hv: 1.0,
                    CategoriaCarga.H: 1.0,
                    CategoriaCarga.L: 1.0,
                    CategoriaCarga.Lsc: 1.0,
                },
            ),
            CombinacionCarga(
                nombre="S-2: D + 0.7E + H",
                estado_limite=EstadoLimite.ELS,
                factores={
                    CategoriaCarga.D: 1.0,
                    CategoriaCarga.Hv: 1.0,
                    CategoriaCarga.H: 1.0,
                    CategoriaCarga.E: 0.7,
                },
            ),
        ]

    # ---------- Verificación geotécnica (sin factores) ----------
    @staticmethod
    def geotecnica() -> list[CombinacionCarga]:
        """Combinación sin mayorar para verificar FS geotécnicos."""
        return [
            CombinacionCarga(
                nombre="GEO-1: D + H + Lsc  (característica)",
                estado_limite=EstadoLimite.EGEO,
                factores={
                    CategoriaCarga.D: 1.0,
                    CategoriaCarga.Hv: 1.0,
                    CategoriaCarga.H: 1.0,
                    CategoriaCarga.Lsc: 1.0,
                    CategoriaCarga.L: 1.0,
                },
            ),
            CombinacionCarga(
                nombre="GEO-2: D + H + E (sismo)",
                estado_limite=EstadoLimite.EGEO,
                factores={
                    CategoriaCarga.D: 1.0,
                    CategoriaCarga.Hv: 1.0,
                    CategoriaCarga.H: 1.0,
                    CategoriaCarga.E: 1.0,
                },
            ),
        ]


# =============================================================================
# Aplicador de combinaciones
# =============================================================================
class AplicadorCombinaciones:
    """Aplica una combinación a un ``SistemaCargas``."""

    @staticmethod
    def aplicar(
        combinacion: CombinacionCarga,
        sistema: SistemaCargas,
    ) -> CargasFactoradas:
        """Mayoriza todas las cargas y calcula resultantes.

        Args:
            combinacion: Combinación a aplicar.
            sistema:     Conjunto de cargas características.

        Returns:
            ``CargasFactoradas`` con los totales ya mayorados.
        """
        V_total = 0.0
        H_emp = 0.0
        H_res = 0.0
        M_estab = 0.0
        M_volc = 0.0
        detalle: list[tuple[Carga, float]] = []

        for carga in sistema.cargas:
            factor = combinacion.factor(carga.categoria)
            if factor == 0.0:
                continue
            detalle.append((carga, factor))

            if carga.tipo == TipoCarga.VERTICAL:
                V_total += factor * carga.magnitud * carga.sentido
            else:
                if carga.sentido > 0:
                    H_emp += factor * carga.magnitud
                else:
                    H_res += factor * carga.magnitud

            m = carga.momento_respecto_C() * factor
            if m > 0:
                M_estab += m
            else:
                M_volc += -m

        return CargasFactoradas(
            combinacion=combinacion,
            V_total=V_total,
            H_total=H_emp,
            H_resistente=H_res,
            M_estabilizador=M_estab,
            M_volcador=M_volc,
            cargas_detalle=detalle,
        )

    @staticmethod
    def aplicar_todas(
        combinaciones: list[CombinacionCarga],
        sistema: SistemaCargas,
    ) -> list[CargasFactoradas]:
        """Aplica una lista de combinaciones."""
        return [AplicadorCombinaciones.aplicar(c, sistema) for c in combinaciones]

    @staticmethod
    def envolvente_critica(
        resultados: list[CargasFactoradas],
        variable: str = "M_volcador",
    ) -> CargasFactoradas:
        """Devuelve la combinación más crítica según la variable indicada."""
        if not resultados:
            raise ValueError("Lista de resultados vacía.")
        return max(resultados, key=lambda r: getattr(r, variable))
