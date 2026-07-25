# ARGeoSt — Diseño de muros de contención (NSR-10)

App de escritorio (Electron + Python/Flask) para diseño y verificación
de muros de contención conforme a la NSR-10 colombiana.

Validada contra los ejemplos 8.1 y 8.2 de Braja M. Das,
*Fundamentos de ingeniería de cimentaciones*.

## Estructura

```
ARGeoSt/
├── package.json         ← configuración Electron
├── src/
│   ├── main.js          ← proceso principal (Electron)
│   ├── preload.js       ← puente seguro renderer↔main
│   └── assets/          ← íconos
└── python/              ← backend Flask (lógica de cálculo)
    ├── app.py
    ├── run_server.py    ← punto de entrada cuando corre desde Electron
    ├── retaining_wall/  ← módulos de cálculo
    ├── templates/
    └── static/
```

## Requisitos para desarrollo

- **Node.js** 18 o superior (para Electron)
- **Python** 3.10 o superior (para el backend)
- **Dependencias Python** instaladas:
  ```bash
  cd python
  pip install -r requirements.txt
  ```

## Cómo correrlo en desarrollo

### Modo Electron (app de escritorio)

```bash
npm install        # solo la primera vez, baja Electron
npm start
```

Esto lanza Python en un puerto libre aleatorio, espera a que esté listo,
y abre la ventana de Electron cargando la UI.

### Modo navegador (debug rápido)

```bash
cd python
python app.py     # arranca Flask en http://localhost:5000
```

Abre tu navegador en `http://localhost:5000`. Útil para iterar UI rápido
sin tener que reiniciar Electron.

### Desarrollo con DevTools de Electron

```bash
ARGEOST_DEVTOOLS=1 npm start          # macOS/Linux
set ARGEOST_DEVTOOLS=1 && npm start   # Windows
```

## Cómo empaquetar (instalador `.exe`)

El empaquetado tiene **dos fases**: primero compilamos el backend Python como
ejecutable autocontenido (PyInstaller), luego Electron Forge incluye ese
ejecutable junto con la UI dentro del instalador final.

### Fase 1 — Compilar el backend Python

Esto solo lo haces UNA vez (o cuando cambies código del backend):

**Windows:**
```cmd
build_backend.bat
```

**macOS/Linux:**
```bash
./build_backend.sh
```

El script:
1. Verifica que `pyinstaller` esté instalado (lo instala si falta).
2. Empaqueta `python/run_server.py` con todas sus dependencias en un
   ejecutable autocontenido (`argeost-backend.exe` en Windows).
3. Copia el resultado a `python-backend/` en la raíz del proyecto.

Tarda 1-3 minutos. El resultado es ~135 MB (incluye Python + matplotlib +
reportlab + Flask). El usuario final NO necesita tener Python instalado.

### Fase 2 — Empaquetar Electron + instalador

Una vez el backend está compilado:

```bash
npm run package    # genera carpeta out/ con la app empaquetada
npm run make       # genera el instalador final
```

En **Windows** produce `out/make/squirrel.windows/x64/ARGeoSt-Setup.exe`.
En **macOS/Linux** produce un `.zip`.

El instalador es un solo archivo que tu usuario descarga y ejecuta.

## Verificación

El motor de cálculo tiene una suite de pruebas en `tests/` que valida lo que la
app ejecuta realmente (empujes, estabilidad, pipeline de muros, pilote/zapata/
dado y combinaciones NSR-10). Ver `tests/README.md`.

```bash
python tests/run_all.py     # sin dependencias extra
pytest                      # si tienes pytest instalado
```

### Validación contra Braja Das

Reproducidos automáticamente en `tests/test_das.py` con la geometría exacta de
las figuras 8.12 y 8.13 del libro:

| Caso | Magnitud | Das | ARGeoSt | Δ |
|---|---|---|---|---|
| Ej. 8.1 (voladizo) | FS_volcamiento | 2.95 | 2.98 | +1.0% |
| | FS_deslizamiento | 2.70 | 2.73 | +1.0% |
| | FS_capacidad | 2.98 | 3.02 | +1.3% |
| | q_puntera | 190.2 kPa | 189.1 kPa | −0.6% |
| Ej. 8.2 (gravedad) | FS_volcamiento | 2.67 | 2.67 | ~0% |
| | FS_deslizamiento | 2.84 | 2.84 | ~0% |
| | q_puntera | 188.4 kPa | 188.3 kPa | ~0% |

> El +1% del Ej. 8.1 proviene de que Das toma Ka = 0.3532 de tabla, mientras el
> programa usa la fórmula cerrada de Rankine (Ka = 0.3495). El test E2E de la
> cadena Electron→PyInstaller→Flask→PDF aún no está implementado.
