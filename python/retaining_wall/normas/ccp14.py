"""Factores de carga y de resistencia de la CCP-14 (LRFD-AASHTO).

Fuente: Norma Colombiana de Diseño de Puentes CCP-14.
  - Sección 3  — Cargas y factores de carga (Tablas 3.4.1-1 y 3.4.1-2).
  - Sección 10 — Cimentaciones (Tabla 10.5.5.2.2-1, factores φ).
  - Sección 11 — Muros, estribos y pilas (Tabla 11.5.7-1; Art. 11.6.3, 11.6.5).

Este módulo NO calcula nada de un muro concreto: solo concentra los NÚMEROS de
la norma y las reglas para clasificar cada carga en su tipo AASHTO, para que los
módulos de cálculo (muros, zapatas, pilotes…) los reutilicen.

Convención de factores permanentes: cada entrada es ``(gamma_max, gamma_min)``
de la Tabla 3.4.1-2. Se usa el que produzca el efecto más desfavorable en cada
verificación (Art. 3.4.1).
"""
from __future__ import annotations

from ..core.cargas import Carga, CategoriaCarga, TipoCarga


# ===========================================================================
# Tipos de carga AASHTO relevantes para cimentaciones y muros
# ===========================================================================
DC = "DC"      # peso propio de componentes estructurales (concreto)
EV = "EV"      # presión vertical del peso propio del suelo de relleno
EH = "EH"      # empuje horizontal del suelo (activo)
EH_V = "EH_V"  # componente vertical del empuje de suelo (relleno inclinado)
ES = "ES"      # sobrecarga de suelo (permanente)
LS = "LS"      # sobrecarga viva (empuje lateral por carga viva)
EP = "EP"      # presión pasiva del suelo (resistencia, no carga)
EQ = "EQ"      # carga sísmica (incremento dinámico del empuje)


# ===========================================================================
# Tabla 3.4.1-2 — Factores para cargas permanentes γ_p  (máx, mín)
# ===========================================================================
GAMMA_P = {
    "DC": (1.25, 0.90),                 # Componentes y accesorios
    "DC_solo_resistencia_IV": (1.50, 0.90),
    "DW": (1.50, 0.65),                 # Superficie de rodadura e instalaciones
    "EH_activa": (1.50, 0.90),          # Presión horizontal de suelo — activa
    "EH_reposo": (1.35, 0.90),          # Presión horizontal de suelo — en reposo
    "EV_muro": (1.35, 1.00),            # Presión vertical — muros de contención y estribos
    "EV_estabilidad_global": (1.00, None),
    "ES": (1.50, 0.75),                 # Sobrecarga de suelo
}

# Tabla 3.4.1-1 — factor de la sobrecarga viva (LS) en Resistencia I = factor LL
GAMMA_LS_RESISTENCIA = 1.75


# ===========================================================================
# Factores de resistencia φ
# ===========================================================================
# Tabla 11.5.7-1 — muros de contención permanentes (gravedad / semigravedad)
PHI_CAPACIDAD_MURO_GS = 0.55       # capacidad de carga, muros gravedad/semigravedad
PHI_CAPACIDAD_MURO_MSE = 0.65      # muros de suelo mecánicamente estabilizado
PHI_FLEXION_ELEM_VERTICAL = 0.90   # capacidad a flexión de elementos verticales

# Tabla 10.5.5.2.2-1 — cimentaciones superficiales (zapatas)
PHI_CAPACIDAD = {
    "teorico_arcilla": 0.50,
    "teorico_arena_cpt": 0.50,
    "teorico_arena_spt": 0.45,
    "semiempirico_meyerhof": 0.45,     # Meyerhof (1957), todos los suelos
    "roca": 0.45,
    "prueba_placa": 0.55,
}
PHI_DESLIZAMIENTO = {
    "prefab_arena": 0.90,              # concreto prefabricado sobre arena
    "insitu_arena": 0.80,              # concreto fundido in situ sobre arena
    "insitu_arcilla": 0.85,            # concreto fundido in situ o prefab. sobre arcilla
    "suelo_sobre_suelo": 0.90,
}
PHI_PASIVO = 0.50                      # φ_ep — resistencia pasiva componente del deslizamiento

# Art. 11.5.8 — Estado límite de Evento Extremo (sísmico): φ = 1.0 salvo…
PHI_EVENTO_EXTREMO = 1.0
PHI_CAPACIDAD_MURO_GS_EE = 0.80        # capacidad de carga, muros gravedad/semigravedad, EE


# ===========================================================================
# Límites de excentricidad (ubicación de la resultante) — Art. 11.6.3.3 / 11.6.5.1
# ===========================================================================
def limite_excentricidad(B: float, *, apoyo_roca: bool = False,
                         gamma_EQ: float | None = None) -> float:
    """Excentricidad máxima admisible |e| según la CCP-14.

    Estático (Art. 11.6.3.3):
        - Suelo: resultante dentro del tercio medio → |e| ≤ B/3.
        - Roca:  resultante dentro de 9/10 medios   → |e| ≤ 0.45·B.

    Sísmico / Evento Extremo I (Art. 11.6.5.1), interpolando linealmente por
    ``gamma_EQ`` entre:
        - γ_EQ = 0.0 → dos tercios medios  → |e| ≤ B/3
        - γ_EQ = 1.0 → ocho décimos medios → |e| ≤ 0.4·B

    Args:
        B: ancho de la base (m).
        apoyo_roca: True si la cimentación se apoya en roca.
        gamma_EQ: si se da (caso sísmico), interpola el límite en suelo entre
            B/3 y 0.4·B. En roca el límite sísmico se mantiene en 0.45·B.
    """
    if apoyo_roca:
        return 0.45 * B
    if gamma_EQ is None:                       # estático, suelo
        return B / 3.0
    g = min(1.0, max(0.0, gamma_EQ))
    frac = (1.0 / 3.0) + (0.40 - 1.0 / 3.0) * g   # B/3 → 0.4B
    return frac * B


# ===========================================================================
# Clasificación de una ``Carga`` de la app en su tipo AASHTO
# ===========================================================================
def tipo_aashto(carga: Carga) -> str:
    """Mapea una ``Carga`` (nomenclatura NSR-10) a su tipo de carga AASHTO.

    - Peso propio vertical (categoría D): concreto → DC, suelo → EV.
    - Empuje activo horizontal (categoría H, sentido +1) → EH.
    - Componente vertical del empuje activo (categoría Hv) → EH_V.
    - Empuje por sobrecarga viva (categoría Lsc) → LS.
    - Empuje pasivo (categoría H, sentido −1) → EP (resistencia).
    - Incremento sísmico (categoría E) → EQ.
    """
    cat = carga.categoria
    if cat == CategoriaCarga.D:
        return DC if (carga.material == "concreto") else EV
    if cat == CategoriaCarga.Hv:
        return EH_V
    if cat == CategoriaCarga.Lsc:
        return LS
    if cat == CategoriaCarga.E:
        return EQ
    if cat == CategoriaCarga.H:
        return EP if carga.sentido < 0 else EH
    # F, W u otras no consideradas para estabilidad externa de muros
    return EH if carga.tipo == TipoCarga.HORIZONTAL else EV


# ===========================================================================
# Factores γ por caso de combinación (estado límite) para muros
# ===========================================================================
# Cada caso es un dict {tipo_aashto: factor}. El empuje pasivo (EP) nunca lleva
# factor de carga: es resistencia y se afecta con φ_ep en el chequeo.
#
# Resistencia I, dos subcasos (guía Art. 3.4.1 pág. 3-13 y figuras C11.5.6-1/2):
#   * capacidad portante: maximizar demanda vertical y de vuelco.
#   * deslizamiento/excentricidad: minimizar cargas estabilizadoras.
FACTORES_RESISTENCIA_I_CAPACIDAD = {
    DC: GAMMA_P["DC"][0],          # 1.25
    EV: GAMMA_P["EV_muro"][0],     # 1.35
    EH: GAMMA_P["EH_activa"][0],   # 1.50
    EH_V: GAMMA_P["EH_activa"][0], # 1.50 (la comp. vertical suma a ΣV)
    LS: GAMMA_LS_RESISTENCIA,      # 1.75
    EQ: 0.0,                       # estático
}
FACTORES_RESISTENCIA_I_DESLIZAMIENTO = {
    DC: GAMMA_P["DC"][1],          # 0.90 (minimiza peso estabilizador)
    EV: GAMMA_P["EV_muro"][1],     # 1.00
    EH: GAMMA_P["EH_activa"][0],   # 1.50 (maximiza empuje motriz)
    EH_V: GAMMA_P["EH_activa"][1], # 0.90 (la comp. vertical estabiliza → mín)
    LS: GAMMA_LS_RESISTENCIA,      # 1.75 (empuje motriz por sobrecarga)
    EQ: 0.0,
}
# Evento Extremo I (sísmico). γ_p ≈ 1.0 para permanentes (Fig. C11.5.6-4);
# EQ = 1.0 sobre toda la presión sísmica; la sobrecarga viva usa γ_EQ.
def factores_evento_extremo(gamma_EQ: float) -> dict:
    return {
        DC: 1.0,
        EV: 1.0,
        EH: 1.0,
        EH_V: 1.0,
        LS: max(0.0, gamma_EQ),
        EQ: 1.0,
    }


def phi_deslizamiento(cohesion: float) -> float:
    """φ_τ para deslizamiento de concreto fundido in situ (Tabla 10.5.5.2.2-1).

    Se elige por el tipo de suelo de cimentación: si la cohesión es apreciable
    se trata como arcilla (0.85); en caso contrario como arena (0.80).
    """
    return PHI_DESLIZAMIENTO["insitu_arcilla"] if cohesion > 5.0 \
        else PHI_DESLIZAMIENTO["insitu_arena"]
