/**
 * CimX — Proceso principal de Electron
 *
 * Responsabilidades:
 *   1. Lanzar el backend Python (Flask) como subprocess al iniciar la app.
 *   2. Esperar a que el servidor responda /api/health antes de cargar UI.
 *   3. Crear la ventana principal y cargar http://127.0.0.1:<puerto>.
 *   4. Manejar los menús y el ciclo de vida (cerrar Python al salir).
 *
 * El backend Python es siempre local (loopback 127.0.0.1) y nunca expone
 * el servidor a la red. El renderer NO tiene acceso directo a Node.js
 * por seguridad — toda la comunicación pasa por el preload script.
 */
'use strict';

const { app, BrowserWindow, Menu, shell, dialog } = require('electron');
const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');
const os = require('os');
const http = require('http');

// ─────────────────────────────────────────────────────────────────────
// Configuración
// ─────────────────────────────────────────────────────────────────────
const APP_NAME = 'CimX';
const STARTUP_TIMEOUT_MS = 30_000;     // 30 s para que Python arranque
const HEALTH_POLL_INTERVAL_MS = 200;   // cada 200 ms
const HOST = '127.0.0.1';

// Para distinguir desarrollo de producción.
// En desarrollo: Python está en ./python/ relativo a este archivo.
// En producción (empaquetado): Python está en process.resourcesPath/python.
const isDev = !app.isPackaged;

// ─────────────────────────────────────────────────────────────────────
// Estado global
// ─────────────────────────────────────────────────────────────────────
let pythonProcess = null;
let backendPort = null;
let mainWindow = null;

// ─────────────────────────────────────────────────────────────────────
// Lanzar el backend Python
// ─────────────────────────────────────────────────────────────────────
function getBackendCommand() {
  // Devuelve {executable, args} para arrancar el backend.
  //
  // En PRODUCCIÓN (app empaquetada) usamos el binario PyInstaller que
  // está en resources/python-backend/cimx-backend(.exe). Es totalmente
  // autocontenido — el usuario final NO necesita Python instalado.
  //
  // En DESARROLLO (npm start desde el repo) usamos el python del sistema
  // ejecutando ./python/run_server.py. Es lo que hicimos en el Paso 2.

  if (!isDev) {
    // Producción: binario empaquetado
    const exeName = process.platform === 'win32'
      ? 'cimx-backend.exe' : 'cimx-backend';
    const exePath = path.join(
      process.resourcesPath, 'python-backend', exeName
    );
    if (!fs.existsSync(exePath)) {
      throw new Error(
        `No se encuentra el backend empaquetado en:\n${exePath}\n\n`
        + `Esto significa que la app fue compilada sin haber corrido\n`
        + `previamente "python build_backend.py".`
      );
    }
    return { executable: exePath, args: [], cwd: path.dirname(exePath) };
  }

  // Desarrollo: python del sistema
  const pyExe = process.platform === 'win32' ? 'python' : 'python3';
  const pyScript = path.join(__dirname, '..', 'python', 'run_server.py');
  if (!fs.existsSync(pyScript)) {
    throw new Error(`No se encontró el script Python: ${pyScript}`);
  }
  return {
    executable: pyExe,
    args: [pyScript],
    cwd: path.dirname(pyScript),
  };
}

function getPortFilePath() {
  const tmp = app.getPath('userData');
  if (!fs.existsSync(tmp)) fs.mkdirSync(tmp, { recursive: true });
  return path.join(tmp, 'port.txt');
}

function startPythonBackend() {
  return new Promise((resolve, reject) => {
    const portFile = getPortFilePath();
    // Limpiar puerto anterior si existe
    try { if (fs.existsSync(portFile)) fs.unlinkSync(portFile); } catch (_) {}

    let cmd;
    try {
      cmd = getBackendCommand();
    } catch (err) {
      return reject(err);
    }

    console.log(`[CimX] Lanzando backend: ${cmd.executable}`);
    if (cmd.args.length) {
      console.log(`[CimX]   args: ${cmd.args.join(' ')}`);
    }
    console.log(`[CimX] Archivo de puerto: ${portFile}`);

    const fullArgs = [...cmd.args, '--host', HOST, '--port-file', portFile];
    pythonProcess = spawn(cmd.executable, fullArgs, {
      cwd: cmd.cwd,
      stdio: ['ignore', 'pipe', 'pipe'],
      windowsHide: true,
    });

    pythonProcess.stdout.on('data', (data) => {
      process.stdout.write(`[backend] ${data}`);
    });
    pythonProcess.stderr.on('data', (data) => {
      process.stderr.write(`[backend:err] ${data}`);
    });
    pythonProcess.on('error', (err) => {
      console.error('[CimX] Error al lanzar backend:', err);
      reject(err);
    });
    pythonProcess.on('exit', (code, signal) => {
      console.log(`[CimX] Backend terminó (code=${code}, signal=${signal})`);
      pythonProcess = null;
    });

    // Poll del archivo de puerto + /api/health
    const t0 = Date.now();
    const check = setInterval(async () => {
      // Timeout
      if (Date.now() - t0 > STARTUP_TIMEOUT_MS) {
        clearInterval(check);
        return reject(new Error(
          'Timeout: el backend no respondió a tiempo. '
          + (isDev
              ? 'Verifica que Python esté instalado y en el PATH.'
              : 'Reinstala la aplicación.')
        ));
      }
      // ¿Existe ya el archivo con el puerto?
      if (!fs.existsSync(portFile)) return;
      let port;
      try {
        port = parseInt(fs.readFileSync(portFile, 'utf-8').trim(), 10);
      } catch (_) { return; }
      if (!port || isNaN(port)) return;

      // ¿Responde /api/health?
      const healthy = await pingHealth(port).catch(() => false);
      if (!healthy) return;

      clearInterval(check);
      backendPort = port;
      console.log(`[CimX] Backend listo en http://${HOST}:${port}`);
      resolve(port);
    }, HEALTH_POLL_INTERVAL_MS);
  });
}

function pingHealth(port) {
  return new Promise((resolve) => {
    const req = http.get(
      { host: HOST, port, path: '/api/health', timeout: 1500 },
      (res) => {
        let data = '';
        res.on('data', (c) => (data += c));
        res.on('end', () => {
          try {
            const j = JSON.parse(data);
            resolve(!!j.ok);
          } catch (_) { resolve(false); }
        });
      }
    );
    req.on('error', () => resolve(false));
    req.on('timeout', () => { req.destroy(); resolve(false); });
  });
}

// ─────────────────────────────────────────────────────────────────────
// Ventana principal
// ─────────────────────────────────────────────────────────────────────
function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1500,
    height: 950,
    minWidth: 1200,
    minHeight: 750,
    title: APP_NAME,
    backgroundColor: '#f5f7fa',
    icon: getIconPath(),
    show: false,                 // mostrar después de cargar para evitar parpadeo
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,    // aislamiento del contexto (seguridad)
      nodeIntegration: false,    // sin Node en el renderer
      sandbox: false,            // necesitamos `require` en el preload
    },
  });

  // Aplicar el menú estándar
  Menu.setApplicationMenu(buildAppMenu());

  // Cargar la URL del backend local
  const url = `http://${HOST}:${backendPort}/`;
  console.log(`[CimX] Cargando UI: ${url}`);
  mainWindow.loadURL(url);

  mainWindow.once('ready-to-show', () => mainWindow.show());

  // Evita que enlaces externos abran ventanas dentro de Electron
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: 'deny' };
  });

  // En desarrollo abre DevTools al inicio si la env var está activa
  if (isDev && process.env.CIMX_DEVTOOLS === '1') {
    mainWindow.webContents.openDevTools({ mode: 'detach' });
  }
}

function getIconPath() {
  const iconBase = path.join(__dirname, 'assets', 'icon');
  if (process.platform === 'win32' && fs.existsSync(iconBase + '.ico'))
    return iconBase + '.ico';
  if (process.platform === 'darwin' && fs.existsSync(iconBase + '.icns'))
    return iconBase + '.icns';
  if (fs.existsSync(iconBase + '.png')) return iconBase + '.png';
  return undefined;        // Electron usa ícono por defecto
}

function buildAppMenu() {
  const isMac = process.platform === 'darwin';
  const template = [
    ...(isMac ? [{
      label: APP_NAME,
      submenu: [
        { role: 'about' },
        { type: 'separator' },
        { role: 'services' },
        { type: 'separator' },
        { role: 'hide' },
        { role: 'hideOthers' },
        { role: 'unhide' },
        { type: 'separator' },
        { role: 'quit' },
      ],
    }] : []),
    {
      label: 'Archivo',
      submenu: [
        isMac ? { role: 'close' } : { role: 'quit', label: 'Salir' },
      ],
    },
    {
      label: 'Editar',
      submenu: [
        { role: 'undo', label: 'Deshacer' },
        { role: 'redo', label: 'Rehacer' },
        { type: 'separator' },
        { role: 'cut', label: 'Cortar' },
        { role: 'copy', label: 'Copiar' },
        { role: 'paste', label: 'Pegar' },
        { role: 'selectAll', label: 'Seleccionar todo' },
      ],
    },
    {
      label: 'Ver',
      submenu: [
        { role: 'reload', label: 'Recargar' },
        { role: 'forceReload', label: 'Forzar recarga' },
        { role: 'toggleDevTools', label: 'Herramientas de desarrollador' },
        { type: 'separator' },
        { role: 'resetZoom', label: 'Tamaño normal' },
        { role: 'zoomIn', label: 'Acercar' },
        { role: 'zoomOut', label: 'Alejar' },
        { type: 'separator' },
        { role: 'togglefullscreen', label: 'Pantalla completa' },
      ],
    },
    {
      label: 'Ayuda',
      submenu: [
        {
          label: 'Acerca de CimX',
          click: () => {
            dialog.showMessageBox(mainWindow, {
              type: 'info',
              title: 'Acerca de CimX',
              message: 'CimX v1.0.0',
              detail:
                'Diseño de muros de contención conforme a la NSR-10 (Colombia).\n'
                + '\n'
                + 'Validado contra los ejemplos 8.1 y 8.2 de\n'
                + 'Braja M. Das — "Fundamentos de ingeniería de cimentaciones".\n'
                + '\n'
                + 'Tipos soportados: voladizo, gravedad.\n'
                + 'Métodos: Rankine, Coulomb, Mononobe-Okabe.',
              buttons: ['OK'],
            });
          },
        },
      ],
    },
  ];
  return Menu.buildFromTemplate(template);
}

// ─────────────────────────────────────────────────────────────────────
// IPC: el renderer pregunta cuál es la URL del backend
// ─────────────────────────────────────────────────────────────────────
const { ipcMain } = require('electron');
ipcMain.handle('cimx:get-backend-url', () => {
  return backendPort ? `http://${HOST}:${backendPort}` : null;
});

// ─────────────────────────────────────────────────────────────────────
// Ciclo de vida
// ─────────────────────────────────────────────────────────────────────
app.whenReady().then(async () => {
  try {
    await startPythonBackend();
    createWindow();
  } catch (err) {
    dialog.showErrorBox(
      'Error iniciando CimX',
      `No se pudo iniciar el backend de cálculo:\n\n${err.message}`
    );
    app.quit();
  }

  app.on('activate', () => {
    // En macOS recrear la ventana cuando se reactiva la app
    if (BrowserWindow.getAllWindows().length === 0 && backendPort) {
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

app.on('before-quit', () => {
  // Apagar el backend Python ordenadamente
  if (pythonProcess) {
    console.log('[CimX] Cerrando backend Python...');
    try {
      // En Windows kill() manda SIGTERM; el proceso debería cerrar limpio.
      pythonProcess.kill();
    } catch (e) {
      console.error('Error al cerrar Python:', e);
    }
  }
});
