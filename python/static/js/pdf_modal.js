/* ============================================================
   CimX — Modal de previsualización del PDF
   Renderiza el PDF con PDF.js (canvas 2D) en lugar del visor
   nativo del navegador. Esto funciona de forma idéntica en el
   navegador y en Electron (incluso con render por software /
   sin GPU), donde el visor nativo no muestra blobs en <iframe>.
   ============================================================ */
'use strict';

window.CimXPDFModal = (function () {

  let modalEl = null;
  let currentBlobUrl = null;
  let renderToken = 0;          // invalida renders en curso al reabrir/cerrar

  const WORKER_SRC = '/static/js/vendor/pdf.worker.min.js';

  function buildModal() {
    if (modalEl) return modalEl;
    modalEl = document.createElement('div');
    modalEl.className = 'pdf-modal';
    modalEl.innerHTML = `
      <div class="pdf-modal-backdrop"></div>
      <div class="pdf-modal-card">
        <div class="pdf-modal-header">
          <div class="pdf-modal-title">
            <svg viewBox="0 0 24 24" width="20" height="20" stroke="currentColor"
                 fill="none" stroke-width="1.8" style="vertical-align:-4px;margin-right:6px">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
              <polyline points="14 2 14 8 20 8"/>
            </svg>
            <span>Previsualización del Reporte</span>
          </div>
          <div class="pdf-modal-actions">
            <button class="btn btn-primary" id="pdf-modal-download">
              <svg viewBox="0 0 24 24" width="16" height="16" stroke="currentColor"
                   fill="none" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
              <span>Descargar</span>
            </button>
            <button class="btn btn-secondary" id="pdf-modal-close">
              <svg viewBox="0 0 24 24" width="16" height="16" stroke="currentColor"
                   fill="none" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
              <span>Cerrar</span>
            </button>
          </div>
        </div>
        <div class="pdf-modal-body">
          <div id="pdf-modal-pages" class="pdf-modal-pages"></div>
        </div>
      </div>
    `;
    document.body.appendChild(modalEl);

    modalEl.querySelector('.pdf-modal-backdrop').addEventListener('click', close);
    modalEl.querySelector('#pdf-modal-close').addEventListener('click', close);
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && modalEl.classList.contains('open')) close();
    });

    return modalEl;
  }

  function _status(msg) {
    const cont = modalEl.querySelector('#pdf-modal-pages');
    cont.innerHTML = `<div class="pdf-modal-status">${msg}</div>`;
  }

  function _withTimeout(promise, ms, label) {
    let to;
    const guard = new Promise((_, rej) => {
      to = setTimeout(() => rej(new Error('timeout ' + label)), ms);
    });
    return Promise.race([promise, guard]).finally(() => clearTimeout(to));
  }

  function _fallbackMsg() {
    // Aviso no destructivo cuando la previsualización no está disponible.
    const cont = modalEl.querySelector('#pdf-modal-pages');
    if (cont.querySelector('canvas')) return;   // ya hay páginas: no molestar
    _status('No se pudo generar la previsualización en pantalla. '
            + 'El reporte está listo: usa el botón «Descargar» (arriba a la '
            + 'derecha) para abrirlo o guardarlo.');
  }

  async function _render(blob, token) {
    const cont = modalEl.querySelector('#pdf-modal-pages');
    if (typeof pdfjsLib === 'undefined') { _fallbackMsg(); return; }
    let pdf;
    try {
      pdfjsLib.GlobalWorkerOptions.workerSrc = WORKER_SRC;
      const data = await blob.arrayBuffer();
      if (token !== renderToken) return;
      pdf = await _withTimeout(pdfjsLib.getDocument({ data }).promise, 15000, 'getDocument');
      if (token !== renderToken) return;
    } catch (err) {
      console.error('[PDF.js] No se pudo abrir el PDF:', err);
      _fallbackMsg();
      return;
    }
    cont.innerHTML = '';

    const body = modalEl.querySelector('.pdf-modal-body');
    const availW = Math.max(320, body.clientWidth - 28);
    const dpr = Math.min(window.devicePixelRatio || 1, 1.5);
    let renderizadas = 0;

    for (let n = 1; n <= pdf.numPages; n++) {
      if (token !== renderToken) return;
      try {
        const page = await _withTimeout(pdf.getPage(n), 20000, 'getPage' + n);
        const base = page.getViewport({ scale: 1 });
        const fit = Math.min(1.5, availW / base.width);
        const vp = page.getViewport({ scale: fit * dpr });
        const canvas = document.createElement('canvas');
        canvas.className = 'pdf-page-canvas';
        canvas.width = Math.floor(vp.width);
        canvas.height = Math.floor(vp.height);
        canvas.style.width = Math.floor(vp.width / dpr) + 'px';
        cont.appendChild(canvas);
        await _withTimeout(
          page.render({ canvasContext: canvas.getContext('2d'), viewport: vp }).promise,
          20000, 'render' + n);
        renderizadas++;
      } catch (err) {
        console.error('[PDF.js] Falló la página ' + n + ':', err);
        // Continúa con las demás páginas; si ninguna sale, muestra el aviso.
        const c = cont.lastElementChild;
        if (c && c.tagName === 'CANVAS' && !c.width) c.remove();
        if (n === 1) { _fallbackMsg(); return; }
      }
    }
    if (renderizadas === 0) _fallbackMsg();
  }

  function open(blob, filename) {
    buildModal();
    if (currentBlobUrl) { URL.revokeObjectURL(currentBlobUrl); currentBlobUrl = null; }
    currentBlobUrl = URL.createObjectURL(blob);

    const dlBtn = modalEl.querySelector('#pdf-modal-download');
    dlBtn.onclick = () => {
      const a = document.createElement('a');
      a.href = currentBlobUrl;
      a.download = filename || 'CimX-reporte.pdf';
      document.body.appendChild(a);
      a.click();
      a.remove();
    };

    modalEl.classList.add('open');
    document.body.style.overflow = 'hidden';

    const token = ++renderToken;
    _status('Generando previsualización…');
    // Esperar a que el modal tenga ancho real antes de calcular la escala.
    requestAnimationFrame(() => _render(blob, token));
  }

  function close() {
    if (!modalEl) return;
    renderToken++;                       // cancela cualquier render en curso
    modalEl.classList.remove('open');
    document.body.style.overflow = '';
    setTimeout(() => {
      if (modalEl) modalEl.querySelector('#pdf-modal-pages').innerHTML = '';
      if (currentBlobUrl) { URL.revokeObjectURL(currentBlobUrl); currentBlobUrl = null; }
    }, 300);
  }

  return { open, close };
})();
