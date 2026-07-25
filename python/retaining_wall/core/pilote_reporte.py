"""Memoria de cálculo del pilote (PDF) y dibujo en elevación.

Genera un reporte profesional con:
  - datos del pilote, perfil de suelo y cargas,
  - esquema en elevación (matplotlib),
  - capacidad de carga axial (punta + fuste, por estrato),
  - diseño estructural (columna corta).

Unidades de presentación: MKS (tonf, tonf/m²) — el motor trabaja en SI.
"""
from __future__ import annotations

import io
import math
from datetime import date

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Polygon

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                TableStyle, Image, HRFlowable)

G = 9.80665  # kN -> tonf, kPa -> tonf/m²

VERDE = colors.HexColor("#16a34a")
GRIS = colors.HexColor("#475569")
GRIS_CLARO = colors.HexColor("#e2e8f0")
TINTA = colors.HexColor("#0f172a")

# Fuente Unicode (DejaVuSans, incluida con matplotlib) para que ², ³, φ, σ, δ, ·, ≈ rendericen.
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
# Dibujo en elevación (matplotlib)
# ---------------------------------------------------------------------------
def dibujar_pilote(pilote, perfil) -> "plt.Figure":
    D, L = pilote.D, pilote.L
    hw = D / 2.0
    nf = perfil.nivel_freatico
    sumE = perfil.profundidad_total
    prof = max(L, sumE) * 1.05
    W = max(1.2, 2.2 * D)

    fig, ax = plt.subplots(figsize=(5.2, 6.0))
    C = {"arena": "#d8bd86", "arcilla": "#a98c66", "concreto": "#7f8a93",
         "agua": "#3b9ad6"}

    # Estratos
    z = 0.0
    for e in perfil.estratos:
        col = C["arena"] if e.tipo == "arena" else C["arcilla"]
        ax.add_patch(Rectangle((-W, z), 2 * W, e.espesor, facecolor=col,
                               edgecolor="#6b5b3e", lw=0.6, alpha=0.85, zorder=1))
        ym = z + e.espesor / 2.0
        prop = (f"φ={e.phi:.0f}°" if e.tipo == "arena" else f"cu={_tm(e.cu):.1f} tonf/m²")
        ax.text(W * 1.04, ym - 0.12, e.nombre or e.tipo, fontsize=8.5,
                fontweight="bold", va="center")
        ax.text(W * 1.04, ym + 0.18, f"{prop}, γ={e.gamma/G:.2f} tonf/m³",
                fontsize=7.5, color="#444", va="center")
        z += e.espesor

    # Pilote + punta
    ax.add_patch(Rectangle((-hw, 0), D, L, facecolor=C["concreto"],
                           edgecolor="#2b3137", lw=1.4, zorder=3))
    ax.add_patch(Polygon([(-hw, L), (hw, L), (0, L + 0.5 * D)],
                         facecolor=C["concreto"], edgecolor="#2b3137", lw=1.4, zorder=3))

    # Nivel freático
    if nf is not None and 0 <= nf < prof:
        ax.plot([-W, W], [nf, nf], color=C["agua"], lw=1.4, ls="--", zorder=4)
        ax.text(-W * 0.95, nf - 0.12, f"N.F. {nf:.1f} m", color=C["agua"],
                fontsize=8, va="bottom")

    # Cota L
    ax.annotate("", xy=(-W * 1.18, L), xytext=(-W * 1.18, 0),
                arrowprops=dict(arrowstyle="<->", color="#334155", lw=1))
    ax.text(-W * 1.30, L / 2, f"L = {L:.2f} m", rotation=90, va="center",
            ha="center", fontsize=9, fontweight="bold")
    # Cota D
    ax.text(0, -0.30, f"D = {D:.2f} m", ha="center", fontsize=9, fontweight="bold")

    # Flechas de fuste y punta
    for i in range(1, 5):
        yy = L * i / 5.0
        ax.annotate("", xy=(hw, yy), xytext=(hw + 0.28 * W, yy),
                    arrowprops=dict(arrowstyle="->", color="#d18f2a", lw=1.1))
        ax.annotate("", xy=(-hw, yy), xytext=(-hw - 0.28 * W, yy),
                    arrowprops=dict(arrowstyle="->", color="#d18f2a", lw=1.1))
    ax.annotate("", xy=(0, L + 0.5 * D), xytext=(0, L + 0.5 * D + 0.9),
                arrowprops=dict(arrowstyle="->", color="#d18f2a", lw=1.4))
    ax.text(0.05 * W, L * 0.5, "Qfuste", color="#b9781f", fontsize=8, rotation=90, va="center")
    ax.text(0, L + 0.5 * D + 1.05, "Qpunta", color="#b9781f", fontsize=8, ha="center")

    ax.set_xlim(-W * 1.5, W * 1.6)
    ax.set_ylim(0, prof + 0.6)
    ax.invert_yaxis()
    ax.set_aspect("auto")
    ax.set_xticks([])
    ax.set_ylabel("Profundidad (m)", fontsize=9)
    for s in ("top", "right", "bottom"):
        ax.spines[s].set_visible(False)
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


def generar_memoria_pilote(datos, pilote, perfil, resultado) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=2 * cm, rightMargin=2 * cm,
                            topMargin=1.8 * cm, bottomMargin=1.8 * cm,
                            title="Memoria de cálculo — Pilote")
    ss = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=ss["Heading1"], fontName=_FONT_B, fontSize=15, textColor=TINTA, spaceAfter=2)
    h2 = ParagraphStyle("h2", parent=ss["Heading2"], fontName=_FONT_B, fontSize=11.5, textColor=VERDE,
                        spaceBefore=12, spaceAfter=5)
    p = ParagraphStyle("p", parent=ss["BodyText"], fontName=_FONT, fontSize=9, textColor=TINTA, leading=13)
    small = ParagraphStyle("small", parent=p, fontName=_FONT, fontSize=8, textColor=GRIS)
    el = []

    cap = resultado["capacidad"]
    est = resultado["estructural"]
    pu = cap["punta"]

    # Encabezado
    el.append(Paragraph("Memoria de cálculo — Diseño de pilote", h1))
    el.append(Paragraph("Pilote de concreto vaciado in situ · Capacidad axial y diseño estructural · NSR-10",
                        small))
    el.append(HRFlowable(width="100%", thickness=1, color=VERDE, spaceBefore=6, spaceAfter=6))

    proy = getattr(datos, "proyecto", "") or "—"
    ing = getattr(datos, "ingeniero", "") or "—"
    ubic = getattr(datos, "ubicacion", "") or "—"
    el.append(_tabla([
        ["Proyecto", proy, "Fecha", date.today().isoformat()],
        ["Ingeniero", ing, "Ubicación", ubic],
    ], [2.6 * cm, 6.5 * cm, 2.2 * cm, 5.0 * cm], header=False))

    # 1. Datos
    el.append(Paragraph("1. Datos de entrada", h2))
    el.append(_tabla([
        ["Parámetro", "Valor", "Parámetro", "Valor"],
        ["Diámetro D", f"{pilote.D:.2f} m", "f'c", f"{pilote.fc:.0f} MPa"],
        ["Longitud L", f"{pilote.L:.2f} m", "fy", f"{pilote.fy:.0f} MPa"],
        ["Refuerzo long.", f"{pilote.n_barras} Ø{pilote.db_long:.1f} mm",
         "Transversal", pilote.tipo_refuerzo],
        ["FS geotécnico", f"{cap['FS']:.1f}", "P servicio", f"{_tf(resultado['P_servicio_kN']):.1f} tonf"],
    ], [3.0 * cm, 4.0 * cm, 3.0 * cm, 4.0 * cm]))

    el.append(Spacer(1, 6))
    el.append(Paragraph("Perfil de suelo", p))
    filas = [["#", "Tipo", "Espesor (m)", "γ (tonf/m³)", "φ (°)", "cu (tonf/m²)"]]
    for i, e in enumerate(perfil.estratos, 1):
        filas.append([str(i), e.tipo, f"{e.espesor:.2f}", f"{e.gamma/G:.2f}",
                      f"{e.phi:.0f}" if e.tipo == "arena" else "—",
                      f"{_tm(e.cu):.1f}" if e.tipo == "arcilla" else "—"])
    nf_txt = f"{perfil.nivel_freatico:.1f} m" if perfil.nivel_freatico is not None else "sin N.F."
    el.append(_tabla(filas, [1.0 * cm, 3.0 * cm, 2.6 * cm, 3.0 * cm, 2.0 * cm, 3.2 * cm]))
    el.append(Paragraph(f"Nivel freático: {nf_txt}.", small))

    # Esquema
    fig = dibujar_pilote(pilote, perfil)
    img_buf = io.BytesIO()
    fig.savefig(img_buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    img_buf.seek(0)
    el.append(Spacer(1, 6))
    el.append(Image(img_buf, width=10.5 * cm, height=12.1 * cm))

    # 2. Capacidad axial
    el.append(Paragraph("2. Capacidad de carga axial", h2))
    el.append(Paragraph(
        "Q<sub>límite</sub> = Q<sub>punta</sub> + Q<sub>fuste</sub>. Arenas: "
        "q<sub>p</sub> = σ'<sub>v</sub>·Nq (límite de Meyerhof) y f = K·σ'<sub>v</sub>·tanδ. "
        "Arcillas: q<sub>p</sub> = 9·c<sub>u</sub> y f = α·c<sub>u</sub>.", p))
    filas = [["Estrato", "Tipo", "Prof. (m)", "f (tonf/m²)", "Qs (tonf)"]]
    for d in cap["fuste_detalle"]:
        filas.append([d["estrato"], d["tipo"], f"{d['desde']:.1f}–{d['hasta']:.1f}",
                      f"{_tm(d['f_prom_kPa']):.2f}", f"{_tf(d['Qs_kN']):.1f}"])
    el.append(_tabla(filas, [4.0 * cm, 2.6 * cm, 3.0 * cm, 3.2 * cm, 3.0 * cm]))

    if pu["tipo"] == "arena":
        punta = (f"Punta (arena): Nq = {pu['Nq']}, q<sub>p</sub> = {_tm(pu['qp_kPa']):.1f} tonf/m² "
                 f"(límite Meyerhof aplicado)." if pu["qp_kPa"] < pu.get("qp_sin_limite_kPa", 9e9)
                 else f"Punta (arena): Nq = {pu['Nq']}, q<sub>p</sub> = {_tm(pu['qp_kPa']):.1f} tonf/m².")
    else:
        punta = f"Punta (arcilla): Nc = 9, q<sub>p</sub> = {_tm(pu['qp_kPa']):.1f} tonf/m²."
    el.append(Spacer(1, 4))
    el.append(Paragraph(punta, p))
    el.append(_tabla([
        ["Q punta", f"{_tf(cap['Q_punta_kN']):.1f} tonf",
         "Q fuste", f"{_tf(cap['Q_fuste_kN']):.1f} tonf"],
        ["Q límite", f"{_tf(cap['Q_limite_kN']):.1f} tonf",
         f"Q admisible (FS={cap['FS']:.1f})", f"{_tf(cap['Q_adm_kN']):.1f} tonf"],
    ], [3.2 * cm, 4.0 * cm, 4.6 * cm, 4.0 * cm], header=False))
    el.append(Spacer(1, 4))
    el.append(Paragraph(
        f"<b>Número de pilotes</b> para P = {_tf(resultado['P_servicio_kN']):.1f} tonf: "
        f"<b>N = {resultado['N_pilotes']}</b>.", p))

    # 3. Estructural
    el.append(Paragraph("3. Diseño estructural (columna corta)", h2))
    el.append(Paragraph(
        "φP<sub>n,máx</sub> = φ·α·[0.85·f'c·(A<sub>g</sub> − A<sub>st</sub>) + fy·A<sub>st</sub>], "
        f"con φ = {est['phi']:.2f}.", p))
    tr = est["transversal"]
    if tr["tipo"] == "espiral":
        trtxt = f"Zuncho: ρs = {tr['rho_s_requerida']*100:.2f}%, paso ≈ {tr['paso_m']*100:.1f} cm"
    else:
        trtxt = f"Estribos: separación máx ≈ {tr['separacion_max_m']*100:.1f} cm"
    el.append(_tabla([
        ["A_g", f"{est['A_g_m2']*1e4:.0f} cm²", "A_st", f"{est['A_st_cm2']:.1f} cm²"],
        ["Cuantía ρ", f"{est['cuantia_pct']:.2f} %", "φP_n,máx", f"{_tf(est['phiPn_kN']):.1f} tonf"],
        ["Transversal", trtxt, "", ""],
    ], [3.0 * cm, 4.0 * cm, 3.0 * cm, 4.0 * cm], header=False))

    if est.get("Pu_por_pilote_kN") is not None:
        ok = est.get("cumple_estructural")
        veredicto = "CUMPLE" if ok else "NO CUMPLE"
        cverd = colors.HexColor("#15803d") if ok else colors.HexColor("#b91c1c")
        el.append(Spacer(1, 4))
        msg = (f"P<sub>u</sub> por pilote = {_tf(est['Pu_por_pilote_kN']):.1f} tonf "
               f"(factor {est.get('factor_carga', 1.5)}). φP<sub>n</sub> = "
               f"{_tf(est['phiPn_kN']):.1f} tonf → relación D/C = {est['ratio_demanda_capacidad']}.")
        el.append(Paragraph(msg, p))
        el.append(Paragraph(f"<b>Verificación estructural: <font color='{cverd.hexval()}'>{veredicto}</font></b>", p))

    for a in est.get("avisos", []):
        el.append(Paragraph(f"⚠ {a}", small))

    el.append(Spacer(1, 14))
    el.append(HRFlowable(width="100%", thickness=0.5, color=GRIS_CLARO))
    el.append(Paragraph("Generado por CimX · Metodología: Rodríguez Serquén / Das · NSR-10",
                        small))

    doc.build(el)
    return buf.getvalue()
