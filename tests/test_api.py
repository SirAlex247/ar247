"""Pruebas de la capa HTTP (Flask) usando el test_client — sin levantar servidor.

Verifican el contrato de los endpoints y el manejo de errores centralizado:
mensajes amables ante datos faltantes y SIN fuga de traceback en modo normal.
"""
try:
    import app as _appmod
except ModuleNotFoundError:
    import os, sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "python"))
    import app as _appmod

try:
    from tests.fixtures import MURO_VOLADIZO, ZAPATA
except ModuleNotFoundError:
    from fixtures import MURO_VOLADIZO, ZAPATA

_client = _appmod.app.test_client()


def test_health_responde_ok():
    r = _client.get("/api/health").get_json()
    assert r["ok"] is True and r["service"] == "ARGeoSt backend"


def test_analizar_ok_devuelve_resultado_completo():
    r = _client.post("/api/analizar", json=MURO_VOLADIZO).get_json()
    assert r["ok"] is True
    assert "verificaciones_raw" in r and "diseno_raw" in r


def test_analizar_falta_dato_error_amable_sin_traceback():
    # Payload incompleto → debe responder error de validación legible, no crash.
    r = _client.post("/api/analizar", json={"tipo_muro": "voladizo"}).get_json()
    assert r["ok"] is False
    assert r.get("validacion") is True
    assert "trace" not in r                       # sin fuga de traceback
    assert "requerido" in r["error"].lower() or "inválid" in r["error"].lower()


def test_zapata_endpoint_ok():
    r = _client.post("/api/zapata", json=ZAPATA).get_json()
    assert r["ok"] is True and "geometria" in r


def test_fa_fv_endpoint():
    r = _client.post("/api/Fa_Fv", json={"Aa": 0.15, "Av": 0.20, "tipo": "D"}).get_json()
    assert r["ok"] is True and r["Fa"] > 0 and r["Fv"] > 0
