/* ============================================================
   CimX — Módulo de Caissons / pilas excavadas (frontend)
   Pila de gran diámetro: capacidad axial (β/α) + estructural, norma elegible.
   Reusa helpers globales de cimx.js: $, $$, toSI, fromSI, toast.
   Entradas en MKS (display) → SI al backend (/api/caisson).
   ============================================================ */
'use strict';

let _caiLast = null;
let _caiLastPayload = null;

const _catf = kN => fromSI(kN, 'force');       // kN → tonf
const _catp = kPa => fromSI(kPa, 'pressure');  // kPa → tonf/m²
const _caset = (id, v) => { const el = $('#' + id); if (el) el.textContent = v; };
const _caok = (b) => b ? '<span style="color:var(--green-300)">cumple</span>'
                       : '<span style="color:var(--status-err-tx)">no cumple</span>';

function _caiMag(el) {
  if (!el) return null;
  const v = parseFloat(el.value);
  if (isNaN(v)) return null;
  return el.dataset.mag ? toSI(v, el.dataset.mag) : v;
}

/* ---------- Perfil de suelo (tabla dinámica) ---------- */
function _caiFilaEstrato(e) {
  e = e || { tipo: 'arena', esp: 5, phi: 32, cu: 5, gam: 1.9 };
  const tr = document.createElement('tr');
  tr.innerHTML = `
    <td><select class="input cai-e-tipo" style="min-width:92px">
      <option value="arena">Arena</option><option value="arcilla">Arcilla</option></select></td>
    <td><input type="number" class="input cai-e-esp" style="width:78px" value="${e.esp}" step="0.5"></td>
    <td><input type="number" class="input cai-e-phi" style="width:70px" value="${e.phi}" step="1"></td>
    <td><input type="number" class="input cai-e-cu" style="width:78px" value="${e.cu}" step="0.5"></td>
    <td><input type="number" class="input cai-e-gam" style="width:74px" value="${e.gam}" step="0.05"></td>
    <td><button type="button" class="cai-e-del" title="Quitar" style="background:none;border:none;color:var(--status-err-tx);cursor:pointer;font-size:15px">✕</button></td>`;
  tr.querySelector('.cai-e-tipo').value = e.tipo;
  const sync = () => {
    const arc = tr.querySelector('.cai-e-tipo').value === 'arcilla';
    tr.querySelector('.cai-e-phi').disabled = arc;
    tr.querySelector('.cai-e-cu').disabled = !arc;
    tr.querySelector('.cai-e-phi').style.opacity = arc ? 0.35 : 1;
    tr.querySelector('.cai-e-cu').style.opacity = arc ? 1 : 0.35;
  };
  tr.querySelector('.cai-e-tipo').addEventListener('change', sync);
  tr.querySelector('.cai-e-del').addEventListener('click', () => {
    if ($('#cai-estratos').children.length > 1) tr.remove();
    else toast('Debe quedar al menos un estrato', 'err');
  });
  sync();
  return tr;
}

function caiSeedEstratos() {
  const body = $('#cai-estratos');
  if (!body || body.children.length) return;
  [{ tipo: 'arcilla', esp: 5, phi: 30, cu: 6, gam: 1.85 },
   { tipo: 'arena', esp: 12, phi: 36, cu: 5, gam: 1.95 }].forEach(e => body.appendChild(_caiFilaEstrato(e)));
}

function caiLeerEstratos() {
  const out = [];
  $$('#cai-estratos tr').forEach(tr => {
    const g = sel => tr.querySelector(sel);
    const esp = parseFloat(g('.cai-e-esp').value);
    if (isNaN(esp) || esp <= 0) return;
    out.push({
      tipo: g('.cai-e-tipo').value,
      espesor: esp,                                   // m
      phi: parseFloat(g('.cai-e-phi').value) || 30,   // grados
      cu: toSI(parseFloat(g('.cai-e-cu').value) || 0, 'pressure'),   // tonf/m² → kPa
      gamma: toSI(parseFloat(g('.cai-e-gam').value) || 1.9, 'gamma'),// tonf/m³ → kN/m³
      gamma_sat: toSI(parseFloat(g('.cai-e-gam').value) || 1.9, 'gamma'),
    });
  });
  return out;
}

/* ---------- Norma (campos condicionales) ---------- */
function caiAplicarNorma() {
  const n = ($('#cai_norma') && $('#cai_norma').value) || 'NSR10';
  $$('.cai-norma-cond').forEach(el => {
    el.style.display = (el.getAttribute('data-norma') === n) ? '' : 'none';
  });
  const badge = $('#cai-norma-badge');
  if (badge) badge.textContent = (n === 'CCP14') ? 'CCP-14 · LRFD' : 'NSR-10 · ASD';
  const hint = $('#cai-norma-hint');
  if (hint) hint.innerHTML = (n === 'CCP14')
    ? 'LRFD: R<sub>r</sub> = φ·Q (φ 0.55/0.45 fuste, 0.50/0.40 punta) ≥ carga mayorada P<sub>u</sub>.'
    : 'Esfuerzos admisibles: Q<sub>adm</sub> = Q<sub>últ</sub>/FS ≥ carga de servicio.';
  const capLbl = $('#ck-cap-label');
  if (capLbl) capLbl.textContent = (n === 'CCP14') ? 'R_r factorada' : 'Q admisible';
}

function caiRecolectar() {
  const numv = (id, dv) => { const e = $('#' + id); const v = e ? parseFloat(e.value) : NaN; return isNaN(v) ? dv : v; };
  const chk = (id) => { const e = $('#' + id); return e ? e.checked : false; };
  return {
    norma: ($('#cai_norma') && $('#cai_norma').value) || 'NSR10',
    D: _caiMag($('#cai_D')) || 1.0,
    L: _caiMag($('#cai_L')) || 0,
    L_auto: chk('cai_Lauto'),
    D_campana: _caiMag($('#cai_Dcamp')) || 0,
    altura_campana: _caiMag($('#cai_hcamp')) || 0,
    P_servicio: _caiMag($('#cai_P')) || 0,
    Pu: _caiMag($('#cai_Pu')) || 0,
    FS: numv('cai_FS', 3.0),
    factor_carga: numv('cai_fcarga', 1.6),
    nivel_freatico: _caiMag($('#cai_nf')) || 100,
    estratos: caiLeerEstratos(),
    fc: _caiMag($('#cai_fc')), fy: _caiMag($('#cai_fy')),
    cuantia: numv('cai_rho', 0.01),
    tipo_refuerzo: ($('#cai_reftr') && $('#cai_reftr').value) || 'espiral',
    db_long: numv('cai_dbl', 25.4) / 1000.0,
    recubrimiento: _caiMag($('#cai_rec')),
  };
}

async function caiCalcular() {
  const payload = caiRecolectar();
  if (!payload.P_servicio) { toast('Define la carga de servicio P', 'err'); return; }
  if (!payload.estratos.length) { toast('Define al menos un estrato de suelo', 'err'); return; }
  const btn = $('#btn-caisson-calc-h');
  const lbl = btn && (btn.querySelector('span') || btn);
  if (btn) btn.disabled = true;
  if (lbl) lbl.textContent = 'Calculando…';
  try {
    const r = await fetch('/api/caisson', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await r.json();
    if (!data.ok) { toast(data.error || 'Error en el cálculo', 'err', 6000); }
    else { _caiLastPayload = payload; _caiLast = data; caiRender(data); caiDibujar(data); toast('Cálculo completado', 'ok'); }
  } catch (e) {
    toast('No se pudo conectar con el servidor', 'err');
  } finally {
    if (btn) btn.disabled = false;
    if (lbl) lbl.textContent = 'Calcular';
  }
}

function caiRender(res) {
  const g = res.geometria, cap = res.capacidad, geo = res.geotecnico, e = res.estructural;
  const ccp = res.norma === 'CCP14';
  _caset('ck-dl', `${g.D_m}×${g.L_m}`);
  _caset('ck-qult', _catf(cap.Q_ult_kN).toFixed(0));
  _caset('ck-cap', _catf(ccp ? geo.R_r_kN : geo.Q_adm_kN).toFixed(0));
  _caset('ck-dcgeo', geo.ratio);
  _caset('ck-phipn', _catf(e.phiPn_kN).toFixed(0));
  _caset('ck-dcest', e.ratio);

  const filas = (cap.fuste_detalle || []).map(d => `
    <tr><td>${d.estrato} (${d.tipo})</td><td style="text-align:right">${d.desde}–${d.hasta}</td>
    <td style="text-align:right">${_catp(d.f_prom_kPa).toFixed(2)}</td>
    <td style="text-align:right">${_catf(d.Qs_kN).toFixed(1)}</td></tr>`).join('');

  let verif;
  if (ccp) {
    verif = `<div class="pil-line"><b>Verificación CCP-14 (LRFD):</b> R<sub>r</sub>=φ·Q =
      ${_catf(geo.R_r_kN).toFixed(1)} tonf (fuste ${_catf(geo.R_fuste_kN).toFixed(0)} + punta ${_catf(geo.R_punta_kN).toFixed(0)}) ·
      P<sub>u</sub>=${_catf(geo.Pu_demanda_kN).toFixed(1)} tonf → ${_caok(geo.cumple)} (CDR=${geo.CDR})</div>`;
  } else {
    verif = `<div class="pil-line"><b>Verificación NSR-10:</b> Q<sub>adm</sub>=Q<sub>últ</sub>/FS=
      ${_catf(geo.Q_adm_kN).toFixed(1)} tonf (FS=${geo.FS}) · P<sub>serv</sub>=${_catf(geo.P_servicio_kN).toFixed(1)} tonf
      → ${_caok(geo.cumple)} (D/C=${geo.ratio})</div>`;
  }
  const avisos = (res.avisos && res.avisos.length)
    ? `<div class="hint" style="border-color:var(--status-warn-bd);color:var(--status-warn-tx)">⚠ ${res.avisos.join('<br>⚠ ')}</div>` : '';

  $('#caisson-detalle').innerHTML = `
    <div class="pil-line"><b>Pila</b> Ø${g.D_m} m · L=${g.L_m} m${g.acampanada ? ` · campana Ø${g.D_campana_m} m` : ''} ·
      volumen ${g.volumen_concreto_m3} m³</div>
    <div class="pil-line"><b>Capacidad axial:</b> Q<sub>fuste</sub>=${_catf(cap.Q_fuste_kN).toFixed(1)} +
      Q<sub>punta</sub>=${_catf(cap.Q_punta_kN).toFixed(1)} = <b>Q<sub>últ</sub>=${_catf(cap.Q_ult_kN).toFixed(1)} tonf</b></div>
    ${verif}
    <div class="pil-line"><b>Estructural (columna):</b> φP<sub>n</sub>=${_catf(e.phiPn_kN).toFixed(1)} tonf ·
      ${e.n_barras} Ø${e.db_long_mm} mm (ρ=${e.cuantia_pct}%) → ${_caok(e.cumple)} (D/C=${e.ratio})</div>
    <table class="pil-table" style="margin-top:8px">
      <thead><tr><th>Estrato</th><th style="text-align:right">Tramo (m)</th><th style="text-align:right">f (tonf/m²)</th><th style="text-align:right">Q_fuste (tonf)</th></tr></thead>
      <tbody>${filas}</tbody>
    </table>
    ${avisos}`;
}

/* ---------- Esquema: elevación (SVG) ---------- */
function caiDibujar(res) {
  const cont = $('#caisson-preview');
  if (!cont) return;
  const g = res.geometria, cap = res.capacidad;
  const estr = (_caiLastPayload && _caiLastPayload.estratos) || [];
  const nf = (_caiLastPayload && _caiLastPayload.nivel_freatico) || 1e9;
  const D = g.D_m, L = g.L_m, Db = g.acampanada ? g.D_campana_m : D, hb = g.altura_campana_m || 0;
  const C = { bg: '#0d1c16', concrete: '#6f7a83', edge: '#1f262c', steel: '#e07a3a',
              arrow: '#e7c46b', water: '#5a93c9', txt: '#eaf2ee', sub: '#9fc0b2' };
  const SOIL = ['#caa86a', '#b9975a', '#a9bda0', '#c9b79b', '#bfa98b'];

  const W = 460, H = 440, mTop = 42, mBot = 40;
  const soilDepth = estr.reduce((a, e) => a + (e.espesor || 0), 0);
  const depth = Math.max(L + 1.5, soilDepth, L + hb + 1.0);
  const s = (H - mTop - mBot) / depth;                 // px por metro (vertical)
  const y0 = mTop;                                     // y del terreno (z=0)
  const cx = W / 2;
  const sx = Math.min(s, 26);                          // escala horizontal (limita ancho)
  const terrenoW = Math.min(W - 40, Math.max(180, Db * sx * 2.4));

  const YZ = z => y0 + z * s;
  let svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${W} ${H}" width="100%" height="100%"
    style="display:block;background:${C.bg};border-radius:10px;font-family:'Inter',system-ui,sans-serif">
    <text x="${cx}" y="22" font-size="12" font-weight="700" fill="${C.txt}" text-anchor="middle">ELEVACIÓN — pila y perfil de suelo</text>`;

  // estratos
  let prof = 0;
  estr.forEach((e, i) => {
    const esp = e.espesor || 0; if (esp <= 0) return;
    const yTop = YZ(prof), hpx = esp * s;
    svg += `<rect x="${cx - terrenoW / 2}" y="${yTop.toFixed(1)}" width="${terrenoW}" height="${hpx.toFixed(1)}"
      fill="${SOIL[i % SOIL.length]}" fill-opacity="0.5" stroke="#7a6a44" stroke-width="0.5"/>`;
    const et = e.tipo === 'arcilla' ? `arcilla c_u=${_catp(e.cu).toFixed(1)}` : `arena φ=${e.phi}°`;
    svg += `<text x="${cx - terrenoW / 2 + 5}" y="${(yTop + 12).toFixed(1)}" font-size="8.5" fill="#2a2418">${et}</text>`;
    prof += esp;
  });
  // terreno
  svg += `<line x1="${cx - terrenoW / 2}" y1="${y0}" x2="${cx + terrenoW / 2}" y2="${y0}" stroke="#6b5b3e" stroke-width="1.4"/>`;
  // nivel freático
  if (nf > 0 && nf < depth) {
    svg += `<line x1="${cx - terrenoW / 2}" y1="${YZ(nf).toFixed(1)}" x2="${cx + terrenoW / 2}" y2="${YZ(nf).toFixed(1)}" stroke="${C.water}" stroke-width="1" stroke-dasharray="5 3"/>`;
    svg += `<text x="${cx + terrenoW / 2 - 4}" y="${(YZ(nf) - 3).toFixed(1)}" font-size="8" fill="${C.water}" text-anchor="end">N.F.</text>`;
  }

  // fuste
  const dwpx = Math.max(16, D * sx), dbpx = Math.max(dwpx, Db * sx);
  const yFuste0 = y0, yFuste1 = YZ(L - hb), yBase = YZ(L);
  svg += `<rect x="${(cx - dwpx / 2).toFixed(1)}" y="${yFuste0}" width="${dwpx.toFixed(1)}" height="${(yFuste1 - yFuste0).toFixed(1)}"
    fill="${C.concrete}" fill-opacity="0.9" stroke="${C.edge}" stroke-width="1.3"/>`;
  // campana
  if (g.acampanada && hb > 0) {
    svg += `<polygon points="${(cx - dwpx / 2).toFixed(1)},${yFuste1.toFixed(1)} ${(cx + dwpx / 2).toFixed(1)},${yFuste1.toFixed(1)}
      ${(cx + dbpx / 2).toFixed(1)},${yBase.toFixed(1)} ${(cx - dbpx / 2).toFixed(1)},${yBase.toFixed(1)}"
      fill="${C.concrete}" fill-opacity="0.9" stroke="${C.edge}" stroke-width="1.3"/>`;
  }
  // fricción (flechas)
  const nfl = 5;
  for (let i = 0; i < nfl; i++) {
    const yy = y0 + (yFuste1 - y0) * (i + 0.5) / nfl;
    svg += `<line x1="${(cx - dwpx / 2 - 12).toFixed(1)}" y1="${yy.toFixed(1)}" x2="${(cx - dwpx / 2 - 1).toFixed(1)}" y2="${yy.toFixed(1)}" stroke="${C.steel}" stroke-width="1"/>`;
    svg += `<line x1="${(cx + dwpx / 2 + 12).toFixed(1)}" y1="${yy.toFixed(1)}" x2="${(cx + dwpx / 2 + 1).toFixed(1)}" y2="${yy.toFixed(1)}" stroke="${C.steel}" stroke-width="1"/>`;
  }
  svg += `<text x="${(cx + dbpx / 2 + 16).toFixed(1)}" y="${((y0 + yFuste1) / 2).toFixed(1)}" font-size="9" fill="${C.steel}">Q_fuste ${_catf(cap.Q_fuste_kN).toFixed(0)} tonf</text>`;
  // punta (flechas arriba)
  for (let i = 0; i <= 4; i++) {
    const xx = cx - dbpx / 2 + dbpx * i / 4;
    svg += `<line x1="${xx.toFixed(1)}" y1="${(yBase + 16).toFixed(1)}" x2="${xx.toFixed(1)}" y2="${(yBase + 2).toFixed(1)}" stroke="${C.arrow}" stroke-width="1.2"/>`;
  }
  svg += `<text x="${cx}" y="${(yBase + 30).toFixed(1)}" font-size="9" fill="${C.arrow}" text-anchor="middle">Q_punta = ${_catf(cap.Q_punta_kN).toFixed(0)} tonf</text>`;
  // cotas
  svg += `<text x="${cx}" y="${(y0 - 6).toFixed(1)}" font-size="9" fill="${C.txt}" text-anchor="middle">D = ${D.toFixed(2)} m${g.acampanada ? ` · campana Ø${Db.toFixed(2)}` : ''}</text>`;
  svg += `<text x="${(cx - terrenoW / 2 - 6).toFixed(1)}" y="${((y0 + yBase) / 2).toFixed(1)}" font-size="9" fill="${C.txt}" text-anchor="middle" transform="rotate(-90 ${(cx - terrenoW / 2 - 6).toFixed(1)} ${((y0 + yBase) / 2).toFixed(1)})">L = ${L.toFixed(2)} m</text>`;
  svg += `</svg>`;
  cont.innerHTML = svg;
}

/* ---------- Memoria (PDF) ---------- */
async function caiGenerarPDF(btn) {
  const payload = caiRecolectar();
  if (!payload.P_servicio) { toast('Define la carga de servicio P', 'err'); return; }
  if (!payload.estratos.length) { toast('Define al menos un estrato de suelo', 'err'); return; }
  const val = id => { const e = $('#' + id); return e ? e.value : ''; };
  payload.proyecto = val('proyecto'); payload.ingeniero = val('ingeniero');
  payload.ubicacion = val('ubicacion'); payload.empresa = val('empresa');
  const old = btn ? btn.innerHTML : '';
  if (btn) { btn.disabled = true; btn.textContent = 'Generando…'; }
  try {
    const r = await fetch('/api/caisson_pdf', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!r.ok) { const j = await r.json().catch(() => ({})); toast('Error PDF: ' + (j.error || r.status), 'err', 6000); return; }
    const blob = await r.blob();
    const filename = `CimX-caisson-${(payload.proyecto || 'memoria').replace(/[^a-z0-9]/gi, '_')}.pdf`;
    if (window.CimXPDFModal) { CimXPDFModal.open(blob, filename); toast('Memoria generada — usa "Descargar" en el visor', 'ok'); }
    else { const url = URL.createObjectURL(blob); const a = document.createElement('a'); a.href = url; a.download = filename; a.click(); URL.revokeObjectURL(url); }
  } catch (e) {
    toast('No se pudo generar la memoria', 'err', 6000);
  } finally {
    if (btn) { btn.disabled = false; btn.innerHTML = old; }
  }
}

/* ---------- Init ---------- */
document.addEventListener('DOMContentLoaded', () => {
  caiSeedEstratos();
  const bAdd = $('#cai-add-estrato');
  if (bAdd) bAdd.addEventListener('click', () => $('#cai-estratos').appendChild(_caiFilaEstrato()));
  const selN = $('#cai_norma');
  if (selN) selN.addEventListener('change', caiAplicarNorma);
  caiAplicarNorma();

  const bCalc = $('#btn-caisson-calc-h');
  if (bCalc) bCalc.addEventListener('click', () => { if (typeof showView === 'function') showView('caisson'); caiCalcular(); });
  const bPdf = $('#btn-caisson-pdf-h');
  if (bPdf) bPdf.addEventListener('click', () => caiGenerarPDF(bPdf));
  const bPdf2 = $('#btn-caisson-pdf-2');
  if (bPdf2) bPdf2.addEventListener('click', () => caiGenerarPDF(bPdf2));

  window.caiCalcular = caiCalcular;
  window.caiGenerarPDF = caiGenerarPDF;
});
