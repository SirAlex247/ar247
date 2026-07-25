"""Captura el 'fingerprint' numérico actual del motor para congelarlo en las
pruebas de caracterización. NO es una prueba; se corre una sola vez a mano.
"""
import os, sys, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "python"))
os.environ.setdefault("MPLBACKEND", "Agg")
import matplotlib; matplotlib.use("Agg")
import app
from fixtures import MURO_VOLADIZO, MURO_GRAVEDAD, PILOTE, ZAPATA, DADO

def r(x, n=3):
    return round(x, n) if isinstance(x, (int, float)) else x

print("### VOLADIZO ###")
v = app.ejecutar_analisis(MURO_VOLADIZO)
tot = v["totales"]; tm = v["totales_momentos"]; pr = v["presiones_raw"]
print("SV", r(tot["SV"],2), "SMR", r(tot["SMR"],2), "SMo", r(tot["SMo"],2))
print("FS_volc", r(tm["FS_volcamiento"],3))
print("q_puntera", r(pr["q_puntera_kPa"],2), "q_talon", r(pr["q_talon_kPa"],2))
print("e", r(pr["e_m"],4), "B_prima", r(pr["B_prima_m"],3))
for vv in v["verificaciones_raw"]:
    print("  VER", vv["nombre"][:28], r(vv["valor"],3), vv["estado"])
for d in v["diseno_raw"]:
    print("  DIS", d["nombre"], "Mu", r(d["Mu_kNm"],2), "As", r(d["As_mm2_por_m"],1), "Vu", r(d["Vu_kN"],2), d["estado"])
print("global", v["resultado_global"]["estado"])

print("\n### GRAVEDAD ###")
g = app.ejecutar_analisis(MURO_GRAVEDAD)
gtot = g["totales_momentos"]; gpr = g["presiones_raw"]
print("FS_volc", r(gtot["FS_volcamiento"],3))
print("q_puntera", r(gpr["q_puntera_kPa"],2), "q_talon", r(gpr["q_talon_kPa"],2))
for vv in g["verificaciones_raw"]:
    print("  VER", vv["nombre"][:28], r(vv["valor"],3), vv["estado"])
print("elu_len", len(g["combinaciones_elu"]), "els_len", len(g["combinaciones_els"]))
print("global", g["resultado_global"]["estado"])

print("\n### PILOTE ###")
p = app.construir_pilote_desde_datos(PILOTE)
print("keys", sorted(p.keys()))
print(json.dumps({k: (r(vv,2) if isinstance(vv,(int,float)) else "…") for k,vv in p.get("capacidad",{}).items()}, ensure_ascii=False)[:400])

print("\n### ZAPATA ###")
z = app.construir_zapata_desde_datos(ZAPATA)
print("keys", sorted(z.keys()))
print("geometria", json.dumps({k:r(vv,3) for k,vv in z.get("geometria",{}).items() if isinstance(vv,(int,float))}, ensure_ascii=False)[:400])

print("\n### DADO ###")
d = app.construir_dado_desde_datos(DADO)
print("keys", sorted(d.keys()))
print("cumple", d.get("cumple"))
print("geometria", json.dumps({k:r(vv,3) for k,vv in d.get("geometria",{}).items() if isinstance(vv,(int,float))}, ensure_ascii=False)[:400])
