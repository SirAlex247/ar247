"""
Generación de reportes PDF profesionales del diseño del muro.

Usa ReportLab para crear un PDF con:
    - Portada con datos de la empresa, proyecto, ingeniero.
    - Catálogo de fórmulas utilizadas (1 página).
    - Resumen del muro y vista gráfica.
    - Tablas de cargas, combinaciones, verificaciones, diseño.
    - Pie de página y numeración.

Paleta de colores: verde muy sutil sobre blanco (editable en las constantes
COLOR_* al inicio del archivo).

Numeración de secciones configurable (clase Numerador):
    - Modo standalone   : 1., 2., 3., ... (para memoria de solo muros).
    - Modo anidado      : <prefijo>.1, <prefijo>.2, ... (cuando el reporte
      se incluye dentro de una memoria mayor, p.ej. prefijo="10").
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    BaseDocTemplate, Frame, Image, KeepTogether, PageBreak, PageTemplate,
    Paragraph, Spacer, Table, TableStyle,
)


# =============================================================================
# Paleta de colores (verde sutil + blanco)
# =============================================================================
# Tonos principales
COLOR_VERDE_OSCURO   = colors.HexColor("#065f46")   # verde bosque (títulos)
COLOR_VERDE_MEDIO    = colors.HexColor("#047857")   # verde medio (subtítulos)
COLOR_VERDE_CLARO    = colors.HexColor("#10b981")   # verde vivo (realces)
COLOR_VERDE_SUAVE    = colors.HexColor("#d1fae5")   # verde fondo OK
COLOR_VERDE_CASI_BCO = colors.HexColor("#ecfdf5")   # fondo alternado filas
# Neutros
COLOR_TEXTO          = colors.HexColor("#1f2937")   # texto principal
COLOR_TEXTO_SUAVE    = colors.HexColor("#4b5563")   # texto secundario
COLOR_BORDE          = colors.HexColor("#d1d5db")   # bordes de tabla
COLOR_HEADER_OSCURO  = colors.HexColor("#064e3b")   # header tablas de resultado
# Semánticos (se mantienen)
COLOR_OK_BG          = colors.HexColor("#d1fae5")
COLOR_OK_TXT         = colors.HexColor("#065f46")
COLOR_ERR_BG         = colors.HexColor("#fee2e2")
COLOR_ERR_TXT        = colors.HexColor("#991b1b")


# =============================================================================
# Numerador de secciones
# =============================================================================
class Numerador:
    """Genera números de sección para el reporte.

    Soporta dos modos:

    * ``prefix=None`` → reporte independiente:  1., 2., 3., ...
      con subsecciones 1.1, 1.2, 2.1, ...
    * ``prefix="10"`` → reporte anidado dentro de una memoria mayor:
      10.1, 10.2, ... con subsecciones 10.1.1, 10.1.2, 10.2.1, ...

    Uso:
        num = Numerador("10")          # o Numerador() para standalone
        num.h1()  # -> "10.1"
        num.h2()  # -> "10.1.1"
        num.h2()  # -> "10.1.2"
        num.h1()  # -> "10.2"          (resetea el contador de subsecciones)
    """

    def __init__(self, prefix: str | None = None) -> None:
        raw = str(prefix).strip() if prefix is not None else ""
        self.prefix = raw if raw else None
        self.main = 0
        self.sub = 0

    def h1(self) -> str:
        """Avanza al siguiente H1 y devuelve su número formateado."""
        self.main += 1
        self.sub = 0
        if self.prefix:
            return f"{self.prefix}.{self.main}"
        return f"{self.main}."

    def h2(self) -> str:
        """Avanza al siguiente H2 (subsección) y devuelve su número formateado."""
        self.sub += 1
        if self.prefix:
            return f"{self.prefix}.{self.main}.{self.sub}"
        return f"{self.main}.{self.sub}"


# =============================================================================
# Catálogo de fórmulas utilizadas (página 2 del reporte)
# =============================================================================
# Estructura:  [(titulo_grupo, [(concepto, formula_html), ...]), ...]
# Las fórmulas usan HTML mínimo soportado por ReportLab (<sub>, <sup>, <b>, <i>)
# y entidades Unicode para símbolos matemáticos.
_FORMULAS_CATALOGO: list[tuple[str, list[tuple[str, str]]]] = [
    ("Coeficientes de empuje y presiones laterales", [
        ("K<sub>a</sub> Rankine (α = 0)",
         "K<sub>a</sub> = tan²(45° − φ/2)"),
        ("K<sub>a</sub> Rankine (relleno inclinado α)",
         "K<sub>a</sub> = cos α · (cos α − √(cos²α − cos²φ)) / "
         "(cos α + √(cos²α − cos²φ))"),
        ("K<sub>p</sub> Rankine",
         "K<sub>p</sub> = tan²(45° + φ/2)"),
        ("Empuje activo",
         "P<sub>a</sub> = ½ · γ · K<sub>a</sub> · H²"),
        ("Empuje por sobrecarga uniforme",
         "P<sub>q</sub> = q · K<sub>a</sub> · H"),
        ("Empuje pasivo (suelo c-φ)",
         "P<sub>p</sub> = ½ · γ · K<sub>p</sub> · H² + 2 · c' · √K<sub>p</sub> · H"),
    ]),
    ("Cargas sísmicas (NSR-10 A.10 y Mononobe-Okabe)", [
        ("Factores de sitio",
         "F<sub>a</sub>, F<sub>v</sub> por interpolación en Tablas "
         "A.2.4-3 y A.2.4-4 según perfil de suelo"),
        ("Aceleración efectiva",
         "A<sub>max</sub> = F<sub>a</sub> · A<sub>a</sub>"),
        ("k<sub>h</sub> — se admite desplazamiento (Richards-Elms)",
         "k<sub>h</sub> = A<sub>max</sub> / 2  ;  k<sub>v</sub> = 0"),
        ("k<sub>h</sub> — sin desplazamiento",
         "k<sub>h</sub> = k<sub>v</sub> = 0.6 · A<sub>max</sub>"),
        ("Ángulo sísmico",
         "θ = arctan( k<sub>h</sub> / (1 − k<sub>v</sub>) )"),
        ("Empuje activo sísmico (Mononobe-Okabe)",
         "P<sub>ae</sub> = ½ · γ · K<sub>ae</sub> · H² · (1 − k<sub>v</sub>)"),
        ("Incremento dinámico",
         "ΔP<sub>ae</sub> = P<sub>ae</sub> − P<sub>a</sub>  "
         "(aplicado a 0.6·H)"),
        ("Fuerza de inercia del muro",
         "F<sub>inercia</sub> = k<sub>h</sub> · W<sub>concreto</sub>  "
         "(en el CG del concreto)"),
    ]),
    ("Combinaciones de carga NSR-10", [
        ("ELU B-1", "1.4 · (D + H)"),
        ("ELU B-2", "1.2·D + 1.6·L + 1.6·L<sub>sc</sub> + 1.6·H"),
        ("ELU B-5", "1.2·D + 1.0·E + 1.0·L + 1.0·H"),
        ("ELU B-6", "0.9·D + 1.0·E + 0.9·H"),
        ("ELS S-1", "D + H + L + L<sub>sc</sub>"),
        ("ELS S-2", "D + 0.7·E + H"),
    ]),
    ("Verificaciones de estabilidad", [
        ("Factor de seguridad al volcamiento",
         "FS<sub>volc</sub> = Σ M<sub>R</sub> / Σ M<sub>o</sub>   ≥ 2.0"),
        ("Factor de seguridad al deslizamiento",
         "FS<sub>des</sub> = (ΣV·tan δ + B·c<sub>a</sub> + P<sub>p</sub> "
         "+ P<sub>p,diente</sub>) / ΣH   ≥ 1.5"),
        ("Fricción/cohesión reducidas",
         "δ = k<sub>1</sub> · φ  ;  c<sub>a</sub> = k<sub>2</sub> · c'"),
        ("Excentricidad",
         "e = | B/2 − (Σ M<sub>R</sub> − Σ M<sub>o</sub>) / ΣV |   ≤ B/6"),
        ("Presiones bajo zapata  (|e| ≤ B/6)",
         "q<sub>max</sub>, q<sub>min</sub> = ΣV/B · (1 ± 6·e/B)"),
        ("Presiones bajo zapata  (|e| &gt; B/6, reducción)",
         "q<sub>max</sub> = 2·ΣV / [ 3·(B/2 − e) ]"),
    ]),
    ("Capacidad de carga del suelo (Meyerhof / Hansen / Vesic)", [
        ("Ancho efectivo",
         "B' = B − 2·e"),
        ("Capacidad última",
         "q<sub>u</sub> = c'·N<sub>c</sub>·F<sub>cd</sub>·F<sub>ci</sub> "
         "+ q·N<sub>q</sub>·F<sub>qd</sub>·F<sub>qi</sub> "
         "+ ½·γ·B'·N<sub>γ</sub>·F<sub>γd</sub>·F<sub>γi</sub>"),
        ("Factor N<sub>q</sub>",
         "N<sub>q</sub> = e<sup>π·tan φ</sup> · tan²(45° + φ/2)"),
        ("Factor N<sub>c</sub>",
         "N<sub>c</sub> = (N<sub>q</sub> − 1) · cot φ"),
        ("Factor N<sub>γ</sub> (Vesic)",
         "N<sub>γ</sub> = 2 · (N<sub>q</sub> + 1) · tan φ"),
        ("Factor de seguridad por capacidad",
         "FS<sub>cc</sub> = q<sub>u</sub> / q<sub>max</sub>   ≥ 3.0"),
    ]),
    ("Diseño estructural (NSR-10 Título C)", [
        ("Resistencia requerida (flexión, φ = 0.90)",
         "R<sub>n</sub> = M<sub>u</sub> / (φ · b · d²)"),
        ("Cuantía de refuerzo por flexión",
         "ρ = (0.85·f'<sub>c</sub>/f<sub>y</sub>) · "
         "(1 − √(1 − 2·R<sub>n</sub> / (0.85·f'<sub>c</sub>)))"),
        ("Acero requerido",
         "A<sub>s</sub> = ρ · b · d"),
        ("Acero mínimo por flexión (C.10.5.1)",
         "A<sub>s,min</sub> = max( 1.4·b·d / f<sub>y</sub>,   "
         "√f'<sub>c</sub> · b·d / (4·f<sub>y</sub>) )"),
        ("Cortante del concreto (φ = 0.75)",
         "V<sub>c</sub> = 0.17 · √f'<sub>c</sub> · b · d  ;  "
         "φV<sub>c</sub> = 0.75 · V<sub>c</sub>"),
        ("Cuantía mínima vástago vertical / horizontal (C.14.3.2-3)",
         "ρ<sub>v,min</sub> = 0.0012   ;   ρ<sub>h,min</sub> = 0.0020"),
        ("Cuantía mínima retracción/temperatura zapata (C.7.12.2.1)",
         "ρ<sub>min</sub> = 0.0018"),
    ]),
]


# =============================================================================
# Catálogo de fórmulas — CCP-14 (LRFD-AASHTO)
# =============================================================================
# La teoría de empujes y de capacidad portante es la misma; cambian el formato
# de seguridad (factores γ y φ en vez de FS globales) y las referencias.
_FORMULAS_CATALOGO_CCP14: list[tuple[str, list[tuple[str, str]]]] = [
    ("Coeficientes de empuje y presiones laterales", [
        ("K<sub>a</sub> Rankine (α = 0)",
         "K<sub>a</sub> = tan²(45° − φ/2)"),
        ("K<sub>a</sub> Rankine (relleno inclinado α)",
         "K<sub>a</sub> = cos α · (cos α − √(cos²α − cos²φ)) / "
         "(cos α + √(cos²α − cos²φ))"),
        ("K<sub>p</sub> Rankine",
         "K<sub>p</sub> = tan²(45° + φ/2)"),
        ("Empuje activo / sobrecarga / pasivo",
         "P<sub>a</sub> = ½·γ·K<sub>a</sub>·H² ; P<sub>q</sub> = q·K<sub>a</sub>·H ; "
         "P<sub>p</sub> = ½·γ·K<sub>p</sub>·H² + 2·c'·√K<sub>p</sub>·H"),
    ]),
    ("Factores de carga γ — permanentes (CCP-14 Tabla 3.4.1-2)", [
        ("DC — peso propio del concreto", "γ = 1.25 (máx) / 0.90 (mín)"),
        ("EV — peso del suelo (muros y estribos)", "γ = 1.35 (máx) / 1.00 (mín)"),
        ("EH — empuje horizontal activo del suelo", "γ = 1.50 (máx) / 0.90 (mín)"),
        ("LS — sobrecarga viva (empuje lateral)", "γ = 1.75"),
    ]),
    ("Combinaciones de diseño (CCP-14 Tabla 3.4.1-1)", [
        ("Resistencia I — capacidad portante (máx)",
         "1.25·DC + 1.35·EV + 1.50·EH + 1.75·LS"),
        ("Resistencia I — deslizamiento y excentricidad (mín)",
         "0.90·DC + 1.00·EV + 1.50·EH + 1.75·LS"),
        ("Evento Extremo I — sísmico",
         "1.0·(DC + EV + EH) + γ<sub>EQ</sub>·LS + 1.0·EQ ; φ = 1.0"),
    ]),
    ("Verificaciones por estados límite (CCP-14 Art. 11.6.3)", [
        ("Excentricidad — reemplaza el vuelco (Art. 11.6.3.3)",
         "|e| = |B/2 − ΣM<sub>may</sub>/ΣV<sub>may</sub>| ≤ B/3  (suelo) ; ≤ 0.45·B (roca)"),
        ("Deslizamiento (Art. 10.6.3.4)",
         "CDR = [φ<sub>τ</sub>·(ΣV·tanφ + c'·B) + φ<sub>ep</sub>·P<sub>p</sub>] / ΣH ≥ 1.0"),
        ("Factores de resistencia (Tabla 10.5.5.2.2-1)",
         "φ<sub>τ</sub> = 0.80 (arena) / 0.85 (arcilla) ; φ<sub>ep</sub> = 0.50"),
        ("Presión de contacto en suelo (Art. 11.6.3.2)",
         "σ<sub>v</sub> = ΣV<sub>may</sub> / (B − 2e)  (uniforme sobre el ancho efectivo)"),
        ("Capacidad portante (Art. 11.6.3.2 · Tabla 11.5.7-1)",
         "CDR = φ<sub>b</sub>·q<sub>n</sub> / σ<sub>v</sub> ≥ 1.0 ; φ<sub>b</sub> = 0.55"),
    ]),
    ("Capacidad de carga del suelo (Meyerhof / Hansen / Vesic)", [
        ("Ancho efectivo", "B' = B − 2·e"),
        ("Capacidad nominal q<sub>n</sub>",
         "q<sub>n</sub> = c'·N<sub>c</sub>·F<sub>cd</sub>·F<sub>ci</sub> "
         "+ q·N<sub>q</sub>·F<sub>qd</sub>·F<sub>qi</sub> "
         "+ ½·γ·B'·N<sub>γ</sub>·F<sub>γd</sub>·F<sub>γi</sub>"),
        ("Factores N",
         "N<sub>q</sub> = e<sup>π·tanφ</sup>·tan²(45°+φ/2) ; "
         "N<sub>c</sub> = (N<sub>q</sub>−1)·cotφ ; "
         "N<sub>γ</sub> = 2·(N<sub>q</sub>+1)·tanφ"),
    ]),
    ("Cargas sísmicas (CCP-14 Art. 11.6.5 y Mononobe-Okabe)", [
        ("Empuje activo sísmico (Mononobe-Okabe)",
         "P<sub>ae</sub> = ½·γ·K<sub>ae</sub>·H²·(1 − k<sub>v</sub>)"),
        ("Incremento dinámico (Evento Extremo I, γ = 1.0)",
         "ΔP<sub>ae</sub> = P<sub>ae</sub> − P<sub>a</sub>  (aplicado a 0.6·H)"),
        ("Ángulo sísmico",
         "θ = arctan( k<sub>h</sub> / (1 − k<sub>v</sub>) )"),
    ]),
    ("Diseño estructural (CCP-14 Sección 5 — AASHTO LRFD)", [
        ("Resistencia requerida (flexión, φ<sub>f</sub> = 0.90)",
         "R<sub>n</sub> = M<sub>u</sub> / (φ · b · d²)"),
        ("Cuantía de refuerzo por flexión",
         "ρ = (0.85·f'<sub>c</sub>/f<sub>y</sub>) · "
         "(1 − √(1 − 2·R<sub>n</sub> / (0.85·f'<sub>c</sub>)))"),
        ("Refuerzo mínimo (Art. 5.7.3.3.2)",
         "φ·M<sub>n</sub> ≥ mín(1.33·M<sub>u</sub>, M<sub>cr</sub>)"),
        ("Momento de fisuración",
         "M<sub>cr</sub> = γ<sub>3</sub>·γ<sub>1</sub>·f<sub>r</sub>·S ; "
         "γ<sub>1</sub>=1.6, γ<sub>3</sub>=0.67 ; f<sub>r</sub> = 0.62·√f'<sub>c</sub>"),
        ("Cortante del concreto (φ<sub>v</sub> = 0.90, Art. 5.8.3)",
         "V<sub>c</sub> = 0.083·β·√f'<sub>c</sub>·b<sub>v</sub>·d<sub>v</sub> ; "
         "β = 2.0 ; d<sub>v</sub> = máx(0.9·d, 0.72·h)"),
    ]),
]


def _config_norma(norma: str) -> dict:
    """Textos y catálogo de fórmulas del reporte según la norma seleccionada."""
    v = str(norma or "").upper().replace("-", "").replace(" ", "").replace("_", "")
    if v in ("CCP14", "CCP", "AASHTO", "LRFD", "LRFDCCP14"):
        return {
            "id": "CCP14",
            "subtitulo": "Conforme al Código Colombiano de Puentes CCP-14 "
                         "(LRFD-AASHTO)",
            "author": "Diseño de Muros CCP-14",
            "footer": "Diseño de muro de contención — CCP-14 (LRFD)",
            "catalogo": _FORMULAS_CATALOGO_CCP14,
            "sismo_titulo": "Parámetros sísmicos (CCP-14 Art. 3.10)",
            "sismo_diagrama": (
                "Cargas sísmicas del estado de <b>Evento Extremo I</b> "
                "(CCP-14 Art. 11.6.5, Mononobe-Okabe): empuje activo total "
                "P<sub>ae</sub> aplicado a 0.6·H, incremento dinámico "
                "ΔP<sub>ae</sub> = P<sub>ae</sub> − P<sub>a</sub> (factor de carga "
                "γ<sub>EQ</sub> = 1.0), y fuerza de inercia del muro "
                "F<sub>inercia</sub> = k<sub>h</sub>·W en el CG del concreto."),
            "combos_titulo": "Combinaciones de carga CCP-14 (LRFD)",
            "combos_sub": "Estados límite de Resistencia I y Evento Extremo I "
                          "(Art. 3.4.1)",
            "combos_gravedad": (
                "En muros de gravedad las combinaciones LRFD se usan para "
                "verificar la capacidad portante y el deslizamiento; el diseño "
                "estructural por flexión no aplica."),
            "verif_min_header": "Requerido",
            "verif_base": (
                "<b>Base normativa:</b> verificaciones geotécnicas por estados "
                "límite (CCP-14 Secc. 10 y 11). Se reporta la relación "
                "capacidad/demanda <b>CDR ≥ 1.0</b> en lugar del factor de "
                "seguridad: la excentricidad reemplaza el vuelco "
                "(|e| ≤ B/3 en suelo, Art. 11.6.3.3); deslizamiento con "
                "φ<sub>τ</sub> y φ<sub>ep</sub> (Tabla 10.5.5.2.2-1); capacidad "
                "portante con φ<sub>b</sub> = 0.55 (Tabla 11.5.7-1). Teoría de "
                "capacidad: Meyerhof/Vesic."),
            "estructural_titulo": "Diseño estructural (CCP-14 Sección 5)",
            "estructural_gravedad_ref": "CCP-14 Sección 5",
            "estructural_pasos_nota": (
                "Para cada elemento se muestran los datos de entrada, los pasos "
                "para obtener el momento último M<sub>u</sub> con factores LRFD "
                "(EH·1.50, LS·1.75, DC·1.25, EV·1.35), y el refuerzo por flexión "
                "y mínimo (CCP-14 Art. 5.7.3.3.2: "
                "φ·M<sub>n</sub> ≥ mín(1.33·M<sub>u</sub>, M<sub>cr</sub>); "
                "φ<sub>f</sub> = φ<sub>v</sub> = 0.90)."),
            "momentos_nota": (
                "Descomposición carga por carga del momento estabilizador y del "
                "volcador respecto a la puntera (C), con <b>cargas características "
                "(sin mayorar)</b>; sirve de referencia. En la CCP-14 el vuelco se "
                "controla por el límite de excentricidad con cargas mayoradas "
                "(sección de excentricidad)."),
            "term": {
                "volc_titulo": "Estabilidad al vuelco — relación capacidad/demanda",
                "volc_formula_label": "CDR = e_lím / |e|  (Art. 11.6.3.3)",
                "min_label": "CDR requerido",
                "desliz_titulo": "Deslizamiento — relación capacidad/demanda (CDR)",
                "desliz_intro": (
                    "Cálculo LRFD de la relación capacidad/demanda "
                    "CDR = R<sub>R</sub> / ΣH, con "
                    "R<sub>R</sub> = φ<sub>τ</sub>·(ΣV·tanφ + c'·B) + "
                    "φ<sub>ep</sub>·P<sub>p</sub> (CCP-14 Art. 10.6.3.4). "
                    "Cargas <b>mayoradas</b> (Resistencia I / Evento Extremo I)."),
                "desliz_fs_titulo": "Relación capacidad/demanda al deslizamiento",
                "desliz_fs_label": "CDR = R_R / ΣH",
                "capac_titulo": "Capacidad portante — relación capacidad/demanda (CDR)",
                "capac_intro": (
                    "Capacidad nominal q<sub>n</sub> (Meyerhof/Vesic) afectada por "
                    "φ<sub>b</sub> = 0.55; demanda σ<sub>v</sub> = ΣV<sub>may</sub>/"
                    "(B − 2e). CDR = φ<sub>b</sub>·q<sub>n</sub> / σ<sub>v</sub> "
                    "(CCP-14 Art. 11.6.3.2). Cargas <b>mayoradas</b>."),
                "capac_fs_titulo": "Relación capacidad/demanda por capacidad portante",
                "capac_qu_label": "q_R = φ_b·q_n (capacidad mayorada)",
                "capac_qmax_label": "σ_v (demanda mayorada)",
                "capac_fs_label": "CDR = q_R / σ_v",
                "excent_intro_zona": "el tercio medio (|e| ≤ B/3 en suelo; ≤ 0.45·B "
                                     "en roca), Art. 11.6.3.3",
                "excent_limite_label": "Límite (tercio medio, B/3 / sísmico)",
                "excent_condicion": "|e| ≤ e_lím",
            },
        }
    return {
        "id": "NSR10",
        "subtitulo": "Conforme a NSR-10 (Colombia)",
        "author": "Diseño de Muros NSR-10",
        "footer": "Diseño de muro de contención — NSR-10",
        "catalogo": _FORMULAS_CATALOGO,
        "sismo_titulo": "Parámetros sísmicos (NSR-10 A.2)",
        "sismo_diagrama": (
            "Cargas sísmicas según NSR-10 H.6: empuje activo total "
            "P<sub>ae</sub> aplicado a 0.6·H, incremento dinámico "
            "ΔP<sub>ae</sub> = P<sub>ae</sub> − P<sub>a</sub>, y fuerza de "
            "inercia del muro F<sub>inercia</sub> = k<sub>h</sub>·W aplicada "
            "en el centro de gravedad del concreto."),
        "combos_titulo": "Combinaciones de carga NSR-10",
        "combos_sub": "Estado Límite Último (ELU, B.2.4)",
        "combos_gravedad": (
            "En muros de gravedad solo se aplican combinaciones de servicio (ELS) "
            "para verificar las presiones admisibles del suelo. Las combinaciones "
            "últimas (ELU) no aplican porque estos muros no se diseñan por flexión."),
        "verif_min_header": "Mínimo",
        "verif_base": (
            "<b>Base normativa:</b> verificaciones geotécnicas según el marco de la "
            "NSR-10 Título H (geotecnia y cimentaciones), con los factores de "
            "seguridad de la práctica: volcamiento FS ≥ 2.0, deslizamiento FS ≥ 1.5 "
            "y capacidad portante FS ≥ 3.0 (q_u/q_máx); la resultante debe caer "
            "dentro del núcleo central (|e| ≤ B/6). Fundamento teórico: Braja M. "
            "Das, <i>Fundamentos de ingeniería de cimentaciones</i>, cap. 3 y 8."),
        "estructural_titulo": "Diseño estructural (NSR-10 Título C)",
        "estructural_gravedad_ref": "NSR-10 Título C.7",
        "estructural_pasos_nota": (
            "Para cada elemento se muestran los datos de entrada, los "
            "pasos para obtener el momento último M_u, y los pasos para "
            "obtener la cuantía de refuerzo ρ y el acero requerido A_s "
            "(NSR-10 C.10.5.1 para la cuantía mínima y C.10.3 para la "
            "cuantía máxima controlada por tracción)."),
        "momentos_nota": (
            "Descomposición carga por carga del momento estabilizador y "
            "del momento volcador respecto a la puntera (C). Para cada fila: "
            "momento = fuerza × brazo. Cálculo con cargas características "
            "(sin mayorar)."),
        "term": {
            "volc_titulo": "Factor de seguridad al volcamiento",
            "volc_formula_label": "FS_volc = ΣM_R / ΣM_o",
            "min_label": "FS mínimo requerido",
            "desliz_titulo": "Factor de Seguridad al Deslizamiento",
            "desliz_intro": (
                "Cálculo detallado de FS<sub>des</sub> = (ΣV·tan δ + B·c<sub>a</sub> "
                "+ P<sub>p</sub> + P<sub>p,diente</sub>) / ΣH. Cargas sin mayorar; "
                "la fricción y cohesión se reducen con los factores "
                "k<sub>1</sub> y k<sub>2</sub>."),
            "desliz_fs_titulo": "Factor de seguridad al deslizamiento",
            "desliz_fs_label": "FS_des = Σ F_res / Σ F_act",
            "capac_titulo": "Factor de Seguridad por Capacidad de Carga",
            "capac_intro": (
                "Cálculo detallado con la ecuación general (Meyerhof/Vesic): "
                "q<sub>u</sub> = c'·N<sub>c</sub>·F<sub>cd</sub>·F<sub>ci</sub> + "
                "q·N<sub>q</sub>·F<sub>qd</sub>·F<sub>qi</sub> + "
                "½·γ·B'·N<sub>γ</sub>·F<sub>γd</sub>·F<sub>γi</sub>. "
                "Cargas sin mayorar."),
            "capac_fs_titulo": "Factor de seguridad por capacidad de carga",
            "capac_qu_label": "q_u (capacidad última)",
            "capac_qmax_label": "q_max (presión en puntera)",
            "capac_fs_label": "FS_cap = q_u / q_max",
            "excent_intro_zona": "el núcleo central (|e| ≤ B/6)",
            "excent_limite_label": "Límite del núcleo central (B/6)",
            "excent_condicion": "|e| ≤ B/6",
        },
    }


# =============================================================================
# Datos de la portada
# =============================================================================
@dataclass
class DatosProyecto:
    """Información editorial del reporte.

    Attributes:
        numeracion_prefijo: Si se deja vacío, el reporte usa numeración
            independiente (1., 2., 3., ...).  Si se define (p.ej. "10"),
            el reporte se numera como subsección de una memoria mayor
            (10.1, 10.2, ... con subsubsecciones 10.1.1, 10.1.2, ...).
    """
    empresa: str = ""
    proyecto: str = ""
    ubicacion: str = ""
    ingeniero: str = ""
    contratante: str = ""
    fecha: str = ""
    observaciones: str = ""
    numeracion_prefijo: str = ""      # "" => independiente;  "10" => 10.1, 10.2, ...

    def __post_init__(self) -> None:
        if not self.fecha:
            self.fecha = datetime.now().strftime("%d/%m/%Y")


# =============================================================================
# Estilos
# =============================================================================
_styles = getSampleStyleSheet()

H1 = ParagraphStyle(
    "H1", parent=_styles["Heading1"],
    fontSize=16, leading=20, spaceAfter=10,
    textColor=COLOR_TEXTO, alignment=TA_LEFT,
)
H2 = ParagraphStyle(
    "H2", parent=_styles["Heading2"],
    fontSize=12, leading=16, spaceBefore=8, spaceAfter=6,
    textColor=COLOR_TEXTO,
)
H3 = ParagraphStyle(
    "H3", parent=_styles["Heading3"],
    fontSize=10.5, leading=13, spaceBefore=4, spaceAfter=3,
    textColor=COLOR_TEXTO,
)
BODY = ParagraphStyle(
    "BODY", parent=_styles["Normal"],
    fontSize=9.5, leading=13, spaceAfter=4,
    textColor=COLOR_TEXTO,
)
TITULO_PORTADA = ParagraphStyle(
    "TitPort", parent=_styles["Title"],
    fontSize=22, leading=28, alignment=TA_CENTER,
    textColor=COLOR_TEXTO, spaceAfter=20,
)
SUBTITULO_PORTADA = ParagraphStyle(
    "SubPort", parent=_styles["Normal"],
    fontSize=13, leading=17, alignment=TA_CENTER,
    textColor=COLOR_TEXTO_SUAVE, spaceAfter=10,
)
# Estilos compactos para la página de fórmulas
FORMULA_GRUPO = ParagraphStyle(
    "FormGrupo", parent=_styles["Heading3"],
    fontSize=10.5, leading=13, spaceBefore=6, spaceAfter=3,
    textColor=COLOR_TEXTO,
)
FORMULA_CONCEPTO = ParagraphStyle(
    "FormConcepto", parent=_styles["Normal"],
    fontSize=8.5, leading=10.5, textColor=COLOR_TEXTO_SUAVE,
)
FORMULA_EXPR = ParagraphStyle(
    "FormExpr", parent=_styles["Normal"],
    fontSize=8.5, leading=10.5, textColor=COLOR_TEXTO,
    fontName="Helvetica",
)


# =============================================================================
# Estilos de tabla
# =============================================================================
def _estilo_tabla_datos() -> TableStyle:
    return TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), COLOR_VERDE_OSCURO),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9.5),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("FONTSIZE", (0, 1), (-1, -1), 9),
        ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
        ("TEXTCOLOR", (0, 1), (0, -1), COLOR_TEXTO),
        ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
        ("ALIGN", (0, 1), (0, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.4, COLOR_BORDE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.white, COLOR_VERDE_CASI_BCO]),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ])


def _estilo_tabla_resultado() -> TableStyle:
    return TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), COLOR_HEADER_OSCURO),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9.5),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("FONTSIZE", (0, 1), (-1, -1), 9),
        ("ALIGN", (1, 1), (-1, -1), "CENTER"),
        ("ALIGN", (0, 1), (0, -1), "LEFT"),
        ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
        ("TEXTCOLOR", (0, 1), (0, -1), COLOR_TEXTO),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.4, COLOR_BORDE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.white, COLOR_VERDE_CASI_BCO]),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ])


# =============================================================================
# Pie y encabezado de página
# =============================================================================
class _PaginaPlantilla:
    def __init__(self, datos: DatosProyecto,
                 footer_label: str = "Diseño de muro de contención — NSR-10") -> None:
        self.datos = datos
        self.footer_label = footer_label

    def dibujar(self, canvas, doc) -> None:
        canvas.saveState()
        # Encabezado
        canvas.setFont("Helvetica-Bold", 9)
        canvas.setFillColor(COLOR_TEXTO)
        canvas.drawString(2 * cm, LETTER[1] - 1.2 * cm,
                          (self.datos.empresa or "Informe técnico")[:80])
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(COLOR_TEXTO_SUAVE)
        canvas.drawRightString(LETTER[0] - 2 * cm, LETTER[1] - 1.2 * cm,
                               f"Proyecto: {self.datos.proyecto[:60]}")
        canvas.setStrokeColor(COLOR_VERDE_MEDIO)
        canvas.setLineWidth(0.7)
        canvas.line(2 * cm, LETTER[1] - 1.4 * cm,
                    LETTER[0] - 2 * cm, LETTER[1] - 1.4 * cm)

        # Pie
        canvas.setFont("Helvetica-Oblique", 8)
        canvas.setFillColor(COLOR_TEXTO_SUAVE)
        canvas.drawString(2 * cm, 1.2 * cm, self.footer_label)
        canvas.drawRightString(LETTER[0] - 2 * cm, 1.2 * cm,
                               f"Página {doc.page} — {self.datos.fecha}")
        canvas.setStrokeColor(COLOR_VERDE_MEDIO)
        canvas.line(2 * cm, 1.5 * cm, LETTER[0] - 2 * cm, 1.5 * cm)
        canvas.restoreState()


# =============================================================================
# Constructor del reporte
# =============================================================================
def generar_pdf(
    datos: DatosProyecto,
    muro_resumen: dict,
    parametros_sismo: dict | None,
    cargas_rows: list[list],
    combinaciones_elu_rows: list[list],
    combinaciones_els_rows: list[list],
    verificaciones_rows: list[list],
    presiones: dict,
    diseno_rows: list[list],
    resultado_global: dict,
    imagen_muro_png: bytes,
    momentos_estabilizadores_rows: list[list] | None = None,
    momentos_volcadores_rows: list[list] | None = None,
    totales_momentos: dict | None = None,
    imagen_empujes_png: bytes | None = None,
    imagen_sismo_png: bytes | None = None,
    incluye_sismo: bool = False,
    imagen_muro_nombres_png: bytes | None = None,
    imagen_muro_cotas_png: bytes | None = None,
    deslizamiento_detalle: dict | None = None,
    capacidad_carga_detalle: dict | None = None,
    excentricidad_detalle: dict | None = None,
    diseno_detalle: dict | None = None,
    imagen_esfuerzos_zapata_png: bytes | None = None,
    sistema_unidades: str = "MKS",
    tipo_muro: str = "voladizo",
    norma: str = "NSR10",
    estabilidad_global: dict | None = None,
    imagen_estab_global_png: bytes | None = None,
    contrafuertes: dict | None = None,
) -> bytes:
    """Genera el reporte PDF y lo devuelve como bytes.

    El parámetro ``tipo_muro`` determina si se incluyen las secciones de
    diseño estructural (vástago/punta/talón) y diagrama de esfuerzos en
    la zapata. Para muros de gravedad estas secciones se omiten porque
    no aplican (no llevan armadura por flexión).

    La numeración de secciones se controla por ``datos.numeracion_prefijo``:
    vacío = reporte independiente (1., 2., 3., ...);
    valor como "10" = reporte anidado (10.1, 10.2, ..., con subsecciones
    10.1.1, 10.1.2, ...).
    """
    es_gravedad = (tipo_muro == "gravedad")
    cfg = _config_norma(norma)          # textos y catálogo según la norma
    T = cfg["term"]                     # terminología (FS ↔ CDR, B/6 ↔ B/3, …)
    # Importación local para evitar ciclo de imports
    from retaining_wall.utils.formato import FormatoUnidades
    ufmt = FormatoUnidades(sistema_unidades)

    # Etiquetas de unidades que aparecen en los headers de tabla
    U_F    = ufmt.u_F_lineal      # kN/m  | tonf/m
    U_M    = ufmt.u_M_lineal      # kN·m/m | tonf·m/m
    U_Q    = ufmt.u_presion       # kPa    | tonf/m²

    buffer = io.BytesIO()

    # Numerador de secciones (independiente vs. anidado)
    num = Numerador(datos.numeracion_prefijo or None)

    doc = BaseDocTemplate(
        buffer, pagesize=LETTER,
        leftMargin=2 * cm, rightMargin=2 * cm,
        topMargin=2.2 * cm, bottomMargin=2 * cm,
        title=f"Reporte - {datos.proyecto}",
        author=datos.empresa or cfg["author"],
    )

    frame = Frame(2 * cm, 2 * cm,
                  LETTER[0] - 4 * cm, LETTER[1] - 4.2 * cm,
                  id="normal")
    plantilla = _PaginaPlantilla(datos, footer_label=cfg["footer"])
    doc.addPageTemplates([PageTemplate(id="main", frames=frame,
                                       onPage=plantilla.dibujar)])

    story = []

    # ============ PORTADA ============
    story.append(Spacer(1, 3 * cm))
    story.append(Paragraph("DISEÑO DE MURO DE CONTENCIÓN", TITULO_PORTADA))
    story.append(Paragraph(cfg["subtitulo"], SUBTITULO_PORTADA))
    story.append(Spacer(1, 2 * cm))

    filas_portada = [
        ["Proyecto", datos.proyecto or "—"],
        ["Empresa", datos.empresa or "—"],
        ["Ubicación", datos.ubicacion or "—"],
        ["Contratante", datos.contratante or "—"],
        ["Ingeniero responsable", datos.ingeniero or "—"],
        ["Fecha", datos.fecha],
    ]
    t = Table(filas_portada, colWidths=[5 * cm, 11 * cm])
    t.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 10.5),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("TEXTCOLOR", (0, 0), (0, -1), COLOR_TEXTO),
        ("TEXTCOLOR", (1, 0), (1, -1), COLOR_TEXTO),
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, COLOR_BORDE),
    ]))
    story.append(t)

    if datos.observaciones:
        story.append(Spacer(1, 1 * cm))
        story.append(Paragraph("<b>Observaciones:</b>", H3))
        story.append(Paragraph(datos.observaciones, BODY))

    story.append(PageBreak())

    # ============ FÓRMULAS UTILIZADAS (1 página, sólo referencia) ============
    story.append(Paragraph(
        f"{num.h1()} Fórmulas utilizadas en el análisis", H1))
    story.append(Paragraph(
        "Listado de las expresiones empleadas por el programa, agrupadas por "
        "tema. Esta sección es únicamente de referencia: las fórmulas no se "
        "aplican aquí, sólo se listan. Los cálculos con valores se presentan "
        "en las secciones posteriores.",
        BODY))
    story.append(Spacer(1, 0.15 * cm))

    # Construimos una sola tabla compacta con todos los grupos para
    # maximizar la posibilidad de caber en una página.
    filas_form: list[list] = []
    estilo_form = TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ("ALIGN", (1, 0), (1, -1), "LEFT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
        ("TEXTCOLOR", (0, 0), (0, -1), COLOR_TEXTO_SUAVE),
        ("TEXTCOLOR", (1, 0), (1, -1), COLOR_TEXTO),
        ("LINEBELOW", (0, 0), (-1, -1), 0.25, COLOR_BORDE),
    ])
    idx = 0
    for grupo_titulo, items in cfg["catalogo"]:
        # Fila-header del grupo (fusionada)
        filas_form.append([Paragraph(f"<b>{grupo_titulo}</b>",
                                     ParagraphStyle(
                                         "gh", fontSize=9, leading=11,
                                         textColor=COLOR_TEXTO,
                                         fontName="Helvetica-Bold")),
                          ""])
        estilo_form.add("SPAN", (0, idx), (1, idx))
        estilo_form.add("BACKGROUND", (0, idx), (1, idx),
                        COLOR_VERDE_CASI_BCO)
        estilo_form.add("TOPPADDING", (0, idx), (1, idx), 4)
        estilo_form.add("BOTTOMPADDING", (0, idx), (1, idx), 3)
        idx += 1
        for concepto_html, formula_html in items:
            filas_form.append([
                Paragraph(concepto_html, FORMULA_CONCEPTO),
                Paragraph(formula_html, FORMULA_EXPR),
            ])
            idx += 1

    t_form = Table(filas_form, colWidths=[6.8 * cm, 9.2 * cm])
    t_form.setStyle(estilo_form)
    story.append(t_form)
    story.append(PageBreak())

    # ============ DATOS DEL MURO ============
    story.append(Paragraph(
        f"{num.h1()} Datos del muro de contención", H1))
    filas = [["Parámetro", "Valor"]]
    for k, v in muro_resumen.items():
        filas.append([k, str(v)])
    t = Table(filas, colWidths=[9 * cm, 7 * cm])
    t.setStyle(_estilo_tabla_datos())
    story.append(t)
    story.append(Spacer(1, 0.4 * cm))

    # ============ VISTA GRÁFICA DEL MURO ============
    # --- Esquema con identificación de partes (primera figura) ---
    img_nombres = imagen_muro_nombres_png or imagen_muro_png
    img_stream_nombres = io.BytesIO(img_nombres)
    img1 = Image(img_stream_nombres, width=17 * cm, height=11.7 * cm,
                 kind="proportional")
    # Título + subtítulo + descripción + imagen se mantienen juntos en una
    # sola página (evita que el H1 quede huérfano al final de la anterior).
    story.append(KeepTogether([
        Paragraph(f"{num.h1()} Vista gráfica del muro", H1),
        Paragraph(
            f"<b>{num.h2()} Identificación de las partes del muro</b>", H2),
        Paragraph(
            "Esquema del muro con el nombre de cada elemento: zapata, vástago "
            "(pantalla), puntera, talón, corona y — si aplica — diente de cortante. "
            "Se indican también el suelo de cimentación, el relleno retenido y "
            "el nivel de terreno frontal.", BODY),
        img1,
    ]))
    story.append(PageBreak())

    # --- Esquema con cotas y dimensiones ---
    img_cotas = imagen_muro_cotas_png or imagen_muro_png
    story.append(Paragraph(
        f"<b>{num.h2()} Cotas y dimensiones</b>", H2))
    story.append(Paragraph(
        "Mismo muro con las dimensiones numéricas de cada cota. Las cotas "
        "verticales se muestran a la izquierda (espesor de zapata, altura "
        "del vástago, altura de relleno) y a la derecha (profundidad de "
        "desplante D). Las horizontales aparecen abajo (puntera, base del "
        "vástago, talón y ancho total B) y arriba (ancho de corona).", BODY))
    img_stream_cotas = io.BytesIO(img_cotas)
    img2 = Image(img_stream_cotas, width=17 * cm, height=11.7 * cm,
                 kind="proportional")
    story.append(img2)
    story.append(PageBreak())

    # ============ PARÁMETROS SÍSMICOS ============
    if parametros_sismo:
        story.append(Paragraph(
            f"{num.h1()} {cfg['sismo_titulo']}", H1))
        filas = [["Parámetro", "Valor"]]
        for k, v in parametros_sismo.items():
            filas.append([k, str(v)])
        t = Table(filas, colWidths=[9 * cm, 7 * cm])
        t.setStyle(_estilo_tabla_datos())
        story.append(t)
        story.append(Spacer(1, 0.5 * cm))

    # ============ CARGAS CARACTERÍSTICAS ============
    story.append(Paragraph(f"{num.h1()} Cargas características", H1))
    story.append(Paragraph(
        "Cargas por metro lineal de muro, obtenidas sin mayorar.", BODY))
    header = ["#", "Carga", f"Magnitud ({U_F})", "Tipo", "Cat."]
    filas = [header] + cargas_rows
    t = Table(filas, colWidths=[1 * cm, 6.5 * cm, 3.5 * cm, 3 * cm, 2 * cm])
    t.setStyle(_estilo_tabla_resultado())
    story.append(t)
    story.append(Spacer(1, 0.5 * cm))

    # ------------ DIAGRAMA DE EMPUJES LATERALES ------------
    if imagen_empujes_png:
        story.append(PageBreak())
        story.append(Paragraph(
            f"<b>{num.h2()} Diagrama de presiones laterales</b>", H2))
        story.append(Paragraph(
            "Distribución de presiones sobre el muro: empuje activo "
            "(triangular, Rankine), empuje por sobrecarga (rectangular) y "
            "empuje pasivo en la puntera (triangular). Se indican las "
            "resultantes P<sub>a</sub>, P<sub>q</sub> y P<sub>p</sub> con "
            "sus puntos de aplicación.",
            BODY))
        img_stream_emp = io.BytesIO(imagen_empujes_png)
        img_emp = Image(img_stream_emp, width=16 * cm, height=10.3 * cm,
                        kind="proportional")
        story.append(img_emp)
        story.append(Spacer(1, 0.3 * cm))

    # ------------ DIAGRAMA DE CARGAS SÍSMICAS ------------
    if imagen_sismo_png and incluye_sismo:
        story.append(PageBreak())
        story.append(Paragraph(
            f"<b>{num.h2()} Diagrama de cargas sísmicas (Mononobe-Okabe)</b>", H2))
        story.append(Paragraph(cfg["sismo_diagrama"], BODY))
        img_stream_sis = io.BytesIO(imagen_sismo_png)
        img_sis = Image(img_stream_sis, width=16 * cm, height=10.3 * cm,
                        kind="proportional")
        story.append(img_sis)
        story.append(Spacer(1, 0.3 * cm))

    story.append(PageBreak())

    # ============ COMBINACIONES DE CARGA ============
    # Para muros de gravedad omitimos las ELU (no se diseña por flexión).
    # Las ELS se mantienen en ambos casos porque sirven para verificar
    # presiones admisibles del suelo.
    story.append(Paragraph(f"{num.h1()} {cfg['combos_titulo']}", H1))
    if not es_gravedad and combinaciones_elu_rows:
        story.append(Paragraph(
            f"<b>{num.h2()} {cfg['combos_sub']}</b>", H2))
        header = ["Combinación",
                  f"V ({U_F})", f"H ({U_F})",
                  f"M_est ({U_M})", f"M_volc ({U_M})"]
        filas = [header] + combinaciones_elu_rows
        t = Table(filas, colWidths=[5.5 * cm, 2.4 * cm, 2.4 * cm, 2.8 * cm, 2.9 * cm])
        t.setStyle(_estilo_tabla_resultado())
        story.append(t)
        story.append(Spacer(1, 0.4 * cm))
    elif es_gravedad:
        story.append(Paragraph(cfg["combos_gravedad"], BODY))

    if combinaciones_els_rows:
        header = ["Combinación",
                  f"V ({U_F})", f"H ({U_F})",
                  f"M_est ({U_M})", f"M_volc ({U_M})"]
        story.append(Paragraph(
            f"<b>{num.h2()} Estado Límite de Servicio (ELS, B.2.3)</b>", H2))
        filas = [header] + combinaciones_els_rows
        t = Table(filas, colWidths=[5.5 * cm, 2.4 * cm, 2.4 * cm, 2.8 * cm, 2.9 * cm])
        t.setStyle(_estilo_tabla_resultado())
        story.append(t)
    story.append(PageBreak())

    # ============ MOMENTOS (DESGLOSE DEL CÁLCULO) ============
    if momentos_estabilizadores_rows or momentos_volcadores_rows:
        story.append(Paragraph(
            f"{num.h1()} Cálculo de momentos respecto a la puntera (C)", H1))
        story.append(Paragraph(
            cfg["momentos_nota"] + f" Fuerzas en {U_F}, brazos en m, "
            f"momentos en {U_M}.", BODY))

        tot = totales_momentos or {}
        header_mom = ["#", "Elemento / carga", "Cat.", "Tipo",
                      f"F ({U_F})", "Brazo (m)", f"M ({U_M})"]

        # Estabilizadores
        story.append(Paragraph(
            f"<b>{num.h2()} Momentos estabilizadores</b> (M<sub>R</sub>)", H2))
        filas = [header_mom]
        for i, row in enumerate(momentos_estabilizadores_rows or [], start=1):
            filas.append([str(i)] + list(row))
        filas.append(["", "Σ M_R", "", "", "", "",
                      f"{tot.get('SMR', 0):.2f}"])
        t = Table(filas,
                  colWidths=[0.9*cm, 5.6*cm, 1.2*cm, 1.1*cm,
                             2.0*cm, 2.0*cm, 2.5*cm])
        estilo = _estilo_tabla_resultado()
        estilo.add("BACKGROUND", (0, -1), (-1, -1), COLOR_OK_BG)
        estilo.add("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold")
        t.setStyle(estilo)
        story.append(t)
        story.append(Spacer(1, 0.4 * cm))

        # Volcadores
        story.append(Paragraph(
            f"<b>{num.h2()} Momentos volcadores</b> (M<sub>o</sub>)", H2))
        filas = [header_mom]
        for i, row in enumerate(momentos_volcadores_rows or [], start=1):
            filas.append([str(i)] + list(row))
        filas.append(["", "Σ M_o", "", "", "", "",
                      f"{tot.get('SMo', 0):.2f}"])
        t = Table(filas,
                  colWidths=[0.9*cm, 5.6*cm, 1.2*cm, 1.1*cm,
                             2.0*cm, 2.0*cm, 2.5*cm])
        estilo = _estilo_tabla_resultado()
        estilo.add("BACKGROUND", (0, -1), (-1, -1), COLOR_ERR_BG)
        estilo.add("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold")
        t.setStyle(estilo)
        story.append(t)
        story.append(Spacer(1, 0.4 * cm))

        # FS al volcamiento — solo en NSR-10 (esfuerzos admisibles).
        # En CCP-14 el vuelco se controla por el límite de excentricidad con
        # cargas mayoradas (ver la sección de excentricidad).
        if cfg["id"] == "CCP14":
            story.append(Paragraph(
                "<b>Nota (CCP-14):</b> el vuelco no se verifica con un factor de "
                "seguridad global. La estabilidad al vuelco se controla mediante "
                "el límite de excentricidad de la resultante con cargas mayoradas "
                "(|e| ≤ B/3 en suelo), presentado en la sección de excentricidad "
                "(Art. 11.6.3.3).", BODY))
        else:
            story.append(Paragraph(
                f"<b>{num.h2()} {T['volc_titulo']}</b>", H2))
            FS = tot.get("FS_volcamiento")
            FS_req = tot.get("FS_requerido", 2.0)
            FS_txt = ("∞" if FS is None
                      else (f"{FS:.3f}" if isinstance(FS, (int, float)) else str(FS)))
            estado_fs = ("CUMPLE" if (FS is None or
                         (isinstance(FS, (int, float)) and FS >= FS_req))
                         else "NO CUMPLE")
            filas_fs = [
                ["Concepto", "Valor"],
                [f"ΣM_R ({U_M})", f"{tot.get('SMR', 0):.2f}"],
                [f"ΣM_o ({U_M})", f"{tot.get('SMo', 0):.2f}"],
                [T["volc_formula_label"], FS_txt],
                [T["min_label"], f"{FS_req:.2f}"],
                ["Estado", estado_fs],
            ]
            t = Table(filas_fs, colWidths=[9 * cm, 7 * cm])
            estilo = _estilo_tabla_datos()
            color = COLOR_OK_BG if estado_fs == "CUMPLE" else COLOR_ERR_BG
            estilo.add("BACKGROUND", (-1, -1), (-1, -1), color)
            estilo.add("FONTNAME", (-1, -1), (-1, -1), "Helvetica-Bold")
            t.setStyle(estilo)
            story.append(t)
        story.append(PageBreak())

    # ============ DESLIZAMIENTO — CÁLCULO DETALLADO ============
    if deslizamiento_detalle:
        story.append(Paragraph(
            f"{num.h1()} {T['desliz_titulo']}", H1))
        story.append(Paragraph(T["desliz_intro"], BODY))

        # Parámetros
        story.append(Paragraph(
            f"<b>{num.h2()} Parámetros de cálculo</b>", H2))
        filas = [["Parámetro", "Valor"]]
        for p in deslizamiento_detalle.get("parametros", []):
            val = p["valor"]
            unidad = p.get("unidad", "")
            filas.append([p["nombre"],
                          f"{val:.2f} {unidad}" if isinstance(val, (int, float))
                          else f"{val} {unidad}"])
        t = Table(filas, colWidths=[9.5 * cm, 6.5 * cm])
        t.setStyle(_estilo_tabla_datos())
        story.append(t)
        story.append(Spacer(1, 0.3 * cm))

        # Fuerzas resistentes
        story.append(Paragraph(
            f"<b>{num.h2()} Fuerzas resistentes al deslizamiento</b>", H2))
        header = ["Componente", "Fórmula", "Cálculo", f"Valor ({U_F})"]
        filas = [header]
        for f in deslizamiento_detalle.get("fuerzas_resistentes", []):
            filas.append([f["nombre"], f["formula"],
                          f.get("detalle", ""), f"{f['valor']:.2f}"])
        F_res = deslizamiento_detalle["totales"]["F_resistente"]
        filas.append(["", "Σ F_resistente", "", f"{F_res:.2f}"])
        t = Table(filas, colWidths=[4.0 * cm, 4.0 * cm, 5.5 * cm, 2.5 * cm])
        estilo = _estilo_tabla_resultado()
        estilo.add("BACKGROUND", (0, -1), (-1, -1), COLOR_OK_BG)
        estilo.add("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold")
        t.setStyle(estilo)
        story.append(t)
        story.append(Spacer(1, 0.3 * cm))

        # Fuerzas actuantes
        story.append(Paragraph(
            f"<b>{num.h2()} Fuerzas actuantes (desestabilizadoras)</b>", H2))
        filas = [header]
        for f in deslizamiento_detalle.get("fuerzas_actuantes", []):
            filas.append([f["nombre"], f["formula"],
                          f.get("detalle", ""), f"{f['valor']:.2f}"])
        F_act = deslizamiento_detalle["totales"]["F_actuante"]
        filas.append(["", "Σ F_actuante", "", f"{F_act:.2f}"])
        t = Table(filas, colWidths=[4.0 * cm, 4.0 * cm, 5.5 * cm, 2.5 * cm])
        estilo = _estilo_tabla_resultado()
        estilo.add("BACKGROUND", (0, -1), (-1, -1), COLOR_ERR_BG)
        estilo.add("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold")
        t.setStyle(estilo)
        story.append(t)
        story.append(Spacer(1, 0.3 * cm))

        # Factor de seguridad / relación capacidad-demanda
        story.append(Paragraph(
            f"<b>{num.h2()} {T['desliz_fs_titulo']}</b>", H2))
        tot = deslizamiento_detalle["totales"]
        FS_val = tot["FS"]
        FS_min = tot["FS_min"]
        FS_txt = ("∞" if not (FS_val == FS_val and FS_val != float("inf"))
                  else f"{FS_val:.3f}")
        estado = "CUMPLE" if (FS_val != FS_val or FS_val >= FS_min) else "NO CUMPLE"
        if FS_val == FS_val and FS_val != float("inf"):
            estado = "CUMPLE" if FS_val >= FS_min else "NO CUMPLE"
        filas_fs = [
            ["Concepto", "Valor"],
            ["Σ F_resistente", f"{F_res:.2f} {U_F}"],
            ["Σ F_actuante",   f"{F_act:.2f} {U_F}"],
            [T["desliz_fs_label"], FS_txt],
            [T["min_label"], f"{FS_min:.2f}"],
            ["Estado", estado],
        ]
        t = Table(filas_fs, colWidths=[9 * cm, 7 * cm])
        estilo = _estilo_tabla_datos()
        color = COLOR_OK_BG if estado == "CUMPLE" else COLOR_ERR_BG
        estilo.add("BACKGROUND", (-1, -1), (-1, -1), color)
        estilo.add("FONTNAME", (-1, -1), (-1, -1), "Helvetica-Bold")
        t.setStyle(estilo)
        story.append(t)
        story.append(PageBreak())

    # ============ CAPACIDAD DE CARGA — CÁLCULO DETALLADO ============
    if capacidad_carga_detalle:
        story.append(Paragraph(
            f"{num.h1()} {T['capac_titulo']}", H1))
        story.append(Paragraph(T["capac_intro"], BODY))

        # Parámetros
        story.append(Paragraph(
            f"<b>{num.h2()} Parámetros del suelo y la zapata</b>", H2))
        filas = [["Parámetro", "Valor"]]
        for p in capacidad_carga_detalle.get("parametros", []):
            val = p["valor"]
            unidad = p.get("unidad", "")
            filas.append([p["nombre"],
                          f"{val:.2f} {unidad}" if isinstance(val, (int, float))
                          else f"{val} {unidad}"])
        t = Table(filas, colWidths=[9.5 * cm, 6.5 * cm])
        t.setStyle(_estilo_tabla_datos())
        story.append(t)
        story.append(Spacer(1, 0.3 * cm))

        # Factores N
        story.append(Paragraph(
            f"<b>{num.h2()} Factores de capacidad de carga N</b> (dependen de φ)", H2))
        filas = [["Factor", "Expresión", "Valor"]]
        for f in capacidad_carga_detalle.get("factores_N", []):
            filas.append([f["nombre"], f.get("formula", ""),
                          f"{f['valor']:.2f}"])
        t = Table(filas, colWidths=[4.5 * cm, 8.0 * cm, 3.5 * cm])
        t.setStyle(_estilo_tabla_resultado())
        story.append(t)
        story.append(Spacer(1, 0.3 * cm))

        # Factores de profundidad
        story.append(Paragraph(
            f"<b>{num.h2()} Factores de profundidad F<sub>d</sub></b> (Hansen)", H2))
        filas = [["Factor", "Valor"]]
        for f in capacidad_carga_detalle.get("factores_d", []):
            filas.append([f["nombre"], f"{f['valor']:.2f}"])
        t = Table(filas, colWidths=[11.5 * cm, 4.5 * cm])
        t.setStyle(_estilo_tabla_datos())
        story.append(t)
        story.append(Spacer(1, 0.3 * cm))

        # Factores de inclinación
        story.append(Paragraph(
            f"<b>{num.h2()} Factores de inclinación de carga F<sub>i</sub></b>", H2))
        filas = [["Factor", "Expresión", "Valor"]]
        for f in capacidad_carga_detalle.get("factores_i", []):
            filas.append([f["nombre"], f.get("formula", ""),
                          f"{f['valor']:.2f}"])
        t = Table(filas, colWidths=[5.0 * cm, 7.5 * cm, 3.5 * cm])
        t.setStyle(_estilo_tabla_resultado())
        story.append(t)
        story.append(Spacer(1, 0.3 * cm))

        # Términos
        story.append(Paragraph(
            f"<b>{num.h2()} Términos de la ecuación de capacidad</b>", H2))
        header = ["Término", "Fórmula", "Cálculo", f"Aporte ({U_Q})"]
        filas = [header]
        for t_dict in capacidad_carga_detalle.get("terminos", []):
            filas.append([t_dict["nombre"], t_dict["formula"],
                          t_dict.get("detalle", ""),
                          f"{t_dict['valor']:.2f}"])
        qu_val = capacidad_carga_detalle["totales"]["qu"]
        filas.append(["", "q_u (total)", "", f"{qu_val:.2f}"])
        t = Table(filas, colWidths=[3.8 * cm, 3.5 * cm, 6.2 * cm, 2.5 * cm])
        estilo = _estilo_tabla_resultado()
        estilo.add("BACKGROUND", (0, -1), (-1, -1), COLOR_OK_BG)
        estilo.add("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold")
        t.setStyle(estilo)
        story.append(t)
        story.append(Spacer(1, 0.3 * cm))

        # FS
        story.append(Paragraph(
            f"<b>{num.h2()} {T['capac_fs_titulo']}</b>", H2))
        tot_cc = capacidad_carga_detalle["totales"]
        FS_cc = tot_cc["FS"]
        FS_cc_min = tot_cc["FS_min"]
        FS_txt = ("∞" if FS_cc == float("inf")
                  else f"{FS_cc:.3f}")
        estado_cc = "CUMPLE" if (FS_cc == float("inf") or FS_cc >= FS_cc_min) \
                    else "NO CUMPLE"
        filas_fs = [
            ["Concepto", "Valor"],
            [T["capac_qu_label"],   f"{tot_cc['qu']:.2f} {U_Q}"],
            [T["capac_qmax_label"], f"{tot_cc['q_max']:.2f} {U_Q}"],
            [T["capac_fs_label"], FS_txt],
            [T["min_label"], f"{FS_cc_min:.2f}"],
            ["Estado", estado_cc],
        ]
        t = Table(filas_fs, colWidths=[9 * cm, 7 * cm])
        estilo = _estilo_tabla_datos()
        color = COLOR_OK_BG if estado_cc == "CUMPLE" else COLOR_ERR_BG
        estilo.add("BACKGROUND", (-1, -1), (-1, -1), color)
        estilo.add("FONTNAME", (-1, -1), (-1, -1), "Helvetica-Bold")
        t.setStyle(estilo)
        story.append(t)
        story.append(PageBreak())

    # ============ EXCENTRICIDAD — CÁLCULO DETALLADO ============
    if excentricidad_detalle:
        story.append(Paragraph(
            f"{num.h1()} Cálculo detallado de la Excentricidad", H1))
        story.append(Paragraph(
            "Descomposición paso a paso del cálculo de la excentricidad "
            "<b>e</b> de la resultante vertical respecto al eje de la "
            f"base, y verificación de que cae en {T['excent_intro_zona']} "
            "para evitar tensiones en el talón / pérdida de contacto en la base.",
            BODY))

        # Parámetros
        story.append(Paragraph(
            f"<b>{num.h2()} Parámetros de entrada</b>", H2))
        filas = [["Parámetro", "Valor"]]
        for p in excentricidad_detalle.get("parametros", []):
            val = p["valor"]
            unidad = p.get("unidad", "")
            filas.append([p["nombre"],
                          f"{val:.2f} {unidad}" if isinstance(val, (int, float))
                          else f"{val} {unidad}"])
        t = Table(filas, colWidths=[9.5 * cm, 6.5 * cm])
        t.setStyle(_estilo_tabla_datos())
        story.append(t)
        story.append(Spacer(1, 0.3 * cm))

        # Pasos del cálculo
        story.append(Paragraph(
            f"<b>{num.h2()} Pasos del cálculo</b>", H2))
        _pc = ParagraphStyle("excConcept", parent=_styles["Normal"],
                             fontSize=8.5, leading=10.2, textColor=COLOR_TEXTO)
        _pf = ParagraphStyle("excForm", parent=_styles["Normal"],
                             fontSize=8.2, leading=10.0, textColor=COLOR_TEXTO_SUAVE)
        header = ["#", "Concepto", "Fórmula", "Cálculo", "Valor"]
        filas = [header]
        for i, paso in enumerate(excentricidad_detalle.get("pasos", []),
                                 start=1):
            val = paso["valor"]
            unidad = paso.get("unidad", "")
            filas.append([
                str(i),
                Paragraph(paso["nombre"], _pc),
                Paragraph(paso["formula"], _pf),
                Paragraph(paso.get("detalle", ""), _pf),
                f"{val:.2f} {unidad}" if isinstance(val, (int, float))
                else f"{val} {unidad}",
            ])
        t = Table(filas, colWidths=[0.8*cm, 4.9*cm, 3.5*cm, 3.5*cm, 3.3*cm])
        estilo_exc = _estilo_tabla_resultado()
        estilo_exc.add("VALIGN", (0, 1), (-1, -1), "MIDDLE")
        t.setStyle(estilo_exc)
        story.append(t)
        story.append(Spacer(1, 0.3 * cm))

        # Verificación final
        story.append(Paragraph(
            f"<b>{num.h2()} Verificación</b>", H2))
        tot_e = excentricidad_detalle["totales"]
        estado_e = tot_e.get("estado", "CUMPLE")
        filas_fs = [
            ["Concepto", "Valor"],
            ["Excentricidad calculada |e|", f"{tot_e['abs_e']:.2f} m"],
            ["Dirección de la excentricidad", tot_e.get("lado", "—")],
            [T["excent_limite_label"], f"{tot_e['limite']:.2f} m"],
            ["Condición", T["excent_condicion"]],
            ["Estado", estado_e],
        ]
        t = Table(filas_fs, colWidths=[9 * cm, 7 * cm])
        estilo = _estilo_tabla_datos()
        color = COLOR_OK_BG if estado_e == "CUMPLE" else COLOR_ERR_BG
        estilo.add("BACKGROUND", (-1, -1), (-1, -1), color)
        estilo.add("FONTNAME", (-1, -1), (-1, -1), "Helvetica-Bold")
        t.setStyle(estilo)
        story.append(t)
        story.append(PageBreak())

    # ============ VERIFICACIONES (RESUMEN) ============
    story.append(Paragraph(
        f"{num.h1()} Verificaciones de estabilidad — Resumen", H1))
    story.append(Paragraph(
        "Tabla resumen de las cuatro verificaciones geotécnicas. El cálculo "
        "detallado de cada una de ellas se presenta en las secciones "
        "anteriores (momentos, deslizamiento y capacidad de carga). "
        + ("Se reporta la relación capacidad/demanda (CDR ≥ 1.0) con cargas "
           "mayoradas por los factores de la CCP-14."
           if cfg["id"] == "CCP14"
           else "Todas las verificaciones se realizan con cargas características "
                "(sin mayorar)."),
        BODY))
    header = ["Verificación", "Calculado", cfg["verif_min_header"], "Unid.", "Estado"]
    filas = [header] + verificaciones_rows
    t = Table(filas, colWidths=[6.5 * cm, 2.8 * cm, 2.5 * cm, 1.5 * cm, 2.7 * cm])
    estilo = _estilo_tabla_resultado()
    for i, row in enumerate(verificaciones_rows, start=1):
        if "CUMPLE" in row[-1]:
            estilo.add("BACKGROUND", (-1, i), (-1, i), COLOR_OK_BG)
            estilo.add("TEXTCOLOR", (-1, i), (-1, i), COLOR_OK_TXT)
        else:
            estilo.add("BACKGROUND", (-1, i), (-1, i), COLOR_ERR_BG)
            estilo.add("TEXTCOLOR", (-1, i), (-1, i), COLOR_ERR_TXT)
        estilo.add("FONTNAME", (-1, i), (-1, i), "Helvetica-Bold")
    t.setStyle(estilo)
    story.append(t)
    story.append(Spacer(1, 0.25 * cm))
    story.append(Paragraph(cfg["verif_base"], BODY))
    story.append(Spacer(1, 0.4 * cm))

    # Presiones
    story.append(Paragraph("<b>Presiones bajo la zapata:</b>", H3))
    filas = [["Descripción", "Valor"]]
    for k, v in presiones.items():
        filas.append([k, f"{v:.2f}" if isinstance(v, (int, float)) else str(v)])
    t = Table(filas, colWidths=[9 * cm, 7 * cm])
    t.setStyle(_estilo_tabla_datos())
    story.append(t)
    story.append(Spacer(1, 0.4 * cm))

    # ============ ESTABILIDAD GLOBAL (falla profunda por dovelas) ============
    if estabilidad_global and estabilidad_global.get("disponible"):
        eg = estabilidad_global
        story.append(Paragraph(
            f"<b>{num.h2()} Estabilidad global (falla de talud profunda)</b>", H2))
        story.append(Paragraph(
            "Verificación de que el conjunto muro + suelo no falle a lo largo "
            "de una superficie de deslizamiento profunda que envuelve la "
            "cimentación. Se emplea el método de las dovelas sobre superficies "
            "circulares (Fellenius ordinario y Bishop simplificado) con "
            "búsqueda del círculo crítico (el de menor factor de seguridad). "
            "El FS mínimo recomendado es 1.5 en condición estática y 1.1 con "
            "sismo (EN 1997 / FHWA).", BODY))
        estado_eg = eg.get("estado", "—")
        c = eg.get("circulo", {})
        filas_eg = [
            ["Parámetro", "Valor"],
            ["FS mínimo (crítico)", f"{eg.get('FS_min', 0):.2f}"],
            ["FS requerido", f"{eg.get('FS_requerido', 1.5):.1f}"],
            ["Estado", estado_eg],
            ["FS Bishop simplificado", f"{eg.get('FS_bishop', 0):.2f}"],
            ["FS Fellenius (ordinario)", f"{eg.get('FS_fellenius', 0):.2f}"],
            ["Método gobernante", str(eg.get("metodo", "bishop")).capitalize()],
            ["Incluye nivel freático", "Sí" if eg.get("incluye_agua") else "No"],
            ["Centro del círculo (x, y)", f"({c.get('xc','—')}, {c.get('yc','—')}) m"],
            ["Radio", f"{c.get('R','—')} m"],
            ["Profundidad bajo la base", f"{c.get('profundidad_bajo_base','—')} m"],
            ["Nº de dovelas", str(c.get("n_dovelas", "—"))],
        ]
        t = Table(filas_eg, colWidths=[9 * cm, 7 * cm])
        estilo_eg = _estilo_tabla_datos()
        idx_estado = 3
        if "NO" in estado_eg or "✗" in estado_eg:
            estilo_eg.add("BACKGROUND", (1, idx_estado), (1, idx_estado), COLOR_ERR_BG)
            estilo_eg.add("TEXTCOLOR", (1, idx_estado), (1, idx_estado), COLOR_ERR_TXT)
        else:
            estilo_eg.add("BACKGROUND", (1, idx_estado), (1, idx_estado), COLOR_OK_BG)
            estilo_eg.add("TEXTCOLOR", (1, idx_estado), (1, idx_estado), COLOR_OK_TXT)
        estilo_eg.add("FONTNAME", (1, idx_estado), (1, idx_estado), "Helvetica-Bold")
        t.setStyle(estilo_eg)
        story.append(t)
        story.append(Spacer(1, 0.3 * cm))
        if imagen_estab_global_png:
            img_stream_eg = io.BytesIO(imagen_estab_global_png)
            story.append(Image(img_stream_eg, width=16 * cm, height=10.3 * cm,
                               kind="proportional"))

    # ============ DISEÑO DE CONTRAFUERTES ============
    if contrafuertes and contrafuertes.get("disponible"):
        story.append(Spacer(1, 0.4 * cm))
        story.append(Paragraph(
            f"<b>{num.h2()} Diseño de contrafuertes</b>", H2))
        story.append(Paragraph(
            "La estabilidad externa es idéntica a la de un muro en voladizo "
            "equivalente. La pantalla y el talón flexionan horizontalmente como "
            "losas continuas apoyadas en los contrafuertes (M = w·s²/10), y el "
            "contrafuerte trabaja como una viga T en voladizo empotrada en la "
            f"zapata. Separación s = {contrafuertes['separacion_m']:.2f} m, "
            f"espesor del contrafuerte = {contrafuertes['espesor_contrafuerte_m']:.2f} m, "
            f"K<sub>a</sub> = {contrafuertes['Ka']}, presión lateral en la base "
            f"= {contrafuertes['p_base_kPa']:.2f} kPa.", BODY))
        header = ["Elemento", "Mu", "As requerido", "Espesor/b_w (m)", "Estado"]
        filas = [header] + contrafuertes.get("tabla_rows", [])
        t = Table(filas, colWidths=[6 * cm, 3.2 * cm, 3.2 * cm, 2.6 * cm, 2 * cm])
        estilo = _estilo_tabla_resultado()
        for i, row in enumerate(contrafuertes.get("tabla_rows", []), start=1):
            ok = "OK" in row[-1]
            estilo.add("BACKGROUND", (-1, i), (-1, i),
                       COLOR_OK_BG if ok else COLOR_ERR_BG)
            estilo.add("TEXTCOLOR", (-1, i), (-1, i),
                       COLOR_OK_TXT if ok else COLOR_ERR_TXT)
            estilo.add("FONTNAME", (-1, i), (-1, i), "Helvetica-Bold")
        t.setStyle(estilo)
        story.append(t)
        cfd = contrafuertes.get("contrafuerte", {})
        tir = contrafuertes.get("tirantes", {})
        story.append(Spacer(1, 0.2 * cm))
        story.append(Paragraph(
            f"<b>Contrafuerte:</b> P = {cfd.get('P_total_kN', 0):.0f} kN a "
            f"{cfd.get('y_aplicacion_m', 0):.2f} m de la base, d = "
            f"{cfd.get('d_m', 0):.2f} m, Vu = {cfd.get('Vu_kN', 0):.0f} kN / "
            f"φVc = {cfd.get('phiVc_kN', 0):.0f} kN"
            + (" (requiere estribos). " if cfd.get("requiere_estribos") else ". ")
            + f"<b>Tirantes:</b> pantalla ↔ contrafuerte = "
            f"{tir.get('pantalla_As_mm2_m', 0):.0f} mm²/m, talón ↔ contrafuerte = "
            f"{tir.get('talon_As_mm2_m', 0):.0f} mm²/m.", BODY))
        for nota in contrafuertes.get("notas", []):
            story.append(Paragraph(f"⚠ {nota}", BODY))
    story.append(PageBreak())

    # ============ DISEÑO ESTRUCTURAL ============
    # Solo aplica para muros que resisten por flexión (voladizo,
    # contrafuertes). Los muros de gravedad resisten por su propio peso
    # y no llevan armadura por flexión, así que esta sección se omite y
    # se sustituye por una breve nota explicativa.
    if es_gravedad:
        story.append(Paragraph(
            f"{num.h1()} Diseño estructural", H1))
        story.append(Paragraph(
            "Los muros de gravedad resisten los empujes por su propio peso, "
            "no por flexión. No se requiere armadura por flexión para el "
            "cuerpo del muro ni para la zapata, por lo que esta sección "
            "no incluye cálculos de cuantías de acero ni de capacidad a "
            "cortante. Si la verificación de estabilidad y la capacidad de "
            "carga del suelo se cumplen, el muro es estructuralmente "
            "adecuado. Para refuerzo por temperatura/contracción y "
            "consideraciones constructivas (juntas, drenaje, lloraderos) "
            f"consulte la {cfg['estructural_gravedad_ref']} y las recomendaciones "
            "de Das (§8.10).",
            BODY))
        story.append(Spacer(1, 0.6 * cm))
    else:
        story.append(Paragraph(
            f"{num.h1()} {cfg['estructural_titulo']}", H1))
        story.append(Paragraph(
            "Refuerzo longitudinal por flexión y verificación a cortante para "
            "cada elemento, por metro lineal de muro. Se diseñan tres elementos: "
            "el vástago (empotramiento en la base), la punta de la zapata "
            "(voladizo frontal) y el talón (voladizo posterior). En las "
            "subsecciones siguientes se presenta (a) el diagrama de esfuerzos "
            "bajo la zapata con el valor de la presión en cada lado y las "
            "secciones críticas, (b) el paso a paso del cálculo de M_u y la "
            "cuantía ρ para cada elemento, y (c) la tabla resumen de resultados.",
            BODY))

        # --- Subsección: diagrama de esfuerzos en la zapata ---
        if imagen_esfuerzos_zapata_png:
            story.append(Paragraph(
                f"<b>{num.h2()} Diagrama de esfuerzos bajo la zapata</b>", H2))
            story.append(Paragraph(
                "Distribución de presiones de contacto del suelo sobre la "
                "zapata (sin mayorar), con sus valores en la puntera, en la "
                "cara frontal del vástago, en la cara posterior del vástago "
                "y en el talón. Las líneas punteadas rojas marcan las "
                "secciones críticas donde se calcula el momento M_u de cada "
                "voladizo.",
                BODY))
            img_stream_zap = io.BytesIO(imagen_esfuerzos_zapata_png)
            img_zap = Image(img_stream_zap, width=17 * cm, height=8.3 * cm,
                            kind="proportional")
            story.append(img_zap)
            story.append(Spacer(1, 0.3 * cm))

    # --- Subsección: paso a paso del cálculo por elemento ---
    if diseno_detalle and not es_gravedad:
        story.append(PageBreak())
        story.append(Paragraph(
            f"<b>{num.h2()} Paso a paso del cálculo estructural</b>", H2))
        story.append(Paragraph(cfg["estructural_pasos_nota"], BODY))

        # Estilo compacto común a las tablas de pasos
        _cell_concept = ParagraphStyle(
            "cellConcept", parent=_styles["Normal"],
            fontSize=8.5, leading=10.5, textColor=COLOR_TEXTO,
            fontName="Helvetica")
        _cell_formula = ParagraphStyle(
            "cellFormula", parent=_styles["Normal"],
            fontSize=8.2, leading=10.0, textColor=COLOR_TEXTO_SUAVE,
            fontName="Helvetica")
        _cell_valor = ParagraphStyle(
            "cellValor", parent=_styles["Normal"],
            fontSize=8.5, leading=10.5, textColor=COLOR_TEXTO,
            fontName="Helvetica-Bold", alignment=TA_CENTER)

        def _mini_header_fila() -> list[str]:
            return ["#", "Concepto", "Fórmula", "Cálculo", "Valor"]

        def _fila_paso(i: int, p: dict) -> list:
            val = p.get("valor", "")
            u   = p.get("unidad", "")
            if isinstance(val, (int, float)):
                # Política: 2 decimales en todos los números, salvo cuantías
                # (adimensionales, típicamente 0.003–0.02) donde se usan 5
                # decimales para conservar precisión.
                if abs(val) < 0.1 and u in ("-", ""):
                    vstr = f"{val:.5f}"
                else:
                    vstr = f"{val:.2f}"
                txt = f"{vstr} {u}".strip()
            else:
                txt = f"{val} {u}".strip()
            return [str(i),
                    Paragraph(p.get("nombre", ""),  _cell_concept),
                    Paragraph(p.get("formula", ""), _cell_formula),
                    Paragraph(p.get("detalle", ""), _cell_formula),
                    Paragraph(txt, _cell_valor)]

        col_widths_pasos = [0.7*cm, 4.5*cm, 4.3*cm, 4.7*cm, 3.1*cm]

        for clave in ("vastago", "punta", "talon"):
            d = diseno_detalle.get(clave)
            if not d: continue

            story.append(Spacer(1, 0.2 * cm))
            story.append(Paragraph(
                f"<b>{num.h2()} {d.get('titulo','')}</b>", H2))
            estado = d.get("estado", "")
            est_color_txt = "#065f46" if estado == "CUMPLE" else "#991b1b"
            story.append(Paragraph(
                f"Estado del elemento: "
                f"<b><font color='{est_color_txt}'>{estado}</font></b>",
                BODY))

            # Datos de entrada
            story.append(Paragraph("<b>Datos de entrada</b>", H3))
            filas_de = [["Parámetro", "Valor"]]
            for p in d.get("datos_entrada", []):
                val = p["valor"]
                u   = p.get("unidad", "")
                vstr = (f"{val:.2f} {u}".strip()
                        if isinstance(val, (int, float))
                        else f"{val} {u}".strip())
                filas_de.append([
                    Paragraph(p["nombre"], _cell_concept),
                    Paragraph(vstr,        _cell_valor),
                ])
            t = Table(filas_de, colWidths=[10.5 * cm, 5.5 * cm])
            t.setStyle(_estilo_tabla_datos())
            story.append(t)
            story.append(Spacer(1, 0.2 * cm))

            # Pasos del cálculo de Mu
            story.append(Paragraph(
                "<b>Cálculo del momento último M_u</b>", H3))
            filas_mu = [_mini_header_fila()]
            for i, p in enumerate(d.get("pasos_mu", []), start=1):
                filas_mu.append(_fila_paso(i, p))
            t = Table(filas_mu, colWidths=col_widths_pasos)
            t.setStyle(_estilo_tabla_resultado())
            story.append(t)
            story.append(Spacer(1, 0.2 * cm))

            # Pasos de la cuantía
            story.append(Paragraph(
                "<b>Cálculo de la cuantía ρ y del acero A_s</b>", H3))
            filas_cu = [_mini_header_fila()]
            for i, p in enumerate(d.get("pasos_cuantia", []), start=1):
                filas_cu.append(_fila_paso(i, p))
            t = Table(filas_cu, colWidths=col_widths_pasos)
            t.setStyle(_estilo_tabla_resultado())
            story.append(t)
            story.append(PageBreak())

    # --- Subsección: tabla resumen (la original) — solo si hay diseño ---
    if not es_gravedad:
        story.append(Paragraph(
            f"<b>{num.h2()} Resumen del diseño estructural</b>", H2))
        header = ["Elemento", f"Mu ({U_M})", "As_req (mm²/m)",
                  f"Vu ({U_F})", f"φVc ({U_F})", "Estado"]
        filas = [header] + diseno_rows
        t = Table(filas,
                  colWidths=[2.4 * cm, 2.6 * cm, 3 * cm, 2.4 * cm, 2.4 * cm, 3.2 * cm])
        estilo = _estilo_tabla_resultado()
        for i, row in enumerate(diseno_rows, start=1):
            if "OK" in row[-1]:
                estilo.add("BACKGROUND", (-1, i), (-1, i), COLOR_OK_BG)
                estilo.add("TEXTCOLOR", (-1, i), (-1, i), COLOR_OK_TXT)
            else:
                estilo.add("BACKGROUND", (-1, i), (-1, i), COLOR_ERR_BG)
                estilo.add("TEXTCOLOR", (-1, i), (-1, i), COLOR_ERR_TXT)
            estilo.add("FONTNAME", (-1, i), (-1, i), "Helvetica-Bold")
        t.setStyle(estilo)
        story.append(t)
        story.append(Spacer(1, 0.6 * cm))

    # ============ RESULTADO GLOBAL ============
    story.append(Paragraph(
        f"{num.h1()} Resultado global del análisis", H1))
    est = resultado_global.get("estado", "—")
    estabilidad = resultado_global.get("estabilidad", "—")
    diseno_estr = resultado_global.get("diseno", "—")
    color_caja = COLOR_OK_BG if "APROBADO" in est else COLOR_ERR_BG
    color_txt = COLOR_OK_TXT if "APROBADO" in est else COLOR_ERR_TXT
    filas_res = [
        ["Verificaciones de estabilidad", estabilidad],
        ["Diseño estructural", diseno_estr],
        ["ESTADO FINAL", est],
    ]
    t = Table(filas_res, colWidths=[9 * cm, 7 * cm])
    t.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 10.5),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, COLOR_BORDE),
        ("ALIGN", (1, 0), (1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("BACKGROUND", (0, 2), (-1, 2), color_caja),
        ("TEXTCOLOR", (0, 2), (-1, 2), color_txt),
        ("FONTSIZE", (0, 2), (-1, 2), 12),
    ]))
    story.append(t)

    # ============ Firma ============
    story.append(Spacer(1, 2.5 * cm))
    firma = [
        ["_" * 40, "", "_" * 40],
        [datos.ingeniero or "Ingeniero Estructural", "", "Revisado por"],
    ]
    t = Table(firma, colWidths=[7 * cm, 2 * cm, 7 * cm])
    t.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("TEXTCOLOR", (0, 0), (-1, -1), COLOR_TEXTO),
    ]))
    story.append(t)

    doc.build(story)
    return buffer.getvalue()
