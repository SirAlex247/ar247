"""
Aplicación web interactiva para diseño de muros de contención (NSR-10).

Ejecución:
    python app.py

Luego abre en el navegador:
    http://localhost:5000
"""

from __future__ import annotations

import base64
import logging
import os
import traceback
from logging.handlers import RotatingFileHandler

from flask import Flask, jsonify, render_template, request, send_file

from retaining_wall import (
    AceroRefuerzo,
    AnalisisEstabilidad,
    AplicadorCombinaciones,
    CalculadoraCargas,
    CalculadoraGeometria,
    CombinacionesNSR10,
    Concreto,
    CondicionesCarga,
    DisenadorMuroVoladizo,
    GeometriaMuro,
    MuroContencion,
    Suelo,
)
from retaining_wall.core.dibujo import (
    dibujar_muro, figura_a_png,
    dibujar_diagrama_empujes, dibujar_diagrama_sismo,
    dibujar_esfuerzos_zapata,
)
from retaining_wall.core.reporte_pdf import DatosProyecto, generar_pdf
from retaining_wall.core.sismo_nsr10 import (
    ParametrosSismicosNSR10, TipoSueloNSR10,
    calcular_Fa, calcular_Fv,
)
# Tipos adicionales (gravedad)
from retaining_wall.models.muro_gravedad import MuroGravedad
from retaining_wall.core.cargas_gravedad import CalculadoraCargasGravedad


from retaining_wall.utils.formato import FormatoUnidades


app = Flask(__name__, template_folder="templates", static_folder="static")


# =============================================================================
# Logging y manejo de errores centralizado
# =============================================================================
# En modo debug (env ``CIMX_DEBUG=1``) las respuestas de error incluyen el
# traceback completo para depurar. En producción NO se filtra el traceback al
# cliente; se registra en el archivo de log y se devuelve un mensaje limpio.
CIMX_DEBUG = os.environ.get("CIMX_DEBUG", "") not in ("", "0", "false", "False")

logger = logging.getLogger("cimx")
logger.setLevel(logging.INFO)


def _setup_file_logging() -> None:
    """Configura un archivo de log rotativo. Nunca rompe la app si falla
    (p.ej. carpeta no escribible en el empaquetado)."""
    try:
        log_dir = os.environ.get("CIMX_LOG_DIR") or os.path.join(os.getcwd(), "logs")
        os.makedirs(log_dir, exist_ok=True)
        handler = RotatingFileHandler(
            os.path.join(log_dir, "cimx.log"),
            maxBytes=1_000_000, backupCount=3, encoding="utf-8",
        )
        handler.setFormatter(logging.Formatter(
            "%(asctime)s  %(levelname)-7s  %(message)s"))
        if not logger.handlers:
            logger.addHandler(handler)
    except Exception:
        pass


_setup_file_logging()


def _error_response(e: Exception, contexto: str = ""):
    """Respuesta JSON de error uniforme.

    - ``KeyError`` → falta un dato requerido (mensaje amable, HTTP 200 con
      ``ok=False`` para que el frontend lo muestre inline).
    - Subclases de ``ValueError`` (incluye ``ValidacionError`` del paquete)
      → error de validación con el mensaje real.
    - Cualquier otra → error inesperado; se registra el traceback y se
      devuelve un mensaje genérico (el traceback solo va al cliente en
      modo debug).
    """
    if not contexto:
        try:
            contexto = request.path
        except Exception:
            contexto = "?"
    if isinstance(e, KeyError):
        campo = str(e).strip("'\"")
        logger.warning("Falta dato requerido (%s): %s", contexto, campo)
        payload = {"ok": False, "validacion": True,
                   "error": f"Falta un dato requerido: {campo}."}
    elif isinstance(e, ValueError):
        logger.warning("Validación (%s): %s", contexto, e)
        payload = {"ok": False, "validacion": True,
                   "error": str(e) or "Datos de entrada inválidos."}
    else:
        logger.exception("Error inesperado (%s)", contexto)
        payload = {"ok": False, "validacion": False,
                   "error": ("Ocurrió un error al procesar la solicitud. "
                             "Revisa los datos e inténtalo de nuevo.")}
    if CIMX_DEBUG:
        payload["trace"] = traceback.format_exc()
    return jsonify(payload)


# ------------------------------- helpers --------------------------------
def _reformat_params(params_list: list[dict],
                     fmt: FormatoUnidades) -> list[dict]:
    """Re-escribe la lista ``[{nombre, valor, unidad}, ...]`` (parámetros
    detallados en SI) al sistema pedido: ``valor`` se convierte y
    ``unidad`` cambia de etiqueta. Ángulos, adimensionales y longitudes
    se dejan igual (iguales en ambos sistemas)."""
    conv = {
        "kN/m":   fmt.fuerza_lineal,
        "kN/m³":  fmt.densidad_suelo,
        "kPa":    fmt.presion,
        "kN·m/m": fmt.momento_lineal,
    }
    out = []
    for p in params_list or []:
        p2 = dict(p)
        u = p2.get("unidad", "")
        v = p2.get("valor")
        if u in conv and isinstance(v, (int, float)):
            v_new, u_new = conv[u](v)
            p2["valor"]  = v_new
            p2["unidad"] = u_new
        out.append(p2)
    return out


def _reformat_items(items: list[dict], fmt: FormatoUnidades,
                    tipo: str) -> list[dict]:
    """Convierte ``valor`` de una lista de ítems (fuerzas, términos)
    al sistema pedido. ``tipo`` ∈ {fuerza_lineal, momento_lineal,
    presion}. El string ``detalle`` (traza del cálculo intermedio) se
    mantiene en SI (no se guardan valores crudos de cada operación)."""
    out = []
    for it in items or []:
        it2 = dict(it)
        v = it2.get("valor")
        if isinstance(v, (int, float)):
            if tipo == "fuerza_lineal":
                it2["valor"], _ = fmt.fuerza_lineal(v)
            elif tipo == "momento_lineal":
                it2["valor"], _ = fmt.momento_lineal(v)
            elif tipo == "presion":
                it2["valor"], _ = fmt.presion(v)
        out.append(it2)
    return out


# =============================================================================
# Motor de cálculo
# =============================================================================
def construir_muro_desde_datos(d: dict) -> tuple[MuroContencion, ParametrosSismicosNSR10 | None]:
    """Construye el muro a partir del diccionario recibido desde el frontend.

    El frontend envía todos los valores ya en SI (la función ``inputSI`` del JS
    hace la conversión MKS→SI antes de enviar), por lo que el backend trabaja
    directamente en kN, m, kPa, MPa sin convertir nada.
    """
    # H_relleno opcional: si viene vacío o 0, se toma H_vastago
    H_rell_val = d.get("H_relleno", None)
    try:
        H_rell = float(H_rell_val) if H_rell_val not in (None, "", 0, "0") else None
    except (TypeError, ValueError):
        H_rell = None

    # Helper para convertir valores opcionales a float (vacío -> 0)
    def _fopt(k: str, default: float = 0.0) -> float:
        v = d.get(k, default)
        if v in (None, ""):
            return default
        try:
            return float(v)
        except (TypeError, ValueError):
            return default

    # x_diente opcional
    x_diente_val = d.get("x_diente", None)
    try:
        x_diente = (float(x_diente_val)
                    if x_diente_val not in (None, "", "None") else None)
    except (TypeError, ValueError):
        x_diente = None

    # ──────────────────────────────────────────────────────────────────
    # Despachador por tipo de muro
    # ──────────────────────────────────────────────────────────────────
    tipo_muro = str(d.get("tipo_muro", "voladizo") or "voladizo").lower()

    relleno = Suelo(
        gamma=float(d["relleno_gamma"]),
        phi=float(d["relleno_phi"]),
        cohesion=float(d.get("relleno_cohesion", 0.0)),
        nombre=d.get("relleno_nombre", "Relleno"),
    )
    cimentacion = Suelo(
        gamma=float(d["ciment_gamma"]),
        phi=float(d["ciment_phi"]),
        cohesion=float(d.get("ciment_cohesion", 0.0)),
        nombre=d.get("ciment_nombre", "Cimentación"),
    )

    # Parámetros sísmicos
    params_sismo = None
    kh, kv = 0.0, 0.0
    if d.get("incluir_sismo", False):
        params_sismo = ParametrosSismicosNSR10(
            Aa=float(d["Aa"]),
            Av=float(d["Av"]),
            tipo_suelo=TipoSueloNSR10(d.get("tipo_suelo_nsr", "D")),
            permite_desplazamiento=d.get("permite_desplazamiento", True),
        )
        kh = params_sismo.kh
        kv = params_sismo.kv

    condiciones = CondicionesCarga(
        alpha=float(d.get("alpha", 0.0)),
        sobrecarga=float(d.get("sobrecarga", 0.0)),
        kh=kh,
        kv=kv,
    )

    concreto = Concreto(
        fc=float(d.get("concreto_fc", 21.0)),
        gamma=float(d.get("concreto_gamma", 24.0)),
    )
    acero = AceroRefuerzo(fy=float(d.get("acero_fy", 420.0)))

    if tipo_muro == "gravedad":
        from retaining_wall.models.geometria_gravedad import GeometriaMuroGravedad
        from retaining_wall.models.muro_gravedad import MuroGravedad
        geometria_g = GeometriaMuroGravedad(
            H_muro=float(d["H_muro"]),
            e_zapata=float(d["e_zapata"]),
            b_corona=float(d["b_corona"]),
            a_frontal=_fopt("a_frontal"),
            a_posterior=_fopt("a_posterior"),
            b_puntera=_fopt("b_puntera"),
            b_talon=_fopt("b_talon"),
            D=float(d["D"]),
        )
        muro = MuroGravedad(
            geometria=geometria_g,
            suelo_relleno=relleno,
            suelo_cimentacion=cimentacion,
            concreto=concreto,
            acero=acero,
            condiciones=condiciones,
        )
        return muro, params_sismo

    # ──────────────────────────────────────────────────────────────────
    # Tipo voladizo (default)
    # ──────────────────────────────────────────────────────────────────
    _afv = d.get("a_frontal_v")
    _apv = d.get("a_posterior_v")
    a_frontal_v = float(_afv) if _afv not in (None, "") else None
    a_posterior_v = float(_apv) if _apv not in (None, "") else None
    geometria = GeometriaMuro(
        H_vastago=float(d["H_vastago"]),
        e_zapata=float(d["e_zapata"]),
        b_puntera=float(d["b_puntera"]),
        b_talon=float(d["b_talon"]),
        b_corona=float(d["b_corona"]),
        b_base_vast=float(d["b_base_vast"]),
        D=float(d["D"]),
        H_relleno=H_rell,
        cara_posterior_vertical=bool(d.get("cara_posterior_vertical", True)),
        h_diente=_fopt("h_diente"),
        b_diente=_fopt("b_diente"),
        x_diente=x_diente,
        a_frontal_v=a_frontal_v,
        a_posterior_v=a_posterior_v,
    )
    muro = MuroContencion(
        geometria=geometria,
        suelo_relleno=relleno,
        suelo_cimentacion=cimentacion,
        concreto=concreto,
        acero=acero,
        condiciones=condiciones,
    )
    return muro, params_sismo


def _resultado_gravedad(muro, sistema, reporte, fmt: FormatoUnidades,
                        desliz_detalle: dict,
                        capcar_detalle: dict,
                        exc_detalle: dict,
                        res_elu: list, res_els: list,
                        datos: dict) -> dict:
    """Construye la respuesta completa para muros de gravedad.

    Incluye todos los datos necesarios para generar el reporte PDF: resumen,
    cargas, combinaciones, verificaciones, presiones, momentos detallados,
    e imágenes (muro principal, diagrama de empujes, sismo si aplica).
    Omite el diseño estructural por flexión, que no aplica para muros de
    gravedad.
    """
    from retaining_wall.core.dibujo import (
        dibujar_muro_gravedad, figura_a_png,
        dibujar_diagrama_empujes, dibujar_diagrama_sismo,
    )

    # ─── Imágenes (PNG en base64) ───────────────────────────────────
    # Imagen principal del muro (con cotas numéricas)
    fig_num = dibujar_muro_gravedad(muro, mostrar_empujes=True, modo="numerico")
    png_bytes = figura_a_png(fig_num)
    img_b64 = base64.b64encode(png_bytes).decode("ascii")
    # Imagen con nombres (para el reporte: identifica las partes)
    fig_nom = dibujar_muro_gravedad(muro, mostrar_empujes=False,
                                    figsize=(16, 11), modo="nombres")
    img_nombres_b64 = base64.b64encode(figura_a_png(fig_nom)).decode("ascii")
    # Imagen con cotas (para el reporte)
    fig_cot = dibujar_muro_gravedad(muro, mostrar_empujes=True,
                                    figsize=(16, 11), modo="cotas")
    img_cotas_b64 = base64.b64encode(figura_a_png(fig_cot)).decode("ascii")

    # Diagrama de empujes laterales — dibujar_diagrama_empujes funciona
    # con cualquier muro que tenga geometria, suelo_relleno y H_prima.
    try:
        fig_emp = dibujar_diagrama_empujes(muro)
        img_emp_b64 = base64.b64encode(figura_a_png(fig_emp)).decode("ascii")
    except Exception:
        img_emp_b64 = ""    # falla silenciosa si la geometría no encaja
    # Diagrama sísmico (placeholder si no hay sismo)
    try:
        fig_sis = dibujar_diagrama_sismo(muro)
        img_sis_b64 = base64.b64encode(figura_a_png(fig_sis)).decode("ascii")
    except Exception:
        img_sis_b64 = ""

    # ─── Cargas (filas en MKS + raw para frontend) ──────────────────
    cargas_rows = []
    cargas_raw = []
    for c in sistema.cargas:
        F = fmt.fuerza_lineal(c.magnitud * c.sentido)[0]
        cargas_rows.append([
            c.nombre, c.tipo.value, c.categoria.value,
            f"{F:.2f}",
            f"{c.x_aplicacion:.2f}" if c.tipo.value == "vertical" else "—",
            f"{c.y_aplicacion:.2f}" if c.tipo.value == "horizontal" else "—",
        ])
        cargas_raw.append({
            "nombre":   c.nombre,
            "magnitud_kN": c.magnitud,
            "tipo":     c.tipo.value,
            "categoria": c.categoria.value,
        })

    # ─── Tablas detalladas de momentos ──────────────────────────────
    momentos_estabilizadores = []
    for fila in sistema.tabla_momentos_estabilizadores():
        F  = fmt.fuerza_lineal(fila["fuerza"])[0]
        M  = fmt.momento_lineal(fila["momento"])[0]
        momentos_estabilizadores.append([
            fila["nombre"], fila["categoria"], fila["tipo"],
            f"{F:.2f}", f"{fila['brazo']:.2f}", f"{M:.2f}",
        ])
    momentos_volcadores = []
    for fila in sistema.tabla_momentos_volcadores():
        F  = fmt.fuerza_lineal(fila["fuerza"])[0]
        M  = fmt.momento_lineal(fila["momento"])[0]
        momentos_volcadores.append([
            fila["nombre"], fila["categoria"], fila["tipo"],
            f"{F:.2f}", f"{fila['brazo']:.2f}", f"{M:.2f}",
        ])
    # Versiones raw (lista de dicts, en SI) para el frontend JS
    momentos_estabilizadores_raw = sistema.tabla_momentos_estabilizadores()
    momentos_volcadores_raw      = sistema.tabla_momentos_volcadores()

    # ─── Combinaciones ──────────────────────────────────────────────
    def _comb_rows(res_list):
        rows = []
        for r in res_list:
            V  = fmt.fuerza_lineal(r.V_total)[0]
            H  = fmt.fuerza_lineal(r.H_total)[0]
            MR = fmt.momento_lineal(r.M_estabilizador)[0]
            Mo = fmt.momento_lineal(r.M_volcador)[0]
            rows.append([r.combinacion.nombre, f"{V:.2f}", f"{H:.2f}",
                         f"{MR:.2f}", f"{Mo:.2f}"])
        return rows
    def _comb_raw(r):
        return {
            "nombre": r.combinacion.nombre,
            "V_kN":  r.V_total,
            "H_kN":  r.H_total,
            "MR_kNm": r.M_estabilizador,
            "Mo_kNm": r.M_volcador,
        }
    combinaciones_elu = _comb_rows(res_elu)
    combinaciones_els = _comb_rows(res_els)
    combinaciones_elu_raw = [_comb_raw(r) for r in res_elu]
    combinaciones_els_raw = [_comb_raw(r) for r in res_els]

    # ─── Verificaciones ─────────────────────────────────────────────
    verificaciones = []
    for r in (reporte.volcamiento, reporte.deslizamiento,
              reporte.capacidad_carga, reporte.excentricidad):
        verificaciones.append([
            r.verificacion,
            f"{r.valor_calculado:.3f}",
            f"{r.valor_requerido:.2f}",
            r.unidades,
            r.estado.value,
        ])
    # Versión raw (lista de dicts) — mismo formato que voladizo, para que
    # el frontend la procese con .map() sin necesidad de un branch especial.
    def _ver_raw(v):
        return {
            "nombre": v.verificacion,
            "valor": v.valor_calculado,
            "requerido": v.valor_requerido,
            "unidades_si": v.unidades,
            "estado": v.estado.value,
            "referencia": v.detalle.get("referencia", ""),
        }
    verificaciones_raw = [
        _ver_raw(reporte.volcamiento),
        _ver_raw(reporte.deslizamiento),
        _ver_raw(reporte.capacidad_carga),
        _ver_raw(reporte.excentricidad),
    ]

    # ─── Totales de momentos ────────────────────────────────────────
    SV = sistema.suma_vertical()
    SH_neta = (sistema.suma_horizontal_empuje()
               - sistema.suma_horizontal_resistente())
    SH_emp  = sistema.suma_horizontal_empuje()
    SH_pas  = sistema.suma_horizontal_resistente()
    SMR = sistema.momento_estabilizador()
    SMo = sistema.momento_volcador()
    totales_momentos = {
        "SV":  fmt.fuerza_lineal(SV)[0],
        "SH":  fmt.fuerza_lineal(SH_neta)[0],
        "SH_empuje":   fmt.fuerza_lineal(SH_emp)[0],
        "SH_pasivo":   fmt.fuerza_lineal(SH_pas)[0],
        "SMR": fmt.momento_lineal(SMR)[0],
        "SMo": fmt.momento_lineal(SMo)[0],
        "FS_volcamiento": reporte.volcamiento.valor_calculado,
        "FS_requerido":   reporte.volcamiento.valor_requerido,
    }

    # ─── Resumen del muro (formato dict para portada PDF) ───────────
    g = muro.geometria
    muro_resumen = {
        "Tipo de muro": "Gravedad (cuerpo trapezoidal)",
        "H total (m)":  f"{g.H_total:.2f}",
        "B total (m)":  f"{g.B:.2f}",
        "Altura cuerpo (m)":   f"{g.H_muro:.2f}",
        "Espesor zapata (m)":  f"{g.e_zapata:.2f}",
        "Corona del cuerpo (m)":   f"{g.b_corona:.2f}",
        "Acartelado frontal (m)":  f"{g.a_frontal:.2f}",
        "Acartelado posterior (m)": f"{g.a_posterior:.2f}",
        "Puntera (m)": f"{g.b_puntera:.2f}",
        "Talón (m)":   f"{g.b_talon:.2f}",
        "β (cara posterior, °)":   f"{g.beta_grados:.1f}",
        "Profundidad desplante D (m)": f"{g.D:.2f}",
    }
    muro_resumen.update({
        "Relleno": (
            f"γ={fmt.fmt_densidad_suelo(muro.suelo_relleno.gamma)}, "
            f"φ={muro.suelo_relleno.phi}°, "
            f"c'={fmt.fmt_presion(muro.suelo_relleno.cohesion)}"),
        "Cimentación": (
            f"γ={fmt.fmt_densidad_suelo(muro.suelo_cimentacion.gamma)}, "
            f"φ={muro.suelo_cimentacion.phi}°, "
            f"c'={fmt.fmt_presion(muro.suelo_cimentacion.cohesion)}"),
        "Concreto": (
            f"f'c = {fmt.fmt_fc(muro.concreto.fc)}, "
            f"γ = {fmt.fmt_gamma_concreto(muro.concreto.gamma)}"),
        "Acero": f"fy = {fmt.fmt_fy(muro.acero.fy)}",
        "Inclinación relleno α (°)": f"{muro.condiciones.alpha}",
        f"Sobrecarga ({fmt.u_presion})": (
            f"{fmt.presion(muro.condiciones.sobrecarga)[0]:.2f}"),
    })

    # ─── Presiones ──────────────────────────────────────────────────
    qp_v, qp_u = fmt.presion(reporte.presiones["q_puntera"])
    qt_v, qt_u = fmt.presion(reporte.presiones["q_talon"])
    sv_v, sv_u = fmt.fuerza_lineal(reporte.presiones["SV"])
    presiones = {
        f"q_puntera ({qp_u})":     round(qp_v, 2),
        f"q_talón ({qt_u})":       round(qt_v, 2),
        "B_efectivo = B - 2e (m)": round(reporte.presiones["B_prima"], 2),
        "Excentricidad e (m)":     round(reporte.presiones["e"], 2),
        f"ΣV ({sv_u})":            round(sv_v, 2),
    }
    presiones_raw = {
        "q_puntera_kPa": reporte.presiones["q_puntera"],
        "q_talon_kPa":   reporte.presiones["q_talon"],
        "q_max_kPa":     reporte.presiones.get("q_max"),
        "qu_kPa":        reporte.capacidad_carga.detalle.get("qu_kPa", 0.0),
        "B_prima_m":     reporte.presiones["B_prima"],
        "e_m":           reporte.presiones["e"],
        "SV_kN":         reporte.presiones["SV"],
        "redistribuido": reporte.presiones.get("redistribuido", False),
        # Para el frontend de gravedad
        "B_m":           muro.B,
    }

    # Resumen numérico para que el frontend formatee
    muro_resumen_raw = {
        "tipo_muro": "gravedad",
        "H_total_m": g.H_total,
        "B_total_m": g.B,
        "H_muro_m": g.H_muro,
        "e_zapata_m": g.e_zapata,
        "b_corona_m": g.b_corona,
        "a_frontal_m": g.a_frontal,
        "a_posterior_m": g.a_posterior,
        "b_puntera_m": g.b_puntera,
        "b_talon_m": g.b_talon,
        "D_m": g.D,
        "beta_grados": g.beta_grados,
        "relleno_gamma_kNm3":  muro.suelo_relleno.gamma,
        "relleno_phi_grados":  muro.suelo_relleno.phi,
        "relleno_cohesion_kPa":muro.suelo_relleno.cohesion,
        "ciment_gamma_kNm3":   muro.suelo_cimentacion.gamma,
        "ciment_phi_grados":   muro.suelo_cimentacion.phi,
        "ciment_cohesion_kPa": muro.suelo_cimentacion.cohesion,
        "concreto_fc_MPa":     muro.concreto.fc,
        "concreto_gamma_kNm3": muro.concreto.gamma,
        "acero_fy_MPa":        muro.acero.fy,
        "alpha_grados":        muro.condiciones.alpha,
        "sobrecarga_kPa":      muro.condiciones.sobrecarga,
    }

    return {
        "ok": True,
        "tipo_muro": "gravedad",
        "muro_resumen": muro_resumen,
        "muro_resumen_raw": muro_resumen_raw,
        "sismo_resumen": None,                  # gravedad-sismo: futuro
        "incluye_sismo": False,
        "cargas_rows": cargas_rows,
        "cargas_raw": cargas_raw,
        # Gravedad: NO se diseña por flexión, así que las combinaciones últimas
        # (ELU) no aplican. Se mantienen las de servicio (ELS) para verificar
        # presiones admisibles del suelo.
        "combinaciones_elu": [],
        "combinaciones_els": combinaciones_els,
        "combinaciones_elu_raw": [],
        "combinaciones_els_raw": combinaciones_els_raw,
        "verificaciones": verificaciones,
        "verificaciones_raw": verificaciones_raw,
        "totales_momentos": totales_momentos,
        "momentos_estabilizadores": momentos_estabilizadores,
        "momentos_volcadores": momentos_volcadores,
        "momentos_estabilizadores_raw": momentos_estabilizadores_raw,
        "momentos_volcadores_raw":      momentos_volcadores_raw,
        "presiones": presiones,
        "presiones_raw": presiones_raw,
        "deslizamiento_detalle": desliz_detalle,
        "capacidad_carga_detalle": capcar_detalle,
        "excentricidad_detalle": exc_detalle,
        "diseno_detalle": None,                 # no aplica
        "resultado_global": {
            "estado": "APROBADO" if reporte.cumple_todas else "REVISAR",
            "estabilidad": "APROBADO" if reporte.cumple_todas else "REVISAR",
            "diseno": "No aplica (muro de gravedad)",
        },
        "diseno": [],                           # no aplica
        "diseno_raw": [],                       # no aplica (lista vacía)
        "imagen_muro": f"data:image/png;base64,{img_b64}",
        "imagen_muro_raw": img_b64,
        "imagen_muro_nombres_raw": img_nombres_b64,
        "imagen_muro_cotas_raw":   img_cotas_b64,
        "imagen_empujes_raw":      img_emp_b64,
        "imagen_sismo_raw":        img_sis_b64,
        "imagen_esfuerzos_zapata_raw": "",      # no se genera para gravedad
    }


def ejecutar_analisis(datos: dict) -> dict:
    """Corre el análisis completo y devuelve todos los resultados.

    Toda la app trabaja en MKS de cara al usuario. Internamente se calcula
    en SI; aquí se convierten filas, presiones y parámetros a MKS para
    que el frontend y el reporte muestren tonf, tonf/m², tonf·m/m,
    kgf/cm², ton/m³ según corresponda.
    """
    fmt = FormatoUnidades()
    muro, params_sismo = construir_muro_desde_datos(datos)

    # Cargas — despachador según tipo de muro
    from retaining_wall.models.muro_gravedad import MuroGravedad
    if isinstance(muro, MuroGravedad):
        from retaining_wall.core.cargas_gravedad import CalculadoraCargasGravedad
        # Para gravedad el método estándar de Das es Coulomb (sobre la cara
        # posterior real). Permitimos override desde el payload.
        metodo = datos.get("metodo_empuje", "coulomb")
        calc_cargas = CalculadoraCargasGravedad(muro, metodo_empuje=metodo)
    else:
        calc_cargas = CalculadoraCargas(
            muro, metodo_empuje=datos.get("metodo_empuje", "rankine"))
    sistema = calc_cargas.calcular(incluir_sismo=datos.get("incluir_sismo", False))

    # Estabilidad
    analisis = AnalisisEstabilidad(muro, sistema)
    reporte = analisis.analisis_completo()

    # Desgloses detallados (deslizamiento, capacidad de carga, excentricidad)
    desliz_detalle = analisis.tabla_deslizamiento()
    capcar_detalle = analisis.tabla_capacidad_carga()
    exc_detalle    = analisis.tabla_excentricidad()

    # Reformatear a MKS (parámetros + items; los detalles textuales
    # ``detalle:`` se quedan en SI como traza del cálculo intermedio).
    desliz_detalle = {
        **desliz_detalle,
        "parametros": _reformat_params(desliz_detalle["parametros"], fmt),
        "fuerzas_resistentes": _reformat_items(
            desliz_detalle["fuerzas_resistentes"], fmt, "fuerza_lineal"),
        "fuerzas_actuantes": _reformat_items(
            desliz_detalle["fuerzas_actuantes"], fmt, "fuerza_lineal"),
        "totales": {
            **desliz_detalle["totales"],
            "F_resistente": fmt.fuerza_lineal(
                desliz_detalle["totales"]["F_resistente"])[0],
            "F_actuante": fmt.fuerza_lineal(
                desliz_detalle["totales"]["F_actuante"])[0],
            # FS y FS_min son adimensionales → no se convierten
        },
    }
    capcar_detalle = {
        **capcar_detalle,
        "parametros": _reformat_params(capcar_detalle["parametros"], fmt),
        "terminos": _reformat_items(
            capcar_detalle.get("terminos", []), fmt, "presion"),
        "totales": {
            **capcar_detalle["totales"],
            "qu":    fmt.presion(capcar_detalle["totales"]["qu"])[0],
            "q_max": fmt.presion(capcar_detalle["totales"]["q_max"])[0],
            # FS y FS_min adimensionales
        },
    }
    # Excentricidad: pasos mezclan momentos, fuerzas y longitudes.
    exc_detalle = {
        **exc_detalle,
        "parametros": _reformat_params(exc_detalle["parametros"], fmt),
        "pasos": [
            {**p,
             "valor": (
                 fmt.momento_lineal(p["valor"])[0] if p.get("unidad") == "kN·m/m"
                 else fmt.fuerza_lineal(p["valor"])[0] if p.get("unidad") == "kN/m"
                 else p["valor"]),
             "unidad": (
                 fmt.u_M_lineal if p.get("unidad") == "kN·m/m"
                 else fmt.u_F_lineal if p.get("unidad") == "kN/m"
                 else p.get("unidad", "")),
            } for p in exc_detalle.get("pasos", [])
        ],
        # totales: e, |e|, límite son todos longitudes (m) — no cambian
    }

    # Combinaciones
    res_elu = AplicadorCombinaciones.aplicar_todas(CombinacionesNSR10.elu(), sistema)
    res_els = AplicadorCombinaciones.aplicar_todas(CombinacionesNSR10.els(), sistema)

    # ──────────────────────────────────────────────────────────────────
    # MURO DE GRAVEDAD — flujo simplificado (MVP)
    # No incluye diseño estructural (los muros de gravedad típicamente no
    # llevan armadura por flexión; resisten por su propio peso). Tampoco
    # genera el dibujo del muro ni el diagrama de esfuerzos en la zapata
    # por ahora — eso quedará para un siguiente paso.
    # ──────────────────────────────────────────────────────────────────
    if isinstance(muro, MuroGravedad):
        return _resultado_gravedad(
            muro, sistema, reporte, fmt,
            desliz_detalle, capcar_detalle, exc_detalle,
            res_elu, res_els, datos,
        )

    # Diseño estructural
    disenador = DisenadorMuroVoladizo(
        muro,
        metodo_empuje=datos.get("metodo_empuje", "rankine"),
    )
    reporte_dis = disenador.disenar(
        q_puntera=reporte.presiones["q_puntera"],
        q_talon=reporte.presiones["q_talon"],
    )

    # Desglose paso a paso del diseño estructural (Mu y cuantía por elemento)
    diseno_detalle = disenador.detalle_diseno_estructural(
        q_puntera=reporte.presiones["q_puntera"],
        q_talon=reporte.presiones["q_talon"],
        reporte=reporte_dis,
    )
    # Reformateo a MKS (fuerzas, momentos, presiones)
    def _conv_paso(p: dict) -> dict:
        u = p.get("unidad", "")
        v = p.get("valor")
        if isinstance(v, (int, float)):
            if u == "kN/m":
                nv, nu = fmt.fuerza_lineal(v)
                return {**p, "valor": nv, "unidad": nu}
            if u == "kN·m/m":
                nv, nu = fmt.momento_lineal(v)
                return {**p, "valor": nv, "unidad": nu}
            if u == "kPa":
                nv, nu = fmt.presion(v)
                return {**p, "valor": nv, "unidad": nu}
            if u == "kN/m³":
                nv, nu = fmt.densidad_suelo(v)
                return {**p, "valor": nv, "unidad": nu}
            if u == "MPa":
                # R_n siempre se reporta en MPa (esfuerzo nominal),
                # tal como aparece en la fórmula del ACI/NSR-10.
                return p
        return p
    for k in ("vastago", "punta", "talon"):
        diseno_detalle[k] = {
            **diseno_detalle[k],
            "datos_entrada": [_conv_paso(p) for p in diseno_detalle[k]["datos_entrada"]],
            "pasos_mu":      [_conv_paso(p) for p in diseno_detalle[k]["pasos_mu"]],
            "pasos_cuantia": [_conv_paso(p) for p in diseno_detalle[k]["pasos_cuantia"]],
        }

    # Diagrama de esfuerzos en la zapata
    fig_zap = dibujar_esfuerzos_zapata(
        muro,
        q_puntera=reporte.presiones["q_puntera"],
        q_talon=reporte.presiones["q_talon"],
        Mu_punta=reporte_dis.punta.flexion.Mu,
        Mu_talon=reporte_dis.talon.flexion.Mu,
    )
    png_zap = figura_a_png(fig_zap)
    img_zap_b64 = base64.b64encode(png_zap).decode("ascii")


    # Dibujo del muro para la interfaz (modo numérico, un poco más alejado)
    fig = dibujar_muro(muro, mostrar_empujes=True, modo="numerico")
    png_bytes = figura_a_png(fig)
    img_b64 = base64.b64encode(png_bytes).decode("ascii")

    # Dibujo para el reporte PDF: versión con nombres de las partes
    # y versión con cotas numéricas (tamaño más grande).
    fig_nombres = dibujar_muro(muro, mostrar_empujes=False,
                               figsize=(16, 11), modo="nombres")
    png_nombres = figura_a_png(fig_nombres)
    img_nombres_b64 = base64.b64encode(png_nombres).decode("ascii")

    fig_cotas = dibujar_muro(muro, mostrar_empujes=True,
                             figsize=(16, 11), modo="cotas")
    png_cotas = figura_a_png(fig_cotas)
    img_cotas_b64 = base64.b64encode(png_cotas).decode("ascii")

    # Diagrama de empujes laterales (triangular activo + sobrecarga + pasivo)
    fig_emp = dibujar_diagrama_empujes(muro)
    png_emp = figura_a_png(fig_emp)
    img_emp_b64 = base64.b64encode(png_emp).decode("ascii")

    # Diagrama de cargas sísmicas (Mononobe-Okabe) — solo si el análisis
    # incluyó sismo; si no, se genera una figura placeholder informativa.
    incluye_sismo = bool(datos.get("incluir_sismo", False)) and muro.condiciones.kh > 0
    fig_sis = dibujar_diagrama_sismo(muro)
    png_sis = figura_a_png(fig_sis)
    img_sis_b64 = base64.b64encode(png_sis).decode("ascii")

    # Cargas (filas para tabla)
    cargas_rows = []
    cargas_raw = []
    for i, c in enumerate(sistema.cargas, start=1):
        mag_out, _ = fmt.fuerza_lineal(c.magnitud)
        cargas_rows.append([
            str(i), c.nombre, f"{mag_out:.2f}",
            c.tipo.value, c.categoria.value,
        ])
        cargas_raw.append({
            "nombre": c.nombre,
            "magnitud_kN": c.magnitud,     # kN/m (SI) para el frontend
            "tipo": c.tipo.value,
            "categoria": c.categoria.value,
        })

    # Combinaciones (filas)
    def _combo_row(r):
        V  = fmt.fuerza_lineal(r.V_total)[0]
        H  = fmt.fuerza_lineal(r.H_total)[0]
        MR = fmt.momento_lineal(r.M_estabilizador)[0]
        Mo = fmt.momento_lineal(r.M_volcador)[0]
        return [
            r.combinacion.nombre,
            f"{V:.2f}", f"{H:.2f}",
            f"{MR:.2f}", f"{Mo:.2f}",
        ]
    def _combo_raw(r):
        return {
            "nombre": r.combinacion.nombre,
            "V_kN": r.V_total,              # kN/m
            "H_kN": r.H_total,              # kN/m
            "MR_kNm": r.M_estabilizador,    # kN·m/m
            "Mo_kNm": r.M_volcador,         # kN·m/m
        }
    combos_elu = [_combo_row(r) for r in res_elu]
    combos_els = [_combo_row(r) for r in res_els]
    combos_elu_raw = [_combo_raw(r) for r in res_elu]
    combos_els_raw = [_combo_raw(r) for r in res_els]

    # Tablas de momentos (desglose del cálculo de FS volcamiento)
    def _mom_row(f: dict) -> list[str]:
        F = fmt.fuerza_lineal(f["fuerza"])[0]
        M = fmt.momento_lineal(f["momento"])[0]
        return [
            f["nombre"],
            f["categoria"],
            f["tipo"],
            f"{F:.2f}",
            f"{f['brazo']:.2f}",    # brazo en m, igual en ambos sistemas
            f"{M:.2f}",
        ]

    filas_est = sistema.tabla_momentos_estabilizadores()
    filas_vol = sistema.tabla_momentos_volcadores()
    momentos_est_rows = [_mom_row(f) for f in filas_est]
    momentos_vol_rows = [_mom_row(f) for f in filas_vol]
    # Los mismos pero numéricos en SI (kN, m, kN·m) — para el frontend JS
    momentos_est_raw = filas_est
    momentos_vol_raw = filas_vol
    SMR = sistema.momento_estabilizador()
    SMo = sistema.momento_volcador()
    FS_volc = SMR / SMo if SMo > 0 else 9999.0
    # Totales convertidos (se usan en el PDF para mostrar ΣM_R y ΣM_o)
    SMR_out = fmt.momento_lineal(SMR)[0]
    SMo_out = fmt.momento_lineal(SMo)[0]
    SV_out  = fmt.fuerza_lineal(sistema.suma_vertical())[0]
    SH_out  = fmt.fuerza_lineal(
        sistema.suma_horizontal_empuje()
        - sistema.suma_horizontal_resistente()
    )[0]

    # Verificaciones: volcamiento y deslizamiento son adimensionales (FS);
    # excentricidad está en m (igual en ambos sistemas); capacidad de carga
    # compara q_max vs q_u (adimensional también, FS) → ninguno requiere
    # conversión numérica. Sólo la unidad mostrada cambia en algunos casos.
    def _ver_row(v):
        return [
            v.verificacion,
            f"{v.valor_calculado:.2f}",
            f"{v.valor_requerido}",
            v.unidades,
            v.estado.value,
        ]
    def _ver_raw(v):
        return {
            "nombre": v.verificacion,
            "valor": v.valor_calculado,
            "requerido": v.valor_requerido,
            "unidades_si": v.unidades,         # "-", "m", etc.
            "estado": v.estado.value,
            "referencia": v.detalle.get("referencia", ""),
        }
    verificaciones_rows = [
        _ver_row(reporte.volcamiento),
        _ver_row(reporte.deslizamiento),
        _ver_row(reporte.capacidad_carga),
        _ver_row(reporte.excentricidad),
    ]
    verificaciones_raw = [
        _ver_raw(reporte.volcamiento),
        _ver_raw(reporte.deslizamiento),
        _ver_raw(reporte.capacidad_carga),
        _ver_raw(reporte.excentricidad),
    ]

    # Diseño estructural
    def _dis_row(el):
        Mu = fmt.momento_lineal(el.flexion.Mu)[0]
        Vu = fmt.fuerza_lineal(el.cortante.Vu)[0]
        phiVc = fmt.fuerza_lineal(el.cortante.phi_Vc)[0]
        return [
            el.nombre,
            f"{Mu:.2f}",
            f"{el.flexion.As_requerido:.0f}",   # mm²/m en ambos sistemas
            f"{Vu:.2f}",
            f"{phiVc:.2f}",
            "OK" if (el.flexion.cumple and el.cortante.cumple) else "REVISAR",
        ]
    def _dis_raw(el):
        return {
            "nombre": el.nombre,
            "Mu_kNm": el.flexion.Mu,           # kN·m/m
            "As_mm2_por_m": el.flexion.As_requerido,
            "Vu_kN": el.cortante.Vu,           # kN/m
            "phi_Vc_kN": el.cortante.phi_Vc,   # kN/m
            "estado": ("OK" if (el.flexion.cumple and el.cortante.cumple)
                       else "REVISAR"),
        }
    diseno_rows = [
        _dis_row(reporte_dis.vastago),
        _dis_row(reporte_dis.punta),
        _dis_row(reporte_dis.talon),
    ]
    diseno_raw = [
        _dis_raw(reporte_dis.vastago),
        _dis_raw(reporte_dis.punta),
        _dis_raw(reporte_dis.talon),
    ]

    # Resumen del muro para portada/reporte
    g = muro.geometria
    muro_resumen = {
        "H total (m)": f"{muro.H:.2f}",
        "B total (m)": f"{muro.B:.2f}",
        "Altura vástago (m)": f"{g.H_vastago:.2f}",
        "Altura relleno retenido (m)": f"{g.H_relleno_ef:.2f}",
        "Espesor zapata (m)": f"{g.e_zapata:.2f}",
        "Puntera (m)": f"{g.b_puntera:.2f}",
        "Talón (m)": f"{g.b_talon:.2f}",
        "Corona vástago (m)": f"{g.b_corona:.2f}",
        "Base vástago (m)": f"{g.b_base_vast:.2f}",
        "Profundidad desplante D (m)": f"{g.D:.2f}",
        "Lado del acartelado": ("Cara vista (cara posterior vertical)"
                                if g.cara_posterior_vertical
                                else "Contra terreno (cara frontal vertical)"),
    }
    if g.tiene_diente:
        muro_resumen["Diente de cortante"] = (
            f"h = {g.h_diente:.2f} m × b = {g.b_diente:.2f} m "
            f"(x = {g.x_diente_ef:.2f} m)"
        )
    muro_resumen.update({
        "Relleno": (
            f"γ={fmt.fmt_densidad_suelo(muro.suelo_relleno.gamma)}, "
            f"φ={muro.suelo_relleno.phi}°, "
            f"c'={fmt.fmt_presion(muro.suelo_relleno.cohesion)}"),
        "Cimentación": (
            f"γ={fmt.fmt_densidad_suelo(muro.suelo_cimentacion.gamma)}, "
            f"φ={muro.suelo_cimentacion.phi}°, "
            f"c'={fmt.fmt_presion(muro.suelo_cimentacion.cohesion)}"),
        "Concreto": (
            f"f'c = {fmt.fmt_fc(muro.concreto.fc)}, "
            f"γ = {fmt.fmt_gamma_concreto(muro.concreto.gamma)}"),
        "Acero": f"fy = {fmt.fmt_fy(muro.acero.fy)}",
        "Inclinación relleno α (°)": f"{muro.condiciones.alpha}",
        f"Sobrecarga ({fmt.u_presion})": (
            f"{fmt.presion(muro.condiciones.sobrecarga)[0]:.2f}"),
    })

    sismo_resumen = params_sismo.resumen() if params_sismo else None

    qp_v, qp_u = fmt.presion(reporte.presiones["q_puntera"])
    qt_v, qt_u = fmt.presion(reporte.presiones["q_talon"])
    sv_v, sv_u = fmt.fuerza_lineal(reporte.presiones["SV"])
    presiones_redondeadas = {
        f"q_puntera ({qp_u})":     round(qp_v, 2),
        f"q_talón ({qt_u})":       round(qt_v, 2),
        "B_efectivo = B - 2e (m)": round(reporte.presiones["B_prima"], 2),
        "Excentricidad e (m)":     round(reporte.presiones["e"], 2),
        f"ΣV ({sv_u})":            round(sv_v, 2),
    }
    presiones_raw = {
        "q_puntera_kPa": reporte.presiones["q_puntera"],
        "q_talon_kPa": reporte.presiones["q_talon"],
        "q_max_kPa": reporte.presiones.get("q_max"),
        "B_prima_m": reporte.presiones["B_prima"],
        "e_m": reporte.presiones["e"],
        "SV_kN": reporte.presiones["SV"],
        "redistribuido": reporte.presiones.get("redistribuido", False),
    }

    # Resumen numérico para que el frontend formatee con unidades elegidas
    muro_resumen_raw = {
        "H_total_m": muro.H,
        "B_total_m": muro.B,
        "H_vastago_m": g.H_vastago,
        "H_relleno_m": g.H_relleno_ef,
        "e_zapata_m": g.e_zapata,
        "b_puntera_m": g.b_puntera,
        "b_talon_m": g.b_talon,
        "b_corona_m": g.b_corona,
        "b_base_vast_m": g.b_base_vast,
        "D_m": g.D,
        "relleno_gamma_kNm3": muro.suelo_relleno.gamma,
        "relleno_phi_deg": muro.suelo_relleno.phi,
        "relleno_cohesion_kPa": muro.suelo_relleno.cohesion,
        "ciment_gamma_kNm3": muro.suelo_cimentacion.gamma,
        "ciment_phi_deg": muro.suelo_cimentacion.phi,
        "ciment_cohesion_kPa": muro.suelo_cimentacion.cohesion,
        "concreto_fc_MPa": muro.concreto.fc,
        "concreto_gamma_kNm3": muro.concreto.gamma,
        "acero_fy_MPa": muro.acero.fy,
        "alpha_deg": muro.condiciones.alpha,
        "sobrecarga_kPa": muro.condiciones.sobrecarga,
        "lado_acartelado": ("cara_vista" if g.cara_posterior_vertical
                            else "terreno"),
    }

    estado_global = ("MURO APROBADO ✓"
                     if reporte.cumple_todas and reporte_dis.cumple_todo
                     else "MURO NO APROBADO ✗")

    return {
        "ok": True,
        "muro_resumen": muro_resumen,
        "muro_resumen_raw": muro_resumen_raw,
        "sismo_resumen": sismo_resumen,
        "imagen_muro": f"data:image/png;base64,{img_b64}",
        "imagen_muro_raw": img_b64,
        "imagen_muro_nombres_raw": img_nombres_b64,
        "imagen_muro_cotas_raw": img_cotas_b64,
        "imagen_empujes": f"data:image/png;base64,{img_emp_b64}",
        "imagen_empujes_raw": img_emp_b64,
        "imagen_sismo": f"data:image/png;base64,{img_sis_b64}",
        "imagen_sismo_raw": img_sis_b64,
        "imagen_esfuerzos_zapata": f"data:image/png;base64,{img_zap_b64}",
        "imagen_esfuerzos_zapata_raw": img_zap_b64,
        "incluye_sismo": incluye_sismo,
        "cargas_rows": cargas_rows,
        "cargas_raw": cargas_raw,
        "combinaciones_elu": combos_elu,
        "combinaciones_els": combos_els,
        "combinaciones_elu_raw": combos_elu_raw,
        "combinaciones_els_raw": combos_els_raw,
        "verificaciones": verificaciones_rows,
        "verificaciones_raw": verificaciones_raw,
        "presiones": presiones_redondeadas,
        "presiones_raw": presiones_raw,
        "diseno": diseno_rows,
        "diseno_raw": diseno_raw,
        "momentos_estabilizadores": momentos_est_rows,
        "momentos_estabilizadores_raw": momentos_est_raw,
        "momentos_volcadores": momentos_vol_rows,
        "momentos_volcadores_raw": momentos_vol_raw,
        "deslizamiento_detalle": desliz_detalle,
        "capacidad_carga_detalle": capcar_detalle,
        "excentricidad_detalle": exc_detalle,
        "diseno_detalle": diseno_detalle,
        "totales_momentos": {
            "SV":  round(SV_out, 2),
            "SH":  round(SH_out, 2),
            "SMR": round(SMR_out, 2),
            "SMo": round(SMo_out, 2),
            "FS_volcamiento": round(FS_volc, 3) if SMo > 0 else None,
            "FS_requerido": 2.0,
        },
        "totales": {
            "SV": round(sistema.suma_vertical(), 2),
            "SH_empuje": round(sistema.suma_horizontal_empuje(), 2),
            "SH_pasivo": round(sistema.suma_horizontal_resistente(), 2),
            "SMR": round(sistema.momento_estabilizador(), 2),
            "SMo": round(sistema.momento_volcador(), 2),
            "H_prima": round(CalculadoraGeometria(muro).altura_efectiva_rankine(), 2),
        },
        "resultado_global": {
            "estado": estado_global,
            "estabilidad": "CUMPLE ✓" if reporte.cumple_todas else "NO CUMPLE ✗",
            "diseno": "CUMPLE ✓" if reporte_dis.cumple_todo else "NO CUMPLE ✗",
        },
    }


# =============================================================================
# Rutas Flask
# =============================================================================
@app.route("/")
def index():
    resp = app.make_response(render_template("index.html"))
    # Evitar que el navegador cachee el HTML. Los cambios en la UI deben
    # aparecer inmediatamente al refrescar sin tener que hacer Ctrl+F5.
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp


@app.route("/api/health")
def api_health():
    """Endpoint de health-check usado por el shell de CimX (Electron)
    para hacer poll y saber cuándo cargar la UI con seguridad. Siempre
    responde rápido y no toca disco; es seguro pegarle muchas veces."""
    return jsonify({
        "ok": True,
        "service": "CimX backend",
        "version": "1.0.0",
    })


@app.route("/api/vista_previa", methods=["POST"])
def api_vista_previa():
    """Genera sólo la imagen del muro (para vista previa en tiempo real)."""
    try:
        d = request.get_json(force=True)
        muro, _ = construir_muro_desde_datos(d)
        if isinstance(muro, MuroGravedad):
            from retaining_wall.core.dibujo import dibujar_muro_gravedad
            fig = dibujar_muro_gravedad(muro, mostrar_empujes=True,
                                        modo="numerico")
        else:
            fig = dibujar_muro(muro, mostrar_empujes=True, modo="numerico")
        png = figura_a_png(fig)
        img_b64 = base64.b64encode(png).decode("ascii")
        return jsonify({"ok": True, "imagen": f"data:image/png;base64,{img_b64}"})
    except Exception as e:
        return _error_response(e)


@app.route("/api/analizar", methods=["POST"])
def api_analizar():
    """Ejecuta el análisis completo y devuelve todos los resultados."""
    try:
        d = request.get_json(force=True)
        resultado = ejecutar_analisis(d)
        return jsonify(resultado)
    except Exception as e:
        return _error_response(e)


def _construir_pilote_objs(d: dict):
    """Construye (pilote, perfil) desde el payload (SI)."""
    from retaining_wall.models.pilote import PiloteConcreto, PerfilSuelo, EstratoSuelo

    def _f(v, default=0.0):
        return float(v) if v not in (None, "") else default

    estratos = []
    for e in d.get("estratos", []):
        estratos.append(EstratoSuelo(
            tipo=e.get("tipo", "arena"),
            espesor=_f(e.get("espesor")),
            gamma=_f(e.get("gamma")),
            gamma_sat=(_f(e.get("gamma_sat")) if e.get("gamma_sat") not in (None, "") else None),
            phi=_f(e.get("phi")),
            cu=_f(e.get("cu")),
            nombre=str(e.get("nombre", "") or ""),
        ))
    nf = d.get("nivel_freatico")
    perfil = PerfilSuelo(estratos=estratos,
                         nivel_freatico=(_f(nf) if nf not in (None, "") else None))
    pilote = PiloteConcreto(
        D=_f(d.get("D")), L=_f(d.get("L")),
        fc=_f(d.get("fc"), 21.0), fy=_f(d.get("fy"), 420.0),
        n_barras=int(d.get("n_barras", 6) or 6),
        db_long=_f(d.get("db_long"), 19.05),
        tipo_refuerzo=str(d.get("tipo_refuerzo", "espiral") or "espiral"),
        db_trans=_f(d.get("db_trans"), 9.53),
        recubrimiento=_f(d.get("recubrimiento"), 0.075),
    )
    return pilote, perfil


def analizar_pilote_completo(d: dict):
    """Devuelve (pilote, perfil, resultado) ejecutando el análisis completo."""
    from retaining_wall.core.pilote import analizar_pilote

    def _f(v, default=0.0):
        return float(v) if v not in (None, "") else default

    pilote, perfil = _construir_pilote_objs(d)
    resultado = analizar_pilote(
        pilote, perfil,
        P_servicio=_f(d.get("P_servicio")),
        FS=_f(d.get("FS"), 3.0),
        instalacion=str(d.get("instalacion", "perforado") or "perforado"),
        delta_factor=_f(d.get("delta_factor"), 0.6),
        factor_carga=_f(d.get("factor_carga"), 1.5),
    )
    return pilote, perfil, resultado


def construir_pilote_desde_datos(d: dict) -> dict:
    """Análisis de capacidad axial + diseño estructural (solo el resultado)."""
    return analizar_pilote_completo(d)[2]


@app.route("/api/pilote", methods=["POST"])
def api_pilote():
    """Capacidad axial (punta+fuste, multiestrato) y diseño estructural de un pilote."""
    try:
        d = request.get_json(force=True)
        resultado = construir_pilote_desde_datos(d)
        return jsonify({"ok": True, **resultado})
    except Exception as e:
        return _error_response(e)


@app.route("/api/pilote_pdf", methods=["POST"])
def api_pilote_pdf():
    """Genera la memoria de cálculo (PDF) del pilote y la devuelve como descarga."""
    try:
        d = request.get_json(force=True)
        pilote, perfil, resultado = analizar_pilote_completo(d)
        datos = DatosProyecto(
            empresa=d.get("empresa", ""),
            proyecto=d.get("proyecto", ""),
            ubicacion=d.get("ubicacion", ""),
            ingeniero=d.get("ingeniero", ""),
            contratante=d.get("contratante", ""),
        )
        from retaining_wall.core.pilote_reporte import generar_memoria_pilote
        pdf_bytes = generar_memoria_pilote(datos, pilote, perfil, resultado)
        import io
        buffer = io.BytesIO(pdf_bytes)
        buffer.seek(0)
        nombre = (datos.proyecto or "memoria_pilote").replace(" ", "_")
        return send_file(buffer, mimetype="application/pdf",
                         as_attachment=True, download_name=f"{nombre}_pilote.pdf")
    except Exception as e:
        return _error_response(e)


def construir_pilote_diseno_desde_datos(d: dict) -> dict:
    """Diseño estructural de pilotes (geotecnia como entrada) desde el payload (SI)."""
    from retaining_wall.core.pilote import disenar_pilote_estructural

    def _f(v, dv=0.0):
        return float(v) if v not in (None, "") else dv

    return disenar_pilote_estructural(
        P_servicio=_f(d.get("P_servicio")), factor_carga=_f(d.get("factor_carga"), 1.5),
        Pu=_f(d.get("Pu")), f_s=_f(d.get("f_s")), q_p=_f(d.get("q_p")), FS=_f(d.get("FS"), 2.5),
        fc=_f(d.get("fc"), 21.0), fy=_f(d.get("fy"), 420.0), cuantia=_f(d.get("cuantia"), 0.01),
        tipo_refuerzo=str(d.get("tipo_refuerzo", "espiral") or "espiral"),
        db_long=_f(d.get("db_long"), 0.01905), db_trans=_f(d.get("db_trans"), 0.00953),
        recubrimiento=_f(d.get("recubrimiento"), 0.075),
        D=_f(d.get("D")), N=int(_f(d.get("N"))), L_max=_f(d.get("L_max"), 25.0),
    )


@app.route("/api/pilote_diseno", methods=["POST"])
def api_pilote_diseno():
    """Diseño de pilotes: dada la carga y la geotecnia, calcula D, N, L y acero."""
    try:
        d = request.get_json(force=True)
        return jsonify({"ok": True, **construir_pilote_diseno_desde_datos(d)})
    except Exception as e:
        return _error_response(e)


@app.route("/api/pilote_diseno_pdf", methods=["POST"])
def api_pilote_diseno_pdf():
    """Memoria de cálculo (PDF) del diseño de pilotes."""
    try:
        d = request.get_json(force=True)
        resultado = construir_pilote_diseno_desde_datos(d)
        datos = DatosProyecto(
            empresa=d.get("empresa", ""), proyecto=d.get("proyecto", ""),
            ubicacion=d.get("ubicacion", ""), ingeniero=d.get("ingeniero", ""),
            contratante=d.get("contratante", ""),
        )
        from retaining_wall.core.pilote_diseno_reporte import generar_memoria_pilote_diseno
        pdf_bytes = generar_memoria_pilote_diseno(datos, resultado, d)
        import io
        buffer = io.BytesIO(pdf_bytes)
        buffer.seek(0)
        nombre = (datos.proyecto or "memoria_pilotes").replace(" ", "_")
        return send_file(buffer, mimetype="application/pdf",
                         as_attachment=True, download_name=f"{nombre}_pilotes.pdf")
    except Exception as e:
        return _error_response(e)


def construir_zapata_desde_datos(d: dict) -> dict:
    """Diseña una zapata aislada desde el payload (SI)."""
    from retaining_wall.core.zapata import disenar_zapata

    def _f(v, dv=0.0):
        return float(v) if v not in (None, "") else dv

    return disenar_zapata(
        c1=_f(d.get("c1"), 0.40), c2=_f(d.get("c2"), 0.40),
        P_servicio=_f(d.get("P_servicio")), M_servicio=_f(d.get("M_servicio")),
        q_adm=_f(d.get("q_adm"), 200.0),
        fc=_f(d.get("fc"), 21.0), fy=_f(d.get("fy"), 420.0),
        recubrimiento=_f(d.get("recubrimiento"), 0.075), db=_f(d.get("db"), 0.01905),
        B=_f(d.get("B")), L=_f(d.get("L")), h=_f(d.get("h")),
        Df=_f(d.get("Df"), 1.5),
        gamma_suelo=_f(d.get("gamma_suelo"), 18.0),
        gamma_concreto=_f(d.get("gamma_concreto"), 24.0),
        Pu=_f(d.get("Pu")), factor_carga=_f(d.get("factor_carga"), 1.5),
        posicion=str(d.get("posicion", "interior") or "interior"),
    )


@app.route("/api/zapata", methods=["POST"])
def api_zapata():
    """Dimensionamiento geotécnico y diseño estructural de una zapata aislada."""
    try:
        d = request.get_json(force=True)
        return jsonify({"ok": True, **construir_zapata_desde_datos(d)})
    except Exception as e:
        return _error_response(e)


@app.route("/api/zapata_pdf", methods=["POST"])
def api_zapata_pdf():
    """Genera la memoria de cálculo (PDF) de la zapata y la devuelve como descarga."""
    try:
        d = request.get_json(force=True)
        resultado = construir_zapata_desde_datos(d)
        datos = DatosProyecto(
            empresa=d.get("empresa", ""),
            proyecto=d.get("proyecto", ""),
            ubicacion=d.get("ubicacion", ""),
            ingeniero=d.get("ingeniero", ""),
            contratante=d.get("contratante", ""),
        )
        from retaining_wall.core.zapata_reporte import generar_memoria_zapata
        pdf_bytes = generar_memoria_zapata(datos, resultado, d)
        import io
        buffer = io.BytesIO(pdf_bytes)
        buffer.seek(0)
        nombre = (datos.proyecto or "memoria_zapata").replace(" ", "_")
        return send_file(buffer, mimetype="application/pdf",
                         as_attachment=True, download_name=f"{nombre}_zapata.pdf")
    except Exception as e:
        return _error_response(e)


def construir_dado_desde_datos(d: dict) -> dict:
    """Diseña un dado/cabezal de pilotes desde el payload (SI)."""
    from retaining_wall.core.dado import disenar_dado

    def _f(v, dv=0.0):
        return float(v) if v not in (None, "") else dv

    return disenar_dado(
        n_pilotes=int(_f(d.get("n_pilotes"), 4)),
        Dp=_f(d.get("Dp"), 0.45), c1=_f(d.get("c1"), 0.45), c2=_f(d.get("c2"), 0.45),
        Pu=_f(d.get("Pu")), Mux=_f(d.get("Mux")), Muy=_f(d.get("Muy")),
        s=_f(d.get("s")), e=_f(d.get("e")), h=_f(d.get("h")),
        fc=_f(d.get("fc"), 21.0), fy=_f(d.get("fy"), 420.0),
        recubrimiento=_f(d.get("recubrimiento"), 0.075),
        db=_f(d.get("db"), 0.01905), db_col=_f(d.get("db_col"), 0.01905),
        capacidad_pilote=_f(d.get("capacidad_pilote")),
        gamma_concreto=_f(d.get("gamma_concreto"), 24.0),
        factor_peso=_f(d.get("factor_peso"), 1.2),
        posicion=str(d.get("posicion", "interior") or "interior"),
        metodo=str(d.get("metodo", "ambos") or "ambos"),
    )


@app.route("/api/dado", methods=["POST"])
def api_dado():
    """Diseño estructural de un dado/cabezal sobre pilotes."""
    try:
        d = request.get_json(force=True)
        return jsonify({"ok": True, **construir_dado_desde_datos(d)})
    except Exception as e:
        return _error_response(e)


@app.route("/api/dado_pdf", methods=["POST"])
def api_dado_pdf():
    """Genera la memoria de cálculo (PDF) del dado y la devuelve como descarga."""
    try:
        d = request.get_json(force=True)
        resultado = construir_dado_desde_datos(d)
        datos = DatosProyecto(
            empresa=d.get("empresa", ""),
            proyecto=d.get("proyecto", ""),
            ubicacion=d.get("ubicacion", ""),
            ingeniero=d.get("ingeniero", ""),
            contratante=d.get("contratante", ""),
        )
        from retaining_wall.core.dado_reporte import generar_memoria_dado
        pdf_bytes = generar_memoria_dado(datos, resultado, d)
        import io
        buffer = io.BytesIO(pdf_bytes)
        buffer.seek(0)
        nombre = (datos.proyecto or "memoria_dado").replace(" ", "_")
        return send_file(buffer, mimetype="application/pdf",
                         as_attachment=True, download_name=f"{nombre}_dado.pdf")
    except Exception as e:
        return _error_response(e)


@app.route("/api/pdf", methods=["POST"])
def api_pdf():
    """Genera el reporte PDF y lo devuelve como descarga."""
    try:
        d = request.get_json(force=True)
        datos_pdf = DatosProyecto(
            empresa=d.get("empresa", ""),
            proyecto=d.get("proyecto", ""),
            ubicacion=d.get("ubicacion", ""),
            ingeniero=d.get("ingeniero", ""),
            contratante=d.get("contratante", ""),
            observaciones=d.get("observaciones", ""),
            numeracion_prefijo=str(d.get("numeracion_prefijo", "") or "").strip(),
        )
        resultado = ejecutar_analisis(d)
        es_gravedad = resultado.get("tipo_muro") == "gravedad"

        img_bytes = base64.b64decode(resultado["imagen_muro_raw"])
        img_nombres_bytes = base64.b64decode(resultado["imagen_muro_nombres_raw"])
        img_cotas_bytes = base64.b64decode(resultado["imagen_muro_cotas_raw"])
        img_empujes_bytes = base64.b64decode(resultado["imagen_empujes_raw"]) if resultado.get("imagen_empujes_raw") else None
        img_sismo_bytes   = base64.b64decode(resultado["imagen_sismo_raw"])   if resultado.get("imagen_sismo_raw")   else None
        img_zapata_bytes  = (base64.b64decode(resultado["imagen_esfuerzos_zapata_raw"])
                             if resultado.get("imagen_esfuerzos_zapata_raw") else None)

        pdf_bytes = generar_pdf(
            datos=datos_pdf,
            muro_resumen=resultado["muro_resumen"],
            parametros_sismo=resultado["sismo_resumen"],
            cargas_rows=resultado["cargas_rows"],
            combinaciones_elu_rows=resultado["combinaciones_elu"],
            combinaciones_els_rows=resultado["combinaciones_els"],
            verificaciones_rows=resultado["verificaciones"],
            presiones=resultado["presiones"],
            diseno_rows=resultado["diseno"],
            resultado_global=resultado["resultado_global"],
            imagen_muro_png=img_bytes,
            imagen_muro_nombres_png=img_nombres_bytes,
            imagen_muro_cotas_png=img_cotas_bytes,
            imagen_empujes_png=img_empujes_bytes,
            imagen_sismo_png=img_sismo_bytes,
            incluye_sismo=resultado.get("incluye_sismo", False),
            momentos_estabilizadores_rows=resultado.get("momentos_estabilizadores"),
            momentos_volcadores_rows=resultado.get("momentos_volcadores"),
            totales_momentos=resultado.get("totales_momentos"),
            deslizamiento_detalle=resultado.get("deslizamiento_detalle"),
            capacidad_carga_detalle=resultado.get("capacidad_carga_detalle"),
            excentricidad_detalle=resultado.get("excentricidad_detalle"),
            diseno_detalle=resultado.get("diseno_detalle"),
            imagen_esfuerzos_zapata_png=img_zapata_bytes,
            tipo_muro=resultado.get("tipo_muro", "voladizo"),
        )

        import io
        buffer = io.BytesIO(pdf_bytes)
        buffer.seek(0)
        nombre = (datos_pdf.proyecto or "reporte_muro").replace(" ", "_")
        return send_file(
            buffer, mimetype="application/pdf",
            as_attachment=True,
            download_name=f"{nombre}.pdf",
        )
    except Exception as e:
        return _error_response(e)


@app.route("/api/Fa_Fv", methods=["POST"])
def api_Fa_Fv():
    """Devuelve Fa y Fv para Aa, Av y tipo de suelo dados."""
    try:
        d = request.get_json(force=True)
        Aa = float(d["Aa"])
        Av = float(d["Av"])
        tipo = TipoSueloNSR10(d.get("tipo", "D"))
        return jsonify({
            "ok": True,
            "Fa": round(calcular_Fa(Aa, tipo), 3),
            "Fv": round(calcular_Fv(Av, tipo), 3),
        })
    except Exception as e:
        return _error_response(e)


if __name__ == "__main__":
    print("=" * 60)
    print("  Aplicación de diseño de muros de contención - NSR-10")
    print("=" * 60)
    print("\n  Abre en tu navegador: http://localhost:5000")
    print("  Para detener: Ctrl + C")
    print()
    app.run(host="127.0.0.1", port=5000, debug=False)
