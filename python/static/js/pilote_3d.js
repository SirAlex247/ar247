/* ============================================================
   CimX — Visor 3D del pilote (Three.js + OrbitControls)
   Pilote (cilindro + punta) embebido en suelo estratificado translúcido,
   con nivel freático, etiquetas de cota y de cada estrato, sombras suaves.
   Instancia única (un solo contexto WebGL).
   ============================================================ */
'use strict';

window.CimXPile3D = (function () {

  const COL = {
    concrete: 0x9aa3ab, arena: 0xceae72, arcilla: 0x9b8260,
    water: 0x4aa3df, grass: 0x6aa860, edge: 0x223129,
    bg: 0x0b1813, grid: 0x274034,
  };

  let R = {
    renderer: null, scene: null, camera: null, controls: null, sun: null,
    group: null, raf: null, ro: null, container: null, onDbl: null,
  };

  function clamp(v, a, b) { return Math.max(a, Math.min(b, v)); }
  const G = 9.80665;

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
    ctx.beginPath(); ctx.moveTo(x + r, y);
    ctx.arcTo(x + w, y, x + w, y + h, r); ctx.arcTo(x + w, y + h, x, y + h, r);
    ctx.arcTo(x, y + h, x, y, r); ctx.arcTo(x, y, x + w, y, r); ctx.closePath();
  }
  function makeLabel(text, color, sub) {
    const fs = 44, fss = 30, pad = 16;
    const c = document.createElement('canvas');
    const ctx = c.getContext('2d');
    ctx.font = 'bold ' + fs + 'px Inter, Arial, sans-serif';
    const w1 = ctx.measureText(text).width;
    ctx.font = '600 ' + fss + 'px Inter, Arial, sans-serif';
    const w2 = sub ? ctx.measureText(sub).width : 0;
    const w = Math.max(w1, w2);
    c.width = Math.ceil(w + pad * 2);
    c.height = (sub ? fs + fss + 10 : fs) + pad * 2;
    ctx.fillStyle = 'rgba(8,18,14,0.82)';
    roundRect(ctx, 1, 1, c.width - 2, c.height - 2, 15); ctx.fill();
    ctx.strokeStyle = 'rgba(120,160,140,0.5)'; ctx.lineWidth = 2;
    roundRect(ctx, 1, 1, c.width - 2, c.height - 2, 15); ctx.stroke();
    ctx.textAlign = 'center';
    ctx.fillStyle = color || '#eaf2ee';
    ctx.font = 'bold ' + fs + 'px Inter, Arial, sans-serif';
    ctx.textBaseline = 'middle';
    ctx.fillText(text, c.width / 2, pad + fs / 2);
    if (sub) {
      ctx.fillStyle = 'rgba(200,215,205,0.9)';
      ctx.font = '600 ' + fss + 'px Inter, Arial, sans-serif';
      ctx.fillText(sub, c.width / 2, pad + fs + 6 + fss / 2);
    }
    const tex = new THREE.CanvasTexture(c); tex.minFilter = THREE.LinearFilter;
    const sp = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, transparent: true, depthTest: false, depthWrite: false }));
    const s = 0.0042;
    sp.scale.set(c.width * s, c.height * s, 1);
    return sp;
  }

  function buildGroup(payload) {
    const g = new THREE.Group();
    const D = payload.D || 0.5, L = payload.L || 8;
    const N = Math.max(1, payload.N || 1);
    const r = D / 2;
    const s = 3 * D;                          // separación entre ejes
    const cols = Math.min(N, Math.ceil(Math.sqrt(N)));
    const rows = Math.ceil(N / cols);
    const pos = [];
    let k = 0;
    for (let i = 0; i < rows && k < N; i++)
      for (let j = 0; j < cols && k < N; j++, k++)
        pos.push([(j - (cols - 1) / 2) * s, (i - (rows - 1) / 2) * s]);
    const spanX = (cols - 1) * s, spanZ = (rows - 1) * s;
    const S = Math.max(1.5, spanX / 2 + 2 * D, spanZ / 2 + 2 * D);
    const prof = L * 1.06;

    // Suelo translúcido
    const soil = new THREE.Mesh(new THREE.BoxGeometry(2 * S, prof, 2 * S),
      new THREE.MeshStandardMaterial({ color: COL.arena, roughness: 1.0, transparent: true, opacity: 0.16, depthWrite: false }));
    soil.position.set(0, -prof / 2, 0); g.add(soil);
    const se = new THREE.LineSegments(new THREE.EdgesGeometry(soil.geometry),
      new THREE.LineBasicMaterial({ color: COL.arena, transparent: true, opacity: 0.4 }));
    se.position.copy(soil.position); g.add(se);

    // Superficie del terreno (recibe sombra)
    const surf = new THREE.Mesh(new THREE.BoxGeometry(2 * S * 1.04, 0.04, 2 * S * 1.04),
      new THREE.MeshStandardMaterial({ color: COL.grass, roughness: 0.95 }));
    surf.receiveShadow = true; g.add(surf);

    // Pilotes (cilindro + punta cónica) con barras representativas
    const matC = new THREE.MeshStandardMaterial({ color: COL.concrete, roughness: 0.82, metalness: 0.03 });
    const matSteel = new THREE.MeshStandardMaterial({ color: 0xe07a3a, roughness: 0.45, metalness: 0.25 });
    pos.forEach(([x, zz]) => {
      const pil = new THREE.Mesh(new THREE.CylinderGeometry(r, r, L, 28), matC);
      pil.position.set(x, -L / 2, zz); pil.castShadow = true; g.add(pil);
      const tip = new THREE.Mesh(new THREE.ConeGeometry(r, r * 1.4, 28), matC);
      tip.position.set(x, -L - r * 0.7, zz); tip.rotation.x = Math.PI; tip.castShadow = true; g.add(tip);
      const nbar = 6, rb = Math.max(0.04, r - 0.05);
      for (let i = 0; i < nbar; i++) {
        const a = 2 * Math.PI * i / nbar;
        const bar = new THREE.Mesh(new THREE.CylinderGeometry(0.012, 0.012, Math.max(0.2, L - 0.1), 6), matSteel);
        bar.position.set(x + rb * Math.cos(a), -L / 2, zz + rb * Math.sin(a)); g.add(bar);
      }
    });

    // Etiquetas
    const lD = makeLabel('D = ' + D.toFixed(2) + ' m', '#eaf2ee'); lD.position.set(pos[0][0], 0.55, pos[0][1]); g.add(lD);
    const lL = makeLabel('L = ' + L.toFixed(2) + ' m', '#eaf2ee'); lL.position.set(-S - 0.5, -L / 2, 0); g.add(lL);
    const lN = makeLabel(N + ' pilote(s) Ø' + (D * 100).toFixed(0) + ' cm', '#dfe6f2'); lN.position.set(0, 0.95, -S - 0.3); g.add(lN);

    g.userData.bbox3 = {
      min: new THREE.Vector3(-(S + 0.7), -(prof + 0.4), -(S + 0.4)),
      max: new THREE.Vector3(S + 0.7, 1.0, S + 0.4),
    };
    return g;
  }

  function fitCamera() {
    const b = R.group.userData.bbox3;
    const center = b.min.clone().add(b.max).multiplyScalar(0.5);
    const radius = b.max.distanceTo(b.min) * 0.5;
    const fov = R.camera.fov * Math.PI / 180;
    const dist = (radius / Math.sin(fov / 2)) * 1.04;
    const dir = new THREE.Vector3(0.9, 0.4, 1).normalize();
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
    R.scene.fog = new THREE.Fog(COL.bg, 40, 120);
    R.camera = new THREE.PerspectiveCamera(45, 1, 0.05, 4000);

    R.controls = new THREE.OrbitControls(R.camera, R.renderer.domElement);
    R.controls.enableDamping = true;
    R.controls.dampingFactor = 0.08;
    R.controls.maxPolarAngle = Math.PI * 0.95;
    R.controls.addEventListener('start', () => { R.renderer.domElement.style.cursor = 'grabbing'; });
    R.controls.addEventListener('end', () => { R.renderer.domElement.style.cursor = 'grab'; });

    const hemi = new THREE.HemisphereLight(0xcfe0db, 0x26332c, 0.6);
    R.sun = new THREE.DirectionalLight(0xfff4e2, 0.95);
    R.sun.castShadow = true;
    R.sun.shadow.mapSize.width = 1024; R.sun.shadow.mapSize.height = 1024;
    R.sun.shadow.bias = -0.0006;
    const fill = new THREE.DirectionalLight(0xbfe0ff, 0.25); fill.position.set(-4, 3, -5);
    const amb = new THREE.AmbientLight(0xffffff, 0.24);
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
    grid.position.set(0, R.group.userData.bbox3.min.y + 0.01, 0);
    grid.material.opacity = 0.4; grid.material.transparent = true;
    R.scene.add(grid);
    R.group.userData.grid = grid;
  }

  function updateSun() {
    const b = R.group.userData.bbox3;
    const span = Math.max(b.max.x - b.min.x, b.max.z - b.min.z, b.max.y - b.min.y);
    R.sun.position.set(b.max.x + span * 0.5, b.max.y + span * 0.7, b.max.z + span * 0.35);
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
