/**
 * Configuración de Electron Forge para CimX.
 *
 * Firma de código (Windows) — OPCIONAL y por variables de entorno, para no
 * guardar secretos en el repo. Se activa SOLO si defines:
 *
 *   CIMX_CSC_LINK            ruta al certificado .pfx/.p12
 *   CIMX_CSC_KEY_PASSWORD    contraseña del certificado
 *   CIMX_TIMESTAMP_URL       (opcional) servidor de sellado de tiempo
 *
 * Sin esas variables, el build NO firma (modo desarrollo). Con ellas, firma
 * tanto el ejecutable de la app como el instalador. Ver SIGNING.md.
 */
'use strict';

function windowsSign() {
  const certificateFile = process.env.CIMX_CSC_LINK;
  if (!certificateFile) return undefined;   // sin certificado → no se firma
  return {
    certificateFile,
    certificatePassword: process.env.CIMX_CSC_KEY_PASSWORD || undefined,
    // Sellado de tiempo: mantiene válida la firma aun después de que el
    // certificado expire. Requiere red durante el build.
    timestampServer: process.env.CIMX_TIMESTAMP_URL || 'http://timestamp.digicert.com',
    hashes: ['sha256'],
  };
}

const firma = windowsSign();

module.exports = {
  packagerConfig: {
    name: 'CimX',
    executableName: 'CimX',
    icon: 'src/assets/icon',
    asar: true,
    extraResource: ['python-backend'],
    ignore: [
      '^/python($|/)',
      '^/build_backend\\.bat$',
      '^/build_backend\\.sh$',
      '^/forge\\.config\\.js$',
      '^/tests($|/)',
      '^/libros($|/)',
      '/__pycache__/',
      '\\.pyc$',
    ],
    // Firma del ejecutable de la app y sus DLLs (solo si hay certificado).
    ...(firma ? { windowsSign: firma } : {}),
  },
  rebuildConfig: {},
  makers: [
    {
      name: '@electron-forge/maker-squirrel',
      config: {
        name: 'CimX',
        setupExe: 'CimX-Setup.exe',
        iconUrl: 'https://raw.githubusercontent.com/example/cimx/main/icon.ico',
        setupIcon: 'src/assets/icon.ico',
        // Firma del instalador Setup.exe (solo si hay certificado).
        ...(firma ? { windowsSign: firma } : {}),
      },
    },
    {
      name: '@electron-forge/maker-zip',
      platforms: ['darwin', 'linux'],
    },
  ],
  // Publicación de releases (para el auto-update). `npm run publish` sube los
  // artefactos (RELEASES, *.nupkg, *-Setup.exe) a GitHub Releases. Requiere:
  //   GITHUB_TOKEN     token con permiso 'repo'
  //   CIMX_GH_OWNER    dueño del repo (usuario u organización)
  //   CIMX_GH_REPO     nombre del repo (por defecto "CimX")
  // Ver UPDATES.md.
  publishers: [
    {
      name: '@electron-forge/publisher-github',
      config: {
        repository: {
          owner: process.env.CIMX_GH_OWNER || 'tu-usuario-github',
          name: process.env.CIMX_GH_REPO || 'CimX',
        },
        prerelease: false,
        draft: true,   // crea el release como borrador para revisarlo antes de publicar
      },
    },
  ],
};
