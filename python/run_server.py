"""Punto de entrada del backend Flask para empaquetado en CimX (Electron).

Diferencias respecto a ``app.py``:
- Acepta el puerto por argumento ``--port``. Si se omite, busca un puerto
  libre aleatorio (lo que hace Electron para evitar colisiones).
- Escribe el puerto efectivo a ``port.txt`` en la carpeta indicada por
  ``--port-file``, para que el proceso padre (Electron) lo lea.
- Acepta ``--host`` (default ``127.0.0.1``) — solo loopback, nunca expone
  el servidor a la red.
- Escribe logs a stdout/stderr para que Electron los capture.

Uso típico desde Electron:
    python run_server.py --port-file ./port.txt

Uso para desarrollo (puerto fijo conocido):
    python run_server.py --port 5000
"""
from __future__ import annotations

import argparse
import socket
import sys
from pathlib import Path

from app import app


def _puerto_libre() -> int:
    """Encuentra un puerto TCP libre asignado por el SO."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Backend Flask de CimX — diseño de muros NSR-10",
    )
    parser.add_argument(
        "--host", default="127.0.0.1",
        help="Interfaz a la que se enlaza el servidor (default 127.0.0.1)",
    )
    parser.add_argument(
        "--port", type=int, default=None,
        help="Puerto fijo. Si se omite, se busca uno libre aleatorio.",
    )
    parser.add_argument(
        "--port-file", default=None,
        help="Ruta donde escribir el puerto efectivo (para Electron)",
    )
    args = parser.parse_args()

    puerto = args.port if args.port is not None else _puerto_libre()

    if args.port_file:
        try:
            Path(args.port_file).write_text(str(puerto), encoding="utf-8")
        except Exception as e:
            print(f"[CimX] No se pudo escribir el archivo de puerto: {e}",
                  file=sys.stderr)
            return 2

    # El log a stdout es importante: Electron lo captura y puede usar
    # marcadores para saber cuándo el server está listo.
    print(f"[CimX] Backend iniciado en http://{args.host}:{puerto}",
          flush=True)
    print(f"[CimX] READY puerto={puerto}", flush=True)

    # Werkzeug muestra mucho ruido por defecto; en producción Electron
    # no lo quiere. Lo silenciamos pero conservamos los errores.
    import logging
    logging.getLogger("werkzeug").setLevel(logging.ERROR)

    try:
        app.run(host=args.host, port=puerto, debug=False,
                use_reloader=False, threaded=True)
    except KeyboardInterrupt:
        print("[CimX] Detenido por el usuario", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
