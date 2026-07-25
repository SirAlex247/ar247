@echo off
echo =======================================================
echo  INSTALACION DE DEPENDENCIAS - MURO CONTENCION NSR-10
echo =======================================================
echo.
python --version
if errorlevel 1 (
    echo ERROR: Python no esta instalado o no esta en el PATH.
    echo Descarga Python desde https://python.org y marca "Add to PATH"
    pause
    exit /b 1
)
echo.
echo Instalando librerias necesarias...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
echo.
echo =======================================================
echo  INSTALACION COMPLETADA
echo =======================================================
echo Ahora puedes ejecutar la aplicacion presionando el boton
echo Run (triangulo verde) sobre el archivo app.py en VSCode,
echo o ejecutando "iniciar.bat"
echo.
pause
