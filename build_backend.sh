#!/usr/bin/env bash
# ============================================================
#   ARGeoSt — Build del backend (PyInstaller)
# ============================================================
# Este script crea el ejecutable autocontenido del backend
# Python que se empaquetará junto con Electron.
# ============================================================
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT/python"

echo
echo "=== Verificando PyInstaller ==="
if ! python3 -c "import PyInstaller" 2>/dev/null; then
    echo "PyInstaller no está instalado. Instalando..."
    pip install pyinstaller || pip install --break-system-packages pyinstaller
fi

echo
echo "=== Construyendo backend (esto tarda 1-3 minutos) ==="
python3 build_backend.py

echo
echo "=== Copiando binario al proyecto Electron ==="
cd "$ROOT"
rm -rf python-backend
cp -r python/dist/argeost-backend python-backend

echo
echo "============================================================"
echo "  BUILD COMPLETO"
echo "============================================================"
if [ -f "python-backend/argeost-backend.exe" ]; then
    echo "Backend listo en: $ROOT/python-backend/argeost-backend.exe"
else
    echo "Backend listo en: $ROOT/python-backend/argeost-backend"
fi
echo
echo "Próximo paso:"
echo "   npm run make    (genera el instalador)"
echo
