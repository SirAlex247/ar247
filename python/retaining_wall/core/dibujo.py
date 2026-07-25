"""
Dibujo del muro de contención (matplotlib).

Genera una figura 2D con:
    - Muro (vástago + zapata) a escala.
    - Relleno detrás del muro con su inclinación.
    - Suelo de cimentación.
    - Cotas principales (separadas para evitar solapamientos).
    - Empujes (flechas) si se pasa el sistema de cargas.

El vástago es acartelado: una de sus caras es vertical y la otra inclinada.
El lado vertical se controla con ``muro.geometria.cara_posterior_vertical``:
    True  => cara posterior (contra terreno) vertical; acartelado frontal.
    False => cara frontal (cara vista) vertical;       acartelado atrás.
"""

from __future__ import annotations

import io
import math

import matplotlib
matplotlib.use("Agg")          # backend sin ventana (para el servidor)
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt

from ..models.muro import MuroContencion


# Paleta
COLOR_CONCRETO = "#555555"
COLOR_RELLENO = "#C9A96E"
COLOR_CIMIENTO = "#8B6F47"
COLOR_ACOTADO = "#0066CC"
COLOR_EMPUJE = "#D93025"


def dibujar_muro(muro: MuroContencion,
                 mostrar_empujes: bool = True,
                 figsize: tuple[float, float] = (16, 11),
                 modo: str = "numerico",
                 sistema_unidades: str = "MKS") -> plt.Figure:
    """Genera una figura matplotlib con el muro a escala.

    Args:
        muro: Muro a dibujar.
        mostrar_empujes: Si True, dibuja flechas de empuje activo y pasivo.
        figsize: Tamaño de la figura en pulgadas.
        modo: Estilo de anotaciones:
            - ``"numerico"``: cotas con solo el valor numérico (p. ej. "0.70 m").
              Es el default y se usa en la interfaz web.
            - ``"nombres"``: muestra los nombres de las partes del muro
              (puntera, talón, vástago, zapata, corona, etc.) SIN valores
              numéricos. Útil para un esquema didáctico en el reporte.
            - ``"cotas"``: muestra SOLO valores numéricos con tamaño de fuente
              más grande. Se usa en el reporte después del esquema con nombres.
        sistema_unidades: parámetro ignorado (MKS único).

    Returns:
        Objeto Figure de matplotlib.
    """
    from ..utils.formato import FormatoUnidades
    _fmtU = FormatoUnidades(sistema_unidades)

    g = muro.geometria
    cond = muro.condiciones
    H_rel = g.H_relleno_ef
    y_tope_relleno = g.e_zapata + H_rel

    fig, ax = plt.subplots(figsize=figsize)

    # --- Márgenes ---
    # Interfaz: un poco más amplio para que se vea "alejado" (modo numerico).
    # Reporte: igual de amplio para aprovechar la página (modos nombres/cotas).
    if modo == "numerico":
        margen_x = max(g.B * 1.35, 5.5)
        margen_y = max(g.H_total * 0.28, 2.0)
    else:
        margen_x = max(g.B * 1.05, 4.5)
        margen_y = max(g.H_total * 0.18, 1.4)

    x_min = -margen_x
    x_max = g.B + margen_x
    y_min = -max(g.D, g.h_diente + 0.3) - margen_y * 0.9
    y_max = g.H_total + margen_y + g.b_talon * math.tan(math.radians(cond.alpha))

    # ---------- Suelo de cimentación ----------
    cimiento = mpatches.Rectangle(
        (x_min, y_min), x_max - x_min, -y_min,
        facecolor=COLOR_CIMIENTO, alpha=0.35, edgecolor="none", zorder=1,
    )
    ax.add_patch(cimiento)
    for x in range(int(x_min), int(x_max) + 1):
        ax.plot([x, x + 0.3], [0, -0.3], color=COLOR_CIMIENTO,
                alpha=0.6, lw=0.6, zorder=2)

    # ---------- Zapata ----------
    zapata = mpatches.Rectangle(
        (0, 0), g.B, g.e_zapata,
        facecolor=COLOR_CONCRETO, edgecolor="black", lw=1.8, zorder=5,
    )
    ax.add_patch(zapata)

    # ---------- Diente de cortante (si existe) ----------
    if g.tiene_diente:
        diente = mpatches.Rectangle(
            (g.x_diente_ef, -g.h_diente), g.b_diente, g.h_diente,
            facecolor=COLOR_CONCRETO, edgecolor="black", lw=1.8, zorder=5,
        )
        ax.add_patch(diente)

    # ---------- Vástago acartelado ----------
    x_base_frontal   = g.x_cara_frontal_base
    x_base_posterior = g.x_cara_posterior_base
    x_corona_frontal   = g.x_cara_frontal_corona
    x_corona_posterior = g.x_cara_posterior_corona

    vastago_pts = [
        (x_base_frontal,   g.e_zapata),
        (x_base_posterior, g.e_zapata),
        (x_corona_posterior, g.H_total),
        (x_corona_frontal,   g.H_total),
    ]
    vastago = mpatches.Polygon(
        vastago_pts, closed=True,
        facecolor=COLOR_CONCRETO, edgecolor="black", lw=1.8, zorder=5,
    )
    ax.add_patch(vastago)

    # ---------- Relleno detrás del muro ----------
    alpha_rad = math.radians(cond.alpha)
    y_tope_relleno = g.e_zapata + H_rel
    y_tope_back = y_tope_relleno + g.b_talon * math.tan(alpha_rad)

    # Punto de contacto del relleno con la cara posterior del vástago a la
    # altura del relleno. La interpolación es general: si la cara posterior es
    # vertical (x_corona_posterior == x_base_posterior) coincide con
    # x_base_posterior; con acartelamiento posterior sube por la cara inclinada.
    if g.H_vastago > 0:
        frac_y = H_rel / g.H_vastago
        x_contacto_vast = (x_base_posterior
                           + (x_corona_posterior - x_base_posterior) * frac_y)
    else:
        x_contacto_vast = x_base_posterior

    relleno_pts = [
        (x_base_posterior, g.e_zapata),
        (x_contacto_vast,  y_tope_relleno),
        (g.B,              y_tope_back),
        (g.B,              g.e_zapata),
    ]
    relleno = mpatches.Polygon(
        relleno_pts, closed=True,
        facecolor=COLOR_RELLENO, edgecolor="#8B7A50", lw=1.0, zorder=3,
    )
    ax.add_patch(relleno)
    ax.plot([g.B, x_max],
            [y_tope_back, y_tope_back + (x_max - g.B) * math.tan(alpha_rad)],
            color="#8B7A50", lw=1.4, zorder=4)

    # ---------- Terreno frontal ----------
    y_terreno_frontal = g.D
    ax.fill_between(
        [x_min, 0], y_terreno_frontal, y_min,
        color=COLOR_CIMIENTO, alpha=0.35, zorder=2,
    )
    ax.plot([x_min, 0], [y_terreno_frontal, y_terreno_frontal],
            color="#8B7A50", lw=1.4, zorder=4)

    ax.plot([x_min, x_max], [0, 0], color="black", lw=0.9, ls="--", alpha=0.45)

    # =====================================================================
    # COTAS Y ETIQUETAS — estilo según `modo`
    # =====================================================================
    x_cota_v1 = -margen_x * 0.22
    x_cota_v2 = -margen_x * 0.50
    x_cota_v3 = -margen_x * 0.78
    x_cota_der = g.B + margen_x * 0.28

    y_cota_h1a = -margen_y * 0.45
    y_cota_h1b = -margen_y * 0.75
    y_cota_h2  = -margen_y * 1.15

    # Tamaño de fuente para cotas (más grande para el reporte).
    fs_big   = 14 if modo == "cotas" else 11
    fs_small = 12 if modo == "cotas" else 11

    if modo == "nombres":
        # -----------------------------------------------------------------
        # MODO NOMBRES: etiquetas textuales sobre cada parte del muro,
        # sin dimensiones. Es un esquema didáctico.
        # -----------------------------------------------------------------
        # Zapata (centro)
        ax.text(g.B / 2, g.e_zapata / 2, "ZAPATA",
                color="white", fontsize=13, fontweight="bold",
                ha="center", va="center")
        # Vástago — anotación con flecha hacia el vástago para que no
        # quede montada sobre el relleno
        x_vast_mid = ((x_base_frontal + x_base_posterior) / 2
                      + (x_corona_frontal + x_corona_posterior) / 2) / 2
        y_vast_mid = g.e_zapata + 0.55 * g.H_vastago
        ax.annotate("VÁSTAGO\n(pantalla)",
                    xy=(x_vast_mid, y_vast_mid),
                    xytext=(x_min + margen_x * 0.35, y_vast_mid),
                    color="#1f2937", fontsize=12, fontweight="bold",
                    ha="center", va="center",
                    bbox=dict(boxstyle="round,pad=0.3",
                              facecolor="#E5E7EB", edgecolor="#4B5563", lw=0.8),
                    arrowprops=dict(arrowstyle="->", color="#4B5563", lw=1.2))
        # Corona
        ax.text((x_corona_frontal + x_corona_posterior) / 2,
                g.H_total + margen_y * 0.22, "Corona",
                color="#333", fontsize=12, fontweight="bold",
                ha="center", va="bottom", style="italic")
        # Puntera
        if g.b_puntera > 0:
            ax.annotate("Puntera",
                        xy=(g.b_puntera / 2, -0.05),
                        xytext=(g.b_puntera / 2, -margen_y * 0.55),
                        color="#B45309", fontsize=12, fontweight="bold",
                        ha="center",
                        arrowprops=dict(arrowstyle="->", color="#B45309", lw=1.2))
        # Talón
        if g.b_talon > 0:
            x_cen_tal = g.b_puntera + g.b_base_vast + g.b_talon / 2
            ax.annotate("Talón",
                        xy=(x_cen_tal, -0.05),
                        xytext=(x_cen_tal, -margen_y * 0.55),
                        color="#B45309", fontsize=12, fontweight="bold",
                        ha="center",
                        arrowprops=dict(arrowstyle="->", color="#B45309", lw=1.2))
        # Relleno (dentro del polígono de suelo, desplazado hacia el talón)
        x_rel_centro = (x_base_posterior + 3 * g.B) / 4   # más hacia la derecha
        y_rel_centro = g.e_zapata + 0.35 * H_rel
        ax.text(x_rel_centro, y_rel_centro, "RELLENO",
                color="#6B4423", fontsize=12, fontweight="bold",
                ha="center", va="center", style="italic",
                bbox=dict(boxstyle="round,pad=0.25",
                          facecolor="#FFF5E6", edgecolor="#B45309", lw=0.8))
        # Suelo de cimentación
        ax.text(x_min + margen_x * 0.25, y_min + margen_y * 0.25,
                "SUELO DE\nCIMENTACIÓN",
                color="#5D4037", fontsize=11, fontweight="bold",
                ha="center", va="center", style="italic")
        # Línea del terreno frontal
        ax.annotate("Nivel de\nterreno frontal",
                    xy=(x_min + margen_x * 0.15, g.D),
                    xytext=(x_min + margen_x * 0.05, g.D + margen_y * 0.35),
                    color="#5D4037", fontsize=10, fontweight="bold",
                    ha="left",
                    arrowprops=dict(arrowstyle="->", color="#5D4037", lw=1.0))
        # Diente
        if g.tiene_diente:
            ax.annotate("Diente\nde cortante",
                        xy=(g.x_diente_ef + g.b_diente / 2, -g.h_diente - 0.05),
                        xytext=(g.x_diente_ef + g.b_diente / 2,
                                -g.h_diente - margen_y * 0.55),
                        color="#333", fontsize=10, fontweight="bold",
                        ha="center",
                        arrowprops=dict(arrowstyle="->", color="#333", lw=1.0))
        # Profundidad de desplante → etiqueta descriptiva
        ax.text(x_cota_der, g.D / 2, "Profundidad\nde desplante (D)",
                color=COLOR_ACOTADO, fontsize=11, fontweight="bold",
                ha="center", va="center",
                bbox=dict(boxstyle="round,pad=0.3",
                          facecolor="#E3F2FD", edgecolor=COLOR_ACOTADO, lw=0.8))

    else:
        # -----------------------------------------------------------------
        # MODO NUMÉRICO o COTAS: solo números, sin nombres de piezas.
        # -----------------------------------------------------------------
        # Cotas verticales
        _acotar_vertical(ax, x=x_cota_v1, y1=0, y2=g.e_zapata,
                         texto=f"{g.e_zapata:.2f} m", fs=fs_small)
        _acotar_vertical(ax, x=x_cota_v2, y1=g.e_zapata, y2=g.H_total,
                         texto=f"{g.H_vastago:.2f} m", fs=fs_big)
        if abs(H_rel - g.H_vastago) > 0.01:
            _acotar_vertical(ax, x=x_cota_v3, y1=g.e_zapata, y2=y_tope_relleno,
                             texto=f"{H_rel:.2f} m", fs=fs_small)
        _acotar_vertical(ax, x=x_cota_der, y1=0, y2=g.D,
                         texto=f"{g.D:.2f} m", lado="derecha", fs=fs_small)

        # Cotas horizontales
        if g.b_puntera > 0:
            _acotar_horizontal(ax, 0, g.b_puntera, y_cota_h1a,
                               f"{g.b_puntera:.2f}", fs=fs_small)
        _acotar_horizontal(ax, g.b_puntera, g.b_puntera + g.b_base_vast,
                           y_cota_h1b, f"{g.b_base_vast:.2f}", fs=fs_small)
        if g.b_talon > 0:
            _acotar_horizontal(ax, g.b_puntera + g.b_base_vast, g.B,
                               y_cota_h1a, f"{g.b_talon:.2f}", fs=fs_small)
        _acotar_horizontal(ax, 0, g.B, y_cota_h2,
                           f"{g.B:.2f} m", color="black", fs=fs_big)

        _acotar_horizontal(ax, x_corona_frontal, x_corona_posterior,
                           g.H_total + margen_y * 0.30,
                           f"{g.b_corona:.2f}", color="#333333", fs=fs_small)

        if g.tiene_diente:
            ax.text(g.x_diente_ef + g.b_diente / 2,
                    -g.h_diente - margen_y * 0.30,
                    f"{g.b_diente:.2f} × {g.h_diente:.2f}",
                    color="#333333", fontsize=fs_small, ha="center", va="top",
                    style="italic")

    # ---------- Empujes ----------
    if mostrar_empujes:
        y_aplic = g.e_zapata + H_rel / 3.0
        x_flecha_fin = g.B + margen_x * 0.15
        x_flecha_ini = x_flecha_fin + margen_x * 0.15
        ax.annotate("", xy=(g.B - 0.05, y_aplic), xytext=(x_flecha_ini, y_aplic),
                    arrowprops=dict(arrowstyle="->", color=COLOR_EMPUJE, lw=3.0))
        ax.text(x_flecha_ini + 0.15, y_aplic, "Pa",
                color=COLOR_EMPUJE, fontsize=13, fontweight="bold", va="center")

        y_pp = g.D / 3.0
        x_pp_ini = -margen_x * 0.12
        ax.annotate("", xy=(0.05, y_pp), xytext=(x_pp_ini, y_pp),
                    arrowprops=dict(arrowstyle="->", color="#2E7D32", lw=2.4))
        ax.text(x_pp_ini - 0.15, y_pp + 0.25, "Pp", color="#2E7D32",
                fontsize=13, fontweight="bold", va="bottom", ha="right")

    if cond.sobrecarga > 0:
        x_inicio_sc = g.B + 0.25
        x_fin_sc = x_max - margen_x * 0.3
        n_flechas = 6
        for i in range(n_flechas):
            xi = x_inicio_sc + (x_fin_sc - x_inicio_sc) * i / (n_flechas - 1)
            yi_top = y_tope_back + (xi - g.B) * math.tan(alpha_rad) + 0.6
            yi_bot = y_tope_back + (xi - g.B) * math.tan(alpha_rad) + 0.05
            ax.annotate("", xy=(xi, yi_bot), xytext=(xi, yi_top),
                        arrowprops=dict(arrowstyle="->", color="#1565C0", lw=1.7))
        ax.text((x_inicio_sc + x_fin_sc) / 2,
                y_tope_back + (x_fin_sc - g.B) / 2 * math.tan(alpha_rad) + 0.85,
                f"q = {_fmtU.fmt_presion(cond.sobrecarga)}",
                color="#1565C0",
                fontsize=12, ha="center", fontweight="bold")

    if cond.alpha > 0:
        ax.text(g.B + 0.35, y_tope_back + 0.25, f"α = {cond.alpha}°",
                color="#6D4C41", fontsize=12, fontweight="bold")

    x_centro_corona = (x_corona_frontal + x_corona_posterior) / 2.0
    if modo != "nombres":
        ax.text(x_centro_corona, g.H_total - 0.5,
                "MURO\nConcreto", color="white", fontsize=11, fontweight="bold",
                ha="center", va="top")

    af_e, ap_e = g.a_frontal_ef, g.a_posterior_ef
    if af_e > 1e-6 and ap_e > 1e-6:
        lado_txt = "Vástago acartelado en ambas caras"
    elif ap_e > 1e-6:
        lado_txt = "Acartelado al lado del TERRENO"
    elif af_e > 1e-6:
        lado_txt = "Acartelado al lado de CARA VISTA"
    else:
        lado_txt = "Vástago de espesor constante"
    ax.text((x_min + x_max) / 2, y_max + 0.15, lado_txt,
            color="#1f2937", fontsize=11, fontweight="bold",
            ha="center", va="bottom", style="italic",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="#f3f4f6",
                      edgecolor="#cbd5e1", lw=0.8))

    ax.set_xlim(x_min, x_max)
    ax.set_ylim(y_min, y_max + 0.8)
    ax.set_aspect("equal")
    ax.set_xlabel("x (m)", fontsize=12)
    ax.set_ylabel("y (m)", fontsize=12)
    ax.tick_params(labelsize=10)

    if modo == "nombres":
        titulo = (f"Muro de Contención — Esquema con identificación "
                  f"de las partes del muro")
    elif modo == "cotas":
        titulo = (f"Muro de Contención — Cotas y dimensiones  "
                  f"(H = {g.H_total:.2f} m, B = {g.B:.2f} m)")
    else:
        titulo = f"Muro de Contención — H = {g.H_total:.2f} m, B = {g.B:.2f} m"
    ax.set_title(titulo, fontsize=14, fontweight="bold")
    ax.grid(True, alpha=0.25, ls=":")
    ax.set_axisbelow(True)

    plt.tight_layout()
    return fig


# =============================================================================
# Helpers de acotado
# =============================================================================
def _acotar_vertical(ax, x: float, y1: float, y2: float, texto: str,
                     lado: str = "izquierda", fs: int = 11) -> None:
    """Dibuja una cota vertical con flechas, marcas en los extremos y texto."""
    ax.annotate("", xy=(x, y2), xytext=(x, y1),
                arrowprops=dict(arrowstyle="<->", color=COLOR_ACOTADO, lw=1.2))
    delta = 0.14
    ax.plot([x - delta, x + delta], [y1, y1], color=COLOR_ACOTADO, lw=1.2)
    ax.plot([x - delta, x + delta], [y2, y2], color=COLOR_ACOTADO, lw=1.2)
    ha = "right" if lado == "izquierda" else "left"
    x_text = x - 0.18 if lado == "izquierda" else x + 0.18
    ax.text(x_text, (y1 + y2) / 2, texto, color=COLOR_ACOTADO,
            fontsize=fs, va="center", ha=ha, rotation=90, fontweight="bold")


def _acotar_horizontal(ax, x1: float, x2: float, y: float, texto: str,
                       color: str = COLOR_ACOTADO, fs: int = 11) -> None:
    """Dibuja una cota horizontal con flechas, marcas en los extremos y texto."""
    if abs(x2 - x1) < 1e-6:
        return
    ax.annotate("", xy=(x2, y), xytext=(x1, y),
                arrowprops=dict(arrowstyle="<->", color=color, lw=1.2))
    delta = 0.12
    ax.plot([x1, x1], [y - delta, y + delta], color=color, lw=1.2)
    ax.plot([x2, x2], [y - delta, y + delta], color=color, lw=1.2)
    ax.text((x1 + x2) / 2, y - 0.28, texto, color=color,
            fontsize=fs, ha="center", va="top", fontweight="bold")


# =============================================================================
# Utilidades para obtener la imagen en memoria
# =============================================================================
def figura_a_png(fig: plt.Figure, dpi: int = 160) -> bytes:
    """Convierte una figura matplotlib a bytes PNG (mayor DPI = mejor calidad)."""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()


# =============================================================================
# DIAGRAMA DE EMPUJES LATERALES (para el reporte)
# =============================================================================
def dibujar_diagrama_empujes(muro: MuroContencion,
                              figsize: tuple[float, float] = (14, 9),
                              sistema_unidades: str = "MKS") -> plt.Figure:
    """Dibuja el diagrama de distribución de presiones laterales sobre el muro.

    Muestra:
      - Empuje activo: distribución TRIANGULAR σ_a(z) = Ka·γ·z,
        con σ máximo en la base y 0 en la corona.
      - Empuje por sobrecarga: distribución RECTANGULAR σ_q = Ka·q sobre
        toda la altura (solo si q > 0).
      - Empuje pasivo en la puntera: distribución TRIANGULAR frontal.
      - Resultantes Pa, P_q, Pp con sus puntos de aplicación.

    Todo se grafica contra la cara posterior del vástago (lado del relleno).
    """
    from .empujes import EmpujeSuelo

    from ..utils.formato import FormatoUnidades
    _fmtU = FormatoUnidades(sistema_unidades)

    g = muro.geometria
    rel = muro.suelo_relleno
    cim = muro.suelo_cimentacion
    cond = muro.condiciones

    H  = g.H_suelo           # altura total del relleno desde la base de zapata
    Hp = g.D                 # altura frontal (empuje pasivo)
    q  = cond.sobrecarga
    alpha_rad = math.radians(cond.alpha)

    # Coeficientes
    Ka = EmpujeSuelo.calcular_ka_rankine(rel.phi, cond.alpha)
    Kp = EmpujeSuelo.calcular_kp_rankine(cim.phi)

    # Presiones máximas (en la base, kPa)
    sigma_a_max = Ka * rel.gamma * H * math.cos(alpha_rad)
    sigma_q     = Ka * q * math.cos(alpha_rad) if q > 0 else 0.0
    sigma_p_max = Kp * cim.gamma * Hp + 2.0 * cim.cohesion * math.sqrt(Kp)

    # Resultantes
    Pa = 0.5 * sigma_a_max * H
    Pq = sigma_q * H
    Pp = 0.5 * sigma_p_max * Hp

    fig, ax = plt.subplots(figsize=figsize)

    # Escala de referencia: hacemos que la σ máxima ocupe ~1.5 m hacia atrás
    sigma_ref = max(sigma_a_max + sigma_q, sigma_p_max, 1.0)
    k_plot = 1.5 / sigma_ref        # m por kPa

    # Silueta esquemática del muro (un rectángulo + línea de terreno)
    x_muro_ini = 0.0
    x_muro_fin = 0.35     # espesor visual del muro en la gráfica
    ax.add_patch(mpatches.Rectangle((x_muro_ini, 0), x_muro_fin, H,
                 facecolor="#888", edgecolor="black", lw=1.4, zorder=3))
    # Línea de la base de zapata
    ax.plot([-0.3 - Hp*k_plot*0.5, x_muro_fin + 0.3 + (sigma_a_max+sigma_q)*k_plot + 0.5],
            [0, 0], color="black", lw=1.0, ls="--", alpha=0.5)
    # Línea del tope del relleno
    ax.plot([-0.3, x_muro_fin + (sigma_a_max+sigma_q)*k_plot + 0.5],
            [H, H], color="#8B7A50", lw=1.2)

    # ==================================================================
    # EMPUJE ACTIVO (triángulo hacia la derecha del muro: crece con z)
    # ==================================================================
    # Vértice superior en (x_muro_fin, H), base en (x_muro_fin + sigma_a_max*k, 0)
    pts_act = [
        (x_muro_fin, H),
        (x_muro_fin, 0),
        (x_muro_fin + sigma_a_max * k_plot, 0),
    ]
    ax.add_patch(mpatches.Polygon(pts_act, closed=True, facecolor="#D93025",
                 alpha=0.35, edgecolor="#D93025", lw=1.8, zorder=4))

    # Flechas horizontales apuntando hacia el muro (representan las presiones)
    n_arr = 6
    for i in range(1, n_arr + 1):
        z = H * (i / (n_arr + 1))          # desde corona
        y = H - z                          # y desde base
        sigma_z = Ka * rel.gamma * z * math.cos(alpha_rad)
        x_ini = x_muro_fin + sigma_z * k_plot
        ax.annotate("", xy=(x_muro_fin, y), xytext=(x_ini, y),
                    arrowprops=dict(arrowstyle="->", color="#D93025", lw=1.4))

    # Anotación de presión máxima en la base
    ax.text(x_muro_fin + sigma_a_max * k_plot + 0.08,
            0.05 * H,
            f"σa_máx = {_fmtU.fmt_presion(sigma_a_max)}",
            color="#D93025", fontsize=11, fontweight="bold", va="bottom")

    # Resultante Pa a H/3
    y_Pa = H / 3.0
    x_flecha_ini = x_muro_fin + sigma_a_max * k_plot + 1.6
    ax.annotate("", xy=(x_muro_fin + 0.02, y_Pa),
                xytext=(x_flecha_ini, y_Pa),
                arrowprops=dict(arrowstyle="->", color="#B91C1C", lw=3.2))
    ax.text(x_flecha_ini + 0.1, y_Pa,
            f"Pa = {_fmtU.fmt_fuerza_lineal(Pa)}\n(a H/3 = {y_Pa:.2f} m)",
            color="#B91C1C", fontsize=11, fontweight="bold", va="center")

    # ==================================================================
    # EMPUJE POR SOBRECARGA (rectángulo) - si existe
    # ==================================================================
    if q > 0:
        x0 = x_muro_fin + sigma_a_max * k_plot     # inicia donde termina el triángulo activo
        x1 = x0 + sigma_q * k_plot
        ax.add_patch(mpatches.Rectangle((x0, 0), x1 - x0, H,
                     facecolor="#1565C0", alpha=0.30,
                     edgecolor="#1565C0", lw=1.6, zorder=4))
        # Flechas al muro
        for i in range(1, n_arr + 1):
            y = H * (i / (n_arr + 1))
            ax.annotate("", xy=(x_muro_fin, y), xytext=(x1, y),
                        arrowprops=dict(arrowstyle="->", color="#1565C0",
                                        lw=1.2, alpha=0.7))
        ax.text(x1 + 0.08, H * 0.80,
                f"σq = {_fmtU.fmt_presion(sigma_q)}\n(q = {_fmtU.fmt_presion(q)})",
                color="#1565C0", fontsize=10.5, fontweight="bold", va="center")
        # Resultante Pq a H/2
        y_Pq = H / 2.0
        x_flecha_ini = x1 + 1.6
        ax.annotate("", xy=(x_muro_fin + 0.02, y_Pq),
                    xytext=(x_flecha_ini, y_Pq),
                    arrowprops=dict(arrowstyle="->", color="#0B3E8F", lw=2.6))
        ax.text(x_flecha_ini + 0.1, y_Pq,
                f"Pq = {_fmtU.fmt_fuerza_lineal(Pq)}\n(a H/2 = {y_Pq:.2f} m)",
                color="#0B3E8F", fontsize=11, fontweight="bold", va="center")

    # ==================================================================
    # EMPUJE PASIVO (triángulo frontal, a la izquierda del muro)
    # ==================================================================
    if Hp > 0 and sigma_p_max > 0:
        pts_pas = [
            (x_muro_ini, Hp),
            (x_muro_ini, 0),
            (x_muro_ini - sigma_p_max * k_plot, 0),
        ]
        ax.add_patch(mpatches.Polygon(pts_pas, closed=True,
                     facecolor="#2E7D32", alpha=0.35,
                     edgecolor="#2E7D32", lw=1.8, zorder=4))
        n_arr_p = max(3, int(n_arr * Hp / H))
        for i in range(1, n_arr_p + 1):
            z = Hp * (i / (n_arr_p + 1))
            y = Hp - z
            sigma_z = Kp * cim.gamma * z + 2.0 * cim.cohesion * math.sqrt(Kp)
            x_ini = x_muro_ini - sigma_z * k_plot
            ax.annotate("", xy=(x_muro_ini, y), xytext=(x_ini, y),
                        arrowprops=dict(arrowstyle="->", color="#2E7D32", lw=1.4))
        # σ máxima abajo
        ax.text(x_muro_ini - sigma_p_max * k_plot - 0.08,
                0.05 * Hp,
                f"σp_máx = {_fmtU.fmt_presion(sigma_p_max)}",
                color="#2E7D32", fontsize=10.5, fontweight="bold",
                ha="right", va="bottom")
        # Resultante Pp a Hp/3
        y_Pp = Hp / 3.0
        x_flecha_ini = x_muro_ini - sigma_p_max * k_plot - 1.4
        ax.annotate("", xy=(x_muro_ini - 0.02, y_Pp),
                    xytext=(x_flecha_ini, y_Pp),
                    arrowprops=dict(arrowstyle="->", color="#1B5E20", lw=2.8))
        ax.text(x_flecha_ini - 0.1, y_Pp,
                f"Pp = {_fmtU.fmt_fuerza_lineal(Pp)}\n(a Hp/3 = {y_Pp:.2f} m)",
                color="#1B5E20", fontsize=11, fontweight="bold",
                ha="right", va="center")

    # Cotas y etiquetas de altura
    ax.annotate("", xy=(x_muro_ini - 0.25, H), xytext=(x_muro_ini - 0.25, 0),
                arrowprops=dict(arrowstyle="<->", color="#555", lw=1.2))
    ax.text(x_muro_ini - 0.35, H/2, f"H = {H:.2f} m",
            rotation=90, color="#555", fontsize=11, fontweight="bold",
            ha="right", va="center")

    # Texto con coeficientes y fórmulas
    caja = (f"Coeficientes:  Ka = {Ka:.3f}   Kp = {Kp:.3f}\n"
            f"Método: Rankine · Relleno: γ={_fmtU.fmt_densidad_suelo(rel.gamma)}, φ={rel.phi}°, "
            f"α={cond.alpha}°\n"
            f"Cimentación: γ={_fmtU.fmt_densidad_suelo(cim.gamma)}, φ={cim.phi}°, c'={_fmtU.fmt_presion(cim.cohesion)}")
    ax.text(0.02, 0.02, caja, transform=ax.transAxes,
            fontsize=10, color="#1f2937", family="monospace",
            bbox=dict(boxstyle="round,pad=0.4", facecolor="#f3f4f6",
                      edgecolor="#cbd5e1", lw=0.8),
            verticalalignment="bottom")

    # Leyenda
    legend_items = [
        mpatches.Patch(facecolor="#D93025", alpha=0.35, edgecolor="#D93025",
                       label="Empuje activo (triangular)"),
    ]
    if q > 0:
        legend_items.append(mpatches.Patch(facecolor="#1565C0", alpha=0.30,
                            edgecolor="#1565C0",
                            label="Empuje por sobrecarga (rectangular)"))
    if Hp > 0 and sigma_p_max > 0:
        legend_items.append(mpatches.Patch(facecolor="#2E7D32", alpha=0.35,
                            edgecolor="#2E7D32",
                            label="Empuje pasivo en puntera (triangular)"))
    ax.legend(handles=legend_items, loc="upper right", fontsize=10,
              framealpha=0.95)

    # Título y ajustes
    x_der_max = (x_muro_fin + (sigma_a_max + sigma_q) * k_plot + 3.2)
    x_izq_min = (x_muro_ini - sigma_p_max * k_plot - 2.5
                 if sigma_p_max > 0 else x_muro_ini - 1.0)
    ax.set_xlim(x_izq_min, x_der_max)
    ax.set_ylim(-0.6, H + 0.8)
    ax.set_aspect("auto")
    ax.set_xlabel("x (m) — escala presiones: " +
                  f"{1/k_plot:.1f} {_fmtU.u_presion} por metro gráfico", fontsize=11)
    ax.set_ylabel("Altura desde la base de la zapata y (m)", fontsize=11)
    ax.set_title("Diagrama de presiones laterales — Empuje activo, "
                 "sobrecarga y empuje pasivo",
                 fontsize=13, fontweight="bold")
    ax.grid(True, alpha=0.25, ls=":")
    plt.tight_layout()
    return fig


# =============================================================================
# DIAGRAMA DE CARGAS SÍSMICAS (para el reporte)
# =============================================================================
def dibujar_diagrama_sismo(muro: MuroContencion,
                            figsize: tuple[float, float] = (14, 9),
                            sistema_unidades: str = "MKS") -> plt.Figure:
    """Dibuja el diagrama de cargas sísmicas según Mononobe-Okabe (NSR-10 H.6).

    Muestra:
      - Empuje activo estático Pa (diagrama triangular de referencia).
      - Empuje activo total sísmico Pae (Mononobe-Okabe).
      - Incremento dinámico ΔPae = Pae - Pa (aplicado a 0.6·H).
      - Fuerza de inercia del muro F_inercia = kh·W (en el c.g.).
      - Coeficientes sísmicos kh, kv y el ángulo θ = arctan(kh/(1-kv)).

    Solo se grafica si el muro tiene coeficiente sísmico kh > 0.
    """
    from .empujes import EmpujeSuelo
    from .geometria import CalculadoraGeometria
    from ..utils.formato import FormatoUnidades
    _fmtU = FormatoUnidades(sistema_unidades)

    g = muro.geometria
    rel = muro.suelo_relleno
    cond = muro.condiciones
    kh, kv = cond.kh, cond.kv

    if kh <= 0:
        # Retornamos una figura informativa en lugar de fallar
        fig, ax = plt.subplots(figsize=figsize)
        ax.text(0.5, 0.5,
                "El análisis no incluye carga sísmica.\n"
                "Active 'Incluir sismo' en el formulario para generar este diagrama.",
                transform=ax.transAxes, ha="center", va="center",
                fontsize=14, color="#6b7280")
        ax.axis("off")
        return fig

    H = g.H_suelo
    H_prima = CalculadoraGeometria(muro).altura_efectiva_rankine()
    alpha_rad = math.radians(cond.alpha)

    # Empuje estático y sísmico
    emp_est = EmpujeSuelo.calcular_empuje_activo_rankine(
        gamma=rel.gamma, H=H_prima,
        phi_grados=rel.phi, alpha_grados=cond.alpha,
    )
    emp_sis = EmpujeSuelo.calcular_empuje_sismico(
        gamma=rel.gamma, H=H_prima, phi_grados=rel.phi,
        delta_grados=rel.delta_efectivo, beta_grados=90.0,
        alpha_grados=cond.alpha, kh=kh, kv=kv,
    )
    Pa  = emp_est.componente_h
    Pae = emp_sis.componente_h
    dPae = max(0.0, Pae - Pa)

    # ángulo θ de Mononobe-Okabe
    theta = math.degrees(math.atan(kh / max(1e-6, 1.0 - kv)))

    # Peso total para fuerza de inercia (aproximación sencilla con
    # pesos de concreto + suelo sobre el talón)
    secciones = CalculadoraGeometria(muro).descomponer()
    W_total = sum(s.peso for s in secciones if s.material == "concreto")
    F_inercia = kh * W_total
    # Centroide aproximado del concreto
    if W_total > 0:
        x_cg = sum(s.peso * s.x_cg for s in secciones
                   if s.material == "concreto") / W_total
        y_cg = sum(s.peso * s.y_cg for s in secciones
                   if s.material == "concreto") / W_total
    else:
        x_cg = g.B / 2
        y_cg = g.H_total / 2

    fig, ax = plt.subplots(figsize=figsize)

    # Silueta del muro a escala (simple)
    x_muro_ini = 0.0
    x_muro_fin = g.B_vastago_prom = (g.b_corona + g.b_base_vast) / 2  # grueso visual
    # Pero queremos que se vea elegante: dibujamos silueta real completa
    x0 = 0
    # Zapata
    ax.add_patch(mpatches.Rectangle((x0, 0), g.B, g.e_zapata,
                 facecolor="#9ca3af", edgecolor="black", lw=1.4, zorder=3))
    # Vástago
    vastago_pts = [
        (g.x_cara_frontal_base, g.e_zapata),
        (g.x_cara_posterior_base, g.e_zapata),
        (g.x_cara_posterior_corona, g.H_total),
        (g.x_cara_frontal_corona, g.H_total),
    ]
    ax.add_patch(mpatches.Polygon(vastago_pts, closed=True,
                 facecolor="#9ca3af", edgecolor="black", lw=1.4, zorder=3))

    # Línea base zapata y tope del relleno
    ax.plot([-g.B*0.5, g.B*1.8], [0, 0], color="black", lw=1.0, ls="--", alpha=0.5)
    y_tope = g.e_zapata + g.H_relleno_ef
    ax.plot([g.x_cara_posterior_base, g.B*1.5], [y_tope, y_tope],
            color="#8B7A50", lw=1.2)

    # ==================================================================
    # Empuje estático Pa (línea punteada, a H/3)
    # ==================================================================
    y_Pa = g.e_zapata + H_prima / 3.0
    x_flecha_ini_Pa = g.B + 1.6
    ax.annotate("", xy=(g.B, y_Pa), xytext=(x_flecha_ini_Pa, y_Pa),
                arrowprops=dict(arrowstyle="->", color="#94a3b8", lw=2.2,
                                linestyle="--"))
    ax.text(x_flecha_ini_Pa + 0.1, y_Pa,
            f"Pa (estático) = {_fmtU.fmt_fuerza_lineal(Pa)}\n(a H/3 = {H_prima/3:.2f} m)",
            color="#64748b", fontsize=10.5, va="center")

    # ==================================================================
    # Empuje activo sísmico total Pae
    # ==================================================================
    # Mononobe-Okabe: se aplica a 0.6·H (práctica común NSR-10 H.6.3)
    y_Pae = g.e_zapata + 0.6 * H_prima
    x_flecha_ini_Pae = g.B + 2.5
    ax.annotate("", xy=(g.B, y_Pae), xytext=(x_flecha_ini_Pae, y_Pae),
                arrowprops=dict(arrowstyle="->", color="#DC2626", lw=3.2))
    ax.text(x_flecha_ini_Pae + 0.1, y_Pae,
            f"Pae (sísmico) = {_fmtU.fmt_fuerza_lineal(Pae)}\n(a 0.6·H = {0.6*H_prima:.2f} m)",
            color="#B91C1C", fontsize=11, fontweight="bold", va="center")

    # ==================================================================
    # Incremento dinámico ΔPae
    # ==================================================================
    y_dPae = g.e_zapata + 0.6 * H_prima - 0.45
    x_flecha_ini_dP = g.B + 4.0
    ax.annotate("", xy=(g.B, y_dPae), xytext=(x_flecha_ini_dP, y_dPae),
                arrowprops=dict(arrowstyle="->", color="#F59E0B", lw=2.4))
    ax.text(x_flecha_ini_dP + 0.1, y_dPae,
            f"ΔPae = Pae − Pa = {_fmtU.fmt_fuerza_lineal(dPae)}",
            color="#92400E", fontsize=10.5, fontweight="bold", va="center")

    # ==================================================================
    # Fuerza de inercia del muro kh·W
    # ==================================================================
    # La pintamos aplicada en el c.g. del concreto, horizontal
    ax.plot(x_cg, y_cg, "o", color="#7C3AED", markersize=9, zorder=10)
    ax.annotate("", xy=(x_cg - 1.8, y_cg), xytext=(x_cg, y_cg),
                arrowprops=dict(arrowstyle="->", color="#7C3AED", lw=2.8))
    ax.text(x_cg - 1.9, y_cg + 0.2,
            f"F_inercia = kh·W = {_fmtU.fmt_fuerza_lineal(F_inercia)}",
            color="#5B21B6", fontsize=11, fontweight="bold",
            ha="right", va="bottom")
    ax.text(x_cg + 0.08, y_cg - 0.25,
            f"c.g. muro\n({x_cg:.2f}, {y_cg:.2f}) m",
            color="#7C3AED", fontsize=9, ha="left", va="top")

    # Flecha vertical indicando (1-kv)·W si kv > 0
    if kv > 0:
        W_red = (1.0 - kv) * W_total
        ax.annotate("", xy=(x_cg + 0.05, y_cg - 1.2), xytext=(x_cg + 0.05, y_cg),
                    arrowprops=dict(arrowstyle="->", color="#0891B2", lw=2.0))
        ax.text(x_cg + 0.15, y_cg - 0.7,
                f"(1−kv)·W = {_fmtU.fmt_fuerza_lineal(W_red)}",
                color="#0891B2", fontsize=9.5, fontweight="bold", va="center")

    # ==================================================================
    # Bloque con los parámetros sísmicos y coeficientes
    # ==================================================================
    _Pa_u, _ = _fmtU.fuerza_lineal(Pa)
    _Pae_u, _ = _fmtU.fuerza_lineal(Pae)
    _dPae_u, _ = _fmtU.fuerza_lineal(dPae)
    _Fi_u, _ = _fmtU.fuerza_lineal(F_inercia)
    caja = (f"Parámetros sísmicos (Mononobe-Okabe):\n"
            f"  kh = {kh:.4f}    kv = {kv:.4f}\n"
            f"  θ = arctan[kh/(1-kv)] = {theta:.2f}°\n"
            f"  Ka (estático)  = {emp_est.coeficiente:.4f}\n"
            f"  Kae (sísmico)  = {emp_sis.coeficiente:.4f}\n"
            f"  ΔKae = Kae - Ka = {emp_sis.coeficiente - emp_est.coeficiente:.4f}\n"
            f"\nFuerzas ({_fmtU.u_F_lineal} de muro):\n"
            f"  Pa  = ½·γ·H²·Ka·cosα = {_Pa_u:.2f}\n"
            f"  Pae = ½·γ·H²·(1-kv)·Kae·cosα = {_Pae_u:.2f}\n"
            f"  ΔPae = Pae - Pa = {_dPae_u:.2f}\n"
            f"  F_inercia = kh·W = {_Fi_u:.2f}")
    ax.text(0.02, 0.98, caja, transform=ax.transAxes,
            fontsize=10, color="#1f2937", family="monospace",
            bbox=dict(boxstyle="round,pad=0.5", facecolor="#fef3c7",
                      edgecolor="#f59e0b", lw=1.0),
            verticalalignment="top")

    # Leyenda
    from matplotlib.lines import Line2D
    legend_items = [
        Line2D([0], [0], color="#94a3b8", lw=2, ls="--",
               label="Pa — empuje activo estático (referencia)"),
        Line2D([0], [0], color="#DC2626", lw=3,
               label="Pae — empuje activo sísmico total (M-O)"),
        Line2D([0], [0], color="#F59E0B", lw=2.5,
               label="ΔPae — incremento dinámico"),
        Line2D([0], [0], color="#7C3AED", lw=2.5, marker="o", markersize=7,
               label="F_inercia = kh·W (en el c.g. del muro)"),
    ]
    if kv > 0:
        legend_items.append(
            Line2D([0], [0], color="#0891B2", lw=2,
                   label="(1-kv)·W — peso reducido vertical"))
    ax.legend(handles=legend_items, loc="lower right", fontsize=10,
              framealpha=0.95)

    # Ajustes finales
    ax.set_xlim(-g.B*0.6, g.B*1.8 + 3.5)
    ax.set_ylim(-0.5, g.H_total + 1.3)
    ax.set_aspect("auto")
    ax.set_xlabel("x (m) — medido desde la puntera C", fontsize=11)
    ax.set_ylabel("y (m) — altura desde la base de la zapata", fontsize=11)
    ax.set_title("Diagrama de cargas sísmicas — Mononobe-Okabe (NSR-10 H.6)",
                 fontsize=13, fontweight="bold")
    ax.grid(True, alpha=0.25, ls=":")
    plt.tight_layout()
    return fig


# =============================================================================
# DIAGRAMA DE ESFUERZOS EN LA ZAPATA (para el diseño estructural)
# =============================================================================
def dibujar_esfuerzos_zapata(
    muro: MuroContencion,
    q_puntera: float,
    q_talon: float,
    Mu_punta: float | None = None,
    Mu_talon: float | None = None,
    sistema_unidades: str = "MKS",
) -> plt.Figure:
    """Dibuja la distribución de presiones bajo la zapata con sus valores
    en los tres puntos clave: puntera (C), cara del vástago y talón.

    ``sistema_unidades`` se mantiene por compat (la app es MKS único).

    La figura incluye:
      - La zapata en alzado (rectángulo) con el arranque del vástago marcado.
      - El trapecio de presiones del suelo bajo la zapata (hacia arriba).
      - Etiquetas con los valores numéricos de q en la puntera, en la cara
        del vástago (ambos lados) y en el talón.
      - Líneas verticales marcando las secciones críticas donde se
        calculan los momentos M_u (si se pasan como parámetro).

    Argumentos ``q_*`` y ``Mu_*`` SIEMPRE se reciben en SI (kPa, kN·m/m);
    la conversión a la unidad del sistema elegido se hace internamente.
    """
    from ..utils.formato import FormatoUnidades
    fmt = FormatoUnidades(sistema_unidades)

    g = muro.geometria
    B = g.B
    # Posiciones en x desde la puntera C (x = 0)
    x_cara_fr_vast = g.x_cara_frontal_base   # cara frontal (lado de la punta)
    x_cara_po_vast = g.x_fin_vastago         # cara posterior (lado del talón)
    # Valor de la presión en las caras del vástago (interpolación lineal)
    def _q_en(x: float) -> float:
        return q_puntera + (q_talon - q_puntera) * x / B
    q_fr = _q_en(x_cara_fr_vast)
    q_po = _q_en(x_cara_po_vast)
    # Etiqueta y factor de presión para el sistema elegido
    _, u_q = fmt.presion(0.0)
    def _fmt_q(v: float) -> str:
        val, _ = fmt.presion(v)
        return f"{val:.2f} {u_q}"
    _, u_m = fmt.momento_lineal(0.0)
    def _fmt_m(v: float) -> str:
        val, _ = fmt.momento_lineal(v)
        return f"{val:.2f} {u_m}"

    fig, ax = plt.subplots(figsize=(11.0, 5.4))

    # --- zapata (alzado) ---
    y_base = 0.0
    y_top  = g.e_zapata
    ax.add_patch(mpatches.Rectangle(
        (0, y_base), B, g.e_zapata,
        facecolor="#e5e7eb", edgecolor="#374151", linewidth=1.3))

    # --- vástago (sólo indicación del arranque) ---
    h_ind = min(0.8, g.e_zapata * 1.5)   # altura ilustrativa
    ax.add_patch(mpatches.Rectangle(
        (x_cara_fr_vast, y_top), g.b_base_vast, h_ind,
        facecolor="#cbd5e1", edgecolor="#374151",
        linewidth=1.0, hatch="////"))
    ax.annotate("vástago", xy=(x_cara_fr_vast + g.b_base_vast/2, y_top + h_ind*0.55),
                ha="center", fontsize=9, color="#374151")

    # --- trapecio de presiones (abajo, con flechas hacia ARRIBA = reacción) ---
    # Escala vertical: q_max mapea a una altura gráfica de 2.2 m hacia abajo.
    q_max_plot = max(q_puntera, q_talon, 1e-6)
    H_scale = 2.2
    y_q_punt = y_base - (q_puntera / q_max_plot) * H_scale
    y_q_fr   = y_base - (q_fr      / q_max_plot) * H_scale
    y_q_po   = y_base - (q_po      / q_max_plot) * H_scale
    y_q_tal  = y_base - (q_talon   / q_max_plot) * H_scale

    # Polígono del trapecio (cerrado en la base de la zapata)
    poly = [(0, y_base), (0, y_q_punt), (B, y_q_tal), (B, y_base)]
    ax.add_patch(mpatches.Polygon(
        poly, closed=True,
        facecolor="#bae6fd", edgecolor="#0369a1", linewidth=1.4, alpha=0.7))

    # Flechas de presión cada cierto intervalo
    n_arrows = 16
    for i in range(n_arrows + 1):
        x = i * B / n_arrows
        y_top_arrow = y_base
        q_x = _q_en(x)
        y_bot_arrow = y_base - (q_x / q_max_plot) * H_scale
        ax.annotate("", xy=(x, y_top_arrow),
                    xytext=(x, y_bot_arrow - 0.05),
                    arrowprops=dict(arrowstyle="->", color="#0369a1",
                                    lw=1.1, alpha=0.9))

    # Etiquetas en los 4 puntos clave. Se apilan en 4 niveles distintos
    # para evitar solapes en anchos típicos.  Niveles (más bajo = más lejos
    # de la zapata): puntera en nivel 0, cara-frontal en 1, cara-posterior
    # en 2, talón en nivel 3.
    def _place(x, q, txt, nivel, ha="center"):
        # Altura total ocupada por las etiquetas, escalonada
        dy_por_nivel = 0.55
        y_top_label = y_q_punt - 0.25 - nivel * dy_por_nivel
        y_pt = y_base - (q / q_max_plot) * H_scale
        ax.annotate(
            f"{txt}: {_fmt_q(q)}",
            xy=(x, y_pt), xytext=(x, y_top_label),
            ha=ha, va="top", fontsize=9.0, fontweight="bold",
            color="#0c4a6e",
            bbox=dict(boxstyle="round,pad=0.28", fc="#f0f9ff",
                      ec="#0369a1", lw=0.8),
            arrowprops=dict(arrowstyle="-", color="#0369a1", lw=0.6,
                            alpha=0.5))

    _place(0,              q_puntera, "q en puntera",           0, ha="left")
    _place(x_cara_fr_vast, q_fr,      "q en cara frontal vástago",  1)
    _place(x_cara_po_vast, q_po,      "q en cara posterior vástago", 2)
    _place(B,              q_talon,   "q en talón",             3, ha="right")

    # Líneas verticales punteadas en las caras del vástago (secciones críticas
    # para el cálculo del momento en punta y talón)
    for x_sec, label in [(x_cara_fr_vast, "sección crítica\n(punta)"),
                         (x_cara_po_vast, "sección crítica\n(talón)")]:
        ax.plot([x_sec, x_sec], [y_q_punt - 0.3, y_top + h_ind + 0.4],
                ls=":", color="#dc2626", lw=1.3, alpha=0.85)
        ax.annotate(label, xy=(x_sec, y_top + h_ind + 0.45),
                    ha="center", fontsize=8, color="#dc2626",
                    style="italic")

    # Mu en recuadros (si se pasan)
    if Mu_punta is not None:
        x_txt = x_cara_fr_vast / 2.0
        ax.annotate(f"M_u (punta) = {_fmt_m(Mu_punta)}",
                    xy=(x_txt, y_top + h_ind + 0.2),
                    ha="center", fontsize=10, fontweight="bold",
                    color="#065f46",
                    bbox=dict(boxstyle="round,pad=0.35",
                              fc="#d1fae5", ec="#065f46", lw=1.0))
    if Mu_talon is not None:
        x_txt = x_cara_po_vast + (B - x_cara_po_vast) / 2.0
        ax.annotate(f"M_u (talón) = {_fmt_m(Mu_talon)}",
                    xy=(x_txt, y_top + h_ind + 0.2),
                    ha="center", fontsize=10, fontweight="bold",
                    color="#065f46",
                    bbox=dict(boxstyle="round,pad=0.35",
                              fc="#d1fae5", ec="#065f46", lw=1.0))

    # Línea horizontal = base de la zapata
    ax.axhline(y_base, color="#374151", lw=1.2)

    # Cotas horizontales (debajo de las etiquetas apiladas)
    y_cota = y_q_punt - 0.25 - 4 * 0.55 - 0.4
    ax.annotate("", xy=(0, y_cota), xytext=(x_cara_fr_vast, y_cota),
                arrowprops=dict(arrowstyle="<->", color="#555"))
    ax.text(x_cara_fr_vast / 2, y_cota - 0.15,
            f"b_puntera = {g.b_puntera:.2f} m",
            ha="center", va="top", fontsize=9, color="#555")
    ax.annotate("", xy=(x_cara_po_vast, y_cota), xytext=(B, y_cota),
                arrowprops=dict(arrowstyle="<->", color="#555"))
    ax.text(x_cara_po_vast + (B - x_cara_po_vast) / 2, y_cota - 0.15,
            f"b_talón = {g.b_talon:.2f} m",
            ha="center", va="top", fontsize=9, color="#555")

    # Ajuste visual
    ax.set_xlim(-0.7, B + 0.7)
    ax.set_ylim(y_cota - 0.8, y_top + h_ind + 1.0)
    ax.set_aspect("auto")
    ax.set_xlabel("x (m) — medido desde la puntera (C)", fontsize=10)
    ax.set_yticks([])
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_visible(False)
    ax.set_title(
        "Distribución de presiones bajo la zapata (sin mayorar)",
        fontsize=12, fontweight="bold", color="#065f46", pad=12)
    ax.grid(True, axis="x", alpha=0.2, ls=":")
    plt.tight_layout()
    return fig


# =====================================================================
# DIBUJO DEL MURO DE GRAVEDAD
# =====================================================================
def dibujar_muro_gravedad(muro,
                          mostrar_empujes: bool = True,
                          figsize: tuple[float, float] = (16, 11),
                          modo: str = "numerico",
                          sistema_unidades: str = "MKS") -> plt.Figure:
    """Figura matplotlib del muro de gravedad (cuerpo trapezoidal).

    Args:
        muro: ``MuroGravedad`` con su geometría trapezoidal.
        mostrar_empujes: dibuja flechas de Pa, Pp, sobrecarga si True.
        figsize: tamaño de la figura.
        modo: "numerico" (cotas con valor), "nombres" (etiquetas), "cotas".
        sistema_unidades: ignorado por compat (todo en m / unidades del muro).

    Returns:
        Figura matplotlib lista para guardar a PNG.
    """
    from ..utils.formato import FormatoUnidades
    g = muro.geometria
    fmt = FormatoUnidades(sistema_unidades)

    fig, ax = plt.subplots(figsize=figsize)

    # ─── DIBUJAR EL CUERPO TRAPEZOIDAL ───
    cuerpo = mpatches.Polygon(
        g.vertices_cuerpo(), closed=True,
        facecolor=COLOR_CONCRETO, edgecolor="black", linewidth=1.5, zorder=4)
    ax.add_patch(cuerpo)

    # ─── ZAPATA ───
    zapata = mpatches.Rectangle(
        (0, 0), g.B, g.e_zapata,
        facecolor=COLOR_CONCRETO, edgecolor="black", linewidth=1.5, zorder=4)
    ax.add_patch(zapata)

    # ─── TERRENO DE CIMENTACIÓN (BAJO LA ZAPATA) ───
    y_cim_top = 0.0
    y_cim_bot = -max(2.0, g.D + 0.5)
    margen_lat = max(2.5, g.B * 0.4)
    cim = mpatches.Rectangle(
        (-margen_lat, y_cim_bot),
        g.B + 2*margen_lat, y_cim_top - y_cim_bot,
        facecolor=COLOR_CIMIENTO, edgecolor="none", alpha=0.55, zorder=1)
    ax.add_patch(cim)
    # Línea de superficie
    ax.plot([-margen_lat, g.B + margen_lat], [0, 0],
            color="#5e4525", lw=0.8, ls="--", alpha=0.7, zorder=2)

    # ─── RELLENO DETRÁS DEL MURO ───
    # El relleno apoya sobre la cara posterior inclinada del cuerpo y se
    # extiende hacia la derecha. Inclinación α si corresponde.
    alpha_rad = math.radians(muro.condiciones.alpha)
    x_pie_post = g.b_puntera + g.a_frontal + g.b_corona + g.a_posterior
    x_cor_der  = g.b_puntera + g.a_frontal + g.b_corona
    y_top      = g.e_zapata + g.H_muro

    # Vértices del polígono de relleno (CCW desde el pie del cuerpo)
    x_relleno_max = g.B + margen_lat + 1.5
    rell_vertices = [
        (x_pie_post,    g.e_zapata),                    # base sobre zapata
        (g.B,           g.e_zapata),                    # borde del talón
        (x_relleno_max, g.e_zapata),                    # extremo derecho a la altura del talón
        (x_relleno_max, y_top + (x_relleno_max - x_cor_der) * math.tan(alpha_rad)),
        (x_cor_der,     y_top),                         # corona (lado posterior)
    ]
    relleno = mpatches.Polygon(
        rell_vertices, closed=True,
        facecolor=COLOR_RELLENO, edgecolor="none", alpha=0.85, zorder=2)
    ax.add_patch(relleno)
    # Borde de superficie del relleno
    ax.plot([x_cor_der, x_relleno_max],
            [y_top, y_top + (x_relleno_max - x_cor_der) * math.tan(alpha_rad)],
            color="#5e4525", lw=1.0, zorder=3)

    # ─── COTAS Y ETIQUETAS ───
    if modo == "nombres":
        # Etiquetas descriptivas
        ax.annotate("Cuerpo (concreto)",
                    xy=(g.b_puntera + g.a_frontal + g.b_corona/2,
                        g.e_zapata + g.H_muro/2),
                    color="white", fontsize=12, fontweight="bold",
                    ha="center", va="center", zorder=5)
        ax.annotate("Zapata", xy=(g.B/2, g.e_zapata/2),
                    color="white", fontsize=11, fontweight="bold",
                    ha="center", va="center", zorder=5)
        ax.annotate("Relleno", xy=(g.B + 1.5, y_top - 0.5),
                    color="#5e4525", fontsize=12, fontweight="bold",
                    ha="left", va="top", zorder=5)
        ax.annotate("Suelo cimentación", xy=(g.B/2, -1.0),
                    color="white", fontsize=11, fontweight="bold",
                    ha="center", va="center", zorder=5)
    else:
        # Cotas numéricas
        # Altura H (cuerpo)
        ax.annotate(f"H = {g.H_muro:.2f} m",
                    xy=(-0.7, g.e_zapata + g.H_muro/2),
                    color=COLOR_ACOTADO, fontsize=11, fontweight="bold",
                    ha="right", va="center", rotation=90, zorder=6)
        # B
        ax.annotate(f"B = {g.B:.2f} m",
                    xy=(g.B/2, -0.35),
                    color=COLOR_ACOTADO, fontsize=11, fontweight="bold",
                    ha="center", va="top", zorder=6)
        # Espesor zapata
        ax.annotate(f"e = {g.e_zapata:.2f} m",
                    xy=(g.B + 0.3, g.e_zapata/2),
                    color=COLOR_ACOTADO, fontsize=10, fontweight="bold",
                    ha="left", va="center", zorder=6)
        # b_corona en la corona
        ax.annotate(f"b_corona = {g.b_corona:.2f} m",
                    xy=(g.b_puntera + g.a_frontal + g.b_corona/2, y_top + 0.25),
                    color=COLOR_ACOTADO, fontsize=10, fontweight="bold",
                    ha="center", va="bottom", zorder=6)
        # β (ángulo cara posterior)
        ax.annotate(f"β = {g.beta_grados:.1f}°",
                    xy=(x_pie_post - 0.3, g.e_zapata + g.H_muro/2),
                    color=COLOR_ACOTADO, fontsize=10, fontweight="bold",
                    ha="right", va="center", zorder=6)
        # D
        ax.annotate(f"D = {g.D:.2f} m",
                    xy=(-1.0, -g.D/2),
                    color=COLOR_ACOTADO, fontsize=10, fontweight="bold",
                    ha="right", va="center", zorder=6)

    # ─── EMPUJES (flechas) ───
    if mostrar_empujes:
        # Pa actúa sobre la cara posterior a H'/3 desde la base de zapata.
        y_pa = (g.H_muro + g.e_zapata) / 3.0
        # Punto de aplicación sobre la cara posterior real:
        if y_pa <= g.e_zapata:
            x_pa = x_pie_post
        else:
            t = (y_pa - g.e_zapata) / g.H_muro
            x_pa = x_pie_post + t * (x_cor_der - x_pie_post)

        # Pa con ángulo (90 - β) + δ desde horizontal
        ang_pa = math.radians((90 - g.beta_grados) + muro.suelo_relleno.delta_efectivo)
        # Dirección: empuja hacia la izquierda y hacia abajo
        L = 1.5  # longitud visual
        dx = -L * math.cos(ang_pa)
        dy = -L * math.sin(ang_pa)
        ax.arrow(x_pa - dx, y_pa - dy, dx, dy,
                 head_width=0.20, head_length=0.18,
                 fc=COLOR_EMPUJE, ec=COLOR_EMPUJE, lw=2.0, zorder=7,
                 length_includes_head=True)
        ax.annotate("Pa", xy=(x_pa - dx - 0.3, y_pa - dy + 0.1),
                    color=COLOR_EMPUJE, fontsize=12, fontweight="bold",
                    ha="right", zorder=8)

        # Pp delante de la puntera (resistente)
        if g.D > 0:
            y_pp = g.D / 3.0    # bajo la base de la zapata, pero lo dibujamos a y > 0
            ax.arrow(-1.2, -y_pp, 0.9, 0,
                     head_width=0.15, head_length=0.15,
                     fc="#16a34a", ec="#16a34a", lw=2.0, zorder=7,
                     length_includes_head=True)
            ax.annotate("Pp", xy=(-1.5, -y_pp), color="#16a34a",
                        fontsize=11, fontweight="bold",
                        ha="right", va="center", zorder=8)

    # ─── EJES Y FORMATO ───
    ax.set_aspect("equal", adjustable="datalim")
    ax.set_xlim(-margen_lat, g.B + margen_lat + 2)
    ax.set_ylim(y_cim_bot - 0.3, y_top + 1.5 +
                (x_relleno_max - x_cor_der) * math.tan(alpha_rad))
    ax.set_xlabel("x (m)")
    ax.set_ylabel("y (m)")
    ax.set_title(
        f"Muro de Gravedad — H = {g.H_total:.2f} m, B = {g.B:.2f} m, β = {g.beta_grados:.1f}°",
        fontsize=13, fontweight="bold")
    ax.grid(True, alpha=0.25, ls=":")
    plt.tight_layout()
    return fig
