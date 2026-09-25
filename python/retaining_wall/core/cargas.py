"""
Agregación y categorización de cargas actuantes sobre el muro.

Cada carga individual se clasifica según:
    - **Tipo**: vertical u horizontal.
    - **Categoría NSR-10**: permanente (D), empuje de tierra (H), viva (L),
      sobrecarga-empuje (Lsup), sísmica (E), etc.

Esto permite aplicar luego las combinaciones de carga correctamente.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from ..models.muro import MuroContencion
from .empujes import Empuje, EmpujeSuelo
from .geometria import CalculadoraGeometria, SeccionGeometrica


# =============================================================================
# Enumeraciones
# =============================================================================
class CategoriaCarga(str, Enum):
    """Categorías de carga según nomenclatura NSR-10 Título B."""
    D = "D"          # Permanente (muerta)
    L = "L"          # Viva
    H = "H"          # Empuje lateral de tierra
    Hv = "Hv"        # Componente vertical del empuje de tierra
    F = "F"          # Fluidos / presión hidrostática
    E = "E"          # Sismo
    W = "W"          # Viento
    Lsc = "Lsc"      # Empuje por sobrecarga viva


class TipoCarga(str, Enum):
    VERTICAL = "vertical"
    HORIZONTAL = "horizontal"


# =============================================================================
# Clase de carga individual
# =============================================================================
@dataclass(frozen=True)
class Carga:
    """Una carga concentrada equivalente por metro lineal de muro.

    Attributes:
        nombre:       Descripción legible.
        magnitud:     kN/m (positiva).
        tipo:         Vertical u horizontal.
        categoria:    D, L, H, etc. (NSR-10).
        x_aplicacion: Coordenada x desde el punto C (m), solo para verticales.
        y_aplicacion: Altura sobre la base (m), solo para horizontales.
        sentido:      +1 empuja/pesa hacia el muro; -1 lo resiste (pasivo).
        material:     "concreto", "suelo_relleno", "suelo_cimentacion" o None.
                      Solo lo usan las cargas de peso propio; permite a las
                      normas LRFD (CCP-14) separar DC (concreto) de EV (suelo).
                      No afecta el flujo NSR-10, que trata todo como D.
    """

    nombre: str
    magnitud: float
    tipo: TipoCarga
    categoria: CategoriaCarga
    x_aplicacion: float = 0.0
    y_aplicacion: float = 0.0
    sentido: int = 1
    material: str | None = None

    def momento_respecto_C(self) -> float:
        """Momento de la carga respecto al punto C (puntera).

        Convención: un momento POSITIVO es estabilizador (se opone al volcamiento).
        """
        if self.tipo == TipoCarga.VERTICAL:
            return self.magnitud * self.x_aplicacion * self.sentido
        # Horizontal: produce momento de volcamiento si sentido = +1
        return -self.magnitud * self.y_aplicacion * self.sentido


# =============================================================================
# Contenedor de todas las cargas
# =============================================================================
@dataclass
class SistemaCargas:
    """Conjunto de cargas calculadas para un muro.

    Attributes:
        cargas: Lista completa de cargas.
    """

    cargas: list[Carga] = field(default_factory=list)

    # ------------------------------------------------------------------
    def agregar(self, carga: Carga) -> None:
        self.cargas.append(carga)

    # Acceso por categoría --------------------------------------------
    def por_categoria(self, cat: CategoriaCarga) -> list[Carga]:
        return [c for c in self.cargas if c.categoria == cat]

    def verticales(self) -> list[Carga]:
        return [c for c in self.cargas if c.tipo == TipoCarga.VERTICAL]

    def horizontales(self) -> list[Carga]:
        return [c for c in self.cargas if c.tipo == TipoCarga.HORIZONTAL]

    # Resultantes características (sin mayorar) ------------------------
    def suma_vertical(self) -> float:
        return sum(c.magnitud * c.sentido for c in self.verticales())

    def suma_horizontal_empuje(self) -> float:
        return sum(c.magnitud * c.sentido for c in self.horizontales() if c.sentido > 0)

    def suma_horizontal_resistente(self) -> float:
        return sum(c.magnitud for c in self.horizontales() if c.sentido < 0)

    def momento_estabilizador(self) -> float:
        """Suma de momentos que estabilizan respecto a C (puntera).

        IMPORTANTE — convención conservadora (Braja Das, Bowles, etc.):
        El momento del empuje pasivo Pp **NO se incluye** en el cálculo de
        FS_volcamiento. La razón: Pp puede perderse fácilmente por
        excavaciones futuras frente al muro, erosión, o degradación del
        relleno frontal. Incluirlo da una falsa sensación de seguridad.

        Por tanto, aquí sumamos sólo los momentos producidos por cargas
        VERTICALES con momento positivo respecto a C (peso propio del
        muro, peso del suelo sobre el talón, componente vertical Pv del
        empuje activo). Las cargas horizontales resistentes (Pp en la
        puntera, Pp del diente) se ignoran.
        """
        return sum(
            max(0.0, c.momento_respecto_C())
            for c in self.cargas
            if c.tipo == TipoCarga.VERTICAL
        )

    def momento_volcador(self) -> float:
        """Suma de momentos que provocan volcamiento (valor positivo).

        Sólo cargas horizontales activas (sentido = +1) contribuyen al
        momento de volcamiento respecto a C. Pp (sentido = -1) no aporta.
        """
        return sum(
            -min(0.0, c.momento_respecto_C())
            for c in self.cargas
            if c.tipo == TipoCarga.HORIZONTAL and c.sentido > 0
        )

    # ------------------------------------------------------------------
    # Descomposición fila-a-fila para tablas (cálculo paso a paso)
    # ------------------------------------------------------------------
    def tabla_momentos_estabilizadores(self) -> list[dict]:
        """Devuelve una lista de dicts con el cálculo detallado de cada
        aporte al momento estabilizador respecto a la puntera (punto C).

        Cada fila: ``{nombre, categoria, fuerza, brazo, momento}`` donde
            - fuerza  = magnitud (kN/m)
            - brazo   = x de aplicación (m) para cargas verticales
            - momento = F · x (kN·m/m)
        Sólo se incluyen las cargas VERTICALES con momento positivo
        respecto a C (peso propio, peso del suelo sobre el talón, Pv).
        El empuje pasivo Pp se considera por separado en el análisis de
        deslizamiento, NO en el momento resistente al volcamiento.
        """
        filas: list[dict] = []
        for c in self.cargas:
            if c.tipo != TipoCarga.VERTICAL:
                continue            # Pp y otras horizontales resistentes
            M = c.momento_respecto_C()
            if M <= 0:
                continue
            filas.append({
                "nombre": c.nombre,
                "categoria": c.categoria.value,
                "tipo": "V",
                "fuerza": c.magnitud * c.sentido,
                "brazo": c.x_aplicacion,
                "momento": M,
            })
        return filas

    def tabla_momentos_volcadores(self) -> list[dict]:
        """Lista de dicts con el cálculo detallado de cada aporte al
        momento volcador respecto a C.

        Cada fila: ``{nombre, categoria, fuerza, brazo, momento}`` con
        momento en valor absoluto (positivo).
        """
        filas: list[dict] = []
        for c in self.cargas:
            M = c.momento_respecto_C()
            if M >= 0:
                continue
            # Horizontal activa (empuje, sobrecarga, sismo) → volcador
            filas.append({
                "nombre": c.nombre,
                "categoria": c.categoria.value,
                "tipo": "H",
                "fuerza": c.magnitud,
                "brazo": c.y_aplicacion,
                "momento": -M,   # lo dejamos positivo para la tabla
            })
        return filas


# =============================================================================
# Generador de cargas a partir del muro
# =============================================================================
class CalculadoraCargas:
    """Construye el ``SistemaCargas`` a partir de un ``MuroContencion``."""

    def __init__(self, muro: MuroContencion,
                 metodo_empuje: str = "rankine") -> None:
        """
        Args:
            muro: Muro a analizar.
            metodo_empuje: ``"rankine"`` o ``"coulomb"``.
        """
        self.muro = muro
        self.metodo_empuje = metodo_empuje.lower()
        self._geometria = CalculadoraGeometria(muro)

    # ------------------------------------------------------------------
    def calcular(self, incluir_sismo: bool = False) -> SistemaCargas:
        """Genera todas las cargas características del muro.

        Args:
            incluir_sismo: Si ``True`` adiciona el empuje sísmico (Mononobe-Okabe).

        Returns:
            Instancia de ``SistemaCargas``.
        """
        sistema = SistemaCargas()

        # 1) Pesos propios (concreto y suelo sobre el talón)
        for sec in self._geometria.descomponer():
            categoria = CategoriaCarga.D  # todas son cargas permanentes
            sistema.agregar(Carga(
                nombre=f"W-{sec.nombre}",
                magnitud=sec.peso,
                tipo=TipoCarga.VERTICAL,
                categoria=categoria,
                x_aplicacion=sec.x_cg,
                sentido=+1,
                material=sec.material,   # concreto->DC, suelo->EV (LRFD/CCP-14)
            ))

        # 2) Empuje activo del relleno
        self._agregar_empuje_activo(sistema)

        # 3) Empuje por sobrecarga
        if self.muro.condiciones.sobrecarga > 0:
            self._agregar_empuje_sobrecarga(sistema)

        # 4) Empuje pasivo frente a la puntera (resistente al deslizamiento)
        self._agregar_empuje_pasivo(sistema)

        # 5) Sismo (opcional)
        if incluir_sismo and self.muro.condiciones.kh > 0:
            self._agregar_empuje_sismico(sistema)

        return sistema

    # ------------------------------------------------------------------
    # Helpers privados
    # ------------------------------------------------------------------
    def _agregar_empuje_activo(self, sistema: SistemaCargas) -> None:
        relleno = self.muro.suelo_relleno
        cond = self.muro.condiciones
        H_prima = self._geometria.altura_efectiva_rankine()
        B = self.muro.geometria.B

        if self.metodo_empuje == "rankine":
            emp = EmpujeSuelo.calcular_empuje_activo_rankine(
                gamma=relleno.gamma, H=H_prima, phi_grados=relleno.phi,
                alpha_grados=cond.alpha, cohesion=relleno.cohesion,
            )
            x_vertical = B  # Pv actúa en el plano vertical AB (borde del talón)
        else:
            emp = EmpujeSuelo.calcular_empuje_activo_coulomb(
                gamma=relleno.gamma, H=self.muro.H,
                phi_grados=relleno.phi,
                delta_grados=relleno.delta_efectivo,
                alpha_grados=cond.alpha,
            )
            x_vertical = B  # aproximación; ajustable por geometría

        # Componente horizontal (produce volcamiento)
        sistema.agregar(Carga(
            nombre="Empuje activo (horiz.)",
            magnitud=emp.componente_h,
            tipo=TipoCarga.HORIZONTAL,
            categoria=CategoriaCarga.H,
            y_aplicacion=emp.y_aplicacion,
            sentido=+1,
        ))
        # Componente vertical (estabilizadora)
        if emp.componente_v > 0:
            sistema.agregar(Carga(
                nombre="Empuje activo (vert.)",
                magnitud=emp.componente_v,
                tipo=TipoCarga.VERTICAL,
                categoria=CategoriaCarga.Hv,
                x_aplicacion=x_vertical,
                sentido=+1,
            ))

    def _agregar_empuje_sobrecarga(self, sistema: SistemaCargas) -> None:
        cond = self.muro.condiciones
        relleno = self.muro.suelo_relleno
        H_prima = self._geometria.altura_efectiva_rankine()

        emp = EmpujeSuelo.calcular_empuje_sobrecarga(
            q=cond.sobrecarga, H=H_prima,
            phi_grados=relleno.phi, alpha_grados=cond.alpha,
        )
        sistema.agregar(Carga(
            nombre="Empuje sobrecarga (horiz.)",
            magnitud=emp.componente_h,
            tipo=TipoCarga.HORIZONTAL,
            categoria=CategoriaCarga.Lsc,
            y_aplicacion=emp.y_aplicacion,
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
            sentido=-1,   # resiste
        ))

    def _agregar_empuje_sismico(self, sistema: SistemaCargas) -> None:
        relleno = self.muro.suelo_relleno
        cond = self.muro.condiciones

        # Componente total Pae
        emp_est = EmpujeSuelo.calcular_empuje_activo_rankine(
            gamma=relleno.gamma, H=self._geometria.altura_efectiva_rankine(),
            phi_grados=relleno.phi, alpha_grados=cond.alpha,
        )
        emp_sis = EmpujeSuelo.calcular_empuje_sismico(
            gamma=relleno.gamma, H=self._geometria.altura_efectiva_rankine(),
            phi_grados=relleno.phi,
            delta_grados=relleno.delta_efectivo,
            beta_grados=90.0,
            alpha_grados=cond.alpha,
            kh=cond.kh, kv=cond.kv,
        )
        # Incremento dinámico = Pae - Pa
        delta_P = max(0.0, emp_sis.componente_h - emp_est.componente_h)
        sistema.agregar(Carga(
            nombre="Empuje sísmico (incremento)",
            magnitud=delta_P,
            tipo=TipoCarga.HORIZONTAL,
            categoria=CategoriaCarga.E,
            y_aplicacion=emp_sis.y_aplicacion,
            sentido=+1,
        ))
