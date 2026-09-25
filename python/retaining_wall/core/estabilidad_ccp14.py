"""Estabilidad externa de muros de contención por la CCP-14 (LRFD).

A diferencia de ``estabilidad.py`` (esfuerzos admisibles, FS sobre cargas sin
mayorar), aquí el diseño es por estados límite: los efectos de carga se mayoran
con los factores γ de la Tabla 3.4.1-1/2 y se comparan contra resistencias
afectadas por φ. No hay factor de seguridad global; cada verificación reporta la
**relación capacidad/demanda (CDR = R_R / efecto)**, que debe ser ≥ 1.0.

Verificaciones (Art. 11.5.3 / 11.6.3):
    1. Excentricidad — pérdida de contacto en la base. En suelo |e| ≤ B/3
       (tercio medio); reemplaza el chequeo de vuelco (C11.6.3.3).
    2. Deslizamiento (Art. 10.6.3.4): ΣH_may ≤ φ_τ·(ΣV_may·tanφ + c·B) + φ_ep·Pp.
    3. Capacidad portante (Art. 11.6.3.2): σ_v = ΣV_may/(B−2e) ≤ φ_b·q_n.

Casos de combinación:
    - Resistencia I — capacidad (maximiza demanda): DC 1.25, EV 1.35, EH 1.50, LS 1.75.
    - Resistencia I — deslizamiento/excentricidad (minimiza estabilizadoras):
      DC 0.90, EV 1.00, EH 1.50, EH_v 0.90, LS 1.75.
    - Evento Extremo I (si hay sismo): γ_p ≈ 1.0, EQ 1.0, φ = 1.0 (φ_b = 0.8).

Todas las magnitudes internas en SI (kN/m, kN·m/m, m, kPa).
"""
from __future__ import annotations

import math

from ..models.muro import MuroContencion
from ..normas import ccp14
from .cargas import SistemaCargas, TipoCarga
from .estabilidad import (
    AnalisisEstabilidad,
    EstadoVerificacion,
    ReporteEstabilidad,
    ResultadoVerificacion,
)
from .suelos import PropiedadesSuelo


def _estado(cumple: bool) -> EstadoVerificacion:
    return EstadoVerificacion.CUMPLE if cumple else EstadoVerificacion.NO_CUMPLE


class AnalisisEstabilidadCCP14:
    """Verificaciones de estabilidad externa de un muro según la CCP-14."""

    def __init__(
        self,
        muro: MuroContencion,
        sistema_cargas: SistemaCargas,
        *,
        apoyo_roca: bool = False,
        incluir_sismo: bool = False,
        gamma_EQ: float = 0.5,
        incluir_empuje_pasivo: bool = True,
    ) -> None:
        """
        Args:
            muro: muro a analizar.
            sistema_cargas: cargas características (sin mayorar); si contiene el
                incremento sísmico (categoría E), ``incluir_sismo`` debe ser True.
            apoyo_roca: True si la cimentación se apoya en roca (límite de
                excentricidad 0.45·B y φ_b de roca).
            incluir_sismo: evalúa además el estado de Evento Extremo I y reporta
                el caso gobernante en cada verificación.
            gamma_EQ: factor de carga viva en Evento Extremo I (Art. 3.4.1, a
                definir por proyecto; 0.5 es razonable — Regla de Turkstra).
            incluir_empuje_pasivo: considera Pp en la resistencia al deslizamiento.
        """
        self.muro = muro
        self.cargas = sistema_cargas
        self.apoyo_roca = apoyo_roca
        self.incluir_sismo = incluir_sismo
        self.gamma_EQ = gamma_EQ
        self.incluir_pp = incluir_empuje_pasivo
        # Se reutiliza el analizador ASD solo para las presiones de servicio
        # (distribución para el dibujo); los chequeos son LRFD.
        self._asd = AnalisisEstabilidad(muro, sistema_cargas)

    # ==================================================================
    # Mayoración de efectos para un caso de combinación
    # ==================================================================
    def _factorizar(self, factores: dict) -> dict:
        """Suma los efectos mayorados de un caso de combinación.

        Devuelve ΣV (vertical), ΣH_motriz (horizontal actuante), ΣM_C (momento
        neto respecto a la puntera C, positivo estabiliza) y la excentricidad e.
        El empuje pasivo (EP) se excluye de ΣV/ΣM (se usa solo en deslizamiento,
        Art. 11.6.3.5).
        """
        B = self.muro.B
        SV = 0.0
        SH = 0.0
        SM = 0.0
        for c in self.cargas.cargas:
            t = ccp14.tipo_aashto(c)
            if t == ccp14.EP:
                continue                     # resistencia pasiva → solo deslizamiento
            g = factores.get(t, 0.0)
            if g == 0.0:
                continue
            if c.tipo == TipoCarga.VERTICAL:
                SV += g * c.magnitud * c.sentido
                SM += g * c.momento_respecto_C()
            else:
                SH += g * c.magnitud * c.sentido      # motriz (sentido +1)
                SM += g * c.momento_respecto_C()      # momento volcador (negativo)
        e = B / 2.0 - (SM / SV if SV > 0 else 0.0)
        return {"SV": SV, "SH": SH, "SM": SM, "e": e}

    def _pasivo_nominal(self) -> float:
        return self.cargas.suma_horizontal_resistente() if self.incluir_pp else 0.0

    # ==================================================================
    # EXCENTRICIDAD (reemplaza vuelco)
    # ==================================================================
    def _eval_excentricidad(self, factores: dict, gamma_EQ_lim):
        B = self.muro.B
        r = self._factorizar(factores)
        e = r["e"]
        lim = ccp14.limite_excentricidad(B, apoyo_roca=self.apoyo_roca,
                                          gamma_EQ=gamma_EQ_lim)
        cdr = lim / abs(e) if abs(e) > 1e-9 else 999.0
        return {"e": e, "abs_e": abs(e), "limite": lim, "cdr": cdr,
                "cumple": abs(e) <= lim, "SV": r["SV"], "SH": r["SH"], "SM": r["SM"]}

    # ==================================================================
    # DESLIZAMIENTO
    # ==================================================================
    def _eval_deslizamiento(self, factores: dict, phi_tau: float, phi_ep: float):
        cim = self.muro.suelo_cimentacion
        B = self.muro.B
        r = self._factorizar(factores)
        SV, SH = r["SV"], r["SH"]
        tan_phi = math.tan(math.radians(cim.phi))
        friccion = SV * tan_phi
        adherencia = cim.cohesion * B
        Pp = self._pasivo_nominal()
        R_R = phi_tau * (friccion + adherencia) + phi_ep * Pp
        cdr = R_R / SH if SH > 0 else 999.0
        return {"SV": SV, "SH": SH, "friccion": friccion, "adherencia": adherencia,
                "Pp": Pp, "phi_tau": phi_tau, "phi_ep": phi_ep, "R_R": R_R,
                "cdr": cdr, "cumple": R_R >= SH, "tan_phi": tan_phi}

    # ==================================================================
    # CAPACIDAD PORTANTE
    # ==================================================================
    def _eval_capacidad(self, factores: dict, phi_b: float):
        cim = self.muro.suelo_cimentacion
        D = self.muro.geometria.D
        B = self.muro.B
        r = self._factorizar(factores)
        SV, SH, e = r["SV"], r["SH"], r["e"]
        B_ef = max(1e-6, B - 2.0 * abs(e))
        sigma_v = SV / B_ef if SV > 0 else 0.0          # Ec. 11.6.3.2-1 (uniforme)
        qn = PropiedadesSuelo.capacidad_carga_ultima(
            c=cim.cohesion, phi_grados=cim.phi, gamma=cim.gamma,
            D=D, B_efectivo=B_ef, Ph=SH, V=SV,
        )
        q_n = qn["qu"]
        q_R = phi_b * q_n
        cdr = q_R / sigma_v if sigma_v > 0 else 999.0
        return {"SV": SV, "SH": SH, "e": e, "B_ef": B_ef, "sigma_v": sigma_v,
                "q_n": q_n, "phi_b": phi_b, "q_R": q_R, "cdr": cdr,
                "cumple": q_R >= sigma_v, "factores_qn": qn}

    # ==================================================================
    # Selección del caso gobernante (menor CDR)
    # ==================================================================
    def _casos_estaticos(self):
        return {
            "capacidad": ccp14.FACTORES_RESISTENCIA_I_CAPACIDAD,
            "desliz": ccp14.FACTORES_RESISTENCIA_I_DESLIZAMIENTO,
        }

    def _phi_capacidad(self) -> float:
        return ccp14.PHI_CAPACIDAD["roca"] if self.apoyo_roca else ccp14.PHI_CAPACIDAD_MURO_GS

    # ------------------------------------------------------------------
    def verificar_excentricidad(self) -> ResultadoVerificacion:
        est = self._eval_excentricidad(
            ccp14.FACTORES_RESISTENCIA_I_DESLIZAMIENTO, gamma_EQ_lim=None)
        gobernante, caso = est, "Resistencia I (mín)"
        if self.incluir_sismo:
            ee = self._eval_excentricidad(
                ccp14.factores_evento_extremo(self.gamma_EQ), gamma_EQ_lim=self.gamma_EQ)
            if ee["abs_e"] / ee["limite"] > gobernante["abs_e"] / gobernante["limite"]:
                gobernante, caso = ee, "Evento Extremo I"
        return ResultadoVerificacion(
            verificacion="Excentricidad |e| ≤ e_lím (ubicación de la resultante)",
            valor_calculado=gobernante["abs_e"],
            valor_requerido=round(gobernante["limite"], 4),
            unidades="m",
            estado=_estado(gobernante["cumple"]),
            detalle={
                "e": gobernante["e"], "abs_e": gobernante["abs_e"],
                "limite": gobernante["limite"], "caso": caso,
                "SV_may": gobernante["SV"], "SM_may": gobernante["SM"],
                "referencia": ("CCP-14 Art. 11.6.3.3 — en suelo la resultante debe "
                               "caer en el tercio medio (|e| ≤ B/3); reemplaza la "
                               "verificación de vuelco (C11.6.3.3)."),
            },
        )

    def verificar_vuelco_como_cdr(self) -> ResultadoVerificacion:
        """Chequeo de vuelco expresado como CDR de ubicación de la resultante.

        La CCP-14 reemplaza la relación M_estab/M_vuelco por el límite de
        excentricidad; aquí se reporta CDR = e_lím/|e| (≥ 1.0) para conservar
        el campo 'volcamiento' del reporte.
        """
        est = self._eval_excentricidad(
            ccp14.FACTORES_RESISTENCIA_I_DESLIZAMIENTO, gamma_EQ_lim=None)
        caso = "Resistencia I (mín)"
        if self.incluir_sismo:
            ee = self._eval_excentricidad(
                ccp14.factores_evento_extremo(self.gamma_EQ), gamma_EQ_lim=self.gamma_EQ)
            if ee["cdr"] < est["cdr"]:
                est, caso = ee, "Evento Extremo I"
        return ResultadoVerificacion(
            verificacion="Estabilidad al vuelco (CCP-14: por excentricidad)",
            valor_calculado=est["cdr"],
            valor_requerido=1.0,
            unidades="-",
            estado=_estado(est["cumple"]),
            detalle={"tipo": "CDR", "e": est["e"], "limite": est["limite"],
                     "caso": caso,
                     "referencia": ("CCP-14 C11.6.3.3 — la ubicación de la resultante "
                                    "sustituye la relación de momentos de vuelco.")},
        )

    def verificar_deslizamiento(self) -> ResultadoVerificacion:
        phi_tau = ccp14.phi_deslizamiento(self.muro.suelo_cimentacion.cohesion)
        est = self._eval_deslizamiento(
            ccp14.FACTORES_RESISTENCIA_I_DESLIZAMIENTO, phi_tau, ccp14.PHI_PASIVO)
        caso = "Resistencia I (mín)"
        if self.incluir_sismo:
            ee = self._eval_deslizamiento(
                ccp14.factores_evento_extremo(self.gamma_EQ),
                ccp14.PHI_EVENTO_EXTREMO, ccp14.PHI_EVENTO_EXTREMO)
            if ee["cdr"] < est["cdr"]:
                est, caso = ee, "Evento Extremo I"
        return ResultadoVerificacion(
            verificacion="Deslizamiento CDR = R_R/ΣH ≥ 1.0",
            valor_calculado=est["cdr"],
            valor_requerido=1.0,
            unidades="-",
            estado=_estado(est["cumple"]),
            detalle={
                "SV_may": est["SV"], "SH_may": est["SH"], "R_R": est["R_R"],
                "friccion": est["friccion"], "adherencia": est["adherencia"],
                "Pp": est["Pp"], "phi_tau": est["phi_tau"], "phi_ep": est["phi_ep"],
                "caso": caso,
                "referencia": ("CCP-14 Art. 10.6.3.4 — R_R = φ_τ·(ΣV·tanφ + c·B) + "
                               "φ_ep·Pp; φ_τ y φ_ep de la Tabla 10.5.5.2.2-1."),
            },
        )

    def verificar_capacidad_carga(self) -> ResultadoVerificacion:
        phi_b = self._phi_capacidad()
        est = self._eval_capacidad(ccp14.FACTORES_RESISTENCIA_I_CAPACIDAD, phi_b)
        caso = "Resistencia I (máx)"
        if self.incluir_sismo:
            phi_b_ee = ccp14.PHI_CAPACIDAD_MURO_GS_EE
            ee = self._eval_capacidad(
                ccp14.factores_evento_extremo(self.gamma_EQ), phi_b_ee)
            if ee["cdr"] < est["cdr"]:
                est, caso = ee, "Evento Extremo I"
        return ResultadoVerificacion(
            verificacion="Capacidad portante CDR = q_R/σ_v ≥ 1.0",
            valor_calculado=est["cdr"],
            valor_requerido=1.0,
            unidades="-",
            estado=_estado(est["cumple"]),
            detalle={
                "sigma_v_kPa": est["sigma_v"], "q_n_kPa": est["q_n"],
                "q_R_kPa": est["q_R"], "phi_b": est["phi_b"],
                "B_ef": est["B_ef"], "e": est["e"], "SV_may": est["SV"], "caso": caso,
                "referencia": ("CCP-14 Art. 11.6.3.2 — σ_v = ΣV/(B−2e) ≤ φ_b·q_n; "
                               "φ_b = 0.55 (Tabla 11.5.7-1, muros gravedad/semigravedad)."),
            },
        )

    # ==================================================================
    # ANÁLISIS COMPLETO
    # ==================================================================
    def analisis_completo(self) -> ReporteEstabilidad:
        return ReporteEstabilidad(
            volcamiento=self.verificar_vuelco_como_cdr(),
            deslizamiento=self.verificar_deslizamiento(),
            capacidad_carga=self.verificar_capacidad_carga(),
            excentricidad=self.verificar_excentricidad(),
            presiones=self._asd.calcular_presiones(),   # servicio, para el dibujo
        )

    # ==================================================================
    # DESGLOSES PASO A PASO (mismo formato que estabilidad.py → PDF)
    # Aquí "FS" es la relación capacidad/demanda (CDR) y "FS_min" = 1.0.
    # ==================================================================
    def tabla_deslizamiento(self) -> dict:
        phi_tau = ccp14.phi_deslizamiento(self.muro.suelo_cimentacion.cohesion)
        est = self._eval_deslizamiento(
            ccp14.FACTORES_RESISTENCIA_I_DESLIZAMIENTO, phi_tau, ccp14.PHI_PASIVO)
        caso = "Resistencia I (mín)"
        if self.incluir_sismo:
            ee = self._eval_deslizamiento(
                ccp14.factores_evento_extremo(self.gamma_EQ),
                ccp14.PHI_EVENTO_EXTREMO, ccp14.PHI_EVENTO_EXTREMO)
            if ee["cdr"] < est["cdr"]:
                est, caso, phi_tau = ee, "Evento Extremo I", est["phi_tau"]
        cim = self.muro.suelo_cimentacion
        B = self.muro.B
        return {
            "norma": "CCP-14", "caso": caso,
            "parametros": [
                {"nombre": "φ (fricción del suelo de cimentación)", "valor": cim.phi, "unidad": "°"},
                {"nombre": "c' (cohesión)", "valor": cim.cohesion, "unidad": "kPa"},
                {"nombre": "B (ancho de la zapata)", "valor": B, "unidad": "m"},
                {"nombre": "φ_τ (factor de resistencia, deslizamiento)", "valor": est["phi_tau"], "unidad": "-"},
                {"nombre": "φ_ep (factor de resistencia, pasivo)", "valor": est["phi_ep"], "unidad": "-"},
                {"nombre": "ΣV mayorada", "valor": est["SV"], "unidad": "kN/m"},
            ],
            "fuerzas_resistentes": [
                {"nombre": "Fricción en la base (φ_τ·ΣV·tanφ)", "formula": "φ_τ·ΣV·tanφ",
                 "detalle": f"{est['phi_tau']:.2f}·{est['SV']:.1f}·{est['tan_phi']:.3f}",
                 "valor": est["phi_tau"] * est["friccion"]},
                {"nombre": "Adherencia (φ_τ·c·B)", "formula": "φ_τ·c·B",
                 "detalle": f"{est['phi_tau']:.2f}·{cim.cohesion:.1f}·{B:.2f}",
                 "valor": est["phi_tau"] * est["adherencia"]},
                {"nombre": "Empuje pasivo (φ_ep·Pp)", "formula": "φ_ep·Pp",
                 "detalle": f"{est['phi_ep']:.2f}·{est['Pp']:.1f}",
                 "valor": est["phi_ep"] * est["Pp"]},
            ],
            "fuerzas_actuantes": [
                {"nombre": "ΣH mayorada (empuje motriz)", "formula": "ΣH_may",
                 "detalle": "empuje activo·1.50 + sobrecarga·1.75 (+ sismo·1.0)",
                 "valor": est["SH"]},
            ],
            "totales": {"F_resistente": est["R_R"], "F_actuante": est["SH"],
                        "FS": est["cdr"], "FS_min": 1.0},
        }

    def tabla_capacidad_carga(self) -> dict:
        phi_b = self._phi_capacidad()
        est = self._eval_capacidad(ccp14.FACTORES_RESISTENCIA_I_CAPACIDAD, phi_b)
        caso = "Resistencia I (máx)"
        if self.incluir_sismo:
            ee = self._eval_capacidad(
                ccp14.factores_evento_extremo(self.gamma_EQ), ccp14.PHI_CAPACIDAD_MURO_GS_EE)
            if ee["cdr"] < est["cdr"]:
                est, caso = ee, "Evento Extremo I"
        qn = est["factores_qn"]
        return {
            "norma": "CCP-14", "caso": caso,
            "parametros": [
                {"nombre": "ΣV mayorada", "valor": est["SV"], "unidad": "kN/m"},
                {"nombre": "Excentricidad e", "valor": est["e"], "unidad": "m"},
                {"nombre": "B' = B − 2·|e| (ancho efectivo)", "valor": est["B_ef"], "unidad": "m"},
                {"nombre": "φ_b (factor de resistencia, capacidad)", "valor": est["phi_b"], "unidad": "-"},
            ],
            "factores_N": [
                {"nombre": "N_c", "valor": qn["Nc"]},
                {"nombre": "N_q", "valor": qn["Nq"]},
                {"nombre": "N_γ", "valor": qn["Ngamma"]},
            ],
            "terminos": [
                {"nombre": "σ_v = ΣV/(B−2e) (demanda mayorada)", "formula": "ΣV/(B−2e)",
                 "detalle": f"{est['SV']:.1f}/{est['B_ef']:.2f}", "valor": est["sigma_v"]},
                {"nombre": "q_n (capacidad nominal)", "formula": "Meyerhof/Vesic",
                 "detalle": "c·Nc·… + q·Nq·… + ½γB'Nγ…", "valor": est["q_n"]},
                {"nombre": "q_R = φ_b·q_n (capacidad mayorada)", "formula": "φ_b·q_n",
                 "detalle": f"{est['phi_b']:.2f}·{est['q_n']:.1f}", "valor": est["q_R"]},
            ],
            "presiones": {"sigma_v": est["sigma_v"], "q_n": est["q_n"], "q_R": est["q_R"],
                          "B_prima": est["B_ef"], "e": est["e"], "SV": est["SV"]},
            "totales": {"qu": est["q_R"], "q_max": est["sigma_v"],
                        "FS": est["cdr"], "FS_min": 1.0},
        }

    def tabla_excentricidad(self) -> dict:
        est = self._eval_excentricidad(
            ccp14.FACTORES_RESISTENCIA_I_DESLIZAMIENTO, gamma_EQ_lim=None)
        caso, gEQ = "Resistencia I (mín)", None
        if self.incluir_sismo:
            ee = self._eval_excentricidad(
                ccp14.factores_evento_extremo(self.gamma_EQ), gamma_EQ_lim=self.gamma_EQ)
            if ee["abs_e"] / ee["limite"] > est["abs_e"] / est["limite"]:
                est, caso, gEQ = ee, "Evento Extremo I", self.gamma_EQ
        B = self.muro.B
        estado = "CUMPLE" if est["cumple"] else "NO CUMPLE"
        return {
            "norma": "CCP-14", "caso": caso,
            "parametros": [
                {"nombre": "B (ancho total de la zapata)", "valor": B, "unidad": "m"},
                {"nombre": "ΣV mayorada", "valor": est["SV"], "unidad": "kN/m"},
                {"nombre": "ΣM mayorado respecto a C", "valor": est["SM"], "unidad": "kN·m/m"},
            ],
            "pasos": [
                {"nombre": "Posición de la resultante (desde la puntera)",
                 "formula": "x_R = ΣM_may / ΣV_may",
                 "detalle": f"{est['SM']:.1f} / {est['SV']:.1f}",
                 "valor": (B / 2.0 - est["e"]), "unidad": "m"},
                {"nombre": "Excentricidad (con signo)", "formula": "e = B/2 − x_R",
                 "detalle": f"{B/2:.3f} − x_R", "valor": est["e"], "unidad": "m"},
                {"nombre": "Excentricidad |e|", "formula": "|e|", "detalle": "",
                 "valor": est["abs_e"], "unidad": "m"},
                {"nombre": ("Límite (tercio medio B/3)" if gEQ is None
                            else "Límite sísmico (interpola B/3→0.4B)"),
                 "formula": "e_lím", "detalle": f"caso {caso}",
                 "valor": est["limite"], "unidad": "m"},
            ],
            "totales": {"CE": (B / 2.0 - est["e"]), "e": est["e"], "abs_e": est["abs_e"],
                        "limite": est["limite"], "estado": estado,
                        "dentro_nucleo": est["cumple"],
                        "lado": ("hacia la puntera" if est["e"] > 0 else "hacia el talón")},
        }

    # ==================================================================
    # COMBINACIONES LRFD (para la pestaña de combinaciones y el PDF)
    # ==================================================================
    def combinaciones_lrfd(self) -> list["_ComboLRFD"]:
        casos = [
            ("Resistencia I — capacidad (máx)", ccp14.FACTORES_RESISTENCIA_I_CAPACIDAD),
            ("Resistencia I — desliz./exc. (mín)", ccp14.FACTORES_RESISTENCIA_I_DESLIZAMIENTO),
        ]
        if self.incluir_sismo:
            casos.append(("Evento Extremo I (sismo)",
                          ccp14.factores_evento_extremo(self.gamma_EQ)))
        out = []
        for nombre, fac in casos:
            SV = SH = MR = Mo = 0.0
            for c in self.cargas.cargas:
                t = ccp14.tipo_aashto(c)
                if t == ccp14.EP:
                    continue
                g = fac.get(t, 0.0)
                if g == 0.0:
                    continue
                m = g * c.momento_respecto_C()
                if c.tipo == TipoCarga.VERTICAL:
                    SV += g * c.magnitud * c.sentido
                else:
                    SH += g * c.magnitud * c.sentido
                if m >= 0:
                    MR += m
                else:
                    Mo += -m
            out.append(_ComboLRFD(nombre, SV, SH, MR, Mo))
        return out


class _ComboCCP14Nombre:
    __slots__ = ("nombre",)

    def __init__(self, nombre: str) -> None:
        self.nombre = nombre


class _ComboLRFD:
    """Fila de combinación LRFD con la misma interfaz que las NSR-10
    (``.combinacion.nombre``, ``.V_total``, ``.H_total``,
    ``.M_estabilizador``, ``.M_volcador``) para reutilizar el ensamblado."""

    def __init__(self, nombre: str, V: float, H: float, MR: float, Mo: float) -> None:
        self.combinacion = _ComboCCP14Nombre(nombre)
        self.V_total = V
        self.H_total = H
        self.M_estabilizador = MR
        self.M_volcador = Mo
