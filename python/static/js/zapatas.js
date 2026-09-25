/* ============================================================
   CimX — Módulo de Zapatas (frontend)
   Zapata aislada: dimensionamiento geotécnico + diseño estructural.
   Reusa helpers globales de cimx.js: $, $$, toSI, fromSI, toast.
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
  const chk = (id, dv) => { const e = $('#' + id); return e ? e.checked : dv; };
  const numv = (id, dv) => { const e = $('#' + id); const v = e ? parseFloat(e.value) : NaN; return isNaN(v) ? dv : v; };
  return {
    tipo: ($('#zap_tipo') && $('#zap_tipo').value) || 'aislada',
    forma: ($('#zap_forma') && $('#zap_forma').value) || 'cuadrada',
    // Columna 1 (sirve también como la única en aislada)
    c1: zReadMag($('#zap_c1')), c2: zReadMag($('#zap_c2')),
    P_servicio: zReadMag($('#zap_P')) || 0,
    M_servicio: zReadMag($('#zap_M')) || 0,
    My_servicio: zReadMag($('#zap_My')) || 0,
    Pu: zReadMag($('#zap_Pu')) || 0,
    factor_carga: numv('zap_fcarga', 1.5),
    q_adm: zReadMag($('#zap_qadm')) || 0,
    Df: zReadMag($('#zap_Df')) || 0,
    gamma_suelo: zReadMag($('#zap_gs')) || 18,
    gamma_concreto: zReadMag($('#zap_gc')) || 24,
    posicion: $('#zap_pos').value,
    fc: zReadMag($('#zap_fc')), fy: zReadMag($('#zap_fy')),
    db: (numv('zap_db', 19.05)) / 1000.0,   // mm → m
    recubrimiento: zReadMag($('#zap_rec')),
    B: zReadMag($('#zap_B')) || 0,
    L: zReadMag($('#zap_L')) || 0,
    h: zReadMag($('#zap_h')) || 0,
    relacion_LB: numv('zap_relLB', 1.0),
    // Combinada
    c1a: zReadMag($('#zap_c1')), c2a: zReadMag($('#zap_c2')),
    P1_servicio: zReadMag($('#zap_P')) || 0,
    c1b: zReadMag($('#zap_c1b')), c2b: zReadMag($('#zap_c2b')),
    P2_servicio: zReadMag($('#zap_P2')) || 0,
    separacion: zReadMag($('#zap_sep')) || 0,
    medianeria_izquierda: chk('zap_mediz', true),
    // Esquinera
    viga_centradora: chk('zap_viga', true),
    // Triangular
    base: zReadMag($('#zap_base')) || 0,
    altura: zReadMag($('#zap_altura')) || 0,
  };
}

/* Muestra/oculta los campos según el tipo y la forma de zapata. */
function zapAplicarTipo() {
  const t = ($('#zap_tipo') && $('#zap_tipo').value) || 'aislada';
  const forma = ($('#zap_forma') && $('#zap_forma').value) || 'cuadrada';
  document.querySelectorAll('.ztipo-cond').forEach(el => {
    const tipos = (el.getAttribute('data-ztipo') || '').split(/\s+/).filter(Boolean);
    el.style.display = tipos.includes(t) ? '' : 'none';
  });
  // Campos que dependen de la FORMA (solo aplican a la aislada).
  document.querySelectorAll('.zforma-cond').forEach(el => {
    const fs = (el.getAttribute('data-zforma') || '').split(/\s+/).filter(Boolean);
    el.style.display = (t === 'aislada' && fs.includes(forma)) ? '' : 'none';
  });
  const t1 = $('#zap-col1-title');
  if (t1) t1.textContent = (t === 'combinada') ? 'Columna 1 y cargas' : 'Columna y cargas';
  const hint = $('#zap-tipo-hint');
  if (hint) {
    const H = {
      aislada: 'Una columna. Elige forma (cuadrada/rectangular); es concéntrica si M=0, o excéntrica con Mₓ/M_y.',
      combinada: 'Dos columnas sobre una zapata rectangular que trabaja como viga longitudinal.',
      conectada: 'Columna de medianería/esquina unida por una viga de enlace (centradora) a una zapata interior.',
      triangular: 'Planta triangular con la columna en el baricentro (caso especial).',
    };
    hint.textContent = H[t] || '';
  }
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

const _zset = (id, v) => { const el = $('#' + id); if (el) el.textContent = v; };
const _zok = (b) => b ? '<span style="color:var(--green-300)">cumple</span>'
                      : '<span style="color:var(--status-err-tx)">no cumple</span>';
const _zavisos = (res) => (res.avisos && res.avisos.length)
  ? `<div class="hint" style="border-color:var(--status-warn-bd);color:var(--status-warn-tx)">⚠ ${res.avisos.join('<br>⚠ ')}</div>` : '';

function zapRender(res) {
  const t = res.tipo || 'aislada';
  if (t === 'combinada') return zapRenderCombinada(res);
  if (t === 'triangular') return zapRenderTriangular(res);
  return zapRenderAislada(res);
}

function zapRenderCombinada(res) {
  const g = res.geometria, geo = res.geotecnico, e = res.estructural;
  const asMax = Math.max(e.flexion_long_inferior.As_cm2, e.flexion_long_superior.As_cm2,
                         e.flexion_transversal_col1.As_cm2, e.flexion_transversal_col2.As_cm2);
  _zset('zk-bl', `${g.B_m}×${g.L_m}`);
  _zset('zk-h', g.h_m); _zset('zk-d', g.d_m);
  _zset('zk-q', _ztp(geo.q_max_kPa).toFixed(1));
  _zset('zk-punz', Math.max(e.punzonamiento_col1.ratio || 0, e.punzonamiento_col2.ratio || 0));
  _zset('zk-as', asMax.toFixed(1));
  $('#zap-detalle').innerHTML = `
    <div class="pil-line"><b>Zapata combinada</b> · viga longitudinal ${g.L_m}×${g.B_m} m ·
      columnas en x=${g.x1_col_m} y x=${g.x2_col_m} m (sep. ${g.separacion_m} m)</div>
    <div class="pil-line"><b>Geotecnia:</b> P total ${_ztf(geo.P_total_servicio_kN).toFixed(1)} tonf ·
      excentricidad ${geo.excentricidad_m} m · q<sub>máx</sub> ${_ztp(geo.q_max_kPa).toFixed(1)} /
      q<sub>adm</sub> ${_ztp(geo.q_adm_kPa).toFixed(1)} tonf/m² → ${_zok(geo.cumple)} (D/C=${geo.ratio})</div>
    <div class="pil-line"><b>Viga:</b> M⁺=${_ztm(e.M_pos_kNm).toFixed(1)} (x=${e.x_M_pos_m} m, acero inferior) ·
      M⁻=${_ztm(e.M_neg_kNm).toFixed(1)} tonf·m (x=${e.x_M_neg_m} m, acero superior) ·
      V<sub>máx</sub>=${_ztf(e.V_max_kN).toFixed(1)} tonf → ${_zok(e.cumple_v_long)}</div>
    <div class="pil-line"><b>Punzonamiento:</b> col.1 D/C=${e.punzonamiento_col1.ratio} ${_zok(e.punzonamiento_col1.cumple)} ·
      col.2 D/C=${e.punzonamiento_col2.ratio} ${_zok(e.punzonamiento_col2.cumple)}</div>
    <table class="pil-table" style="margin-top:8px">
      <thead><tr><th>Refuerzo</th><th style="text-align:right">Mu (tonf·m)</th><th style="text-align:right">As (cm²)</th><th style="text-align:right">Barras</th></tr></thead>
      <tbody>
        ${_zfila(e.flexion_long_inferior, 'Longitudinal inferior (M⁺)')}
        ${_zfila(e.flexion_long_superior, 'Longitudinal superior (M⁻)')}
        ${_zfila(e.flexion_transversal_col1, 'Transversal col. 1')}
        ${_zfila(e.flexion_transversal_col2, 'Transversal col. 2')}
      </tbody>
    </table>
    ${_zavisos(res)}`;
}

function zapRenderTriangular(res) {
  const g = res.geometria, geo = res.geotecnico, e = res.estructural;
  _zset('zk-bl', `${g.base_m}×${g.altura_m}`);
  _zset('zk-h', g.h_m); _zset('zk-d', g.d_m);
  _zset('zk-q', _ztp(geo.q_max_kPa).toFixed(1));
  _zset('zk-punz', e.punzonamiento.ratio);
  _zset('zk-as', e.flexion.As_cm2.toFixed ? e.flexion.As_cm2.toFixed(1) : e.flexion.As_cm2);
  $('#zap-detalle').innerHTML = `
    <div class="pil-line"><b>Zapata triangular</b> · base ${g.base_m} m × altura ${g.altura_m} m ·
      A=${g.area_m2} m² (lado eq. ${g.lado_equivalente_m} m)</div>
    <div class="pil-line"><b>Geotecnia:</b> P total ${_ztf(geo.P_total_servicio_kN).toFixed(1)} tonf ·
      q<sub>unif</sub> ${_ztp(geo.q_uniforme_kPa).toFixed(1)} / q<sub>adm</sub> ${_ztp(geo.q_adm_kPa).toFixed(1)} tonf/m²
      → ${_zok(geo.cumple)} (D/C=${geo.ratio})</div>
    <div class="pil-line"><b>Punzonamiento:</b> D/C=${e.punzonamiento.ratio} ${_zok(e.punzonamiento.cumple)} ·
      <b>Cortante 1 vía:</b> D/C=${e.una_via.ratio} ${_zok(e.una_via.cumple)}</div>
    <table class="pil-table" style="margin-top:8px">
      <thead><tr><th>Flexión (aprox. eq.)</th><th style="text-align:right">Mu</th><th style="text-align:right">As (cm²)</th><th style="text-align:right">Barras</th></tr></thead>
      <tbody>${_zfila(e.flexion, 'Ambas direcciones')}</tbody>
    </table>
    ${_zavisos(res)}`;
}

function _zfila(f, dir) {
  return `<tr><td>${dir}</td>
    <td style="text-align:right">${_ztm(f.Mu_kNm).toFixed(2)}</td>
    <td style="text-align:right">${f.As_cm2}${f.gobierna_minimo ? ' <span class="muted">(mín)</span>' : ''}</td>
    <td style="text-align:right">${f.n_barras} Ø${f.db_mm} @ ${f.sep_cm} cm</td></tr>`;
}

function zapRenderAislada(res) {
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
  const t = res.tipo || 'aislada';
  if (t === 'combinada') return zapDibujarCombinada(res, cont);
  if (t === 'triangular') return zapDibujarTriangular(res, cont);
  return zapDibujarAislada(res, cont);
}

const _ZCOL = { bg: '#0d1c16', concrete: '#6f7a83', col: '#9aa6ae', soil: '#caa86a',
                txt: '#eaf2ee', sub: '#9fc0b2', steel: '#e07a3a', edge: '#1f262c', arrow: '#e7c46b' };

function zapDibujarCombinada(res, cont) {
  const g = res.geometria, e = res.estructural, C = _ZCOL;
  const W = 460, H = 300, m = 40;
  const s = (W - 2 * m) / g.L_m;
  const bl = g.L_m * s, bw = Math.min(120, g.B_m * s);
  const x0 = m, y0 = 90;
  let svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${W} ${H}" width="100%" height="100%"
    style="display:block;background:${C.bg};border-radius:10px;font-family:'Inter',system-ui,sans-serif">
    <text x="${W/2}" y="24" font-size="12" font-weight="700" fill="${C.txt}" text-anchor="middle">ZAPATA COMBINADA — planta</text>`;
  svg += `<rect x="${x0}" y="${y0}" width="${bl.toFixed(1)}" height="${bw.toFixed(1)}" fill="${C.concrete}" fill-opacity="0.30" stroke="${C.concrete}" stroke-width="1.6"/>`;
  [g.x1_col_m, g.x2_col_m].forEach((xc, i) => {
    const cx = x0 + xc * s, cw = 14;
    svg += `<rect x="${(cx - cw/2).toFixed(1)}" y="${(y0 + bw/2 - cw/2).toFixed(1)}" width="${cw}" height="${cw}" fill="${C.col}" stroke="${C.edge}"/>`;
    svg += `<text x="${cx.toFixed(1)}" y="${(y0 - 6).toFixed(1)}" font-size="10" fill="${C.txt}" text-anchor="middle">C${i+1}</text>`;
  });
  // presión uniforme (flechas)
  for (let i = 0; i <= 10; i++) { const xx = x0 + bl * i / 10;
    svg += `<line x1="${xx.toFixed(1)}" y1="${(y0+bw+26).toFixed(1)}" x2="${xx.toFixed(1)}" y2="${(y0+bw+4).toFixed(1)}" stroke="${C.arrow}" stroke-width="1.1"/>`; }
  svg += `<text x="${(x0+bl/2).toFixed(1)}" y="${(y0+bw+42).toFixed(1)}" font-size="10" fill="${C.arrow}" text-anchor="middle">q_u = ${_ztp(e.qu_kPa).toFixed(1)} tonf/m²</text>`;
  svg += `<text x="${(x0+bl/2).toFixed(1)}" y="${(y0+bw+62).toFixed(1)}" font-size="11" fill="${C.txt}" text-anchor="middle">L = ${g.L_m} m · B = ${g.B_m} m · h = ${g.h_m} m</text>`;
  svg += `</svg>`;
  cont.innerHTML = svg;
}

function zapDibujarTriangular(res, cont) {
  const g = res.geometria, e = res.estructural, C = _ZCOL;
  const W = 460, H = 300, m = 50;
  const s = Math.min((W - 2*m) / g.base_m, (H - 2*m - 30) / g.altura_m) * 0.9;
  const bw = g.base_m * s, ht = g.altura_m * s;
  const cx = W/2, by = H - m;
  const p1 = [cx - bw/2, by], p2 = [cx + bw/2, by], p3 = [cx, by - ht];
  const gx = (p1[0]+p2[0]+p3[0])/3, gy = (p1[1]+p2[1]+p3[1])/3;
  let svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${W} ${H}" width="100%" height="100%"
    style="display:block;background:${C.bg};border-radius:10px;font-family:'Inter',system-ui,sans-serif">
    <text x="${W/2}" y="24" font-size="12" font-weight="700" fill="${C.txt}" text-anchor="middle">ZAPATA TRIANGULAR — planta</text>`;
  svg += `<polygon points="${p1[0].toFixed(1)},${p1[1].toFixed(1)} ${p2[0].toFixed(1)},${p2[1].toFixed(1)} ${p3[0].toFixed(1)},${p3[1].toFixed(1)}" fill="${C.concrete}" fill-opacity="0.30" stroke="${C.concrete}" stroke-width="1.6"/>`;
  svg += `<rect x="${(gx-7).toFixed(1)}" y="${(gy-7).toFixed(1)}" width="14" height="14" fill="${C.col}" stroke="${C.edge}"/>`;
  svg += `<text x="${gx.toFixed(1)}" y="${(gy-12).toFixed(1)}" font-size="10" fill="${C.txt}" text-anchor="middle">columna (baricentro)</text>`;
  svg += `<text x="${cx.toFixed(1)}" y="${(by+22).toFixed(1)}" font-size="11" fill="${C.txt}" text-anchor="middle">base = ${g.base_m} m · altura = ${g.altura_m} m · h = ${g.h_m} m</text>`;
  svg += `<text x="${cx.toFixed(1)}" y="${(by+40).toFixed(1)}" font-size="10" fill="${C.arrow}" text-anchor="middle">q_u = ${_ztp(e.qu_kPa).toFixed(1)} tonf/m² (uniforme)</text>`;
  svg += `</svg>`;
  cont.innerHTML = svg;
}

/* ---------- Esquema aislada: planta + sección (SVG) ---------- */
function zapDibujarAislada(res, cont) {
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
  // El visor 3D solo aplica a la zapata aislada (rectangular con una columna).
  const g0 = _zapLast.geometria || {};
  const soporta3D = (g0.c1_m !== undefined && g0.B_m !== undefined);
  if (_vista3D_zap && soporta3D && window.CimXFooting3D && CimXFooting3D.isAvailable()) {
    const g = _zapLast.geometria;
    try {
      CimXFooting3D.render({
        B: g.B_m, L: g.L_m, h: g.h_m, c1: g.c1_m, c2: g.c2_m,
        Df: (_zapLastPayload && _zapLastPayload.Df) || 1.5,
      }, cont);
    } catch (e) {
      console.error('[footing3d]', e);
      if (window.CimXFooting3D) CimXFooting3D.dispose();
      zapDibujar(_zapLast);
    }
  } else {
    if (window.CimXFooting3D) CimXFooting3D.dispose();
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
    const filename = `CimX-zapata-${(payload.proyecto || 'memoria').replace(/[^a-z0-9]/gi, '_')}.pdf`;
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

  // Selector de tipo/forma de zapata → muestra/oculta campos
  const selTipo = $('#zap_tipo');
  const selForma = $('#zap_forma');
  if (selTipo) selTipo.addEventListener('change', zapAplicarTipo);
  if (selForma) selForma.addEventListener('change', zapAplicarTipo);
  if (selTipo) zapAplicarTipo();

  window.zapAplicarTipo = zapAplicarTipo;
  window.zapCalcular = zapCalcular;
  window.zapMostrar = zapMostrar;
  window.zapGenerarPDF = zapGenerarPDF;
});
