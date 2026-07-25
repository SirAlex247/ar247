/* ============================================================
   ARGeoSt — Módulo de Zapatas (frontend)
   Zapata aislada: dimensionamiento geotécnico + diseño estructural.
   Reusa helpers globales de argeost.js: $, $$, toSI, fromSI, toast.
   Entradas en MKS (display) → SI al backend (/api/zapata).
   ============================================================ */
'use strict';

let _zapLast = null;
let _zapLastPayload = null;
let _vista3D_zap = false;

function zReadMag(el) {
  if (!el) return null;
  const v = parseFloat(el.value);
  if (isNaN(v)) return null;
  return el.dataset.mag ? toSI(v, el.dataset.mag) : v;
}

function zapRecolectar() {
  return {
    c1: zReadMag($('#zap_c1')), c2: zReadMag($('#zap_c2')),
    P_servicio: zReadMag($('#zap_P')) || 0,
    M_servicio: zReadMag($('#zap_M')) || 0,
    Pu: zReadMag($('#zap_Pu')) || 0,
    factor_carga: parseFloat($('#zap_fcarga').value) || 1.5,
    q_adm: zReadMag($('#zap_qadm')) || 0,
    Df: zReadMag($('#zap_Df')) || 0,
    gamma_suelo: zReadMag($('#zap_gs')) || 18,
    gamma_concreto: zReadMag($('#zap_gc')) || 24,
    posicion: $('#zap_pos').value,
    fc: zReadMag($('#zap_fc')), fy: zReadMag($('#zap_fy')),
    db: (parseFloat($('#zap_db').value) || 19.05) / 1000.0,   // mm → m
    recubrimiento: zReadMag($('#zap_rec')),
    B: zReadMag($('#zap_B')) || 0,
    L: zReadMag($('#zap_L')) || 0,
    h: zReadMag($('#zap_h')) || 0,
  };
}

async function zapCalcular() {
  const payload = zapRecolectar();
  if (!payload.P_servicio) { toast('Define la carga de servicio P', 'err'); return; }
  if (!payload.q_adm) { toast('Define la capacidad admisible q_adm', 'err'); return; }
  const btn = $('#btn-zap-calc-h');
  const lbl = btn && (btn.querySelector('span') || btn);
  if (btn) btn.disabled = true;
  if (lbl) lbl.textContent = 'Calculando…';
  try {
    const r = await fetch('/api/zapata', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await r.json();
    if (!data.ok) { toast(data.error || 'Error en el cálculo', 'err', 6000); }
    else { _zapLastPayload = payload; _zapLast = data; zapRender(data); zapMostrar(); toast('Cálculo completado', 'ok'); }
  } catch (e) {
    toast('No se pudo conectar con el servidor', 'err');
  } finally {
    if (btn) btn.disabled = false;
    if (lbl) lbl.textContent = 'Calcular';
  }
}

const _ztf = kN => fromSI(kN, 'force');       // kN → tonf
const _ztp = kPa => fromSI(kPa, 'pressure');  // kPa → tonf/m²
const _ztm = kNm => fromSI(kNm, 'moment');    // kN·m → tonf·m

function zapRender(res) {
  const g = res.geometria, geo = res.geotecnico, e = res.estructural;
  const set = (id, v) => { const el = $('#' + id); if (el) el.textContent = v; };
  const asMax = Math.max(e.flexion_L.As_cm2, e.flexion_B.As_cm2);
  set('zk-bl', `${g.B_m}×${g.L_m}`);
  set('zk-h', g.h_m);
  set('zk-d', g.d_m);
  set('zk-q', _ztp(geo.q_max_kPa).toFixed(1));
  set('zk-punz', e.punzonamiento.ratio);
  set('zk-as', asMax.toFixed(1));

  const ok = (b) => b ? '<span style="color:var(--green-300)">cumple</span>'
                      : '<span style="color:var(--status-err-tx)">no cumple</span>';
  const fila = (f, dir) => `
    <tr><td>${dir}</td>
        <td style="text-align:right">${_ztm(f.Mu_kNm).toFixed(2)}</td>
        <td style="text-align:right">${f.As_cm2}${f.gobierna_minimo ? ' <span class="muted">(mín)</span>' : ''}</td>
        <td style="text-align:right">${f.n_barras} Ø${f.db_mm} @ ${f.sep_cm} cm</td></tr>`;

  const avisos = (res.avisos && res.avisos.length)
    ? `<div class="hint" style="border-color:var(--status-warn-bd);color:var(--status-warn-tx)">⚠ ${res.avisos.join('<br>⚠ ')}</div>` : '';

  $('#zap-detalle').innerHTML = `
    <div class="pil-line"><b>Geotecnia:</b> A requerida ${geo.A_req_m2} m² · P total ${_ztf(geo.P_total_servicio_kN).toFixed(1)} tonf ·
      q<sub>máx</sub> ${_ztp(geo.q_max_kPa).toFixed(1)} / q<sub>adm</sub> ${_ztp(geo.q_adm_kPa).toFixed(1)} tonf/m² → ${ok(geo.cumple)} (D/C=${geo.ratio})</div>
    <div class="pil-line"><b>q<sub>u</sub> de diseño:</b> ${_ztp(e.qu_kPa).toFixed(1)} tonf/m² · P<sub>u</sub> ${_ztf(e.Pu_kN).toFixed(1)} tonf</div>
    <div class="pil-line"><b>Punzonamiento (2 vías):</b> V<sub>u</sub>=${_ztf(e.punzonamiento.Vu_kN).toFixed(1)} φV<sub>c</sub>=${_ztf(e.punzonamiento.phiVc_kN).toFixed(1)} tonf (v<sub>c</sub>=${e.punzonamiento.vc_MPa} MPa) → ${ok(e.punzonamiento.cumple)} (D/C=${e.punzonamiento.ratio})</div>
    <div class="pil-line"><b>Cortante 1 vía:</b> dir B → D/C=${e.una_via_L.ratio} ${ok(e.una_via_L.cumple)} · dir L → D/C=${e.una_via_B.ratio} ${ok(e.una_via_B.cumple)}</div>
    <table class="pil-table" style="margin-top:8px">
      <thead><tr><th>Flexión</th><th style="text-align:right">Mu (tonf·m)</th><th style="text-align:right">As (cm²)</th><th style="text-align:right">Refuerzo</th></tr></thead>
      <tbody>${fila(e.flexion_L, 'Dir. B (volado en L)')}${fila(e.flexion_B, 'Dir. L (volado en B)')}</tbody>
    </table>
    ${avisos}`;
}

/* ---------- Esquema: planta + sección (SVG) ---------- */
function zapDibujar(res) {
  const cont = $('#zap-preview');
  if (!cont) return;
  const g = res.geometria, e = res.estructural;
  const B = g.B_m, L = g.L_m, h = g.h_m, c1 = g.c1_m, c2 = g.c2_m;

  const W = 460, H = 520;
  const COL = { bg: '#0d1c16', concrete: '#6f7a83', col: '#9aa6ae',
                soil: '#caa86a', txt: '#eaf2ee', sub: '#9fc0b2', steel: '#e07a3a',
                edge: '#1f262c', arrow: '#e7c46b' };

  // ----- PLANTA (arriba) -----
  const pX0 = 60, pX1 = 300, pY0 = 40, pY1 = 230;
  const sPlan = Math.min((pX1 - pX0) / B, (pY1 - pY0) / L) * 0.85;
  const bw = B * sPlan, bl = L * sPlan;
  const pcx = (pX0 + pX1) / 2, pcy = (pY0 + pY1) / 2;
  const px = pcx - bw / 2, py = pcy - bl / 2;
  const cw = c1 * sPlan, cl = c2 * sPlan;

  let svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${W} ${H}" width="100%" height="100%"
    style="display:block;background:${COL.bg};border-radius:10px;font-family:'Inter',system-ui,sans-serif">
    <defs><marker id="zarr" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto">
      <path d="M0 0 L10 5 L0 10 z" fill="${COL.arrow}"/></marker></defs>
    <text x="${pcx}" y="24" font-size="12" font-weight="700" fill="${COL.txt}" text-anchor="middle">PLANTA</text>`;

  // zapata
  svg += `<rect x="${px.toFixed(1)}" y="${py.toFixed(1)}" width="${bw.toFixed(1)}" height="${bl.toFixed(1)}"
            fill="${COL.concrete}" fill-opacity="0.30" stroke="${COL.concrete}" stroke-width="1.6"/>`;
  // refuerzo (líneas en ambas direcciones)
  const nlx = 7, nly = 7;
  for (let i = 1; i < nlx; i++) {
    const yy = py + bl * i / nlx;
    svg += `<line x1="${(px + 4).toFixed(1)}" y1="${yy.toFixed(1)}" x2="${(px + bw - 4).toFixed(1)}" y2="${yy.toFixed(1)}" stroke="${COL.steel}" stroke-width="0.5" stroke-opacity="0.7"/>`;
  }
  for (let i = 1; i < nly; i++) {
    const xx = px + bw * i / nly;
    svg += `<line x1="${xx.toFixed(1)}" y1="${(py + 4).toFixed(1)}" x2="${xx.toFixed(1)}" y2="${(py + bl - 4).toFixed(1)}" stroke="${COL.steel}" stroke-width="0.5" stroke-opacity="0.5"/>`;
  }
  // columna
  svg += `<rect x="${(pcx - cw / 2).toFixed(1)}" y="${(pcy - cl / 2).toFixed(1)}" width="${cw.toFixed(1)}" height="${cl.toFixed(1)}"
            fill="${COL.col}" stroke="${COL.edge}" stroke-width="1.2"/>`;
  // cotas B (abajo) y L (izquierda)
  svg += `<text x="${pcx}" y="${(py + bl + 18).toFixed(1)}" font-size="11" fill="${COL.txt}" text-anchor="middle">B = ${B.toFixed(2)} m</text>`;
  svg += `<text x="${(px - 12).toFixed(1)}" y="${pcy.toFixed(1)}" font-size="11" fill="${COL.txt}" text-anchor="middle" transform="rotate(-90 ${(px - 12).toFixed(1)} ${pcy.toFixed(1)})">L = ${L.toFixed(2)} m</text>`;
  // etiqueta refuerzo
  svg += `<text x="${pX1 + 14}" y="${pcy - 6}" font-size="10" fill="${COL.steel}">Refuerzo inferior</text>`;
  svg += `<text x="${pX1 + 14}" y="${pcy + 9}" font-size="9.5" fill="${COL.sub}">malla en 2 direcciones</text>`;

  // ----- SECCIÓN (abajo) -----
  const secTitleY = 280;
  svg += `<text x="${W / 2}" y="${secTitleY}" font-size="12" font-weight="700" fill="${COL.txt}" text-anchor="middle">SECCIÓN</text>`;
  const baseY = 470;                       // base de la zapata
  const sSec = Math.min(300 / B, 150 / (h + 0.9)) * 0.9;
  const bwS = B * sSec, hS = h * sSec;
  const scx = W / 2 - 40;
  const sx = scx - bwS / 2;
  const colW = c1 * sSec, colH = Math.max(40, 0.9 * sSec);
  const groundY = baseY - hS - colH * 0.35;     // nivel de terreno aprox

  // suelo (bandas a los lados)
  svg += `<rect x="20" y="${groundY.toFixed(1)}" width="${W - 40}" height="${(baseY - groundY).toFixed(1)}" fill="${COL.soil}" fill-opacity="0.18"/>`;
  svg += `<line x1="20" y1="${groundY.toFixed(1)}" x2="${W - 20}" y2="${groundY.toFixed(1)}" stroke="${COL.soil}" stroke-width="1"/>`;
  // zapata (losa)
  svg += `<rect x="${sx.toFixed(1)}" y="${(baseY - hS).toFixed(1)}" width="${bwS.toFixed(1)}" height="${hS.toFixed(1)}"
            fill="${COL.concrete}" stroke="${COL.edge}" stroke-width="1.6"/>`;
  // columna (arranque)
  svg += `<rect x="${(scx - colW / 2).toFixed(1)}" y="${(baseY - hS - colH).toFixed(1)}" width="${colW.toFixed(1)}" height="${colH.toFixed(1)}"
            fill="${COL.col}" stroke="${COL.edge}" stroke-width="1.2"/>`;
  // refuerzo inferior (línea)
  svg += `<line x1="${(sx + 5).toFixed(1)}" y1="${(baseY - 7).toFixed(1)}" x2="${(sx + bwS - 5).toFixed(1)}" y2="${(baseY - 7).toFixed(1)}" stroke="${COL.steel}" stroke-width="1.6"/>`;
  // presión del suelo (flechas hacia arriba)
  const nq = 6;
  for (let i = 0; i <= nq; i++) {
    const xx = sx + bwS * i / nq;
    svg += `<line x1="${xx.toFixed(1)}" y1="${(baseY + 26).toFixed(1)}" x2="${xx.toFixed(1)}" y2="${(baseY + 4).toFixed(1)}" stroke="${COL.arrow}" stroke-width="1.2" marker-end="url(#zarr)"/>`;
  }
  svg += `<text x="${scx.toFixed(1)}" y="${(baseY + 40).toFixed(1)}" font-size="10" fill="${COL.arrow}" text-anchor="middle">q_u = ${_ztp(e.qu_kPa).toFixed(1)} tonf/m²</text>`;
  // cotas
  svg += `<text x="${scx.toFixed(1)}" y="${(baseY - hS - colH - 8).toFixed(1)}" font-size="10" fill="${COL.txt}" text-anchor="middle">columna ${(c1 * 100).toFixed(0)}×${(c2 * 100).toFixed(0)} cm</text>`;
  svg += `<line x1="${(sx + bwS + 14).toFixed(1)}" y1="${(baseY - hS).toFixed(1)}" x2="${(sx + bwS + 14).toFixed(1)}" y2="${baseY.toFixed(1)}" stroke="${COL.sub}" stroke-width="0.8" marker-start="url(#zarr)" marker-end="url(#zarr)"/>`;
  svg += `<text x="${(sx + bwS + 30).toFixed(1)}" y="${(baseY - hS / 2).toFixed(1)}" font-size="10" fill="${COL.txt}" text-anchor="middle" transform="rotate(90 ${(sx + bwS + 30).toFixed(1)} ${(baseY - hS / 2).toFixed(1)})">h = ${h.toFixed(2)} m</text>`;
  svg += `<text x="${scx.toFixed(1)}" y="${(baseY + 56).toFixed(1)}" font-size="10" fill="${COL.sub}" text-anchor="middle">d = ${g.d_m.toFixed(3)} m</text>`;

  svg += `</svg>`;
  cont.innerHTML = svg;
}

/* ---------- Esquema: 2D (SVG) o 3D en el mismo panel ---------- */
function zapMostrar() {
  const cont = $('#zap-preview');
  if (!cont || !_zapLast) return;
  if (_vista3D_zap && window.ARGeoStFooting3D && ARGeoStFooting3D.isAvailable()) {
    const g = _zapLast.geometria;
    try {
      ARGeoStFooting3D.render({
        B: g.B_m, L: g.L_m, h: g.h_m, c1: g.c1_m, c2: g.c2_m,
        Df: (_zapLastPayload && _zapLastPayload.Df) || 1.5,
      }, cont);
    } catch (e) {
      console.error('[footing3d]', e);
      if (window.ARGeoStFooting3D) ARGeoStFooting3D.dispose();
      zapDibujar(_zapLast);
    }
  } else {
    if (window.ARGeoStFooting3D) ARGeoStFooting3D.dispose();
    zapDibujar(_zapLast);
  }
}

/* Cambia el modo del visor del esquema ('2d' | '3d'). */
function setVistaZap(modo) {
  _vista3D_zap = (modo === '3d');
  $$('[data-vista-zap]').forEach(b =>
    b.classList.toggle('active', b.getAttribute('data-vista-zap') === modo));
  const hint = $('#zap-vista-hint');
  if (hint) hint.style.display = _vista3D_zap ? '' : 'none';
  zapMostrar();
}

/* ---------- Memoria de cálculo (PDF) ---------- */
async function zapGenerarPDF(btn) {
  const payload = zapRecolectar();
  if (!payload.P_servicio) { toast('Define la carga de servicio P', 'err'); return; }
  if (!payload.q_adm) { toast('Define la capacidad admisible q_adm', 'err'); return; }
  const val = id => { const e = $('#' + id); return e ? e.value : ''; };
  payload.proyecto = val('proyecto');
  payload.ingeniero = val('ingeniero');
  payload.ubicacion = val('ubicacion');
  payload.empresa = val('empresa');
  const old = btn ? btn.innerHTML : '';
  if (btn) { btn.disabled = true; btn.textContent = 'Generando…'; }
  try {
    const r = await fetch('/api/zapata_pdf', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!r.ok) { const j = await r.json().catch(() => ({})); toast('Error PDF: ' + (j.error || r.status), 'err', 6000); return; }
    const blob = await r.blob();
    const filename = `ARGeoSt-zapata-${(payload.proyecto || 'memoria').replace(/[^a-z0-9]/gi, '_')}.pdf`;
    if (window.ARGeoStPDFModal) {
      ARGeoStPDFModal.open(blob, filename);
      toast('Memoria generada — usa "Descargar" en el visor', 'ok');
    } else {
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a'); a.href = url; a.download = filename; a.click();
      URL.revokeObjectURL(url);
    }
  } catch (e) {
    toast('No se pudo generar la memoria', 'err', 6000);
  } finally {
    if (btn) { btn.disabled = false; btn.innerHTML = old; }
  }
}

/* ---------- Init ---------- */
document.addEventListener('DOMContentLoaded', () => {
  // Acciones en el header (unificadas por módulo)
  const bCalcH = $('#btn-zap-calc-h');
  if (bCalcH) bCalcH.addEventListener('click', () => { if (typeof showView === 'function') showView('footing'); zapCalcular(); });
  const bPdfH = $('#btn-zap-pdf-h');
  if (bPdfH) bPdfH.addEventListener('click', () => zapGenerarPDF(bPdfH));
  // Botón de la pestaña Memoria
  const bpdf = $('#btn-footing-pdf');
  if (bpdf) bpdf.addEventListener('click', () => zapGenerarPDF(bpdf));
  // Toggle 2D / 3D del esquema
  $$('[data-vista-zap]').forEach(b =>
    b.addEventListener('click', () => setVistaZap(b.getAttribute('data-vista-zap'))));

  window.zapCalcular = zapCalcular;
  window.zapMostrar = zapMostrar;
  window.zapGenerarPDF = zapGenerarPDF;
});
