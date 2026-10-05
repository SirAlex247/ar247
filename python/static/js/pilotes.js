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
    norma: ($('#pil_norma') && $('#pil_norma').value) || 'NSR10',
    tipo_suelo: ($('#pil_tsuelo') && $('#pil_tsuelo').value) || 'arena',
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
    // Solicitaciones estructurales (opcional)
    M_servicio: pilReadMag($('#pil_M')) || 0,
    T_servicio: pilReadMag($('#pil_T')) || 0,
    Lu_libre: pilReadMag($('#pil_Lu')) || 0,
    k_pandeo: parseFloat($('#pil_k') && $('#pil_k').value) || 1.0,
    disipacion: ($('#pil_disip') && $('#pil_disip').value) || 'DMO',
    // Grupo y carga lateral (opcional)
    Mx_servicio: pilReadMag($('#pil_Mx')) || 0,
    My_servicio: pilReadMag($('#pil_My')) || 0,
    H_servicio: pilReadMag($('#pil_H')) || 0,
    s_grupo: pilReadMag($('#pil_sgrp')) || 0,
    tipo_reaccion: ($('#pil_treac') && $('#pil_treac').value) || 'nh',
    nh_suelo: (($('#pil_treac') && $('#pil_treac').value) === 'nh') ? (pilReadMag($('#pil_reac')) || 0) : 0,
    k_suelo: (($('#pil_treac') && $('#pil_treac').value) === 'k') ? (pilReadMag($('#pil_reac')) || 0) : 0,
    cabeza_pilote: ($('#pil_cabeza') && $('#pil_cabeza').value) || 'libre',
    // Análisis p-y (suelo) y downdrag
    gamma_lat: pilReadMag($('#pil_glat')) || 0,
    phi_lat: (($('#pil_treac') && $('#pil_treac').value) === 'nh') ? (parseFloat($('#pil_phicu') && $('#pil_phicu').value) || 0) : 0,
    cu_lat: (($('#pil_treac') && $('#pil_treac').value) === 'k') ? ((parseFloat($('#pil_phicu') && $('#pil_phicu').value) || 0) * 9.80665) : 0,
    eps50: parseFloat($('#pil_eps50') && $('#pil_eps50').value) || 0.01,
    fs_negativa: pilReadMag($('#pil_fsneg')) || 0,
    L_downdrag: pilReadMag($('#pil_ldd')) || 0,
  };
}

const _ptf = kN => fromSI(kN, 'force');       // kN → tonf
const _ptm = kPa => fromSI(kPa, 'pressure');  // kPa → tonf/m²
const _ptMom = kNm => fromSI(kNm, 'moment');  // kN·m → tonf·m

/* Dibuja el diagrama de interacción P-M (φPn vs φMn) con el punto de demanda. */
function pilDiagramaPM(diag, flexo) {
  const pts = (diag && diag.puntos) || [];
  if (!pts.length) return '';
  const W = 340, H = 300, ml = 52, mr = 14, mt = 16, mb = 40;
  const xs = pts.map(p => Math.abs(_ptMom(p.phiMn_kNm)));
  const ys = pts.map(p => _ptf(p.phiPn_kN));
  const muD = _ptMom(flexo.Mu_kNm), puD = _ptf(flexo.Pu_kN);
  const xMax = Math.max(...xs, muD) * 1.15 || 1;
  const yMin = Math.min(...ys, puD, 0), yMax = Math.max(...ys, puD) * 1.08 || 1;
  const px = v => ml + (v / xMax) * (W - ml - mr);
  const py = v => (H - mb) - ((v - yMin) / (yMax - yMin)) * (H - mt - mb);
  const C = { bg: '#0d1c16', curve: '#5fa0d8', grid: '#243', txt: '#cfe3d8', dem: '#e07a3a', sub: '#8fb0a3' };
  let svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${W} ${H}" width="100%" height="100%"
    style="display:block;background:${C.bg};border-radius:10px;font-family:'Inter',system-ui,sans-serif">`;
  // ejes
  svg += `<line x1="${ml}" y1="${py(yMin)}" x2="${W - mr}" y2="${py(yMin)}" stroke="${C.sub}" stroke-width="1"/>`;
  svg += `<line x1="${ml}" y1="${mt}" x2="${ml}" y2="${H - mb}" stroke="${C.sub}" stroke-width="1"/>`;
  if (yMin < 0) svg += `<line x1="${ml}" y1="${py(0)}" x2="${W - mr}" y2="${py(0)}" stroke="${C.grid}" stroke-width="0.8" stroke-dasharray="3 3"/>`;
  // curva
  const path = pts.map((p, i) => `${i ? 'L' : 'M'}${px(Math.abs(_ptMom(p.phiMn_kNm))).toFixed(1)},${py(_ptf(p.phiPn_kN)).toFixed(1)}`).join(' ');
  svg += `<path d="${path}" fill="none" stroke="${C.curve}" stroke-width="2"/>`;
  svg += `<path d="${path}" fill="${C.curve}" fill-opacity="0.10" stroke="none"/>`;
  // punto de demanda
  const inside = flexo.cumple;
  svg += `<circle cx="${px(muD).toFixed(1)}" cy="${py(puD).toFixed(1)}" r="5" fill="${inside ? '#4ade80' : '#ef4444'}" stroke="#fff" stroke-width="1"/>`;
  svg += `<text x="${px(muD).toFixed(1) - 6}" y="${py(puD).toFixed(1) - 8}" font-size="10" fill="${inside ? '#4ade80' : '#ef4444'}" text-anchor="end">(${muD.toFixed(1)}, ${puD.toFixed(0)})</text>`;
  // etiquetas de ejes
  svg += `<text x="${(W) / 2}" y="${H - 8}" font-size="10" fill="${C.txt}" text-anchor="middle">φMn (tonf·m)</text>`;
  svg += `<text x="14" y="${H / 2}" font-size="10" fill="${C.txt}" text-anchor="middle" transform="rotate(-90 14 ${H / 2})">φPn (tonf)</text>`;
  svg += `<text x="${W / 2}" y="12" font-size="10" font-weight="700" fill="${C.txt}" text-anchor="middle">Diagrama de interacción P-M</text>`;
  svg += `</svg>`;
  return svg;
}

/* Muestra/oculta campos y etiquetas según la norma seleccionada. */
function pilAplicarNorma() {
  const n = ($('#pil_norma') && $('#pil_norma').value) || 'NSR10';
  $$('.pil-norma-cond').forEach(el => {
    el.style.display = (el.getAttribute('data-norma') === n) ? '' : 'none';
  });
  const lbl = $('#pk-cap-label');
  if (lbl) lbl.textContent = (n === 'CCP14') ? 'R_r factorada' : 'Q admisible';
  const hint = $('#pil-norma-hint');
  if (hint) hint.innerHTML = (n === 'CCP14')
    ? 'LRFD: R<sub>r</sub> = φ<sub>s</sub>·Q<sub>fuste</sub> + φ<sub>p</sub>·Q<sub>punta</sub> ≥ P<sub>u</sub>. El diseño ajusta L/N° para cumplir.'
    : 'Esfuerzos admisibles: Q<sub>adm</sub> = Q<sub>últ</sub>/FS ≥ carga de servicio por pilote.';
}

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
  const ccp = (res.norma === 'CCP14') || (g.norma === 'CCP14');
  const set = (id, v) => { const el = $('#' + id); if (el) el.textContent = v; };
  set('pk-n', d.N_pilotes);
  set('pk-d', d.D_m.toFixed(2));
  set('pk-l', d.L_m.toFixed(2));
  set('pk-as', e.A_st_cm2.toFixed(1));
  set('pk-phipn', _ptf(e.phiPn_kN).toFixed(1));
  set('pk-qadm', _ptf(ccp ? g.R_r_kN : g.Qadm_kN).toFixed(1));
  const capLbl = $('#pk-cap-label');
  if (capLbl) capLbl.textContent = ccp ? 'R_r factorada' : 'Q admisible';

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

  const geoLine = ccp
    ? `<div class="pil-line"><b>Geotecnia (CCP-14):</b> Q<sub>punta</sub>=${_ptf(g.Qpunta_kN).toFixed(1)} + Q<sub>fuste</sub>=${_ptf(g.Qfuste_kN).toFixed(1)} = Q<sub>últ</sub>=${_ptf(g.Qult_kN).toFixed(1)} tonf →
       R<sub>r</sub>=φ·Q=${_ptf(g.R_r_kN).toFixed(1)} tonf (φ ${g.phi_fuste}/${g.phi_punta}) · P<sub>u</sub>/pilote=${_ptf(g.Pu_pilote_kN).toFixed(1)} · CDR=${g.CDR} → ${ok(g.cumple)}</div>`
    : `<div class="pil-line"><b>Geotecnia (NSR-10):</b> Q<sub>punta</sub>=${_ptf(g.Qpunta_kN).toFixed(1)} + Q<sub>fuste</sub>=${_ptf(g.Qfuste_kN).toFixed(1)} → Q<sub>adm</sub>=${_ptf(g.Qadm_kN).toFixed(1)} tonf (FS=${g.FS}) · P/pilote=${_ptf(g.Pserv_pilote_kN).toFixed(1)} · D/C=${g.ratio} → ${ok(g.cumple)}</div>`;

  $('#pil-detalle').innerHTML = `
    <div class="pil-line"><b>Diseño:</b> ${d.N_pilotes} pilote(s) de Ø${(d.D_m * 100).toFixed(0)} cm · L = ${d.L_m.toFixed(2)} m ${autoTxt ? `<span class="muted">(${autoTxt})</span>` : ''}</div>
    <div class="pil-line"><b>Acero longitudinal:</b> ${e.n_barras} Ø${e.db_long_mm} (${e.A_st_cm2.toFixed(1)} cm², ρ = ${e.cuantia_pct}%) · transversal: ${tr}</div>
    <div class="pil-line"><b>Estructural (axial):</b> φPn = ${_ptf(e.phiPn_kN).toFixed(1)} tonf · Pu/pilote = ${_ptf(e.Pu_pilote_kN).toFixed(1)} tonf · D/C = ${e.ratio} → ${ok(e.cumple)}</div>
    ${_pilLineasEstr(res)}
    ${geoLine}
    <div class="pil-line"><b>Volumen de concreto:</b> ${d.volumen_concreto_m3} m³ (${d.N_pilotes} pilotes)</div>
    ${avisos}`;

  // Diagrama P-M en su tarjeta, si hay momento.
  const fx = e.flexocompresion;
  const pmCard = $('#pil-pm-card'), pmDiag = $('#pil-pm-diagram');
  if (pmCard && pmDiag) {
    if (fx && fx.Mu_kNm > 0.1 && e.diagrama_interaccion) {
      pmCard.style.display = '';
      pmDiag.innerHTML = pilDiagramaPM(e.diagrama_interaccion, fx);
    } else {
      pmCard.style.display = 'none';
      pmDiag.innerHTML = '';
    }
  }
  // Perfiles p-y (deflexión y momento vs profundidad).
  const pyCard = $('#pil-py-card'), pyDiag = $('#pil-py-diagram');
  if (pyCard && pyDiag) {
    if (e.analisis_py && e.analisis_py.aplica) {
      pyCard.style.display = '';
      pyDiag.innerHTML = pilPerfilPY(e.analisis_py);
    } else {
      pyCard.style.display = 'none';
      pyDiag.innerHTML = '';
    }
  }
}

/* Dibuja los perfiles de deflexión y(z) y momento M(z) del análisis p-y. */
function pilPerfilPY(py) {
  if (!py || !py.aplica) return '';
  const z = py.z, M = py.M_kNm, y = py.y_mm;
  const W = 360, H = 320, mt = 22, mb = 30, ml = 42, mr = 14, gap = 30;
  const zmax = z[z.length - 1] || 1;
  const pw = (W - ml - mr - gap) / 2;
  const C = { bg: '#0d1c16', y: '#e07a3a', m: '#5fa0d8', txt: '#cfe3d8', sub: '#8fb0a3', zero: '#243' };
  const pz = v => mt + (v / zmax) * (H - mt - mb);   // profundidad hacia abajo
  function panel(x0, vals, color, title, unit) {
    const vmax = Math.max(Math.abs(Math.min(...vals)), Math.abs(Math.max(...vals))) || 1;
    const cx = x0 + pw / 2;
    const px = v => cx + (v / vmax) * (pw / 2 - 4);
    let s = `<text x="${cx}" y="14" font-size="10" font-weight="700" fill="${color}" text-anchor="middle">${title}</text>`;
    s += `<line x1="${cx}" y1="${mt}" x2="${cx}" y2="${H - mb}" stroke="${C.zero}" stroke-width="0.8" stroke-dasharray="3 3"/>`;
    s += `<line x1="${x0}" y1="${mt}" x2="${x0}" y2="${H - mb}" stroke="${C.sub}" stroke-width="0.8"/>`;
    const path = vals.map((v, i) => `${i ? 'L' : 'M'}${px(v).toFixed(1)},${pz(z[i]).toFixed(1)}`).join(' ');
    s += `<path d="${path}" fill="none" stroke="${color}" stroke-width="1.8"/>`;
    // valor extremo
    let iex = 0; vals.forEach((v, i) => { if (Math.abs(v) > Math.abs(vals[iex])) iex = i; });
    s += `<circle cx="${px(vals[iex]).toFixed(1)}" cy="${pz(z[iex]).toFixed(1)}" r="3.5" fill="${color}"/>`;
    s += `<text x="${cx}" y="${H - 8}" font-size="9" fill="${C.txt}" text-anchor="middle">${unit}</text>`;
    return s;
  }
  let svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${W} ${H}" width="100%" height="100%" style="display:block;background:${C.bg};border-radius:10px;font-family:'Inter',system-ui,sans-serif">`;
  // eje de profundidad (compartido, a la izquierda)
  svg += `<text x="12" y="${H / 2}" font-size="10" fill="${C.sub}" text-anchor="middle" transform="rotate(-90 12 ${H / 2})">profundidad z (m)</text>`;
  [0, Math.round(zmax / 2), Math.round(zmax)].forEach(zz => {
    svg += `<text x="${ml - 4}" y="${pz(zz) + 3}" font-size="8" fill="${C.sub}" text-anchor="end">${zz}</text>`;
  });
  svg += panel(ml, y, C.y, 'Deflexión y', 'mm');
  svg += panel(ml + pw + gap, M, C.m, 'Momento M', 'tonf·m (rel.)');
  svg += `</svg>`;
  return svg;
}

/* Líneas de flexo-compresión, esbeltez, tracción y confinamiento sísmico. */
function _pilLineasEstr(res) {
  const e = res.estructural;
  const ok = (b) => b ? '<span style="color:var(--green-300)">cumple</span>'
                      : '<span style="color:var(--status-err-tx)">no cumple</span>';
  let out = '';
  // Grupo (distribución de la columna a los pilotes)
  const gr = e.grupo;
  if (gr && gr.n > 1 && (Math.abs(gr.P_max_kN - gr.P_min_kN) > 1)) {
    const trac = gr.hay_traccion ? ` · <span style="color:var(--status-err-tx)">TRACCIÓN P<sub>mín</sub>=${_ptf(gr.P_min_kN).toFixed(1)} tonf</span>` : ` · P<sub>mín</sub>=${_ptf(gr.P_min_kN).toFixed(1)} tonf`;
    out += `<div class="pil-line"><b>Grupo (cabezal rígido):</b> ${gr.n} pilotes · P<sub>máx</sub>=${_ptf(gr.P_max_kN).toFixed(1)} tonf${trac}</div>`;
  }
  // Carga lateral — p-y no lineal si aplica, si no la estimación de Broms.
  const py = e.analisis_py, lat = e.carga_lateral;
  if (py && py.aplica) {
    out += `<div class="pil-line"><b>Análisis lateral p-y (no lineal, ${py.tipo}):</b> M<sub>máx</sub>=${_ptMom(py.Mmax_kNm).toFixed(1)} tonf·m a ${py.z_Mmax_m} m · deflexión cabeza = ${py.y0_mm} mm · V<sub>máx</sub>=${_ptf(py.Vmax_kN).toFixed(1)} tonf</div>`;
  } else if (lat && lat.aplica) {
    out += `<div class="pil-line"><b>Carga lateral (${lat.etiqueta}):</b> H=${_ptf(lat.H_kN).toFixed(1)} tonf → M<sub>máx</sub>=${_ptMom(lat.Mmax_kNm).toFixed(1)} tonf·m · deflexión cabeza = ${lat.y0_mm} mm (cabeza ${lat.cabeza})</div>`;
  }
  const fx = e.flexocompresion, esb = e.esbeltez;
  if (fx && fx.Mu_kNm > 0.1) {
    const mc = esb && esb.es_esbelto ? ` (M amplificado a ${_ptMom(esb.Mc_kNm).toFixed(1)} tonf·m por δ<sub>ns</sub>=${esb.delta_ns})` : '';
    out += `<div class="pil-line"><b>Flexo-compresión (P-M):</b> Mu = ${_ptMom(fx.Mu_kNm).toFixed(1)} tonf·m${mc} · φMn disp. = ${_ptMom(fx.phiMn_disponible_kNm).toFixed(1)} tonf·m · relación = ${fx.ratio_interaccion} → ${ok(fx.cumple)}</div>`;
  }
  if (esb) {
    out += esb.es_esbelto
      ? `<div class="pil-line"><b>Esbeltez:</b> kL<sub>u</sub>/r = ${esb.esbeltez_klu_r} > ${esb.limite} → esbelto · P<sub>c</sub> = ${_ptf(esb.Pc_kN || 0).toFixed(1)} tonf · δ<sub>ns</sub> = ${esb.delta_ns}${esb.inestable ? ' <span style="color:var(--status-err-tx)">(inestable)</span>' : ''}</div>`
      : `<div class="pil-line"><b>Esbeltez:</b> kL<sub>u</sub>/r = ${esb.esbeltez_klu_r} ≤ ${esb.limite} → columna corta (sin amplificación)</div>`;
  }
  const tr = e.traccion;
  if (tr && tr.aplica) {
    out += `<div class="pil-line"><b>Tracción / arranque:</b> φTn = ${_ptf(tr.phiTn_kN).toFixed(1)} tonf · Tu = ${_ptf(tr.Tu_kN).toFixed(1)} tonf · D/C = ${tr.ratio} → ${ok(tr.cumple)}</div>`;
  }
  const cv = e.cortante;
  if (cv && cv.Vu_kN > 0.1) {
    out += `<div class="pil-line"><b>Cortante del pilote:</b> Vu = ${_ptf(cv.Vu_kN).toFixed(1)} tonf · φVc = ${_ptf(cv.phiVc_kN).toFixed(1)} · φVn = ${_ptf(cv.phiVn_kN).toFixed(1)} tonf → ${ok(cv.cumple)}${cv.requiere_refuerzo ? ' <span class="muted">(el transversal aporta cortante)</span>' : ''}</div>`;
  }
  const dav = e.pandeo_davisson;
  if (dav && dav.aplica) {
    out += `<div class="pil-line"><b>Pandeo (Davisson):</b> z<sub>fij</sub>=${dav.z_fijacion_m} m · L<sub>e</sub>=${dav.Le_m} m · P<sub>cr</sub>=${_ptf(dav.Pcr_kN).toFixed(1)} tonf · P<sub>adm</sub>=${_ptf(dav.Padm_kN).toFixed(1)} tonf → ${ok(dav.cumple)}</div>`;
  }
  const dd = e.downdrag;
  if (dd && dd.aplica) {
    out += `<div class="pil-line"><b>Fricción negativa (downdrag):</b> Q<sub>n</sub>=${_ptf(dd.Qn_kN).toFixed(1)} tonf se suma a la axial · plano neutro a ${dd.plano_neutro_m} m</div>`;
  }
  if (py && py.aplica && py.z_refuerzo_m) {
    out += `<div class="pil-line"><b>Refuerzo longitudinal:</b> necesario hasta ≈ ${py.z_refuerzo_m} m de profundidad (donde M(z) decae al 10% del máximo)</div>`;
  }
  const cf = e.confinamiento_sismico;
  if (cf) {
    const paso = cf.tipo === 'espiral'
      ? `espiral ρ<sub>s</sub>=${cf.rho_s_confinamiento}, paso ≤ ${(cf.paso_confinado_m * 100).toFixed(0)} cm`
      : `estribos sep ≤ ${(cf.sep_confinada_m * 100).toFixed(0)} cm`;
    out += `<div class="pil-line"><b>Confinamiento sísmico (${cf.disipacion}):</b> zona de rótula L<sub>o</sub> = ${cf.longitud_confinamiento_m} m · ${paso}</div>`;
  }
  return out;
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

  // Selector de norma → muestra/oculta campos
  const selN = $('#pil_norma');
  if (selN) selN.addEventListener('change', pilAplicarNorma);
  pilAplicarNorma();

  window.pilMostrar = pilMostrar;
  window.pilGenerarPDF = pilGenerarPDF;
  window.pilCalcular = pilCalcular;
});
