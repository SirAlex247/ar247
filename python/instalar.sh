#!/bin/bash
echo "======================================================="
echo "  INSTALACION - MURO CONTENCION NSR-10"
echo "======================================================="
echo
python3 --version || { echo "ERROR: instala Python 3 primero"; exit 1; }
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
echo
echo "Instalacion completada. Ejecuta 'python3 app.py' o usa el boton Run."
