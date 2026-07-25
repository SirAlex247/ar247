"""Formato de unidades del reporte (MKS único).

El backend SIEMPRE calcula internamente en SI (kN, m, kPa, MPa, kN/m³).
Esta clase convierte valores SI a MKS, que es el único sistema soportado
por la aplicación:

    - Longitudes: m
    - Fuerzas: tonf (1 tonf = 9.80665 kN)
    - Fuerzas por metro lineal de muro: tonf/m
    - Momentos por metro lineal: tonf·m/m
    - Presiones y esfuerzos geotécnicos: tonf/m²
    - Pesos unitarios del suelo (γ_suelo): tonf/m³
    - Materiales (excepción explícita):
        * f'c en kgf/cm²
        * fy  en kgf/cm²
        * γ del concreto en ton/m³

Conversiones base (1 kgf = 9.80665 N exactamente):

    1 kN        = 0.101971621... tonf
    1 kPa       = 0.101971621... tonf/m²
    1 MPa       = 10.1971621...  kgf/cm²
    1 kN/m³     = 0.101971621... tonf/m³  (= ton/m³)
"""
from __future__ import annotations

# Factor base (kgf a N): 1 kgf = 9.80665 N. Inverso usado para todas las
# conversiones kN→tonf y kPa→tonf/m².
_G = 9.80665
_INV_G = 1.0 / _G            # ≈ 0.101971621


class FormatoUnidades:
    """Formatea valores SI en el sistema MKS.

    Cada método devuelve una tupla ``(valor_convertido, unidad_str)``.
    Los métodos ``fmt_*`` devuelven directamente el string formateado.

    El constructor acepta un argumento ``sistema`` (ignorado) por
    compatibilidad con código existente que aún lo pasa.
    """

    def __init__(self, sistema: str | None = None) -> None:
        # Argumento ignorado: la app es MKS único.
        self.sistema = "MKS"

    # ---------- magnitudes ----------
    def longitud(self, v_m: float) -> tuple[float, str]:
        return v_m, "m"

    def fuerza(self, v_kN: float) -> tuple[float, str]:
        return v_kN * _INV_G, "tonf"

    def fuerza_lineal(self, v_kN_por_m: float) -> tuple[float, str]:
        """Fuerza por unidad de longitud de muro."""
        return v_kN_por_m * _INV_G, "tonf/m"

    def momento_lineal(self, v_kNm_por_m: float) -> tuple[float, str]:
        """Momento por metro de muro."""
        return v_kNm_por_m * _INV_G, "tonf·m/m"

    def presion(self, v_kPa: float) -> tuple[float, str]:
        """Presiones y esfuerzos cortantes (NO materiales)."""
        # 1 kPa = 1 kN/m² = INV_G tonf/m²
        return v_kPa * _INV_G, "tonf/m²"

    def densidad_suelo(self, v_kN_m3: float) -> tuple[float, str]:
        """Peso unitario del suelo (γ_suelo)."""
        return v_kN_m3 * _INV_G, "tonf/m³"

    # ---------- propiedades de materiales (tratadas especial) ----------
    def fc(self, v_MPa: float) -> tuple[float, str]:
        """f'c del concreto en kgf/cm².
        1 MPa = 1 N/mm² = 100 N/cm² = 100/9.80665 kgf/cm² ≈ 10.197 kgf/cm².
        """
        return v_MPa * 100.0 * _INV_G, "kgf/cm²"

    def fy(self, v_MPa: float) -> tuple[float, str]:
        """fy del acero en kgf/cm²."""
        return v_MPa * 100.0 * _INV_G, "kgf/cm²"

    def gamma_concreto(self, v_kN_m3: float) -> tuple[float, str]:
        """γ del concreto en ton/m³ (densidad del material)."""
        return v_kN_m3 * _INV_G, "ton/m³"

    # ---------- formatos listos (strings) ----------
    def fmt_presion(self, v_kPa: float, dec: int = 2) -> str:
        v, u = self.presion(v_kPa)
        return f"{v:.{dec}f} {u}"

    def fmt_fuerza_lineal(self, v: float, dec: int = 2) -> str:
        v2, u = self.fuerza_lineal(v); return f"{v2:.{dec}f} {u}"

    def fmt_momento_lineal(self, v: float, dec: int = 2) -> str:
        v2, u = self.momento_lineal(v); return f"{v2:.{dec}f} {u}"

    def fmt_fc(self, v_MPa: float, dec: int = 2) -> str:
        v, u = self.fc(v_MPa); return f"{v:.{dec}f} {u}"

    def fmt_fy(self, v_MPa: float, dec: int = 0) -> str:
        v, u = self.fy(v_MPa); return f"{v:.{dec}f} {u}"

    def fmt_gamma_concreto(self, v: float, dec: int = 2) -> str:
        v2, u = self.gamma_concreto(v); return f"{v2:.{dec}f} {u}"

    def fmt_densidad_suelo(self, v: float, dec: int = 2) -> str:
        v2, u = self.densidad_suelo(v); return f"{v2:.{dec}f} {u}"

    # ---------- labels cortos para headers de tabla ----------
    @property
    def u_F_lineal(self) -> str:
        return "tonf/m"

    @property
    def u_M_lineal(self) -> str:
        return "tonf·m/m"

    @property
    def u_presion(self) -> str:
        return "tonf/m²"
