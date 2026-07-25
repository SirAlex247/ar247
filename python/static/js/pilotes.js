/* ============================================================
   CimX — Módulo de Pilotes (diseño estructural)
   La geotecnia (f_s, q_p, FS) es dato de entrada; el módulo calcula
   diámetro, número de pilotes, longitud y acero longitudinal.
   Reusa helpers globales de cimx.js: $, $$, toSI, fromSI, toast.
   Entradas en MKS (display) → SI al backend (/api/pilote_diseno).
   ============================================================ */
'use strict';

let _pilLast = null;
let _pilLastPayload = null;
let _vista3D_pil = false;

function pilReadMag(el) {
  if (!el) return null;
  const v = parseFloat(el.value);
  if (isNaN(v)) return null;
  return el.dataset.mag ? toSI(v, el.dataset.mag) : v;
}

function pilRecolectar() {
  return {
    P_servicio: pilReadMag($('#pil_P')) || 0,
    factor_carga: parseFloat($('#pil_fcarga').value) || 1.5,
    f_s: pilReadMag($('#pil_fs')) || 0,
    q_p: pilReadMag($('#pil_qp')) || 0,
    FS: parseFloat($('#pil_FS').value) || 2.5,
    fc: pilReadMag($('#pil_fc')),
    fy: pilReadMag($('#pil_fy')),
    cuantia: (parseFloat($('#pil_rho').value) || 1.0) / 100.0,
    tipo_refuerzo: $('#pil_tiporef').value,
    db_long: (parseFloat($('#pil_dblong').value) || 19.05) / 1000.0,
    db_trans: (parseFloat($('#pil_dbtrans').value) || 9.53) / 1000.0,
    recubrimiento: pilReadMag($('#pil_rec')),
    D: pilReadMag($('#pil_D')) || 0,
    N: parseInt($('#pil_N').value) || 0,
    L_max: pilReadMag($('#pil_Lmax')) || 25,
  };
}

const _ptf = kN => fromSI(kN, 'force');       // kN → tonf
const _ptm = kPa => fromSI(kPa, 'pressure');  // kPa → tonf/m²

async function pilCalcular() {
  const payload = pilRecolectar();
  if (!payload.P_servicio) { toast('Define la carga de servicio P', 'err'); return; }
  if (!payload.f_s && !payload.q_p) { toast('Define la geotecnia (f_s y/o q_p)', 'err'); return; }
  const btn = $('#btn-pile-calc-h');
  const lbl = btn && (btn.querySelector('span') || btn);
  if (btn) btn.disabled = true;
  if (lbl) lbl.textContent = 'Calculando…';
  try {
    const r = await fetch('/api/pilote_diseno', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await r.json();
    if (!data.ok) { toast(data.error || 'Error en el cálculo', 'err', 6000); }
    else { _pilLastPayload = payload; _pilLast = data; pilRender(data); pilMostrar(); toast('Diseño calculado', 'ok'); }
  } catch (e) {
    toast('No se pudo conectar con el servidor', 'err');
  } finally {
    if (btn) btn.disabled = false;
    if (lbl) lbl.textContent = 'Calcular';
  }
}

function pilRender(res) {
  const d = res.diseno, e = res.estructural, g = res.geotecnia;
  const set = (id, v) => { const el = $('#' + id); if (el) el.textContent = v; };
  set('pk-n', d.N_pilotes);
  set('pk-d', d.D_m.toFixed(2));
  set('pk-l', d.L_m.toFixed(2));
  set('pk-as', e.A_st_cm2.toFixed(1));
  set('pk-phipn', _ptf(e.phiPn_kN).toFixed(1));
  set('pk-qadm', _ptf(g.Qadm_kN).toFixed(1));

  const ok = (b) => b ? '<span style="color:var(--green-300)">cumple</span>'
                      : '<span style="color:var(--status-err-tx)">no cumple</span>';
  const tr = e.transversal.tipo === 'espiral'
    ? `espiral paso ≤ ${(e.transversal.paso_m * 100).toFixed(0)} cm`
    : `estribos sep ≤ ${(e.transversal.sep_max_m * 100).toFixed(0)} cm`;
  let autoTxt = '';
  if (d.auto_D && d.auto_N) autoTxt = 'D y N° automáticos';
  else if (d.auto_D) autoTxt = 'D automático';
  else if (d.auto_N) autoTxt = 'N° automático';

  const avisos = (res.avisos && res.avisos.length)
    ? `<div class="hint" style="border-color:var(--status-warn-bd);color:var(--status-warn-tx)">⚠ ${res.avisos.join('<br>⚠ ')}</div>` : '';

  $('#pil-detalle').innerHTML = `
    <div class="pil-line"><b>Diseño:</b> ${d.N_pilotes} pilote(s) de Ø${(d.D_m * 100).toFixed(0)} cm · L = ${d.L_m.toFixed(2)} m ${autoTxt ? `<span class="muted">(${autoTxt})</span>` : ''}</div>
    <div class="pil-line"><b>Acero longitudinal:</b> ${e.n_barras} Ø${e.db_long_mm} (${e.A_st_cm2.toFixed(1)} cm², ρ = ${e.cuantia_pct}%) · transversal: ${tr}</div>
    <div class="pil-line"><b>Estructural:</b> φPn = ${_ptf(e.phiPn_kN).toFixed(1)} tonf · Pu/pilote = ${_ptf(e.Pu_pilote_kN).toFixed(1)} tonf · D/C = ${e.ratio} → ${ok(e.cumple)}</div>
    <div class="pil-line"><b>Geotecnia:</b> Q<sub>punta</sub>=${_ptf(g.Qpunta_kN).toFixed(1)} + Q<sub>fuste</sub>=${_ptf(g.Qfuste_kN).toFixed(1)} → Q<sub>adm</sub>=${_ptf(g.Qadm_kN).toFixed(1)} tonf · P/pilote=${_ptf(g.Pserv_pilote_kN).toFixed(1)} · D/C=${g.ratio} → ${ok(g.cumple)}</div>
    <div class="pil-line"><b>Volumen de concreto:</b> ${d.volumen_concreto_m3} m³ (${d.N_pilotes} pilotes)</div>
    ${avisos}`;
}

/* ---------- Esquema 2D: elevación + sección ---------- */
function pilDibujar(res) {
  const cont = $('#pil-preview');
  if (!cont) return;
  const d = res.diseno, e = res.estructural;
  const D = d.D_m, L = d.L_m, N = d.N_pilotes, nb = e.n_barras;
  const C = { bg: '#0d1c16', pile: '#5a6b8c', soil: '#caa867', txt: '#eaf2ee',
              sub: '#9fc0b2', steel: '#e07a3a', edge: '#1f262c' };
  const W = 460, H = 470;

  // elevación (izquierda)
  const exC = 150, topY = 56, botY = 410;
  const pH = botY - topY;
  const pW = Math.max(26, Math.min(60, 60 * D));      // ancho visual del pilote
  const soilW = 150;

  let svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${W} ${H}" width="100%" height="100%"
    style="display:block;background:${C.bg};border-radius:10px;font-family:'Inter',system-ui,sans-serif">
    <defs><marker id="parr" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0 0 L10 5 L0 10 z" fill="${C.sub}"/></marker></defs>
    <text x="${exC}" y="26" font-size="11" font-weight="700" fill="${C.txt}" text-anchor="middle">ELEVACIÓN</text>`;

  // suelo
  svg += `<rect x="${exC - soilW / 2}" y="${topY}" width="${soilW}" height="${pH}" fill="${C.soil}" fill-opacity="0.22"/>`;
  svg += `<line x1="${exC - soilW / 2}" y1="${topY}" x2="${exC + soilW / 2}" y2="${topY}" stroke="#7a6a3a" stroke-width="1.2"/>`;
  svg += `<text x="${exC - soilW / 2 + 4}" y="${topY - 4}" font-size="9" fill="#b9a978">N.T.</text>`;
  // pilote
  svg += `<rect x="${exC - pW / 2}" y="${topY}" width="${pW}" height="${pH}" fill="${C.pile}" stroke="${C.edge}" stroke-width="1.3"/>`;
  // barras long + espiral
  svg += `<line x1="${exC - pW / 2 + 5}" y1="${topY + 6}" x2="${exC - pW / 2 + 5}" y2="${botY - 6}" stroke="${C.steel}" stroke-width="1.6"/>`;
  svg += `<line x1="${exC + pW / 2 - 5}" y1="${topY + 6}" x2="${exC + pW / 2 - 5}" y2="${botY - 6}" stroke="${C.steel}" stroke-width="1.6"/>`;
  const nlin = Math.max(6, Math.round(L));
  for (let i = 0; i <= nlin; i++) {
    const y = topY + pH * i / nlin;
    svg += `<line x1="${exC - pW / 2 + 4}" y1="${y.toFixed(1)}" x2="${exC + pW / 2 - 4}" y2="${y.toFixed(1)}" stroke="${C.steel}" stroke-width="0.5" stroke-opacity="0.65"/>`;
  }
  // cotas
  svg += `<line x1="${exC + soilW / 2 + 14}" y1="${topY}" x2="${exC + soilW / 2 + 14}" y2="${botY}" stroke="${C.sub}" stroke-width="0.8" marker-start="url(#parr)" marker-end="url(#parr)"/>`;
  svg += `<text x="${exC + soilW / 2 + 30}" y="${(topY + botY) / 2}" font-size="10" fill="${C.txt}" text-anchor="middle" transform="rotate(90 ${exC + soilW / 2 + 30} ${(topY + botY) / 2})">L = ${L.toFixed(2)} m</text>`;
  svg += `<line x1="${exC - pW / 2}" y1="${topY - 12}" x2="${exC + pW / 2}" y2="${topY - 12}" stroke="${C.sub}" stroke-width="0.8" marker-start="url(#parr)" marker-end="url(#parr)"/>`;
  svg += `<text x="${exC}" y="${topY - 16}" font-size="10" fill="${C.txt}" text-anchor="middle">D = ${(D * 100).toFixed(0)} cm</text>`;

  // sección (derecha)
  const scx = 370, scy = 200, rsec = 70 * 0.5 + 40;   // radio visual fijo ~75
  const Rv = 74;
  svg += `<text x="${scx}" y="26" font-size="11" font-weight="700" fill="${C.txt}" text-anchor="middle">SECCIÓN</text>`;
  svg += `<circle cx="${scx}" cy="${scy}" r="${Rv}" fill="${C.pile}" stroke="${C.edge}" stroke-width="1.4"/>`;
  const rb = Rv - 14;
  svg += `<circle cx="${scx}" cy="${scy}" r="${rb}" fill="none" stroke="${C.steel}" stroke-width="0.9" stroke-dasharray="4 3"/>`;
  for (let i = 0; i < nb; i++) {
    const a = 2 * Math.PI * i / nb - Math.PI / 2;
    svg += `<circle cx="${(scx + rb * Math.cos(a)).toFixed(1)}" cy="${(scy + rb * Math.sin(a)).toFixed(1)}" r="3.4" fill="${C.steel}" stroke="#7a3a10" stroke-width="0.6"/>`;
  }
  svg += `<text x="${scx}" y="${scy + Rv + 22}" font-size="10" fill="${C.txt}" text-anchor="middle">${nb} Ø${e.db_long_mm} · ρ=${e.cuantia_pct}%</text>`;
  svg += `<text x="${scx}" y="${scy + Rv + 40}" font-size="11" fill="${C.sub}" text-anchor="middle" font-weight="700">${N} pilote(s)</text>`;

  svg += `</svg>`;
  cont.innerHTML = svg;
}

/* ---------- Esquema: 2D (SVG) o 3D en el mismo panel ---------- */
function pilMostrar() {
  const cont = $('#pil-preview');
  if (!cont || !_pilLast) return;
  const d = _pilLast.diseno;
  if (_vista3D_pil && window.CimXPile3D && CimXPile3D.isAvailable()) {
    try {
      CimXPile3D.render({ D: d.D_m, L: d.L_m, N: d.N_pilotes }, cont);
    } catch (e) {
      console.error('[pile3d]', e);
      if (window.CimXPile3D) CimXPile3D.dispose();
      pilDibujar(_pilLast);
    }
  } else {
    if (window.CimXPile3D) CimXPile3D.dispose();
    pilDibujar(_pilLast);
  }
}

function setVistaPile(modo) {
  _vista3D_pil = (modo === '3d');
  $$('[data-vista-pile]').forEach(b =>
    b.classList.toggle('active', b.getAttribute('data-vista-pile') === modo));
  const hint = $('#pile-vista-hint');
  if (hint) hint.style.display = _vista3D_pil ? '' : 'none';
  pilMostrar();
}

/* ---------- Memoria de cálculo (PDF) ---------- */
async function pilGenerarPDF(btn) {
  const payload = pilRecolectar();
  if (!payload.P_servicio) { toast('Define la carga de servicio P', 'err'); return; }
  const val = id => { const e = $('#' + id); return e ? e.value : ''; };
  payload.proyecto = val('proyecto');
  payload.ingeniero = val('ingeniero');
  payload.ubicacion = val('ubicacion');
  payload.empresa = val('empresa');
  const old = btn ? btn.innerHTML : '';
  if (btn) { btn.disabled = true; btn.textContent = 'Generando…'; }
  try {
    const r = await fetch('/api/pilote_diseno_pdf', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!r.ok) { const j = await r.json().catch(() => ({})); toast('Error PDF: ' + (j.error || r.status), 'err', 6000); return; }
    const blob = await r.blob();
    const filename = `CimX-pilotes-${(payload.proyecto || 'memoria').replace(/[^a-z0-9]/gi, '_')}.pdf`;
    if (window.CimXPDFModal) { CimXPDFModal.open(blob, filename); toast('Memoria generada', 'ok'); }
    else { const url = URL.createObjectURL(blob); const a = document.createElement('a'); a.href = url; a.download = filename; a.click(); URL.revokeObjectURL(url); }
  } catch (e) {
    toast('No se pudo generar la memoria', 'err', 6000);
  } finally {
    if (btn) { btn.disabled = false; btn.innerHTML = old; }
  }
}

/* ---------- Init ---------- */
document.addEventListener('DOMContentLoaded', () => {
  const bCalcH = $('#btn-pile-calc-h');
  if (bCalcH) bCalcH.addEventListener('click', () => { if (typeof showView === 'function') showView('piles'); pilCalcular(); });
  const bPdfH = $('#btn-pile-pdf-h');
  if (bPdfH) bPdfH.addEventListener('click', () => pilGenerarPDF(bPdfH));
  ['#btn-pile-pdf', '#btn-pile-pdf-2'].forEach(sel => {
    const b = $(sel);
    if (b) b.addEventListener('click', () => pilGenerarPDF(b));
  });

  // Toggle 2D / 3D del esquema
  $$('[data-vista-pile]').forEach(b =>
    b.addEventListener('click', () => setVistaPile(b.getAttribute('data-vista-pile'))));

  window.pilMostrar = pilMostrar;
  window.pilGenerarPDF = pilGenerarPDF;
  window.pilCalcular = pilCalcular;
});
