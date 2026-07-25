/* ============================================================
   CimX — Lógica principal del frontend
   - Navegación entre vistas
   - Recolección de datos del formulario
   - Llamadas al backend (API)
   - Renderizado de resultados
   ============================================================ */
'use strict';

const $  = sel => document.querySelector(sel);
const $$ = sel => Array.from(document.querySelectorAll(sel));

/* ---------- Conversión de unidades MKS↔SI ---------- */
const G = 9.80665;       // factor para tonf↔kN, tonf/m²↔kPa, etc.

const fac = {
  // valor_UI = valor_SI * fac
  length:   1,            // m → m
  force:    1 / G,        // kN → tonf (~0.102)
  moment:   1 / G,        // kN·m → tonf·m
  pressure: 1 / G,        // kPa → tonf/m²
  gamma:    1 / G,        // kN/m³ → tonf/m³
  stress:   10.197,       // MPa → kgf/cm²  (1 MPa = 10.197 kgf/cm²)
};

const toSI    = (v, mag) => (v == null || isNaN(v)) ? v : (v / fac[mag]);
const fromSI  = (v, mag) => (v == null || isNaN(v)) ? v : (v * fac[mag]);

const labelOf = mag => ({
  length:    'm',     force:        'tonf',
  moment:    'tonf·m', pressure:     'tonf/m²',
  gamma:     'tonf/m³', stress:      'kgf/cm²',
  force_per_m:  'tonf/m', moment_per_m: 'tonf·m/m',
  area_per_m:   'mm²/m',
}[mag] || '');

function fmt(v, mag) {
  if (v == null || isNaN(v) || !isFinite(v)) return '—';
  const abs = Math.abs(v);
  let d = 2;
  if (mag === 'length')        d = abs < 0.1 ? 4 : abs < 10 ? 3 : 2;
  else if (mag === 'force')    d = abs < 1 ? 3 : 2;
  else if (mag === 'moment')   d = abs < 1 ? 3 : 2;
  else if (mag === 'pressure') d = abs < 0.1 ? 4 : 2;
  else if (mag === 'gamma')    d = 2;
  else if (mag === 'stress')   d = abs < 10 ? 2 : 1;
  return v.toFixed(d);
}
const fmtU = (v, mag) => `${fmt(v, mag)} ${labelOf(mag)}`;

function inputSI(id) {
  const el = $('#' + id);
  if (!el) return null;
  const s = el.value;
  if (s === '' || s == null) return null;
  const v = parseFloat(s);
  if (isNaN(v)) return null;
  return el.dataset.mag ? toSI(v, el.dataset.mag) : v;
}

/* ---------- Toast ---------- */
function toast(msg, kind = 'ok', ms = 3500) {
  const t = document.createElement('div');
  t.className = `toast ${kind}`;
  t.textContent = msg;
  $('#toaster').appendChild(t);
  setTimeout(() => {
    t.style.opacity = '0';
    t.style.transform = 'translateX(120%)';
    t.style.transition = 'all 0.3s ease';
    setTimeout(() => t.remove(), 300);
  }, ms);
}

/* ---------- Navegación entre vistas ---------- */
function showView(name) {
  $$('.view').forEach(v => v.classList.toggle('active', v.dataset.view === name));
  $$('.nav-item[data-view]').forEach(b =>
    b.classList.toggle('active', b.dataset.view === name));
  // Actualiza el título del header según la vista
  const titles = {
    summary: { t: 'Resumen del Proyecto', s: 'Vista general y verificaciones' },
    geometry: { t: 'Geometría del Muro', s: 'Dimensiones y tipo de muro' },
    soils: { t: 'Suelos', s: 'Relleno y cimentación' },
    loads: { t: 'Cargas y Sismo', s: 'Sobrecarga, inclinación, sismo NSR-10' },
    materials: { t: 'Materiales', s: 'Concreto y acero de refuerzo' },
    piles: { t: 'Diseño de Pilotes', s: 'Capacidad axial y diseño estructural' },
    pilereport: { t: 'Memoria de cálculo', s: 'Reporte PDF del pilote' },
    footing: { t: 'Diseño de Zapata', s: 'Zapata aislada — geotecnia y estructura' },
    footingreport: { t: 'Memoria de cálculo', s: 'Reporte PDF de la zapata' },
    dado: { t: 'Diseño del Dado', s: 'Cabezal/encepado sobre pilotes — NSR-10' },
    dadoreport: { t: 'Memoria de cálculo', s: 'Reporte PDF del dado / cabezal' },
    results: { t: 'Resultados', s: 'Cargas, combinaciones y diseño estructural' },
    project: { t: 'Datos del Proyecto', s: 'Información general del reporte' },
  };
  const meta = titles[name];
  if (meta) {
    $('#header-title-main').textContent  = meta.t;
    $('#header-title-small').textContent = meta.s;
  }
  // Al salir de Geometría, liberar el contexto WebGL del visor 3D del muro.
  if (name !== 'geometry' && window.CimXWall3D) CimXWall3D.dispose();
  // Visores 3D embebidos en cada vista de diseño: redibujar al entrar, liberar al salir.
  if (window.CimXPile3D) {
    if (name === 'piles') { if (typeof window.pilMostrar === 'function') setTimeout(window.pilMostrar, 50); }
    else CimXPile3D.dispose();
  }
  if (window.CimXFooting3D) {
    if (name === 'footing') { if (typeof window.zapMostrar === 'function') setTimeout(window.zapMostrar, 50); }
    else CimXFooting3D.dispose();
  }
  if (window.CimXDado3D) {
    if (name === 'dado') { if (typeof window.dadMostrar === 'function') setTimeout(window.dadMostrar, 50); }
    else CimXDado3D.dispose();
  }
}

function setupNav() {
  $$('.nav-item[data-view]').forEach(item => {
    item.addEventListener('click', () => showView(item.dataset.view));
  });
}

/* ---------- Módulos (dashboard / navegación por elemento) ---------- */
const MODULO_VIEW = {
  summary: 'muro', geometry: 'muro', soils: 'muro', loads: 'muro',
  materials: 'muro', results: 'muro', project: 'muro pilote zapata dado',
  piles: 'pilote', pilereport: 'pilote',
  footing: 'zapata', footingreport: 'zapata',
  dado: 'dado', dadoreport: 'dado',
};
const MODULO_DEFAULT_VIEW = { muro: 'summary', pilote: 'piles', zapata: 'footing', dado: 'dado' };
const MODULO_NOMBRE = { muro: 'Muros de contención', pilote: 'Pilotes', zapata: 'Zapatas', dado: 'Dados / Cabezales' };

function etiquetarModulos() {
  // Asigna data-module a las vistas y a las acciones del header propias del muro.
  $$('.view[data-view]').forEach(v => {
    const m = MODULO_VIEW[v.dataset.view];
    if (m && !v.dataset.module) v.dataset.module = m;
  });
  ['btn-preview', 'btn-analyze', 'btn-pdf', 'estado-pill'].forEach(id => {
    const el = $('#' + id);
    if (el && !el.dataset.module) el.dataset.module = 'muro';
  });
  const ps = $('.proj-selector');
  if (ps && !ps.dataset.module) ps.dataset.module = 'muro';
}

function aplicarVisibilidadModulo(mod) {
  // Oculta todo elemento [data-module] que no incluya el módulo activo.
  $$('[data-module]').forEach(el => {
    const tokens = (el.dataset.module || '').split(/\s+/).filter(Boolean);
    el.classList.toggle('fuera-de-modulo', !tokens.includes(mod));
  });
}

function seleccionarModulo(mod) {
  if (!MODULO_DEFAULT_VIEW[mod]) return;
  document.body.classList.remove('en-dashboard');
  document.body.dataset.modulo = mod;
  aplicarVisibilidadModulo(mod);
  const tag = $('.brand-tagline');
  if (tag) tag.textContent = MODULO_NOMBRE[mod] || 'Diseño Geotécnico';
  showView(MODULO_DEFAULT_VIEW[mod]);
  if (mod === 'muro') setTimeout(actualizarVistaPrevia, 60);
}

function irADashboard() {
  if (window.CimXWall3D) CimXWall3D.dispose();
  if (window.CimXPile3D) CimXPile3D.dispose();
  if (window.CimXFooting3D) CimXFooting3D.dispose();
  if (window.CimXDado3D) CimXDado3D.dispose();
  document.body.classList.add('en-dashboard');
}

function setupDashboard() {
  $$('[data-modulo-sel]').forEach(card => {
    card.addEventListener('click', () => seleccionarModulo(card.dataset.moduloSel));
  });
  const inicio = $('#nav-inicio');
  if (inicio) inicio.addEventListener('click', irADashboard);
}

/* ---------- Tabs internos (en una vista) ---------- */
function setupTabs() {
  $$('.tabs').forEach(tabs => {
    const panels = tabs.parentElement.querySelectorAll('.tab-panel');
    tabs.querySelectorAll('.tab').forEach(tab => {
      tab.addEventListener('click', () => {
        tabs.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        panels.forEach(p =>
          p.classList.toggle('active', p.dataset.panel === tab.dataset.tab));
      });
    });
  });
}

/* ---------- Recolectar datos del formulario ---------- */
function recolectar() {
  const getF = id => parseFloat(($('#' + id) || {}).value);
  const getS = id => (($('#' + id) || {}).value) || '';
  const tipoMuro = $('#tipo_muro').value;

  const Hrell_raw = $('#H_relleno') ? $('#H_relleno').value : '';
  let H_relleno = '';
  if (Hrell_raw !== '' && !isNaN(parseFloat(Hrell_raw)))
    H_relleno = toSI(parseFloat(Hrell_raw), 'length');

  let geom = {};
  if (tipoMuro === 'gravedad') {
    geom = {
      tipo_muro:   'gravedad',
      H_muro:      inputSI('H_muro'),
      e_zapata:    inputSI('e_zapata_g'),
      b_corona:    inputSI('b_corona_g'),
      a_frontal:   inputSI('a_frontal'),
      a_posterior: inputSI('a_posterior'),
      b_puntera:   inputSI('b_puntera_g'),
      b_talon:     inputSI('b_talon_g'),
      D:           inputSI('D_g'),
    };
  } else {
    const _bc  = inputSI('b_corona');
    const _afv = inputSI('a_frontal_v') || 0;
    const _apv = inputSI('a_posterior_v') || 0;
    geom = {
      tipo_muro:   'voladizo',
      H_vastago:   inputSI('H_vastago'),
      e_zapata:    inputSI('e_zapata'),
      H_relleno,
      b_puntera:   inputSI('b_puntera'),
      b_talon:     inputSI('b_talon'),
      b_corona:    _bc,
      b_base_vast: _bc + _afv + _apv,
      a_frontal_v: _afv,
      a_posterior_v: _apv,
      D:           inputSI('D'),
      cara_posterior_vertical: true,
      h_diente: 0, b_diente: 0, x_diente: '',
    };
  }

  return {
    proyecto:     getS('proyecto'),
    empresa:      getS('empresa'),
    ubicacion:    getS('ubicacion'),
    ingeniero:    getS('ingeniero'),
    contratante:  getS('contratante'),
    observaciones:getS('observaciones'),
    numeracion_prefijo: '',

    ...geom,

    relleno_nombre:   getS('relleno_nombre') || 'Relleno',
    relleno_gamma:    inputSI('relleno_gamma'),
    relleno_phi:      getF('relleno_phi'),
    relleno_cohesion: inputSI('relleno_cohesion') || 0,

    ciment_nombre:    getS('ciment_nombre') || 'Cimentación',
    ciment_gamma:     inputSI('ciment_gamma'),
    ciment_phi:       getF('ciment_phi'),
    ciment_cohesion:  inputSI('ciment_cohesion') || 0,

    alpha:      getF('alpha') || 0,
    sobrecarga: inputSI('sobrecarga') || 0,

    incluir_sismo: $('#incluir_sismo') ? $('#incluir_sismo').checked : false,
    Aa: getF('Aa') || 0.15,
    Av: getF('Av') || 0.15,
    tipo_suelo_nsr: getS('tipo_suelo_nsr') || 'D',
    permite_desplazamiento: $('#permite_desplazamiento')
      ? $('#permite_desplazamiento').checked : true,

    concreto_fc:    fromSI ? toSI(getF('concreto_fc'), 'stress') : getF('concreto_fc'),
    concreto_gamma: inputSI('concreto_gamma'),
    acero_fy:       toSI(getF('acero_fy'), 'stress'),

    metodo_empuje: getS('metodo_empuje') || 'rankine',
  };
}

/* ---------- Tipo de muro toggle ---------- */
function aplicarTipoMuro() {
  const t = $('#tipo_muro').value;
  $('#geom-voladizo').style.display = (t === 'gravedad') ? 'none' : '';
  $('#geom-gravedad').style.display = (t === 'gravedad') ? '' : 'none';
  const sel = $('#metodo_empuje');
  if (sel) {
    if (t === 'gravedad' && sel.value !== 'coulomb') sel.value = 'coulomb';
    if (t === 'voladizo' && sel.value !== 'rankine')  sel.value = 'rankine';
  }
  actualizarVistaPrevia();
}

/* ---------- Vista previa del muro (2D SVG nativo + 3D Three.js) ---------- */
let vista3D = false;   // modo del visor de la pestaña Geometría

function _datosMuro() {
  const tipo = $('#tipo_muro').value;
  if (tipo === 'gravedad') {
    return { tipo, data: {
      H_muro:      parseFloat($('#H_muro').value)      || 0,
      e_zapata:    parseFloat($('#e_zapata_g').value)  || 0,
      b_corona:    parseFloat($('#b_corona_g').value)  || 0,
      a_frontal:   parseFloat($('#a_frontal').value)   || 0,
      a_posterior: parseFloat($('#a_posterior').value) || 0,
      b_puntera:   parseFloat($('#b_puntera_g').value) || 0,
      b_talon:     parseFloat($('#b_talon_g').value)   || 0,
      D:           parseFloat($('#D_g').value)         || 0,
      alpha:       parseFloat($('#alpha').value)       || 0,
      sobrecarga:  parseFloat($('#sobrecarga').value)  || 0,
    }};
  }
  const _bc  = parseFloat($('#b_corona').value) || 0;
  const _afv = parseFloat($('#a_frontal_v').value) || 0;
  const _apv = parseFloat($('#a_posterior_v').value) || 0;
  const _bbv = _bc + _afv + _apv;
  const _bbvEl = $('#b_base_vast'); if (_bbvEl) _bbvEl.value = _bbv.toFixed(2);
  return { tipo: 'voladizo', data: {
    H_vastago:   parseFloat($('#H_vastago').value)   || 0,
    e_zapata:    parseFloat($('#e_zapata').value)    || 0,
    b_puntera:   parseFloat($('#b_puntera').value)   || 0,
    b_talon:     parseFloat($('#b_talon').value)     || 0,
    b_corona:    _bc,
    a_frontal_v: _afv,
    a_posterior_v: _apv,
    b_base_vast: _bbv,
    D:           parseFloat($('#D').value)           || 0,
    H_relleno:   parseFloat($('#H_relleno').value)   || 0,
    alpha:       parseFloat($('#alpha').value)       || 0,
    sobrecarga:  parseFloat($('#sobrecarga').value)  || 0,
  }};
}

function _geomMuro(tipo, data) {
  return (tipo === 'gravedad')
    ? CimXWallSVG.buildGravedad(data)
    : CimXWallSVG.buildVoladizo(data);
}

function _draw2D(tipo, data, container) {
  if (!container) return;
  if (tipo === 'gravedad') CimXWallSVG.renderGravedad(data, container);
  else CimXWallSVG.renderVoladizo(data, container);
}

function dibujarMuroSVG() {
  const { tipo, data } = _datosMuro();

  // Pestaña Resumen: siempre vista 2D (miniatura)
  _draw2D(tipo, data, $('#preview-frame'));

  // Pestaña Geometría: 2D o 3D según el toggle
  const f2 = $('#preview-frame-2');
  if (!f2) return;
  if (vista3D && window.CimXWall3D && CimXWall3D.isAvailable()) {
    try {
      CimXWall3D.render(_geomMuro(tipo, data), f2, { background: 0x0d1c16 });
    } catch (e) {
      console.error('[CimX 3D]', e);
      CimXWall3D.dispose();
      _draw2D(tipo, data, f2);
    }
  } else {
    if (window.CimXWall3D) CimXWall3D.dispose();
    _draw2D(tipo, data, f2);
  }
}

/** Cambia el modo del visor de la pestaña Geometría ('2d' | '3d'). */
function setVistaMuro(modo) {
  vista3D = (modo === '3d');
  $$('[data-vista-btn]').forEach(b =>
    b.classList.toggle('active', b.getAttribute('data-vista-btn') === modo));
  const hint = $('#vista3d-hint');
  if (hint) hint.style.display = vista3D ? '' : 'none';
  dibujarMuroSVG();
}

/* Función que reusa el nombre del API anterior para no romper otros llamados */
function actualizarVistaPrevia() {
  dibujarMuroSVG();
  llenarResumenRapido();
}

/* ---------- Resumen rápido (panel derecho de Resumen) ---------- */
function llenarResumenRapido() {
  const tipo = $('#tipo_muro').value;
  const fmt2 = v => (isNaN(v) || v == null) ? '—' : `${v.toFixed(2)} m`;
  if (tipo === 'gravedad') {
    const H = (parseFloat($('#H_muro').value) || 0)
            + (parseFloat($('#e_zapata_g').value) || 0);
    const B = (parseFloat($('#b_puntera_g').value) || 0)
            + (parseFloat($('#b_corona_g').value) || 0)
            + (parseFloat($('#a_frontal').value)  || 0)
            + (parseFloat($('#a_posterior').value)|| 0)
            + (parseFloat($('#b_talon_g').value)  || 0);
    const D = parseFloat($('#D_g').value) || 0;
    const m = $('#metodo_empuje').value;
    if ($('#sum-tipo'))    $('#sum-tipo').textContent    = 'Gravedad';
    if ($('#sum-metodo'))  $('#sum-metodo').textContent  = (m === 'coulomb' ? 'Coulomb' : 'Rankine');
    if ($('#sum-h'))       $('#sum-h').textContent       = fmt2(H);
    if ($('#sum-b'))       $('#sum-b').textContent       = fmt2(B);
    if ($('#sum-d'))       $('#sum-d').textContent       = fmt2(D);
  } else {
    const H = (parseFloat($('#H_vastago').value)  || 0)
            + (parseFloat($('#e_zapata').value)   || 0);
    const B = (parseFloat($('#b_puntera').value)  || 0)
            + (parseFloat($('#b_base_vast').value)|| 0)
            + (parseFloat($('#b_talon').value)    || 0);
    const D = parseFloat($('#D').value) || 0;
    const m = $('#metodo_empuje').value;
    if ($('#sum-tipo'))    $('#sum-tipo').textContent    = 'Voladizo';
    if ($('#sum-metodo'))  $('#sum-metodo').textContent  = (m === 'coulomb' ? 'Coulomb' : 'Rankine');
    if ($('#sum-h'))       $('#sum-h').textContent       = fmt2(H);
    if ($('#sum-b'))       $('#sum-b').textContent       = fmt2(B);
    if ($('#sum-d'))       $('#sum-d').textContent       = fmt2(D);
  }
}

/* ---------- Ejecutar análisis ---------- */
async function ejecutarAnalisis() {
  const btn = $('#btn-analyze');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span><span>Analizando…</span>';
  // Estado en el header
  setEstadoIdle();

  try {
    const data = recolectar();
    const r = await fetch('/api/analizar', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    const j = await r.json();
    if (!j.ok) {
      toast('Error: ' + (j.error || 'fallo del análisis'), 'err', 6000);
      setEstadoError();
      return;
    }
    window._lastResult = j;
    renderizarKPIs(j);
    renderizarVerificaciones(j);
    renderizarResultados(j);
    setEstadoFinal(j);
    toast('Análisis completado', 'ok');
  } catch (e) {
    toast('Error de red: ' + e.message, 'err', 6000);
    setEstadoError();
  } finally {
    btn.disabled = false;
    btn.innerHTML = `<svg class="icon" viewBox="0 0 24 24"><polygon points="5 3 19 12 5 21 5 3"/></svg><span>Ejecutar análisis</span>`;
  }
}

/* ---------- Generar PDF (con preview en modal) ---------- */
async function generarPDF() {
  const btn = $('#btn-pdf');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span><span>Generando…</span>';
  try {
    const data = recolectar();
    const r = await fetch('/api/pdf', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!r.ok) {
      const j = await r.json().catch(() => ({}));
      toast('Error PDF: ' + (j.error || r.status), 'err', 6000);
      return;
    }
    const blob = await r.blob();
    const filename = `CimX-${($('#proyecto').value || 'reporte').replace(/[^a-z0-9]/gi, '_')}.pdf`;
    // Abrir el modal de preview en vez de descargar directo
    CimXPDFModal.open(blob, filename);
    toast('Reporte generado — usa el botón "Descargar" en el visor', 'ok');
  } catch (e) {
    toast('Error al generar PDF: ' + e.message, 'err', 6000);
  } finally {
    btn.disabled = false;
    btn.innerHTML = `<svg class="icon" viewBox="0 0 24 24"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg><span>Generar PDF</span>`;
  }
}

/* ---------- Estado en el header ---------- */
function setEstadoIdle() {
  const p = $('#estado-pill');
  p.className = 'status-pill idle';
  p.querySelector('.value').textContent = 'PENDIENTE';
}
function setEstadoError() {
  const p = $('#estado-pill');
  p.className = 'status-pill err';
  p.querySelector('.value').textContent = 'ERROR';
}
function setEstadoFinal(j) {
  const p = $('#estado-pill');
  let estado = '';
  if (j.resultado_global) {
    estado = (typeof j.resultado_global === 'string')
      ? j.resultado_global
      : (j.resultado_global.estado || '');
  }
  // Aceptar varios formatos: "APROBADO", "OK", "MURO APROBADO ✓"
  const esOK = /APROBADO|OK/i.test(estado) && !/NO APROBADO|NO\s*OK/i.test(estado);
  if (esOK) {
    p.className = 'status-pill';
    p.querySelector('.value').textContent = 'ESTABLE';
  } else {
    p.className = 'status-pill warn';
    p.querySelector('.value').textContent = 'REVISAR';
  }
}

/* ---------- Renderizar KPIs ---------- */
function renderizarKPIs(j) {
  const tm  = j.totales_momentos || {};
  const ver = j.verificaciones_raw || [];
  const setKpi = (id, val, unit, cls) => {
    const el = $(`#kpi-${id}`);
    if (!el) return;
    el.querySelector('.kpi-value').textContent = val;
    if (unit !== undefined) el.querySelector('.kpi-unit').textContent = unit;
    el.classList.remove('warn', 'err');
    if (cls) el.classList.add(cls);
  };
  // Backend devuelve los totales ya en MKS (tonf, tonf·m). NO reconvertir.
  const f2 = (v) => (v == null || isNaN(v)) ? '—' : Number(v).toFixed(2);
  const f3 = (v) => (v == null || isNaN(v)) ? '—' : Number(v).toFixed(3);
  setKpi('sv',  f2(tm.SV),  'tonf/m');
  setKpi('sh',  f2(tm.SH),  'tonf/m');
  setKpi('smr', f2(tm.SMR), 'tonf·m/m');
  setKpi('smo', f2(tm.SMo), 'tonf·m/m');
  // FS volcamiento — color según estado
  const fsv = ver.find(v => v.nombre && v.nombre.toLowerCase().includes('volcamiento'));
  if (fsv) {
    setKpi('fs', f3(fsv.valor), '',
           fsv.estado === 'CUMPLE' ? null : 'warn');
  }
}

/* ---------- Renderizar tarjetas de verificaciones ---------- */
function renderizarVerificaciones(j) {
  const ver = j.verificaciones_raw || [];
  const cont = $('#ver-cards');
  if (!cont) return;
  cont.innerHTML = '';
  ver.forEach(v => {
    const ok = v.estado === 'CUMPLE';
    const card = document.createElement('div');
    card.className = 'kpi ' + (ok ? '' : 'warn');
    card.innerHTML = `
      <div class="kpi-label">${v.nombre}</div>
      <div class="kpi-value">${fmt(v.valor, 'length')}</div>
      <div class="kpi-foot">
        <span class="muted size-sm">mín: ${fmt(v.requerido, 'length')}</span>
        <span class="state ${ok ? 'ok' : 'err'}" style="margin-left:auto">
          <span class="dot"></span>${ok ? 'CUMPLE' : 'REVISAR'}
        </span>
      </div>`;
    cont.appendChild(card);
  });
}

/* ---------- Renderizar tablas de resultados (vista Resultados) ---------- */
function renderizarResultados(j) {
  // Tabla de cargas — usar cargas_raw que es uniforme entre voladizo y gravedad
  const cargas = $('#tbl-cargas tbody');
  if (cargas) {
    cargas.innerHTML = '';
    const rows = j.cargas_raw || [];
    if (rows.length === 0) {
      cargas.innerHTML = `<tr><td colspan="4" class="muted" style="text-align:center;padding:24px">Sin cargas registradas</td></tr>`;
    } else {
      rows.forEach((c, i) => {
        // tipo: "vertical" → "V", "horizontal" → "H"
        const tipoCorto = c.tipo === 'vertical' ? 'V' : (c.tipo === 'horizontal' ? 'H' : c.tipo);
        // categoria viene de un Enum: "Muerta" → D, "Viva" → L, "H" → H, "S" → S
        const catMap = {
          'Muerta': 'D', 'D': 'D',
          'Viva':   'L', 'L': 'L',
          'Empuje horizontal': 'H', 'H': 'H',
          'Sismo':  'S', 'S': 'S',
          'Hv':     'Hv',
        };
        const catCorto = catMap[c.categoria] || c.categoria || '—';
        // Magnitud en MKS (tonf/m) — el backend devuelve kN, hay que convertir
        const F_mks = c.magnitud_kN / 9.80665;
        cargas.innerHTML += `<tr>
          <td class="muted text-mono">${String(i + 1).padStart(2, '0')}</td>
          <td>${c.nombre}</td>
          <td><span class="state ${tipoCorto === 'V' ? 'ok' : 'warn'}" style="padding:2px 8px;font-size:10.5px">${tipoCorto}</span></td>
          <td><span class="muted" style="font-family:var(--font-mono)">${catCorto}</span></td>
          <td class="table-num">${F_mks.toFixed(2)}</td>
        </tr>`;
      });
    }
  }
  // Tabla de combinaciones — la cambiamos para mostrar ELU + ELS condicionalmente
  renderizarCombinaciones(j);
  // Tabla de diseño estructural (solo voladizo)
  const dis = $('#tbl-diseno tbody');
  if (dis) {
    dis.innerHTML = '';
    if (j.tipo_muro === 'gravedad') {
      dis.innerHTML = `<tr><td colspan="6" class="muted" style="text-align:center;padding:24px">
        Los muros de gravedad resisten por su propio peso, no requieren armadura por flexión.
      </td></tr>`;
    } else {
      (j.diseno || []).forEach(r => {
        dis.innerHTML += `<tr>
          <td>${r[0]}</td><td class="table-num">${r[1]}</td>
          <td class="table-num">${r[2]}</td><td class="table-num">${r[3]}</td>
          <td class="table-num">${r[4]}</td>
          <td><span class="state ${r[5].includes('OK') ? 'ok' : 'err'}">
            <span class="dot"></span>${r[5]}</span></td>
        </tr>`;
      });
    }
  }
}

function renderizarCombinaciones(j) {
  const cont = $('#tbl-combinaciones-wrap');
  if (!cont) return;
  const elu = j.combinaciones_elu_raw || [];
  const els = j.combinaciones_els_raw || [];
  // Los muros de gravedad NO muestran ELU (no se diseña por flexión)
  const ocultarELU = (j.tipo_muro === 'gravedad');
  const f2 = v => (v == null) ? '—' : (v / 9.80665).toFixed(2);  // kN→tonf
  const renderTable = (rows, titulo) => {
    if (rows.length === 0) return '';
    let html = `<div class="card mb-3">
      <div class="card-header"><div class="card-title">${titulo}</div></div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr><th>Combinación</th><th class="text-right">V (tonf/m)</th><th class="text-right">H (tonf/m)</th>
                <th class="text-right">M_R (tonf·m/m)</th><th class="text-right">M_o (tonf·m/m)</th></tr>
          </thead>
          <tbody>`;
    rows.forEach(r => {
      html += `<tr>
        <td>${r.nombre}</td>
        <td class="table-num">${f2(r.V_kN)}</td>
        <td class="table-num">${f2(r.H_kN)}</td>
        <td class="table-num">${f2(r.MR_kNm)}</td>
        <td class="table-num">${f2(r.Mo_kNm)}</td>
      </tr>`;
    });
    html += `</tbody></table></div></div>`;
    return html;
  };
  let html = '';
  if (!ocultarELU && elu.length > 0) {
    html += renderTable(elu, 'Combinaciones últimas (ELU) — para diseño estructural');
  }
  if (els.length > 0) {
    html += renderTable(els, 'Combinaciones de servicio (ELS) — para verificaciones de estabilidad');
  }
  if (ocultarELU && elu.length > 0) {
    html += `<div class="hint">Para muros de gravedad solo se muestran las combinaciones de servicio (ELS), ya que no se realiza diseño estructural por flexión.</div>`;
  }
  if (html === '') {
    html = `<div class="muted" style="text-align:center;padding:24px">Sin combinaciones registradas</div>`;
  }
  cont.innerHTML = html;
}

/* ---------- Bind y arranque ---------- */
function bindAll() {
  setupNav();
  setupTabs();
  etiquetarModulos();
  setupDashboard();
  $('#btn-analyze').addEventListener('click', ejecutarAnalisis);
  $('#btn-pdf').addEventListener('click', generarPDF);
  $('#btn-preview').addEventListener('click', actualizarVistaPrevia);
  $('#tipo_muro').addEventListener('change', () => {
    aplicarTipoMuro();
    actualizarVistaPrevia();
  });

  // Cuando cambia cualquier input numérico de geometría → re-dibuja el SVG.
  // Usamos 'input' (en tiempo real) con debounce para no sobrecargar.
  let _t = null;
  const onInput = () => {
    clearTimeout(_t);
    _t = setTimeout(actualizarVistaPrevia, 150);
  };
  ['#H_vastago', '#e_zapata', '#b_puntera', '#b_talon', '#b_corona',
   '#b_base_vast', '#a_frontal_v', '#a_posterior_v', '#D', '#H_relleno',
   '#alpha', '#sobrecarga',
   '#H_muro', '#e_zapata_g', '#b_corona_g', '#a_frontal', '#a_posterior',
   '#b_puntera_g', '#b_talon_g', '#D_g', '#metodo_empuje'].forEach(sel => {
    const el = $(sel);
    if (el) el.addEventListener('input', onInput);
    if (el) el.addEventListener('change', onInput);
  });

  // Al cambiar de vista, si la nueva es Resumen o Geometría, re-dibujar
  // (los <div> contenedores pueden estar ocultos cuando se cargó la app)
  $$('.nav-item[data-view]').forEach(item => {
    item.addEventListener('click', () => {
      const v = item.dataset.view;
      if (v === 'summary' || v === 'geometry') {
        setTimeout(actualizarVistaPrevia, 50);
      }
    });
  });

  // Toggle 2D / 3D del visor de Geometría
  $$('[data-vista-btn]').forEach(btn => {
    btn.addEventListener('click', () => setVistaMuro(btn.getAttribute('data-vista-btn')));
  });

  // Inicial
  aplicarTipoMuro();
  setEstadoIdle();
  // Vista previa al cargar
  setTimeout(actualizarVistaPrevia, 100);
}

document.addEventListener('DOMContentLoaded', bindAll);
