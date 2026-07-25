/**
 * CimX — Preload script
 *
 * Este script corre en el proceso renderer ANTES de cargar tu HTML, pero
 * con acceso a Node.js. Sirve de puente seguro: expone al renderer una
 * API mínima en `window.cimx` sin darle acceso completo a Node.
 *
 * El renderer NO puede importar electron ni fs ni path. Solo puede llamar
 * los métodos que se exponen aquí explícitamente.
 */
'use strict';

const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('cimx', {
  /**
   * Devuelve la URL base del backend Python (ej. "http://127.0.0.1:50192").
   * Si el backend aún no está listo, devuelve null.
   */
  getBackendUrl: async () => {
    return await ipcRenderer.invoke('cimx:get-backend-url');
  },

  /**
   * Indica si la app corre dentro de Electron (true) o en navegador (false).
   * Útil para que el frontend tenga un fallback.
   */
  isElectron: true,

  /**
   * Versión de la app (para mostrar en la UI si se quiere).
   */
  appVersion: '1.0.0',
});
