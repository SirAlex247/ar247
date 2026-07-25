"""Pruebas del motor de combinaciones NSR-10 (retaining_wall/core/combinaciones.py).

Congela valores verificados a mano. Correr con:  python -m pytest tests/ -q
(o directamente:  python tests/test_combinaciones.py)
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "python"))
from retaining_wall.core.combinaciones_nsr10 import combinar, valor_diseno  # noqa: E402

# Caso base usado en varias pruebas (solo axial P, en tonf)
BASE = {"D": 100, "L": 40, "Lr": 10, "W": 30, "Ex": 50, "Ey": 20, "H": 15}


def _p(combos, nombre, caso=""):
    """P de la combinación 'nombre' (y 'caso' si aplica)."""
    for c in combos:
        if c["nombre"] == nombre and (caso == "" or c["caso"] == caso):
            return c["efectos"].get("P", 0.0)
    raise KeyError(f"{nombre} {caso}")


def test_resistencia_basicas():
    r = combinar(BASE)["resistencia"]
    assert _p(r, "B.2.4-1") == 140.0
    assert _p(r, "B.2.4-2") == 213.0
    assert _p(r, "B.2.4-3a") == 176.0
    assert _p(r, "B.2.4-3b", "+W") == 160.0
    assert _p(r, "B.2.4-3b", "-W") == 112.0
    assert _p(r, "B.2.4-4", "+W") == 213.0
    assert _p(r, "B.2.4-6", "+W") == 162.0


def test_resistencia_sismo_ortogonal_100_30():
    r = combinar(BASE)["resistencia"]
    # B.2.4-5: 1.2D + 1.0E + 1.0L = 160 + E ; E(+Ex+0.3Ey)=56
    assert _p(r, "B.2.4-5", "+Ex+0.3Ey") == 216.0
    assert _p(r, "B.2.4-5", "-Ex-0.3Ey") == 104.0
    # B.2.4-7: 0.9D + 1.0E + 1.6H = 90 + 24 + E
    assert _p(r, "B.2.4-7", "+Ex+0.3Ey") == 170.0
    assert _p(r, "B.2.4-7", "-Ex-0.3Ey") == 58.0


def test_envolvente_resistencia():
    env = combinar(BASE)["envolvente_resistencia"]["P"]
    assert env["max"]["valor"] == 216.0 and env["max"]["combo"] == "B.2.4-5"
    assert env["min"]["valor"] == 58.0 and env["min"]["combo"] == "B.2.4-7"
    assert valor_diseno(combinar(BASE), "P", "resistencia", "max") == 216.0


def test_servicio_basicas_y_envolvente():
    res = combinar(BASE)
    s = res["servicio"]
    assert _p(s, "B.2.3-1") == 100.0
    assert _p(s, "B.2.3-2") == 155.0
    assert _p(s, "B.2.3-4") == 152.5
    assert _p(s, "B.2.3-7", "+W") == 175.0
    assert round(_p(s, "B.2.3-8", "+Ex+0.3Ey"), 1) == 181.9
    assert _p(s, "B.2.3-9", "-W") == 45.0
    assert round(_p(s, "B.2.3-10", "-Ex-0.3Ey"), 1) == 35.8
    env = res["envolvente_servicio"]["P"]
    assert round(env["max"]["valor"], 1) == 181.9 and env["max"]["combo"] == "B.2.3-8"
    assert round(env["min"]["valor"], 1) == 35.8 and env["min"]["combo"] == "B.2.3-10"


def test_opcion_viento_sin_direccionalidad_1_3W():
    r = combinar(BASE, w_sin_direccionalidad=True)["resistencia"]
    # B.2.4-4 +W: 1.2D + 1.3W + 1.0L + 0.5Lr = 120 + 39 + 40 + 5
    assert _p(r, "B.2.4-4", "+W") == 204.0


def test_opcion_sismo_servicio_1_4E():
    r = combinar(BASE, e_servicio=True)["resistencia"]
    # B.2.4-5 +Ex+0.3Ey: 160 + 1.4*56 = 160 + 78.4
    assert round(_p(r, "B.2.4-5", "+Ex+0.3Ey"), 1) == 238.4


def test_opcion_reducir_L():
    r = combinar(BASE, reducir_L=True)["resistencia"]
    # B.2.4-5 +Ex+0.3Ey: 1.2D + E + 0.5L = 120 + 56 + 20
    assert _p(r, "B.2.4-5", "+Ex+0.3Ey") == 196.0


def test_opcion_H_neutraliza():
    r = combinar(BASE, h_neutraliza=True)["resistencia"]
    # B.2.4-7 +Ex+0.3Ey: 0.9D + E + 0*H = 90 + 56
    assert _p(r, "B.2.4-7", "+Ex+0.3Ey") == 146.0


def test_sismo_unidireccional():
    r = combinar(BASE, bidireccional=False)["resistencia"]
    # solo +-Ex y +-Ey, sin 30%
    assert _p(r, "B.2.4-5", "+Ex") == 210.0   # 160 + 50
    assert _p(r, "B.2.4-5", "+Ey") == 180.0   # 160 + 20


def test_multicomponente_P_Mx_My():
    cargas = {
        "D": {"P": 100, "Mx": 10, "My": 5},
        "L": {"P": 40, "Mx": 8, "My": 2},
        "Ex": {"P": 0, "Mx": 60, "My": 0},
        "Ey": {"P": 0, "Mx": 0, "My": 45},
    }
    r = combinar(cargas)
    # B.2.4-5 +Ex+0.3Ey: Mx = 1.2*10 + 1.0*(60) + 0.3*0 + 1.0*8 = 12 + 60 + 8 = 80
    #                      My = 1.2*5  + 0.3*45 + 1.0*2 = 6 + 13.5 + 2 = 21.5
    mx = _p(r["resistencia"], "B.2.4-5", "+Ex+0.3Ey")  # esto es P
    # leer componentes directamente
    c = next(x for x in r["resistencia"] if x["nombre"] == "B.2.4-5" and x["caso"] == "+Ex+0.3Ey")
    assert c["efectos"]["Mx"] == 80.0
    assert c["efectos"]["My"] == 21.5
    # envolvente de Mx
    assert r["envolvente_resistencia"]["Mx"]["max"]["valor"] == 80.0


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    ok = 0
    for fn in fns:
        try:
            fn(); ok += 1; print(f"  PASS  {fn.__name__}")
        except AssertionError as e:
            print(f"  FALLA {fn.__name__}: {e}")
        except Exception as e:
            print(f"  ERROR {fn.__name__}: {e}")
    print(f"\n{ok}/{len(fns)} pruebas OK")
