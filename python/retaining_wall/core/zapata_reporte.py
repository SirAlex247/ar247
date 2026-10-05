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
from matplotlib.patches import Rectangle, Polygon

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

    C = {"concreto": "#7f8a93", "hatch": "#333b45", "col": "#9aa6ae",
         "suelo": "#d8bd86", "acero": "#d97a2b"}
    plt.rcParams["hatch.linewidth"] = 0.5

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(5.4, 7.4),
                                   gridspec_kw={"height_ratios": [1.0, 1.0]})

    # ---------------- PLANTA ----------------
    ax1.add_patch(Rectangle((-B / 2, -L / 2), B, L, facecolor=C["concreto"],
                            edgecolor=C["hatch"], lw=1.4, alpha=0.5, hatch="xxx"))
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


def _fig_to_image(fig, ancho_cm, alto_cm) -> "Image":
    """Renderiza una figura matplotlib a un flowable Image (cerrando la figura)."""
    b = io.BytesIO()
    fig.savefig(b, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    b.seek(0)
    return Image(b, width=ancho_cm * cm, height=alto_cm * cm)


def _titulo_aislada(resultado) -> str:
    """Título descriptivo para la memoria de la aislada / conectada.

    Ej.: «Zapata aislada rectangular · excéntrica», «Zapata conectada /
    medianera (con viga centradora)».
    """
    tipo = resultado.get("tipo", "aislada")
    if tipo == "conectada":
        vc = resultado.get("esquinera", {}).get("viga_centradora", True)
        return ("Zapata conectada / medianera"
                + (" (con viga centradora)" if vc else " (sin viga centradora)"))
    partes = ["Zapata aislada"]
    forma = resultado.get("forma", "")
    if forma:
        partes.append(forma)
    txt = " ".join(partes)
    carga = resultado.get("carga", "")
    if carga:
        txt += f" · {carga}"
    return txt


def generar_memoria_zapata(datos, resultado, entradas) -> bytes:
    est = resultado.get("estructural", {})
    # Los tipos combinada/triangular tienen otra forma de resultado → memoria
    # específica. La aislada (y la esquinera, que reusa su forma) sigue aquí.
    if "flexion_L" not in est:
        return _memoria_zapata_especial(datos, resultado, entradas,
                                        resultado.get("tipo", "aislada"))
    g = resultado["geometria"]
    geo = resultado["geotecnico"]
    pz = est["punzonamiento"]
    fL = est["flexion_L"]
    fB = est["flexion_B"]

    titulo = _titulo_aislada(resultado)
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=2 * cm, rightMargin=2 * cm,
                            topMargin=1.8 * cm, bottomMargin=1.8 * cm,
                            title=f"Memoria de cálculo — {titulo}")
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
    Mx = float(entradas.get("M_servicio", 0.0) or 0.0)
    My = float(entradas.get("My_servicio", 0.0) or 0.0)
    if abs(My) > 1e-9:
        mom_str = f"Mx={_tf(Mx):.1f} · My={_tf(My):.1f} tonf·m"
    elif abs(Mx) > 1e-9:
        mom_str = f"{_tf(Mx):.1f} tonf·m"
    else:
        mom_str = "0.0 tonf·m (concéntrica)"

    # Encabezado
    el.append(Paragraph(f"Memoria de cálculo — {titulo}", h1))
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
        ["P servicio", f"{_tf(est['Pu_kN']/fcarga):.1f} tonf", "Momento", mom_str],
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
    if pz.get("vu_momento_kPa", 0) > 0.1:
        el.append(Spacer(1, 3))
        el.append(Paragraph(
            "Transferencia de momento por cortante excéntrico (NSR-10 C.11.11.7): "
            f"v<sub>u</sub> = {_tm(pz['vu_directo_kPa']):.1f} (directo) + "
            f"{_tm(pz['vu_momento_kPa']):.1f} (γ<sub>v</sub>·M, γ<sub>v</sub>={pz['gamma_v_x']}) = "
            f"<b>{_tm(pz['vu_total_kPa']):.1f}</b> tonf/m² vs φv<sub>c</sub> = "
            f"{_tm(pz['phi_vc_kPa']):.1f} tonf/m² → <b>{_ok(pz['cumple_momento'])}</b> "
            f"(D/C = {pz['ratio_momento']}).", p))

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
        dv = f.get("desarrollo", {})
        ld = (f"{dv.get('ld_m', 0):.2f}/{dv.get('ld_disponible_m', 0):.2f}"
              + ("" if dv.get("cumple", True) else " ✗") if dv else "—")
        return [dirn, f"{_tm(f['Mu_kNm']):.2f}", f"{f['As_cm2']:.1f}{gob}",
                f"{f['n_barras']} Ø{f['db_mm']:.1f} @ {f['sep_cm']:.0f} cm", ld]
    el.append(_tabla([
        ["Dirección", "Mu (tonf·m)", "As (cm²)", "Refuerzo", "ℓd/disp (m)"],
        _fila_flex(fL, "Dir. B (volado en L)"),
        _fila_flex(fB, "Dir. L (volado en B)"),
    ], [3.8 * cm, 2.6 * cm, 2.2 * cm, 4.2 * cm, 3.0 * cm]))
    # Banda central (zapata rectangular)
    banda = fL.get("banda_central") or fB.get("banda_central")
    if banda:
        el.append(Spacer(1, 3))
        el.append(Paragraph(
            "Distribución en banda central del refuerzo de la dirección corta "
            f"(NSR-10 C.15.4.4.2): β = {banda['beta']}, γ<sub>s</sub> = "
            f"{banda['gamma_s']} → {banda['n_banda']} barras en la banda central "
            f"(ancho {banda['ancho_banda_m']:.2f} m) + {banda['n_fuera']} fuera.", p))
    # Control de fisuración y cuantía máxima (ductilidad)
    fis = fL.get("fisuracion"); cua = fL.get("cuantia")
    if fis and cua:
        el.append(Spacer(1, 2))
        el.append(Paragraph(
            f"Control de fisuración (C.10.6.4): separación {fL['sep_cm']:.0f} cm ≤ "
            f"{fis['sep_max_m']*100:.0f} cm {_ok(fis['cumple'])}. "
            f"Cuantía (C.10.3.5): ρ = {cua['rho']:.4f} ≤ ρ<sub>máx</sub> = "
            f"{cua['rho_max']:.4f} {_ok(cua['cumple'])}.", p))

    # 3.4 Transferencia de carga (aplastamiento + dowels)
    tr = est.get("transferencia")
    if tr:
        el.append(Spacer(1, 6))
        el.append(Paragraph("3.4 Transferencia de carga columna→zapata (C.15.8)", p))
        el.append(_tabla([
            ["Concepto", "Valor", "Concepto", "Valor"],
            ["Pu (tonf)", f"{_tf(tr['Pu_kN']):.1f}", "√(A₂/A₁)", f"{tr['sqrt_A2A1']}"],
            ["φPn zapata (tonf)", f"{_tf(tr['phiPn_zapata_kN']):.1f}",
             "φPn columna (tonf)", f"{_tf(tr['phiPn_columna_kN']):.1f}"],
            ["Aplastamiento D/C", f"{tr['ratio']}", "Estado",
             "cumple" if tr["cumple_aplastamiento"] else "no cumple"],
            ["Dowels", f"{tr['n_dowels']} Ø{tr['db_dowel_mm']:.1f}",
             "As dowels (cm²)", f"{tr['As_dowels_req_cm2']:.1f}"
             + (" mín" if tr["gobierna_minimo"] else "")],
            ["ℓdc dowel (m)", f"{tr['ldc_dowel_m']:.2f}", "ℓdc disponible (m)",
             f"{tr['ldc_disponible_m']:.2f}"],
        ], [4.2 * cm, 3.4 * cm, 4.2 * cm, 3.4 * cm]))

    el.append(Spacer(1, 5))
    el.append(Paragraph(
        f"<b>Verificación al cortante: {_ok(est['cumple_cortante'])}</b> "
        f"(punzonamiento —con momento— y una vía) · "
        f"<b>Transferencia: {_ok(est.get('cumple_transferencia', True))}</b>.", p))

    for a in resultado.get("avisos", []):
        el.append(Paragraph(f"⚠ {a}", small))

    el.append(Spacer(1, 14))
    el.append(HRFlowable(width="100%", thickness=0.5, color=GRIS_CLARO))
    el.append(Paragraph(f"Generado por CimX · {titulo} · NSR-10 / ACI 318", small))

    doc.build(el)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Dibujos de los tipos especiales (combinada, triangular)
# ---------------------------------------------------------------------------
def dibujar_combinada(res, entradas) -> "plt.Figure":
    """Planta (dos columnas sobre la viga-zapata) + diagrama de momentos M(x)."""
    g, est = res["geometria"], res["estructural"]
    B, L = g["B_m"], g["L_m"]
    x1, x2 = g["x1_col_m"], g["x2_col_m"]
    c1a, c2a = g["c1a_m"], g["c2a_m"]
    c1b, c2b = g["c1b_m"], g["c2b_m"]
    Pu1, Pu2 = est["Pu1_kN"], est["Pu2_kN"]
    w = (Pu1 + Pu2) / L if L else 0.0

    def M(x):
        m = w * x * x / 2.0
        if x > x1:
            m -= Pu1 * (x - x1)
        if x > x2:
            m -= Pu2 * (x - x2)
        return m

    C = {"concreto": "#7f8a93", "hatch": "#333b45", "col": "#9aa6ae",
         "mpos": "#2f6f4f", "mneg": "#b45309"}
    plt.rcParams["hatch.linewidth"] = 0.5

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(6.2, 5.8),
                                   gridspec_kw={"height_ratios": [1.0, 1.05]})

    # -------------------- PLANTA --------------------
    ax1.add_patch(Rectangle((0, -B / 2), L, B, facecolor=C["concreto"],
                            edgecolor=C["hatch"], lw=1.4, alpha=0.5, hatch="xxx"))
    for xc, c1c, c2c, lab in [(x1, c1a, c2a, "C1"), (x2, c1b, c2b, "C2")]:
        ax1.add_patch(Rectangle((xc - c1c / 2, -c2c / 2), c1c, c2c,
                                facecolor=C["col"], edgecolor="#2b3137", lw=1.2))
        ax1.text(xc, c2c / 2 + 0.05 * B + 0.03, lab, ha="center", va="bottom",
                 fontsize=8.5, fontweight="bold", color="#33404a")
    ax1.annotate("", xy=(L, -B / 2 - 0.20 * B), xytext=(0, -B / 2 - 0.20 * B),
                 arrowprops=dict(arrowstyle="<->", color="#334155", lw=1))
    ax1.text(L / 2, -B / 2 - 0.34 * B, f"L = {L:.2f} m", ha="center",
             fontsize=8.5, fontweight="bold")
    ax1.annotate("", xy=(x2, B / 2 + 0.12 * B), xytext=(x1, B / 2 + 0.12 * B),
                 arrowprops=dict(arrowstyle="<->", color="#334155", lw=1))
    ax1.text((x1 + x2) / 2, B / 2 + 0.17 * B, f"s = {x2 - x1:.2f} m",
             ha="center", fontsize=8)
    ax1.text(-0.03 * L, 0, f"B = {B:.2f} m", ha="right", va="center",
             rotation=90, fontsize=8.5, fontweight="bold")
    ax1.set_xlim(-0.12 * L, 1.06 * L)
    ax1.set_ylim(-B * 1.05, B * 1.05)
    ax1.set_aspect("equal")
    ax1.set_title("PLANTA", fontsize=10, fontweight="bold")
    ax1.axis("off")

    # -------------------- DIAGRAMA DE MOMENTOS --------------------
    xs = [L * i / 240 for i in range(241)]
    ms = [M(x) / G for x in xs]           # tonf·m
    ax2.axhline(0, color="#334155", lw=1.0)
    ax2.plot(xs, ms, color="#1f2937", lw=1.5)
    ax2.fill_between(xs, ms, 0, where=[m >= 0 for m in ms],
                     color=C["mpos"], alpha=0.28, interpolate=True)
    ax2.fill_between(xs, ms, 0, where=[m < 0 for m in ms],
                     color=C["mneg"], alpha=0.28, interpolate=True)
    for xc in (x1, x2):
        ax2.axvline(xc, color=C["col"], ls="--", lw=0.8)
    Mp, xp = est["M_pos_kNm"] / G, est["x_M_pos_m"]
    Mn, xn = est["M_neg_kNm"] / G, est["x_M_neg_m"]
    if abs(Mp) > 1e-6:
        ax2.plot(xp, Mp, "o", color=C["mpos"], ms=4)
        ax2.annotate(f"M⁺={Mp:.1f}", xy=(xp, Mp), xytext=(0, 6),
                     textcoords="offset points", ha="center", fontsize=8,
                     color=C["mpos"], fontweight="bold")
    if abs(Mn) > 1e-6:
        ax2.plot(xn, Mn, "o", color=C["mneg"], ms=4)
        ax2.annotate(f"M⁻={Mn:.1f}", xy=(xn, Mn), xytext=(0, -12),
                     textcoords="offset points", ha="center", fontsize=8,
                     color=C["mneg"], fontweight="bold")
    ax2.set_xlim(-0.02 * L, 1.02 * L)
    ax2.set_title("DIAGRAMA DE MOMENTOS  [tonf·m]", fontsize=10, fontweight="bold")
    ax2.set_xlabel("x  [m]", fontsize=8)
    ax2.grid(True, ls=":", lw=0.4, alpha=0.5)
    for s in ("top", "right"):
        ax2.spines[s].set_visible(False)

    fig.tight_layout()
    return fig


def dibujar_triangular(res, entradas) -> "plt.Figure":
    """Planta triangular isósceles con la columna en el baricentro."""
    g = res["geometria"]
    base, altura = g["base_m"], g["altura_m"]
    c1, c2 = g["c1_m"], g["c2_m"]

    C = {"concreto": "#7f8a93", "hatch": "#333b45", "col": "#9aa6ae"}
    plt.rcParams["hatch.linewidth"] = 0.5
    fig, ax = plt.subplots(figsize=(5.0, 4.8))

    verts = [(-base / 2, 0), (base / 2, 0), (0, altura)]
    ax.add_patch(Polygon(verts, closed=True, facecolor=C["concreto"],
                         edgecolor=C["hatch"], lw=1.4, alpha=0.5, hatch="xxx"))
    yb = altura / 3.0                     # baricentro
    ax.add_patch(Rectangle((-c1 / 2, yb - c2 / 2), c1, c2, facecolor=C["col"],
                           edgecolor="#2b3137", lw=1.2))
    ax.plot(0, yb, "+", color="#2b3137", ms=11, mew=1.3)
    ax.text(0, yb - 0.12 * altura, "columna\n(baricentro)", ha="center",
            va="top", fontsize=8, color="#33404a")
    ax.annotate("", xy=(base / 2, -0.12 * altura), xytext=(-base / 2, -0.12 * altura),
                arrowprops=dict(arrowstyle="<->", color="#334155", lw=1))
    ax.text(0, -0.20 * altura, f"base = {base:.2f} m", ha="center",
            fontsize=8.5, fontweight="bold")
    ax.annotate("", xy=(base / 2 + 0.14 * base, altura),
                xytext=(base / 2 + 0.14 * base, 0),
                arrowprops=dict(arrowstyle="<->", color="#334155", lw=1))
    ax.text(base / 2 + 0.24 * base, altura / 2, f"altura = {altura:.2f} m",
            va="center", ha="center", rotation=90, fontsize=8.5, fontweight="bold")
    ax.set_xlim(-base * 0.90, base * 1.00)
    ax.set_ylim(-0.28 * altura, 1.12 * altura)
    ax.set_aspect("equal")
    ax.set_title("PLANTA TRIANGULAR", fontsize=10, fontweight="bold")
    ax.axis("off")
    fig.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# Memoria específica para tipos con otra forma de resultado (combinada, triangular)
# ---------------------------------------------------------------------------
_TIPO_TITULO = {
    "combinada": "Zapata combinada (dos columnas)",
    "triangular": "Zapata triangular",
}


def _memoria_zapata_especial(datos, resultado, entradas, tipo) -> bytes:
    g = resultado["geometria"]
    geo = resultado["geotecnico"]
    est = resultado["estructural"]

    buf = io.BytesIO()
    titulo = _TIPO_TITULO.get(tipo, "Zapata")
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=2 * cm, rightMargin=2 * cm,
                            topMargin=1.8 * cm, bottomMargin=1.8 * cm,
                            title=f"Memoria de cálculo — {titulo}")
    ss = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=ss["Heading1"], fontName=_FONT_B, fontSize=15, textColor=TINTA, spaceAfter=2)
    h2 = ParagraphStyle("h2", parent=ss["Heading2"], fontName=_FONT_B, fontSize=11.5, textColor=VERDE, spaceBefore=12, spaceAfter=5)
    p = ParagraphStyle("p", parent=ss["BodyText"], fontName=_FONT, fontSize=9, textColor=TINTA, leading=13)
    small = ParagraphStyle("small", parent=p, fontName=_FONT, fontSize=8, textColor=GRIS)
    el = []

    fc = float(entradas.get("fc", 21) or 21)
    fy = float(entradas.get("fy", 420) or 420)
    Df = float(entradas.get("Df", 1.5) or 1.5)

    el.append(Paragraph(f"Memoria de cálculo — {titulo}", h1))
    el.append(Paragraph("Dimensionamiento geotécnico y diseño estructural · NSR-10 / ACI 318", small))
    el.append(HRFlowable(width="100%", thickness=1, color=VERDE, spaceBefore=6, spaceAfter=6))
    el.append(_tabla([
        ["Proyecto", getattr(datos, "proyecto", "") or "—", "Fecha", date.today().isoformat()],
        ["Ingeniero", getattr(datos, "ingeniero", "") or "—",
         "Ubicación", getattr(datos, "ubicacion", "") or "—"],
    ], [2.6 * cm, 6.5 * cm, 2.2 * cm, 5.0 * cm], header=False))

    def _cortante_ok(): return _ok(est.get("cumple_cortante", False))

    if tipo == "combinada":
        el.append(Paragraph("1. Geometría", h2))
        el.append(_tabla([
            ["Ancho B", f"{g['B_m']:.2f} m", "Largo L", f"{g['L_m']:.2f} m"],
            ["Espesor h", f"{g['h_m']:.2f} m", "Peralte d", f"{g['d_m']:.3f} m"],
            ["Columna 1", f"{g['c1a_m']*100:.0f}×{g['c2a_m']*100:.0f} cm (x={g['x1_col_m']:.2f} m)",
             "Columna 2", f"{g['c1b_m']*100:.0f}×{g['c2b_m']*100:.0f} cm (x={g['x2_col_m']:.2f} m)"],
            ["Separación", f"{g['separacion_m']:.2f} m", "Profundidad Df", f"{Df:.2f} m"],
        ], [3.2 * cm, 4.0 * cm, 3.2 * cm, 4.0 * cm], header=False))

        el.append(Spacer(1, 6))
        el.append(_fig_to_image(dibujar_combinada(resultado, entradas), 14.0, 13.1))
        el.append(Paragraph("Esquema en planta y diagrama de momentos de la viga "
                            "longitudinal (M⁺ en voladizos, M⁻ entre columnas).", small))

        el.append(Paragraph("2. Dimensionamiento geotécnico", h2))
        el.append(Paragraph("La planta se dimensiona para que la resultante de las cargas "
                            "coincida con el centroide (presión de contacto ~uniforme).", p))
        el.append(_tabla([
            ["Resultante (servicio)", f"{_tf(geo['resultante_servicio_kN']):.1f} tonf",
             "Excentricidad", f"{geo['excentricidad_m']:.3f} m"],
            ["q máx", f"{_tm(geo['q_max_kPa']):.1f} tonf/m²", "q mín", f"{_tm(geo['q_min_kPa']):.1f} tonf/m²"],
            ["q admisible", f"{_tm(geo['q_adm_kPa']):.1f} tonf/m²", "Relación D/C", f"{geo['ratio']}"],
        ], [3.4 * cm, 3.8 * cm, 3.4 * cm, 3.8 * cm], header=False))
        el.append(Paragraph(f"<b>Verificación geotécnica: {_ok(geo['cumple'])}</b>", p))

        el.append(Paragraph("3. Diseño estructural (viga longitudinal)", h2))
        el.append(Paragraph(f"Presión de diseño q<sub>u</sub> = {_tm(est['qu_kPa']):.1f} tonf/m². "
                            "La zapata trabaja como viga en la dirección L.", p))
        el.append(_tabla([
            ["Momento máx. (+)", f"{_tm(est['M_pos_kNm']):.1f} tonf·m", "en x", f"{est['x_M_pos_m']:.2f} m"],
            ["Momento máx. (−)", f"{_tm(est['M_neg_kNm']):.1f} tonf·m", "en x", f"{est['x_M_neg_m']:.2f} m"],
            ["Cortante V máx", f"{_tf(est['V_max_kN']):.1f} tonf", "φVc (viga)", f"{_tf(est['phiVc_long_kN']):.1f} tonf"],
        ], [3.4 * cm, 3.8 * cm, 3.4 * cm, 3.8 * cm], header=False))

        el.append(Spacer(1, 4))
        el.append(Paragraph("3.1 Punzonamiento por columna", p))
        p1, p2 = est["punzonamiento_col1"], est["punzonamiento_col2"]
        el.append(_tabla([
            ["Columna", "Vu (tonf)", "φVc (tonf)", "D/C", "Estado"],
            ["Columna 1", f"{_tf(p1['Vu_kN']):.1f}", f"{_tf(p1['phiVc_kN']):.1f}", f"{p1['ratio']}",
             "cumple" if p1["cumple"] else "no cumple"],
            ["Columna 2", f"{_tf(p2['Vu_kN']):.1f}", f"{_tf(p2['phiVc_kN']):.1f}", f"{p2['ratio']}",
             "cumple" if p2["cumple"] else "no cumple"],
        ], [4.0 * cm, 2.8 * cm, 2.8 * cm, 2.0 * cm, 2.6 * cm]))
        if p1.get("vu_momento_kPa", 0) > 0.1 or p2.get("vu_momento_kPa", 0) > 0.1:
            el.append(Paragraph(
                "Con transferencia de momento (γv, C.11.11.7): col.1 D/C = "
                f"{p1.get('ratio_momento')} → {_ok(p1.get('cumple_momento', True))} · "
                f"col.2 D/C = {p2.get('ratio_momento')} → {_ok(p2.get('cumple_momento', True))}.", p))
        tr1, tr2 = est.get("transferencia_col1"), est.get("transferencia_col2")
        if tr1 and tr2:
            el.append(Spacer(1, 3))
            el.append(Paragraph(
                "Transferencia de carga columna→zapata (C.15.8): col.1 aplastamiento "
                f"D/C = {tr1['ratio']} {_ok(tr1['cumple_aplastamiento'])}, dowels "
                f"{tr1['n_dowels']} Ø{tr1['db_dowel_mm']:.1f} {_ok(tr1['cumple_dowels'])} · "
                f"col.2 aplastamiento D/C = {tr2['ratio']} {_ok(tr2['cumple_aplastamiento'])}, "
                f"dowels {tr2['n_dowels']} Ø{tr2['db_dowel_mm']:.1f} {_ok(tr2['cumple_dowels'])}.", p))

        el.append(Spacer(1, 4))
        el.append(Paragraph("3.2 Flexión y refuerzo", p))
        def _row(f, nom):
            gob = " (mín.)" if f["gobierna_minimo"] else ""
            return [nom, f"{_tm(f['Mu_kNm']):.2f}", f"{f['As_cm2']:.1f}{gob}",
                    f"{f['n_barras']} Ø{f['db_mm']:.1f} @ {f['sep_cm']:.0f} cm"]
        el.append(_tabla([
            ["Refuerzo", "Mu (tonf·m)", "As (cm²)", "Distribución"],
            _row(est["flexion_long_inferior"], "Longitudinal inferior (M⁺)"),
            _row(est["flexion_long_superior"], "Longitudinal superior (M⁻)"),
            _row(est["flexion_transversal_col1"], "Transversal columna 1"),
            _row(est["flexion_transversal_col2"], "Transversal columna 2"),
        ], [5.2 * cm, 2.8 * cm, 2.6 * cm, 3.6 * cm]))

    else:  # triangular
        el.append(Paragraph("1. Geometría", h2))
        el.append(_tabla([
            ["Base", f"{g['base_m']:.2f} m", "Altura", f"{g['altura_m']:.2f} m"],
            ["Área", f"{g['area_m2']:.2f} m²", "Lado equivalente", f"{g['lado_equivalente_m']:.2f} m"],
            ["Espesor h", f"{g['h_m']:.2f} m", "Peralte d", f"{g['d_m']:.3f} m"],
        ], [3.2 * cm, 4.0 * cm, 3.2 * cm, 4.0 * cm], header=False))

        el.append(Spacer(1, 6))
        el.append(_fig_to_image(dibujar_triangular(resultado, entradas), 10.5, 10.1))

        el.append(Paragraph("2. Dimensionamiento geotécnico", h2))
        el.append(_tabla([
            ["P total (servicio)", f"{_tf(geo['P_total_servicio_kN']):.1f} tonf",
             "q uniforme", f"{_tm(geo['q_uniforme_kPa']):.1f} tonf/m²"],
            ["q máx", f"{_tm(geo['q_max_kPa']):.1f} tonf/m²", "q admisible", f"{_tm(geo['q_adm_kPa']):.1f} tonf/m²"],
        ], [3.4 * cm, 3.8 * cm, 3.4 * cm, 3.8 * cm], header=False))
        el.append(Paragraph(f"<b>Verificación geotécnica: {_ok(geo['cumple'])}</b>", p))

        el.append(Paragraph("3. Diseño estructural (aprox. cuadrada equivalente)", h2))
        pz, cu, fx = est["punzonamiento"], est["una_via"], est["flexion"]
        el.append(_tabla([
            ["Verificación", "Vu (tonf)", "φVc (tonf)", "D/C", "Estado"],
            ["Punzonamiento", f"{_tf(pz['Vu_kN']):.1f}", f"{_tf(pz['phiVc_kN']):.1f}", f"{pz['ratio']}",
             "cumple" if pz["cumple"] else "no cumple"],
            ["Cortante una vía", f"{_tf(cu['Vu_kN']):.1f}", f"{_tf(cu['phiVc_kN']):.1f}", f"{cu['ratio']}",
             "cumple" if cu["cumple"] else "no cumple"],
        ], [4.0 * cm, 2.8 * cm, 2.8 * cm, 2.0 * cm, 2.6 * cm]))
        el.append(Spacer(1, 4))
        gob = " (mín.)" if fx["gobierna_minimo"] else ""
        el.append(_tabla([
            ["Flexión", "Mu (tonf·m)", "As (cm²)", "Refuerzo"],
            ["Ambas direcciones", f"{_tm(fx['Mu_kNm']):.2f}", f"{fx['As_cm2']:.1f}{gob}",
             f"{fx['n_barras']} Ø{fx['db_mm']:.1f} @ {fx['sep_cm']:.0f} cm"],
        ], [4.2 * cm, 2.8 * cm, 2.8 * cm, 4.0 * cm]))
        tr = est.get("transferencia")
        if tr:
            el.append(Spacer(1, 3))
            el.append(Paragraph(
                "Transferencia de carga columna→zapata (C.15.8): aplastamiento "
                f"D/C = {tr['ratio']} {_ok(tr['cumple_aplastamiento'])}, dowels "
                f"{tr['n_dowels']} Ø{tr['db_dowel_mm']:.1f} {_ok(tr['cumple_dowels'])}.", p))

    el.append(Spacer(1, 5))
    el.append(Paragraph(f"<b>Verificación al cortante: {_cortante_ok()}</b>", p))
    for a in resultado.get("avisos", []):
        el.append(Paragraph(f"⚠ {a}", small))
    el.append(Spacer(1, 14))
    el.append(HRFlowable(width="100%", thickness=0.5, color=GRIS_CLARO))
    el.append(Paragraph(f"Generado por CimX · {titulo} · NSR-10 / ACI 318", small))
    doc.build(el)
    return buf.getvalue()
