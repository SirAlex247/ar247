"""Motor de combinaciones de carga NSR-10 (Título B).

Recibe los EFECTOS de carga por tipo sobre un elemento y entrega los efectos
combinados, listos para diseño. Cada efecto puede ser un escalar (se toma como
axial P) o un dict de componentes arbitrarios (p.ej. {"P":.., "Mx":.., "My":..,
"Vx":.., "Vy":..}); las combinaciones operan componente a componente.

Tipos de carga (claves admitidas en el dict de entrada):
    D   carga muerta
    L   carga viva
    Lr  carga viva de cubierta   (equivalente a "G" granizo ó "Le" empozamiento;
        se aceptan esas claves como alias y se suman)
    W   viento
    Ex  sismo en X      Ey  sismo en Y   (fuerzas sísmicas reducidas E = Fs/R)
    H   empuje lateral de suelo / presión de agua
    F   fluidos
    T   temperatura, retracción, flujo plástico, asentamientos diferenciales

Devuelve dos conjuntos:
  * RESISTENCIA (B.2.4.2): cargas mayoradas -> diseno estructural (concreto).
  * SERVICIO / ESFUERZOS ADMISIBLES (B.2.3.1): cargas nominales -> chequeos
    geotecnicos (presion de contacto vs q_adm, vuelco, deslizamiento).
y la ENVOLVENTE (valor max/min por componente y la combinacion que gobierna).

Considera: reversibilidad de signo de W y E; combinacion sismica ortogonal
100%/30% del Titulo A (opcional); 1.3W (B.2.4.2.3); 1.0E/1.4E (B.2.4.2.4);
H=0 en B.2.4-6/7 (B.2.4.2.5); y reduccion de L a 0.5 (B.2.4.2.2).

Fuente: NSR-10 Titulo B, secciones B.2.3.1 y B.2.4.2 (texto oficial).

ESTADO (2026-07): motor autonomo y probado (ver tests/test_combinaciones.py),
pero AUN NO CABLEADO en el pipeline de la app. El flujo de muros usa el conjunto
simplificado ``CombinacionesNSR10`` de ``combinaciones.py`` (solo D/H/L/Lsc/E
sobre el sistema de fuerzas del muro). Este modulo, mas completo (viento, sismo
ortogonal 100/30, envolventes), esta pensado para integrarse en el diseno
estructural de zapatas/dados/pilotes, donde las cargas llegan como efectos
P/Mx/My. Integrar o consolidar ambos es trabajo pendiente; no borrar sin decidir
cual es la fuente de verdad de combinaciones.
"""
from __future__ import annotations

LOADS = ("D", "L", "Lr", "W", "Ex", "Ey", "H", "F", "T")


def _vec(x):
    """Normaliza un efecto a dict de componentes. Escalar -> {'P': x}."""
    if x is None:
        return {}
    if isinstance(x, (int, float)):
        return {"P": float(x)}
    return {k: float(v) for k, v in x.items() if v is not None}


def _add(dst, vec, factor):
    for k, v in vec.items():
        dst[k] = dst.get(k, 0.0) + factor * v


def _casos_sismo(Ex, Ey, bidireccional):
    """(sufijo, vector_E) con ortogonalidad 100/30 y reversion de signo."""
    hay_x = any(abs(v) > 1e-12 for v in Ex.values())
    hay_y = any(abs(v) > 1e-12 for v in Ey.values())
    if not hay_x and not hay_y:
        return [("", {})]
    casos = []
    if bidireccional and hay_x and hay_y:
        sg = lambda s: "+" if s > 0 else "-"
        for sx in (1, -1):
            for sy in (1, -1):
                v = {}; _add(v, Ex, sx * 1.0); _add(v, Ey, sy * 0.3)
                casos.append((f"{sg(sx)}Ex{sg(sy)}0.3Ey", v))
                v = {}; _add(v, Ex, sx * 0.3); _add(v, Ey, sy * 1.0)
                casos.append((f"{sg(sx)}0.3Ex{sg(sy)}Ey", v))
    else:
        if hay_x:
            for sx in (1, -1):
                v = {}; _add(v, Ex, float(sx)); casos.append((("+" if sx > 0 else "-") + "Ex", v))
        if hay_y:
            for sy in (1, -1):
                v = {}; _add(v, Ey, float(sy)); casos.append((("+" if sy > 0 else "-") + "Ey", v))
    return casos


def _expandir(templates, efecto, etiqueta, signos_W, casos_E):
    out = []
    for nombre, terminos, lateral in templates:
        if lateral == "W":
            for wsuf, wsig in signos_W:
                out.append({"nombre": nombre, "etiqueta": etiqueta(terminos, wsuf=wsuf),
                            "caso": wsuf, "efectos": efecto(terminos, wsig=wsig)})
        elif lateral == "E":
            for esuf, evec in casos_E:
                out.append({"nombre": nombre, "etiqueta": etiqueta(terminos, esuf=esuf),
                            "caso": esuf, "efectos": efecto(terminos, evec=evec)})
        else:
            out.append({"nombre": nombre, "etiqueta": etiqueta(terminos),
                        "caso": "", "efectos": efecto(terminos)})
    return out


def _envolvente(combos):
    comps = set()
    for c in combos:
        comps.update(c["efectos"].keys())
    env = {}
    for comp in sorted(comps):
        mx = mn = None
        for c in combos:
            v = c["efectos"].get(comp, 0.0)
            ref = {"valor": round(v, 3), "combo": c["nombre"], "caso": c["caso"], "etiqueta": c["etiqueta"]}
            if mx is None or v > mx["valor"]:
                mx = ref
            if mn is None or v < mn["valor"]:
                mn = ref
        env[comp] = {"max": mx, "min": mn}
    return env


def combinar(cargas, *, bidireccional=True, reducir_L=False,
             w_sin_direccionalidad=False, e_servicio=False,
             h_neutraliza=False, incluir_servicio=True):
    """Combinaciones de carga NSR-10 sobre los efectos dados.

    cargas: dict {tipo: efecto}. Tipos: D, L, Lr (o G o Le), W, Ex, Ey, H, F, T.
    Devuelve dict con 'resistencia', 'servicio', sus envolventes y 'parametros'.
    """
    Lm = {k: _vec(cargas.get(k)) for k in LOADS}
    roof = {}
    for k in ("Lr", "G", "Le"):
        _add(roof, _vec(cargas.get(k)), 1.0)
    W = Lm["W"]
    casos_E = _casos_sismo(Lm["Ex"], Lm["Ey"], bidireccional)
    signos_W = ([("+W", 1.0), ("-W", -1.0)]
                if any(abs(v) > 1e-12 for v in W.values()) else [("", 0.0)])

    fW = 1.3 if w_sin_direccionalidad else 1.6
    fE = 1.4 if e_servicio else 1.0
    fL = 0.5 if reducir_L else 1.0
    fH67 = 0.0 if h_neutraliza else 1.6

    fuentes = {"D": Lm["D"], "L": Lm["L"], "Lr": roof, "W": W,
               "H": Lm["H"], "F": Lm["F"], "T": Lm["T"]}

    def efecto(terminos, evec=None, wsig=0.0):
        r = {}
        for coef, sym in terminos:
            if sym == "E":
                _add(r, evec or {}, coef)
            elif sym == "W":
                _add(r, W, coef * wsig)
            else:
                _add(r, fuentes[sym], coef)
        return {k: round(v, 4) for k, v in r.items()}

    def etiqueta(terminos, wsuf="", esuf=""):
        parts = []
        for coef, sym in terminos:
            if sym == "W":
                parts.append(f"{coef:g}W")
            elif sym == "E":
                parts.append(f"{coef:g}*E")
            else:
                parts.append(f"{coef:g}{sym}")
        s = " + ".join(parts)
        if esuf:
            s += f"  [{esuf}]"
        elif wsuf:
            s += f"  [{wsuf}]"
        return s

    # ---- RESISTENCIA (B.2.4.2) ----
    R = [
        ("B.2.4-1",  [(1.4, "D"), (1.4, "F")], None),
        ("B.2.4-2",  [(1.2, "D"), (1.2, "F"), (1.2, "T"), (1.6, "L"), (1.6, "H"), (0.5, "Lr")], None),
        ("B.2.4-3a", [(1.2, "D"), (1.6, "Lr"), (fL, "L")], None),
        ("B.2.4-3b", [(1.2, "D"), (1.6, "Lr"), (0.8, "W")], "W"),
        ("B.2.4-4",  [(1.2, "D"), (fW, "W"), (fL, "L"), (0.5, "Lr")], "W"),
        ("B.2.4-5",  [(1.2, "D"), (fE, "E"), (fL, "L")], "E"),
        ("B.2.4-6",  [(0.9, "D"), (fW, "W"), (fH67, "H")], "W"),
        ("B.2.4-7",  [(0.9, "D"), (fE, "E"), (fH67, "H")], "E"),
    ]
    resistencia = _expandir(R, efecto, etiqueta, signos_W, casos_E)

    servicio = []
    if incluir_servicio:
        fEs = 0.7  # B.2.3.2 - factor sismico de servicio
        S = [
            ("B.2.3-1",  [(1.0, "D"), (1.0, "F")], None),
            ("B.2.3-2",  [(1.0, "D"), (1.0, "H"), (1.0, "F"), (1.0, "L"), (1.0, "T")], None),
            ("B.2.3-3",  [(1.0, "D"), (1.0, "H"), (1.0, "F"), (1.0, "Lr")], None),
            ("B.2.3-4",  [(1.0, "D"), (1.0, "H"), (1.0, "F"), (0.75, "L"), (0.75, "T"), (0.75, "Lr")], None),
            ("B.2.3-5",  [(1.0, "D"), (1.0, "H"), (1.0, "F"), (1.0, "W")], "W"),
            ("B.2.3-6",  [(1.0, "D"), (1.0, "H"), (1.0, "F"), (fEs, "E")], "E"),
            ("B.2.3-7",  [(1.0, "D"), (1.0, "H"), (1.0, "F"), (0.75, "W"), (0.75, "L"), (0.75, "Lr")], "W"),
            ("B.2.3-8",  [(1.0, "D"), (1.0, "H"), (1.0, "F"), (round(0.75 * fEs, 4), "E"), (0.75, "L"), (0.75, "Lr")], "E"),
            ("B.2.3-9",  [(0.6, "D"), (1.0, "W"), (1.0, "H")], "W"),
            ("B.2.3-10", [(0.6, "D"), (fEs, "E"), (1.0, "H")], "E"),
        ]
        servicio = _expandir(S, efecto, etiqueta, signos_W, casos_E)

    return {
        "resistencia": resistencia,
        "servicio": servicio,
        "envolvente_resistencia": _envolvente(resistencia),
        "envolvente_servicio": _envolvente(servicio),
        "parametros": {
            "bidireccional": bidireccional, "reducir_L": reducir_L,
            "w_sin_direccionalidad": w_sin_direccionalidad, "e_servicio": e_servicio,
            "h_neutraliza": h_neutraliza, "factor_W": fW, "factor_E": fE,
            "factor_L": fL, "factor_H_B6B7": fH67, "factor_E_servicio": 0.7,
        },
    }


def valor_diseno(res, componente="P", conjunto="resistencia", extremo="max"):
    """Atajo: valor gobernante de un componente. extremo: 'max' | 'min' | 'abs'."""
    env = res["envolvente_resistencia"] if conjunto == "resistencia" else res["envolvente_servicio"]
    if componente not in env:
        return 0.0
    if extremo == "abs":
        return max(abs(env[componente]["max"]["valor"]), abs(env[componente]["min"]["valor"]))
    return env[componente][extremo]["valor"]


if __name__ == "__main__":
    demo = combinar({"D": 100, "L": 40, "Lr": 10, "W": 30, "Ex": 50, "Ey": 20, "H": 15})
    print("Combinaciones de resistencia (P):")
    for c in demo["resistencia"]:
        print(f"  {c['nombre']:9s} {c['etiqueta']:34s} P = {c['efectos'].get('P', 0):.1f}")
    e = demo["envolvente_resistencia"]["P"]
    print(f"\nEnvolvente P -> max {e['max']['valor']} ({e['max']['combo']} {e['max']['caso']}) | "
          f"min {e['min']['valor']} ({e['min']['combo']} {e['min']['caso']})")
