"""Memoria de cálculo de la zapata aislada (PDF) y dibujo planta + sección.

Reporte profesional con:
  - datos de entrada (columna, cargas, suelo, materiales),
  - esquema en planta y sección (matplotlib),
  - dimensionamiento geotécnico (presiones de contacto),
  - diseño estructural: punzonamiento, cortante en una vía y flexión.

Unidades de presentación: MKS (tonf, tonf/m², cm²) — el motor trabaja en SI.
"""
from __future__ import annotations

import io
from datetime import date

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

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

# Fuente Unicode (DejaVuSans, incluida con matplotlib) para que ², ₀, φ, · rendericen.
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
# Dibujo: planta + sección (matplotlib)
# ---------------------------------------------------------------------------
def dibujar_zapata(res, entradas) -> "plt.Figure":
    g, e = res["geometria"], res["estructural"]
    B, L, h, d = g["B_m"], g["L_m"], g["h_m"], g["d_m"]
    c1, c2 = g["c1_m"], g["c2_m"]
    Df = float(entradas.get("Df", 1.5) or 1.5)
    if Df <= h:
        Df = h + 0.4
    qu_t = e["qu_kPa"] / G

    C = {"concreto": "#7f8a93", "col": "#9aa6ae", "suelo": "#d8bd86",
         "acero": "#d97a2b"}

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(5.4, 7.4),
                                   gridspec_kw={"height_ratios": [1.0, 1.0]})

    # ---------------- PLANTA ----------------
    ax1.add_patch(Rectangle((-B / 2, -L / 2), B, L, facecolor=C["concreto"],
                            edgecolor="#2b3137", lw=1.4, alpha=0.35))
    n = 7
    for i in range(1, n):
        yy = -L / 2 + L * i / n
        ax1.plot([-B / 2 + 0.05, B / 2 - 0.05], [yy, yy], color=C["acero"], lw=0.6, alpha=0.75)
        xx = -B / 2 + B * i / n
        ax1.plot([xx, xx], [-L / 2 + 0.05, L / 2 - 0.05], color=C["acero"], lw=0.5, alpha=0.5)
    ax1.add_patch(Rectangle((-c1 / 2, -c2 / 2), c1, c2, facecolor=C["col"],
                            edgecolor="#2b3137", lw=1.2))
    m = max(B, L) * 0.66
    ax1.annotate("", xy=(B / 2, -L / 2 - m * 0.13), xytext=(-B / 2, -L / 2 - m * 0.13),
                 arrowprops=dict(arrowstyle="<->", color="#334155", lw=1))
    ax1.text(0, -L / 2 - m * 0.23, f"B = {B:.2f} m", ha="center", fontsize=9, fontweight="bold")
    ax1.annotate("", xy=(-B / 2 - m * 0.13, L / 2), xytext=(-B / 2 - m * 0.13, -L / 2),
                 arrowprops=dict(arrowstyle="<->", color="#334155", lw=1))
    ax1.text(-B / 2 - m * 0.24, 0, f"L = {L:.2f} m", va="center", ha="center",
             rotation=90, fontsize=9, fontweight="bold")
    ax1.set_xlim(-m, m)
    ax1.set_ylim(-m, m)
    ax1.set_aspect("equal")
    ax1.set_title("PLANTA", fontsize=10, fontweight="bold")
    ax1.axis("off")

    # ---------------- SECCIÓN ----------------
    colTop = Df + 0.5
    ax2.add_patch(Rectangle((-B * 0.98, 0), 2 * B * 0.98, Df, facecolor=C["suelo"],
                            edgecolor="none", alpha=0.30))
    ax2.plot([-B * 0.98, B * 0.98], [Df, Df], color="#6b5b3e", lw=1.0)
    ax2.text(-B * 0.92, Df + 0.04, "N.T.", fontsize=8, color="#6b5b3e", va="bottom")
    ax2.add_patch(Rectangle((-B / 2, 0), B, h, facecolor=C["concreto"],
                            edgecolor="#2b3137", lw=1.4))
    ax2.add_patch(Rectangle((-c1 / 2, h), c1, colTop - h, facecolor=C["col"],
                            edgecolor="#2b3137", lw=1.2))
    ax2.plot([-B / 2 + 0.06, B / 2 - 0.06], [0.06, 0.06], color=C["acero"], lw=1.8)
    nq = 6
    for i in range(nq + 1):
        xx = -B / 2 + B * i / nq
        ax2.annotate("", xy=(xx, 0), xytext=(xx, -h * 0.6 - 0.20),
                     arrowprops=dict(arrowstyle="->", color="#c79a2b", lw=1.1))
    ax2.text(0, -h * 0.6 - 0.36, f"qu = {qu_t:.1f} tonf/m²", ha="center",
             color="#a87d1c", fontsize=8.5)
    ax2.annotate("", xy=(B / 2 + 0.20, h), xytext=(B / 2 + 0.20, 0),
                 arrowprops=dict(arrowstyle="<->", color="#334155", lw=1))
    ax2.text(B / 2 + 0.34, h / 2, f"h = {h:.2f} m", va="center", ha="center",
             rotation=90, fontsize=8.5, fontweight="bold")
    ax2.text(0, h + (colTop - h) * 0.5, f"columna\n{c1*100:.0f}×{c2*100:.0f} cm",
             ha="center", va="center", fontsize=8, color="#33404a")
    ax2.text(0, -h * 0.6 - 0.54, f"d = {d:.3f} m", ha="center", fontsize=8, color="#555")
    ax2.set_xlim(-B * 1.05, B * 1.05)
    ax2.set_ylim(-h * 0.6 - 0.75, colTop + 0.25)
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


def generar_memoria_zapata(datos, resultado, entradas) -> bytes:
    g = resultado["geometria"]
    geo = resultado["geotecnico"]
    est = resultado["estructural"]
    pz = est["punzonamiento"]
    fL = est["flexion_L"]
    fB = est["flexion_B"]

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=2 * cm, rightMargin=2 * cm,
                            topMargin=1.8 * cm, bottomMargin=1.8 * cm,
                            title="Memoria de cálculo — Zapata aislada")
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
    Df = float(entradas.get("Df", 1.5) or 1.5)
    gs = float(entradas.get("gamma_suelo", 18) or 18)
    gc = float(entradas.get("gamma_concreto", 24) or 24)
    pos = str(entradas.get("posicion", "interior") or "interior")
    fcarga = float(entradas.get("factor_carga", 1.5) or 1.5)

    # Encabezado
    el.append(Paragraph("Memoria de cálculo — Diseño de zapata aislada", h1))
    el.append(Paragraph("Dimensionamiento geotécnico y diseño estructural · NSR-10 / ACI 318", small))
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
    el.append(_tabla([
        ["Parámetro", "Valor", "Parámetro", "Valor"],
        ["Columna", f"{g['c1_m']*100:.0f} × {g['c2_m']*100:.0f} cm", "Posición", pos],
        ["P servicio", f"{_tf(est['Pu_kN']/fcarga):.1f} tonf", "Momento M",
         f"{_tm(geo['P_total_servicio_kN']*geo['excentricidad_m']):.1f} tonf·m"],
        ["q admisible", f"{_tm(geo['q_adm_kPa']):.1f} tonf/m²", "Profundidad Df", f"{Df:.2f} m"],
        ["f'c", f"{fc:.0f} MPa", "fy", f"{fy:.0f} MPa"],
        ["γ suelo", f"{gs/G:.2f} tonf/m³", "γ concreto", f"{gc/G:.2f} tonf/m³"],
        ["Ø barra", f"{db_mm:.1f} mm", "Recubrimiento", f"{rec*100:.1f} cm"],
        ["Factor de carga", f"{fcarga:.2f}", "Pu de diseño", f"{_tf(est['Pu_kN']):.1f} tonf"],
    ], [3.2 * cm, 4.0 * cm, 3.2 * cm, 4.0 * cm]))

    # Esquema
    fig = dibujar_zapata(resultado, entradas)
    img_buf = io.BytesIO()
    fig.savefig(img_buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    img_buf.seek(0)
    el.append(Spacer(1, 6))
    el.append(Image(img_buf, width=10.0 * cm, height=13.7 * cm))

    # 2. Dimensionamiento geotécnico
    el.append(Paragraph("2. Dimensionamiento geotécnico", h2))
    el.append(Paragraph(
        "El área se obtiene con la presión neta admisible (descontando el peso propio "
        "de la zapata y la sobrecarga de suelo). Se verifica que la presión de contacto "
        "no exceda la capacidad admisible del terreno.", p))
    el.append(_tabla([
        ["Área requerida", f"{geo['A_req_m2']:.2f} m²", "Dimensión B×L",
         f"{g['B_m']:.2f} × {g['L_m']:.2f} m"],
        ["P total (servicio)", f"{_tf(geo['P_total_servicio_kN']):.1f} tonf", "Excentricidad e",
         f"{geo['excentricidad_m']:.3f} m"],
        ["q máx", f"{_tm(geo['q_max_kPa']):.1f} tonf/m²", "q mín",
         f"{_tm(geo['q_min_kPa']):.1f} tonf/m²"],
        ["q admisible", f"{_tm(geo['q_adm_kPa']):.1f} tonf/m²", "Relación D/C",
         f"{geo['ratio']}"],
    ], [3.4 * cm, 3.8 * cm, 3.4 * cm, 3.8 * cm], header=False))
    el.append(Spacer(1, 3))
    el.append(Paragraph(f"<b>Verificación geotécnica: {_ok(geo['cumple'])}</b> "
                        f"(q<sub>máx</sub> ≤ q<sub>adm</sub>).", p))

    # 3. Diseño estructural
    el.append(Paragraph("3. Diseño estructural", h2))
    el.append(Paragraph(
        f"Presión neta de diseño q<sub>u</sub> = P<sub>u</sub> / (B·L) = "
        f"{_tm(est['qu_kPa']):.1f} tonf/m². Peralte efectivo d = {g['d_m']:.3f} m "
        f"(espesor h = {g['h_m']:.2f} m). Factores: φ<sub>cortante</sub> = 0.75, "
        f"φ<sub>flexión</sub> = 0.90.", p))

    # 3.1 Punzonamiento
    el.append(Paragraph("3.1 Cortante por punzonamiento (dos vías)", p))
    el.append(_tabla([
        ["b₀ (m)", "v_c (MPa)", "Vu (tonf)", "φVc (tonf)", "D/C", "Estado"],
        [f"{pz['b0_m']:.2f}", f"{pz['vc_MPa']:.2f}", f"{_tf(pz['Vu_kN']):.1f}",
         f"{_tf(pz['phiVc_kN']):.1f}", f"{pz['ratio']}",
         "cumple" if pz["cumple"] else "no cumple"],
    ], [2.6 * cm, 2.6 * cm, 2.8 * cm, 2.8 * cm, 2.0 * cm, 2.6 * cm]))

    # 3.2 Cortante una vía
    el.append(Spacer(1, 4))
    el.append(Paragraph("3.2 Cortante en una vía (viga ancha)", p))
    cuL, cuB = est["una_via_L"], est["una_via_B"]
    el.append(_tabla([
        ["Dirección", "Vu (tonf)", "φVc (tonf)", "D/C", "Estado"],
        ["Dir. B (volado en L)", f"{_tf(cuL['Vu_kN']):.1f}", f"{_tf(cuL['phiVc_kN']):.1f}",
         f"{cuL['ratio']}", "cumple" if cuL["cumple"] else "no cumple"],
        ["Dir. L (volado en B)", f"{_tf(cuB['Vu_kN']):.1f}", f"{_tf(cuB['phiVc_kN']):.1f}",
         f"{cuB['ratio']}", "cumple" if cuB["cumple"] else "no cumple"],
    ], [4.6 * cm, 2.8 * cm, 2.8 * cm, 2.0 * cm, 2.6 * cm]))

    # 3.3 Flexión
    el.append(Spacer(1, 4))
    el.append(Paragraph("3.3 Flexión y refuerzo", p))
    def _fila_flex(f, dirn):
        gob = " (mín.)" if f["gobierna_minimo"] else ""
        return [dirn, f"{_tm(f['Mu_kNm']):.2f}", f"{f['As_req_cm2']:.1f}",
                f"{f['As_cm2']:.1f}{gob}", f"{f['n_barras']} Ø{f['db_mm']:.1f} @ {f['sep_cm']:.0f} cm"]
    el.append(_tabla([
        ["Dirección", "Mu (tonf·m)", "As req (cm²)", "As (cm²)", "Refuerzo"],
        _fila_flex(fL, "Dir. B (volado en L)"),
        _fila_flex(fB, "Dir. L (volado en B)"),
    ], [4.2 * cm, 2.8 * cm, 2.8 * cm, 2.4 * cm, 4.0 * cm]))

    el.append(Spacer(1, 5))
    el.append(Paragraph(
        f"<b>Verificación al cortante: {_ok(est['cumple_cortante'])}</b> "
        f"(punzonamiento y una vía).", p))

    for a in resultado.get("avisos", []):
        el.append(Paragraph(f"⚠ {a}", small))

    el.append(Spacer(1, 14))
    el.append(HRFlowable(width="100%", thickness=0.5, color=GRIS_CLARO))
    el.append(Paragraph("Generado por CimX · Zapata aislada · NSR-10 / ACI 318", small))

    doc.build(el)
    return buf.getvalue()
