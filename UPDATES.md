# Auto-actualización — CimX

CimX se actualiza solo usando el **autoUpdater de Squirrel.Windows** a través de
[`update-electron-app`](https://github.com/electron/update-electron-app) (el
updater oficial de Electron). La comprobación corre en segundo plano al arrancar
la app **empaquetada** (en desarrollo no hace nada) y, si hay una versión nueva,
la descarga e instala en el siguiente reinicio, avisando al usuario.

## Dos formas de distribuir las actualizaciones

Elige **una** y define sus variables de entorno en la máquina/CI de release.
El código (`src/updater.js`) ya soporta ambas sin cambios.

### A) GitHub Releases (repo PÚBLICO) — gratis

Usa el servicio gratuito `update.electronjs.org`. **Requiere que el repo de
GitHub sea público** y que cada versión se publique como *release*.

En la app (variable de entorno al **construir/empaquetar**):

```
CIMX_UPDATE_REPO = tu-usuario/CimX
```

### B) Servidor propio (distribución PRIVADA)

Sirve tú mismo los artefactos de Squirrel bajo
`<baseUrl>/<plataforma>/<arch>/` (p. ej. un bucket S3, un IIS/nginx estático,
o herramientas como Nuts/Hazel). Los archivos son los que produce
`npm run make`: `RELEASES`, `CimX-1.0.0-full.nupkg`, `CimX-Setup.exe`.

En la app:

```
CIMX_UPDATE_BASEURL = https://descargas.tudominio.com/cimx
```

> Si defines ambas, gana `CIMX_UPDATE_BASEURL`. Si no defines ninguna, la app
> funciona igual pero sin buscar actualizaciones.

## Publicar una versión nueva (ciclo completo)

1. **Subir la versión** en `package.json` (`version`). Squirrel compara por
   SemVer; sin subirla, no hay actualización.

2. **Recompilar el backend** si cambió código Python:
   ```powershell
   python python\build_backend.py
   Copy-Item -Recurse -Force python\dist\cimx-backend python-backend
   ```

3. **Construir (idealmente firmado)** — ver SIGNING.md:
   ```powershell
   $env:CIMX_CSC_LINK = "C:\ruta\cert.pfx"; $env:CIMX_CSC_KEY_PASSWORD = "clave"
   ```

4. **Publicar** los artefactos:

   - **GitHub (opción A):**
     ```powershell
     $env:GITHUB_TOKEN = "<token con permiso repo>"
     $env:CIMX_GH_OWNER = "tu-usuario"; $env:CIMX_GH_REPO = "CimX"
     npm run publish
     ```
     Crea un **release en borrador** (`draft: true` en `forge.config.js`);
     revísalo en GitHub y publícalo para que los usuarios lo reciban.

   - **Servidor propio (opción B):** corre `npm run make` y sube el contenido
     de `out\make\squirrel.windows\x64\` a `<baseUrl>/win32/x64/`.

5. Los usuarios con una versión anterior reciben la actualización
   automáticamente en la próxima apertura de la app.

## Requisitos y notas

- **Firma de código muy recomendada** (SIGNING.md): sin firma, cada
  actualización puede disparar SmartScreen y algunos entornos la bloquean.
- El repo de GitHub aún **no está creado ni subido**: `git init` es local. Para
  la opción A hay que crear el repo (público) y `git push`. Como el proyecto es
  `Proprietary`, valora la opción B (privada) si no quieres el código público.
- `electron-squirrel-startup` (ya integrado) gestiona los accesos directos y el
  ciclo de instalación/actualización/desinstalación de Squirrel.
- macOS necesitaría firma + notarización de Apple para su autoUpdater; hoy el
  foco es Windows.

## Estado

Integrado y empaquetado: la app empaquetada arranca con la comprobación de
updates activa (no-op si no se configura fuente, sin afectar el arranque).
Falta, del lado de infraestructura, elegir A o B y publicar el primer release.
