"""
Diseño de MUROS ANCLADOS (anchored walls / tieback walls) por el método de las
PRESIONES APARENTES (Terzaghi-Peck / FHWA GEC-4, FHWA-IF-99-015).

El muro (pantalla continua, tablestaca o pilas-viga) se sostiene con una o
varias filas de anclajes al terreno. El procedimiento:

1. **Envolvente de presión aparente** según el tipo de suelo:
   - Arena: diagrama trapezoidal con ordenada máxima
     ``p = 1.3·γ·H²·Ka / (1.5H − 0.5·H1 − 0.5·Hn+1)``.
   - Arcilla rígida (Ns ≤ 4): ``p ≈ 0.3·γ·H`` (trapezoidal).
   - Arcilla blanda/media (Ns > 4): ``p = Ka·γ·H`` con
     ``Ka = 1 − 4·Su/(γH)``.
   Se añade la sobrecarga como componente uniforme ``Ka·q``.

2. **Cargas de anclaje** por el método del área tributaria: cada fila toma el
   área de la envolvente en su zona tributaria; la reacción de la base toma la
   porción inferior.

3. **Diseño de cada anclaje**: fuerza de diseño ``T = Th·sh/cosθ``, longitud de
   bulbo ``Lb = T·FS / (π·d·τ)`` y longitud libre mínima para superar la cuña
   de falla activa.

4. **Momento flector máximo aproximado** de la pantalla, para dimensionar la
   sección (viga-pila o tablestaca).

Convención: z se mide desde la corona hacia abajo (0 arriba, H en el fondo de
excavación). Unidades SI (kN, m, kPa, kN/m³, grados).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field


def _ka_rankine(phi_grados: float) -> float:
    return math.tan(math.radians(45 - phi_grados / 2.0)) ** 2


@dataclass
class Anclaje:
    """Resultados de una fila de anclajes."""
    i: int
    z: float               # profundidad de la fila (m)
    Th: float              # carga horizontal por metro de muro (kN/m)
    T_diseno: float        # fuerza de diseño por anclaje (kN)
    Lb: float              # longitud de bulbo (m)
    Lf: float              # longitud libre (m)
    L_total: float         # longitud total del anclaje (m)


@dataclass
class ResultadoMuroAnclado:
    H: float
    tipo_suelo: str
    n_anclajes: int
    p_max: float           # ordenada máxima de la envolvente (kPa)
    Ka: float
    anclajes: list[Anclaje] = field(default_factory=list)
    reaccion_base: float = 0.0     # kN/m
    momento_max: float = 0.0       # kN·m/m
    empuje_total: float = 0.0      # kN/m
    parametros: dict = field(default_factory=dict)
    avisos: list[str] = field(default_factory=list)
    resumen: dict = field(default_factory=dict)


class DisenadorMuroAnclado:
    """Diseñador de muros anclados por presiones aparentes."""

    def __init__(self, *,
                 H: float, gamma: float, phi: float,
                 z_anclajes: list[float] | None = None,
                 n_anclajes: int = 2, z_primero: float = 1.5, sv: float = 2.5,
                 inclinacion: float = 15.0, sh: float = 2.5,
                 sobrecarga: float = 0.0,
                 tipo_suelo: str = "arena", Su: float = 0.0,
                 tau_bond: float = 150.0, d_bulbo: float = 0.15,
                 FS_pullout: float = 2.0,
                 Lf_min: float = 4.5) -> None:
        self.H = float(H)
        self.gamma = float(gamma)
        self.phi = float(phi)
        self.q = float(sobrecarga)
        self.theta = math.radians(inclinacion)
        self.sh = float(sh)
        self.tipo = tipo_suelo
        self.Su = float(Su)
        self.tau = float(tau_bond)
        self.d_bulbo = float(d_bulbo)
        self.FS = float(FS_pullout)
        self.Lf_min = float(Lf_min)

        # Posiciones de los anclajes
        if z_anclajes:
            self.z = sorted(float(z) for z in z_anclajes if 0 < float(z) < self.H)
        else:
            self.z = [z_primero + i * sv for i in range(int(n_anclajes))
                      if z_primero + i * sv < self.H]
        if not self.z:
            self.z = [min(0.3 * self.H, 1.5)]
        self.n = len(self.z)

    # ------------------------------------------------------------------
    def _Ka(self) -> float:
        if self.tipo == "arcilla":
            Ns = self.gamma * self.H / self.Su if self.Su > 0 else 0.0
            if Ns > 4:                       # blanda/media
                return max(0.22, 1.0 - 4.0 / Ns)
            return 0.3                       # rígida (equivalente p≈0.3γH)
        return _ka_rankine(self.phi)         # arena

    def _p_max(self, Ka: float) -> float:
        """Ordenada máxima de la envolvente de presión aparente (kPa)."""
        H = self.H
        H1 = self.z[0]
        Hn1 = H - self.z[-1]
        if self.tipo == "arcilla":
            Ns = self.gamma * H / self.Su if self.Su > 0 else 0.0
            if Ns > 4:                       # blanda/media: p = Ka·γ·H
                p = Ka * self.gamma * H
            else:                            # rígida: p ≈ 0.3 γ H
                p = 0.3 * self.gamma * H
        else:                                # arena (trapezoidal FHWA)
            denom = 1.5 * H - 0.5 * H1 - 0.5 * Hn1
            p = 1.3 * self.gamma * H ** 2 * Ka / denom if denom > 0 else Ka * self.gamma * H
        # Componente por sobrecarga (uniforme, Ka·q).
        p += Ka * self.q
        return p

    def _envolvente(self, z: float, p: float) -> float:
        """Valor de la envolvente trapezoidal a la profundidad z (kPa)."""
        H = self.H
        H1 = self.z[0]
        z_last = self.z[-1]
        if z <= 0 or z >= H:
            return 0.0
        if z < H1:
            return p * z / H1                 # rampa superior
        if z <= z_last:
            return p                          # meseta
        # rampa inferior desde el último anclaje hasta la base
        return p * (H - z) / (H - z_last) if H > z_last else p

    def _integral(self, p: float, z0: float, z1: float, n: int = 200) -> tuple[float, float]:
        """Integra la envolvente entre z0 y z1; devuelve (área, z del centroide)."""
        if z1 <= z0:
            return 0.0, 0.5 * (z0 + z1)
        dz = (z1 - z0) / n
        A = 0.0
        Mz = 0.0
        for k in range(n):
            z = z0 + (k + 0.5) * dz
            s = self._envolvente(z, p)
            A += s * dz
            Mz += s * z * dz
        zc = Mz / A if A > 1e-12 else 0.5 * (z0 + z1)
        return A, zc

    # ------------------------------------------------------------------
    def disenar(self) -> ResultadoMuroAnclado:
        Ka = self._Ka()
        p = self._p_max(Ka)
        H = self.H
        z = self.z
        n = self.n
        avisos: list[str] = []

        # Zonas tributarias (método del área tributaria).
        fronteras = [0.0]
        for i in range(n - 1):
            fronteras.append(0.5 * (z[i] + z[i + 1]))
        frontera_base = 0.5 * (z[-1] + H)       # separa último anclaje / base
        fronteras.append(frontera_base)

        anclajes: list[Anclaje] = []
        for i in range(n):
            z0 = fronteras[i]
            z1 = fronteras[i + 1]
            Th, _ = self._integral(p, z0, z1)     # kN/m (carga horizontal)
            # Fuerza de diseño por anclaje (según inclinación y separación horiz.)
            T_dis = Th * self.sh / math.cos(self.theta)
            # Longitud de bulbo (arrancamiento del bulbo inyectado).
            cap_unit = math.pi * self.d_bulbo * self.tau     # kN/m de bulbo
            Lb = self.FS * T_dis / cap_unit if cap_unit > 0 else 0.0
            # Longitud libre mínima: superar la cuña activa (45+φ/2) + holgura.
            dist_cuna = (H - z[i]) * math.tan(math.radians(45 - self.phi / 2.0))
            Lf = max(self.Lf_min, dist_cuna / math.cos(self.theta) + 1.5)
            anclajes.append(Anclaje(
                i=i + 1, z=z[i], Th=Th, T_diseno=T_dis,
                Lb=Lb, Lf=Lf, L_total=Lb + Lf))

        # Reacción en la base (porción inferior de la envolvente).
        R_base, _ = self._integral(p, frontera_base, H)

        # Empuje total (área de la envolvente completa).
        empuje_total, _ = self._integral(p, 0.0, H, n=400)

        # Momento máximo aproximado de la pantalla (viga continua).
        spans = [z[0]] + [z[i] - z[i - 1] for i in range(1, n)] + [H - z[-1]]
        L_max = max(spans)
        M_max = p * L_max ** 2 / 10.0            # aproximación (wL²/10)

        # Avisos
        if any(a.Lf < self.Lf_min + 1e-6 and a.Lf == self.Lf_min for a in anclajes):
            avisos.append(f"Longitud libre limitada por el mínimo ({self.Lf_min:.1f} m).")
        if z[-1] > 0.85 * H:
            avisos.append("El último anclaje está muy cerca del fondo; revisa la "
                          "estabilidad del pie y el empotramiento de la pantalla.")
        for a in anclajes:
            if a.Lb > 12.0:
                avisos.append(f"Anclaje {a.i}: bulbo largo (Lb={a.Lb:.1f} m); "
                              "considera mayor τ_bond o diámetro.")

        parametros = {
            "gamma": self.gamma, "phi": self.phi, "sobrecarga": self.q,
            "tipo_suelo": self.tipo, "Su": self.Su,
            "inclinacion_grados": math.degrees(self.theta),
            "sh": self.sh, "tau_bond": self.tau, "d_bulbo": self.d_bulbo,
            "FS_pullout": self.FS, "Lf_min": self.Lf_min,
            "z_anclajes": list(z),
        }
        resumen = {
            "p_max_kPa": round(p, 2),
            "empuje_total_kN_m": round(empuje_total, 2),
            "T_diseno_max_kN": round(max((a.T_diseno for a in anclajes), default=0.0), 1),
            "Lb_max_m": round(max((a.Lb for a in anclajes), default=0.0), 2),
            "L_total_max_m": round(max((a.L_total for a in anclajes), default=0.0), 2),
            "momento_max_kNm_m": round(M_max, 1),
        }
        return ResultadoMuroAnclado(
            H=H, tipo_suelo=self.tipo, n_anclajes=n, p_max=p, Ka=Ka,
            anclajes=anclajes, reaccion_base=R_base, momento_max=M_max,
            empuje_total=empuje_total, parametros=parametros,
            avisos=avisos, resumen=resumen)
