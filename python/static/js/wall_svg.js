/* ============================================================
   CimX — Renderizador SVG del muro (rediseñado)
   Estilo: tema oscuro alineado con la interfaz. Cotas en verde
   neón sobre fondo verde-oscuro, texturas con SVG patterns,
   sombras sutiles para dar volumen.
   ============================================================ */
'use strict';

window.CimXWallSVG = (function () {

  // ID único de la instancia actual (se reasigna en cada render para evitar
  // colisiones cuando hay múltiples SVGs en la misma página).
  let ID = { arrow: 'arrow', arrowLoad: 'arrow-load', shadow: 'shadow' };

  /* ---------- Tokens visuales ---------- */
  const STYLE = {
    // Fondo del SVG (combina con --bg-input de la app)
    background:      '#0d1c16',

    // Materiales — colores base + sombra para shading
    concrete:        '#5b6770',
    concreteHL:      '#6f7a83',          // highlight (cara iluminada)
    concreteShadow:  '#3d464d',          // sombra (cara opuesta)
    concreteEdge:    '#1f262c',          // borde

    fill:            '#b47f51',          // relleno ocre
    fillHL:          '#e0a067',
    fillShadow:      '#9a6432',
    fillEdge:        '#3a2916',

    grass:           '#5fa052',          // pasto vista frontal
    grassHL:         '#7dbd6d',
    grassShadow:     '#3d6e34',
    grassEdge:       '#1f3a18',

    foundation:      '#7d6648',          // suelo de cimentación
    foundationHL:    '#977d57',
    foundationShadow:'#503f2c',
    foundationEdge:  '#23190f',

    sobrecarga:      '#9ca3af',          // gris claro para la sobrecarga
    sobrecargaEdge:  '#4b5563',

    // Cotas — color claro para líneas, blanco para números
    dimLine:         '#dbe0de',          // color claro (líneas y flechas)
    dimText:         '#ffffff',          // BLANCO para los números
    dimTextSubtle:   '#a7c4b6',          // texto secundario / labels
    centerLine:      '#a7c4b6',          // ejes auxiliares (más apagado)

    // Tipografía
    fontFamily:      "'Inter', system-ui, sans-serif",
    fontMono:        "'JetBrains Mono', 'SF Mono', monospace",
  };

  const TXT = {
    dim:    22,
    label:  18,
    title:  20,
  };

  /* ---------- Helpers de geometría ---------- */
  /**
   * Construye coordenadas del muro voladizo. Origen en esquina inferior
   * izquierda de la zapata, X→derecha, Y→arriba.
   */
  function buildVoladizo(d) {
    const {
      H_vastago, e_zapata,
      b_puntera, b_talon, b_corona, b_base_vast, D
    } = d;

    const H_relleno = (d.H_relleno && d.H_relleno > 0) ? d.H_relleno : H_vastago;
    const alpha = d.alpha || 0;
    const alphaRad = alpha * Math.PI / 180;
    const B = b_puntera + b_base_vast + b_talon;

    // Vástago acartelado. Acartelamiento independiente frontal/posterior; si no
    // se especifica, todo el batter va al frente (cara posterior vertical).
    const af = (d.a_frontal_v != null) ? d.a_frontal_v : (b_base_vast - b_corona);
    const ap = (d.a_posterior_v != null) ? d.a_posterior_v : 0;
    const vast_x_left  = b_puntera;
    const vast_x_right = b_puntera + b_base_vast;
    const vast_y_bot   = e_zapata;
    const vast_y_top   = e_zapata + H_vastago;
    const corona_x_left  = b_puntera + af;
    const corona_x_right = b_puntera + b_base_vast - ap;

    const vastago = [
      [vast_x_left,    vast_y_bot],
      [vast_x_right,   vast_y_bot],
      [corona_x_right, vast_y_top],
      [corona_x_left,  vast_y_top],
    ];

    const zapata = [
      [0, 0], [B, 0], [B, e_zapata], [0, e_zapata]
    ];

    // Relleno detrás del vástago, sobre el talón. La cara izquierda sigue la
    // cara posterior del vástago (inclinada si hay acartelamiento posterior).
    const xbp = vast_x_right;                                  // cara posterior, base
    const fracR = (H_vastago > 0) ? Math.min(1, H_relleno / H_vastago) : 1;
    const rell_x_left  = xbp - ap * fracR;     // contacto a la altura del relleno
    const rell_x_right = B;
    const rell_y_left  = e_zapata + H_relleno;
    const rell_y_right = rell_y_left + (rell_x_right - rell_x_left) * Math.tan(alphaRad);

    const relleno = [
      [xbp,          e_zapata],
      [rell_x_right, e_zapata],
      [rell_x_right, rell_y_right],
      [rell_x_left,  rell_y_left],
    ];

    // Sobrecarga: rectángulo paralelo a la pendiente del relleno, sobre el
    // relleno con un pequeño gap. Su espesor es proporcional a q (visual).
    let sobrecarga_polygon = null;
    let sobrecarga_height_m = 0;
    const q = d.sobrecarga || 0;     // tonf/m²
    if (q > 0) {
      // Largo visual de las flechas: 5% de H_relleno por cada tonf/m²,
      // capeado a [0.18, 0.50] m. Más cortas que el rectángulo anterior
      // para que las flechas se lean bien sin dominar.
      sobrecarga_height_m = Math.max(0.18, Math.min(0.50, H_relleno * 0.05 * q));
      const gap = 0.10;        // separación visual del relleno
      // Vértices: paralelos a la pendiente del relleno
      // Base inferior = top del relleno + gap (perpendicular a la pendiente)
      const cosA = Math.cos(alphaRad);
      const dx_perp = -Math.sin(alphaRad);   // dirección perpendicular hacia arriba
      const dy_perp =  cosA;
      // Pie izquierdo del rectángulo
      const p1x = rell_x_left  + dx_perp * gap;
      const p1y = rell_y_left  + dy_perp * gap;
      const p2x = rell_x_right + dx_perp * gap;
      const p2y = rell_y_right + dy_perp * gap;
      // Top del rectángulo (a sobrecarga_height_m perpendicular hacia arriba)
      const p3x = p2x + dx_perp * sobrecarga_height_m;
      const p3y = p2y + dy_perp * sobrecarga_height_m;
      const p4x = p1x + dx_perp * sobrecarga_height_m;
      const p4y = p1y + dy_perp * sobrecarga_height_m;
      sobrecarga_polygon = [[p1x, p1y], [p2x, p2y], [p3x, p3y], [p4x, p4y]];
    }

    // Suelos
    const terr_y = D;       // terreno frontal
    const margin_x = Math.max(B * 0.15, 0.4);
    const margin_y = Math.max(D * 0.50, 0.7);

    const ground = {
      // Terreno frontal — pasto verde arriba, suelo terracota debajo.
      // El pasto se extiende DESDE la cara frontal del vástago (x=b_puntera)
      // hasta el borde izquierdo del SVG. Esto cubre el "recuadro rojo"
      // que quedaba hueco encima de la puntera.
      front_grass: [
        [-margin_x,    terr_y],
        [b_puntera,    terr_y],
        [b_puntera,    terr_y - 0.20],
        [-margin_x,    terr_y - 0.20],
      ],
      front_soil: [
        // Cubre desde la base del pasto hacia abajo, extendiéndose por
        // encima de la zapata frontal hasta tocar el vástago.
        [-margin_x,    terr_y - 0.20],
        [b_puntera,    terr_y - 0.20],
        [b_puntera,    e_zapata],         // baja por la cara izq del vástago
        [-margin_x,    e_zapata],
      ],
      below: [
        [0, 0], [B, 0], [B, -margin_y], [0, -margin_y]
      ],
      // Suelo de cimentación al frente, debajo del nivel de la zapata
      front_below: [
        [-margin_x, e_zapata],
        [0,         e_zapata],
        [0,         -margin_y],
        [-margin_x, -margin_y],
      ],
      back: [
        [B, 0], [B + margin_x, 0],
        [B + margin_x, -margin_y], [B, -margin_y]
      ],
    };

    // Y máxima del bbox: incluir sobrecarga si existe
    let ymax_total = Math.max(rell_y_right, vast_y_top) + 0.2;
    if (sobrecarga_polygon) {
      const max_y_sob = Math.max(...sobrecarga_polygon.map(p => p[1]));
      ymax_total = Math.max(ymax_total, max_y_sob + 0.2);
    }

    return {
      tipo: 'voladizo',
      vastago, zapata, relleno, ground,
      sobrecarga: sobrecarga_polygon,
      cotas: {
        B, H_vastago, e_zapata, b_puntera, b_talon, b_corona, b_base_vast,
        D, H_relleno, alpha, terr_y,
        a_frontal_v: af, a_posterior_v: ap,
        sobrecarga: q,
        sobrecarga_height_m,
      },
      bbox: {
        xmin: -margin_x, xmax: B + margin_x,
        ymin: -margin_y, ymax: ymax_total,
      },
    };
  }

  /**
   * Construye coordenadas del muro de gravedad (trapezoidal macizo sobre
   * zapata). Replica el modelo del backend (geometria_gravedad.py →
   * vertices_cuerpo / vertices_zapata). Mismo sistema de ejes que voladizo:
   * origen en la esquina inferior izquierda de la zapata (puntera C).
   */
  function buildGravedad(d) {
    const {
      H_muro, e_zapata, b_corona,
      a_frontal, a_posterior, b_puntera, b_talon, D
    } = d;

    const alpha = d.alpha || 0;
    const alphaRad = alpha * Math.PI / 180;
    const tanA = Math.tan(alphaRad);

    const B = b_puntera + a_frontal + b_corona + a_posterior + b_talon;
    const y_base = e_zapata;
    const y_top  = e_zapata + H_muro;

    // Cuerpo trapezoidal (CCW desde el pie frontal)
    const x_pie_front = b_puntera;
    const x_pie_post  = b_puntera + a_frontal + b_corona + a_posterior;
    const x_cor_izq   = b_puntera + a_frontal;
    const x_cor_der   = x_cor_izq + b_corona;

    const cuerpo = [
      [x_pie_front, y_base],
      [x_pie_post,  y_base],
      [x_cor_der,   y_top],
      [x_cor_izq,   y_top],
    ];

    const zapata = [
      [0, 0], [B, 0], [B, e_zapata], [0, e_zapata]
    ];

    // Relleno detrás de la cara posterior inclinada, sobre el talón.
    // Top a nivel de corona con pendiente alpha hacia la derecha.
    const rell_x_left  = x_cor_der;
    const rell_x_right = B;
    const rell_y_left  = y_top;
    const rell_y_right = y_top + (rell_x_right - rell_x_left) * tanA;
    const relleno = [
      [x_pie_post,   y_base],
      [B,            y_base],
      [rell_x_right, rell_y_right],
      [rell_x_left,  rell_y_left],
    ];

    // Sobrecarga: mismo criterio visual que el voladizo (rectángulo paralelo
    // a la pendiente del relleno con flechas hacia abajo).
    let sobrecarga_polygon = null;
    let sobrecarga_height_m = 0;
    const q = d.sobrecarga || 0;
    if (q > 0) {
      sobrecarga_height_m = Math.max(0.18, Math.min(0.50, H_muro * 0.05 * q));
      const gap = 0.10;
      const dx_perp = -Math.sin(alphaRad);
      const dy_perp =  Math.cos(alphaRad);
      const p1x = rell_x_left  + dx_perp * gap;
      const p1y = rell_y_left  + dy_perp * gap;
      const p2x = rell_x_right + dx_perp * gap;
      const p2y = rell_y_right + dy_perp * gap;
      const p3x = p2x + dx_perp * sobrecarga_height_m;
      const p3y = p2y + dy_perp * sobrecarga_height_m;
      const p4x = p1x + dx_perp * sobrecarga_height_m;
      const p4y = p1y + dy_perp * sobrecarga_height_m;
      sobrecarga_polygon = [[p1x, p1y], [p2x, p2y], [p3x, p3y], [p4x, p4y]];
    }

    const terr_y = D;
    const margin_x = Math.max(B * 0.15, 0.4);
    const margin_y = Math.max(D * 0.50, 0.7);

    const ground = {
      front_grass: [
        [-margin_x, terr_y],
        [b_puntera, terr_y],
        [b_puntera, terr_y - 0.20],
        [-margin_x, terr_y - 0.20],
      ],
      front_soil: [
        [-margin_x, terr_y - 0.20],
        [b_puntera, terr_y - 0.20],
        [b_puntera, e_zapata],
        [-margin_x, e_zapata],
      ],
      below: [
        [0, 0], [B, 0], [B, -margin_y], [0, -margin_y]
      ],
      front_below: [
        [-margin_x, e_zapata],
        [0,         e_zapata],
        [0,         -margin_y],
        [-margin_x, -margin_y],
      ],
      back: [
        [B, 0], [B + margin_x, 0],
        [B + margin_x, -margin_y], [B, -margin_y]
      ],
    };

    let ymax_total = Math.max(rell_y_right, y_top) + 0.2;
    if (sobrecarga_polygon) {
      const max_y_sob = Math.max(...sobrecarga_polygon.map(p => p[1]));
      ymax_total = Math.max(ymax_total, max_y_sob + 0.2);
    }

    const beta = (a_posterior === 0)
      ? 90 : Math.atan2(H_muro, a_posterior) * 180 / Math.PI;

    return {
      tipo: 'gravedad',
      cuerpo, zapata, relleno, ground,
      sobrecarga: sobrecarga_polygon,
      cotas: {
        B, H_muro, e_zapata, b_corona, a_frontal, a_posterior,
        b_puntera, b_talon, D, alpha, terr_y, beta,
        x_pie_front, x_pie_post, x_cor_izq, x_cor_der,
        sobrecarga: q, sobrecarga_height_m,
      },
      bbox: {
        xmin: -margin_x, xmax: B + margin_x,
        ymin: -margin_y, ymax: ymax_total,
      },
    };
  }

  /* ---------- Construcción del SVG ---------- */
  function render(dims, opts = {}) {
    // Estrategia: el viewBox se calcula PROPORCIONAL al muro real, no en
    // pixels fijos. Reservamos espacio para las cotas como un porcentaje
    // del lado mayor del muro. Así, sin importar el tamaño del card, el
    // muro siempre ocupa la mayor parte del frame.

    const bx = dims.bbox;
    const wx_m = bx.xmax - bx.xmin;        // ancho del muro en metros
    const wy_m = bx.ymax - bx.ymin;        // alto en metros
    const sideMax = Math.max(wx_m, wy_m);

    // Margen para cotas (en METROS, proporcional al muro):
    const m_left   = sideMax * 0.07;
    const m_right  = sideMax * 0.07;
    const m_top    = sideMax * 0.04;
    const m_bottom = sideMax * 0.08;

    // viewBox total en metros (incluyendo márgenes para cotas)
    const vbX = bx.xmin - m_left;
    const vbY = bx.ymin - m_bottom;
    const vbW = wx_m + m_left + m_right;
    const vbH = wy_m + m_top + m_bottom;

    // Pixels por metro: calculado para que el viewBox del SVG quepa cómodo.
    // Usamos un valor base que da buena resolución para los textos.
    const PX_PER_M = 130;
    const W = vbW * PX_PER_M;
    const H = vbH * PX_PER_M;

    // sx / sy convierten metros a coords del SVG con Y invertida.
    // Origen del SVG está en (0,0) pero el contenido va de vbX..vbX+vbW
    // y de (vbY+vbH)..vbY (Y invertido).
    const sx = (x) => (x - vbX) * PX_PER_M;
    const sy = (y) => (vbY + vbH - y) * PX_PER_M;

    // Sufijo único por instancia: evita colisión de IDs cuando hay
    // múltiples SVGs en la misma página (Resumen y Geometría).
    // El navegador toma el PRIMER ID que encuentra, y los markers/filtros
    // del segundo SVG no aparecen.
    const UID = 'w' + Math.random().toString(36).slice(2, 8);
    ID = {
      arrow:     `arrow-${UID}`,
      arrowLoad: `arrow-load-${UID}`,
      shadow:    `shadow-${UID}`,
    };

    let svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${W.toFixed(1)} ${H.toFixed(1)}"
      width="100%" height="100%" preserveAspectRatio="xMidYMin meet"
      style="display:block;background:${STYLE.background};border-radius:10px;font-family:${STYLE.fontFamily}">
      <defs>
        ${defsBlock(ID)}
      </defs>`;

    // ─── 1. Suelos al fondo ───
    svg += polygon(dims.ground.front_below, sx, sy, STYLE.foundation, STYLE.foundationEdge, 0.8);
    svg += polygon(dims.ground.front_soil,  sx, sy, STYLE.foundation, STYLE.foundationEdge, 0.8);
    svg += polygon(dims.ground.below,       sx, sy, STYLE.foundation, STYLE.foundationEdge, 0.8);
    svg += polygon(dims.ground.back,        sx, sy, STYLE.foundation, STYLE.foundationEdge, 0.8);
    // Banda de pasto (encima del suelo frontal)
    svg += polygon(dims.ground.front_grass, sx, sy, STYLE.grass, STYLE.grassEdge, 0.8);

    // Línea horizontal del nivel del terreno frontal (sutil)
    svg += line(sx(bx.xmin) + 4, sy(dims.cotas.terr_y), sx(0), sy(dims.cotas.terr_y),
                STYLE.centerLine, 0.5, ' stroke-dasharray="2 3" opacity="0.4"');

    // ─── 2. Relleno ───
    svg += polygon(dims.relleno, sx, sy, STYLE.fill, STYLE.fillEdge, 0.8);

    // ─── 2.5. Sobrecarga (carga distribuida con flechas hacia abajo) ───
    if (dims.sobrecarga) {
      // dims.sobrecarga = [[p1x,p1y], [p2x,p2y], [p3x,p3y], [p4x,p4y]]
      // donde p1=pie izq, p2=pie der (sobre el relleno),
      //       p3=top der,  p4=top izq (paralelo al relleno arriba)
      const [p1, p2, p3, p4] = dims.sobrecarga;
      // Línea SUPERIOR de la carga distribuida (paralela a la pendiente)
      svg += line(sx(p4[0]), sy(p4[1]), sx(p3[0]), sy(p3[1]),
                  STYLE.sobrecarga, 2);
      // Flechas verticales hacia abajo, espaciadas. Cada flecha va desde
      // un punto interpolado entre p4 y p3 (línea superior) hasta el punto
      // correspondiente entre p1 y p2 (línea inferior, sobre el relleno).
      // El número de flechas es proporcional al ancho del relleno.
      const ancho_carga = Math.hypot(p3[0] - p4[0], p3[1] - p4[1]);  // en m
      const N = Math.max(4, Math.min(10, Math.round(ancho_carga * 3)));
      for (let i = 0; i <= N; i++) {
        const t = i / N;
        // Punto en línea superior
        const tx = p4[0] + t * (p3[0] - p4[0]);
        const ty = p4[1] + t * (p3[1] - p4[1]);
        // Punto en línea inferior (pie - sobre el relleno)
        const bx = p1[0] + t * (p2[0] - p1[0]);
        const by = p1[1] + t * (p2[1] - p1[1]);
        // Flecha vertical hacia abajo (de top hacia pie)
        svg += `<line x1="${sx(tx).toFixed(1)}" y1="${sy(ty).toFixed(1)}"
                      x2="${sx(bx).toFixed(1)}" y2="${sy(by).toFixed(1)}"
                      stroke="${STYLE.sobrecarga}" stroke-width="1.5"
                      marker-end="url(#${ID.arrowLoad})"/>`;
      }
      // Etiqueta "q = X tonf/m²" justo arriba de la línea superior
      const cx_sob = (p3[0] + p4[0]) / 2;
      const cy_sob = (p3[1] + p4[1]) / 2;
      const labelStr = `q = ${dims.cotas.sobrecarga.toFixed(1)} tonf/m²`;
      svg += text(sx(cx_sob), sy(cy_sob) - 14, labelStr, {
        size: TXT.label, fill: '#ffffff', weight: '600',
      });
    }

    // ─── 3. Muro (zapata + vástago/cuerpo) ───
    svg += polygon(dims.zapata,  sx, sy, STYLE.concrete, STYLE.concreteEdge, 0.9);
    svg += polygon(dims.vastago || dims.cuerpo, sx, sy, STYLE.concrete, STYLE.concreteEdge, 0.9);

    // ─── 4. Cotas ───
    svg += (dims.tipo === 'gravedad' ? dimensionsGravedad : dimensions)(dims, sx, sy);

    svg += `</svg>`;
    return svg;
  }

  /* ---------- Defs: filtros, marcadores, gradientes ---------- */
  function defsBlock(ID) {
    return `
      <!-- Sombra suave -->
      <filter id="${ID.shadow}" x="-10%" y="-10%" width="120%" height="120%">
        <feGaussianBlur in="SourceAlpha" stdDeviation="1.5"/>
        <feOffset dx="1" dy="2" result="off"/>
        <feFlood flood-color="#000" flood-opacity="0.45"/>
        <feComposite in2="off" operator="in"/>
        <feMerge><feMergeNode/><feMergeNode in="SourceGraphic"/></feMerge>
      </filter>

      <!-- Marker de flecha para cotas -->
      <marker id="${ID.arrow}" viewBox="0 0 10 10" refX="9" refY="5"
              markerWidth="8" markerHeight="8" orient="auto-start-reverse">
        <path d="M 0 0 L 10 5 L 0 10 z" fill="${STYLE.dimLine}"/>
      </marker>

      <!-- Marker de flecha rellena para carga distribuida (sobrecarga) -->
      <marker id="${ID.arrowLoad}" viewBox="0 0 10 10" refX="9" refY="5"
              markerWidth="6" markerHeight="6" orient="auto">
        <path d="M 0 0 L 10 5 L 0 10 z" fill="${STYLE.sobrecarga}"/>
      </marker>
    `;
  }

  /* ---------- Helpers SVG ---------- */
  function polygon(pts, sx, sy, fill, stroke, strokeW, extra = '') {
    const d = pts.map(([x, y]) => `${sx(x).toFixed(1)},${sy(y).toFixed(1)}`).join(' ');
    return `<polygon points="${d}" fill="${fill}" stroke="${stroke}"
                     stroke-width="${strokeW}" stroke-linejoin="round"${extra}/>`;
  }
  function line(x1, y1, x2, y2, stroke, w = 1, extra = '') {
    return `<line x1="${x1.toFixed(1)}" y1="${y1.toFixed(1)}"
                  x2="${x2.toFixed(1)}" y2="${y2.toFixed(1)}"
                  stroke="${stroke}" stroke-width="${w}"${extra}/>`;
  }
  function text(x, y, str, opts = {}) {
    const anchor = opts.anchor || 'middle';
    const baseline = opts.baseline || 'middle';
    const size = opts.size || TXT.dim;
    const weight = opts.weight || '500';
    const family = opts.family || STYLE.fontMono;
    const fill = opts.fill || STYLE.dimText;
    const trans = opts.transform ? ` transform="${opts.transform}"` : '';
    return `<text x="${x.toFixed(1)}" y="${y.toFixed(1)}"
                  text-anchor="${anchor}" dominant-baseline="${baseline}"
                  font-size="${size}" font-weight="${weight}"
                  font-family="${family}" fill="${fill}"${trans}>${str}</text>`;
  }

  /* ---------- Cotas estilo "moderno": texto encima sin fondo ---------- */

  /**
   * Cota horizontal con texto ENCIMA de la línea (sin fondo, sin partir).
   * El estilo del mockup que el usuario pidió.
   */
  function hDim(ax, bx, y_orig, y_dim, valor_m, opts = {}) {
    const extOver = 6;
    const showExt = opts.showExt !== false;     // líneas de extensión por default
    let s = '';
    if (showExt) {
      s += line(ax, y_orig, ax, y_dim + extOver, STYLE.dimLine, 0.7);
      s += line(bx, y_orig, bx, y_dim + extOver, STYLE.dimLine, 0.7);
    }
    // Línea de cota continua con flechas en ambos extremos
    s += `<line x1="${ax}" y1="${y_dim}" x2="${bx}" y2="${y_dim}"
                stroke="${STYLE.dimLine}" stroke-width="0.7"
                marker-start="url(#${ID.arrow})" marker-end="url(#${ID.arrow})"/>`;
    // Texto encima centrado
    const cx = (ax + bx) / 2;
    const valStr = `${valor_m.toFixed(2)} m`;
    s += text(cx, y_dim - 14, valStr, { size: TXT.dim, weight: '600' });
    // Etiqueta opcional debajo del texto principal
    if (opts.label) {
      s += text(cx, y_dim + 16, opts.label, {
        size: 10, fill: STYLE.dimTextSubtle, weight: '400', family: STYLE.fontFamily,
      });
    }
    return s;
  }

  /** Cota vertical estilo similar al mockup. Texto al lado izquierdo de la
   *  línea, alineado verticalmente al centro, rotado -90°. */
  function vDim(x_orig, x_dim, ya, yb, valor_m, opts = {}) {
    const extOver = 6;
    const showExt = opts.showExt !== false;
    const side = opts.side || 'left';   // 'left' = texto a la izq de la línea
    let s = '';
    if (showExt) {
      s += line(x_orig, ya, x_dim + (side === 'left' ? -extOver : extOver), ya, STYLE.dimLine, 0.7);
      s += line(x_orig, yb, x_dim + (side === 'left' ? -extOver : extOver), yb, STYLE.dimLine, 0.7);
    }
    s += `<line x1="${x_dim}" y1="${ya}" x2="${x_dim}" y2="${yb}"
                stroke="${STYLE.dimLine}" stroke-width="0.7"
                marker-start="url(#${ID.arrow})" marker-end="url(#${ID.arrow})"/>`;
    const cy = (ya + yb) / 2;
    const valStr = `${valor_m.toFixed(2)} m`;
    // Texto rotado, desplazado al lado opuesto a la línea
    const tx = side === 'left' ? x_dim - 16 : x_dim + 16;
    s += `<text x="${tx}" y="${cy}" text-anchor="middle" dominant-baseline="middle"
                font-size="${TXT.dim}" font-weight="600" font-family="${STYLE.fontMono}"
                fill="${STYLE.dimText}"
                transform="rotate(-90, ${tx}, ${cy})">${valStr}</text>`;
    // Etiqueta opcional ("Nivel de desplante")
    if (opts.label) {
      const ltx = side === 'left' ? x_dim - 24 : x_dim + 24;
      s += `<text x="${ltx}" y="${cy}" text-anchor="middle" dominant-baseline="middle"
                  font-size="${TXT.label - 4}" font-weight="400" font-family="${STYLE.fontFamily}"
                  fill="${STYLE.dimTextSubtle}"
                  transform="rotate(-90, ${ltx}, ${cy})">${opts.label}</text>`;
    }
    return s;
  }

  /* ---------- Disposición de las cotas (selectividad) ---------- */
  function dimensions(dims, sx, sy) {
    const c = dims.cotas;
    let s = '';

    // ─── Cotas horizontales abajo ───
    const y_zap_bot = sy(0);
    const y_dim_1   = y_zap_bot + 40;     // primera línea: puntera | base | talón
    const y_dim_2   = y_zap_bot + 70;     // segunda línea: B total
    // Línea 1: las 3 sub-cotas
    s += hDim(sx(0),                                 sx(c.b_puntera),
              y_zap_bot, y_dim_1, c.b_puntera);
    s += hDim(sx(c.b_puntera),                       sx(c.b_puntera + c.b_base_vast),
              y_zap_bot, y_dim_1, c.b_base_vast);
    s += hDim(sx(c.b_puntera + c.b_base_vast),       sx(c.B),
              y_zap_bot, y_dim_1, c.b_talon);
    // Línea 2: B total
    s += hDim(sx(0), sx(c.B), y_zap_bot, y_dim_2, c.B);

    // ─── Cotas verticales a la izquierda ───
    // Col 1 (cerca del muro): D — profundidad de desplante
    // Col 2 (más afuera): H_total
    const x_left = sx(0);
    const x_dim_L1 = x_left - 28;
    const x_dim_L2 = x_left - 65;

    // D — profundidad de desplante
    s += vDim(x_left, x_dim_L1, sy(0), sy(c.terr_y), c.D);
    // H total
    s += vDim(x_left, x_dim_L2, sy(0), sy(c.e_zapata + c.H_vastago),
              c.e_zapata + c.H_vastago);

    // ─── Cotas verticales a la derecha ───
    // Ambas cotas en la MISMA columna externa (alineadas verticalmente).
    // Como cubren tramos Y distintos (e_zapata: 0→e_zap, H_relleno: e_zap→top),
    // no se solapan. Esto da una composición simétrica con la izquierda.
    const x_right = sx(c.B);
    const x_dim_R = x_right + 50;        // columna única externa

    s += vDim(x_right, x_dim_R, sy(0), sy(c.e_zapata), c.e_zapata, { side: 'right' });
    s += vDim(x_right, x_dim_R,
              sy(c.e_zapata),
              sy(c.e_zapata + c.H_relleno),
              c.H_relleno, { side: 'right' });

    // ─── Cota arriba: corona del vástago ───
    if (c.b_corona && c.b_corona > 0) {
      const y_top = sy(c.e_zapata + c.H_vastago);
      const y_dim_top = y_top - 28;
      const afc = (c.a_frontal_v != null) ? c.a_frontal_v : (c.b_base_vast - c.b_corona);
      const x_corona_left  = sx(c.b_puntera + afc);
      const x_corona_right = sx(c.b_puntera + afc + c.b_corona);
      s += hDim(x_corona_left, x_corona_right, y_top, y_dim_top, c.b_corona);
    }

    // ─── Indicación del ángulo α ───
    if (c.alpha && c.alpha > 0) {
      // Posición del α: a la derecha del vástago, sobre la pendiente del
      // relleno. La línea horizontal de referencia sale desde el punto
      // donde el relleno empieza la pendiente (cara posterior del vástago).
      const x_a = sx(c.b_puntera + c.b_base_vast);
      const y_a = sy(c.e_zapata + c.H_relleno);
      // Línea horizontal de referencia (punteada)
      s += line(x_a, y_a, x_a + 90, y_a, STYLE.dimTextSubtle, 0.8,
                ' stroke-dasharray="4 3" opacity="0.7"');
      // Texto "α = X°" un poco más a la derecha y abajo de la línea
      s += text(x_a + 55, y_a + 16, `α = ${c.alpha.toFixed(0)}°`, {
        size: TXT.dim, fill: '#ffffff', weight: '600',
      });
    }

    return s;
  }

  /* ---------- Cotas para el muro de gravedad ---------- */
  function dimensionsGravedad(dims, sx, sy) {
    const c = dims.cotas;
    let s = '';

    // ─── Cotas horizontales abajo: 5 sub-cotas + B total ───
    const y_zap_bot = sy(0);
    const y_dim_1 = y_zap_bot + 40;
    const y_dim_2 = y_zap_bot + 70;
    let x0 = 0;
    const segs = [c.b_puntera, c.a_frontal, c.b_corona, c.a_posterior, c.b_talon];
    for (const w of segs) {
      if (w > 0.005) {
        s += hDim(sx(x0), sx(x0 + w), y_zap_bot, y_dim_1, w);
      }
      x0 += w;
    }
    s += hDim(sx(0), sx(c.B), y_zap_bot, y_dim_2, c.B);

    // ─── Cotas verticales a la izquierda: D y H_total ───
    const x_left = sx(0);
    s += vDim(x_left, x_left - 28, sy(0), sy(c.terr_y), c.D);
    s += vDim(x_left, x_left - 65, sy(0), sy(c.e_zapata + c.H_muro),
              c.e_zapata + c.H_muro);

    // ─── Cotas verticales a la derecha: e_zapata y H_muro ───
    const x_right = sx(c.B);
    const x_dim_R = x_right + 50;
    s += vDim(x_right, x_dim_R, sy(0), sy(c.e_zapata), c.e_zapata, { side: 'right' });
    s += vDim(x_right, x_dim_R,
              sy(c.e_zapata), sy(c.e_zapata + c.H_muro), c.H_muro, { side: 'right' });

    // ─── Cota arriba: corona ───
    if (c.b_corona && c.b_corona > 0) {
      const y_top = sy(c.e_zapata + c.H_muro);
      s += hDim(sx(c.x_cor_izq), sx(c.x_cor_der), y_top, y_top - 28, c.b_corona);
    }

    // ─── Ángulo β de la cara posterior (a media altura) ───
    if (c.a_posterior > 0) {
      const x_mid = sx((c.x_pie_post + c.x_cor_der) / 2);
      const y_mid = sy(c.e_zapata + c.H_muro / 2);
      s += text(x_mid + 22, y_mid, `β = ${c.beta.toFixed(0)}°`, {
        size: TXT.dim, fill: '#ffffff', weight: '600',
      });
    }

    // ─── Ángulo α del relleno (si hay pendiente) ───
    if (c.alpha && c.alpha > 0) {
      const x_a = sx(c.x_cor_der);
      const y_a = sy(c.e_zapata + c.H_muro);
      s += line(x_a, y_a, x_a + 80, y_a, STYLE.dimTextSubtle, 0.8,
                ' stroke-dasharray="4 3" opacity="0.7"');
      s += text(x_a + 48, y_a + 16, `α = ${c.alpha.toFixed(0)}°`, {
        size: TXT.dim, fill: '#ffffff', weight: '600',
      });
    }

    return s;
  }

  /* ---------- API pública ---------- */
  return {
    renderVoladizo: function (dims_input, container, opts) {
      const required = ['H_vastago', 'e_zapata', 'b_puntera', 'b_talon',
                        'b_corona', 'b_base_vast', 'D'];
      for (const k of required) {
        if (dims_input[k] == null || isNaN(dims_input[k]) || dims_input[k] < 0) {
          container.innerHTML = `<div style="padding:24px;color:#a00;font-family:sans-serif">
            Datos insuficientes para dibujar el muro (falta ${k}).</div>`;
          return;
        }
      }
      const geom = buildVoladizo(dims_input);
      const svg  = render(geom, opts || {});
      container.innerHTML = svg;
    },

    renderGravedad: function (dims_input, container, opts) {
      const required = ['H_muro', 'e_zapata', 'b_corona', 'a_frontal',
                        'a_posterior', 'b_puntera', 'b_talon', 'D'];
      for (const k of required) {
        if (dims_input[k] == null || isNaN(dims_input[k]) || dims_input[k] < 0) {
          container.innerHTML = `<div style="padding:24px;color:#a00;font-family:sans-serif">
            Datos insuficientes para dibujar el muro (falta ${k}).</div>`;
          return;
        }
      }
      const geom = buildGravedad(dims_input);
      const svg  = render(geom, opts || {});
      container.innerHTML = svg;
    },

    // Exponen la geometría (polígonos en metros + bbox) para el visor 3D,
    // manteniendo una única fuente de verdad para la forma del muro.
    buildVoladizo: buildVoladizo,
    buildGravedad: buildGravedad,
  };

})();
