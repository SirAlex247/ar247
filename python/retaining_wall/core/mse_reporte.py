"""Memoria de cálculo (PDF) y dibujo de un muro de tierra armada / MSE.

Reutiliza el estilo del reporte de zapatas. Incluye el esquema del muro con las
capas de refuerzo y la superficie de falla interna, la tabla de estabilidad
interna capa a capa (Tmax, rotura y arrancamiento) y la de estabilidad externa.
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
                                HRFlowable)

from .zapata_reporte import (VERDE, GRIS, GRIS_CLARO, TINTA, _FONT, _FONT_B,
                             _tf, _tabla, _ok, _fig_to_image)


# ---------------------------------------------------------------------------
# Dibujo del muro MSE (matplotlib)
# ---------------------------------------------------------------------------
C_REF = "#c9b079"       # relleno reforzado
C_RET = "#d9c39a"       # relleno retenido
C_CIM = "#a98d67"       # cimentación
C_FACE = "#707a86"      # panel de fachada
C_STEEL = "#c0392b"     # refuerzo
C_FALLA = "#1d4ed8"     # superficie de falla interna


def dibujar_mse(res) -> "plt.Figure":
    """Esquema del muro de tierra armada: bloque reforzado, capas de refuerzo,
    superficie de falla interna, relleno retenido y sobrecarga."""
    H, L = res.H, res.L
    fig, ax = plt.subplots(figsize=(7.2, 5.2))

    x_min = -0.25 * L
    x_max = L + 0.9 * L
    y_min = -0.18 * H
    y_max = H + 0.28 * H

    # Cimentación
    ax.add_patch(Rectangle((x_min, y_min), x_max - x_min, -y_min,
                           facecolor=C_CIM, alpha=0.5, edgecolor="none", zorder=1))
    # Relleno retenido (detrás del bloque)
    ax.add_patch(Rectangle((L, 0), x_max - L, H, facecolor=C_RET, alpha=0.55,
                           edgecolor="#8a7a52", lw=1.0, zorder=2))
    # Bloque reforzado
    ax.add_patch(Rectangle((0, 0), L, H, facecolor=C_REF, alpha=0.75,
                           edgecolor="#8a7a52", lw=1.2, zorder=3))
    # Panel de fachada (cara izquierda)
    ax.add_patch(Rectangle((-0.06 * L, 0), 0.06 * L, H, facecolor=C_FACE,
                           edgecolor="#333b45", lw=1.0, zorder=5))

    # Capas de refuerzo (líneas horizontales) y su parte activa/resistente
    for c in res.capas:
        y = H - c.z
        ax.plot([0, L], [y, y], color=C_STEEL, lw=1.3, zorder=6, alpha=0.85)

    # Superficie de falla interna (a través de los La de cada capa + extremos)
    pts = [(0.0, 0.0)]
    for c in sorted(res.capas, key=lambda k: k.z, reverse=True):
        pts.append((c.La, H - c.z))
    pts.append((res.capas[0].La if res.capas else 0.0, H))
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    ax.plot(xs, ys, color=C_FALLA, lw=2.2, ls="--", zorder=7,
            label="Superficie de falla interna")
    ax.fill_betweenx(ys, 0, xs, color=C_FALLA, alpha=0.07, zorder=4)

    # Sobrecarga
    q = res.parametros.get("sobrecarga", 0.0)
    if q and q > 0:
        for xf in [x_min + (x_max - x_min) * k / 12 for k in range(13)]:
            ax.annotate("", xy=(xf, H), xytext=(xf, H + 0.16 * H),
                        arrowprops=dict(arrowstyle="->", color="#7a3", lw=1.0))
        ax.text((x_max + L) / 2, H + 0.19 * H, f"q = {q:.0f} kPa",
                color="#5a7a2a", fontsize=9, ha="center", fontweight="bold")

    # Cotas
    ax.annotate("", xy=(0, -0.10 * H), xytext=(L, -0.10 * H),
                arrowprops=dict(arrowstyle="<->", color="#1d4ed8", lw=1.1))
    ax.text(L / 2, -0.145 * H, f"L = {L:.2f} m", color="#1d4ed8", ha="center",
            fontsize=9, fontweight="bold")
    ax.annotate("", xy=(-0.14 * L, 0), xytext=(-0.14 * L, H),
                arrowprops=dict(arrowstyle="<->", color="#1d4ed8", lw=1.1))
    ax.text(-0.19 * L, H / 2, f"H = {H:.2f} m", color="#1d4ed8", va="center",
            ha="center", rotation=90, fontsize=9, fontweight="bold")

    ax.text(L / 2, H * 0.5, f"{res.n_capas} capas\n@ {res.Sv:.2f} m",
            ha="center", va="center", fontsize=8.5, color="#5b4a22", alpha=0.8)
    ax.text(L + (x_max - L) / 2, H * 0.5, "relleno\nretenido", ha="center",
            va="center", fontsize=8.5, color="#6b5a34", alpha=0.8)

    ax.plot([x_min, x_max], [0, 0], color="black", lw=0.8, ls="--", alpha=0.4)
    ax.set_xlim(x_min, x_max)
    ax.set_ylim(y_min, y_max)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel("x (m)")
    ax.set_ylabel("y (m)")
    tipo = "geosintético" if res.tipo_refuerzo != "metalico" else "metálico"
    ax.set_title(f"Muro de tierra armada (MSE) — refuerzo {tipo}",
                 fontsize=12, fontweight="bold")
    ax.legend(loc="upper right", fontsize=8.5, framealpha=0.9)
    ax.grid(True, alpha=0.2, ls=":")
    fig.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# Memoria PDF
# ---------------------------------------------------------------------------
def generar_memoria_mse(datos, resultado, entradas) -> bytes:
    res = resultado
    ext = res.externa
    rs = res.resumen

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm,
                            topMargin=1.8 * cm, bottomMargin=1.8 * cm,
                            title="Memoria — Muro de tierra armada (MSE)")
    ss = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=ss["Heading1"], fontName=_FONT_B, fontSize=15, textColor=TINTA, spaceAfter=2)
    h2 = ParagraphStyle("h2", parent=ss["Heading2"], fontName=_FONT_B, fontSize=11.5, textColor=VERDE, spaceBefore=12, spaceAfter=5)
    p = ParagraphStyle("p", parent=ss["BodyText"], fontName=_FONT, fontSize=9, textColor=TINTA, leading=13)
    small = ParagraphStyle("small", parent=p, fontName=_FONT, fontSize=8, textColor=GRIS)
    el = []

    el.append(Paragraph("Memoria de cálculo — Muro de tierra armada (MSE)", h1))
    el.append(Paragraph("Método simplificado FHWA (NHI-10-024) / AASHTO · "
                        "estabilidad interna (rotura y arrancamiento) y externa", small))
    el.append(HRFlowable(width="100%", thickness=1, color=VERDE, spaceBefore=6, spaceAfter=6))
    el.append(_tabla([
        ["Proyecto", getattr(datos, "proyecto", "") or "—", "Fecha", date.today().isoformat()],
        ["Ingeniero", getattr(datos, "ingeniero", "") or "—",
         "Ubicación", getattr(datos, "ubicacion", "") or "—"],
    ], [2.6 * cm, 6.5 * cm, 2.2 * cm, 5.0 * cm], header=False))

    # 1. Datos
    pr = res.parametros
    tipo = "geosintético (extensible)" if res.tipo_refuerzo != "metalico" else "metálico (inextensible)"
    el.append(Paragraph("1. Geometría y materiales", h2))
    el.append(_tabla([
        ["Altura H", f"{res.H:.2f} m", "Longitud refuerzo L", f"{res.L:.2f} m"],
        ["Espaciamiento Sv", f"{res.Sv:.2f} m", "Nº de capas", f"{res.n_capas}"],
        ["Tipo de refuerzo", tipo, "Ta admisible", f"{pr['Ta']:.1f} kN/m"],
        ["Relleno reforzado", f"γ={pr['gamma_r']:.1f} kN/m³, φ={pr['phi_r']:.0f}°",
         "Relleno retenido", f"γ={pr['gamma_b']:.1f} kN/m³, φ={pr['phi_b']:.0f}°"],
        ["Cimentación", f"γ={pr['gamma_f']:.1f} kN/m³, φ={pr['phi_f']:.0f}°, c={pr['c_f']:.0f} kPa",
         "Sobrecarga", f"{pr['sobrecarga']:.1f} kPa"],
        ["F* (arrancamiento)", f"{pr['F_pullout']:.3f}", "α · Rc", f"{pr['alpha']:.2f} · {pr['Rc']:.2f}"],
    ], [4.2 * cm, 4.0 * cm, 4.0 * cm, 3.4 * cm], header=False))

    el.append(Spacer(1, 6))
    el.append(_fig_to_image(dibujar_mse(res), 14.5, 10.5))

    # 2. Estabilidad interna
    el.append(Paragraph("2. Estabilidad interna (por capa)", h2))
    el.append(Paragraph(
        "Para cada capa: esfuerzo vertical σ<sub>v</sub>=γ·z+q, coeficiente K<sub>r</sub>, "
        "tensión máxima T<sub>max</sub>=σ<sub>h</sub>·S<sub>v</sub>, verificación de rotura "
        "(T<sub>a</sub>/T<sub>max</sub>) y de arrancamiento (P<sub>r</sub>/T<sub>max</sub> ≥ "
        f"{pr['objetivos']['pullout']:.1f}).", p))
    filas = [["#", "z (m)", "σv (kPa)", "Kr", "Tmax (kN/m)", "Le (m)",
              "FS rot.", "FS pull.", "Estado"]]
    # Submuestreo si hay muchas capas
    capas = res.capas
    paso = max(1, len(capas) // 16)
    for c in capas[::paso]:
        okc = c.cumple_rotura and c.cumple_pullout
        filas.append([str(c.i), f"{c.z:.2f}", f"{c.sigma_v:.1f}", f"{c.Kr:.3f}",
                      f"{c.Tmax:.2f}", f"{c.Le:.2f}", f"{c.FS_rotura:.2f}",
                      f"{c.FS_pullout:.2f}", "OK" if okc else "REVISAR"])
    el.append(_tabla(filas, [1.0*cm, 1.4*cm, 1.9*cm, 1.5*cm, 2.4*cm, 1.6*cm,
                             1.6*cm, 1.7*cm, 2.0*cm]))
    el.append(Spacer(1, 3))
    el.append(Paragraph(
        f"FS rotura mínimo = {rs['FS_rotura_min']:.2f} (capa {rs['capa_critica_rotura']}), "
        f"FS arrancamiento mínimo = {rs['FS_pullout_min']:.2f} (capa {rs['capa_critica_pullout']}) → "
        f"<b>{_ok(rs['interna_ok'])}</b>.", p))

    # 3. Estabilidad externa
    el.append(Paragraph("3. Estabilidad externa (bloque como muro de gravedad)", h2))
    el.append(_tabla([
        ["Verificación", "Valor", "Requerido", "Estado"],
        ["Deslizamiento (FS)", f"{ext['FS_deslizamiento']:.2f}",
         f"{pr['objetivos']['deslizamiento']:.1f}", "CUMPLE" if ext['cumple_deslizamiento'] else "NO CUMPLE"],
        ["Volcamiento (FS)", f"{ext['FS_volcamiento']:.2f}",
         f"{pr['objetivos']['volcamiento']:.1f}", "CUMPLE" if ext['cumple_volcamiento'] else "NO CUMPLE"],
        ["Excentricidad e (m)", f"{ext['e_m']:.3f}", f"≤ {ext['e_max_m']:.3f}",
         "CUMPLE" if ext['cumple_excentricidad'] else "NO CUMPLE"],
        ["Capacidad portante (FS)", f"{ext['FS_capacidad']:.2f}",
         f"{pr['objetivos']['capacidad']:.1f}", "CUMPLE" if ext['cumple_capacidad'] else "NO CUMPLE"],
    ], [5.2 * cm, 3.5 * cm, 3.5 * cm, 3.4 * cm]))
    el.append(Spacer(1, 3))
    el.append(Paragraph(
        f"Empuje activo del relleno retenido P<sub>a</sub> = {_tf(ext['Pa_kN']):.1f} tonf/m; "
        f"peso del bloque W = {_tf(ext['W_kN']):.1f} tonf/m; "
        f"q<sub>ref</sub> = {ext['q_referencia_kPa']:.0f} kPa vs q<sub>ult</sub> = "
        f"{ext['q_ultimo_kPa']:.0f} kPa.", p))

    el.append(Spacer(1, 6))
    el.append(Paragraph(f"<b>Resultado global: {_ok(rs['cumple_global'])}</b> "
                        "(estabilidad interna y externa).", p))
    for a in res.avisos:
        el.append(Paragraph(f"⚠ {a}", small))
    el.append(Spacer(1, 12))
    el.append(HRFlowable(width="100%", thickness=0.5, color=GRIS_CLARO))
    el.append(Paragraph("Generado por CimX · Muro de tierra armada (MSE) · FHWA/AASHTO", small))
    doc.build(el)
    return buf.getvalue()
