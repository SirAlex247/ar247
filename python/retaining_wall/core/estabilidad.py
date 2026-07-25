"""
Verificaciones de estabilidad global del muro de contención.

Estados verificados (con cargas SIN mayorar, según práctica geotécnica):
    1. Volcamiento respecto a la puntera (FS >= 2.0).
    2. Deslizamiento a lo largo de la base (FS >= 1.5).
    3. Capacidad de carga del suelo de fundación (FS >= 3.0).
    4. Excentricidad admisible (|e| <= B/6).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Literal

from ..models.muro import MuroContencion
from .cargas import SistemaCargas
from .suelos import PropiedadesSuelo


# =============================================================================
# Resultado de una verificación
# =============================================================================
class EstadoVerificacion(str, Enum):
    CUMPLE = "CUMPLE"
    NO_CUMPLE = "NO CUMPLE"


@dataclass
class ResultadoVerificacion:
    """Resultado estándar de una verificación de estabilidad."""
    verificacion: str
    valor_calculado: float
    valor_requerido: float
    unidades: str
    estado: EstadoVerificacion
    detalle: dict = field(default_factory=dict)

    @property
    def cumple(self) -> bool:
        return self.estado == EstadoVerificacion.CUMPLE

    def __str__(self) -> str:
        simbolo = "✓" if self.cumple else "✗"
        return (f"{simbolo} {self.verificacion}: "
                f"{self.valor_calculado:.3f} {self.unidades} "
                f"(req. {self.valor_requerido}) -> {self.estado.value}")


@dataclass
class ReporteEstabilidad:
    """Agrupa todos los resultados de las verificaciones."""
    volcamiento: ResultadoVerificacion
    deslizamiento: ResultadoVerificacion
    capacidad_carga: ResultadoVerificacion
    excentricidad: ResultadoVerificacion
    presiones: dict = field(default_factory=dict)

    @property
    def cumple_todas(self) -> bool:
        return all(r.cumple for r in (
            self.volcamiento, self.deslizamiento,
            self.capacidad_carga, self.excentricidad,
        ))

    def resumen(self) -> str:
        lineas = [
            "=" * 65,
            "REPORTE DE ESTABILIDAD",
            "=" * 65,
            str(self.volcamiento),
            str(self.deslizamiento),
            str(self.capacidad_carga),
            str(self.excentricidad),
            "-" * 65,
            f"Estado global: {'CUMPLE ✓' if self.cumple_todas else 'REVISAR ✗'}",
            "=" * 65,
        ]
        return "\n".join(lineas)


# =============================================================================
# Analizador
# =============================================================================
class AnalisisEstabilidad:
    """Realiza todas las verificaciones de estabilidad sobre un muro.

    Factores de seguridad mínimos (valores clásicos; pueden sobreescribirse):
        FS_volcamiento  = 2.0
        FS_deslizamiento = 1.5
        FS_capacidad    = 3.0
    """

    FS_VOLCAMIENTO_MIN = 2.0
    FS_DESLIZAMIENTO_MIN = 1.5
    FS_CAPACIDAD_MIN = 3.0

    def __init__(
        self,
        muro: MuroContencion,
        sistema_cargas: SistemaCargas,
        k1_friccion: float = 2.0 / 3.0,
        k2_adherencia: float = 2.0 / 3.0,
        incluir_empuje_pasivo: bool = True,
    ) -> None:
        """
        Args:
            muro: Muro a analizar.
            sistema_cargas: Cargas características (sin mayorar).
            k1_friccion: Factor de reducción δ = k1·φ₂ (NSR-10 recomienda 1/2 a 2/3).
            k2_adherencia: Factor de reducción c_a = k2·c₂.
            incluir_empuje_pasivo: Si se considera Pp al deslizamiento.
        """
        self.muro = muro
        self.cargas = sistema_cargas
        self.k1 = k1_friccion
        self.k2 = k2_adherencia
        self.incluir_pp = incluir_empuje_pasivo

    # ==================================================================
    # VOLCAMIENTO
    # ==================================================================
    def verificar_volcamiento(self) -> ResultadoVerificacion:
        """FS volcamiento = ΣMR / ΣMo."""
        MR = self.cargas.momento_estabilizador()
        Mo = self.cargas.momento_volcador()

        FS = MR / Mo if Mo > 0 else 9999.0
        estado = (EstadoVerificacion.CUMPLE if FS >= self.FS_VOLCAMIENTO_MIN
                  else EstadoVerificacion.NO_CUMPLE)

        return ResultadoVerificacion(
            verificacion="Factor de Seguridad al Volcamiento",
            valor_calculado=FS,
            valor_requerido=self.FS_VOLCAMIENTO_MIN,
            unidades="-",
            estado=estado,
            detalle={
                "SM_R": MR, "SM_o": Mo,
                "referencia": ("Estabilidad al volcamiento, FS ≥ 2.0. "
                               "Marco: NSR-10 Título H (geotecnia/cimentaciones). "
                               "Base teórica: Braja Das, cap. 8."),
            },
        )

    # ==================================================================
    # DESGLOSE DE DESLIZAMIENTO (para tablas detalladas)
    # ==================================================================
    def tabla_deslizamiento(self) -> dict:
        """Devuelve la descomposición paso a paso del FS al deslizamiento.

        Estructura:
            {
                "parametros":  [...]   # φ2, δ, c2, ca, B, k1, k2
                "fuerzas_resistentes":  [filas con descripcion, formula, valor]
                "fuerzas_actuantes":    [filas con descripcion, formula, valor]
                "totales": {F_resistente, F_actuante, FS, FS_min}
            }
        Todas las fuerzas en kN/m, en SI.
        """
        cim = self.muro.suelo_cimentacion
        g = self.muro.geometria
        B = self.muro.B

        SV = self.cargas.suma_vertical()
        H_empuje = self.cargas.suma_horizontal_empuje()
        Pp_resistente = self.cargas.suma_horizontal_resistente()

        delta_deg = self.k1 * cim.phi       # ángulo de fricción muro-suelo
        delta_rad = math.radians(delta_deg)
        tan_delta = math.tan(delta_rad)
        ca = self.k2 * cim.cohesion         # adherencia efectiva

        F_friccion = SV * tan_delta
        F_adherencia = B * ca

        Pp = Pp_resistente if self.incluir_pp else 0.0

        # Empuje pasivo adicional por diente de cortante
        Pp_diente = 0.0
        detalle_diente = None
        if g.tiene_diente:
            from .empujes import EmpujeSuelo
            H_sin = g.D
            H_con = g.D + g.h_diente
            emp_sin = EmpujeSuelo.calcular_empuje_pasivo_rankine(
                gamma=cim.gamma, H=H_sin,
                phi_grados=cim.phi, cohesion=cim.cohesion,
            )
            emp_con = EmpujeSuelo.calcular_empuje_pasivo_rankine(
                gamma=cim.gamma, H=H_con,
                phi_grados=cim.phi, cohesion=cim.cohesion,
            )
            Pp_diente = max(0.0, emp_con.componente_h - emp_sin.componente_h)
            detalle_diente = {
                "H_sin_diente": H_sin,
                "H_con_diente": H_con,
                "Pp_sin": emp_sin.componente_h,
                "Pp_con": emp_con.componente_h,
            }

        F_resistente = F_friccion + F_adherencia + Pp + Pp_diente
        FS = F_resistente / H_empuje if H_empuje > 0 else 9999.0

        parametros = [
            {"nombre": "φ (fricción del suelo de cimentación)",
             "valor": cim.phi, "unidad": "°"},
            {"nombre": "k1 (factor de reducción de φ)",
             "valor": self.k1, "unidad": "-"},
            {"nombre": "δ = k1·φ (fricción muro-suelo)",
             "valor": delta_deg, "unidad": "°"},
            {"nombre": "c' (cohesión del suelo de cimentación)",
             "valor": cim.cohesion, "unidad": "kPa"},
            {"nombre": "k2 (factor de reducción de c)",
             "valor": self.k2, "unidad": "-"},
            {"nombre": "c_a = k2·c' (adherencia base-suelo)",
             "valor": ca, "unidad": "kPa"},
            {"nombre": "B (ancho de la zapata)",
             "valor": B, "unidad": "m"},
        ]

        fuerzas_resistentes = [
            {"nombre": "Fricción en la base",
             "formula": "ΣV · tan(δ)",
             "detalle": f"{SV:.2f} × tan({delta_deg:.2f}°) = {SV:.2f} × {tan_delta:.4f}",
             "valor": F_friccion},
            {"nombre": "Adherencia en la base",
             "formula": "B · c_a",
             "detalle": f"{B:.2f} × {ca:.2f}",
             "valor": F_adherencia},
        ]
        if self.incluir_pp and Pp > 0:
            fuerzas_resistentes.append({
                "nombre": "Empuje pasivo en la puntera",
                "formula": "P_p (Rankine)",
                "detalle": "(hasta la profundidad de desplante D)",
                "valor": Pp})
        if g.tiene_diente and Pp_diente > 0:
            fuerzas_resistentes.append({
                "nombre": "Empuje pasivo adicional por diente",
                "formula": "P_p(D+h_d) − P_p(D)",
                "detalle": (f"{detalle_diente['Pp_con']:.2f} − "
                            f"{detalle_diente['Pp_sin']:.2f}"),
                "valor": Pp_diente})

        fuerzas_actuantes = [
            {"nombre": "Empuje activo + sobrecarga + sismo (horizontal)",
             "formula": "ΣH",
             "detalle": "Suma de componentes horizontales actuantes",
             "valor": H_empuje},
        ]

        return {
            "parametros": parametros,
            "fuerzas_resistentes": fuerzas_resistentes,
            "fuerzas_actuantes": fuerzas_actuantes,
            "totales": {
                "F_resistente": F_resistente,
                "F_actuante": H_empuje,
                "FS": FS,
                "FS_min": self.FS_DESLIZAMIENTO_MIN,
            },
        }

    # ==================================================================
    # DESLIZAMIENTO
    # ==================================================================
    def verificar_deslizamiento(self) -> ResultadoVerificacion:
        """FS deslizamiento = (ΣV·tan(k1·φ₂) + B·k2·c₂ + Pp + Pp_diente) / (Pa·cos α).

        Si el muro tiene diente de cortante, se agrega el empuje pasivo
        adicional movilizado sobre el plano frontal del diente (Rankine).
        """
        cim = self.muro.suelo_cimentacion
        g = self.muro.geometria
        B = self.muro.B

        SV = self.cargas.suma_vertical()
        H_empuje = self.cargas.suma_horizontal_empuje()

        phi_rad = math.radians(self.k1 * cim.phi)
        F_friccion = SV * math.tan(phi_rad)
        F_adherencia = B * self.k2 * cim.cohesion

        Pp = 0.0
        if self.incluir_pp:
            Pp = self.cargas.suma_horizontal_resistente()

        # Empuje pasivo adicional por el diente de cortante.
        # El diente profundiza el plano de falla hasta D + h_diente,
        # incrementando el empuje pasivo disponible.
        Pp_diente = 0.0
        if g.tiene_diente:
            from .empujes import EmpujeSuelo
            H_sin_diente = g.D
            H_con_diente = g.D + g.h_diente
            emp_sin = EmpujeSuelo.calcular_empuje_pasivo_rankine(
                gamma=cim.gamma, H=H_sin_diente,
                phi_grados=cim.phi, cohesion=cim.cohesion,
            )
            emp_con = EmpujeSuelo.calcular_empuje_pasivo_rankine(
                gamma=cim.gamma, H=H_con_diente,
                phi_grados=cim.phi, cohesion=cim.cohesion,
            )
            Pp_diente = max(0.0, emp_con.componente_h - emp_sin.componente_h)

        F_resistente = F_friccion + F_adherencia + Pp + Pp_diente
        FS = F_resistente / H_empuje if H_empuje > 0 else 9999.0

        estado = (EstadoVerificacion.CUMPLE if FS >= self.FS_DESLIZAMIENTO_MIN
                  else EstadoVerificacion.NO_CUMPLE)

        detalle = {
            "SV": SV, "H_empuje": H_empuje,
            "F_friccion": F_friccion, "F_adherencia": F_adherencia, "Pp": Pp,
            "referencia": ("Estabilidad al deslizamiento, FS ≥ 1.5. "
                           "Marco: NSR-10 Título H (geotecnia/cimentaciones). "
                           "Base teórica: Braja Das, cap. 8."),
        }
        if g.tiene_diente:
            detalle["Pp_diente"] = Pp_diente

        return ResultadoVerificacion(
            verificacion="Factor de Seguridad al Deslizamiento",
            valor_calculado=FS,
            valor_requerido=self.FS_DESLIZAMIENTO_MIN,
            unidades="-",
            estado=estado,
            detalle=detalle,
        )

    # ==================================================================
    # EXCENTRICIDAD
    # ==================================================================
    def _calcular_excentricidad(self) -> tuple[float, float, float]:
        """Calcula excentricidad e y posición CE.

        Returns:
            (CE, e, B/6)
        """
        SV = self.cargas.suma_vertical()
        M_neto = (self.cargas.momento_estabilizador()
                  - self.cargas.momento_volcador())
        CE = M_neto / SV if SV > 0 else 0.0
        B = self.muro.B
        e = B / 2.0 - CE
        return CE, e, B / 6.0

    def verificar_excentricidad(self) -> ResultadoVerificacion:
        """|e| <= B/6 para evitar tensiones en el talón."""
        CE, e, limite = self._calcular_excentricidad()
        estado = (EstadoVerificacion.CUMPLE if abs(e) <= limite
                  else EstadoVerificacion.NO_CUMPLE)

        return ResultadoVerificacion(
            verificacion="Excentricidad |e| ≤ B/6",
            valor_calculado=abs(e),
            valor_requerido=limite,
            unidades="m",
            estado=estado,
            detalle={
                "CE": CE, "e": e, "B/6": limite,
                "referencia": ("Resultante dentro del núcleo central |e| ≤ B/6, "
                               "para evitar tracciones en la base. "
                               "Base teórica: Braja Das, cap. 8."),
            },
        )

    # ==================================================================
    # DESGLOSE DE EXCENTRICIDAD (para tabla detallada)
    # ==================================================================
    def tabla_excentricidad(self) -> dict:
        """Devuelve la descomposición paso a paso de la excentricidad.

        La excentricidad mide qué tan descentrada queda la resultante
        vertical respecto al eje de la base. Se calcula como:

            CE = (ΣM_R − ΣM_o) / ΣV         (posición de la resultante
                                              desde la puntera)
            e  = B/2 − CE                    (desplazamiento respecto al
                                              centro de la base)
            |e| ≤ B/6                        (condición de no-tensión)

        Estructura devuelta (misma forma que ``tabla_deslizamiento`` y
        ``tabla_capacidad_carga``): parametros, pasos, totales.
        Todas las fuerzas/momentos en SI (kN/m, kN·m/m, m).
        """
        B = self.muro.B
        SV = self.cargas.suma_vertical()
        SMR = self.cargas.momento_estabilizador()
        SMo = self.cargas.momento_volcador()
        M_neto = SMR - SMo
        CE = M_neto / SV if SV > 0 else 0.0
        e = B / 2.0 - CE
        limite = B / 6.0
        absE = abs(e)
        estado = "CUMPLE" if absE <= limite else "NO CUMPLE"
        # Observación sobre la dirección de la excentricidad
        if abs(e) < 1e-9:
            lado = "coincide con el eje central (excentricidad nula)"
        elif e > 0:
            lado = "hacia la puntera (resultante al frente del centro)"
        else:
            lado = "hacia el talón (resultante detrás del centro)"

        return {
            "parametros": [
                {"nombre": "B (ancho total de la zapata)",
                 "valor": B, "unidad": "m"},
                {"nombre": "ΣV (suma de cargas verticales)",
                 "valor": SV, "unidad": "kN/m"},
                {"nombre": "ΣM_R (momento estabilizador)",
                 "valor": SMR, "unidad": "kN·m/m"},
                {"nombre": "ΣM_o (momento volcador)",
                 "valor": SMo, "unidad": "kN·m/m"},
            ],
            "pasos": [
                {"nombre": "Momento neto respecto a la puntera",
                 "formula": "M_neto = ΣM_R − ΣM_o",
                 "detalle": f"{SMR:.2f} − {SMo:.2f}",
                 "valor": M_neto, "unidad": "kN·m/m"},
                {"nombre": "Posición de la resultante (desde la puntera)",
                 "formula": "CE = M_neto / ΣV",
                 "detalle": f"{M_neto:.2f} / {SV:.2f}",
                 "valor": CE, "unidad": "m"},
                {"nombre": "Posición del centro geométrico",
                 "formula": "B/2",
                 "detalle": f"{B:.3f} / 2",
                 "valor": B / 2.0, "unidad": "m"},
                {"nombre": "Excentricidad (con signo)",
                 "formula": "e = B/2 − CE",
                 "detalle": f"{B/2:.3f} − {CE:.3f}",
                 "valor": e, "unidad": "m"},
                {"nombre": "Excentricidad en valor absoluto",
                 "formula": "|e|",
                 "detalle": "",
                 "valor": absE, "unidad": "m"},
                {"nombre": "Límite admisible (núcleo central)",
                 "formula": "B/6",
                 "detalle": f"{B:.3f} / 6",
                 "valor": limite, "unidad": "m"},
            ],
            "totales": {
                "CE": CE,
                "e": e,
                "abs_e": absE,
                "limite": limite,
                "estado": estado,
                "lado": lado,
                "dentro_nucleo": absE <= limite,
            },
        }

    # ==================================================================
    # PRESIONES SOBRE EL SUELO
    # ==================================================================
    def calcular_presiones(self) -> dict[str, float]:
        """Calcula la distribución de presiones de contacto bajo la zapata.

        Dos regímenes:

        * **|e| ≤ B/6** (resultante dentro del núcleo central): distribución
          lineal (trapezoidal), ``q = ΣV/B · (1 ± 6e/B)``.
        * **|e| > B/6** (resultante fuera del núcleo): el suelo no toma
          tracción, por lo que la presión se **redistribuye a un diagrama
          triangular** sobre una longitud de contacto reducida (método
          convencional / Meyerhof):

          .. math::
              q_{máx} = \\frac{2\\,\\Sigma V}{3\\,(B/2 - |e|)}, \\quad
              L_{contacto} = 3\\,(B/2 - |e|)

          y la presión en el extremo opuesto es 0. Esto evita reportar
          presiones negativas (físicamente imposibles).

        Returns:
            dict con ``q_puntera``, ``q_talon``, ``q_max``, ``B_prima``
            (ancho efectivo de Meyerhof B−2|e|), ``e``, ``SV``,
            ``redistribuido`` (bool) y ``long_contacto``.
        """
        SV = self.cargas.suma_vertical()
        _, e, _ = self._calcular_excentricidad()
        B = self.muro.B
        B_prima = B - 2.0 * abs(e)

        if abs(e) <= B / 6.0:
            # Núcleo central: distribución lineal (trapezoidal).
            q_puntera = (SV / B) * (1.0 + 6.0 * e / B)
            q_talon = (SV / B) * (1.0 - 6.0 * e / B)
            q_max = max(q_puntera, q_talon)
            return {
                "q_puntera": q_puntera, "q_talon": q_talon, "q_max": q_max,
                "B_prima": B_prima, "e": e, "SV": SV,
                "redistribuido": False, "long_contacto": B,
            }

        # Fuera del núcleo: redistribución triangular (Meyerhof).
        brazo = B / 2.0 - abs(e)            # semiancho útil hasta el borde
        if brazo <= 1e-6:
            # Resultante prácticamente fuera de la base: falla total. Se
            # devuelve una presión pico muy alta para que el FS de capacidad
            # colapse (la excentricidad ya marca NO CUMPLE por su cuenta).
            brazo = 1e-6
        long_contacto = 3.0 * brazo
        q_max = 2.0 * SV / (3.0 * brazo) if SV > 0 else 0.0
        if e >= 0.0:                        # resultante hacia la puntera
            q_puntera, q_talon = q_max, 0.0
        else:                               # resultante hacia el talón
            q_puntera, q_talon = 0.0, q_max

        return {
            "q_puntera": q_puntera, "q_talon": q_talon, "q_max": q_max,
            "B_prima": B_prima, "e": e, "SV": SV,
            "redistribuido": True, "long_contacto": long_contacto,
        }

    # ==================================================================
    # CAPACIDAD DE CARGA
    # ==================================================================
    def verificar_capacidad_carga(self) -> ResultadoVerificacion:
        """FS = qu / q_máx."""
        presiones = self.calcular_presiones()
        cim = self.muro.suelo_cimentacion
        D = self.muro.geometria.D

        SV = presiones["SV"]
        # Inclinación de la carga sobre la cimentación: se usa el empuje
        # horizontal ACTUANTE (activo + sobrecarga + sismo), NO neto del empuje
        # pasivo. Restar Pp aquí anula los factores de inclinación y sobrestima
        # q_u de forma no conservadora (cf. Braja Das, Ej. 8.1: usa Ph=Pa·cosα).
        H_actuante = self.cargas.suma_horizontal_empuje()

        resultado_qu = PropiedadesSuelo.capacidad_carga_ultima(
            c=cim.cohesion,
            phi_grados=cim.phi,
            gamma=cim.gamma,
            D=D,
            B_efectivo=presiones["B_prima"],
            Ph=H_actuante,
            V=SV,
        )
        qu = resultado_qu["qu"]
        q_max = presiones["q_max"]        # pico real (contempla redistribución)
        FS = qu / q_max if q_max > 0 else 9999.0

        estado = (EstadoVerificacion.CUMPLE if FS >= self.FS_CAPACIDAD_MIN
                  else EstadoVerificacion.NO_CUMPLE)

        return ResultadoVerificacion(
            verificacion="FS por Capacidad de Carga",
            valor_calculado=FS,
            valor_requerido=self.FS_CAPACIDAD_MIN,
            unidades="-",
            estado=estado,
            detalle={
                "qu_kPa": qu,
                "q_max_kPa": q_max,
                "q_min_kPa": presiones["q_talon"],
                "referencia": ("Capacidad portante, FS ≥ 3.0 (q_u / q_máx). "
                               "Marco: NSR-10 Título H (capacidad admisible del "
                               "suelo). Teoría: Meyerhof/Vesic — Braja Das, cap. 3."),
                **{k: v for k, v in resultado_qu.items() if k != "qu"},
            },
        )

    # ==================================================================
    # DESGLOSE DE CAPACIDAD DE CARGA (para tablas detalladas)
    # ==================================================================
    def tabla_capacidad_carga(self) -> dict:
        """Devuelve la descomposición paso a paso del FS por capacidad portante.

        Estructura:
            {
                "parametros":  [c', φ, γ, D, B, e, B', q=γD, ψ, ...]
                "factores_N":  [Nc, Nq, Nγ]
                "factores_d":  [Fcd, Fqd, Fγd]
                "factores_i":  [Fci, Fqi, Fγi]
                "terminos":    [término cohesivo, de sobrecarga, de ancho]
                "presiones":   {q_puntera, q_talon, q_max, B_prima, e}
                "totales":     {qu, q_max, FS, FS_min}
            }
        """
        presiones = self.calcular_presiones()
        cim = self.muro.suelo_cimentacion
        D = self.muro.geometria.D
        B = self.muro.B

        SV = presiones["SV"]
        e_exc = presiones["e"]
        B_prima = presiones["B_prima"]
        q_puntera = presiones["q_puntera"]
        q_talon = presiones["q_talon"]
        q_max = presiones["q_max"]

        # Empuje horizontal ACTUANTE para la inclinación de carga (sin restar
        # el pasivo; ver nota en verificar_capacidad_carga).
        H_actuante = self.cargas.suma_horizontal_empuje()

        resultado_qu = PropiedadesSuelo.capacidad_carga_ultima(
            c=cim.cohesion, phi_grados=cim.phi, gamma=cim.gamma,
            D=D, B_efectivo=B_prima, Ph=H_actuante, V=SV,
        )
        qu = resultado_qu["qu"]
        FS = qu / q_max if q_max > 0 else 9999.0

        Nc = resultado_qu["Nc"]
        Nq = resultado_qu["Nq"]
        Ng = resultado_qu["Ngamma"]
        Fcd = resultado_qu["Fcd"]
        Fqd = resultado_qu["Fqd"]
        Fgd = resultado_qu["Fgd"]
        Fci = resultado_qu["Fci"]
        Fqi = resultado_qu["Fqi"]
        Fgi = resultado_qu["Fgi"]
        psi = resultado_qu["psi_grados"]
        q_sobrec = resultado_qu["q_sobrecarga"]

        # Contribución de cada término a qu
        term_c = cim.cohesion * Nc * Fcd * Fci
        term_q = q_sobrec * Nq * Fqd * Fqi
        term_g = 0.5 * cim.gamma * B_prima * Ng * Fgd * Fgi

        parametros = [
            {"nombre": "c' (cohesión del suelo de cimentación)",
             "valor": cim.cohesion, "unidad": "kPa"},
            {"nombre": "φ (fricción del suelo)",
             "valor": cim.phi, "unidad": "°"},
            {"nombre": "γ (peso específico)",
             "valor": cim.gamma, "unidad": "kN/m³"},
            {"nombre": "D (profundidad de desplante)",
             "valor": D, "unidad": "m"},
            {"nombre": "q = γ·D (sobrecarga efectiva)",
             "valor": q_sobrec, "unidad": "kPa"},
            {"nombre": "B (ancho de la zapata)",
             "valor": B, "unidad": "m"},
            {"nombre": "ΣV", "valor": SV, "unidad": "kN/m"},
            {"nombre": "Excentricidad e",
             "valor": e_exc, "unidad": "m"},
            {"nombre": "B' = B − 2·|e| (ancho efectivo)",
             "valor": B_prima, "unidad": "m"},
            {"nombre": "H actuante (ΣH activo+sobrecarga+sismo)",
             "valor": H_actuante, "unidad": "kN/m"},
            {"nombre": "ψ = atan(H_actuante / ΣV)",
             "valor": psi, "unidad": "°"},
        ]

        factores_N = [
            {"nombre": "N_c (cohesión)", "valor": Nc,
             "formula": "(Nq − 1) / tan φ" if cim.phi > 0 else "π + 2"},
            {"nombre": "N_q (sobrecarga)", "valor": Nq,
             "formula": "e^(π·tan φ) · tan²(45° + φ/2)"},
            {"nombre": "N_γ (ancho)", "valor": Ng,
             "formula": "2·(Nq + 1)·tan φ  (Vesic)"},
        ]

        factores_d = [
            {"nombre": "F_cd (profundidad, cohesivo)", "valor": Fcd},
            {"nombre": "F_qd (profundidad, sobrecarga)", "valor": Fqd},
            {"nombre": "F_γd (profundidad, ancho)", "valor": Fgd},
        ]

        factores_i = [
            {"nombre": "F_ci (inclinación, cohesivo)", "valor": Fci,
             "formula": "(1 − ψ/90°)²"},
            {"nombre": "F_qi (inclinación, sobrecarga)", "valor": Fqi,
             "formula": "(1 − ψ/90°)²"},
            {"nombre": "F_γi (inclinación, ancho)", "valor": Fgi,
             "formula": "(1 − ψ/φ)²"},
        ]

        terminos = [
            {"nombre": "Término cohesivo",
             "formula": "c' · Nc · F_cd · F_ci",
             "detalle": (f"{cim.cohesion:.2f} × {Nc:.3f} × "
                         f"{Fcd:.3f} × {Fci:.3f}"),
             "valor": term_c},
            {"nombre": "Término de sobrecarga",
             "formula": "q · Nq · F_qd · F_qi",
             "detalle": (f"{q_sobrec:.2f} × {Nq:.3f} × "
                         f"{Fqd:.3f} × {Fqi:.3f}"),
             "valor": term_q},
            {"nombre": "Término de ancho",
             "formula": "½ · γ · B' · N_γ · F_γd · F_γi",
             "detalle": (f"0.5 × {cim.gamma:.2f} × {B_prima:.3f} × "
                         f"{Ng:.3f} × {Fgd:.3f} × {Fgi:.3f}"),
             "valor": term_g},
        ]

        return {
            "parametros": parametros,
            "factores_N": factores_N,
            "factores_d": factores_d,
            "factores_i": factores_i,
            "terminos": terminos,
            "presiones": {
                "q_puntera": q_puntera,
                "q_talon": q_talon,
                "q_max": q_max,
                "B_prima": B_prima,
                "e": e_exc,
                "SV": SV,
            },
            "totales": {
                "qu": qu,
                "q_max": q_max,
                "FS": FS,
                "FS_min": self.FS_CAPACIDAD_MIN,
            },
        }

    # ==================================================================
    # ANÁLISIS COMPLETO
    # ==================================================================
    def analisis_completo(self) -> ReporteEstabilidad:
        """Ejecuta todas las verificaciones y devuelve el reporte consolidado."""
        volc = self.verificar_volcamiento()
        desl = self.verificar_deslizamiento()
        exc = self.verificar_excentricidad()
        cap = self.verificar_capacidad_carga()
        presiones = self.calcular_presiones()

        return ReporteEstabilidad(
            volcamiento=volc,
            deslizamiento=desl,
            capacidad_carga=cap,
            excentricidad=exc,
            presiones=presiones,
        )
