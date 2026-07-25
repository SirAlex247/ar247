@echo off
title Muro Contencion NSR-10
echo =======================================================
echo  APP DE DISENO DE MUROS DE CONTENCION - NSR-10
echo =======================================================
echo.
echo Iniciando servidor web...
echo Se abrira automaticamente en tu navegador.
echo.
echo Para DETENER la app, cierra esta ventana negra.
echo =======================================================
echo.
start "" "http://localhost:5000"
python app.py
pause
