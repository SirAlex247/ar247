"""Memoria de cálculo (PDF) del caisson / pila excavada de gran diámetro.

Reutiliza el estilo del reporte de zapatas. El texto se adapta a la norma
seleccionada (NSR-10 esfuerzos admisibles ↔ CCP-14 LRFD-AASHTO). Incluye un
esquema de la pila con el perfil de suelo, la campana (si existe) y las
resistencias de fuste y punta.
"""
from __future__ import annotations

import io
from datetime import date

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Polygon

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                Image, HRFlowable)

from ..normas import NORMA_CCP14
from .zapata_reporte import (G, VERDE, GRIS, GRIS_CLARO, TINTA, _FONT, _FONT_B,
                             _tf, _tabla, _ok, _fig_to_image)


def _norma_txt(norma):
    if norma == NORMA_CCP14:
        return {
            "titulo": "CCP-14 (LRFD-AASHTO)",
            "sub": "Capacidad axial por estados límite · Sección 10.8 · resistencia "
                   "factorada R_r = φ·Q frente a las cargas mayoradas.",
            "pie": "CCP-14 / AASHTO LRFD (Sección 10.8)",
        }
    return {
        "titulo": "NSR-10 (Título H)",
        "sub": "Capacidad axial por esfuerzos admisibles · Q_adm = Q_últ / FS "
               "frente a la carga de servicio.",
        "pie": "NSR-10 · Título H",
    }


# ---------------------------------------------------------------------------
# Dibujo: elevación de la pila con el perfil de suelo
# ---------------------------------------------------------------------------
def dibujar_caisson(res, entradas) -> "plt.Figure":
    g, cap = res["geometria"], res["capacidad"]
    D, L = g["D_m"], g["L_m"]
    Db = g["D_campana_m"]
    hb = g["altura_campana_m"]
    acamp = g["acampanada"]
    estratos = entradas.get("estratos", []) or []
    nf = float(entradas.get("nivel_freatico", 100.0) or 100.0)

    COL_SUELO = ["#d8bd86", "#c7a86a", "#bfa98b", "#a9bda0", "#c9b79b"]
    C = {"concreto": "#7f8a83", "hatch": "#333b45", "acero": "#d97a2b", "agua": "#4a7fb5"}
    plt.rcParams["hatch.linewidth"] = 0.5

    fig, ax = plt.subplots(figsize=(5.6, 6.8))
    ancho_terreno = max(5.6, 5.0 * D)
    prof_total = max(L + 2.0, L + hb + 1.0)

    # --- estratos de suelo ---
    prof = 0.0
    for i, e in enumerate(estratos):
        esp = float(e.get("espesor", 0.0) or 0.0)
        if esp <= 0:
            continue
        col = COL_SUELO[i % len(COL_SUELO)]
        ax.add_patch(Rectangle((-ancho_terreno / 2, -(prof + esp)), ancho_terreno, esp,
                               facecolor=col, edgecolor="#8a7a52", lw=0.6, alpha=0.55))
        tipo = str(e.get("tipo", "")).lower()
        etq = "arcilla" if tipo.startswith(("arc", "clay")) else "arena"
        par = (f"c_u={e.get('cu')} kPa" if etq == "arcilla" else f"φ={e.get('phi')}°")
        ax.text(-ancho_terreno / 2 + 0.12, -(prof + 0.28),
                f"{e.get('nombre') or etq} · {par}", fontsize=6.8, va="top",
                ha="left", color="#4a4433")
        prof += esp
    # nivel freático
    if 0 < nf < prof_total:
        ax.plot([-ancho_terreno / 2, ancho_terreno / 2], [-nf, -nf],
                color=C["agua"], lw=1.0, ls="--")
        ax.text(ancho_terreno / 2 - 0.1, -nf + 0.12, "N.F.", fontsize=7,
                color=C["agua"], ha="right", va="bottom")
    # terreno
    ax.plot([-ancho_terreno / 2, ancho_terreno / 2], [0, 0], color="#6b5b3e", lw=1.2)

    # --- pila (fuste) ---
    ax.add_patch(Rectangle((-D / 2, -L + (hb if acamp else 0)), D,
                           L - (hb if acamp else 0),
                           facecolor=C["concreto"], edgecolor=C["hatch"],
                           lw=1.3, hatch="xxx", alpha=0.85))
    # campana (trapecio)
    if acamp:
        yb = -L
        ax.add_patch(Polygon([(-D / 2, yb + hb), (D / 2, yb + hb),
                              (Db / 2, yb), (-Db / 2, yb)], closed=True,
                             facecolor=C["concreto"], edgecolor=C["hatch"],
                             lw=1.3, hatch="xxx", alpha=0.85))
    # fricción de fuste (flechas laterales)
    ztop = min(1.5, L * 0.15)
    nfl = 6
    for i in range(nfl):
        yy = -ztop - (L - ztop - (hb if acamp else D)) * (i + 0.5) / nfl
        ax.annotate("", xy=(-D / 2, yy), xytext=(-D / 2 - 0.5, yy),
                    arrowprops=dict(arrowstyle="->", color=C["acero"], lw=0.9))
        ax.annotate("", xy=(D / 2, yy), xytext=(D / 2 + 0.5, yy),
                    arrowprops=dict(arrowstyle="->", color=C["acero"], lw=0.9))
    ax.text(D / 2 + 0.55, -L * 0.5, f"Q_fuste\n{_tf(cap['Q_fuste_kN']):.0f} tonf",
            fontsize=7.5, color="#a2611e", va="center", ha="left")
    # punta (flechas hacia arriba)
    yb = -L
    nb = 5
    for i in range(nb + 1):
        xx = -Db / 2 + Db * i / nb
        ax.annotate("", xy=(xx, yb), xytext=(xx, yb - 0.6),
                    arrowprops=dict(arrowstyle="->", color="#c79a2b", lw=1.0))
    ax.text(0, yb - 0.9, f"Q_punta = {_tf(cap['Q_punta_kN']):.0f} tonf",
            fontsize=7.5, color="#a2611e", ha="center", va="top")

    # cotas D y L
    ax.annotate("", xy=(D / 2, 0.4), xytext=(-D / 2, 0.4),
                arrowprops=dict(arrowstyle="<->", color="#334155", lw=1))
    ax.text(0, 0.6, f"D = {D:.2f} m", ha="center", fontsize=8.5, fontweight="bold")
    ax.annotate("", xy=(-ancho_terreno / 2 - 0.3, -L), xytext=(-ancho_terreno / 2 - 0.3, 0),
                arrowprops=dict(arrowstyle="<->", color="#334155", lw=1))
    ax.text(-ancho_terreno / 2 - 0.55, -L / 2, f"L = {L:.2f} m", va="center",
            ha="center", rotation=90, fontsize=8.5, fontweight="bold")
    if acamp:
        ax.annotate(f"campana Ø{Db:.2f} m", xy=(-Db / 2, yb + hb / 2),
                    xytext=(-Db / 2 - 0.8, yb + hb / 2), fontsize=7, color="#33404a",
                    va="center", ha="right",
                    arrowprops=dict(arrowstyle="->", color="#7a8089", lw=0.7))

    ax.set_xlim(-ancho_terreno / 2 - 1.2, ancho_terreno / 2 + 1.4)
    ax.set_ylim(-prof_total - 0.6, 1.2)
    ax.set_aspect("equal")
    ax.set_title("ELEVACIÓN — pila y perfil de suelo", fontsize=10, fontweight="bold")
    ax.axis("off")
    fig.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# Memoria (PDF)
# ---------------------------------------------------------------------------
def generar_memoria_caisson(datos, resultado, entradas) -> bytes:
    g = resultado["geometria"]
    cap = resultado["capacidad"]
    geo = resultado["geotecnico"]
    est = resultado["estructural"]
    norma = resultado.get("norma", "NSR10")
    N = _norma_txt(norma)
    ccp = (norma == NORMA_CCP14)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=2 * cm, rightMargin=2 * cm,
                            topMargin=1.8 * cm, bottomMargin=1.8 * cm,
                            title=f"Memoria de cálculo — Caisson ({N['titulo']})")
    ss = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=ss["Heading1"], fontName=_FONT_B, fontSize=15, textColor=TINTA, spaceAfter=2)
    h2 = ParagraphStyle("h2", parent=ss["Heading2"], fontName=_FONT_B, fontSize=11.5, textColor=VERDE, spaceBefore=12, spaceAfter=5)
    p = ParagraphStyle("p", parent=ss["BodyText"], fontName=_FONT, fontSize=9, textColor=TINTA, leading=13)
    small = ParagraphStyle("small", parent=p, fontName=_FONT, fontSize=8, textColor=GRIS)
    el = []

    fc = float(entradas.get("fc", 21) or 21)
    fy = float(entradas.get("fy", 420) or 420)

    el.append(Paragraph(f"Memoria de cálculo — Caisson / pila excavada · {N['titulo']}", h1))
    el.append(Paragraph(N["sub"], small))
    el.append(HRFlowable(width="100%", thickness=1, color=VERDE, spaceBefore=6, spaceAfter=6))
    el.append(_tabla([
        ["Proyecto", getattr(datos, "proyecto", "") or "—", "Fecha", date.today().isoformat()],
        ["Ingeniero", getattr(datos, "ingeniero", "") or "—",
         "Ubicación", getattr(datos, "ubicacion", "") or "—"],
    ], [2.6 * cm, 6.5 * cm, 2.2 * cm, 5.0 * cm], header=False))

    # 1. Geometría
    el.append(Paragraph("1. Geometría y perfil de suelo", h2))
    geo_rows = [
        ["Diámetro fuste D", f"{g['D_m']:.2f} m", "Longitud L", f"{g['L_m']:.2f} m"],
        ["Área fuste A_g", f"{g['A_g_m2']:.3f} m²", "Volumen concreto", f"{g['volumen_concreto_m3']:.2f} m³"],
    ]
    if g["acampanada"]:
        geo_rows.append(["Campana Ø", f"{g['D_campana_m']:.2f} m", "Altura campana", f"{g['altura_campana_m']:.2f} m"])
    el.append(_tabla(geo_rows, [3.4 * cm, 3.8 * cm, 3.4 * cm, 3.8 * cm], header=False))

    estratos = entradas.get("estratos", []) or []
    if estratos:
        filas = [["#", "Estrato", "Tipo", "Espesor (m)", "φ (°) / c_u (kPa)", "γ (tonf/m³)"]]
        for i, e in enumerate(estratos, 1):
            tipo = str(e.get("tipo", "")).lower()
            arc = tipo.startswith(("arc", "clay"))
            par = f"c_u={e.get('cu')}" if arc else f"φ={e.get('phi')}"
            filas.append([str(i), str(e.get("nombre", "") or ("arcilla" if arc else "arena")),
                          "arcilla" if arc else "arena", f"{float(e.get('espesor', 0)):.2f}",
                          par, f"{float(e.get('gamma', 18))/G:.2f}"])
        el.append(Spacer(1, 4))
        el.append(_tabla(filas, [1.1 * cm, 3.6 * cm, 2.2 * cm, 2.4 * cm, 3.2 * cm, 2.6 * cm]))

    el.append(Spacer(1, 6))
    el.append(_fig_to_image(dibujar_caisson(resultado, entradas), 11.0, 13.4))

    # 2. Capacidad axial
    el.append(Paragraph("2. Capacidad axial (métodos de pila perforada)", h2))
    el.append(Paragraph(
        "Fricción de fuste por el método β (arenas, O'Neill &amp; Reese) y α "
        "(arcillas); resistencia de punta q<sub>p</sub>·A<sub>base</sub>. Se "
        "excluye de la fricción el tramo superior (1.5 m) y la zona inferior.", p))
    fdet = cap.get("fuste_detalle", [])
    filas_f = [["Estrato", "Tipo", "Desde (m)", "Hasta (m)", "f prom (tonf/m²)", "Q_fuste (tonf)"]]
    for d in fdet:
        filas_f.append([str(d["estrato"]), d["tipo"], f"{d['desde']:.2f}", f"{d['hasta']:.2f}",
                        f"{d['f_prom_kPa']/G:.2f}", f"{_tf(d['Qs_kN']):.1f}"])
    el.append(_tabla(filas_f, [3.2 * cm, 2.0 * cm, 2.2 * cm, 2.2 * cm, 3.0 * cm, 2.6 * cm]))
    el.append(Spacer(1, 3))
    pu = cap["punta"]
    punta_txt = (f"q_p = 9·c_u = {pu['qp_kPa']/G:.1f} tonf/m²" if pu["tipo"] == "arcilla"
                 else f"q_p = σ'_v·N_q = {pu['qp_kPa']/G:.1f} tonf/m² (N_q={pu.get('Nq')})")
    el.append(Paragraph(
        f"Punta ({pu['tipo']}): {punta_txt} sobre A<sub>base</sub> = {cap['A_base_m2']:.3f} m² → "
        f"Q<sub>punta</sub> = {_tf(cap['Q_punta_kN']):.1f} tonf. "
        f"Q<sub>fuste</sub> = {_tf(cap['Q_fuste_kN']):.1f} tonf · "
        f"<b>Q<sub>últ</sub> = {_tf(cap['Q_ult_kN']):.1f} tonf</b>.", p))

    # 3. Verificación geotécnica (por norma)
    el.append(Paragraph("3. Verificación geotécnica", h2))
    if ccp:
        el.append(_tabla([
            ["φ fuste (arena/arcilla)", f"{geo['phi_fuste_arena']} / {geo['phi_fuste_arcilla']}",
             "φ punta", f"{geo['phi_punta']}"],
            ["R fuste (φ·Q_s)", f"{_tf(geo['R_fuste_kN']):.1f} tonf",
             "R punta (φ·Q_p)", f"{_tf(geo['R_punta_kN']):.1f} tonf"],
            ["Resistencia factorada R_r", f"{_tf(geo['R_r_kN']):.1f} tonf",
             "Carga mayorada P_u", f"{_tf(geo['Pu_demanda_kN']):.1f} tonf"],
            ["CDR = R_r / P_u", f"{geo['CDR']}", "Relación P_u/R_r", f"{geo['ratio']}"],
        ], [3.8 * cm, 3.6 * cm, 3.4 * cm, 3.6 * cm], header=False))
        el.append(Paragraph(f"<b>Verificación geotécnica (CCP-14): {_ok(geo['cumple'])}</b> "
                            f"(R_r ≥ P_u).", p))
    else:
        el.append(_tabla([
            ["Q_últ", f"{_tf(geo['Q_ult_kN']):.1f} tonf", "Factor de seguridad FS", f"{geo['FS']}"],
            ["Q_adm = Q_últ/FS", f"{_tf(geo['Q_adm_kN']):.1f} tonf",
             "Carga de servicio", f"{_tf(geo['P_servicio_kN']):.1f} tonf"],
            ["Relación D/C", f"{geo['ratio']}", "", ""],
        ], [3.8 * cm, 3.6 * cm, 3.4 * cm, 3.6 * cm], header=False))
        el.append(Paragraph(f"<b>Verificación geotécnica (NSR-10): {_ok(geo['cumple'])}</b> "
                            f"(Q_adm ≥ P_servicio).", p))

    # 4. Estructural
    el.append(Paragraph("4. Diseño estructural (columna a compresión)", h2))
    tr = est["transversal"]
    tr_txt = (f"espiral ρ_s={tr.get('rho_s')} @ {tr.get('paso_m')} m" if tr["tipo"] == "espiral"
              else f"estribos s_máx={tr.get('sep_max_m')} m")
    el.append(_tabla([
        ["Refuerzo longitudinal", f"{est['n_barras']} Ø{est['db_long_mm']:.1f} mm (ρ={est['cuantia_pct']}%)",
         "Transversal", tr_txt],
        ["φP_n,máx", f"{_tf(est['phiPn_kN']):.1f} tonf", "P_u", f"{_tf(est['Pu_kN']):.1f} tonf"],
        ["φ / α", f"{est['phi']} / {est['alpha']}", "Relación D/C", f"{est['ratio']}"],
    ], [3.8 * cm, 4.4 * cm, 2.6 * cm, 3.2 * cm], header=False))
    el.append(Paragraph(f"<b>Verificación estructural: {_ok(est['cumple'])}</b> "
                        f"(φP_n ≥ P_u).", p))

    el.append(Spacer(1, 5))
    el.append(Paragraph(f"<b>Resultado global: {_ok(resultado.get('cumple', False))}</b>", p))
    for a in resultado.get("avisos", []):
        el.append(Paragraph(f"⚠ {a}", small))
    el.append(Spacer(1, 12))
    el.append(HRFlowable(width="100%", thickness=0.5, color=GRIS_CLARO))
    el.append(Paragraph(f"Generado por CimX · Caisson / pila excavada · {N['pie']}", small))
    doc.build(el)
    return buf.getvalue()
