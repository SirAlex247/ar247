"""
Diseño de MUROS DE TIERRA ARMADA / MSE (Mechanically Stabilized Earth) por el
método simplificado de la FHWA (NHI-10-024) / AASHTO.

Se verifican dos familias de estados límite:

1. **Estabilidad interna** (capa a capa de refuerzo):
   - Coeficiente de empuje lateral en la masa reforzada ``Kr`` (relación Kr/Ka
     que depende de si el refuerzo es inextensible —metálico— o extensible
     —geosintético—).
   - Esfuerzo vertical ``σv = γr·z + q`` y horizontal ``σh = Kr·σv``.
   - Tensión máxima por capa ``Tmax = σh·Sv``.
   - **Rotura (tensión):** ``Ta ≥ Tmax``  →  ``FS_rotura = Ta/Tmax``.
   - **Arrancamiento (pullout):** ``Pr = F*·α·σv·Le·C·Rc``, con la longitud en
     la zona resistente ``Le = L − La`` (``La`` = distancia a la superficie de
     falla). ``FS_pullout = Pr/Tmax ≥ 1.5``.

2. **Estabilidad externa** (el bloque reforzado L×H se trata como un muro de
   gravedad): deslizamiento, volcamiento, excentricidad y capacidad portante,
   con el empuje activo del relleno retenido detrás del bloque.

Convención: z se mide desde la corona hacia abajo (0 arriba, H en la base).
Unidades SI internas (kN, m, kPa, kN/m³).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field


G_W = 9.81   # peso unitario del agua (kN/m³), reservado para futuras extensiones


def _ka_rankine(phi_grados: float) -> float:
    p = math.radians(phi_grados)
    return math.tan(math.pi / 4 - p / 2) ** 2


def _factores_capacidad(phi_grados: float) -> tuple[float, float, float]:
    """Factores de capacidad portante (Vesic)."""
    phi = math.radians(phi_grados)
    if phi_grados <= 0:
        return 5.14, 1.0, 0.0
    Nq = math.exp(math.pi * math.tan(phi)) * math.tan(math.pi / 4 + phi / 2) ** 2
    Nc = (Nq - 1.0) / math.tan(phi)
    Ng = 2.0 * (Nq + 1.0) * math.tan(phi)
    return Nc, Nq, Ng


@dataclass
class CapaRefuerzo:
    """Resultados de estabilidad interna de una capa de refuerzo."""
    i: int
    z: float               # profundidad desde la corona (m)
    sigma_v: float         # esfuerzo vertical (kPa)
    Kr: float
    sigma_h: float         # esfuerzo horizontal (kPa)
    Sv: float              # espaciamiento tributario (m)
    Tmax: float            # tensión máxima (kN/m)
    La: float              # long. en zona activa (m)
    Le: float              # long. en zona resistente (m)
    Ta: float              # resistencia admisible del refuerzo (kN/m)
    Pr: float              # resistencia al arrancamiento (kN/m)
    FS_rotura: float
    FS_pullout: float
    cumple_rotura: bool
    cumple_pullout: bool


@dataclass
class ResultadoMSE:
    H: float
    L: float
    Sv: float
    n_capas: int
    tipo_refuerzo: str
    capas: list[CapaRefuerzo] = field(default_factory=list)
    externa: dict = field(default_factory=dict)
    resumen: dict = field(default_factory=dict)
    parametros: dict = field(default_factory=dict)
    avisos: list[str] = field(default_factory=list)

    @property
    def cumple(self) -> bool:
        return self.resumen.get("cumple_global", False)


class DisenadorMSE:
    """Diseñador de un muro de tierra armada por el método simplificado."""

    def __init__(self, *,
                 H: float, L: float, Sv: float,
                 gamma_r: float, phi_r: float,
                 gamma_b: float, phi_b: float,
                 gamma_f: float, phi_f: float, c_f: float = 0.0,
                 sobrecarga: float = 0.0,
                 tipo_refuerzo: str = "geosintetico",
                 Ta: float = 30.0,
                 F_pullout: float | None = None,
                 alpha_scale: float | None = None,
                 Rc: float = 1.0,
                 FS_rotura_obj: float = 1.0,
                 FS_pullout_obj: float = 1.5,
                 FS_desliz_obj: float = 1.5,
                 FS_volc_obj: float = 2.0,
                 FS_cap_obj: float = 2.5) -> None:
        self.H = float(H)
        self.L = float(L)
        self.Sv = float(Sv)
        self.gamma_r, self.phi_r = float(gamma_r), float(phi_r)
        self.gamma_b, self.phi_b = float(gamma_b), float(phi_b)
        self.gamma_f, self.phi_f, self.c_f = float(gamma_f), float(phi_f), float(c_f)
        self.q = float(sobrecarga)
        self.tipo = tipo_refuerzo
        self.extensible = tipo_refuerzo != "metalico"
        self.Ta = float(Ta)
        self.Rc = float(Rc)
        # F* y α por defecto según tipo de refuerzo (FHWA).
        tanphi = math.tan(math.radians(self.phi_r))
        self.F = (F_pullout if F_pullout is not None
                  else (0.6667 * tanphi if self.extensible else tanphi))
        self.alpha = (alpha_scale if alpha_scale is not None
                      else (0.8 if self.extensible else 1.0))
        self.FS_rotura_obj = FS_rotura_obj
        self.FS_pullout_obj = FS_pullout_obj
        self.FS_desliz_obj = FS_desliz_obj
        self.FS_volc_obj = FS_volc_obj
        self.FS_cap_obj = FS_cap_obj

    # ------------------------------------------------------------------
    def _Kr(self, z: float) -> float:
        """Coeficiente de empuje lateral en la masa reforzada."""
        Ka = _ka_rankine(self.phi_r)
        if self.extensible:
            return Ka                     # geosintético: Kr/Ka = 1.0
        # Metálico (inextensible): Kr/Ka = 1.7 en la corona → 1.2 a 6 m; luego 1.2
        if z >= 6.0:
            ratio = 1.2
        else:
            ratio = 1.7 - (1.7 - 1.2) * (z / 6.0)
        return ratio * Ka

    def _La(self, z: float) -> float:
        """Distancia horizontal de la cara a la superficie de falla, a la
        profundidad z (m)."""
        H = self.H
        if self.extensible:
            # Superficie de Rankine (lineal desde la base).
            return (H - z) * math.tan(math.radians(45 - self.phi_r / 2))
        # Inextensible: superficie bilineal (FHWA). h = altura sobre la base.
        h = H - z
        if h >= H / 2.0:
            return 0.3 * H
        return 0.6 * h

    # ------------------------------------------------------------------
    def _estabilidad_interna(self) -> list[CapaRefuerzo]:
        n = max(1, round(self.H / self.Sv))
        Sv = self.H / n                   # espaciamiento uniforme real
        capas: list[CapaRefuerzo] = []
        for i in range(1, n + 1):
            z = (i - 0.5) * Sv            # centro de la franja tributaria
            sigma_v = self.gamma_r * z + self.q
            Kr = self._Kr(z)
            sigma_h = Kr * sigma_v
            Tmax = sigma_h * Sv
            La = self._La(z)
            Le = max(0.0, self.L - La)
            # Arrancamiento: Pr = F*·α·σv·Le·C·Rc (C=2 → dos caras).
            Pr = self.F * self.alpha * sigma_v * Le * 2.0 * self.Rc
            FS_rot = (self.Ta / Tmax) if Tmax > 1e-9 else 99.0
            FS_po = (Pr / Tmax) if Tmax > 1e-9 else 99.0
            capas.append(CapaRefuerzo(
                i=i, z=z, sigma_v=sigma_v, Kr=Kr, sigma_h=sigma_h, Sv=Sv,
                Tmax=Tmax, La=La, Le=Le, Ta=self.Ta, Pr=Pr,
                FS_rotura=FS_rot, FS_pullout=FS_po,
                cumple_rotura=FS_rot >= self.FS_rotura_obj,
                cumple_pullout=FS_po >= self.FS_pullout_obj))
        return capas

    # ------------------------------------------------------------------
    def _estabilidad_externa(self) -> dict:
        H, L = self.H, self.L
        Ka_b = _ka_rankine(self.phi_b)
        # Empuje activo del relleno retenido detrás del bloque.
        Pa_tierra = 0.5 * Ka_b * self.gamma_b * H ** 2       # kN/m
        Pa_sc = Ka_b * self.q * H                            # kN/m
        Pa = Pa_tierra + Pa_sc
        # Peso del bloque reforzado (+ sobrecarga encima).
        W_suelo = self.gamma_r * L * H
        W_sc = self.q * L
        W = W_suelo + W_sc
        # Deslizamiento en la base (fricción del suelo de cimentación).
        base_tan = math.tan(math.radians(min(self.phi_r, self.phi_f)))
        F_res = W * base_tan + self.c_f * L
        FS_desliz = F_res / Pa if Pa > 1e-9 else 99.0
        # Volcamiento respecto al pie.
        Mo = Pa_tierra * (H / 3.0) + Pa_sc * (H / 2.0)
        Mr = W_suelo * (L / 2.0) + W_sc * (L / 2.0)
        FS_volc = Mr / Mo if Mo > 1e-9 else 99.0
        # Excentricidad y capacidad portante (Meyerhof, ancho efectivo).
        e = (Mo) / W if W > 1e-9 else 0.0
        e = max(0.0, L / 2.0 - (Mr - Mo) / W) if W > 1e-9 else 0.0
        e_max = L / 6.0
        L_ef = L - 2.0 * e
        q_ref = W / L_ef if L_ef > 1e-6 else 9.9e9
        Nc, Nq, Ng = _factores_capacidad(self.phi_f)
        q_ult = self.c_f * Nc + 0.5 * self.gamma_f * L_ef * Ng
        FS_cap = q_ult / q_ref if q_ref > 1e-9 else 99.0
        return {
            "Ka_retenido": Ka_b,
            "Pa_kN": Pa, "Pa_tierra_kN": Pa_tierra, "Pa_sobrecarga_kN": Pa_sc,
            "W_kN": W,
            "FS_deslizamiento": FS_desliz, "FS_volcamiento": FS_volc,
            "e_m": e, "e_max_m": e_max, "L_efectivo_m": L_ef,
            "q_referencia_kPa": q_ref, "q_ultimo_kPa": q_ult, "FS_capacidad": FS_cap,
            "cumple_deslizamiento": FS_desliz >= self.FS_desliz_obj,
            "cumple_volcamiento": FS_volc >= self.FS_volc_obj,
            "cumple_excentricidad": e <= e_max,
            "cumple_capacidad": FS_cap >= self.FS_cap_obj,
        }

    # ------------------------------------------------------------------
    def disenar(self) -> ResultadoMSE:
        capas = self._estabilidad_interna()
        externa = self._estabilidad_externa()
        avisos: list[str] = []

        # Longitud mínima recomendada (FHWA): L ≥ 0.7H y ≥ 2.4 m.
        if self.L < 0.7 * self.H - 1e-6:
            avisos.append(f"La longitud del refuerzo L={self.L:.2f} m es menor que "
                          f"0.7H={0.7*self.H:.2f} m (recomendación FHWA).")
        if self.L < 2.4:
            avisos.append("Se recomienda L ≥ 2.4 m.")
        # Longitud efectiva mínima en zona resistente (≈ 1 m).
        if capas and min(c.Le for c in capas) < 1.0:
            avisos.append("Alguna capa tiene Le < 1.0 m en la zona resistente; "
                          "aumenta L o revisa el arrancamiento en la corona.")

        min_fs_rot = min((c.FS_rotura for c in capas), default=99.0)
        min_fs_po = min((c.FS_pullout for c in capas), default=99.0)
        interna_ok = all(c.cumple_rotura and c.cumple_pullout for c in capas)
        externa_ok = (externa["cumple_deslizamiento"] and externa["cumple_volcamiento"]
                      and externa["cumple_excentricidad"] and externa["cumple_capacidad"])
        resumen = {
            "FS_rotura_min": round(min_fs_rot, 3),
            "FS_pullout_min": round(min_fs_po, 3),
            "capa_critica_rotura": min(capas, key=lambda c: c.FS_rotura).i if capas else 0,
            "capa_critica_pullout": min(capas, key=lambda c: c.FS_pullout).i if capas else 0,
            "interna_ok": interna_ok,
            "externa_ok": externa_ok,
            "cumple_global": interna_ok and externa_ok,
        }
        parametros = {
            "gamma_r": self.gamma_r, "phi_r": self.phi_r,
            "gamma_b": self.gamma_b, "phi_b": self.phi_b,
            "gamma_f": self.gamma_f, "phi_f": self.phi_f, "c_f": self.c_f,
            "sobrecarga": self.q, "tipo_refuerzo": self.tipo,
            "Ta": self.Ta, "F_pullout": self.F, "alpha": self.alpha, "Rc": self.Rc,
            "Ka_reforzado": _ka_rankine(self.phi_r),
            "objetivos": {
                "rotura": self.FS_rotura_obj, "pullout": self.FS_pullout_obj,
                "deslizamiento": self.FS_desliz_obj, "volcamiento": self.FS_volc_obj,
                "capacidad": self.FS_cap_obj},
        }
        return ResultadoMSE(
            H=self.H, L=self.L, Sv=capas[0].Sv if capas else self.Sv,
            n_capas=len(capas), tipo_refuerzo=self.tipo,
            capas=capas, externa=externa, resumen=resumen,
            parametros=parametros, avisos=avisos)
