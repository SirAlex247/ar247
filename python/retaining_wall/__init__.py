"""
retaining_wall
==============

Sistema modular para el diseño y verificación de muros de contención
conforme a la Norma Sismo Resistente Colombiana NSR-10.

Organización:
    models/   : Entidades de dominio (geometría, suelos, materiales).
    core/     : Motores de cálculo (empujes, estabilidad, diseño).
    utils/    : Unidades y validaciones.

Ejemplo rápido:
    >>> from retaining_wall import MuroContencion, GeometriaMuro, Suelo
    >>> from retaining_wall import MaterialesComunes, AnalisisEstabilidad
"""

from .core.cargas import (
    CalculadoraCargas, Carga, CategoriaCarga, SistemaCargas, TipoCarga,
)
from .core.combinaciones import (
    AplicadorCombinaciones, CargasFactoradas, CombinacionCarga,
    CombinacionesNSR10, EstadoLimite,
)
from .core.diseno_estructural import (
    DisenadorMuroVoladizo, DisenoCortante, DisenoElemento,
    DisenoFlexion, DisenoSeccion, ReporteDiseno,
)
from .core.empujes import Empuje, EmpujeSuelo
from .core.estabilidad import (
    AnalisisEstabilidad, EstadoVerificacion, ReporteEstabilidad,
    ResultadoVerificacion,
)
from .core.geometria import CalculadoraGeometria, SeccionGeometrica
from .core.suelos import FactoresCapacidadCarga, PropiedadesSuelo
from .models.material import AceroRefuerzo, Concreto, MaterialesComunes
from .models.muro import (
    CondicionesCarga, GeometriaMuro, MuroContencion, TipoMuro,
)
from .models.suelo import Suelo

__version__ = "1.0.0"

__all__ = [
    # Modelos
    "MuroContencion", "GeometriaMuro", "CondicionesCarga", "TipoMuro",
    "Suelo", "Concreto", "AceroRefuerzo", "MaterialesComunes",
    # Cargas y combinaciones
    "Carga", "CategoriaCarga", "TipoCarga", "SistemaCargas",
    "CalculadoraCargas", "CombinacionCarga", "CombinacionesNSR10",
    "AplicadorCombinaciones", "CargasFactoradas", "EstadoLimite",
    # Empujes
    "Empuje", "EmpujeSuelo",
    # Estabilidad
    "AnalisisEstabilidad", "ResultadoVerificacion", "ReporteEstabilidad",
    "EstadoVerificacion",
    # Geometría / suelos
    "CalculadoraGeometria", "SeccionGeometrica",
    "PropiedadesSuelo", "FactoresCapacidadCarga",
    # Diseño estructural
    "DisenadorMuroVoladizo", "DisenoSeccion", "DisenoFlexion",
    "DisenoCortante", "DisenoElemento", "ReporteDiseno",
]
