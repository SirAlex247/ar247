# Firma de código — CimX (Windows)

Firmar el instalador elimina la advertencia de **"Editor desconocido"** de
Windows SmartScreen y da confianza al usuario final. La firma en CimX es
**opcional y por variables de entorno**: el build funciona sin firmar (para
desarrollo) y firma automáticamente cuando defines el certificado.

## Cómo funciona

`forge.config.js` activa la firma (vía `@electron/windows-sign` + `signtool`)
solo si existe la variable `CIMX_CSC_LINK`. Firma **tres cosas**:

1. El ejecutable de la app (`CimX.exe`) y sus DLLs.
2. El backend Python empaquetado (`resources/python-backend/cimx-backend.exe`).
3. El instalador final (`CimX-Setup.exe`).

Variables de entorno:

| Variable | Obligatoria | Descripción |
|---|---|---|
| `CIMX_CSC_LINK` | sí | Ruta al certificado `.pfx` / `.p12` |
| `CIMX_CSC_KEY_PASSWORD` | sí* | Contraseña del certificado (*si el .pfx la tiene) |
| `CIMX_TIMESTAMP_URL` | no | Servidor de sellado de tiempo (por defecto DigiCert) |

> **Nunca** guardes el `.pfx` ni la contraseña en el repositorio. Están
> excluidos en `.gitignore`. Pásalos por entorno en la máquina/CI de release.

## Build firmado (producción)

Con un certificado de **CA reconocida** (OV o EV code signing):

```powershell
# 1) Compilar el backend Python (una vez, o si cambió)
python python\build_backend.py
Copy-Item -Recurse -Force python\dist\cimx-backend python-backend

# 2) Definir el certificado y firmar durante el make
$env:CIMX_CSC_LINK = "C:\ruta\a\tu-certificado.pfx"
$env:CIMX_CSC_KEY_PASSWORD = "tu-contraseña"
npm run make
```

Resultado firmado: `out\make\squirrel.windows\x64\CimX-Setup.exe`.

Verificar la firma:

```powershell
Get-AuthenticodeSignature out\make\squirrel.windows\x64\CimX-Setup.exe |
  Format-List Status, SignerCertificate, TimeStamperCertificate
```

Con un certificado real, `Status` debe ser **`Valid`**.

## Conseguir un certificado real

- **OV (Organization Validation)**: más barato; SmartScreen construye
  reputación con el tiempo (los primeros usuarios aún verán aviso hasta que
  el certificado acumule descargas).
- **EV (Extended Validation)**: reputación inmediata en SmartScreen, sin
  período de "calentamiento". Suele venir en token HSM/USB.

Proveedores: DigiCert, Sectigo, GlobalSign, SSL.com, etc. El certificado se
emite **a nombre de tu organización/persona** — por eso no puedo generarlo yo.

> Con certificados EV en token hardware, la contraseña/PIN no se pasa por
> archivo; se firma con `signtool` apuntando al certificado del token
> (`/sha1 <thumbprint>`). En ese caso se usa un *hook* de firma personalizado
> en vez de `CIMX_CSC_LINK`. Pídelo cuando tengas el token y lo adapto.

## Probar el pipeline sin comprar certificado (self-signed)

Para validar que el flujo funciona (NO elimina el aviso de SmartScreen, solo
prueba la mecánica):

```powershell
# Crea un certificado de prueba en el escritorio y muestra cómo usarlo
powershell -ExecutionPolicy Bypass -File scripts\crear-cert-prueba.ps1
```

Luego usa la ruta que imprime como `CIMX_CSC_LINK` y corre `npm run make`.
La firma quedará presente pero como "no confiable" (`UnknownError` al
verificar) porque el certificado no viene de una CA — es lo esperado.

## Estado validado

El pipeline se probó end-to-end en Windows con un certificado de prueba:
`CimX.exe`, `cimx-backend.exe` y `CimX-Setup.exe` quedaron firmados y con
sellado de tiempo. Al reemplazar el `.pfx` de prueba por uno de CA real, el
mismo comando produce un instalador de confianza.
