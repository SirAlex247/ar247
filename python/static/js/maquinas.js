/* ============================================================
   CimX — Módulo de Cimentación de máquinas (frontend)
   Bloque dinámico · método de parámetros concentrados (ACI 351.3R).
   Reusa helpers globales de cimx.js: $, $$, toSI, fromSI, toast.
   Entradas en MKS (display) → SI al backend (/api/maquina).
   ============================================================ */
'use strict';

let _maqLast = null;

function _maqMag(el) {
  if (!el) return null;
  const v = parseFloat(el.value);
  if (isNaN(v)) return null;
  return el.dataset.mag ? toSI(v, el.dataset.mag) : v;
}

const _maf = kN => fromSI(kN, 'force');       // kN → tonf
const _map = kPa => fromSI(kPa, 'pressure');  // kPa → tonf/m²
const _mam = kNm => fromSI(kNm, 'moment');    // kN·m → tonf·m
const _maset = (id, v) => { const el = $('#' + id); if (el) el.textContent = v; };
const _maok = (b) => b ? '<span style="color:var(--green-300)">cumple</span>'
                       : '<span style="color:var(--status-err-tx)">no cumple</span>';

function maqRecolectar() {
  const numv = (id, dv) => { const e = $('#' + id); const v = e ? parseFloat(e.value) : NaN; return isNaN(v) ? dv : v; };
  return {
    B: _maqMag($('#maq_B')) || 4, L: _maqMag($('#maq_L')) || 3, h: _maqMag($('#maq_h')) || 1.2,
    gamma_concreto: _maqMag($('#maq_gc')) || 24,
    peso_maquina: _maqMag($('#maq_peso')) || 0,
    rpm: numv('maq_rpm', 1500),
    F0: _maqMag($('#maq_F0')) || 0,
    hcg_maquina: _maqMag($('#maq_hcg')) || 0,
    masa_excentrica_e: numv('maq_mee', 0),
    torque_dinamico: _maqMag($('#maq_torque')) || 0,
    G_suelo: numv('maq_G', 0),
    Vs: numv('maq_Vs', 0),
    nu: numv('maq_nu', 0.33),
    gamma_suelo: _maqMag($('#maq_gs')) || 18,
    q_adm: _maqMag($('#maq_qadm')) || 0,
    amplitud_admisible_um: numv('maq_ampadm', 50),
    // Diseño estructural del bloque (concreto/acero/pernos).
    fc: _maqMag($('#maq_fc')) || 21,
    fy: _maqMag($('#maq_fy')) || 420,
    factor_fatiga: numv('maq_ffat', 2.0),
    n_pernos: numv('maq_npern', 0),
    db_perno: numv('maq_dbpern', 0),
    fy_perno: _maqMag($('#maq_fypern')) || 250,
    embed_perno: _maqMag($('#maq_hefpern')) || 0,
    sep_pernos: _maqMag($('#maq_seppern')) || 0,
    db_refuerzo: numv('maq_dbref', 19.05),
    recubrimiento: _maqMag($('#maq_rec')) || 0.075,
  };
}

async function maqCalcular() {
  const payload = maqRecolectar();
  if (!payload.peso_maquina) { toast('Define el peso de la máquina', 'err'); return; }
  if (!payload.G_suelo && !payload.Vs) { toast('Define G del suelo o Vs', 'err'); return; }
  const btn = $('#btn-maq-calc-h');
  const lbl = btn && (btn.querySelector('span') || btn);
  if (btn) btn.disabled = true;
  if (lbl) lbl.textContent = 'Calculando…';
  try {
    const r = await fetch('/api/maquina', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await r.json();
    if (!data.ok) { toast(data.error || 'Error en el cálculo', 'err', 6000); }
    else { _maqLast = data; maqRender(data); maqDibujar(data); toast('Análisis completado', 'ok'); }
  } catch (e) {
    toast('No se pudo conectar con el servidor', 'err');
  } finally {
    if (btn) btn.disabled = false;
    if (lbl) lbl.textContent = 'Calcular';
  }
}

/* Líneas del diseño estructural del bloque: rigidez, fuerza dinámica de diseño,
   pernos de anclaje y refuerzo mínimo. */
function _maqLineasEstr(e) {
  if (!e) return '';
  const rg = e.rigidez, fd = e.fuerza_diseno, pr = e.pernos, rf = e.refuerzo;
  let h = '';
  if (rg) {
    h += `<div class="pil-line"><b>Bloque rígido:</b> h=${rg.h_m} m ·
      h<sub>mín</sub>=${rg.h_min_m} m · h/L<sub>máx</sub>=${rg.relacion_h_Lmax} →
      ${rg.rigido ? _maok(true) : '<span style="color:var(--status-warn-tx)">verificar rigidez</span>'}
      ${_maok(rg.cumple)}</div>`;
  }
  if (fd) {
    h += `<div class="pil-line"><b>Fuerza dinámica de diseño</b> (fatiga ×${fd.factor_fatiga}):
      F<sub>d</sub>=${_maf(fd.F_dinamica_diseno_kN).toFixed(2)} tonf ·
      M<sub>vuelco</sub>=${_mam(fd.M_vuelco_diseno_kNm).toFixed(2)} tonf·m</div>`;
  }
  if (pr && pr.aplica) {
    h += `<div class="pil-line"><b>Pernos de anclaje:</b> ${pr.n} Ø${pr.db_mm} mm (h<sub>ef</sub>=${pr.hef_m} m) ·
      T=${_maf(pr.T_perno_kN).toFixed(1)}/φN<sub>sa</sub>=${_maf(pr.phiNsa_kN).toFixed(1)} ·
      V=${_maf(pr.V_perno_kN).toFixed(1)}/φV<sub>sa</sub>=${_maf(pr.phiVsa_kN).toFixed(1)} tonf ·
      interacción=${pr.interaccion} → ${_maok(pr.cumple_acero)}</div>
      <div class="pil-line" style="opacity:.85">Rotura del concreto (breakout): φN<sub>cb</sub>=${_maf(pr.phiNcb_kN).toFixed(1)} tonf → ${_maok(pr.cumple_breakout)}</div>`;
  }
  if (rf) {
    h += `<div class="pil-line"><b>Refuerzo mínimo</b> (ρ=${rf.rho}, cada cara): dir. B →
      ${rf.dir_B.n_barras_cara} Ø${rf.db_mm} mm @ ${rf.dir_B.sep_cm} cm · dir. L →
      ${rf.dir_L.n_barras_cara} Ø${rf.db_mm} mm @ ${rf.dir_L.sep_cm} cm · ${rf.acero_kg_m3} kg/m³</div>`;
  }
  return h;
}

function maqRender(res) {
  const ms = res.masas, ex = res.excitacion, geo = res.geotecnico;
  _maset('mk-peso', _maf(ms.peso_total_kN).toFixed(1));
  _maset('mk-relmasa', ms.relacion_masa_bloque_maquina.toFixed(1) + '×');
  _maset('mk-fop', ex.f_operacion_Hz.toFixed(1));
  _maset('mk-amp', res.amplitud_max_um.toFixed(1));
  _maset('mk-reson', res.resonancia_ok ? '✓ OK' : '✗ resonancia');
  _maset('mk-q', _map(geo.q_estatica_kPa).toFixed(1));

  const filas = res.modos.map(m => {
    const sepColor = (m.excitado === false) ? 'var(--text-muted)'
                   : (m.separado ? 'var(--green-300)' : 'var(--status-err-tx)');
    const sep = `<span style="color:${sepColor}">${m.estado_resonancia}</span>`;
    const amp = m.amplitud_ok ? `${m.amplitud_um.toFixed(2)}` : `<span style="color:var(--status-err-tx)">${m.amplitud_um.toFixed(2)}</span>`;
    return `<tr><td>${m.nombre}</td><td style="text-align:right">${m.fn_Hz.toFixed(2)}</td>
      <td style="text-align:right">${m.amortiguamiento_D.toFixed(3)}</td>
      <td style="text-align:right">${m.razon_frec.toFixed(2)}</td>
      <td style="text-align:right">${amp}</td><td style="text-align:right">${sep}</td></tr>`;
  }).join('');

  const avisos = (res.avisos && res.avisos.length)
    ? `<div class="hint" style="border-color:var(--status-warn-bd);color:var(--status-warn-tx)">⚠ ${res.avisos.join('<br>⚠ ')}</div>` : '';

  $('#maquina-detalle').innerHTML = `
    <div class="pil-line"><b>Bloque</b> ${res.geometria.B_m}×${res.geometria.L_m}×${res.geometria.h_m} m ·
      peso total ${_maf(ms.peso_total_kN).toFixed(1)} tonf · G=${res.suelo.G_MPa} MPa (Vs=${res.suelo.Vs_m_s} m/s)</div>
    <div class="pil-line"><b>Operación:</b> ${ex.rpm} rpm = ${ex.f_operacion_Hz.toFixed(2)} Hz · F₀=${_maf(ex.F0_kN).toFixed(2)} tonf</div>
    <table class="pil-table" style="margin-top:8px">
      <thead><tr><th>Modo</th><th style="text-align:right">fₙ (Hz)</th><th style="text-align:right">D</th>
      <th style="text-align:right">f/fₙ</th><th style="text-align:right">amp (µm)</th><th style="text-align:right">sintonización</th></tr></thead>
      <tbody>${filas}</tbody>
    </table>
    <div class="pil-line" style="margin-top:8px"><b>Amplitud máx</b> ${res.amplitud_max_um.toFixed(1)} / ${res.amplitud_admisible_um.toFixed(0)} µm → ${_maok(res.amplitud_ok)} ·
      <b>resonancia</b> ${_maok(res.resonancia_ok)} · <b>presión</b> ${_maok(geo.cumple)}</div>
    <div style="margin-top:10px;padding-top:8px;border-top:1px solid var(--border)"><b style="color:var(--green-300)">Diseño estructural del bloque</b></div>
    ${_maqLineasEstr(res.estructural)}
    ${avisos}`;
}

/* ---------- Esquema: barras de fn vs f_op (SVG) ---------- */
function maqDibujar(res) {
  const cont = $('#maquina-preview');
  if (!cont) return;
  const modos = res.modos, fop = res.excitacion.f_operacion_Hz;
  const C = { bg: '#0d1c16', ok: '#3f9b6d', bad: '#d0603a', off: '#4a5a52', op: '#5aa9e6', txt: '#eaf2ee', grid: '#24382e', band: '#7a4a4a' };
  const W = 460, H = 340, mL = 44, mR = 20, mT = 40, mB = 46;
  const fnMax = Math.max(fop, ...modos.map(m => m.fn_Hz)) * 1.18;
  const plotW = W - mL - mR, plotH = H - mT - mB;
  const Y = f => mT + plotH * (1 - f / fnMax);
  const n = modos.length, bw = plotW / n * 0.5;

  let svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${W} ${H}" width="100%" height="100%"
    style="display:block;background:${C.bg};border-radius:10px;font-family:'Inter',system-ui,sans-serif">
    <text x="${W/2}" y="22" font-size="12" font-weight="700" fill="${C.txt}" text-anchor="middle">SINTONIZACIÓN — fₙ vs f_operación</text>`;
  // ejes y grilla
  for (let g = 0; g <= 4; g++) {
    const fv = fnMax * g / 4, yy = Y(fv);
    svg += `<line x1="${mL}" y1="${yy.toFixed(1)}" x2="${W-mR}" y2="${yy.toFixed(1)}" stroke="${C.grid}" stroke-width="0.6"/>`;
    svg += `<text x="${mL-6}" y="${(yy+3).toFixed(1)}" font-size="8.5" fill="${C.txt}" text-anchor="end">${fv.toFixed(0)}</text>`;
  }
  svg += `<text x="12" y="${mT+plotH/2}" font-size="9" fill="${C.txt}" text-anchor="middle" transform="rotate(-90 12 ${mT+plotH/2})">frecuencia [Hz]</text>`;
  // barras
  modos.forEach((m, i) => {
    const cx = mL + plotW * (i + 0.5) / n;
    const yTop = Y(m.fn_Hz), yBase = Y(0);
    // banda de resonancia ±20%
    svg += `<rect x="${(cx-bw/2-2).toFixed(1)}" y="${Y(1.2*m.fn_Hz).toFixed(1)}" width="${(bw+4).toFixed(1)}" height="${(Y(0.8*m.fn_Hz)-Y(1.2*m.fn_Hz)).toFixed(1)}" fill="${C.band}" opacity="0.20"/>`;
    const barColor = (m.excitado === false) ? C.off : (m.separado ? C.ok : C.bad);
    svg += `<rect x="${(cx-bw/2).toFixed(1)}" y="${yTop.toFixed(1)}" width="${bw.toFixed(1)}" height="${(yBase-yTop).toFixed(1)}" fill="${barColor}" rx="2"/>`;
    svg += `<text x="${cx.toFixed(1)}" y="${(yTop-5).toFixed(1)}" font-size="8.5" font-weight="700" fill="${C.txt}" text-anchor="middle">${m.fn_Hz.toFixed(1)}</text>`;
    svg += `<text x="${cx.toFixed(1)}" y="${(H-mB+16).toFixed(1)}" font-size="8.5" fill="${C.txt}" text-anchor="middle">${m.nombre.split(' (')[0]}</text>`;
  });
  // línea de operación
  const yop = Y(fop);
  svg += `<line x1="${mL}" y1="${yop.toFixed(1)}" x2="${W-mR}" y2="${yop.toFixed(1)}" stroke="${C.op}" stroke-width="1.6" stroke-dasharray="6 3"/>`;
  svg += `<text x="${W-mR}" y="${(yop-4).toFixed(1)}" font-size="9" font-weight="700" fill="${C.op}" text-anchor="end">f_op = ${fop.toFixed(1)} Hz</text>`;
  svg += `</svg>`;
  cont.innerHTML = svg;
}

/* ---------- Memoria (PDF) ---------- */
async function maqGenerarPDF(btn) {
  const payload = maqRecolectar();
  if (!payload.peso_maquina) { toast('Define el peso de la máquina', 'err'); return; }
  if (!payload.G_suelo && !payload.Vs) { toast('Define G del suelo o Vs', 'err'); return; }
  const val = id => { const e = $('#' + id); return e ? e.value : ''; };
  payload.proyecto = val('proyecto'); payload.ingeniero = val('ingeniero');
  payload.ubicacion = val('ubicacion'); payload.empresa = val('empresa');
  const old = btn ? btn.innerHTML : '';
  if (btn) { btn.disabled = true; btn.textContent = 'Generando…'; }
  try {
    const r = await fetch('/api/maquina_pdf', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!r.ok) { const j = await r.json().catch(() => ({})); toast('Error PDF: ' + (j.error || r.status), 'err', 6000); return; }
    const blob = await r.blob();
    const filename = `CimX-maquina-${(payload.proyecto || 'memoria').replace(/[^a-z0-9]/gi, '_')}.pdf`;
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
  const bCalc = $('#btn-maq-calc-h');
  if (bCalc) bCalc.addEventListener('click', () => { if (typeof showView === 'function') showView('maquina'); maqCalcular(); });
  const bPdf = $('#btn-maq-pdf-h');
  if (bPdf) bPdf.addEventListener('click', () => maqGenerarPDF(bPdf));
  const bPdf2 = $('#btn-maq-pdf-2');
  if (bPdf2) bPdf2.addEventListener('click', () => maqGenerarPDF(bPdf2));

  window.maqCalcular = maqCalcular;
  window.maqGenerarPDF = maqGenerarPDF;
});
