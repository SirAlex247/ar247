/**
 * CimX — Guardar / Abrir proyecto
 *
 * Serializa TODOS los campos del formulario (inputs/select/textarea con id) a
 * un archivo `.cimx.json` y los restaura al abrirlo. Es genérico: funciona
 * en todos los módulos (muro, pilote, zapata, dado) porque la UI identifica
 * cada campo por su `id`. No requiere backend.
 */
(function () {
  'use strict';
  const VERSION = '1.0';

  /** Serializa el estado del formulario a un objeto plano. */
  function serializar() {
    const campos = {};
    document.querySelectorAll('input[id], select[id], textarea[id]').forEach((el) => {
      if (['button', 'submit', 'file', 'reset'].includes(el.type)) return;
      if (el.type === 'checkbox' || el.type === 'radio') {
        campos[el.id] = { _tipo: el.type, checked: el.checked, value: el.value };
      } else {
        campos[el.id] = el.value;
      }
    });
    return {
      __cimx_proyecto: VERSION,
      fecha: new Date().toISOString(),
      modulo: document.body.dataset.modulo || '',
      tipo_muro: (document.getElementById('tipo_muro') || {}).value || null,
      campos,
    };
  }

  /** Restaura los valores al DOM y dispara eventos para que la UI reaccione.
   *  Devuelve cuántos campos se aplicaron. */
  function restaurar(data) {
    if (!data || !data.__cimx_proyecto || !data.campos) {
      throw new Error('El archivo no es un proyecto de CimX válido.');
    }
    let aplicados = 0;
    Object.entries(data.campos).forEach(([id, val]) => {
      const el = document.getElementById(id);
      if (!el) return;
      if (val && typeof val === 'object' && (val._tipo === 'checkbox' || val._tipo === 'radio')) {
        el.checked = !!val.checked;
        if (val.value != null) el.value = val.value;
      } else {
        el.value = val;
      }
      el.dispatchEvent(new Event('input', { bubbles: true }));
      el.dispatchEvent(new Event('change', { bubbles: true }));
      aplicados++;
    });
    return aplicados;
  }

  /** Descarga el proyecto actual como archivo .cimx.json. */
  function guardar() {
    const data = serializar();
    const nombre = (document.getElementById('proyecto') || {}).value || 'proyecto';
    const slug = (nombre.trim().replace(/\s+/g, '_').replace(/[^\w-]/g, '')) || 'proyecto';
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = slug + '.cimx.json';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  /** Lee un archivo seleccionado y restaura el proyecto. */
  function abrirDesdeArchivo(file) {
    const reader = new FileReader();
    reader.onload = (ev) => {
      try {
        const data = JSON.parse(ev.target.result);
        // Cambiar al módulo/tipo guardado antes de restaurar (si aplica).
        if (data.modulo && typeof window.seleccionarModulo === 'function') {
          try { window.seleccionarModulo(data.modulo); } catch (_) { /* noop */ }
        }
        const tm = document.getElementById('tipo_muro');
        if (tm && data.tipo_muro) {
          tm.value = data.tipo_muro;
          tm.dispatchEvent(new Event('change', { bubbles: true }));
        }
        const n = restaurar(data);
        if (typeof window.toast === 'function') window.toast(`Proyecto cargado (${n} campos).`);
        else alert(`Proyecto cargado: ${n} campos restaurados.`);
      } catch (err) {
        alert('No se pudo abrir el proyecto: ' + err.message);
      }
    };
    reader.readAsText(file);
  }

  function wire() {
    const btnG = document.getElementById('btn-guardar-proy');
    const btnA = document.getElementById('btn-abrir-proy');
    const fileInput = document.getElementById('input-abrir-proy');
    if (btnG) btnG.addEventListener('click', guardar);
    if (btnA && fileInput) {
      btnA.addEventListener('click', () => fileInput.click());
      fileInput.addEventListener('change', (ev) => {
        if (ev.target.files && ev.target.files[0]) abrirDesdeArchivo(ev.target.files[0]);
        ev.target.value = '';  // permite reabrir el mismo archivo
      });
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', wire);
  } else {
    wire();
  }

  // Expuesto para pruebas y uso programático.
  window.CimXProyecto = { serializar, restaurar, guardar, abrirDesdeArchivo };
})();
