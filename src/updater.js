/**
 * CimX — Auto-actualización (Windows / macOS)
 *
 * Usa `update-electron-app` (el updater oficial de Electron, sobre el
 * autoUpdater de Squirrel). Solo se activa en la app EMPAQUETADA; en
 * desarrollo es no-op. Nunca lanza: cualquier error se registra y se ignora
 * para no afectar el arranque de la app.
 *
 * Fuente de actualizaciones (en orden de preferencia):
 *   1) CIMX_UPDATE_BASEURL → servidor propio (distribución privada). La URL
 *      debe servir los archivos del maker Squirrel (RELEASES, *.nupkg,
 *      *-Setup.exe) bajo <baseUrl>/<plataforma>/<arch>/.
 *   2) Repo GitHub público (CIMX_UPDATE_REPO = "owner/name") vía el servicio
 *      gratuito update.electronjs.org — requiere repo PÚBLICO con Releases.
 *
 * Ver UPDATES.md.
 */
'use strict';

const { app } = require('electron');

function initAutoUpdates(log) {
  log = log || console;

  // Solo en producción (app empaquetada). En desarrollo no tiene sentido.
  if (!app.isPackaged) {
    log.log('[CimX] Auto-update deshabilitado (modo desarrollo).');
    return;
  }
  // Squirrel autoUpdater existe en Windows y macOS; en Linux no.
  if (process.platform !== 'win32' && process.platform !== 'darwin') {
    log.log('[CimX] Auto-update no soportado en esta plataforma.');
    return;
  }

  try {
    const { updateElectronApp, UpdateSourceType } = require('update-electron-app');
    const baseUrl = process.env.CIMX_UPDATE_BASEURL;
    const repo = process.env.CIMX_UPDATE_REPO;   // "owner/name"

    if (baseUrl) {
      updateElectronApp({
        updateSource: {
          type: UpdateSourceType.StaticStorage,
          baseUrl: `${baseUrl.replace(/\/+$/, '')}/${process.platform}/${process.arch}`,
        },
        updateInterval: '1 hour',
        notifyUser: true,
        logger: log,
      });
      log.log(`[CimX] Auto-update: servidor propio (${baseUrl}).`);
    } else if (repo) {
      updateElectronApp({
        updateSource: {
          type: UpdateSourceType.ElectronPublicUpdateService,
          repo,
        },
        updateInterval: '1 hour',
        notifyUser: true,
        logger: log,
      });
      log.log(`[CimX] Auto-update: update.electronjs.org (${repo}).`);
    } else {
      log.log('[CimX] Auto-update sin configurar (define CIMX_UPDATE_BASEURL '
        + 'o CIMX_UPDATE_REPO). La app funciona igual, sin actualizaciones.');
    }
  } catch (err) {
    log.error('[CimX] No se pudo iniciar el auto-update:', err && err.message);
  }
}

module.exports = { initAutoUpdates };
