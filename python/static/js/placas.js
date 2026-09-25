/* ============================================================
   CimX — Módulo de Placas macizas (frontend)
   Losa de cimentación maciza (mat) · método rígido convencional.
   Reusa helpers globales de cimx.js: $, $$, toSI, fromSI, toast.
   Entradas en MKS (display) → SI al backend (/api/placa).
   ============================================================ */
'use strict';

let _plLast = null;
let _plLastPayload = null;

function _plMag(el) {
  if (!el) return null;
  const v = parseFloat(el.value);
  if (isNaN(v)) return null;
  return el.dataset.mag ? toSI(v, el.dataset.mag) : v;
}

function plRecolectar() {
  const numv = (id, dv) => { const e = $('#' + id); const v = e ? parseFloat(e.value) : NaN; return isNaN(v) ? dv : v; };
  return {
    nx: Math.max(1, Math.round(numv('pl_nx', 3))),
    ny: Math.max(1, Math.round(numv('pl_ny', 3))),
    sx: _plMag($('#pl_sx')) || 0,
    sy: _plMag($('#pl_sy')) || 0,
    P: _plMag($('#pl_P')) || 0,
    factor_carga: numv('pl_fcarga', 1.5),
    c1: _plMag($('#pl_c1')) || 0.40,
    c2: _plMag($('#pl_c2')) || 0.40,
    q_adm: _plMag($('#pl_qadm')) || 0,
    voladizo: _plMag($('#pl_vol')) || 0,
    Df: _plMag($('#pl_Df')) || 0,
    gamma_suelo: _plMag($('#pl_gs')) || 18,
    gamma_concreto: _plMag($('#pl_gc')) || 24,
    fc: _plMag($('#pl_fc')), fy: _plMag($('#pl_fy')),
    db: numv('pl_db', 19.05) / 1000.0,   // mm → m
    recubrimiento: _plMag($('#pl_rec')),
    B: _plMag($('#pl_B')) || 0,
    L: _plMag($('#pl_L')) || 0,
    h: _plMag($('#pl_h')) || 0,
  };
}

const _pltf = kN => fromSI(kN, 'force');       // kN → tonf
const _pltp = kPa => fromSI(kPa, 'pressure');  // kPa → tonf/m²
const _pltm = kNm => fromSI(kNm, 'moment');    // kN·m → tonf·m
const _plset = (id, v) => { const el = $('#' + id); if (el) el.textContent = v; };
const _plok = (b) => b ? '<span style="color:var(--green-300)">cumple</span>'
                      : '<span style="color:var(--status-err-tx)">no cumple</span>';

async function plCalcular() {
  const payload = plRecolectar();
  if (!payload.P) { toast('Define la carga por columna P', 'err'); return; }
  if (!payload.q_adm) { toast('Define la capacidad admisible q_adm', 'err'); return; }
  const btn = $('#btn-placa-calc-h');
  const lbl = btn && (btn.querySelector('span') || btn);
  if (btn) btn.disabled = true;
  if (lbl) lbl.textContent = 'Calculando…';
  try {
    const r = await fetch('/api/placa', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await r.json();
    if (!data.ok) { toast(data.error || 'Error en el cálculo', 'err', 6000); }
    else { _plLastPayload = payload; _plLast = data; plRender(data); plDibujar(data); toast('Cálculo completado', 'ok'); }
  } catch (e) {
    toast('No se pudo conectar con el servidor', 'err');
  } finally {
    if (btn) btn.disabled = false;
    if (lbl) lbl.textContent = 'Calcular';
  }
}

function _pAsMax(e) {
  const f = [e.franja_x.acero_inferior, e.franja_x.acero_superior,
             e.franja_y.acero_inferior, e.franja_y.acero_superior];
  return Math.max.apply(null, f.map(a => a.As_cm2));
}

function _pFranjaFilas(fr, nom) {
  const row = (a, cara) => `<tr><td>${nom} · ${cara}</td>
    <td style="text-align:right">${_pltm(cara === 'inferior (M⁺)' ? fr.M_pos_kNm : fr.M_neg_kNm).toFixed(1)}</td>
    <td style="text-align:right">${a.As_cm2}${a.gobierna_minimo ? ' <span class="muted">(mín)</span>' : ''}</td>
    <td style="text-align:right">${a.n_barras} Ø${a.db_mm} @ ${a.sep_cm} cm</td></tr>`;
  return row(fr.acero_inferior, 'inferior (M⁺)') + row(fr.acero_superior, 'superior (M⁻)');
}

function plRender(res) {
  const g = res.geometria, geo = res.geotecnico, e = res.estructural;
  _plset('pk-bl', `${g.B_m}×${g.L_m}`);
  _plset('pk-h', g.h_m);
  _plset('pk-d', g.d_m);
  _plset('pk-q', _pltp(geo.q_max_kPa).toFixed(1));
  _plset('pk-punz', e.punz_critico.ratio);
  _plset('pk-as', _pAsMax(e).toFixed(1));

  const pc = e.punz_critico;
  const avisos = (res.avisos && res.avisos.length)
    ? `<div class="hint" style="border-color:var(--status-warn-bd);color:var(--status-warn-tx)">⚠ ${res.avisos.join('<br>⚠ ')}</div>` : '';

  $('#placa-detalle').innerHTML = `
    <div class="pil-line"><b>Losa maciza</b> ${g.B_m}×${g.L_m} m · ${g.n_columnas} columnas ·
      voladizo ${g.voladizo_m} m · volumen ${g.volumen_concreto_m3} m³</div>
    <div class="pil-line"><b>Geotecnia (método rígido):</b> R ${_pltf(geo.R_servicio_kN).toFixed(1)} tonf ·
      e=(${geo.e_x_m}, ${geo.e_y_m}) m · q<sub>máx</sub> ${_pltp(geo.q_max_kPa).toFixed(1)} /
      q<sub>mín</sub> ${_pltp(geo.q_min_kPa).toFixed(1)} / q<sub>adm</sub> ${_pltp(geo.q_adm_kPa).toFixed(1)} tonf/m²
      → ${_plok(geo.cumple)} (D/C=${geo.ratio})</div>
    <div class="pil-line"><b>Punzonamiento crítico:</b> columna #${pc.columna} (${pc.posicion}) ·
      V<sub>u</sub>=${_pltf(pc.Vu_kN).toFixed(1)} φV<sub>c</sub>=${_pltf(pc.phiVc_kN).toFixed(1)} tonf
      → ${_plok(pc.cumple)} (D/C=${pc.ratio})</div>
    <div class="pil-line"><b>Cortante viga ancha:</b> franja X ${_plok(e.franja_x.cumple_cortante)} ·
      franja Y ${_plok(e.franja_y.cumple_cortante)}</div>
    <table class="pil-table" style="margin-top:8px">
      <thead><tr><th>Franja / cara</th><th style="text-align:right">M (tonf·m)</th><th style="text-align:right">As (cm²)</th><th style="text-align:right">Distribución</th></tr></thead>
      <tbody>${_pFranjaFilas(e.franja_x, 'X')}${_pFranjaFilas(e.franja_y, 'Y')}</tbody>
    </table>
    ${avisos}`;
}

/* ---------- Esquema: planta con columnas + presiones (SVG) ---------- */
const _PLCOL = { bg: '#0d1c16', concrete: '#6f7a83', col: '#9aa6ae', soil: '#caa86a',
                txt: '#eaf2ee', sub: '#9fc0b2', steel: '#e07a3a', edge: '#1f262c',
                arrow: '#e7c46b', hot: '#e0713a', centro: '#e0713a' };

function plDibujar(res) {
  const cont = $('#placa-preview');
  if (!cont) return;
  const g = res.geometria, geo = res.geotecnico, C = _PLCOL;
  const B = g.B_m, L = g.L_m;
  const W = 460, H = 430, m = 54;
  const s = Math.min((W - 2 * m) / B, (H - 2 * m - 20) / L);
  const bw = B * s, bl = L * s;
  const x0 = (W - bw) / 2, y0 = 54;

  let svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${W} ${H}" width="100%" height="100%"
    style="display:block;background:${C.bg};border-radius:10px;font-family:'Inter',system-ui,sans-serif">
    <text x="${W/2}" y="24" font-size="12" font-weight="700" fill="${C.txt}" text-anchor="middle">PLANTA — losa maciza (${g.n_columnas} columnas)</text>`;
  // losa (nota: y del SVG crece hacia abajo → invertimos y para que el origen quede abajo-izq.)
  svg += `<rect x="${x0.toFixed(1)}" y="${y0.toFixed(1)}" width="${bw.toFixed(1)}" height="${bl.toFixed(1)}"
            fill="${C.concrete}" fill-opacity="0.28" stroke="${C.concrete}" stroke-width="1.6"/>`;
  const PX = xm => x0 + xm * s;
  const PY = ym => y0 + (L - ym) * s;   // invierte Y
  // columnas
  (g.columnas || []).forEach(c => {
    const cw = Math.max(7, c.c1_m * s), ch = Math.max(7, c.c2_m * s);
    svg += `<rect x="${(PX(c.x_m) - cw/2).toFixed(1)}" y="${(PY(c.y_m) - ch/2).toFixed(1)}" width="${cw.toFixed(1)}" height="${ch.toFixed(1)}"
              fill="${C.col}" stroke="${C.edge}" stroke-width="1"/>`;
  });
  // centroide de cargas
  svg += `<circle cx="${PX(geo.x_centroide_carga_m).toFixed(1)}" cy="${PY(geo.y_centroide_carga_m).toFixed(1)}" r="4" fill="${C.centro}"/>`;
  // presiones en las esquinas (tonf/m²)
  const esq = geo.esquinas_kPa || {};
  const lab = (xm, ym, key, dx, dy, anchor) => {
    if (esq[key] === undefined) return '';
    return `<text x="${(PX(xm) + dx).toFixed(1)}" y="${(PY(ym) + dy).toFixed(1)}" font-size="10" font-weight="700"
              fill="${C.arrow}" text-anchor="${anchor}">${_pltp(esq[key]).toFixed(1)}</text>`;
  };
  svg += lab(0, 0, 'q_00', -4, 14, 'end');
  svg += lab(B, 0, 'q_B0', 4, 14, 'start');
  svg += lab(0, L, 'q_0L', -4, -6, 'end');
  svg += lab(B, L, 'q_BL', 4, -6, 'start');
  // cotas
  svg += `<text x="${(x0 + bw/2).toFixed(1)}" y="${(y0 + bl + 26).toFixed(1)}" font-size="11" fill="${C.txt}" text-anchor="middle">B = ${B.toFixed(2)} m</text>`;
  svg += `<text x="${(x0 - 16).toFixed(1)}" y="${(y0 + bl/2).toFixed(1)}" font-size="11" fill="${C.txt}" text-anchor="middle" transform="rotate(-90 ${(x0 - 16).toFixed(1)} ${(y0 + bl/2).toFixed(1)})">L = ${L.toFixed(2)} m</text>`;
  svg += `<text x="${(W/2).toFixed(1)}" y="${(H - 10).toFixed(1)}" font-size="10" fill="${C.sub}" text-anchor="middle">presiones de esquina en tonf/m² · • centroide de cargas · h = ${g.h_m} m</text>`;
  svg += `</svg>`;
  cont.innerHTML = svg;
}

/* ---------- Memoria de cálculo (PDF) ---------- */
async function plGenerarPDF(btn) {
  const payload = plRecolectar();
  if (!payload.P) { toast('Define la carga por columna P', 'err'); return; }
  if (!payload.q_adm) { toast('Define la capacidad admisible q_adm', 'err'); return; }
  const val = id => { const e = $('#' + id); return e ? e.value : ''; };
  payload.proyecto = val('proyecto');
  payload.ingeniero = val('ingeniero');
  payload.ubicacion = val('ubicacion');
  payload.empresa = val('empresa');
  const old = btn ? btn.innerHTML : '';
  if (btn) { btn.disabled = true; btn.textContent = 'Generando…'; }
  try {
    const r = await fetch('/api/placa_pdf', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!r.ok) { const j = await r.json().catch(() => ({})); toast('Error PDF: ' + (j.error || r.status), 'err', 6000); return; }
    const blob = await r.blob();
    const filename = `CimX-placa-${(payload.proyecto || 'memoria').replace(/[^a-z0-9]/gi, '_')}.pdf`;
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
  const bCalcH = $('#btn-placa-calc-h');
  if (bCalcH) bCalcH.addEventListener('click', () => { if (typeof showView === 'function') showView('placa'); plCalcular(); });
  const bPdfH = $('#btn-placa-pdf-h');
  if (bPdfH) bPdfH.addEventListener('click', () => plGenerarPDF(bPdfH));
  const bpdf2 = $('#btn-placa-pdf-2');
  if (bpdf2) bpdf2.addEventListener('click', () => plGenerarPDF(bpdf2));

  window.plCalcular = plCalcular;
  window.plGenerarPDF = plGenerarPDF;
});
