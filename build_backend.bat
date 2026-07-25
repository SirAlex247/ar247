@echo off
REM ============================================================
REM   CimX - Build del backend (PyInstaller)
REM ============================================================
REM Este script crea el ejecutable autocontenido del backend
REM Python que se empaquetará junto con Electron.
REM
REM Pre-requisitos:
REM   - Python 3.10+ instalado
REM   - pip install -r python\requirements.txt
REM   - pip install pyinstaller
REM
REM Salida:
REM   python-backend\cimx-backend.exe   (lo que Electron usa)
REM ============================================================

setlocal
set ROOT=%~dp0
cd /d "%ROOT%python"

echo.
echo === Verificando PyInstaller ===
python -c "import PyInstaller" 2>nul
if errorlevel 1 (
    echo PyInstaller no esta instalado. Instalando...
    pip install pyinstaller
    if errorlevel 1 (
        echo ERROR: no se pudo instalar PyInstaller
        exit /b 1
    )
)

echo.
echo === Construyendo backend (esto tarda 1-3 minutos) ===
python build_backend.py
if errorlevel 1 (
    echo ERROR: el build fallo
    exit /b 1
)

echo.
echo === Copiando binario al proyecto Electron ===
cd /d "%ROOT%"
if exist python-backend rmdir /s /q python-backend
xcopy /e /i /q python\dist\cimx-backend python-backend >nul
if errorlevel 1 (
    echo ERROR: no se pudo copiar el binario
    exit /b 1
)

echo.
echo ============================================================
echo   BUILD COMPLETO
echo ============================================================
echo Backend listo en: %ROOT%python-backend\cimx-backend.exe
echo.
echo Proximo paso:
echo    npm run make    (genera el instalador)
echo.
endlocal
