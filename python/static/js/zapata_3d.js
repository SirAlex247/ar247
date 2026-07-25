/* ============================================================
   CimX — Visor 3D de la zapata (Three.js + OrbitControls)
   Losa + arranque de columna embebidos en el suelo, con malla de
   refuerzo, sombras suaves, etiquetas de cota y flechas de presión q_u.
   Instancia única (un contexto WebGL).
   ============================================================ */
'use strict';

window.CimXFooting3D = (function () {

  const COL = {
    concrete: 0x9aa3ab, concrete2: 0x7f8890, col: 0xb4bdc4,
    soil: 0xc4a464, grass: 0x6aa860, steel: 0xe07a3a,
    edge: 0x223129, bg: 0x0b1813, grid: 0x274034, arrow: 0xf0c24a,
  };

  let R = {
    renderer: null, scene: null, camera: null, controls: null, sun: null,
    group: null, raf: null, ro: null, container: null, onDbl: null,
  };

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

  /* --- Etiqueta de texto flotante (sprite con textura de canvas) --- */
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

  function buildGroup(p) {
    const g = new THREE.Group();
    const B = p.B || 1, L = p.L || 1, h = p.h || 0.3;
    const c1 = p.c1 || 0.4, c2 = p.c2 || 0.4;
    const Df = (p.Df && p.Df > h) ? p.Df : (h + 0.4);
    const SX = Math.max(1.7 * B, B + 1.4);
    const SZ = Math.max(1.7 * L, L + 1.4);
    const colTop = Df + 0.6;

    // Terreno (recibe sombra)
    const grass = new THREE.Mesh(
      new THREE.BoxGeometry(SX * 1.12, 0.04, SZ * 1.12),
      new THREE.MeshStandardMaterial({ color: COL.grass, roughness: 0.95, metalness: 0.0 }));
    grass.position.set(0, Df, 0); grass.receiveShadow = true;
    g.add(grass);

    // Suelo (bloque translúcido de 0 a Df)
    const soilGeo = new THREE.BoxGeometry(SX, Df, SZ);
    const soil = new THREE.Mesh(soilGeo, new THREE.MeshStandardMaterial({
      color: COL.soil, roughness: 1.0, transparent: true, opacity: 0.22, depthWrite: false }));
    soil.position.set(0, Df / 2, 0);
    g.add(soil);
    const se = new THREE.LineSegments(new THREE.EdgesGeometry(soilGeo),
      new THREE.LineBasicMaterial({ color: COL.soil, transparent: true, opacity: 0.45 }));
    se.position.copy(soil.position); g.add(se);

    // Zapata (losa) — proyecta y recibe sombra
    const slabGeo = new THREE.BoxGeometry(B, h, L);
    const slab = new THREE.Mesh(slabGeo, new THREE.MeshStandardMaterial({
      color: COL.concrete, roughness: 0.85, metalness: 0.02 }));
    slab.position.set(0, h / 2, 0);
    slab.castShadow = true; slab.receiveShadow = true;
    g.add(slab);
    const sl = new THREE.LineSegments(new THREE.EdgesGeometry(slabGeo),
      new THREE.LineBasicMaterial({ color: COL.edge }));
    sl.position.copy(slab.position); g.add(sl);

    // Columna (arranque)
    const colH = colTop - h;
    const colGeo = new THREE.BoxGeometry(c1, colH, c2);
    const col = new THREE.Mesh(colGeo, new THREE.MeshStandardMaterial({
      color: COL.col, roughness: 0.7, metalness: 0.03 }));
    col.position.set(0, h + colH / 2, 0);
    col.castShadow = true;
    g.add(col);
    const cl = new THREE.LineSegments(new THREE.EdgesGeometry(colGeo),
      new THREE.LineBasicMaterial({ color: COL.edge }));
    cl.position.copy(col.position); g.add(cl);

    // Refuerzo inferior (malla en dos direcciones)
    const matSteel = new THREE.MeshStandardMaterial({ color: COL.steel, roughness: 0.45, metalness: 0.25 });
    const rb = 0.012, rec = 0.06;
    const y1 = rec, y2 = rec + 2 * rb;
    const nz = clamp(Math.round(B / 0.22), 4, 12);
    const nx = clamp(Math.round(L / 0.22), 4, 12);
    const lenX = B - 2 * rec, lenZ = L - 2 * rec;
    for (let i = 0; i < nz; i++) {
      const zz = -L / 2 + rec + (nz > 1 ? (L - 2 * rec) * i / (nz - 1) : 0);
      const bar = new THREE.Mesh(new THREE.BoxGeometry(lenX, rb, rb), matSteel);
      bar.position.set(0, y1, zz); bar.castShadow = true; g.add(bar);
    }
    for (let i = 0; i < nx; i++) {
      const xx = -B / 2 + rec + (nx > 1 ? (B - 2 * rec) * i / (nx - 1) : 0);
      const bar = new THREE.Mesh(new THREE.BoxGeometry(rb, rb, lenZ), matSteel);
      bar.position.set(xx, y2, 0); bar.castShadow = true; g.add(bar);
    }

    // Flechas de presión q_u (conos hacia arriba bajo la zapata)
    const coneMat = new THREE.MeshStandardMaterial({ color: COL.arrow, roughness: 0.5, emissive: 0x3a2c08 });
    const nq = clamp(Math.round(B / 0.7), 2, 4);
    for (let i = 0; i <= nq; i++) {
      for (let j = 0; j <= nq; j++) {
        const xx = -B / 2 + B * i / nq, zz = -L / 2 + L * j / nq;
        const cone = new THREE.Mesh(new THREE.ConeGeometry(0.06, 0.22, 12), coneMat);
        cone.position.set(xx, -0.16, zz);  // apex hacia arriba, bajo la losa
        g.add(cone);
      }
    }

    // Etiquetas de cota
    const yLab = h * 0.55;
    const lB = makeLabel('B = ' + B.toFixed(2) + ' m', '#eaf2ee'); lB.position.set(0, 0.05, L / 2 + 0.45); g.add(lB);
    const lL = makeLabel('L = ' + L.toFixed(2) + ' m', '#eaf2ee'); lL.position.set(B / 2 + 0.45, 0.05, 0); g.add(lL);
    const lh = makeLabel('h = ' + h.toFixed(2) + ' m', '#cfe3d8'); lh.position.set(B / 2 + 0.28, yLab, L / 2 + 0.05); g.add(lh);
    const lc = makeLabel('columna ' + Math.round(c1 * 100) + '×' + Math.round(c2 * 100) + ' cm', '#dfe8ee'); lc.position.set(0, colTop + 0.28, 0); g.add(lc);
    const ld = makeLabel('Df = ' + Df.toFixed(2) + ' m', '#e7d9b0'); ld.position.set(-B / 2 - 0.45, Df * 0.55, 0); g.add(ld);
    const lq = makeLabel('q_u', '#f0c24a'); lq.position.set(0, -0.4, 0); g.add(lq);

    g.userData.bbox3 = {
      min: new THREE.Vector3(-SX / 2, -0.5, -SZ / 2),
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
    R.controls.maxPolarAngle = Math.PI * 0.9;
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

    R.onDbl = () => fitCamera();
    R.renderer.domElement.addEventListener('dblclick', R.onDbl);
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
    if (R.group) {
      if (R.group.userData.grid) R.scene.remove(R.group.userData.grid);
      R.scene.remove(R.group); disposeObject(R.group);
    }
    R.group = buildGroup(payload);
    R.scene.add(R.group);
    const b = R.group.userData.bbox3;
    addGrid(b.max.y - b.min.y, b.max.x);
    updateSun();
  }

  function dispose() {
    if (R.raf) cancelAnimationFrame(R.raf);
    if (R.ro && R.container) { try { R.ro.disconnect(); } catch (e) {} }
    else window.removeEventListener('resize', resize);
    if (R.renderer) {
      if (R.onDbl) R.renderer.domElement.removeEventListener('dblclick', R.onDbl);
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
          group: null, raf: null, ro: null, container: null, onDbl: null };
  }

  return {
    isAvailable: function () {
      return (typeof THREE !== 'undefined') && (typeof THREE.OrbitControls !== 'undefined');
    },
    render: function (payload, container) {
      if (!this.isAvailable()) {
        container.innerHTML = '<div style="padding:36px;text-align:center;color:#a00">No se pudo cargar el motor 3D.</div>';
        return;
      }
      if (R.renderer && R.container === container) { swapGroup(payload); return; }
      dispose();
      init(container);
      swapGroup(payload);
      resize();
      fitCamera();
      loop();
    },
    reset: function () { if (R.renderer) fitCamera(); },
    dispose: dispose,
  };
})();
