"""Memoria de cálculo del dado / cabezal de pilotes (PDF) + dibujo planta y sección.

Unidades de presentación: MKS (tonf, tonf·m, cm²) — el motor trabaja en SI.
"""
from __future__ import annotations

import io
import math
from datetime import date

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle, Polygon

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                TableStyle, Image, HRFlowable)

G = 9.80665  # kN -> tonf, kPa -> tonf/m², kN·m -> tonf·m

VERDE = colors.HexColor("#16a34a")
GRIS = colors.HexColor("#475569")
GRIS_CLARO = colors.HexColor("#e2e8f0")
TINTA = colors.HexColor("#0f172a")

# Fuente Unicode (DejaVuSans, incluida con matplotlib) para ², ₀, φ, ·, ≤.
import os as _os
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.pdfmetrics import registerFontFamily

_FONT, _FONT_B = "Helvetica", "Helvetica-Bold"
try:
    _ttf = _os.path.join(matplotlib.get_data_path(), "fonts", "ttf")
    pdfmetrics.registerFont(TTFont("ARGeo", _os.path.join(_ttf, "DejaVuSans.ttf")))
    pdfmetrics.registerFont(TTFont("ARGeo-B", _os.path.join(_ttf, "DejaVuSans-Bold.ttf")))
    registerFontFamily("ARGeo", normal="ARGeo", bold="ARGeo-B", italic="ARGeo", boldItalic="ARGeo-B")
    _FONT, _FONT_B = "ARGeo", "ARGeo-B"
except Exception:
    pass


def _tf(kN):  return kN / G
def _tm(kPa): return kPa / G


# ---------------------------------------------------------------------------
# Dibujo: planta + sección
# ---------------------------------------------------------------------------
def dibujar_dado(res, entradas) -> "plt.Figure":
    g = res["geometria"]
    Bx, Ly, h, d = g["Bx_m"], g["Ly_m"], g["h_m"], g["d_m"]
    c1, c2 = g["c1_m"], g["c2_m"]
    Dp = g["Dp_m"]
    coords = g["coords"]
    forma = g["forma"]
    verts = g["vertices"]

    C = {"concreto": "#7f8a93", "col": "#9aa6ae", "pilote": "#5a6b8c",
         "acero": "#d97a2b", "suelo": "#d8bd86"}

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(5.4, 7.6),
                                   gridspec_kw={"height_ratios": [1.05, 0.95]})

    # ---------------- PLANTA ----------------
    if forma == "tri" and verts:
        ax1.add_patch(Polygon(verts, closed=True, facecolor=C["concreto"],
                              edgecolor="#2b3137", lw=1.4, alpha=0.35))
    else:
        ax1.add_patch(Rectangle((-Bx / 2, -Ly / 2), Bx, Ly, facecolor=C["concreto"],
                                edgecolor="#2b3137", lw=1.4, alpha=0.35))
    # pilotes
    for i, (x, y) in enumerate(coords):
        ax1.add_patch(Circle((x, y), Dp / 2, facecolor=C["pilote"],
                             edgecolor="#1f2a44", lw=1.1, alpha=0.85))
        ax1.text(x, y, f"P{i+1}", ha="center", va="center", fontsize=7.5,
                 color="white", fontweight="bold")
    # columna
    ax1.add_patch(Rectangle((-c1 / 2, -c2 / 2), c1, c2, facecolor=C["col"],
                            edgecolor="#2b3137", lw=1.2, hatch="////"))
    span = max(Bx, Ly) * 0.62
    ax1.annotate("", xy=(Bx / 2, -Ly / 2 - span * 0.14), xytext=(-Bx / 2, -Ly / 2 - span * 0.14),
                 arrowprops=dict(arrowstyle="<->", color="#334155", lw=1))
    ax1.text(0, -Ly / 2 - span * 0.25, f"Bx = {Bx:.2f} m", ha="center", fontsize=9, fontweight="bold")
    ax1.annotate("", xy=(-Bx / 2 - span * 0.14, Ly / 2), xytext=(-Bx / 2 - span * 0.14, -Ly / 2),
                 arrowprops=dict(arrowstyle="<->", color="#334155", lw=1))
    ax1.text(-Bx / 2 - span * 0.26, 0, f"Ly = {Ly:.2f} m", va="center", ha="center",
             rotation=90, fontsize=9, fontweight="bold")
    lim = max(Bx, Ly) * 0.85
    ax1.set_xlim(-lim, lim); ax1.set_ylim(-lim, lim)
    ax1.set_aspect("equal")
    ax1.set_title(f"PLANTA — {len(coords)} pilote(s)", fontsize=10, fontweight="bold")
    ax1.axis("off")

    # ---------------- SECCIÓN (corte en x) ----------------
    xs = sorted(set(round(x, 3) for (x, y) in coords))
    Lp = 1.30                                   # tramo de pilote dibujado
    emb = 0.12                                  # embebido del pilote en el dado
    colH = 0.55
    # dado
    ax2.add_patch(Rectangle((-Bx / 2, 0), Bx, h, facecolor=C["concreto"],
                            edgecolor="#2b3137", lw=1.4))
    # pilotes bajo el dado
    for x in xs:
        ax2.add_patch(Rectangle((x - Dp / 2, -Lp), Dp, Lp + emb,
                                facecolor=C["pilote"], edgecolor="#1f2a44", lw=1.0, alpha=0.85))
        ax2.annotate("", xy=(x, 0), xytext=(x, -h * 0.55 - 0.18),
                     arrowprops=dict(arrowstyle="->", color="#c79a2b", lw=1.4))
    # columna
    ax2.add_patch(Rectangle((-c1 / 2, h), c1, colH, facecolor=C["col"],
                            edgecolor="#2b3137", lw=1.2, hatch="////"))
    # acero inferior
    ax2.plot([-Bx / 2 + 0.06, Bx / 2 - 0.06], [0.07, 0.07], color=C["acero"], lw=2.0)
    # cota h
    ax2.annotate("", xy=(Bx / 2 + 0.18, h), xytext=(Bx / 2 + 0.18, 0),
                 arrowprops=dict(arrowstyle="<->", color="#334155", lw=1))
    ax2.text(Bx / 2 + 0.32, h / 2, f"h = {h:.2f} m", va="center", ha="center",
             rotation=90, fontsize=8.5, fontweight="bold")
    ax2.text(0, h + colH * 0.5, f"columna\n{c1*100:.0f}×{c2*100:.0f} cm",
             ha="center", va="center", fontsize=8, color="#33404a")
    ax2.text(0, -h * 0.55 - 0.33, "reacciones de pilote", ha="center",
             color="#a87d1c", fontsize=8)
    ax2.text(min(xs), -Lp - 0.12, "pilotes", ha="center", fontsize=8, color="#3a4763")
    ax2.text(Bx / 2 + 0.05, -0.18, f"d = {d:.3f} m", ha="left", fontsize=8, color="#555")
    ax2.set_xlim(-Bx / 1.7, Bx / 1.7)
    ax2.set_ylim(-Lp - 0.35, h + colH + 0.25)
    ax2.set_aspect("equal")
    ax2.set_title("SECCIÓN", fontsize=10, fontweight="bold")
    ax2.axis("off")

    fig.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# Memoria de cálculo (PDF)
# ---------------------------------------------------------------------------
def _tabla(data, anchos, header=True):
    t = Table(data, colWidths=anchos)
    estilo = [
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("FONTNAME", (0, 0), (-1, -1), _FONT),
        ("TEXTCOLOR", (0, 0), (-1, -1), TINTA),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, GRIS_CLARO),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ]
    if header:
        estilo += [
            ("FONTNAME", (0, 0), (-1, 0), _FONT_B),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("BACKGROUND", (0, 0), (-1, 0), VERDE),
            ("LINEBELOW", (0, 0), (-1, 0), 0.6, VERDE),
        ]
    t.setStyle(TableStyle(estilo))
    return t


def _ok(b):
    return ("<font color='#15803d'>CUMPLE</font>" if b
            else "<font color='#b91c1c'>NO CUMPLE</font>")


def generar_memoria_dado(datos, resultado, entradas) -> bytes:
    g = resultado["geometria"]
    c = resultado["cargas"]
    est = resultado["estructural"]
    pc = est["punz_columna"]; pp = est["punz_pilote"]
    cvx = est["cortante_x"]; cvy = est["cortante_y"]
    fx = est["flexion_x"]; fy_ = est["flexion_y"]
    biela = est["biela"]

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=2 * cm, rightMargin=2 * cm,
                            topMargin=1.8 * cm, bottomMargin=1.8 * cm,
                            title="Memoria de cálculo — Dado / cabezal de pilotes")
    ss = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=ss["Heading1"], fontName=_FONT_B, fontSize=15, textColor=TINTA, spaceAfter=2)
    h2 = ParagraphStyle("h2", parent=ss["Heading2"], fontName=_FONT_B, fontSize=11.5, textColor=VERDE,
                        spaceBefore=12, spaceAfter=5)
    p = ParagraphStyle("p", parent=ss["BodyText"], fontName=_FONT, fontSize=9, textColor=TINTA, leading=13)
    small = ParagraphStyle("small", parent=p, fontName=_FONT, fontSize=8, textColor=GRIS)
    el = []

    fc = float(entradas.get("fc", 21) or 21)
    fy = float(entradas.get("fy", 420) or 420)
    db_mm = float(entradas.get("db", 0.01905) or 0.01905) * 1000.0
    rec = float(entradas.get("recubrimiento", 0.075) or 0.075)

    # Encabezado
    _ccp = str(resultado.get("norma", "NSR10")) == "CCP14"
    _norm_txt = "CCP-14 / AASHTO LRFD (Sección 5)" if _ccp else "NSR-10 / ACI 318"
    el.append(Paragraph("Memoria de cálculo — Dado / cabezal de pilotes", h1))
    el.append(Paragraph(f"Encepado sobre grupo de pilotes · {_norm_txt} · método seccional y de bielas", small))
    el.append(HRFlowable(width="100%", thickness=1, color=VERDE, spaceBefore=6, spaceAfter=6))

    proy = getattr(datos, "proyecto", "") or "—"
    ing = getattr(datos, "ingeniero", "") or "—"
    ubic = getattr(datos, "ubicacion", "") or "—"
    el.append(_tabla([
        ["Proyecto", proy, "Fecha", date.today().isoformat()],
        ["Ingeniero", ing, "Ubicación", ubic],
    ], [2.6 * cm, 6.5 * cm, 2.2 * cm, 5.0 * cm], header=False))

    # 1. Datos de entrada
    el.append(Paragraph("1. Datos de entrada", h2))
    cap_txt = f"{_tf(c['capacidad_pilote_kN']):.1f} tonf" if c["capacidad_pilote_kN"] else "—"
    el.append(_tabla([
        ["Parámetro", "Valor", "Parámetro", "Valor"],
        ["N° de pilotes", f"{g['n_pilotes']}", "Ø pilote", f"{g['Dp_m']*100:.0f} cm"],
        ["Separación s", f"{g['s_m']:.2f} m", "Borde e", f"{g['e_m']:.2f} m"],
        ["Columna", f"{g['c1_m']*100:.0f} × {g['c2_m']*100:.0f} cm", "Capacidad pilote", cap_txt],
        ["Pu (columna)", f"{_tf(c['Pu_kN']):.1f} tonf", "Mux / Muy",
         f"{_tm(c['Mux_kNm']):.1f} / {_tm(c['Muy_kNm']):.1f} tonf·m"],
        ["f'c", f"{fc:.0f} MPa", "fy", f"{fy:.0f} MPa"],
        ["Ø barra inferior", f"{db_mm:.1f} mm", "Recubrimiento", f"{rec*100:.1f} cm"],
    ], [3.4 * cm, 4.0 * cm, 3.4 * cm, 4.0 * cm]))

    # Esquema
    fig = dibujar_dado(resultado, entradas)
    img_buf = io.BytesIO()
    fig.savefig(img_buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    img_buf.seek(0)
    el.append(Spacer(1, 6))
    el.append(Image(img_buf, width=9.8 * cm, height=13.8 * cm))

    # 2. Geometría y clasificación
    el.append(Paragraph("2. Geometría del dado", h2))
    forma_txt = "triangular" if g["forma"] == "tri" else "rectangular"
    el.append(_tabla([
        ["Forma en planta", forma_txt, "Dimensión Bx×Ly",
         f"{g['Bx_m']:.2f} × {g['Ly_m']:.2f} m"],
        ["Espesor h", f"{g['h_m']:.2f} m", "Peralte efectivo d", f"{g['d_m']:.3f} m"],
        ["Volado m", f"{g['m_voladizo_m']:.2f} m", "Clasificación", g["clasificacion"]],
        ["Volumen concreto", f"{g['volumen_concreto_m3']:.2f} m³", "Área en planta",
         f"{g['area_m2']:.2f} m²"],
    ], [3.4 * cm, 3.8 * cm, 3.6 * cm, 3.6 * cm], header=False))
    el.append(Spacer(1, 3))
    el.append(Paragraph(
        f"Clasificación según m ≤ 1.5·H: el encepado es <b>{g['clasificacion']}</b> "
        f"(m = {g['m_voladizo_m']:.2f} m, H = {g['h_m']:.2f} m).", small))

    # 3. Reacciones en pilotes
    el.append(Paragraph("3. Reacciones en los pilotes", h2))
    el.append(Paragraph(
        "Cada pilote recibe R = P/n ± M·c/Σc² (incluye el peso propio del dado). "
        "Se verifica que la reacción máxima no supere la capacidad del pilote.", p))
    filas = [["Pilote"] + [f"P{i+1}" for i in range(len(c["reacciones_kN"]))]]
    filas.append(["R (tonf)"] + [f"{_tf(r):.1f}" for r in c["reacciones_kN"]])
    anchos_r = [2.2 * cm] + [(13.0 / max(1, len(c["reacciones_kN"]))) * cm] * len(c["reacciones_kN"])
    el.append(_tabla(filas, anchos_r))
    el.append(Spacer(1, 3))
    rp = f"{c['ratio_pilote']}" if c["ratio_pilote"] is not None else "—"
    el.append(Paragraph(
        f"R<sub>máx</sub> = {_tf(c['Pmax_kN']):.1f} tonf · Capacidad = {cap_txt} · "
        f"D/C = {rp} → <b>{_ok(c['cumple_pilote'])}</b>.", p))

    # 4. Diseño estructural
    est = resultado["estructural"]
    el.append(Paragraph("4. Diseño estructural", h2))
    if _ccp:
        el.append(Paragraph(
            f"Peralte efectivo d = {g['d_m']:.3f} m (h = {g['h_m']:.2f} m); peralte de "
            f"cortante d<sub>v</sub> = máx(0.9d, 0.72h) = {est.get('dv_m', g['d_m']):.3f} m. "
            f"φ<sub>cortante</sub> = {est.get('phi_corte', 0.9)}, φ<sub>flexión</sub> = 0.90 "
            f"(CCP-14 / AASHTO Sección 5).", p))
    else:
        el.append(Paragraph(
            f"Peralte efectivo d = {g['d_m']:.3f} m (h = {g['h_m']:.2f} m). "
            f"φ<sub>cortante</sub> = 0.75, φ<sub>flexión</sub> = 0.90.", p))

    el.append(Paragraph("4.1 Punzonamiento (dos vías)", p))
    el.append(_tabla([
        ["Sección", "b₀ (m)", "v_c (MPa)", "Vu (tonf)", "φVc (tonf)", "D/C", "Estado"],
        ["Columna", f"{pc['b0_m']:.2f}", f"{pc['vc_MPa']:.2f}", f"{_tf(pc['Vu_kN']):.1f}",
         f"{_tf(pc['phiVc_kN']):.1f}", f"{pc['ratio']}", "cumple" if pc["cumple"] else "no cumple"],
        ["Pilote", f"{pp['b0_m']:.2f}", f"{pp['vc_MPa']:.2f}", f"{_tf(pp['Vu_kN']):.1f}",
         f"{_tf(pp['phiVc_kN']):.1f}", f"{pp['ratio']}", "cumple" if pp["cumple"] else "no cumple"],
    ], [2.2 * cm, 2.0 * cm, 2.2 * cm, 2.4 * cm, 2.4 * cm, 1.7 * cm, 2.3 * cm]))

    # Transferencia de momento por cortante excéntrico (γv) en la columna.
    if pc.get("vu_momento_kPa", 0.0) > 0.1:
        el.append(Spacer(1, 3))
        el.append(Paragraph(
            f"Transferencia de momento por cortante excéntrico (NSR-10 C.11.11.7): una "
            f"fracción γ<sub>v</sub> = {pc['gamma_v_x']:.3f} del momento se resiste como "
            f"cortante en el perímetro crítico. Esfuerzo combinado v<sub>u</sub> = "
            f"v<sub>directo</sub> + v<sub>momento</sub> = {pc['vu_directo_kPa']/1000.0:.2f} + "
            f"{pc['vu_momento_kPa']/1000.0:.2f} = {pc['vu_total_kPa']/1000.0:.2f} MPa ≤ "
            f"φv<sub>c</sub> = {pc['phi_vc_kPa']/1000.0:.2f} MPa · D/C = {pc['ratio_momento']} → "
            f"<b>{_ok(pc['cumple_momento'])}</b>.", p))

    el.append(Spacer(1, 4))
    el.append(Paragraph("4.2 Cortante en una vía (a d de la cara)", p))
    el.append(_tabla([
        ["Dirección", "Vu (tonf)", "φVc (tonf)", "D/C", "Estado"],
        ["Dir. X", f"{_tf(cvx['Vu_kN']):.1f}", f"{_tf(cvx['phiVc_kN']):.1f}", f"{cvx['ratio']}",
         "cumple" if cvx["cumple"] else "no cumple"],
        ["Dir. Y", f"{_tf(cvy['Vu_kN']):.1f}", f"{_tf(cvy['phiVc_kN']):.1f}", f"{cvy['ratio']}",
         "cumple" if cvy["cumple"] else "no cumple"],
    ], [3.6 * cm, 3.0 * cm, 3.0 * cm, 2.2 * cm, 3.0 * cm]))

    metodo = est.get("metodo", "ambos")
    el.append(Spacer(1, 4))
    if metodo in ("flexion", "ambos"):
        el.append(Paragraph("4.3 Flexión y refuerzo (método seccional, cara de columna)", p))
        def _fila_flex(f, dirn):
            gob = " (mín.)" if f["gobierna_minimo"] else ""
            return [dirn, f"{_tm(f['Mu_kNm']):.2f}", f"{f['As_req_cm2']:.1f}",
                    f"{f['As_cm2']:.1f}{gob}", f"{f['n_barras']} Ø{f['db_mm']:.1f} @ {f['sep_cm']:.0f} cm"]
        el.append(_tabla([
            ["Dirección", "Mu (tonf·m)", "As req (cm²)", "As (cm²)", "Refuerzo"],
            _fila_flex(fx, "Dir. X"),
            _fila_flex(fy_, "Dir. Y"),
        ], [3.4 * cm, 3.0 * cm, 3.0 * cm, 2.4 * cm, 4.0 * cm]))

    if metodo in ("bielas", "ambos"):
        el.append(Spacer(1, 4))
        el.append(Paragraph("4.4 Método de bielas (puntal-tensor)", p))
        if biela["tipo"] == "triangular":
            a = biela["arista"]
            el.append(Paragraph(
                f"Encepado triangular: tensor por arista T = {_tf(a['T_kN']):.1f} tonf → "
                f"As = {a['As_cm2']:.1f} cm² ({a['n_barras']} barras por arista).", p))
        else:
            bx, by = biela["x"], biela["y"]
            el.append(_tabla([
                ["Dirección", "T tensor (tonf)", "As (cm²)", "Barras"],
                ["Dir. X", f"{_tf(bx['T_kN']):.1f}", f"{bx['As_cm2']:.1f}", f"{bx['n_barras']}"],
                ["Dir. Y", f"{_tf(by['T_kN']):.1f}", f"{by['As_cm2']:.1f}", f"{by['n_barras']}"],
            ], [3.6 * cm, 3.6 * cm, 3.0 * cm, 3.0 * cm]))

    metodo_txt = {"flexion": "método seccional (flexión)",
                  "bielas": "método de bielas (puntal-tensor)",
                  "ambos": "el mayor entre flexión y bielas"}[metodo]
    el.append(Spacer(1, 3))
    el.append(Paragraph(
        f"<b>Acero inferior adoptado ({metodo_txt}):</b> dir. X = {est['as_x_rec_cm2']:.1f} cm² · "
        f"dir. Y = {est['as_y_rec_cm2']:.1f} cm².", p))

    # 4.5 Transferencia de carga columna→dado (aplastamiento + dowels)
    tr = est.get("transferencia")
    if tr:
        el.append(Paragraph("4.5 Transferencia de carga columna→dado (NSR-10 C.15.8)", p))
        el.append(_tabla([
            ["Concepto", "Valor", "Concepto", "Valor"],
            ["Pu", f"{_tf(tr['Pu_kN']):.1f} tonf", "√(A₂/A₁)", f"{tr['sqrt_A2A1']:.2f}"],
            ["φPn dado", f"{_tf(tr['phiPn_zapata_kN']):.1f} tonf",
             "φPn columna", f"{_tf(tr['phiPn_columna_kN']):.1f} tonf"],
            ["φPn aplast.", f"{_tf(tr['phiPn_kN']):.1f} tonf",
             "D/C aplast.", f"{tr['ratio']}"],
            ["Dowels", f"{tr['n_dowels']} Ø{tr['db_dowel_mm']:.0f} mm",
             "As dowels req.", f"{tr['As_dowels_req_cm2']:.1f} cm²"],
            ["ℓdc dowel", f"{tr['ldc_dowel_m']*100:.0f} cm",
             "ℓdc disponible", f"{tr['ldc_disponible_m']*100:.0f} cm"],
        ], [3.2 * cm, 4.1 * cm, 3.2 * cm, 4.1 * cm], header=False))
        el.append(Spacer(1, 2))
        if not tr["cumple_aplastamiento"]:
            el.append(Paragraph(
                "El aplastamiento en la interfaz se excede; el exceso de carga lo toman "
                "los dowels (no es una falla si éstos se desarrollan dentro del espesor).", small))
        el.append(Paragraph(
            f"Desarrollo de los dowels: ℓ<sub>dc</sub> = {tr['ldc_dowel_m']*100:.0f} cm ≤ "
            f"disponible {tr['ldc_disponible_m']*100:.0f} cm → <b>{_ok(tr['cumple_dowels'])}</b>.", p))

    # 4.6 Anclaje del acero de tracción (tensor) y de las barras de la columna
    an = est.get("anclaje_tensor")
    el.append(Spacer(1, 4))
    el.append(Paragraph("4.6 Anclaje del refuerzo", p))
    el.append(Paragraph(
        f"Barras de la columna (compresión en el dado): ℓ<sub>dc</sub> = "
        f"{est['ldc_columna_m']*100:.0f} cm.", p))
    if an:
        _tensor_ok = an["cumple_x"] and an["cumple_y"]
        el.append(Paragraph(
            f"Acero inferior (tensor) más allá del eje del pilote: ℓ<sub>d</sub> = "
            f"{an['ld_m']*100:.0f} cm; longitud disponible = {an['disp_x_m']*100:.0f} cm (X) / "
            f"{an['disp_y_m']*100:.0f} cm (Y) → <b>{_ok(_tensor_ok)}</b>.", p))
        if an["requiere_gancho"]:
            el.append(Paragraph(
                "La longitud recta disponible es insuficiente: colocar gancho estándar a 90° "
                "en el extremo de las barras (crítico en el método de bielas, donde el tensor "
                "debe desarrollar su fuerza total sobre el pilote).", small))

    el.append(Spacer(1, 5))
    el.append(Paragraph(
        f"<b>Verificación global: {_ok(resultado['cumple'])}</b> "
        f"(capacidad de pilotes, punzonamiento, cortante y transferencia de carga).", p))

    for a in resultado.get("avisos", []):
        el.append(Paragraph(f"⚠ {a}", small))

    el.append(Spacer(1, 12))
    el.append(HRFlowable(width="100%", thickness=0.5, color=GRIS_CLARO))
    el.append(Paragraph(f"Generado por CimX · Dado / cabezal de pilotes · {_norm_txt}", small))

    doc.build(el)
    return buf.getvalue()
