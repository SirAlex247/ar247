"""Memoria de cálculo (PDF) de la placa/losa de cimentación maciza.

Reutiliza el estilo y los ayudantes del reporte de zapatas
(``zapata_reporte``) para mantener una identidad visual única. Incluye:
  - datos de entrada y malla de columnas,
  - esquema en planta (columnas + presiones en las esquinas) y diagramas de
    momento de las franjas de diseño (X e Y),
  - dimensionamiento geotécnico por el método rígido (presiones biaxiales),
  - diseño estructural: punzonamiento por columna y flexión por franjas.
"""
from __future__ import annotations

import io
from datetime import date

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                Image, HRFlowable)

from .zapata_reporte import (G, VERDE, GRIS, GRIS_CLARO, TINTA, _FONT, _FONT_B,
                             _tf, _tm, _tabla, _ok, _fig_to_image)


# ---------------------------------------------------------------------------
# Dibujo: planta con columnas y presiones + diagramas de momento de franjas
# ---------------------------------------------------------------------------
def dibujar_placa(res) -> "plt.Figure":
    g, geo, est = res["geometria"], res["geotecnico"], res["estructural"]
    B, L = g["B_m"], g["L_m"]
    cols = g["columnas"]
    esq = geo["esquinas_kPa"]

    C = {"concreto": "#7f8a93", "hatch": "#333b45", "col": "#9aa6ae",
         "mpos": "#2f6f4f", "mneg": "#b45309"}
    plt.rcParams["hatch.linewidth"] = 0.5

    fig = plt.figure(figsize=(6.4, 8.2))
    gs = fig.add_gridspec(3, 2, height_ratios=[1.55, 1.0, 1.0], hspace=0.42, wspace=0.28)
    axp = fig.add_subplot(gs[0, :])
    axx = fig.add_subplot(gs[1, :])
    axy = fig.add_subplot(gs[2, :])

    # ---------------- PLANTA ----------------
    axp.add_patch(Rectangle((0, 0), B, L, facecolor=C["concreto"],
                            edgecolor=C["hatch"], lw=1.4, alpha=0.5, hatch="xxx"))
    for k, c in enumerate(cols):
        x, y, c1, c2 = c["x_m"], c["y_m"], c["c1_m"], c["c2_m"]
        axp.add_patch(Rectangle((x - c1 / 2, y - c2 / 2), c1, c2,
                                facecolor=C["col"], edgecolor="#2b3137", lw=1.0))
        axp.plot(x, y, "+", color="#2b3137", ms=6, mew=0.9)
    # centroide de cargas
    axp.plot(geo["x_centroide_carga_m"], geo["y_centroide_carga_m"], "o",
             color=C["mneg"], ms=6, label="centroide de cargas")
    # presiones en las esquinas
    off = max(B, L) * 0.045
    for (px, py, key, ha, va) in [
        (0, 0, "q_00", "left", "top"), (B, 0, "q_B0", "right", "top"),
        (0, L, "q_0L", "left", "bottom"), (B, L, "q_BL", "right", "bottom")]:
        axp.annotate(f"{_tm(esq[key]):.1f}", xy=(px, py),
                     xytext=(px + (off if ha == "left" else -off),
                             py + (off if va == "bottom" else -off)),
                     fontsize=7.5, color="#7a4a10", ha=ha, va=va, fontweight="bold")
    m = max(B, L) * 0.14
    axp.annotate("", xy=(B, -m * 0.5), xytext=(0, -m * 0.5),
                 arrowprops=dict(arrowstyle="<->", color="#334155", lw=1))
    axp.text(B / 2, -m * 0.95, f"B = {B:.2f} m", ha="center", fontsize=8.5, fontweight="bold")
    axp.annotate("", xy=(-m * 0.5, L), xytext=(-m * 0.5, 0),
                 arrowprops=dict(arrowstyle="<->", color="#334155", lw=1))
    axp.text(-m * 0.95, L / 2, f"L = {L:.2f} m", va="center", ha="center",
             rotation=90, fontsize=8.5, fontweight="bold")
    axp.set_xlim(-m * 1.3, B + m * 0.6)
    axp.set_ylim(-m * 1.3, L + m * 0.6)
    axp.set_aspect("equal")
    axp.set_title(f"PLANTA · {g['n_columnas']} columnas  (presiones de esquina en tonf/m²)",
                  fontsize=9.5, fontweight="bold")
    axp.axis("off")

    # ---------------- FRANJAS (diagramas de momento) ----------------
    def _bmd(ax, franja, titulo):
        w = franja["w_kN_m"]
        longitud = franja["longitud_m"]
        # Cargas de columna proyectadas sobre el eje de la franja (reconstruidas
        # desde la malla de columnas): (posición sobre el eje, Pu).
        eje = franja.get("eje", "x") + "_m"
        pts = sorted((c[eje], c["Pu_kN"]) for c in cols)

        def M(s):
            mm = w * s * s / 2.0
            for si, Pui in pts:
                if s > si:
                    mm -= Pui * (s - si)
            return mm

        xs = [longitud * i / 200 for i in range(201)]
        ms = [M(s) / G for s in xs]
        ax.axhline(0, color="#334155", lw=0.9)
        ax.plot(xs, ms, color="#1f2937", lw=1.3)
        ax.fill_between(xs, ms, 0, where=[v >= 0 for v in ms], color=C["mpos"], alpha=0.28)
        ax.fill_between(xs, ms, 0, where=[v < 0 for v in ms], color=C["mneg"], alpha=0.28)
        for si, _ in pts:
            ax.axvline(si, color=C["col"], ls="--", lw=0.7)
        ax.set_title(titulo, fontsize=9, fontweight="bold")
        ax.set_xlabel("s  [m]", fontsize=7.5)
        ax.grid(True, ls=":", lw=0.4, alpha=0.5)
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
        ax.tick_params(labelsize=7)

    _bmd(axx, est["franja_x"], "FRANJA X · momento [tonf·m]  (acero en x)")
    _bmd(axy, est["franja_y"], "FRANJA Y · momento [tonf·m]  (acero en y)")

    return fig


# ---------------------------------------------------------------------------
# Memoria (PDF)
# ---------------------------------------------------------------------------
def generar_memoria_placa(datos, resultado, entradas) -> bytes:
    g = resultado["geometria"]
    geo = resultado["geotecnico"]
    est = resultado["estructural"]

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=2 * cm, rightMargin=2 * cm,
                            topMargin=1.8 * cm, bottomMargin=1.8 * cm,
                            title="Memoria de cálculo — Placa maciza")
    ss = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=ss["Heading1"], fontName=_FONT_B, fontSize=15, textColor=TINTA, spaceAfter=2)
    h2 = ParagraphStyle("h2", parent=ss["Heading2"], fontName=_FONT_B, fontSize=11.5, textColor=VERDE, spaceBefore=12, spaceAfter=5)
    p = ParagraphStyle("p", parent=ss["BodyText"], fontName=_FONT, fontSize=9, textColor=TINTA, leading=13)
    small = ParagraphStyle("small", parent=p, fontName=_FONT, fontSize=8, textColor=GRIS)
    el = []

    fc = float(entradas.get("fc", 21) or 21)
    fy = float(entradas.get("fy", 420) or 420)
    Df = float(entradas.get("Df", 1.5) or 1.5)

    el.append(Paragraph("Memoria de cálculo — Placa / losa de cimentación maciza", h1))
    el.append(Paragraph("Método rígido convencional · dimensionamiento geotécnico y "
                        "diseño estructural · NSR-10 / ACI 318", small))
    el.append(HRFlowable(width="100%", thickness=1, color=VERDE, spaceBefore=6, spaceAfter=6))
    el.append(_tabla([
        ["Proyecto", getattr(datos, "proyecto", "") or "—", "Fecha", date.today().isoformat()],
        ["Ingeniero", getattr(datos, "ingeniero", "") or "—",
         "Ubicación", getattr(datos, "ubicacion", "") or "—"],
    ], [2.6 * cm, 6.5 * cm, 2.2 * cm, 5.0 * cm], header=False))

    # 1. Geometría
    el.append(Paragraph("1. Geometría y cargas", h2))
    el.append(_tabla([
        ["Losa B×L", f"{g['B_m']:.2f} × {g['L_m']:.2f} m", "Área", f"{g['area_m2']:.2f} m²"],
        ["Espesor h", f"{g['h_m']:.2f} m", "Peralte d", f"{g['d_m']:.3f} m"],
        ["N.º columnas", f"{g['n_columnas']}", "Voladizo", f"{g['voladizo_m']:.2f} m"],
        ["Volumen concreto", f"{g['volumen_concreto_m3']:.2f} m³", "Profundidad Df", f"{Df:.2f} m"],
    ], [3.4 * cm, 3.8 * cm, 3.4 * cm, 3.8 * cm], header=False))

    # tabla de columnas
    filas = [["#", "x (m)", "y (m)", "P serv. (tonf)", "Columna (cm)"]]
    for i, c in enumerate(g["columnas"], 1):
        filas.append([str(i), f"{c['x_m']:.2f}", f"{c['y_m']:.2f}",
                      f"{_tf(c['P_kN']):.1f}", f"{c['c1_m']*100:.0f}×{c['c2_m']*100:.0f}"])
    el.append(Spacer(1, 4))
    el.append(_tabla(filas, [1.4 * cm, 2.8 * cm, 2.8 * cm, 3.6 * cm, 3.6 * cm]))

    # Figura
    el.append(Spacer(1, 6))
    el.append(_fig_to_image(dibujar_placa(resultado), 14.5, 18.6))

    # 2. Geotecnia
    el.append(Paragraph("2. Dimensionamiento geotécnico (método rígido)", h2))
    el.append(Paragraph(
        "La presión de contacto se obtiene por flexión biaxial de la losa: "
        "q = R/A ± (R·e<sub>x</sub>)·x'/I<sub>y</sub> ± (R·e<sub>y</sub>)·y'/I<sub>x</sub>. "
        "Se verifica q<sub>máx</sub> ≤ q<sub>adm</sub> y ausencia de despegue "
        "(q<sub>mín</sub> ≥ 0).", p))
    el.append(_tabla([
        ["Resultante R (servicio)", f"{_tf(geo['R_servicio_kN']):.1f} tonf",
         "Centroide carga", f"({geo['x_centroide_carga_m']:.2f}, {geo['y_centroide_carga_m']:.2f}) m"],
        ["Excentricidad e", f"({geo['e_x_m']:.3f}, {geo['e_y_m']:.3f}) m",
         "q promedio", f"{_tm(geo['q_prom_kPa']):.1f} tonf/m²"],
        ["q máx", f"{_tm(geo['q_max_kPa']):.1f} tonf/m²", "q mín", f"{_tm(geo['q_min_kPa']):.1f} tonf/m²"],
        ["q admisible", f"{_tm(geo['q_adm_kPa']):.1f} tonf/m²", "Relación D/C", f"{geo['ratio']}"],
    ], [3.8 * cm, 3.6 * cm, 3.4 * cm, 3.6 * cm], header=False))
    el.append(Spacer(1, 3))
    el.append(Paragraph(f"<b>Verificación geotécnica: {_ok(geo['cumple'])}</b>", p))

    # 3. Estructural
    el.append(Paragraph("3. Diseño estructural", h2))
    el.append(Paragraph(
        f"Presión última promedio q<sub>u</sub> = R<sub>u</sub>/A = "
        f"{_tm(est['qu_prom_kPa']):.1f} tonf/m². Peralte d = {g['d_m']:.3f} m. "
        f"φ<sub>cortante</sub> = 0.75, φ<sub>flexión</sub> = 0.90.", p))

    # 3.1 Punzonamiento (columna crítica + resumen)
    el.append(Paragraph("3.1 Cortante por punzonamiento (dos vías) — columna crítica", p))
    pc = est["punz_critico"]
    el.append(_tabla([
        ["Columna", "b₀ (m)", "v_c (MPa)", "Vu (tonf)", "φVc (tonf)", "D/C", "Estado"],
        [f"#{pc['columna']} ({pc['posicion']})", f"{pc['b0_m']:.2f}", f"{pc['vc_MPa']:.2f}",
         f"{_tf(pc['Vu_kN']):.1f}", f"{_tf(pc['phiVc_kN']):.1f}", f"{pc['ratio']}",
         "cumple" if pc["cumple"] else "no cumple"],
    ], [3.0 * cm, 2.0 * cm, 2.2 * cm, 2.3 * cm, 2.4 * cm, 1.7 * cm, 2.2 * cm]))
    n_ok = sum(1 for x in est["punzonamiento"] if x["cumple"])
    el.append(Paragraph(f"Punzonamiento verificado en las {len(est['punzonamiento'])} "
                        f"columnas: {n_ok} cumplen.", small))

    # 3.2 Flexión por franjas
    el.append(Spacer(1, 4))
    el.append(Paragraph("3.2 Flexión por el método de las franjas", p))

    def _fila_franja(fr, nom):
        inf, sup = fr["acero_inferior"], fr["acero_superior"]
        return [
            [f"{nom} · inferior (M⁺)", f"{_tm(fr['M_pos_kNm']):.1f}",
             f"{inf['As_cm2']:.1f}{' (mín.)' if inf['gobierna_minimo'] else ''}",
             f"{inf['n_barras']} Ø{inf['db_mm']:.1f} @ {inf['sep_cm']:.0f} cm"],
            [f"{nom} · superior (M⁻)", f"{_tm(fr['M_neg_kNm']):.1f}",
             f"{sup['As_cm2']:.1f}{' (mín.)' if sup['gobierna_minimo'] else ''}",
             f"{sup['n_barras']} Ø{sup['db_mm']:.1f} @ {sup['sep_cm']:.0f} cm"],
        ]
    filas_f = [["Franja / cara", "M (tonf·m)", "As (cm²)", "Distribución (total)"]]
    filas_f += _fila_franja(est["franja_x"], "Franja X")
    filas_f += _fila_franja(est["franja_y"], "Franja Y")
    el.append(_tabla(filas_f, [4.8 * cm, 2.6 * cm, 2.6 * cm, 4.6 * cm]))
    el.append(Spacer(1, 3))
    fx, fyy = est["franja_x"], est["franja_y"]
    el.append(Paragraph(
        f"Cortante como viga ancha — Franja X: Vu = {_tf(fx['V_max_kN']):.1f} tonf, "
        f"φVc = {_tf(fx['phiVc_kN']):.1f} tonf ({_ok(fx['cumple_cortante'])}). "
        f"Franja Y: Vu = {_tf(fyy['V_max_kN']):.1f} tonf, "
        f"φVc = {_tf(fyy['phiVc_kN']):.1f} tonf ({_ok(fyy['cumple_cortante'])}).", p))

    el.append(Spacer(1, 5))
    el.append(Paragraph(f"<b>Verificación al cortante: {_ok(est['cumple_cortante'])}</b>", p))
    for a in resultado.get("avisos", []):
        el.append(Paragraph(f"⚠ {a}", small))
    el.append(Spacer(1, 12))
    el.append(HRFlowable(width="100%", thickness=0.5, color=GRIS_CLARO))
    el.append(Paragraph("Generado por CimX · Placa maciza · método rígido · NSR-10 / ACI 318", small))
    doc.build(el)
    return buf.getvalue()
