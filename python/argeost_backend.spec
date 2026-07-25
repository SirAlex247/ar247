# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec — ARGeoSt backend.

Este archivo describe a PyInstaller cómo empaquetar el backend Flask
(``run_server.py``) en un único ejecutable autocontenido para distribución
con Electron.

Ejecución típica desde la carpeta python/:
    pyinstaller --clean --noconfirm argeost_backend.spec

Salida: dist/argeost-backend/argeost-backend(.exe)
        dist/argeost-backend/_internal/...   (Python + libs + datos)
"""
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# ─── Datos a incluir ──────────────────────────────────────────────────
# Flask necesita los templates Jinja2 y los archivos estáticos. Los
# copiamos directamente al binario.
datas = [
    ('templates', 'templates'),
    ('static', 'static'),
]

# matplotlib trae fonts, mpl-data y otros datos que NO son código y
# deben copiarse para que las figuras se rendericen igual que en
# desarrollo. ``collect_data_files`` los detecta automáticamente.
datas += collect_data_files('matplotlib')
# reportlab también lleva fuentes (.ttf), mapas de glifos, etc.
datas += collect_data_files('reportlab')

# ─── Hidden imports ───────────────────────────────────────────────────
# Algunos módulos se importan dinámicamente (a través de __import__,
# importlib, o decoradores) y PyInstaller no los detecta. Los listamos
# explícitamente.
hiddenimports = []
# matplotlib backends (cargados dinámicamente según uso)
hiddenimports += [
    'matplotlib.backends.backend_agg',
    'matplotlib.backends.backend_svg',
]
# reportlab — fuentes y módulos comunes
hiddenimports += collect_submodules('reportlab.lib')
hiddenimports += collect_submodules('reportlab.pdfbase')
hiddenimports += collect_submodules('reportlab.platypus')
# Flask depende de varios módulos de werkzeug
hiddenimports += collect_submodules('werkzeug')
# Nuestro paquete
hiddenimports += collect_submodules('retaining_wall')

# ─── Análisis ─────────────────────────────────────────────────────────
a = Analysis(
    ['run_server.py'],
    pathex=['.'],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Estos paquetes son grandes y NO se usan; los excluimos para
        # bajar el tamaño del binario en cientos de MB.
        'tkinter', 'IPython', 'jupyter', 'notebook',
        'pytest', 'sphinx', 'docutils', 'pydoc_data',
        'numpy.distutils', 'scipy', 'pandas',
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# ─── EXE ──────────────────────────────────────────────────────────────
# Modo "onedir" (carpeta): más rápido al arranque que onefile y mucho
# más fácil de debuggear si algo falla. El usuario nunca ve esta
# carpeta porque está dentro de los recursos de Electron.
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='argeost-backend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,           # UPX comprime más pero a veces falsos positivos en antivirus
    console=True,        # se mantiene console=True para ver errores; Electron usa
                         # windowsHide=true al spawn para que no se vea la consola
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='argeost-backend',
)
