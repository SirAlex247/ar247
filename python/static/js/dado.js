/* ============================================================
   CimX — Módulo de Dados / Cabezales de pilotes (frontend)
   Encepado sobre 1 a 6 pilotes: reacciones, punzonamiento, cortante,
   flexión y método de bielas (NSR-10).
   Reusa helpers globales de cimx.js: $, $$, toSI, fromSI, toast.
   Entradas en MKS (display) → SI al backend (/api/dado).
   ============================================================ */
'use strict';

function dReadMag(el) {
  if (!el) return null;
  const v = parseFloat(el.value);
  if (isNaN(v)) return null;
  return el.dataset.mag ? toSI(v, el.dataset.mag) : v;
}

function dadRecolectar() {
  const db_m = (parseFloat($('#dado_db').value) || 19.05) / 1000.0;   // mm → m
  return {
    n_pilotes: parseInt($('#dado_n').value) || 4,
    Dp: dReadMag($('#dado_Dp')) || 0.45,
    c1: dReadMag($('#dado_c1')) || 0.45,
    c2: dReadMag($('#dado_c2')) || 0.45,
    Pu: dReadMag($('#dado_Pu')) || 0,
    Mux: dReadMag($('#dado_Mux')) || 0,
    Muy: dReadMag($('#dado_Muy')) || 0,
    s: dReadMag($('#dado_s')) || 0,
    e: dReadMag($('#dado_e')) || 0,
    h: dReadMag($('#dado_h')) || 0,
    fc: dReadMag($('#dado_fc')),
    fc_columna: dReadMag($('#dado_fccol')) || 0,
    fy: dReadMag($('#dado_fy')),
    db: db_m, db_col: db_m,
    recubrimiento: dReadMag($('#dado_rec')),
    capacidad_pilote: dReadMag($('#dado_cap')) || 0,
    factor_peso: parseFloat($('#dado_fp').value) || 1.2,
    posicion: $('#dado_pos').value,
    metodo: ($('#dado_metodo') && $('#dado_metodo').value) || 'ambos',
    norma: ($('#dado_norma') && $('#dado_norma').value) || 'NSR10',
  };
}

const _dtf = kN => fromSI(kN, 'force');       // kN → tonf
const _dtm = kNm => fromSI(kNm, 'moment');    // kN·m → tonf·m

async function dadCalcular() {
  const payload = dadRecolectar();
  if (!payload.Pu) { toast('Define la carga última Pu de la columna', 'err'); return; }
  const btn = $('#btn-dado-calc-h');
  const lbl = btn && (btn.querySelector('span') || btn);
  if (btn) btn.disabled = true;
  if (lbl) lbl.textContent = 'Calculando…';
  try {
    const r = await fetch('/api/dado', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await r.json();
    if (!data.ok) { toast(data.error || 'Error en el cálculo', 'err', 6000); }
    else { _dadLast = data; dadRender(data); dadMostrar(); toast('Cálculo completado', 'ok'); }
  } catch (e) {
    toast('No se pudo conectar con el servidor', 'err');
  } finally {
    if (btn) btn.disabled = false;
    if (lbl) lbl.textContent = 'Calcular';
  }
}

function _asGobernante(e) {
  return Math.max(e.as_x_rec_cm2 || 0, e.as_y_rec_cm2 || 0);
}

function _dadPunzLine(pc, pp) {
  const okf = (b) => b ? '<span style="color:var(--green-300)">cumple</span>'
                       : '<span style="color:var(--status-err-tx)">no cumple</span>';
  if (pc.vu_momento_kPa != null && pc.vu_momento_kPa > 0.1) {
    const _tp = kPa => fromSI(kPa, 'pressure');
    return `<div class="pil-line"><b>Punzonamiento columna (con momento γv):</b>
      v<sub>u</sub> ${_tp(pc.vu_directo_kPa).toFixed(1)}+${_tp(pc.vu_momento_kPa).toFixed(1)}=<b>${_tp(pc.vu_total_kPa).toFixed(1)}</b> vs φv<sub>c</sub> ${_tp(pc.phi_vc_kPa).toFixed(1)} tonf/m² (γ<sub>v</sub>=${pc.gamma_v_x}) → ${okf(pc.cumple_momento)} (D/C=${pc.ratio_momento}) · pilote D/C=${pp.ratio} ${okf(pp.cumple)}</div>`;
  }
  return `<div class="pil-line"><b>Punzonamiento:</b> columna D/C=${pc.ratio} ${okf(pc.cumple)} · pilote D/C=${pp.ratio} ${okf(pp.cumple)}</div>`;
}

function dadRender(res) {
  const g = res.geometria, c = res.cargas, e = res.estructural;
  const set = (id, v) => { const el = $('#' + id); if (el) el.textContent = v; };
  set('dk-bl', `${g.Bx_m}×${g.Ly_m}`);
  set('dk-h', g.h_m);
  set('dk-d', g.d_m);
  set('dk-pile', c.ratio_pilote != null ? c.ratio_pilote : '—');
  set('dk-punz', e.punz_columna.ratio);
  set('dk-as', _asGobernante(e).toFixed(1));

  const ok = (b) => b ? '<span style="color:var(--green-300)">cumple</span>'
                      : '<span style="color:var(--status-err-tx)">no cumple</span>';
  const fila = (f, dir) => {
    const rho = (f.cuantia && !f.cuantia.cumple) ? ' <span style="color:var(--status-err-tx)">✗ρ</span>' : '';
    return `
    <tr><td>${dir}</td>
        <td style="text-align:right">${_dtm(f.Mu_kNm).toFixed(2)}</td>
        <td style="text-align:right">${f.As_cm2}${f.gobierna_minimo ? ' <span class="muted">(mín)</span>' : ''}</td>
        <td style="text-align:right">${f.n_barras} Ø${f.db_mm} @ ${f.sep_cm} cm${rho}</td></tr>`;
  };

  // reacciones
  const reac = c.reacciones_kN.map((r, i) => `P${i + 1}: <b>${_dtf(r).toFixed(1)}</b>`).join(' · ');
  const capTxt = c.capacidad_pilote_kN ? `${_dtf(c.capacidad_pilote_kN).toFixed(1)} tonf` : '—';

  const metodo = e.metodo || 'ambos';

  // bielas
  let bielaHtml = '';
  if (metodo !== 'flexion') {
    if (e.biela.tipo === 'triangular') {
      const a = e.biela.arista;
      bielaHtml = `<div class="pil-line"><b>Bielas (triangular):</b> tensor por arista T=${_dtf(a.T_kN).toFixed(1)} tonf · As=${a.As_cm2} cm² (${a.n_barras} barras/arista)</div>`;
    } else {
      bielaHtml = `<div class="pil-line"><b>Bielas:</b> dir X → T=${_dtf(e.biela.x.T_kN).toFixed(1)} tonf, As=${e.biela.x.As_cm2} cm² · dir Y → T=${_dtf(e.biela.y.T_kN).toFixed(1)} tonf, As=${e.biela.y.As_cm2} cm²</div>`;
    }
  }

  // flexión (tabla)
  let flexHtml = '';
  if (metodo !== 'bielas') {
    flexHtml = `<table class="pil-table" style="margin-top:8px">
      <thead><tr><th>Flexión</th><th style="text-align:right">Mu (tonf·m)</th><th style="text-align:right">As (cm²)</th><th style="text-align:right">Refuerzo</th></tr></thead>
      <tbody>${fila(e.flexion_x, 'Dir. X')}${fila(e.flexion_y, 'Dir. Y')}</tbody></table>`;
  }

  const metodoTxt = { flexion: 'flexión (seccional)', bielas: 'bielas (puntal-tensor)', ambos: 'mayor de flexión y bielas' }[metodo];
  const adoptado = `<div class="pil-line" style="margin-top:6px"><b>Acero inferior adoptado</b> (${metodoTxt}): dir X = <b>${e.as_x_rec_cm2} cm²</b> · dir Y = <b>${e.as_y_rec_cm2} cm²</b></div>`;

  const avisos = (res.avisos && res.avisos.length)
    ? `<div class="hint" style="border-color:var(--status-warn-bd);color:var(--status-warn-tx)">⚠ ${res.avisos.join('<br>⚠ ')}</div>` : '';

  const normaTxt = (res.norma === 'CCP14')
    ? `<span class="norma-badge">CCP-14 · LRFD</span> φ<sub>cortante</sub>=${e.phi_corte}, d<sub>v</sub>=${e.dv_m} m`
    : `<span class="norma-badge">NSR-10 · ACI 318</span> φ<sub>cortante</sub>=${e.phi_corte}, peralte d`;

  $('#dado-detalle').innerHTML = `
    <div class="pil-line">${normaTxt}</div>
    <div class="pil-line"><b>Geometría:</b> ${g.forma === 'tri' ? 'triangular' : 'rectangular'} ${g.Bx_m}×${g.Ly_m} m · h=${g.h_m} m · d=${g.d_m} m · <b>${g.clasificacion}</b> (m=${g.m_voladizo_m} m)</div>
    <div class="pil-line"><b>Reacciones (c/peso):</b> ${reac} tonf</div>
    <div class="pil-line"><b>R<sub>máx</sub> pilote:</b> ${_dtf(c.Pmax_kN).toFixed(1)} / ${capTxt} → ${ok(c.cumple_pilote)} (D/C=${c.ratio_pilote != null ? c.ratio_pilote : '—'})</div>
    ${_dadPunzLine(e.punz_columna, e.punz_pilote)}
    <div class="pil-line"><b>Cortante 1 vía:</b> dir X → D/C=${e.cortante_x.ratio} ${ok(e.cortante_x.cumple)} · dir Y → D/C=${e.cortante_y.ratio} ${ok(e.cortante_y.cumple)}</div>
    ${e.transferencia ? `<div class="pil-line"><b>Transferencia columna→dado (C.15.8):</b> aplastamiento D/C=${e.transferencia.ratio} ${ok(e.transferencia.cumple_aplastamiento)} · dowels ${e.transferencia.n_dowels} Ø${e.transferencia.db_dowel_mm} (ℓ<sub>dc</sub>=${(e.transferencia.ldc_dowel_m*100).toFixed(0)}/${(e.transferencia.ldc_disponible_m*100).toFixed(0)} cm) ${ok(e.transferencia.cumple_dowels)}</div>` : ''}
    ${flexHtml}
    ${bielaHtml}
    ${adoptado}
    ${e.anclaje_tensor ? `<div class="pil-line"><b>Anclaje del tensor:</b> ℓ<sub>d</sub>=${(e.anclaje_tensor.ld_m*100).toFixed(0)} cm vs disp. ${(e.anclaje_tensor.disp_x_m*100).toFixed(0)}/${(e.anclaje_tensor.disp_y_m*100).toFixed(0)} cm → ${e.anclaje_tensor.requiere_gancho ? '<span style="color:var(--status-err-tx)">requiere gancho</span>' : '<span style="color:var(--green-300)">desarrolla recto</span>'}</div>` : ''}
    <div class="pil-line"><b>Anclaje columna:</b> ℓ<sub>dc</sub> = ${(e.ldc_columna_m * 100).toFixed(0)} cm</div>
    ${avisos}`;
}

/* ---------- Esquema: planta + sección (SVG) ---------- */
function dadDibujar(res) {
  const cont = $('#dado-preview');
  if (!cont) return;
  const g = res.geometria;
  const Bx = g.Bx_m, Ly = g.Ly_m, h = g.h_m, c1 = g.c1_m, c2 = g.c2_m, Dp = g.Dp_m;
  const coords = g.coords, forma = g.forma, verts = g.vertices;

  const W = 460, H = 540;
  const COL = { bg: '#0d1c16', concrete: '#6f7a83', col: '#9aa6ae',
                pile: '#5a6b8c', txt: '#eaf2ee', sub: '#9fc0b2', steel: '#e07a3a',
                edge: '#1f262c', arrow: '#e7c46b' };

  // ----- PLANTA (arriba) -----
  const pX0 = 60, pX1 = 300, pY0 = 40, pY1 = 240;
  const sPlan = Math.min((pX1 - pX0) / Bx, (pY1 - pY0) / Ly) * 0.82;
  const pcx = (pX0 + pX1) / 2, pcy = (pY0 + pY1) / 2;
  const wx = x => pcx + x * sPlan, wy = y => pcy - y * sPlan;   // mundo → svg

  let svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${W} ${H}" width="100%" height="100%"
    style="display:block;background:${COL.bg};border-radius:10px;font-family:'Inter',system-ui,sans-serif">
    <defs><marker id="darr" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto">
      <path d="M0 0 L10 5 L0 10 z" fill="${COL.arrow}"/></marker></defs>
    <text x="${pcx}" y="24" font-size="12" font-weight="700" fill="${COL.txt}" text-anchor="middle">PLANTA — ${coords.length} pilote(s)</text>`;

  // cabezal (rect o triángulo)
  if (forma === 'tri' && verts) {
    const pts = verts.map(v => `${wx(v[0]).toFixed(1)},${wy(v[1]).toFixed(1)}`).join(' ');
    svg += `<polygon points="${pts}" fill="${COL.concrete}" fill-opacity="0.30" stroke="${COL.concrete}" stroke-width="1.6"/>`;
  } else {
    const x0 = wx(-Bx / 2), y0 = wy(Ly / 2);
    svg += `<rect x="${x0.toFixed(1)}" y="${y0.toFixed(1)}" width="${(Bx * sPlan).toFixed(1)}" height="${(Ly * sPlan).toFixed(1)}"
              fill="${COL.concrete}" fill-opacity="0.30" stroke="${COL.concrete}" stroke-width="1.6"/>`;
  }
  // pilotes
  coords.forEach((p, i) => {
    svg += `<circle cx="${wx(p[0]).toFixed(1)}" cy="${wy(p[1]).toFixed(1)}" r="${(Dp / 2 * sPlan).toFixed(1)}"
              fill="${COL.pile}" fill-opacity="0.9" stroke="#1f2a44" stroke-width="1.1"/>`;
    svg += `<text x="${wx(p[0]).toFixed(1)}" y="${(wy(p[1]) + 3).toFixed(1)}" font-size="9" fill="#fff" text-anchor="middle" font-weight="700">P${i + 1}</text>`;
  });
  // columna
  svg += `<rect x="${wx(-c1 / 2).toFixed(1)}" y="${wy(c2 / 2).toFixed(1)}" width="${(c1 * sPlan).toFixed(1)}" height="${(c2 * sPlan).toFixed(1)}"
            fill="${COL.col}" stroke="${COL.edge}" stroke-width="1.2"/>`;
  // cotas
  const yBot = wy(-Ly / 2) + 18, xLeft = wx(-Bx / 2) - 12;
  svg += `<text x="${pcx}" y="${yBot.toFixed(1)}" font-size="11" fill="${COL.txt}" text-anchor="middle">Bx = ${Bx.toFixed(2)} m</text>`;
  svg += `<text x="${xLeft.toFixed(1)}" y="${pcy.toFixed(1)}" font-size="11" fill="${COL.txt}" text-anchor="middle" transform="rotate(-90 ${xLeft.toFixed(1)} ${pcy.toFixed(1)})">Ly = ${Ly.toFixed(2)} m</text>`;
  svg += `<text x="${pX1 + 14}" y="${pcy - 4}" font-size="10" fill="${COL.pile}">pilotes Ø${(Dp * 100).toFixed(0)} cm</text>`;

  // ----- SECCIÓN (abajo, corte en x) -----
  const secTitleY = 296;
  svg += `<text x="${W / 2}" y="${secTitleY}" font-size="12" font-weight="700" fill="${COL.txt}" text-anchor="middle">SECCIÓN</text>`;
  const baseY = 470;                       // base del dado
  const Lp = 1.1;                          // tramo de pilote dibujado
  const sSec = Math.min(300 / Bx, 150 / (h + Lp + 0.6)) * 0.9;
  const bwS = Bx * sSec, hS = h * sSec;
  const scx = W / 2 - 30;
  const sx = scx - bwS / 2;
  const colW = c1 * sSec, colH = Math.max(36, 0.55 * sSec);
  const topY = baseY - hS;

  // pilotes (proyección sobre x)
  const xs = [...new Set(coords.map(p => Math.round(p[0] * 1000) / 1000))].sort((a, b) => a - b);
  xs.forEach(x => {
    const cx = scx + x * sSec, pw = Dp * sSec;
    svg += `<rect x="${(cx - pw / 2).toFixed(1)}" y="${topY.toFixed(1)}" width="${pw.toFixed(1)}" height="${(Lp * sSec + hS).toFixed(1)}"
              fill="${COL.pile}" fill-opacity="0.85" stroke="#1f2a44" stroke-width="1"/>`;
    // reacción
    svg += `<line x1="${cx.toFixed(1)}" y1="${(baseY + 30).toFixed(1)}" x2="${cx.toFixed(1)}" y2="${(baseY + 6).toFixed(1)}" stroke="${COL.arrow}" stroke-width="1.3" marker-end="url(#darr)"/>`;
  });
  // dado
  svg += `<rect x="${sx.toFixed(1)}" y="${topY.toFixed(1)}" width="${bwS.toFixed(1)}" height="${hS.toFixed(1)}"
            fill="${COL.concrete}" stroke="${COL.edge}" stroke-width="1.6"/>`;
  // columna
  svg += `<rect x="${(scx - colW / 2).toFixed(1)}" y="${(topY - colH).toFixed(1)}" width="${colW.toFixed(1)}" height="${colH.toFixed(1)}"
            fill="${COL.col}" stroke="${COL.edge}" stroke-width="1.2"/>`;
  // acero inferior
  svg += `<line x1="${(sx + 5).toFixed(1)}" y1="${(baseY - 6).toFixed(1)}" x2="${(sx + bwS - 5).toFixed(1)}" y2="${(baseY - 6).toFixed(1)}" stroke="${COL.steel}" stroke-width="1.8"/>`;
  // cotas
  svg += `<text x="${scx.toFixed(1)}" y="${(topY - colH - 8).toFixed(1)}" font-size="10" fill="${COL.txt}" text-anchor="middle">columna ${(c1 * 100).toFixed(0)}×${(c2 * 100).toFixed(0)} cm</text>`;
  svg += `<line x1="${(sx + bwS + 14).toFixed(1)}" y1="${topY.toFixed(1)}" x2="${(sx + bwS + 14).toFixed(1)}" y2="${baseY.toFixed(1)}" stroke="${COL.sub}" stroke-width="0.8" marker-start="url(#darr)" marker-end="url(#darr)"/>`;
  svg += `<text x="${(sx + bwS + 30).toFixed(1)}" y="${(baseY - hS / 2).toFixed(1)}" font-size="10" fill="${COL.txt}" text-anchor="middle" transform="rotate(90 ${(sx + bwS + 30).toFixed(1)} ${(baseY - hS / 2).toFixed(1)})">h = ${h.toFixed(2)} m</text>`;
  svg += `<text x="${scx.toFixed(1)}" y="${(baseY + 44).toFixed(1)}" font-size="10" fill="${COL.arrow}" text-anchor="middle">reacciones de pilote</text>`;

  svg += `</svg>`;
  cont.innerHTML = svg;
}

/* ---------- Esquema: 2D (SVG) o 3D en el mismo panel ---------- */
function _dadPayload3D(g) {
  return {
    coords: g.coords, vertices: g.vertices, forma: g.forma,
    Dp: g.Dp_m, Bx: g.Bx_m, Ly: g.Ly_m, h: g.h_m, c1: g.c1_m, c2: g.c2_m,
    s: g.s_m, e: g.e_m, n: g.n_pilotes,
  };
}

/* Muestra el esquema 2D o el modelo 3D en #dado-preview según el toggle. */
function dadMostrar() {
  const cont = $('#dado-preview');
  if (!cont || !_dadLast) return;
  if (_vista3D_dado && window.CimXDado3D && CimXDado3D.isAvailable()) {
    try {
      CimXDado3D.render(_dadPayload3D(_dadLast.geometria), cont, { onSelect: dadOnSelect });
    } catch (e) {
      console.error('[dado3d]', e);
      if (window.CimXDado3D) CimXDado3D.dispose();
      dadDibujar(_dadLast);
    }
  } else {
    if (window.CimXDado3D) CimXDado3D.dispose();
    dadHideProps();
    dadDibujar(_dadLast);
  }
}

/* Cambia el modo del visor del esquema ('2d' | '3d'). */
function setVistaDado(modo) {
  _vista3D_dado = (modo === '3d');
  $$('[data-vista-dado]').forEach(b =>
    b.classList.toggle('active', b.getAttribute('data-vista-dado') === modo));
  const hint = $('#dado-vista-hint');
  if (hint) hint.style.display = _vista3D_dado ? '' : 'none';
  if (!_vista3D_dado) dadHideProps();
  dadMostrar();
}

/* ---------- Panel de propiedades (estilo Revit) ---------- */
let _dadSelTipo = null;
let _dadLast = null;
let _vista3D_dado = false;
let _dadEditTimer = null;

const _DAD_CAMPOS = {
  cabezal: [
    { id: 'dp_h', form: 'dado_h', label: 'Espesor h', key: 'h', step: 0.05 },
    { id: 'dp_e', form: 'dado_e', label: 'Borde e', key: 'e', step: 0.05 },
  ],
  pilote: [
    { id: 'dp_Dp', form: 'dado_Dp', label: 'Diámetro Dp', key: 'Dp', step: 0.05 },
    { id: 'dp_s', form: 'dado_s', label: 'Separación s', key: 's', step: 0.05 },
  ],
  columna: [
    { id: 'dp_c1', form: 'dado_c1', label: 'Columna c1', key: 'c1', step: 0.05 },
    { id: 'dp_c2', form: 'dado_c2', label: 'Columna c2', key: 'c2', step: 0.05 },
  ],
};
const _DAD_TITULO = { cabezal: 'Cabezal (dado)', pilote: 'Pilotes', columna: 'Columna' };

function _dadEnsurePanel() {
  if ($('#dado-props')) return $('#dado-props');
  const frame = $('#dado-preview');
  if (!frame) return null;
  const card = frame.closest('.card') || frame.parentElement;
  card.style.position = 'relative';
  const panel = document.createElement('div');
  panel.id = 'dado-props';
  panel.style.cssText = 'position:absolute;top:14px;right:14px;width:248px;z-index:20;display:none;' +
    'background:rgba(11,24,19,0.94);border:1px solid rgba(120,160,140,0.40);border-radius:12px;' +
    'box-shadow:0 10px 30px rgba(0,0,0,0.45);backdrop-filter:blur(4px);font-family:Inter,system-ui,sans-serif;color:#eaf2ee;overflow:hidden';
  panel.innerHTML =
    '<div style="display:flex;align-items:center;justify-content:space-between;padding:10px 12px;background:rgba(22,163,74,0.18);border-bottom:1px solid rgba(120,160,140,0.30)">' +
      '<span id="dp-title" style="font-weight:700;font-size:13px">Elemento</span>' +
      '<button id="dp-close" style="background:none;border:none;color:#cfe3d8;font-size:15px;cursor:pointer;line-height:1;padding:2px 4px">✕</button>' +
    '</div>' +
    '<div id="dp-body" style="padding:12px"></div>' +
    '<div style="padding:8px 12px;border-top:1px solid rgba(120,160,140,0.20);font-size:10.5px;color:#9fc0b2">Edita un valor y el modelo se recalcula.</div>';
  card.appendChild(panel);
  $('#dp-close').addEventListener('click', () => { CimXDado3D.clearSelection(); dadHideProps(); });
  return panel;
}

function dadOnSelect(info) {
  _dadSelTipo = info ? info.tipo : null;
  if (!info) { dadHideProps(); return; }
  dadShowProps(info);
}

function dadShowProps(info) {
  const panel = _dadEnsurePanel();
  if (!panel) return;
  const campos = _DAD_CAMPOS[info.tipo] || [];
  $('#dp-title').textContent = _DAD_TITULO[info.tipo] || 'Elemento';
  const fmt = v => (v == null ? '' : (+v).toFixed(3).replace(/0+$/, '').replace(/\.$/, ''));
  $('#dp-body').innerHTML = campos.map(c => `
    <div style="margin-bottom:10px">
      <label style="display:block;font-size:11px;color:#9fc0b2;margin-bottom:4px">${c.label} <span style="color:#6f8a7e">m</span></label>
      <input type="number" id="${c.id}" step="${c.step}" value="${fmt(info.props[c.key])}"
        style="width:100%;box-sizing:border-box;background:#0d1c16;border:1px solid rgba(120,160,140,0.35);border-radius:8px;color:#eaf2ee;padding:7px 9px;font-size:13px">
    </div>`).join('') +
    (info.tipo === 'cabezal'
      ? `<div style="font-size:10.5px;color:#8aa99c">Bx×Ly = ${(+info.props.Bx).toFixed(2)} × ${(+info.props.Ly).toFixed(2)} m (derivado de s y e)</div>`
      : info.tipo === 'pilote'
        ? `<div style="font-size:10.5px;color:#8aa99c">${info.props.n} pilote(s) · separación entre ejes</div>`
        : '');
  campos.forEach(c => {
    const el = $('#' + c.id);
    if (el) el.addEventListener('input', () => dadEditCampo(c.form, el.value));
  });
  panel.style.display = 'block';
}

function dadHideProps() {
  const p = $('#dado-props'); if (p) p.style.display = 'none';
}

function dadEditCampo(formId, valor) {
  const fEl = $('#' + formId);
  if (fEl) fEl.value = valor;                 // longitudes: m = SI (data-mag length)
  clearTimeout(_dadEditTimer);
  _dadEditTimer = setTimeout(dadAplicarEdicion, 260);
}

async function dadAplicarEdicion() {
  const payload = dadRecolectar();
  if (!payload.Pu) return;
  try {
    const r = await fetch('/api/dado', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await r.json();
    if (!data.ok) { toast(data.error || 'Error al recalcular', 'err', 5000); return; }
    _dadLast = data;
    dadRender(data);                                   // KPIs y detalle
    const cont = $('#dado-preview');                   // re-render 3D en el mismo panel (mantiene cámara y selección)
    if (cont) CimXDado3D.render(_dadPayload3D(data.geometria), cont, { onSelect: dadOnSelect });
    dadRefreshProps(data.geometria);                   // refresca valores derivados (sin pisar el campo activo)
  } catch (e) {
    toast('No se pudo recalcular', 'err');
  }
}

function dadRefreshProps(g) {
  const upd = (id, val) => { const el = $('#' + id); if (el && el !== document.activeElement) el.value = (+val).toFixed(3).replace(/0+$/, '').replace(/\.$/, ''); };
  upd('dp_h', g.h_m); upd('dp_e', g.e_m); upd('dp_Dp', g.Dp_m);
  upd('dp_s', g.s_m); upd('dp_c1', g.c1_m); upd('dp_c2', g.c2_m);
}

/* ---------- Memoria de cálculo (PDF) ---------- */
async function dadGenerarPDF(btn) {
  const payload = dadRecolectar();
  if (!payload.Pu) { toast('Define la carga última Pu de la columna', 'err'); return; }
  const val = id => { const e = $('#' + id); return e ? e.value : ''; };
  payload.proyecto = val('proyecto');
  payload.ingeniero = val('ingeniero');
  payload.ubicacion = val('ubicacion');
  payload.empresa = val('empresa');
  const old = btn ? btn.innerHTML : '';
  if (btn) { btn.disabled = true; btn.textContent = 'Generando…'; }
  try {
    const r = await fetch('/api/dado_pdf', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!r.ok) { const j = await r.json().catch(() => ({})); toast('Error PDF: ' + (j.error || r.status), 'err', 6000); return; }
    const blob = await r.blob();
    const filename = `CimX-dado-${(payload.proyecto || 'memoria').replace(/[^a-z0-9]/gi, '_')}.pdf`;
    if (window.CimXPDFModal) {
      CimXPDFModal.open(blob, filename);
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
  const bCalcH = $('#btn-dado-calc-h');
  if (bCalcH) bCalcH.addEventListener('click', () => { if (typeof showView === 'function') showView('dado'); dadCalcular(); });
  const bPdfH = $('#btn-dado-pdf-h');
  if (bPdfH) bPdfH.addEventListener('click', () => dadGenerarPDF(bPdfH));
  const bpdf = $('#btn-dado-pdf');
  if (bpdf) bpdf.addEventListener('click', () => dadGenerarPDF(bpdf));

  // Toggle 2D / 3D del esquema
  $$('[data-vista-dado]').forEach(b =>
    b.addEventListener('click', () => setVistaDado(b.getAttribute('data-vista-dado'))));

  // Selector de norma → nota
  const selN = $('#dado_norma');
  const setNormaHint = () => {
    const h = $('#dado-norma-hint');
    if (!h) return;
    h.innerHTML = (selN && selN.value === 'CCP14')
      ? 'CCP-14 / AASHTO §5: cortante φ=0.90, peralte d<sub>v</sub>=máx(0.9d, 0.72h), v<sub>c</sub> de dos términos y refuerzo mínimo por M<sub>cr</sub>.'
      : 'NSR-10 / ACI 318: cortante φ=0.75, peralte d, v<sub>c</sub> de tres términos y refuerzo mínimo 0.0018·b·h.';
  };
  if (selN) selN.addEventListener('change', setNormaHint);
  setNormaHint();

  window.dadCalcular = dadCalcular;
  window.dadMostrar = dadMostrar;
  window.dadGenerarPDF = dadGenerarPDF;
});
