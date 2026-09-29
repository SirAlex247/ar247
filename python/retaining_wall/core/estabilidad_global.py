"""
Estabilidad global (falla de talud profunda) de un muro de contención por el
MÉTODO DE LAS DOVELAS sobre superficies de falla circulares.

Se implementan dos métodos clásicos:

* **Fellenius / Ordinario de las dovelas** (no iterativo):

  .. math::
      FS = \\frac{\\sum \\left[c'_i\\,\\ell_i + (W_i\\cos\\alpha_i - u_i\\ell_i)\\tan\\phi'_i\\right]}
                 {\\sum W_i\\sin\\alpha_i}

* **Bishop simplificado** (iterativo, más preciso):

  .. math::
      FS = \\frac{\\sum \\dfrac{c'_i\\,b_i + (W_i - u_i b_i)\\tan\\phi'_i}{m_{\\alpha,i}}}
                 {\\sum W_i\\sin\\alpha_i},\\qquad
      m_{\\alpha,i} = \\cos\\alpha_i\\left(1 + \\frac{\\tan\\alpha_i\\tan\\phi'_i}{FS}\\right)

Se hace una búsqueda en malla del centro y radio del círculo crítico (el de
menor FS). El mismo modelo sirve para cualquier tipología (voladizo, gravedad,
contrafuertes, etc.), porque toma la geometría real del muro (concreto),
el relleno retenido y el suelo de cimentación, e integra columna a columna el
peso sobre la superficie de falla. Admite nivel freático (presión de poros y
peso saturado) y sobrecarga uniforme.

Convención de coordenadas (idéntica a ``dibujo``/``geometria``):
    - Origen en el borde exterior inferior de la puntera (punto C de Das).
    - x positivo hacia el talón (hacia el relleno).
    - y positivo hacia arriba; la base de la zapata está en y = 0.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from ..models.muro import MuroContencion


# =============================================================================
# Resultados
# =============================================================================
@dataclass
class CirculoFalla:
    """Un círculo de falla evaluado."""
    xc: float
    yc: float
    R: float
    FS: float
    n_dovelas: int
    x_entrada: float          # daylight aguas arriba (lado relleno)
    x_salida: float           # daylight aguas abajo (lado puntera/frente)
    metodo: str = "bishop"


@dataclass
class ResultadoEstabilidadGlobal:
    """Resultado del análisis de estabilidad global."""
    FS_min: float
    FS_requerido: float
    cumple: bool
    metodo: str
    circulo: CirculoFalla
    FS_fellenius: float
    FS_bishop: float
    dovelas: list[dict] = field(default_factory=list)
    incluye_agua: bool = False
    n_circulos_evaluados: int = 0
    parametros: dict = field(default_factory=dict)


# =============================================================================
# Análisis
# =============================================================================
class EstabilidadGlobalMuro:
    """Estabilidad global de un muro por el método de las dovelas.

    Args:
        muro:          El muro de contención (voladizo, gravedad, ...).
        FS_requerido:  Factor de seguridad mínimo (1.5 estático, 1.1 sísmico
                       según práctica habitual / EN 1997 - FHWA).
        incluir_agua:  Si True usa el nivel freático de ``muro.condiciones``.
        gamma_w:       Peso unitario del agua (kN/m³).
        gamma_concreto: Peso unitario del concreto (kN/m³); si None se toma
                       del material del muro.
    """

    def __init__(self, muro: MuroContencion, *,
                 FS_requerido: float = 1.5,
                 incluir_agua: bool = True,
                 gamma_w: float = 9.81,
                 gamma_concreto: float | None = None) -> None:
        self.muro = muro
        self.g = muro.geometria
        self.rel = muro.suelo_relleno
        self.cim = muro.suelo_cimentacion
        self.FS_req = FS_requerido
        self.gamma_w = gamma_w
        self.gamma_c = (gamma_concreto if gamma_concreto is not None
                        else muro.concreto.gamma)

        # Geometría de referencia
        self.B = self.g.B
        self.e = self.g.e_zapata
        self.H_total = self.g.H_total
        self.D = muro.geometria.D
        self.H_suelo = self.e + self.g.H_relleno_ef      # tope del relleno
        self.xfb = self.g.x_cara_frontal_base            # cara frontal (base)
        self.xfc = self.g.x_cara_frontal_corona          # cara frontal (corona)
        self.xbb = self.g.x_cara_posterior_base          # cara posterior (base)
        self.xbc = self.g.x_cara_posterior_corona        # cara posterior (corona)

        # Sobrecarga e inclinación del relleno
        cond = muro.condiciones
        self.q_sc = max(0.0, cond.sobrecarga)
        self.alpha = math.radians(cond.alpha or 0.0)
        self._tan_alpha = math.tan(self.alpha)

        # Nivel freático (medido desde la base de la zapata, y = 0)
        nf = getattr(cond, "nivel_freatico_H", None)
        self.incluir_agua = bool(incluir_agua and nf is not None and nf > 0)
        self.y_w = float(nf) if self.incluir_agua else None

    # ------------------------------------------------------------------
    # Perfil físico y materiales
    # ------------------------------------------------------------------
    def _top_fisico(self, x: float) -> float:
        """Elevación del tope físico (suelo o concreto) sobre la base (y=0)."""
        if x <= 0.0:
            return self.D
        if x >= self.B:
            return self.H_suelo + max(0.0, x - self.B) * self._tan_alpha
        if x < self.xfb:            # sobre la puntera (cobertura frontal)
            return self.D
        if x > self.xbb:            # sobre el talón (relleno retenido)
            return self.H_suelo
        return self.H_total         # sobre el vástago (concreto)

    def _stem_interval(self, x: float) -> tuple[float, float] | None:
        """Intervalo vertical (y_lo, y_hi) ocupado por el vástago en la
        abscisa x, o None si el vástago no cubre esa abscisa."""
        e, H = self.e, self.H_total
        lo = min(self.xfb, self.xfc)
        hi = max(self.xbb, self.xbc)
        if x < lo - 1e-9 or x > hi + 1e-9:
            return None
        n = 24
        ys = [e + (H - e) * k / n for k in range(n + 1)]
        dentro = []
        for y in ys:
            t = (y - e) / (H - e) if H > e else 0.0
            XL = self.xfb + (self.xfc - self.xfb) * t
            XR = self.xbb + (self.xbc - self.xbb) * t
            if XL - 1e-9 <= x <= XR + 1e-9:
                dentro.append(y)
        if not dentro:
            return None
        return (min(dentro), max(dentro))

    def _conc_intervalos(self, x: float) -> list[tuple[float, float]]:
        """Intervalos verticales ocupados por concreto en la abscisa x."""
        out: list[tuple[float, float]] = []
        if 0.0 <= x <= self.B:
            out.append((0.0, self.e))            # zapata
        si = self._stem_interval(x)
        if si is not None:
            out.append(si)
        # diente de cortante (llave), si existe
        if self.g.tiene_diente:
            x0 = self.g.x_diente_ef
            if x0 - 1e-9 <= x <= x0 + self.g.b_diente + 1e-9:
                out.append((-self.g.h_diente, 0.0))
        return out

    @staticmethod
    def _restar_intervalos(lo: float, hi: float,
                           huecos: list[tuple[float, float]]) -> list[tuple[float, float]]:
        """Devuelve [lo,hi] menos los huecos (para separar suelo de concreto)."""
        segs = [(lo, hi)]
        for (a, b) in huecos:
            nuevos = []
            for (s0, s1) in segs:
                if b <= s0 or a >= s1:      # sin traslape
                    nuevos.append((s0, s1))
                    continue
                if a > s0:
                    nuevos.append((s0, min(a, s1)))
                if b < s1:
                    nuevos.append((max(b, s0), s1))
            segs = [(s0, s1) for (s0, s1) in nuevos if s1 - s0 > 1e-6]
        return segs

    def _material(self, x: float, y: float) -> str:
        """'rel' (relleno) o 'cim' (cimentación/nativo) del suelo en (x,y)."""
        if y < 0.0:
            return "cim"
        if x <= self.xfb:            # cobertura frontal = suelo nativo
            return "cim"
        return "rel"                 # detrás del vástago = relleno colocado

    def _gamma_suelo(self, mat: str, y_mid: float) -> float:
        s = self.rel if mat == "rel" else self.cim
        if self.y_w is not None and y_mid < self.y_w:
            return s.gamma_saturado
        return s.gamma

    # ------------------------------------------------------------------
    # Peso de una dovela (por metro de ancho fuera del plano)
    # ------------------------------------------------------------------
    def _peso_dovela(self, x: float, y_b: float, b: float) -> float:
        """Peso de la columna en x, entre la superficie de falla y_b y el tope
        físico, integrando suelo (γ o γ_sat) y concreto. Incluye sobrecarga si
        el tope es relleno."""
        y_s = self._top_fisico(x)
        if y_s <= y_b:
            return 0.0
        conc = self._conc_intervalos(x)
        # concreto dentro de la columna
        W = 0.0
        for (a, c) in conc:
            a2, c2 = max(a, y_b), min(c, y_s)
            if c2 > a2:
                W += self.gamma_c * (c2 - a2)
        # suelo = columna menos concreto
        for (a, c) in self._restar_intervalos(y_b, y_s, conc):
            ym = 0.5 * (a + c)
            mat = self._material(x, ym)
            W += self._gamma_suelo(mat, ym) * (c - a)
        W *= b
        # sobrecarga uniforme sobre el relleno
        if self.q_sc > 0 and x >= self.xbb:
            W += self.q_sc * b
        return W

    def _material_base(self, x: float, y_b: float) -> str:
        if y_b < 0.0:
            return "cim"
        if x >= self.xbb:
            return "rel"
        return "cim"

    # ------------------------------------------------------------------
    # Análisis de un círculo
    # ------------------------------------------------------------------
    def _daylight(self, xc: float, yc: float, R: float,
                  n_scan: int = 260) -> tuple[float, float] | None:
        """Abscisas de entrada/salida del arco inferior del círculo con el
        tope físico. Devuelve (x_izq, x_der) o None si no corta en dos puntos."""
        x0, x1 = xc - R, xc + R
        prev_x = None
        prev_f = None
        roots: list[float] = []
        for k in range(n_scan + 1):
            x = x0 + (x1 - x0) * k / n_scan
            dx = x - xc
            rad = R * R - dx * dx
            if rad < 0:
                continue
            ya = yc - math.sqrt(rad)          # arco inferior
            f = ya - self._top_fisico(x)      # <0 dentro del suelo
            if prev_f is not None and prev_f == prev_f:
                if (f <= 0.0) != (prev_f <= 0.0):
                    # interpolación lineal del cruce
                    t = prev_f / (prev_f - f) if (prev_f - f) != 0 else 0.5
                    roots.append(prev_x + (x - prev_x) * t)
            prev_x, prev_f = x, f
        if len(roots) < 2:
            return None
        return (min(roots), max(roots))

    def analizar_circulo(self, xc: float, yc: float, R: float,
                         n: int = 34) -> dict | None:
        """Evalúa un círculo y devuelve FS por Fellenius y Bishop, o None si el
        círculo no es válido (no corta el terreno en dos puntos, no pasa bajo el
        muro, o no hay empuje motor)."""
        dl = self._daylight(xc, yc, R)
        if dl is None:
            return None
        x_ent, x_sal = dl
        if x_sal - x_ent < 0.5:
            return None
        # El arco debe pasar por debajo de la base de la zapata en algún punto
        # dentro del ancho del muro (falla global profunda, no superficial).
        y_low = yc - R
        if y_low >= min(self.D, self.H_suelo):
            return None

        b = (x_sal - x_ent) / n
        dovelas = []
        sum_driving = 0.0
        for i in range(n):
            xm = x_ent + (i + 0.5) * b
            dx = xm - xc
            rad = R * R - dx * dx
            if rad <= 0:
                return None
            y_b = yc - math.sqrt(rad)
            sin_a = dx / R
            cos_a = math.sqrt(max(1e-9, 1.0 - sin_a * sin_a))
            alpha = math.asin(max(-1.0, min(1.0, sin_a)))
            W = self._peso_dovela(xm, y_b, b)
            if W <= 0:
                continue
            mat = self._material_base(xm, y_b)
            s = self.rel if mat == "rel" else self.cim
            phi = math.radians(s.phi)
            c = s.cohesion
            ell = b / cos_a
            u = 0.0
            if self.y_w is not None and y_b < self.y_w:
                u = self.gamma_w * (self.y_w - y_b)
            dovelas.append({
                "x": xm, "y_b": y_b, "alpha": alpha, "b": b, "ell": ell,
                "W": W, "c": c, "tanphi": math.tan(phi), "u": u,
                "sin_a": sin_a, "cos_a": cos_a, "material": mat,
            })
            sum_driving += W * sin_a
        if not dovelas or sum_driving <= 1e-6:
            return None

        # Fellenius (ordinario)
        num_f = 0.0
        for d in dovelas:
            N_ef = d["W"] * d["cos_a"] - d["u"] * d["ell"]
            resist = d["c"] * d["ell"] + max(0.0, N_ef) * d["tanphi"]
            num_f += resist
        FS_fell = num_f / sum_driving

        # Bishop simplificado (iterativo)
        FS = max(0.4, FS_fell)
        for _ in range(60):
            num_b = 0.0
            for d in dovelas:
                m_a = d["cos_a"] * (1.0 + d["sin_a"] / d["cos_a"] * d["tanphi"] / FS)
                if abs(m_a) < 1e-6:
                    m_a = 1e-6
                term = d["c"] * d["b"] + max(0.0, d["W"] - d["u"] * d["b"]) * d["tanphi"]
                num_b += term / m_a
            FS_new = num_b / sum_driving
            if abs(FS_new - FS) < 1e-5:
                FS = FS_new
                break
            FS = FS_new
        FS_bishop = FS

        return {
            "xc": xc, "yc": yc, "R": R, "x_entrada": x_ent, "x_salida": x_sal,
            "n_dovelas": len(dovelas), "FS_fellenius": FS_fell,
            "FS_bishop": FS_bishop, "dovelas": dovelas,
        }

    # ------------------------------------------------------------------
    # Búsqueda del círculo crítico
    # ------------------------------------------------------------------
    def buscar_critico(self, metodo: str = "bishop") -> ResultadoEstabilidadGlobal:
        """Busca el círculo de menor FS mediante malla gruesa + refinamiento."""
        clave = "FS_bishop" if metodo == "bishop" else "FS_fellenius"
        Href = max(self.H_total, 1.0)

        def _barrer(xc_vals, yc_vals, prof_vals):
            mejor = None
            n_eval = 0
            for xc in xc_vals:
                for yc in yc_vals:
                    for prof in prof_vals:       # profundidad bajo la base
                        R = yc + prof            # y_low = yc - R = -prof
                        if R <= 0:
                            continue
                        r = self.analizar_circulo(xc, yc, R)
                        n_eval += 1
                        if r is None:
                            continue
                        fs = r[clave]
                        if fs <= 0:
                            continue
                        if mejor is None or fs < mejor[clave]:
                            mejor = r
            return mejor, n_eval

        # Malla gruesa: centros por encima y detrás del muro.
        xc0 = [self.B * f for f in (-0.2, 0.2, 0.5, 0.8, 1.1, 1.4, 1.8)]
        yc0 = [self.H_total + Href * f for f in (0.2, 0.5, 0.9, 1.3, 1.8)]
        prof0 = [Href * f for f in (0.15, 0.4, 0.7, 1.0, 1.4)]
        mejor, n1 = _barrer(xc0, yc0, prof0)
        n_total = n1

        # Refinamiento alrededor del mejor centro.
        if mejor is not None:
            dx = max(self.B * 0.25, 0.5)
            dy = max(Href * 0.25, 0.5)
            dp = max(Href * 0.25, 0.5)
            xc1 = [mejor["xc"] + dx * f for f in (-1.0, -0.5, 0.0, 0.5, 1.0)]
            yc1 = [mejor["yc"] + dy * f for f in (-1.0, -0.5, 0.0, 0.5, 1.0)]
            p_base = mejor["yc"] - mejor["R"]        # = -prof
            prof1 = [max(0.1, -p_base + dp * f) for f in (-1.0, -0.5, 0.0, 0.5, 1.0)]
            mejor2, n2 = _barrer(xc1, yc1, prof1)
            n_total += n2
            if mejor2 is not None and (mejor is None or mejor2[clave] < mejor[clave]):
                mejor = mejor2

        if mejor is None:
            # Sin círculo válido: devolver un resultado neutro (no gobierna).
            circ = CirculoFalla(0.0, self.H_total, self.H_total, 99.9, 0,
                                0.0, 0.0, metodo)
            return ResultadoEstabilidadGlobal(
                FS_min=99.9, FS_requerido=self.FS_req, cumple=True,
                metodo=metodo, circulo=circ, FS_fellenius=99.9, FS_bishop=99.9,
                dovelas=[], incluye_agua=self.incluir_agua,
                n_circulos_evaluados=n_total,
                parametros=self._parametros())

        FS_min = mejor[clave]
        circ = CirculoFalla(
            xc=mejor["xc"], yc=mejor["yc"], R=mejor["R"], FS=FS_min,
            n_dovelas=mejor["n_dovelas"], x_entrada=mejor["x_entrada"],
            x_salida=mejor["x_salida"], metodo=metodo)
        return ResultadoEstabilidadGlobal(
            FS_min=FS_min, FS_requerido=self.FS_req,
            cumple=FS_min >= self.FS_req, metodo=metodo, circulo=circ,
            FS_fellenius=mejor["FS_fellenius"], FS_bishop=mejor["FS_bishop"],
            dovelas=mejor["dovelas"], incluye_agua=self.incluir_agua,
            n_circulos_evaluados=n_total, parametros=self._parametros())

    def _parametros(self) -> dict:
        return {
            "B_m": self.B, "H_total_m": self.H_total, "D_m": self.D,
            "H_suelo_m": self.H_suelo,
            "relleno": {"gamma": self.rel.gamma, "phi": self.rel.phi,
                        "c": self.rel.cohesion},
            "cimentacion": {"gamma": self.cim.gamma, "phi": self.cim.phi,
                            "c": self.cim.cohesion},
            "sobrecarga_kPa": self.q_sc,
            "nivel_freatico_m": self.y_w,
            "gamma_concreto": self.gamma_c,
        }
