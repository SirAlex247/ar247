/* ============================================================
   CimX — Visor 3D del dado / cabezal de pilotes (Three.js + OrbitControls)
   Cabezal (rectangular o prisma triangular) + pilotes + arranque de columna,
   malla de refuerzo, sombras suaves, etiquetas de cota y flechas de reacción.
   Instancia única (un contexto WebGL).
   ============================================================ */
'use strict';

window.CimXDado3D = (function () {

  const COL = {
    concrete: 0x9aa3ab, col: 0xb4bdc4, pile: 0x6477a0,
    soil: 0xc4a464, grass: 0x6aa860, steel: 0xe07a3a,
    edge: 0x223129, bg: 0x0b1813, grid: 0x274034, arrow: 0xf0c24a,
  };

  let R = {
    renderer: null, scene: null, camera: null, controls: null, sun: null,
    group: null, raf: null, ro: null, container: null, onDbl: null,
    raycaster: null, pointer: { x: 0, y: 0 }, selected: null, selTipo: null,
    hovered: null, onSelect: null, payload: null,
    onDown: null, onUp: null, onMove: null, downXY: null,
  };

  const EM_SEL = 0x2353c7, EM_HOVER = 0x14442a;

  function clamp(v, a, b) { return Math.max(a, Math.min(b, v)); }

  function disposeObject(obj) {
    obj.traverse(o => {
      if (o.geometry) o.geometry.dispose();
      if (o.material) {
        const mats = Array.isArray(o.material) ? o.material : [o.material];
        mats.forEach(m => { if (m.map) m.map.dispose(); m.dispose(); });
      }
    });
  }

  function roundRect(ctx, x, y, w, h, r) {
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.arcTo(x + w, y, x + w, y + h, r);
    ctx.arcTo(x + w, y + h, x, y + h, r);
    ctx.arcTo(x, y + h, x, y, r);
    ctx.arcTo(x, y, x + w, y, r);
    ctx.closePath();
  }
  function makeLabel(text, color) {
    const fs = 46, pad = 18;
    const c = document.createElement('canvas');
    const ctx = c.getContext('2d');
    ctx.font = 'bold ' + fs + 'px Inter, Arial, sans-serif';
    const tw = ctx.measureText(text).width;
    c.width = Math.ceil(tw + pad * 2);
    c.height = fs + pad * 2;
    ctx.font = 'bold ' + fs + 'px Inter, Arial, sans-serif';
    ctx.fillStyle = 'rgba(8,18,14,0.82)';
    roundRect(ctx, 1, 1, c.width - 2, c.height - 2, 16); ctx.fill();
    ctx.strokeStyle = 'rgba(120,160,140,0.55)'; ctx.lineWidth = 2;
    roundRect(ctx, 1, 1, c.width - 2, c.height - 2, 16); ctx.stroke();
    ctx.fillStyle = color || '#eaf2ee';
    ctx.textBaseline = 'middle'; ctx.textAlign = 'center';
    ctx.fillText(text, c.width / 2, c.height / 2 + 2);
    const tex = new THREE.CanvasTexture(c);
    tex.minFilter = THREE.LinearFilter;
    const sp = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, transparent: true, depthTest: false, depthWrite: false }));
    const s = 0.0042;
    sp.scale.set(c.width * s, c.height * s, 1);
    sp.userData.label = true;
    return sp;
  }

  /* ---------- Selección interactiva (estilo Revit) ---------- */
  function _ndc(ev) {
    const r = R.renderer.domElement.getBoundingClientRect();
    R.pointer.x = ((ev.clientX - r.left) / r.width) * 2 - 1;
    R.pointer.y = -((ev.clientY - r.top) / r.height) * 2 + 1;
  }
  function _pick(ev) {
    if (!R.raycaster || !R.group) return null;
    _ndc(ev);
    R.raycaster.setFromCamera(R.pointer, R.camera);
    const hits = R.raycaster.intersectObjects(R.group.userData.selectable || [], false);
    return hits.length ? hits[0].object : null;
  }
  function _setEm(mesh, hex) {
    if (!mesh || !mesh.material || !mesh.material.emissive) return;
    if (mesh.userData._em0 === undefined) mesh.userData._em0 = mesh.material.emissive.getHex();
    mesh.material.emissive.setHex(hex);
  }
  function _restoreEm(mesh) {
    if (!mesh || !mesh.material || !mesh.material.emissive) return;
    if (mesh.userData._em0 !== undefined) mesh.material.emissive.setHex(mesh.userData._em0);
  }
  function _meshesOf(tipo) {
    const p = R.group && R.group.userData.parts; if (!p) return [];
    if (tipo === 'cabezal') return [p.cabezal];
    if (tipo === 'columna') return [p.columna];
    if (tipo === 'pilote') return p.pilotes || [];
    return [];
  }
  function _paint(mesh) {
    if (mesh.userData.sel === R.selTipo) _setEm(mesh, EM_SEL);
    else _restoreEm(mesh);
  }
  function applySel(tipo) {
    (R.group.userData.selectable || []).forEach(_restoreEm);
    R.selTipo = tipo;
    if (tipo) _meshesOf(tipo).forEach(m => _setEm(m, EM_SEL));
    R.hovered = null;
  }
  function _selInfo(tipo, idx) {
    const p = R.payload || {};
    return { tipo, idx, props: { Dp: p.Dp, s: p.s, e: p.e, h: p.h, c1: p.c1, c2: p.c2, Bx: p.Bx, Ly: p.Ly, n: p.n } };
  }
  function onPointerMove(ev) {
    const m = _pick(ev);
    if (R.renderer) R.renderer.domElement.style.cursor = m ? 'pointer' : 'grab';
    if (m === R.hovered) return;
    if (R.hovered) _paint(R.hovered);
    R.hovered = m;
    if (m && m.userData.sel !== R.selTipo) _setEm(m, EM_HOVER);
  }
  function onPointerUp(ev) {
    if (R.downXY) {
      const dx = ev.clientX - R.downXY[0], dy = ev.clientY - R.downXY[1];
      R.downXY = null;
      if (Math.hypot(dx, dy) > 5) return;          // fue un arrastre (órbita)
    }
    const m = _pick(ev);
    if (m) { applySel(m.userData.sel); if (typeof R.onSelect === 'function') R.onSelect(_selInfo(m.userData.sel, m.userData.idx)); }
    else { applySel(null); if (typeof R.onSelect === 'function') R.onSelect(null); }
  }

  function buildGroup(p) {
    const g = new THREE.Group();
    const Bx = p.Bx || 1, Ly = p.Ly || 1, h = p.h || 0.5;
    const c1 = p.c1 || 0.4, c2 = p.c2 || 0.4, Dp = p.Dp || 0.4;
    const coords = p.coords || [[0, 0]];
    const forma = p.forma || 'rect';
    const verts = p.vertices;
    const Lp = clamp(Math.max(3 * Dp, 1.0), 0.8, 2.0);   // tramo de pilote visible
    const emb = 0.12;
    const colH = 0.6;
    const SX = Math.max(1.5 * Bx, Bx + 1.2);
    const SZ = Math.max(1.5 * Ly, Ly + 1.2);

    // Plano de terreno (a nivel del tope del dado), recibe sombra
    const grass = new THREE.Mesh(
      new THREE.BoxGeometry(SX * 1.15, 0.04, SZ * 1.15),
      new THREE.MeshStandardMaterial({ color: COL.grass, roughness: 0.95, metalness: 0.0,
        transparent: true, opacity: 0.5 }));
    grass.position.set(0, h, 0); grass.receiveShadow = true;
    g.add(grass);

    // ---- Cabezal (dado) ----
    const matCon = new THREE.MeshStandardMaterial({ color: COL.concrete, roughness: 0.85, metalness: 0.02 });
    let cap, capEdges;
    if (forma === 'tri' && verts) {
      const shape = new THREE.Shape();
      verts.forEach((v, i) => { const x = v[0], z = -v[1]; if (i === 0) shape.moveTo(x, z); else shape.lineTo(x, z); });
      shape.closePath();
      const geo = new THREE.ExtrudeGeometry(shape, { depth: h, bevelEnabled: false });
      cap = new THREE.Mesh(geo, matCon);
      cap.rotation.x = -Math.PI / 2;          // extrusión (Z) → altura (Y)
      capEdges = new THREE.LineSegments(new THREE.EdgesGeometry(geo),
        new THREE.LineBasicMaterial({ color: COL.edge }));
      capEdges.rotation.x = -Math.PI / 2;
    } else {
      const geo = new THREE.BoxGeometry(Bx, h, Ly);
      cap = new THREE.Mesh(geo, matCon);
      cap.position.set(0, h / 2, 0);
      capEdges = new THREE.LineSegments(new THREE.EdgesGeometry(geo),
        new THREE.LineBasicMaterial({ color: COL.edge }));
      capEdges.position.copy(cap.position);
    }
    cap.castShadow = true; cap.receiveShadow = true;
    cap.userData.sel = 'cabezal';
    g.add(cap); g.add(capEdges);

    // ---- Pilotes (cilindros bajo el dado) ----
    const matPile = new THREE.MeshStandardMaterial({ color: COL.pile, roughness: 0.8, metalness: 0.05 });
    const matCone = new THREE.MeshStandardMaterial({ color: COL.arrow, roughness: 0.5, emissive: 0x3a2c08 });
    const pileMeshes = [];
    coords.forEach((c, i) => {
      const x = c[0], z = c[1];
      const len = Lp + emb;
      const pile = new THREE.Mesh(new THREE.CylinderGeometry(Dp / 2, Dp / 2, len, 18), matPile.clone());
      pile.position.set(x, emb - len / 2, z);     // tope embebido en el dado
      pile.castShadow = true;
      pile.userData.sel = 'pilote'; pile.userData.idx = i;
      g.add(pile); pileMeshes.push(pile);
      // reacción (cono hacia arriba justo bajo el dado)
      const cone = new THREE.Mesh(new THREE.ConeGeometry(0.07, 0.24, 14), matCone);
      cone.position.set(x, -0.18, z);
      g.add(cone);
    });

    // ---- Columna (arranque) ----
    const colGeo = new THREE.BoxGeometry(c1, colH, c2);
    const col = new THREE.Mesh(colGeo, new THREE.MeshStandardMaterial({ color: COL.col, roughness: 0.7, metalness: 0.03 }));
    col.position.set(0, h + colH / 2, 0); col.castShadow = true;
    col.userData.sel = 'columna';
    g.add(col);
    const cl = new THREE.LineSegments(new THREE.EdgesGeometry(colGeo),
      new THREE.LineBasicMaterial({ color: COL.edge }));
    cl.position.copy(col.position); g.add(cl);

    // ---- Malla de refuerzo inferior ----
    const matSteel = new THREE.MeshStandardMaterial({ color: COL.steel, roughness: 0.45, metalness: 0.25 });
    const rb = 0.012, rec = 0.07;
    const y1 = rec, y2 = rec + 2 * rb;
    const nz = clamp(Math.round(Bx / 0.25), 3, 12);
    const nx = clamp(Math.round(Ly / 0.25), 3, 12);
    const lenX = Bx - 2 * rec, lenZ = Ly - 2 * rec;
    for (let i = 0; i < nz; i++) {
      const zz = -Ly / 2 + rec + (nz > 1 ? (Ly - 2 * rec) * i / (nz - 1) : 0);
      const bar = new THREE.Mesh(new THREE.BoxGeometry(lenX, rb, rb), matSteel);
      bar.position.set(0, y1, zz); bar.castShadow = true; g.add(bar);
    }
    for (let i = 0; i < nx; i++) {
      const xx = -Bx / 2 + rec + (nx > 1 ? (Bx - 2 * rec) * i / (nx - 1) : 0);
      const bar = new THREE.Mesh(new THREE.BoxGeometry(rb, rb, lenZ), matSteel);
      bar.position.set(xx, y2, 0); bar.castShadow = true; g.add(bar);
    }

    // ---- Etiquetas ----
    const colTop = h + colH;
    const lB = makeLabel('Bx = ' + Bx.toFixed(2) + ' m', '#eaf2ee'); lB.position.set(0, h + 0.05, Ly / 2 + 0.5); g.add(lB);
    const lL = makeLabel('Ly = ' + Ly.toFixed(2) + ' m', '#eaf2ee'); lL.position.set(Bx / 2 + 0.5, h + 0.05, 0); g.add(lL);
    const lh = makeLabel('h = ' + h.toFixed(2) + ' m', '#cfe3d8'); lh.position.set(Bx / 2 + 0.3, h * 0.5, Ly / 2 + 0.05); g.add(lh);
    const lc = makeLabel('columna ' + Math.round(c1 * 100) + '×' + Math.round(c2 * 100) + ' cm', '#dfe8ee'); lc.position.set(0, colTop + 0.3, 0); g.add(lc);
    const ln = makeLabel(coords.length + ' pilote(s) Ø' + Math.round(Dp * 100) + ' cm', '#dfe6f2'); ln.position.set(0, -Lp - 0.25, 0); g.add(ln);

    g.userData.parts = { cabezal: cap, columna: col, pilotes: pileMeshes };
    g.userData.selectable = [cap, col].concat(pileMeshes);
    g.userData.bbox3 = {
      min: new THREE.Vector3(-SX / 2, -Lp - 0.5, -SZ / 2),
      max: new THREE.Vector3(SX / 2, colTop + 0.4, SZ / 2),
    };
    return g;
  }

  function fitCamera() {
    const b = R.group.userData.bbox3;
    const center = b.min.clone().add(b.max).multiplyScalar(0.5);
    const radius = b.max.distanceTo(b.min) * 0.5;
    const fov = R.camera.fov * Math.PI / 180;
    const dist = (radius / Math.sin(fov / 2)) * 1.02;
    const dir = new THREE.Vector3(0.85, 0.6, 1).normalize();
    R.camera.position.copy(center).add(dir.multiplyScalar(dist));
    R.camera.near = Math.max(0.05, dist - radius * 3);
    R.camera.far = dist + radius * 6;
    R.camera.updateProjectionMatrix();
    R.controls.target.copy(center);
    R.controls.update();
  }

  function resize() {
    if (!R.renderer || !R.container) return;
    const w = R.container.clientWidth || 600;
    const h = R.container.clientHeight || 480;
    R.renderer.setSize(w, h, false);
    R.camera.aspect = w / Math.max(1, h);
    R.camera.updateProjectionMatrix();
  }

  function loop() {
    R.raf = requestAnimationFrame(loop);
    R.controls.update();
    R.renderer.render(R.scene, R.camera);
  }

  function init(container) {
    R.container = container;
    container.innerHTML = '';
    R.renderer = new THREE.WebGLRenderer({ antialias: true });
    R.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    R.renderer.setClearColor(COL.bg, 1);
    R.renderer.shadowMap.enabled = true;
    R.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    R.renderer.domElement.style.cssText = 'display:block;width:100%;height:100%;border-radius:10px;cursor:grab';
    container.appendChild(R.renderer.domElement);

    R.scene = new THREE.Scene();
    R.scene.background = new THREE.Color(COL.bg);
    R.scene.fog = new THREE.Fog(COL.bg, 30, 90);
    R.camera = new THREE.PerspectiveCamera(45, 1, 0.05, 4000);

    R.controls = new THREE.OrbitControls(R.camera, R.renderer.domElement);
    R.controls.enableDamping = true;
    R.controls.dampingFactor = 0.08;
    R.controls.maxPolarAngle = Math.PI * 0.96;
    R.controls.addEventListener('start', () => { R.renderer.domElement.style.cursor = 'grabbing'; });
    R.controls.addEventListener('end', () => { R.renderer.domElement.style.cursor = 'grab'; });

    const hemi = new THREE.HemisphereLight(0xcfe0db, 0x26332c, 0.55);
    R.sun = new THREE.DirectionalLight(0xfff4e2, 1.05);
    R.sun.castShadow = true;
    R.sun.shadow.mapSize.width = 1024;
    R.sun.shadow.mapSize.height = 1024;
    R.sun.shadow.bias = -0.0006;
    const fill = new THREE.DirectionalLight(0xbfe0ff, 0.28); fill.position.set(-4, 3, -5);
    const amb = new THREE.AmbientLight(0xffffff, 0.22);
    R.scene.add(hemi, R.sun, R.sun.target, fill, amb);

    R.raycaster = (typeof THREE.Raycaster !== 'undefined') ? new THREE.Raycaster() : null;
    R.onDbl = () => fitCamera();
    R.renderer.domElement.addEventListener('dblclick', R.onDbl);
    R.onMove = (ev) => onPointerMove(ev);
    R.onDown = (ev) => { R.downXY = [ev.clientX, ev.clientY]; };
    R.onUp = (ev) => onPointerUp(ev);
    R.renderer.domElement.addEventListener('pointermove', R.onMove);
    R.renderer.domElement.addEventListener('pointerdown', R.onDown);
    R.renderer.domElement.addEventListener('pointerup', R.onUp);
    if ('ResizeObserver' in window) {
      R.ro = new ResizeObserver(() => resize());
      R.ro.observe(container);
    } else { window.addEventListener('resize', resize); }
  }

  function addGrid(prof, S) {
    const size = Math.max(2 * S, prof) * 1.3;
    const grid = new THREE.GridHelper(size, clamp(Math.round(size), 6, 30), COL.grid, COL.grid);
    grid.position.set(0, R.group.userData.bbox3.min.y + 0.005, 0);
    grid.material.opacity = 0.4; grid.material.transparent = true;
    R.scene.add(grid);
    R.group.userData.grid = grid;
  }

  function updateSun() {
    const b = R.group.userData.bbox3;
    const span = Math.max(b.max.x - b.min.x, b.max.z - b.min.z, b.max.y - b.min.y);
    R.sun.position.set(b.max.x + span * 0.5, b.max.y + span * 0.9, b.max.z + span * 0.35);
    if (R.sun.target) { R.sun.target.position.set(0, (b.min.y + b.max.y) / 2, 0); if (R.sun.target.updateMatrixWorld) R.sun.target.updateMatrixWorld(); }
    const sc = R.sun.shadow && R.sun.shadow.camera;
    if (sc) {
      sc.left = -span; sc.right = span; sc.top = span; sc.bottom = -span;
      sc.near = 0.1; sc.far = span * 4.5;
      if (sc.updateProjectionMatrix) sc.updateProjectionMatrix();
    }
  }

  function swapGroup(payload) {
    R.payload = payload;
    if (R.group) {
      if (R.group.userData.grid) R.scene.remove(R.group.userData.grid);
      R.scene.remove(R.group); disposeObject(R.group);
    }
    R.group = buildGroup(payload);
    R.scene.add(R.group);
    const b = R.group.userData.bbox3;
    addGrid(b.max.y - b.min.y, b.max.x);
    updateSun();
    if (R.selTipo) applySel(R.selTipo);          // conserva el resaltado al recalcular
  }

  function dispose() {
    if (R.raf) cancelAnimationFrame(R.raf);
    if (R.ro && R.container) { try { R.ro.disconnect(); } catch (e) {} }
    else window.removeEventListener('resize', resize);
    if (R.renderer) {
      if (R.onDbl) R.renderer.domElement.removeEventListener('dblclick', R.onDbl);
      if (R.onMove) R.renderer.domElement.removeEventListener('pointermove', R.onMove);
      if (R.onDown) R.renderer.domElement.removeEventListener('pointerdown', R.onDown);
      if (R.onUp) R.renderer.domElement.removeEventListener('pointerup', R.onUp);
      if (R.controls) R.controls.dispose();
      if (R.group) disposeObject(R.group);
      if (R.group && R.group.userData.grid) {
        R.group.userData.grid.geometry.dispose();
        R.group.userData.grid.material.dispose();
      }
      R.renderer.dispose();
      try { R.renderer.forceContextLoss(); } catch (e) {}
      if (R.renderer.domElement && R.renderer.domElement.parentNode) {
        R.renderer.domElement.parentNode.removeChild(R.renderer.domElement);
      }
    }
    R = { renderer: null, scene: null, camera: null, controls: null, sun: null,
          group: null, raf: null, ro: null, container: null, onDbl: null,
          raycaster: null, pointer: { x: 0, y: 0 }, selected: null, selTipo: null,
          hovered: null, onSelect: null, payload: null,
          onDown: null, onUp: null, onMove: null, downXY: null };
  }

  return {
    isAvailable: function () {
      return (typeof THREE !== 'undefined') && (typeof THREE.OrbitControls !== 'undefined');
    },
    render: function (payload, container, opts) {
      opts = opts || {};
      if (!this.isAvailable()) {
        container.innerHTML = '<div style="padding:36px;text-align:center;color:#a00">No se pudo cargar el motor 3D.</div>';
        return;
      }
      if (R.renderer && R.container === container) {
        if (opts.onSelect !== undefined) R.onSelect = opts.onSelect;
        swapGroup(payload);
        return;
      }
      dispose();
      init(container);
      if (opts.onSelect !== undefined) R.onSelect = opts.onSelect;
      swapGroup(payload);
      resize();
      fitCamera();
      loop();
    },
    selectTipo: function (t) {
      if (!R.group) return;
      applySel(t);
      if (typeof R.onSelect === 'function') R.onSelect(t ? _selInfo(t, null) : null);
    },
    rehighlight: function (t) { if (R.group) applySel(t); },
    clearSelection: function () { if (R.group) applySel(null); },
    reset: function () { if (R.renderer) fitCamera(); },
    dispose: dispose,
  };
})();
