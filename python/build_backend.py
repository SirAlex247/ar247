"""Script de build del backend ARGeoSt.

Ejecuta PyInstaller con el spec ``argeost_backend.spec`` y deja el
resultado en ``dist/argeost-backend/`` listo para ser empaquetado por
Electron Forge en el siguiente paso.

Uso:
    cd python
    python build_backend.py

Esto produce:
    dist/argeost-backend/
    ├── argeost-backend(.exe)        ← ejecutable
    └── _internal/                   ← Python + libs + datos
        ├── ...
        └── matplotlib/...

El binario es completamente autocontenido — el usuario final NO necesita
tener Python instalado.

Notas importantes:
- En Windows produce ``argeost-backend.exe``.
- En Linux produce ``argeost-backend`` (sin extensión).
- En macOS produce ``argeost-backend`` (sin extensión).
- PyInstaller solo puede generar binarios para el OS donde se ejecuta.
  Para distribuir en Windows hay que correr este script en Windows.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


def main() -> int:
    here = Path(__file__).parent.resolve()
    spec = here / "argeost_backend.spec"
    if not spec.exists():
        print(f"ERROR: no se encuentra {spec}", file=sys.stderr)
        return 1

    # Limpiar builds anteriores
    for d in (here / "build", here / "dist"):
        if d.exists():
            print(f"Limpiando {d}...")
            shutil.rmtree(d)

    print("Iniciando PyInstaller... (esto puede tardar 1-3 minutos)")
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--clean", "--noconfirm",
        str(spec),
        "--distpath", str(here / "dist"),
        "--workpath", str(here / "build"),
    ]
    rc = subprocess.call(cmd, cwd=here)
    if rc != 0:
        print(f"ERROR: PyInstaller falló con código {rc}", file=sys.stderr)
        return rc

    out_dir = here / "dist" / "argeost-backend"
    if not out_dir.exists():
        print(f"ERROR: no se generó {out_dir}", file=sys.stderr)
        return 1

    # Mostrar resumen
    exe_name = "argeost-backend.exe" if sys.platform == "win32" else "argeost-backend"
    exe_path = out_dir / exe_name
    if not exe_path.exists():
        print(f"ERROR: no se encuentra el ejecutable {exe_path}",
              file=sys.stderr)
        return 1

    total_size = sum(p.stat().st_size for p in out_dir.rglob("*") if p.is_file())
    print()
    print("=" * 64)
    print("BUILD COMPLETO")
    print("=" * 64)
    print(f"Carpeta:    {out_dir}")
    print(f"Ejecutable: {exe_path}")
    print(f"Tamaño:     {total_size / (1024*1024):.1f} MB")
    print()
    print("Para probar manualmente:")
    print(f'  "{exe_path}" --port 5050')
    print()
    print("Próximo paso: copiar dist/argeost-backend al proyecto Electron.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
