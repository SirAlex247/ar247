/* ============================================================
   CimX — Módulo de Muros Anclados (frontend)
   Método de las presiones aparentes (Terzaghi-Peck / FHWA GEC-4):
   envolvente de presión, cargas de anclaje (área tributaria),
   longitud de bulbo y libre, y momento de la pantalla.
   Reusa helpers globales de cimx.js: $, toSI, toast.
   Entradas en MKS (display) → SI al backend (/api/muro_anclado).
   ============================================================ */
'use strict';

let _ancLast = null;

function ancRecolectar() {
  const raw = id => { const e = $('#' + id); const v = e ? parseFloat(e.value) : NaN; return isNaN(v) ? null : v; };
  return {
    H: inputSI('anc_H') || 10.0,
    tipo_suelo: ($('#anc_tipo') && $('#anc_tipo').value) || 'arena',
    gamma: inputSI('anc_gamma'),
    phi: raw('anc_phi') != null ? raw('anc_phi') : 30.0,
    Su: inputSI('anc_Su') || 0,
    sobrecarga: inputSI('anc_q') || 0,
    n_anclajes: raw('anc_n') != null ? Math.round(raw('anc_n')) : 3,
    z_primero: inputSI('anc_z1') || 2.0,
    sv: inputSI('anc_sv') || 3.0,
    sh: inputSI('anc_sh') || 2.5,
    inclinacion: raw('anc_incl') != null ? raw('anc_incl') : 15.0,
    tau_bond: raw('anc_tau') != null ? raw('anc_tau') : 150.0,   // kPa directo
    d_bulbo: inputSI('anc_d') || 0.15,
    FS_pullout: raw('anc_fs') != null ? raw('anc_fs') : 2.0,
    Lf_min: inputSI('anc_lfmin') || 4.5,
  };
}

async function ancCalcular() {
  const payload = ancRecolectar();
  const btn = $('#btn-anc-calc');
  const lbl = btn && (btn.querySelector('span') || btn);
  if (btn) btn.disabled = true;
  if (lbl) lbl.textContent = 'Calculando…';
  try {
    const r = await fetch('/api/muro_anclado', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await r.json();
    if (!data.ok) { toast(data.error || 'Error en el cálculo', 'err', 6000); }
    else { _ancLast = data; ancRender(data); toast('Cálculo completado', 'ok'); }
  } catch (e) {
    toast('No se pudo conectar con el servidor', 'err');
  } finally {
    if (btn) btn.disabled = false;
    if (lbl) lbl.textContent = 'Calcular';
  }
}

function ancRender(j) {
  const set = (id, v) => { const el = $('#' + id); if (el) el.textContent = v; };
  const rs = j.resumen;
  const _tf = kN => (kN / 9.80665);
  set('anck-p', rs.p_max_kPa.toFixed(1));
  set('anck-t', rs.T_diseno_max_kN.toFixed(0));
  set('anck-e', _tf(rs.empuje_total_kN_m).toFixed(1));
  set('anck-lb', rs.Lb_max_m.toFixed(2));
  set('anck-lt', rs.L_total_max_m.toFixed(2));
  set('anck-m', rs.momento_max_kNm_m.toFixed(1));

  const badge = $('#anc-estado');
  if (badge) {
    const warn = (j.avisos && j.avisos.length) > 0;
    badge.style.display = '';
    badge.className = 'state ' + (warn ? 'warn' : 'ok');
    badge.innerHTML = `<span class="dot"></span>${warn ? 'REVISAR AVISOS' : 'DISEÑADO'}`;
  }

  const p = j.parametros || {};
  const tsuelo = j.tipo_suelo === 'arcilla' ? 'Arcilla' : 'Arena (granular)';
  let det = `
    <div class="pil-line"><b>Suelo:</b> ${tsuelo} · Ka = ${j.Ka} · presión aparente máx p = ${j.p_max.toFixed(1)} kPa</div>
    <div class="pil-line"><b>Empuje total:</b> ${_tf(j.empuje_total).toFixed(1)} tonf/m · reacción en la base R = ${_tf(j.reaccion_base).toFixed(1)} tonf/m</div>
    <div class="pil-line"><b>Pantalla:</b> momento flector máx aprox. ≈ ${j.momento_max.toFixed(1)} kN·m/m (dimensiona la sección: viga-pila o tablestaca)</div>`;
  const avisos = (j.avisos && j.avisos.length)
    ? `<div class="hint" style="border-color:var(--status-warn-bd);color:var(--status-warn-tx);margin-top:8px">⚠ ${j.avisos.join('<br>⚠ ')}</div>` : '';
  const el = $('#anc-detalle'); if (el) el.innerHTML = det + avisos;

  const prev = $('#anc-preview');
  if (prev) {
    prev.innerHTML = j.imagen
      ? `<img src="${j.imagen}" alt="Esquema muro anclado" style="max-width:100%;height:auto;border-radius:8px">`
      : '<div style="padding:36px;color:var(--text-muted)">Sin esquema disponible</div>';
  }

  const card = $('#anc-tabla-card'), wrap = $('#anc-tabla-wrap');
  if (card && wrap) {
    card.style.display = '';
    let html = `<table><thead><tr>
      <th>Anclaje</th><th class="text-right">z (m)</th><th class="text-right">Th (kN/m)</th>
      <th class="text-right">T diseño (kN)</th><th class="text-right">Lb (m)</th>
      <th class="text-right">Lf (m)</th><th class="text-right">L total (m)</th>
    </tr></thead><tbody>`;
    (j.anclajes || []).forEach(a => {
      html += `<tr>
        <td><b>A${a.i}</b></td>
        <td class="table-num">${a.z.toFixed(2)}</td><td class="table-num">${a.Th.toFixed(1)}</td>
        <td class="table-num">${a.T_diseno.toFixed(0)}</td><td class="table-num">${a.Lb.toFixed(2)}</td>
        <td class="table-num">${a.Lf.toFixed(2)}</td><td class="table-num">${a.L_total.toFixed(2)}</td>
      </tr>`;
    });
    html += '</tbody></table>';
    wrap.innerHTML = html;
  }
}

async function ancGenerarPDF(btn) {
  const payload = ancRecolectar();
  const val = id => { const e = $('#' + id); return e ? e.value : ''; };
  payload.proyecto = val('proyecto');
  payload.ingeniero = val('ingeniero');
  payload.ubicacion = val('ubicacion');
  payload.empresa = val('empresa');
  const old = btn ? btn.innerHTML : '';
  if (btn) { btn.disabled = true; btn.textContent = 'Generando…'; }
  try {
    const r = await fetch('/api/muro_anclado_pdf', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!r.ok) { const j = await r.json().catch(() => ({})); toast('Error PDF: ' + (j.error || r.status), 'err', 6000); return; }
    const blob = await r.blob();
    const filename = `CimX-anclado-${(payload.proyecto || 'memoria').replace(/[^a-z0-9]/gi, '_')}.pdf`;
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
  const bc = $('#btn-anc-calc');
  if (bc) bc.addEventListener('click', ancCalcular);
  const bp = $('#btn-anc-pdf');
  if (bp) bp.addEventListener('click', () => ancGenerarPDF(bp));
  window.ancCalcular = ancCalcular;
});
