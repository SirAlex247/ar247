/* ============================================================
   ARGeoSt — Modal de previsualización del PDF
   Crea un modal full-screen con el PDF embebido y botones para
   descargar / cerrar. Funciona con un Blob URL para que el PDF
   se sirva sin disco temporal.
   ============================================================ */
'use strict';

window.ARGeoStPDFModal = (function () {

  let modalEl = null;
  let currentBlobUrl = null;

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
          <iframe id="pdf-modal-iframe" title="PDF"></iframe>
        </div>
      </div>
    `;
    document.body.appendChild(modalEl);

    // Cerrar con click en backdrop o tecla Escape
    modalEl.querySelector('.pdf-modal-backdrop').addEventListener('click', close);
    modalEl.querySelector('#pdf-modal-close').addEventListener('click', close);
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && modalEl.classList.contains('open')) close();
    });

    return modalEl;
  }

  function open(blob, filename) {
    buildModal();
    // Limpiar URL anterior si existe (evita memory leaks)
    if (currentBlobUrl) {
      URL.revokeObjectURL(currentBlobUrl);
      currentBlobUrl = null;
    }
    currentBlobUrl = URL.createObjectURL(blob);
    modalEl.querySelector('#pdf-modal-iframe').src = currentBlobUrl;

    // Botón Descargar
    const dlBtn = modalEl.querySelector('#pdf-modal-download');
    dlBtn.onclick = () => {
      const a = document.createElement('a');
      a.href = currentBlobUrl;
      a.download = filename || 'ARGeoSt-reporte.pdf';
      document.body.appendChild(a);
      a.click();
      a.remove();
    };

    modalEl.classList.add('open');
    document.body.style.overflow = 'hidden';
  }

  function close() {
    if (!modalEl) return;
    modalEl.classList.remove('open');
    document.body.style.overflow = '';
    // Limpiar iframe para liberar memoria
    setTimeout(() => {
      if (modalEl) modalEl.querySelector('#pdf-modal-iframe').src = 'about:blank';
      if (currentBlobUrl) {
        URL.revokeObjectURL(currentBlobUrl);
        currentBlobUrl = null;
      }
    }, 300);
  }

  return { open, close };
})();
