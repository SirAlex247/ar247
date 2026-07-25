/* ============================================================
   CimX — Visor 3D del muro (Three.js + OrbitControls)
   Extruye el perfil 2D del muro (mismo modelo que wall_svg.js)
   a un sólido 3D orbitable. Funciona para voladizo y gravedad.
   Una sola instancia activa (un único contexto WebGL).
   ============================================================ */
'use strict';

window.CimXWall3D = (function () {

  // Paleta alineada con el SVG (wall_svg.js)
  const COL = {
    concrete:   0x6f7a83,
    concreteEdge: 0x141a1f,
    fill:       0xb47f51,   // relleno ocre
    foundation: 0x7d6648,   // suelo de cimentación
    grass:      0x5fa052,
    background: 0x0d1c16,
    grid:       0x2a3b34,
  };

  // Estado de la instancia única
  let R = {
    renderer: null, scene: null, camera: null, controls: null,
    group: null, raf: null, ro: null, container: null,
    onDbl: null, lights: null,
  };

  function clamp(v, a, b) { return Math.max(a, Math.min(b, v)); }

  /* ---------- Construcción de mallas ---------- */
  function shapeFrom(poly) {
    const sh = new THREE.Shape();
    sh.moveTo(poly[0][0], poly[0][1]);
    for (let i = 1; i < poly.length; i++) sh.lineTo(poly[i][0], poly[i][1]);
    sh.closePath();
    return sh;
  }

  function extrudeMesh(poly, depth, color, opts = {}) {
    const geo = new THREE.ExtrudeGeometry(shapeFrom(poly), {
      depth: depth, bevelEnabled: false, steps: 1,
    });
    geo.translate(0, 0, -depth / 2);           // centrar en Z
    const mat = new THREE.MeshStandardMaterial({
      color: color,
      roughness: opts.roughness != null ? opts.roughness : 0.92,
      metalness: 0.0,
      side: THREE.DoubleSide,
      flatShading: false,
    });
    if (opts.opacity != null && opts.opacity < 1) {
      mat.transparent = true; mat.opacity = opts.opacity;
    }
    const mesh = new THREE.Mesh(geo, mat);
    if (opts.edges) {
      const eg = new THREE.EdgesGeometry(geo, 20);
      const el = new THREE.LineSegments(
        eg, new THREE.LineBasicMaterial({ color: COL.concreteEdge }));
      mesh.add(el);
    }
    return mesh;
  }

  function buildGroup(geom) {
    const g = new THREE.Group();
    const bbox = geom.bbox;
    const Wm = bbox.xmax - bbox.xmin;
    const Hm = bbox.ymax - bbox.ymin;
    // Profundidad del "tramo" de muro: proporcional, acotada para que se
    // lea como un bloque 3D (ni lámina, ni losa infinita).
    const L = clamp(0.55 * Math.max(Wm, Hm), 1.2, 6.5);

    const gr = geom.ground;
    // Suelo de cimentación (terracota)
    [gr.below, gr.front_below, gr.back, gr.front_soil].forEach(p => {
      g.add(extrudeMesh(p, L, COL.foundation, { roughness: 1.0 }));
    });
    // Pasto frontal (verde)
    g.add(extrudeMesh(gr.front_grass, L, COL.grass, { roughness: 1.0 }));
    // Relleno (ocre) — ligeramente translúcido para no tapar el muro
    g.add(extrudeMesh(geom.relleno, L, COL.fill, { roughness: 1.0, opacity: 0.96 }));
    // Concreto: zapata + vástago/cuerpo, con aristas marcadas
    g.add(extrudeMesh(geom.zapata, L, COL.concrete, { edges: true }));
    g.add(extrudeMesh(geom.vastago || geom.cuerpo, L, COL.concrete, { edges: true }));

    g.userData.bbox3 = {
      min: new THREE.Vector3(bbox.xmin, bbox.ymin, -L / 2),
      max: new THREE.Vector3(bbox.xmax, bbox.ymax,  L / 2),
    };
    return g;
  }

  /* ---------- Cámara: encuadre automático ---------- */
  function fitCamera() {
    const b = R.group.userData.bbox3;
    const center = b.min.clone().add(b.max).multiplyScalar(0.5);
    const radius = b.max.distanceTo(b.min) * 0.5;
    const fov = R.camera.fov * Math.PI / 180;
    const dist = (radius / Math.sin(fov / 2)) * 1.12;
    const dir = new THREE.Vector3(1.05, 0.7, 1.25).normalize();
    R.camera.position.copy(center).add(dir.multiplyScalar(dist));
    R.camera.near = Math.max(0.02, dist - radius * 3);
    R.camera.far  = dist + radius * 6;
    R.camera.updateProjectionMatrix();
    R.controls.target.copy(center);
    R.controls.update();
  }

  /* ---------- Tamaño / resize ---------- */
  function resize() {
    if (!R.renderer || !R.container) return;
    const w = R.container.clientWidth  || 600;
    const h = R.container.clientHeight || 540;
    R.renderer.setSize(w, h, false);
    R.camera.aspect = w / Math.max(1, h);
    R.camera.updateProjectionMatrix();
  }

  /* ---------- Loop ---------- */
  function loop() {
    R.raf = requestAnimationFrame(loop);
    R.controls.update();
    R.renderer.render(R.scene, R.camera);
  }

  /* ---------- Inicialización ---------- */
  function init(container, opts) {
    const bg = (opts && opts.background != null) ? opts.background : COL.background;

    R.container = container;
    container.innerHTML = '';

    R.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
    R.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    R.renderer.setClearColor(bg, 1);
    R.renderer.domElement.style.display = 'block';
    R.renderer.domElement.style.width = '100%';
    R.renderer.domElement.style.height = '100%';
    R.renderer.domElement.style.borderRadius = '10px';
    R.renderer.domElement.style.cursor = 'grab';
    container.appendChild(R.renderer.domElement);

    R.scene = new THREE.Scene();
    R.scene.background = new THREE.Color(bg);

    R.camera = new THREE.PerspectiveCamera(45, 1, 0.05, 2000);

    R.controls = new THREE.OrbitControls(R.camera, R.renderer.domElement);
    R.controls.enableDamping = true;
    R.controls.dampingFactor = 0.08;
    R.controls.rotateSpeed = 0.85;
    R.controls.zoomSpeed = 0.9;
    R.controls.panSpeed = 0.8;
    R.controls.minDistance = 0.5;
    R.controls.maxDistance = 500;
    // No dejar que la cámara pase bajo el suelo
    R.controls.maxPolarAngle = Math.PI * 0.495;
    R.controls.addEventListener('start', () => {
      R.renderer.domElement.style.cursor = 'grabbing';
    });
    R.controls.addEventListener('end', () => {
      R.renderer.domElement.style.cursor = 'grab';
    });

    // Luces
    R.lights = new THREE.Group();
    const hemi = new THREE.HemisphereLight(0xbfd4cf, 0x20302a, 0.6);
    const dir = new THREE.DirectionalLight(0xffffff, 0.85);
    dir.position.set(-3, 5, 6);
    const dir2 = new THREE.DirectionalLight(0xffffff, 0.25);
    dir2.position.set(4, 2, -4);
    const amb = new THREE.AmbientLight(0xffffff, 0.22);
    R.lights.add(hemi, dir, dir2, amb);
    R.scene.add(R.lights);

    // Doble clic = reencuadrar
    R.onDbl = () => fitCamera();
    R.renderer.domElement.addEventListener('dblclick', R.onDbl);

    // Observa cambios de tamaño del contenedor
    if ('ResizeObserver' in window) {
      R.ro = new ResizeObserver(() => resize());
      R.ro.observe(container);
    } else {
      window.addEventListener('resize', resize);
    }
  }

  function addGrid(geom) {
    const bbox = geom.bbox;
    const size = Math.max(bbox.xmax - bbox.xmin, bbox.ymax - bbox.ymin) * 1.6;
    const div = clamp(Math.round(size), 6, 30);
    const grid = new THREE.GridHelper(size, div, COL.grid, COL.grid);
    grid.position.set((bbox.xmin + bbox.xmax) / 2, bbox.ymin + 0.001,
                      0);
    grid.material.opacity = 0.5;
    grid.material.transparent = true;
    R.scene.add(grid);
    R.group.userData.grid = grid;
  }

  function swapGroup(geom) {
    if (R.group) {
      if (R.group.userData.grid) R.scene.remove(R.group.userData.grid);
      R.scene.remove(R.group);
      disposeObject(R.group);
    }
    R.group = buildGroup(geom);
    R.scene.add(R.group);
    addGrid(geom);
  }

  /* ---------- Limpieza ---------- */
  function disposeObject(obj) {
    obj.traverse(o => {
      if (o.geometry) o.geometry.dispose();
      if (o.material) {
        if (Array.isArray(o.material)) o.material.forEach(m => m.dispose());
        else o.material.dispose();
      }
    });
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
    R = {
      renderer: null, scene: null, camera: null, controls: null,
      group: null, raf: null, ro: null, container: null,
      onDbl: null, lights: null,
    };
  }

  /* ---------- API pública ---------- */
  return {
    isAvailable: function () {
      return (typeof THREE !== 'undefined') && (typeof THREE.OrbitControls !== 'undefined');
    },

    /** Dibuja/actualiza el muro 3D dentro de `container`. */
    render: function (geom, container, opts) {
      if (!this.isAvailable()) {
        container.innerHTML = `<div style="padding:36px;text-align:center;color:#a00;font-family:sans-serif">
          No se pudo cargar el motor 3D (Three.js).</div>`;
        return;
      }
      // Reutiliza la instancia si es el mismo contenedor (conserva el ángulo
      // de cámara mientras el usuario edita la geometría).
      if (R.renderer && R.container === container) {
        swapGroup(geom);
        return;
      }
      dispose();
      init(container, opts || {});
      swapGroup(geom);
      resize();
      fitCamera();
      loop();
    },

    /** Reencuadra la cámara al muro. */
    reset: function () { if (R.renderer) fitCamera(); },

    /** Libera el contexto WebGL (al salir de la vista 3D). */
    dispose: dispose,
  };

})();
