"""Memoria de cálculo (PDF) y dibujo de un muro anclado (tieback wall).

Reutiliza el estilo del reporte de zapatas. Incluye el esquema de la pantalla
con los anclajes (longitud libre + bulbo), la envolvente de presión aparente y
la cuña de falla; la tabla de cargas y longitudes por fila de anclaje; y el
resumen de diseño.
"""
from __future__ import annotations

import io
import math
from datetime import date

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Polygon

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                HRFlowable)

from .zapata_reporte import (VERDE, GRIS, GRIS_CLARO, TINTA, _FONT, _FONT_B,
                             _tf, _tabla, _ok, _fig_to_image)


C_SOIL = "#d9c39a"
C_SOIL_LN = "#8a7a52"
C_WALL = "#707a86"
C_ANCHOR = "#c0392b"
C_BOND = "#8e44ad"
C_PRES = "#1d4ed8"
C_WEDGE = "#2e7d32"


def dibujar_muro_anclado(res) -> "plt.Figure":
    """Esquema de la pantalla anclada: anclajes (libre + bulbo), envolvente de
    presión aparente y cuña de falla activa."""
    H = res.H
    phi = res.parametros.get("phi", 30.0)
    theta = math.radians(res.parametros.get("inclinacion_grados", 15.0))

    fig, ax = plt.subplots(figsize=(7.6, 5.6))

    # Extensión de dibujo
    x_ret = max(a.L_total * math.cos(theta) for a in res.anclajes) + 1.0 if res.anclajes else 0.7 * H
    x_ret = max(x_ret, 0.8 * H)
    x_min = -0.62 * H
    x_max = x_ret + 0.6
    y_min = -0.12 * H
    y_max = H + 0.20 * H

    # Suelo retenido (x > 0)
    ax.add_patch(Rectangle((0, 0), x_max, H, facecolor=C_SOIL, alpha=0.5,
                           edgecolor="none", zorder=1))
    # Suelo bajo el fondo de excavación (todo el ancho)
    ax.add_patch(Rectangle((x_min, y_min), x_max - x_min, -y_min,
                           facecolor="#a98d67", alpha=0.4, edgecolor="none", zorder=1))
    ax.plot([0, x_max], [H, H], color=C_SOIL_LN, lw=1.4, zorder=3)   # superficie
    ax.plot([x_min, 0], [0, 0], color=C_SOIL_LN, lw=1.2, zorder=3)   # fondo excav.

    # Pantalla (muro)
    ax.add_patch(Rectangle((-0.05 * H, 0), 0.05 * H, H, facecolor=C_WALL,
                           edgecolor="#333b45", lw=1.2, zorder=6))

    # Cuña de falla activa (desde el pie)
    ang = math.radians(45 + phi / 2.0)
    x_top = H / math.tan(ang)
    ax.plot([0, x_top], [0, H], color=C_WEDGE, lw=1.6, ls="--", zorder=4,
            label="Cuña de falla activa")

    # Anclajes
    for a in res.anclajes:
        y = H - a.z
        # longitud libre (delgada)
        xf = a.Lf * math.cos(theta)
        yf = y - a.Lf * math.sin(theta)
        ax.plot([0, xf], [y, yf], color=C_ANCHOR, lw=1.6, zorder=7)
        # bulbo (grueso)
        xb = xf + a.Lb * math.cos(theta)
        yb = yf - a.Lb * math.sin(theta)
        ax.plot([xf, xb], [yf, yb], color=C_BOND, lw=5.0, alpha=0.8, zorder=7,
                solid_capstyle="round")
        # cabeza del anclaje
        ax.plot([0], [y], marker="o", color=C_ANCHOR, ms=7, zorder=8)
        ax.text(-0.08 * H, y, f"A{a.i}", color=C_ANCHOR, fontsize=9,
                ha="right", va="center", fontweight="bold")

    # Envolvente de presión aparente (a la izquierda, escalada). Reconstruimos
    # la envolvente trapezoidal a partir de p y las posiciones de los anclajes.
    p = res.p_max
    esc = (0.32 * H) / p if p > 0 else 0.0
    zs = [H * k / 60 for k in range(61)]
    z1 = res.parametros["z_anclajes"][0]
    zlast = res.parametros["z_anclajes"][-1]

    def env(z):
        if z <= 0 or z >= H:
            return 0.0
        if z < z1:
            return p * z / z1
        if z <= zlast:
            return p
        return p * (H - z) / (H - zlast) if H > zlast else p

    xs = [-env(z) * esc for z in zs]
    ys = [H - z for z in zs]
    ax.plot(xs, ys, color=C_PRES, lw=1.8, zorder=5, label="Presión aparente")
    ax.fill_betweenx(ys, 0, xs, color=C_PRES, alpha=0.10, zorder=4)
    ax.text(min(xs) - 0.02 * H, H * 0.5, f"p = {p:.0f} kPa", color=C_PRES,
            fontsize=9, ha="right", va="center", rotation=90, fontweight="bold")

    # Cota de H
    ax.annotate("", xy=(-0.52 * H, 0), xytext=(-0.52 * H, H),
                arrowprops=dict(arrowstyle="<->", color="#0f172a", lw=1.0))
    ax.text(-0.57 * H, H / 2, f"H = {H:.1f} m", color="#0f172a", va="center",
            ha="center", rotation=90, fontsize=9, fontweight="bold")

    ax.plot([], [], color=C_BOND, lw=5, label="Bulbo (zona resistente)")
    ax.set_xlim(x_min, x_max)
    ax.set_ylim(y_min, y_max)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel("x (m)")
    ax.set_ylabel("elevación (m)")
    ax.set_title(f"Muro anclado — {res.n_anclajes} fila(s) de anclajes",
                 fontsize=12, fontweight="bold")
    ax.legend(loc="upper right", fontsize=8, framealpha=0.9)
    ax.grid(True, alpha=0.2, ls=":")
    fig.tight_layout()
    return fig


def generar_memoria_muro_anclado(datos, resultado, entradas) -> bytes:
    res = resultado
    pr = res.parametros
    rs = res.resumen

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm,
                            topMargin=1.8 * cm, bottomMargin=1.8 * cm,
                            title="Memoria — Muro anclado")
    ss = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=ss["Heading1"], fontName=_FONT_B, fontSize=15, textColor=TINTA, spaceAfter=2)
    h2 = ParagraphStyle("h2", parent=ss["Heading2"], fontName=_FONT_B, fontSize=11.5, textColor=VERDE, spaceBefore=12, spaceAfter=5)
    p = ParagraphStyle("p", parent=ss["BodyText"], fontName=_FONT, fontSize=9, textColor=TINTA, leading=13)
    small = ParagraphStyle("small", parent=p, fontName=_FONT, fontSize=8, textColor=GRIS)
    el = []

    el.append(Paragraph("Memoria de cálculo — Muro anclado", h1))
    el.append(Paragraph("Método de las presiones aparentes (Terzaghi-Peck / "
                        "FHWA GEC-4) · cargas de anclaje y longitudes de bulbo", small))
    el.append(HRFlowable(width="100%", thickness=1, color=VERDE, spaceBefore=6, spaceAfter=6))
    el.append(_tabla([
        ["Proyecto", getattr(datos, "proyecto", "") or "—", "Fecha", date.today().isoformat()],
        ["Ingeniero", getattr(datos, "ingeniero", "") or "—",
         "Ubicación", getattr(datos, "ubicacion", "") or "—"],
    ], [2.6 * cm, 6.5 * cm, 2.2 * cm, 5.0 * cm], header=False))

    tsuelo = {"arena": "Arena (granular)", "arcilla": "Arcilla"}.get(res.tipo_suelo, res.tipo_suelo)
    el.append(Paragraph("1. Datos y envolvente de presión aparente", h2))
    el.append(_tabla([
        ["Altura excavación H", f"{res.H:.2f} m", "Nº de anclajes", f"{res.n_anclajes}"],
        ["Tipo de suelo", tsuelo, "γ / φ", f"{pr['gamma']:.1f} kN/m³ / {pr['phi']:.0f}°"],
        ["Sobrecarga q", f"{pr['sobrecarga']:.1f} kPa", "Ka", f"{res.Ka:.3f}"],
        ["Presión máx. p", f"{res.p_max:.1f} kPa", "Empuje total", f"{_tf(res.empuje_total):.1f} tonf/m"],
        ["Inclinación anclajes", f"{pr['inclinacion_grados']:.0f}°",
         "Separación horiz. sh", f"{pr['sh']:.2f} m"],
        ["τ bulbo / Ø bulbo", f"{pr['tau_bond']:.0f} kPa / {pr['d_bulbo']:.2f} m",
         "FS arrancamiento", f"{pr['FS_pullout']:.1f}"],
    ], [4.2 * cm, 4.0 * cm, 4.0 * cm, 3.4 * cm], header=False))

    el.append(Spacer(1, 6))
    el.append(_fig_to_image(dibujar_muro_anclado(res), 14.5, 10.6))

    el.append(Paragraph("2. Cargas y longitudes de anclaje", h2))
    el.append(Paragraph(
        "Carga horizontal por metro T<sub>h</sub> (área tributaria de la "
        "envolvente), fuerza de diseño por anclaje T = T<sub>h</sub>·s<sub>h</sub>/cosθ, "
        "longitud de bulbo L<sub>b</sub> = FS·T/(π·d·τ) y longitud libre L<sub>f</sub> "
        "para superar la cuña de falla.", p))
    filas = [["Anclaje", "z (m)", "Th (kN/m)", "T diseño (kN)", "Lb (m)", "Lf (m)", "L total (m)"]]
    for a in res.anclajes:
        filas.append([f"A{a.i}", f"{a.z:.2f}", f"{a.Th:.1f}", f"{a.T_diseno:.0f}",
                      f"{a.Lb:.2f}", f"{a.Lf:.2f}", f"{a.L_total:.2f}"])
    el.append(_tabla(filas, [2.0*cm, 1.8*cm, 2.4*cm, 2.6*cm, 2.2*cm, 2.2*cm, 2.4*cm]))
    el.append(Spacer(1, 4))
    el.append(Paragraph(
        f"Reacción en la base R = {_tf(res.reaccion_base):.1f} tonf/m · "
        f"momento flector máximo aproximado de la pantalla M<sub>máx</sub> ≈ "
        f"{res.momento_max:.1f} kN·m/m (para dimensionar la sección).", p))

    el.append(Spacer(1, 6))
    el.append(Paragraph("3. Resumen de diseño", h2))
    el.append(_tabla([
        ["Magnitud", "Valor"],
        ["Presión aparente máxima", f"{rs['p_max_kPa']:.1f} kPa"],
        ["Empuje total", f"{rs['empuje_total_kN_m']:.1f} kN/m"],
        ["Fuerza de diseño máxima por anclaje", f"{rs['T_diseno_max_kN']:.0f} kN"],
        ["Longitud de bulbo máxima", f"{rs['Lb_max_m']:.2f} m"],
        ["Longitud total máxima de anclaje", f"{rs['L_total_max_m']:.2f} m"],
        ["Momento flector máx. de la pantalla", f"{rs['momento_max_kNm_m']:.1f} kN·m/m"],
    ], [9.0 * cm, 7.0 * cm]))

    for a in res.avisos:
        el.append(Paragraph(f"⚠ {a}", small))
    el.append(Spacer(1, 12))
    el.append(HRFlowable(width="100%", thickness=0.5, color=GRIS_CLARO))
    el.append(Paragraph("Generado por CimX · Muro anclado · presiones aparentes (FHWA GEC-4)", small))
    doc.build(el)
    return buf.getvalue()
