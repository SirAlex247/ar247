/* ============================================================
   CimX — Módulo de Muros de Tierra Armada / MSE (frontend)
   Método simplificado FHWA (NHI-10-024) / AASHTO:
   estabilidad interna (rotura y arrancamiento capa a capa) y externa.
   Reusa helpers globales de cimx.js: $, $$, toSI, toast.
   Entradas en MKS (display) → SI al backend (/api/mse).
   ============================================================ */
'use strict';

let _mseLast = null;

function mseRecolectar() {
  const raw = id => { const e = $('#' + id); const v = e ? parseFloat(e.value) : NaN; return isNaN(v) ? null : v; };
  return {
    H:  inputSI('mse_H') || 6.0,
    L:  inputSI('mse_L') || 4.2,
    Sv: inputSI('mse_Sv') || 0.6,
    sobrecarga: inputSI('mse_q') || 0,
    tipo_refuerzo: ($('#mse_tipo') && $('#mse_tipo').value) || 'geosintetico',
    Ta: raw('mse_Ta') != null ? raw('mse_Ta') : 30.0,          // kN/m (directo)
    F_pullout: raw('mse_F'),                                    // opcional
    Rc: raw('mse_Rc') != null ? raw('mse_Rc') : 1.0,
    gamma_r: inputSI('mse_gr'), phi_r: raw('mse_pr'),
    gamma_b: inputSI('mse_gb'), phi_b: raw('mse_pb'),
    gamma_f: inputSI('mse_gf'), phi_f: raw('mse_pf'),
    c_f: inputSI('mse_cf') || 0,
  };
}

async function mseCalcular() {
  const payload = mseRecolectar();
  const btn = $('#btn-mse-calc');
  const lbl = btn && (btn.querySelector('span') || btn);
  if (btn) btn.disabled = true;
  if (lbl) lbl.textContent = 'Calculando…';
  try {
    const r = await fetch('/api/mse', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await r.json();
    if (!data.ok) { toast(data.error || 'Error en el cálculo', 'err', 6000); }
    else { _mseLast = data; mseRender(data); toast('Cálculo completado', 'ok'); }
  } catch (e) {
    toast('No se pudo conectar con el servidor', 'err');
  } finally {
    if (btn) btn.disabled = false;
    if (lbl) lbl.textContent = 'Calcular';
  }
}

function _mseFS(v, obj) {
  const cls = (v >= obj) ? 'var(--status-ok-tx)' : 'var(--status-err-tx)';
  return `<span style="color:${cls}">${v.toFixed(2)}</span>`;
}

function mseRender(j) {
  const set = (id, html) => { const el = $('#' + id); if (el) el.innerHTML = html; };
  const rs = j.resumen, ext = j.externa, ob = (j.parametros.objetivos || {});
  set('msek-rot', _mseFS(rs.FS_rotura_min, ob.rotura || 1.0));
  set('msek-po', _mseFS(rs.FS_pullout_min, ob.pullout || 1.5));
  set('msek-n', `${j.n_capas}`);
  const nEl = $('#msek-n'); if (nEl) nEl.parentElement.querySelector('.kpi-unit').textContent = `@ ${j.Sv.toFixed(2)} m`;
  set('msek-desl', _mseFS(ext.FS_deslizamiento, ob.deslizamiento || 1.5));
  set('msek-volc', _mseFS(ext.FS_volcamiento, ob.volcamiento || 2.0));
  set('msek-cap', _mseFS(ext.FS_capacidad, ob.capacidad || 2.5));

  // Badge de estado
  const badge = $('#mse-estado');
  if (badge) {
    badge.style.display = '';
    badge.className = 'state ' + (j.cumple ? 'ok' : 'err');
    badge.innerHTML = `<span class="dot"></span>${j.cumple ? 'CUMPLE ✓' : 'REVISAR ✗'}`;
  }

  // Detalle externo
  const okTxt = b => b ? '<span style="color:var(--status-ok-tx)">cumple</span>'
                       : '<span style="color:var(--status-err-tx)">no cumple</span>';
  const _tf = kN => (kN / 9.80665);   // kN → tonf
  let det = `
    <div class="pil-line"><b>Estabilidad interna:</b> FS rotura mín = ${rs.FS_rotura_min.toFixed(2)} (capa ${rs.capa_critica_rotura}) · FS arrancamiento mín = ${rs.FS_pullout_min.toFixed(2)} (capa ${rs.capa_critica_pullout}) → ${okTxt(rs.interna_ok)}</div>
    <div class="pil-line"><b>Empuje del relleno retenido:</b> Pa = ${_tf(ext.Pa_kN).toFixed(2)} tonf/m · peso del bloque W = ${_tf(ext.W_kN).toFixed(2)} tonf/m</div>
    <div class="pil-line"><b>Excentricidad:</b> e = ${ext.e_m.toFixed(3)} m (máx ${ext.e_max_m.toFixed(3)} m) ${okTxt(ext.cumple_excentricidad)} · B efectivo = ${ext.L_efectivo_m.toFixed(2)} m</div>
    <div class="pil-line"><b>Capacidad portante:</b> q_ref = ${(ext.q_referencia_kPa/9.80665).toFixed(1)} tonf/m² vs q_ult = ${(ext.q_ultimo_kPa/9.80665).toFixed(1)} tonf/m² ${okTxt(ext.cumple_capacidad)}</div>`;
  const avisos = (j.avisos && j.avisos.length)
    ? `<div class="hint" style="border-color:var(--status-warn-bd);color:var(--status-warn-tx);margin-top:8px">⚠ ${j.avisos.join('<br>⚠ ')}</div>` : '';
  set('mse-detalle', det + avisos);

  // Esquema (imagen del backend)
  const prev = $('#mse-preview');
  if (prev) {
    prev.innerHTML = j.imagen
      ? `<img src="${j.imagen}" alt="Esquema MSE" style="max-width:100%;height:auto;border-radius:8px">`
      : '<div style="padding:36px;color:var(--text-muted)">Sin esquema disponible</div>';
  }

  // Tabla de capas
  const card = $('#mse-capas-card'), wrap = $('#mse-capas-wrap');
  if (card && wrap) {
    card.style.display = '';
    // Submuestreo a ~16 filas
    const capas = j.capas || [];
    const paso = Math.max(1, Math.floor(capas.length / 16));
    let html = `<table><thead><tr>
      <th>#</th><th class="text-right">z (m)</th><th class="text-right">σv (kPa)</th><th class="text-right">Kr</th>
      <th class="text-right">Tmax (kN/m)</th><th class="text-right">Le (m)</th>
      <th class="text-right">FS rot.</th><th class="text-right">FS pull.</th><th>Estado</th>
    </tr></thead><tbody>`;
    for (let i = 0; i < capas.length; i += paso) {
      const c = capas[i];
      const ok = c.cumple_rotura && c.cumple_pullout;
      html += `<tr>
        <td class="muted">${c.i}</td>
        <td class="table-num">${c.z.toFixed(2)}</td><td class="table-num">${c.sigma_v.toFixed(1)}</td>
        <td class="table-num">${c.Kr.toFixed(3)}</td><td class="table-num">${c.Tmax.toFixed(2)}</td>
        <td class="table-num">${c.Le.toFixed(2)}</td>
        <td class="table-num">${c.FS_rotura.toFixed(2)}</td><td class="table-num">${c.FS_pullout.toFixed(2)}</td>
        <td><span class="state ${ok ? 'ok' : 'err'}" style="padding:2px 8px;font-size:10.5px"><span class="dot"></span>${ok ? 'OK' : 'REVISAR'}</span></td>
      </tr>`;
    }
    html += '</tbody></table>';
    wrap.innerHTML = html;
  }
}

async function mseGenerarPDF(btn) {
  const payload = mseRecolectar();
  const val = id => { const e = $('#' + id); return e ? e.value : ''; };
  payload.proyecto = val('proyecto');
  payload.ingeniero = val('ingeniero');
  payload.ubicacion = val('ubicacion');
  payload.empresa = val('empresa');
  const old = btn ? btn.innerHTML : '';
  if (btn) { btn.disabled = true; btn.textContent = 'Generando…'; }
  try {
    const r = await fetch('/api/mse_pdf', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!r.ok) { const j = await r.json().catch(() => ({})); toast('Error PDF: ' + (j.error || r.status), 'err', 6000); return; }
    const blob = await r.blob();
    const filename = `CimX-MSE-${(payload.proyecto || 'memoria').replace(/[^a-z0-9]/gi, '_')}.pdf`;
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

document.addEventListener('DOMContentLoaded', () => {
  const bc = $('#btn-mse-calc');
  if (bc) bc.addEventListener('click', mseCalcular);
  const bp = $('#btn-mse-pdf');
  if (bp) bp.addEventListener('click', () => mseGenerarPDF(bp));
  window.mseCalcular = mseCalcular;
});
