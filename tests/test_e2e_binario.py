"""Prueba E2E del binario congelado (PyInstaller) — la cadena que empaqueta
Electron: ejecutable autocontenido → Flask → cálculos NSR-10 → matplotlib →
reportlab PDF, SIN Python del sistema.

Se **salta** automáticamente si el binario no está construido (``python-backend/
argeost-backend[.exe]``). Para construirlo:  ``python python/build_backend.py``
y copiar ``python/dist/argeost-backend`` a ``python-backend/`` (o correr
``build_backend.bat`` en Windows).

Correr:  python tests/run_all.py   (o  pytest tests/test_e2e_binario.py)
"""
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request

_RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


class _Saltar(Exception):
    """Señal de 'prueba saltada' entendida por run_all.py."""


try:
    import pytest
    def _skip(msg): pytest.skip(msg)
except ModuleNotFoundError:
    def _skip(msg): raise _Saltar(msg)


def _ruta_binario():
    exe = "argeost-backend.exe" if sys.platform == "win32" else "argeost-backend"
    return os.path.join(_RAIZ, "python-backend", exe)


def _puerto_libre():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _http_json(url, payload):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.status, r.read()


class _Backend:
    """Arranca el binario, espera a que responda /api/health y lo apaga."""
    def __init__(self, exe):
        self.exe = exe
        self.proc = None
        self.port = _puerto_libre()

    def __enter__(self):
        self.proc = subprocess.Popen(
            [self.exe, "--host", "127.0.0.1", "--port", str(self.port)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        base = f"http://127.0.0.1:{self.port}"
        t0 = time.time()
        while time.time() - t0 < 40:
            if self.proc.poll() is not None:
                raise RuntimeError("el binario terminó antes de responder")
            try:
                with urllib.request.urlopen(base + "/api/health", timeout=2) as r:
                    if json.loads(r.read()).get("ok"):
                        return base
            except Exception:
                time.sleep(0.5)
        raise RuntimeError("timeout esperando /api/health del binario")

    def __exit__(self, *exc):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except Exception:
                self.proc.kill()


_PAYLOAD = {
    "tipo_muro": "voladizo", "H_vastago": 6.0, "e_zapata": 0.7,
    "b_puntera": 0.9, "b_talon": 2.6, "b_corona": 0.3, "b_base_vast": 0.5,
    "D": 1.5, "H_relleno": 6.0, "relleno_gamma": 18.0, "relleno_phi": 34.0,
    "relleno_cohesion": 0.0, "ciment_gamma": 19.0, "ciment_phi": 20.0,
    "ciment_cohesion": 40.0, "concreto_fc": 21.0, "concreto_gamma": 24.0,
    "acero_fy": 420.0, "alpha": 10.0, "sobrecarga": 0.0,
    "metodo_empuje": "rankine", "proyecto": "E2E",
}


def test_e2e_binario_analisis_y_pdf():
    exe = _ruta_binario()
    if not os.path.exists(exe):
        _skip(f"Binario no construido ({exe}). Correr build_backend primero.")

    with _Backend(exe) as base:
        # 1) Análisis completo (incluye figuras matplotlib embebidas)
        status, body = _http_json(base + "/api/analizar", _PAYLOAD)
        assert status == 200
        r = json.loads(body)
        assert r["ok"] is True
        assert abs(r["totales_momentos"]["FS_volcamiento"] - 3.415) < 0.01
        assert r["imagen_muro_raw"]                     # matplotlib rindió el PNG

        # 2) PDF (valida reportlab + fuentes empaquetadas)
        status, pdf = _http_json(base + "/api/pdf", _PAYLOAD)
        assert status == 200
        assert pdf[:5] == b"%PDF-"                       # PDF válido
        assert len(pdf) > 100_000                        # con imágenes embebidas
