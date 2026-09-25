"""Memoria de cálculo del diseño de pilotes (PDF) + dibujo de elevación.

El diseño parte de la carga y de los parámetros geotécnicos (f_s, q_p, FS) y
determina diámetro, número de pilotes, longitud y acero longitudinal.
Unidades de presentación: MKS (tonf, tonf/m², cm²). El motor trabaja en SI.
"""
from __future__ import annotations

import io
import math
import os as _os
from datetime import date

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                TableStyle, Image, HRFlowable)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.pdfmetrics import registerFontFamily

G = 9.80665
VERDE = colors.HexColor("#16a34a")
GRIS = colors.HexColor("#475569")
GRIS_CLARO = colors.HexColor("#e2e8f0")
TINTA = colors.HexColor("#0f172a")

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


def dibujar_pilote_diseno(res) -> "plt.Figure":
    d = res["diseno"]; e = res["estructural"]
    D = d["D_m"]; L = d["L_m"]; n = d["N_pilotes"]
    C = {"pilote": "#6477a0", "suelo": "#d8bd86", "acero": "#d97a2b", "edge": "#1f2a44"}

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(5.6, 6.4),
                                   gridspec_kw={"width_ratios": [1.25, 1.0]})

    # --- Elevación de un pilote ---
    ax1.add_patch(Rectangle((-3, -L), 6, L, facecolor=C["suelo"], alpha=0.30, edgecolor="none"))
    ax1.add_patch(Rectangle((-D / 2, -L), D, L, facecolor=C["pilote"], edgecolor=C["edge"], lw=1.3))
    # acero longitudinal
    for xb in (-D / 2 + 0.06, D / 2 - 0.06):
        ax1.plot([xb, xb], [-L + 0.1, -0.1], color=C["acero"], lw=1.6)
    # espiral/estribos (líneas horizontales)
    nlin = max(6, int(L / 1.0))
    for i in range(nlin + 1):
        y = -L + (L) * i / nlin
        ax1.plot([-D / 2 + 0.05, D / 2 - 0.05], [y, y], color=C["acero"], lw=0.5, alpha=0.7)
    ax1.annotate("", xy=(D / 2 + 0.5, 0), xytext=(D / 2 + 0.5, -L),
                 arrowprops=dict(arrowstyle="<->", color="#334155", lw=1))
    ax1.text(D / 2 + 0.75, -L / 2, f"L = {L:.2f} m", rotation=90, va="center", ha="center",
             fontsize=10, fontweight="bold")
    ax1.annotate("", xy=(D / 2, 0.35), xytext=(-D / 2, 0.35),
                 arrowprops=dict(arrowstyle="<->", color="#334155", lw=1))
    ax1.text(0, 0.7, f"D = {D*100:.0f} cm", ha="center", fontsize=10, fontweight="bold")
    ax1.plot([-3, 3], [0, 0], color="#7a6a3a", lw=1.2)
    ax1.text(-2.8, 0.25, "N.T.", fontsize=8, color="#5a4a20")
    ax1.set_xlim(-3.2, 3.2); ax1.set_ylim(-L * 1.12, L * 0.18)
    ax1.set_aspect("auto"); ax1.axis("off")
    ax1.set_title("ELEVACIÓN", fontsize=10, fontweight="bold")

    # --- Sección transversal con barras ---
    ax2.add_patch(Circle((0, 0), D / 2, facecolor=C["pilote"], edgecolor=C["edge"], lw=1.4))
    rec = 0.075
    rb = (D / 2 - rec)
    nb = e["n_barras"]
    for i in range(nb):
        ang = 2 * math.pi * i / nb + math.pi / 2
        ax2.add_patch(Circle((rb * math.cos(ang), rb * math.sin(ang)), D * 0.028,
                             facecolor=C["acero"], edgecolor="#7a3a10", lw=0.6))
    ax2.add_patch(Circle((0, 0), rb, fill=False, edgecolor=C["acero"], lw=0.9, ls=(0, (4, 3))))
    ax2.set_xlim(-D / 2 * 1.3, D / 2 * 1.3); ax2.set_ylim(-D / 2 * 1.3, D / 2 * 1.3)
    ax2.set_aspect("equal"); ax2.axis("off")
    ax2.set_title(f"SECCIÓN · {nb}Ø{e['db_long_mm']:.0f}", fontsize=10, fontweight="bold")
    ax2.text(0, -D / 2 * 1.22, f"{n} pilote(s)", ha="center", fontsize=9, color="#33404a")

    fig.tight_layout()
    return fig


def _tabla(data, anchos, header=True):
    t = Table(data, colWidths=anchos)
    est = [("FONTSIZE", (0, 0), (-1, -1), 8.5), ("FONTNAME", (0, 0), (-1, -1), _FONT),
           ("TEXTCOLOR", (0, 0), (-1, -1), TINTA), ("LINEBELOW", (0, 0), (-1, -1), 0.4, GRIS_CLARO),
           ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
           ("LEFTPADDING", (0, 0), (-1, -1), 6)]
    if header:
        est += [("FONTNAME", (0, 0), (-1, 0), _FONT_B), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("BACKGROUND", (0, 0), (-1, 0), VERDE)]
    t.setStyle(TableStyle(est))
    return t


def _ok(b):
    return ("<font color='#15803d'>CUMPLE</font>" if b else "<font color='#b91c1c'>NO CUMPLE</font>")


def generar_memoria_pilote_diseno(datos, resultado, entradas) -> bytes:
    d = resultado["diseno"]; e = resultado["estructural"]
    g = resultado["geotecnia"]; ca = resultado["cargas"]
    tr = e["transversal"]

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm,
                            topMargin=1.8 * cm, bottomMargin=1.8 * cm,
                            title="Memoria — Diseño de pilotes")
    ss = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=ss["Heading1"], fontName=_FONT_B, fontSize=15, textColor=TINTA, spaceAfter=2)
    h2 = ParagraphStyle("h2", parent=ss["Heading2"], fontName=_FONT_B, fontSize=11.5, textColor=VERDE, spaceBefore=12, spaceAfter=5)
    p = ParagraphStyle("p", parent=ss["BodyText"], fontName=_FONT, fontSize=9, textColor=TINTA, leading=13)
    small = ParagraphStyle("small", parent=p, fontName=_FONT, fontSize=8, textColor=GRIS)
    el = []

    fc = float(entradas.get("fc", 21) or 21)
    fy = float(entradas.get("fy", 420) or 420)
    ccp = str(resultado.get("norma", "NSR10")) == "CCP14"
    norm_titulo = "CCP-14 (LRFD-AASHTO)" if ccp else "NSR-10 / ACI 318"

    el.append(Paragraph("Memoria de cálculo — Diseño de pilotes", h1))
    el.append(Paragraph(f"Diseño estructural a partir de la carga y de los parámetros geotécnicos · {norm_titulo}", small))
    el.append(HRFlowable(width="100%", thickness=1, color=VERDE, spaceBefore=6, spaceAfter=6))
    el.append(_tabla([
        ["Proyecto", getattr(datos, "proyecto", "") or "—", "Fecha", date.today().isoformat()],
        ["Ingeniero", getattr(datos, "ingeniero", "") or "—", "Ubicación", getattr(datos, "ubicacion", "") or "—"],
    ], [2.6 * cm, 6.5 * cm, 2.2 * cm, 5.0 * cm], header=False))

    # 1. Entrada
    el.append(Paragraph("1. Datos de entrada", h2))
    el.append(_tabla([
        ["Parámetro", "Valor", "Parámetro", "Valor"],
        ["Carga de servicio P", f"{_tf(ca['P_servicio_kN']):.1f} tonf", "Factor de carga", f"{ca['factor_carga']:.2f}"],
        ["Fricción f_s", f"{_tm(g['f_s_kPa']):.1f} tonf/m²", "Punta q_p", f"{_tm(g['q_p_kPa']):.1f} tonf/m²"],
        (["Norma", "CCP-14 (LRFD)", "φ fuste / punta", f"{g['phi_fuste']} / {g['phi_punta']}"]
         if ccp else ["FS geotécnico", f"{g['FS']:.1f}", "Refuerzo transversal", tr["tipo"]]),
        ["f'c", f"{fc:.0f} MPa", "fy", f"{fy:.0f} MPa"],
    ], [3.6 * cm, 4.0 * cm, 3.6 * cm, 4.0 * cm]))

    fig = dibujar_pilote_diseno(resultado)
    img = io.BytesIO(); fig.savefig(img, format="png", dpi=150, bbox_inches="tight"); plt.close(fig); img.seek(0)
    el.append(Spacer(1, 6))
    el.append(Image(img, width=10.5 * cm, height=12.0 * cm))

    # 2. Diseño resultante
    el.append(Paragraph("2. Diseño resultante", h2))
    el.append(_tabla([
        ["Diámetro D", f"{d['D_m']*100:.0f} cm", "N° de pilotes", f"{d['N_pilotes']}"],
        ["Longitud L", f"{d['L_m']:.2f} m", "Volumen concreto", f"{d['volumen_concreto_m3']:.2f} m³"],
        ["Acero longitudinal", f"{e['n_barras']} Ø{e['db_long_mm']:.0f} ({e['A_st_cm2']:.1f} cm²)",
         "Cuantía ρ", f"{e['cuantia_pct']:.2f} %"],
    ], [3.6 * cm, 4.0 * cm, 3.6 * cm, 4.0 * cm], header=False))
    if tr["tipo"] == "espiral":
        el.append(Paragraph(f"Refuerzo transversal: espiral con paso ≤ {tr['paso_m']*100:.0f} cm "
                            f"(ρ_s = {tr['rho_s']*100:.2f}%).", small))
    else:
        el.append(Paragraph(f"Refuerzo transversal: estribos con separación ≤ {tr['sep_max_m']*100:.0f} cm.", small))

    # 3. Verificación estructural
    el.append(Paragraph("3. Capacidad estructural (columna corta)", h2))
    el.append(Paragraph(
        "φP<sub>n,máx</sub> = φ·α·[0.85·f'c·(A<sub>g</sub>−A<sub>st</sub>) + fy·A<sub>st</sub>] "
        f"(φ = {e['phi']}). Carga mayorada por pilote P<sub>u</sub>/N.", p))
    el.append(_tabla([
        ["A_g (m²)", "A_st (cm²)", "φPn (tonf)", "Pu/pilote (tonf)", "D/C", "Estado"],
        [f"{e['A_g_m2']:.3f}", f"{e['A_st_cm2']:.1f}", f"{_tf(e['phiPn_kN']):.1f}",
         f"{_tf(e['Pu_pilote_kN']):.1f}", f"{e['ratio']}", "cumple" if e["cumple"] else "no cumple"],
    ], [2.6 * cm, 2.6 * cm, 2.8 * cm, 3.2 * cm, 1.8 * cm, 2.4 * cm]))

    # 4. Verificación geotécnica (según norma)
    el.append(Paragraph("4. Capacidad geotécnica por pilote", h2))
    if ccp:
        el.append(Paragraph(
            "Q<sub>últ</sub> = q_p·A_punta + f_s·(π·D·L). LRFD: "
            "R<sub>r</sub> = φ<sub>p</sub>·Q<sub>punta</sub> + φ<sub>s</sub>·Q<sub>fuste</sub> ≥ P<sub>u</sub>/N "
            f"(φ según el material, Tabla 10.5.5.2.4-1).", p))
        el.append(_tabla([
            ["Q_punta (tonf)", "Q_fuste (tonf)", "Q_últ (tonf)", "R_r (tonf)", "Pu/pilote (tonf)", "CDR", "Estado"],
            [f"{_tf(g['Qpunta_kN']):.1f}", f"{_tf(g['Qfuste_kN']):.1f}", f"{_tf(g['Qult_kN']):.1f}",
             f"{_tf(g['R_r_kN']):.1f}", f"{_tf(g['Pu_pilote_kN']):.1f}", f"{g['CDR']}",
             "cumple" if g["cumple"] else "no cumple"],
        ], [2.5 * cm, 2.5 * cm, 2.3 * cm, 2.3 * cm, 2.5 * cm, 1.5 * cm, 2.2 * cm]))
    else:
        el.append(Paragraph(
            "Q<sub>últ</sub> = q_p·A_punta + f_s·(π·D·L) ; Q<sub>adm</sub> = Q<sub>últ</sub>/FS ≥ P_servicio/N.", p))
        el.append(_tabla([
            ["Q_punta (tonf)", "Q_fuste (tonf)", "Q_últ (tonf)", "Q_adm (tonf)", "P/pilote (tonf)", "D/C", "Estado"],
            [f"{_tf(g['Qpunta_kN']):.1f}", f"{_tf(g['Qfuste_kN']):.1f}", f"{_tf(g['Qult_kN']):.1f}",
             f"{_tf(g['Qadm_kN']):.1f}", f"{_tf(g['Pserv_pilote_kN']):.1f}", f"{g['ratio']}",
             "cumple" if g["cumple"] else "no cumple"],
        ], [2.5 * cm, 2.5 * cm, 2.3 * cm, 2.3 * cm, 2.5 * cm, 1.5 * cm, 2.2 * cm]))

    el.append(Spacer(1, 6))
    el.append(Paragraph(f"<b>Verificación global: {_ok(resultado['cumple'])}</b> "
                        f"(estructural y geotécnica).", p))
    for a in resultado.get("avisos", []):
        el.append(Paragraph(f"⚠ {a}", small))

    el.append(Spacer(1, 12))
    el.append(HRFlowable(width="100%", thickness=0.5, color=GRIS_CLARO))
    el.append(Paragraph(f"Generado por CimX · Diseño de pilotes · {norm_titulo}", small))
    doc.build(el)
    return buf.getvalue()
