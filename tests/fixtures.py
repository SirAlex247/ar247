"""Payloads canónicos (en SI, tal como los envía el frontend) reutilizados por
las pruebas de caracterización. Mantener ESTOS valores estables: si cambian,
los valores congelados de las pruebas de caracterización dejan de tener sentido.
"""
from __future__ import annotations

# ── Muro voladizo: caso limpio que aprueba todas las verificaciones ──────
MURO_VOLADIZO = {
    "tipo_muro": "voladizo",
    "H_vastago": 6.0, "e_zapata": 0.7,
    "b_puntera": 0.9, "b_talon": 2.6,
    "b_corona": 0.3, "b_base_vast": 0.5,
    "D": 1.5, "H_relleno": 6.0,
    "relleno_gamma": 18.0, "relleno_phi": 34.0, "relleno_cohesion": 0.0,
    "ciment_gamma": 19.0, "ciment_phi": 20.0, "ciment_cohesion": 40.0,
    "concreto_fc": 21.0, "concreto_gamma": 24.0, "acero_fy": 420.0,
    "alpha": 10.0, "sobrecarga": 0.0, "metodo_empuje": "rankine",
}

# ── Muro de gravedad ─────────────────────────────────────────────────────
MURO_GRAVEDAD = {
    "tipo_muro": "gravedad",
    "H_muro": 5.0, "e_zapata": 0.7, "b_corona": 0.6,
    "a_frontal": 0.0, "a_posterior": 1.2,
    "b_puntera": 0.5, "b_talon": 0.5, "D": 1.0,
    "relleno_gamma": 18.0, "relleno_phi": 32.0, "relleno_cohesion": 0.0,
    "ciment_gamma": 19.0, "ciment_phi": 24.0, "ciment_cohesion": 30.0,
    "concreto_fc": 21.0, "concreto_gamma": 24.0, "acero_fy": 420.0,
    "alpha": 0.0, "sobrecarga": 0.0, "metodo_empuje": "coulomb",
}

# ── Pilote (concreto vaciado in situ, multiestrato) ──────────────────────
PILOTE = {
    "D": 0.5, "L": 12.0, "fc": 21.0, "fy": 420.0, "n_barras": 6,
    "P_servicio": 800.0, "FS": 3.0, "instalacion": "perforado",
    "estratos": [
        {"tipo": "arena", "espesor": 6.0, "gamma": 18.0, "phi": 30.0, "cu": 0.0},
        {"tipo": "arcilla", "espesor": 10.0, "gamma": 19.0, "phi": 0.0, "cu": 80.0},
    ],
    "nivel_freatico": 4.0,
}

# ── Zapata aislada ───────────────────────────────────────────────────────
ZAPATA = {
    "c1": 0.4, "c2": 0.4, "P_servicio": 600.0, "M_servicio": 0.0,
    "q_adm": 200.0, "fc": 21.0, "fy": 420.0, "Df": 1.5, "Pu": 840.0,
}

# ── Dado / cabezal sobre pilotes ─────────────────────────────────────────
DADO = {
    "n_pilotes": 4, "Dp": 0.45, "c1": 0.45, "c2": 0.45,
    "Pu": 2000.0, "Mux": 0.0, "Muy": 0.0,
    "s": 1.35, "e": 0.35, "h": 0.9,
    "fc": 21.0, "fy": 420.0, "capacidad_pilote": 700.0,
}
