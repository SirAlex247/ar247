"""Memoria de cálculo (PDF) de la cimentación de máquina (ACI 351.3R).

Reutiliza el estilo del reporte de zapatas. Incluye la tabla de los cuatro
modos (rigidez, frecuencia natural, amortiguamiento, razón de frecuencias y
amplitud) y un diagrama de sintonización (fₙ de cada modo frente a la frecuencia
de operación, con la banda de resonancia sombreada).
"""
from __future__ import annotations

import io
from datetime import date

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                HRFlowable)

from .zapata_reporte import (VERDE, GRIS, GRIS_CLARO, TINTA, _FONT, _FONT_B,
                             _tf, _tm, _tabla, _ok, _fig_to_image)


def dibujar_sintonizacion(res) -> "plt.Figure":
    """Barras de fₙ por modo con la frecuencia de operación y la banda de
    resonancia (0.8–1.2·fₙ) sombreada alrededor de cada barra."""
    modos = res["modos"]
    f_op = res["excitacion"]["f_operacion_Hz"]
    nombres = [m["nombre"].split(" (")[0] for m in modos]
    fns = [m["fn_Hz"] for m in modos]
    seps = [m["separado"] for m in modos]
    excs = [m.get("excitado", True) for m in modos]

    C_ok, C_bad, C_off, C_op = "#2f6f4f", "#b4451f", "#8a938c", "#1f4e79"
    fig, ax = plt.subplots(figsize=(6.0, 3.4))
    x = range(len(modos))
    for i, (fn, ok, exc) in enumerate(zip(fns, seps, excs)):
        color = C_off if not exc else (C_ok if ok else C_bad)
        # banda de resonancia del modo (0.8–1.2 fn) como referencia vertical
        ax.bar(i, fn, width=0.5, color=color, alpha=0.85, zorder=3)
        ax.text(i, fn + max(fns) * 0.02, f"{fn:.1f}", ha="center", va="bottom",
                fontsize=8, fontweight="bold", color="#22303a")
        # banda ±20% alrededor de fn
        ax.add_patch(plt.Rectangle((i - 0.5, 0.8 * fn), 1.0, 0.4 * fn,
                                   facecolor="#c99", alpha=0.18, zorder=1))
    ax.axhline(f_op, color=C_op, lw=1.6, ls="--", zorder=4)
    ax.text(len(modos) - 0.5, f_op, f"  f_op = {f_op:.1f} Hz", color=C_op,
            va="bottom", ha="right", fontsize=8.5, fontweight="bold")
    ax.set_xticks(list(x))
    ax.set_xticklabels(nombres, fontsize=8.5)
    ax.set_ylabel("frecuencia [Hz]", fontsize=9)
    ax.set_title("SINTONIZACIÓN — fₙ por modo vs. frecuencia de operación",
                 fontsize=10, fontweight="bold")
    ax.grid(True, axis="y", ls=":", lw=0.4, alpha=0.5)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    ax.set_ylim(0, max(fns + [f_op]) * 1.18)
    fig.tight_layout()
    return fig


def generar_memoria_maquina(datos, resultado, entradas) -> bytes:
    g = resultado["geometria"]
    ms = resultado["masas"]
    su = resultado["suelo"]
    ex = resultado["excitacion"]
    geo = resultado["geotecnico"]

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm,
                            topMargin=1.8 * cm, bottomMargin=1.8 * cm,
                            title="Memoria — Cimentación de máquina (ACI 351.3R)")
    ss = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=ss["Heading1"], fontName=_FONT_B, fontSize=15, textColor=TINTA, spaceAfter=2)
    h2 = ParagraphStyle("h2", parent=ss["Heading2"], fontName=_FONT_B, fontSize=11.5, textColor=VERDE, spaceBefore=12, spaceAfter=5)
    p = ParagraphStyle("p", parent=ss["BodyText"], fontName=_FONT, fontSize=9, textColor=TINTA, leading=13)
    small = ParagraphStyle("small", parent=p, fontName=_FONT, fontSize=8, textColor=GRIS)
    el = []

    el.append(Paragraph("Memoria de cálculo — Cimentación de máquina", h1))
    el.append(Paragraph("Bloque rígido · método de parámetros concentrados "
                        "(semiespacio elástico, Richart) · ACI 351.3R", small))
    el.append(HRFlowable(width="100%", thickness=1, color=VERDE, spaceBefore=6, spaceAfter=6))
    el.append(_tabla([
        ["Proyecto", getattr(datos, "proyecto", "") or "—", "Fecha", date.today().isoformat()],
        ["Ingeniero", getattr(datos, "ingeniero", "") or "—",
         "Ubicación", getattr(datos, "ubicacion", "") or "—"],
    ], [2.6 * cm, 6.5 * cm, 2.2 * cm, 5.0 * cm], header=False))

    # 1. Datos
    el.append(Paragraph("1. Bloque, máquina y suelo", h2))
    el.append(_tabla([
        ["Bloque B×L×h", f"{g['B_m']:.2f} × {g['L_m']:.2f} × {g['h_m']:.2f} m",
         "Peso bloque", f"{_tf(ms['peso_bloque_kN']):.1f} tonf"],
        ["Peso máquina", f"{_tf(ms['peso_maquina_kN']):.1f} tonf", "Rel. masa bloque/máq.",
         f"{ms['relacion_masa_bloque_maquina']:.2f}×"],
        ["CG máquina (sobre base)", f"{g['hcg_maquina_m']:.2f} m", "Peso total", f"{_tf(ms['peso_total_kN']):.1f} tonf"],
        ["Suelo G / Vs", f"{su['G_MPa']:.1f} MPa / {su['Vs_m_s']:.0f} m/s", "ν / ρ",
         f"{su['nu']} / {su['rho_kg_m3']:.0f} kg/m³"],
        ["Velocidad de operación", f"{ex['rpm']:.0f} rpm ({ex['f_operacion_Hz']:.2f} Hz)",
         "Fuerza de desbalance F₀", f"{_tf(ex['F0_kN']):.2f} tonf"],
    ], [4.2 * cm, 4.0 * cm, 4.0 * cm, 3.4 * cm], header=False))

    # Figura de sintonización
    el.append(Spacer(1, 6))
    el.append(_fig_to_image(dibujar_sintonizacion(resultado), 15.0, 8.5))

    # 2. Respuesta dinámica por modo
    el.append(Paragraph("2. Respuesta dinámica por modo", h2))
    el.append(Paragraph(
        "Para cada modo: rigidez del resorte del suelo k, frecuencia natural fₙ, "
        "amortiguamiento geométrico D, razón de frecuencias r = f/fₙ y amplitud "
        "de vibración en régimen permanente. Sin resonancia si r ≤ 0.8 o r ≥ 1.2.", p))
    filas = [["Modo", "fₙ (Hz)", "D", "r = f/fₙ", "Amplitud (µm)", "Sintonización"]]
    for md in resultado["modos"]:
        filas.append([md["nombre"], f"{md['fn_Hz']:.2f}", f"{md['amortiguamiento_D']:.3f}",
                      f"{md['razon_frec']:.2f}", f"{md['amplitud_um']:.2f}",
                      md["estado_resonancia"]])
    el.append(_tabla(filas, [3.6 * cm, 2.2 * cm, 1.8 * cm, 2.0 * cm, 2.8 * cm, 3.2 * cm]))
    el.append(Spacer(1, 3))
    el.append(Paragraph(
        f"Amplitud máxima = {resultado['amplitud_max_um']:.1f} µm · admisible = "
        f"{resultado['amplitud_admisible_um']:.0f} µm → "
        f"<b>{_ok(resultado['amplitud_ok'])}</b>. "
        f"Separación de resonancia en los 4 modos: <b>{_ok(resultado['resonancia_ok'])}</b>.", p))

    # 3. Estática
    el.append(Paragraph("3. Presión estática de contacto", h2))
    if geo["q_adm_kPa"]:
        el.append(_tabla([
            ["Presión estática", f"{_tm(geo['q_estatica_kPa']):.1f} tonf/m²",
             "q admisible", f"{_tm(geo['q_adm_kPa']):.1f} tonf/m²"],
            ["Relación D/C", f"{geo['ratio']}", "Estado", "cumple" if geo["cumple"] else "no cumple"],
        ], [3.8 * cm, 3.6 * cm, 3.4 * cm, 3.6 * cm], header=False))
    else:
        el.append(Paragraph(f"Presión estática = {_tm(geo['q_estatica_kPa']):.1f} tonf/m² "
                            "(define q_adm para verificar).", p))

    el.append(Spacer(1, 5))
    el.append(Paragraph(f"<b>Resultado global: {_ok(resultado.get('cumple', False))}</b> "
                        "(sin resonancia, amplitud y presión admisibles).", p))
    for a in resultado.get("avisos", []):
        el.append(Paragraph(f"⚠ {a}", small))
    el.append(Spacer(1, 12))
    el.append(HRFlowable(width="100%", thickness=0.5, color=GRIS_CLARO))
    el.append(Paragraph("Generado por CimX · Cimentación de máquina · ACI 351.3R", small))
    doc.build(el)
    return buf.getvalue()
