"""
Análisis lateral no lineal del pilote por CURVAS p-y y diferencias finitas
(método tipo LPILE / Reese & Matlock).

Resuelve la viga sobre resortes no lineales del suelo:

    EI·d⁴y/dz⁴ + E_py(z, y)·y = 0

por diferencias finitas centradas de 4º orden, iterando el módulo secante
E_py de las curvas p-y hasta converger. Devuelve los perfiles de deflexión
y(z), momento M(z) y cortante V(z), y sus valores máximos.

Curvas p-y implementadas (suelo uniforme a lo largo del fuste):
  - Arcilla (Matlock, arcilla blanda):
        p_u = N_p·c_u·D,  N_p = mín(3 + γ'·z/c_u + 0.5·z/D, 9)
        y50 = 2.5·ε50·D,  p = 0.5·p_u·(y/y50)^(1/3) ≤ p_u
  - Arena (modelo simplificado):
        E_py inicial = n_h·z ;  p acotado por p_u = 3·K_p·γ'·z·D (Broms)

Unidades: EI [kN·m²], L, D, z, y [m], p [kN/m], E_py [kN/m²], H [kN], M [kN·m].
"""
from __future__ import annotations

import math

import numpy as np


def _py_arcilla(z, y, *, cu, gamma_ef, D, eps50):
    """Curva p-y de Matlock (arcilla). Devuelve (p, E_py_secante)."""
    y = abs(y)
    Np = min(3.0 + gamma_ef * z / cu + 0.5 * z / D, 9.0) if cu > 0 else 9.0
    pu = Np * cu * D                                   # kN/m
    y50 = 2.5 * eps50 * D
    if y <= 1e-9 or y50 <= 1e-12:
        # rigidez inicial (tangente en el origen, grande pero finita)
        Epy0 = 0.5 * pu / (y50 ** (1.0 / 3.0) * (1e-4) ** (2.0 / 3.0)) if pu > 0 else 0.0
        return 0.0, max(Epy0, 1e-3)
    p = 0.5 * pu * (y / y50) ** (1.0 / 3.0)
    p = min(p, pu)
    return p, p / y


def _py_arena(z, y, *, phi, nh, gamma_ef, D):
    """Curva p-y simplificada (arena): E_py inicial n_h·z, p acotado por el
    empuje pasivo (Broms). Devuelve (p, E_py_secante)."""
    y = abs(y)
    Kp = math.tan(math.radians(45.0 + phi / 2.0)) ** 2
    pu = 3.0 * Kp * gamma_ef * z * D                   # kN/m (cota de flujo)
    Epy_ini = max(nh * z, 1e-3)                        # kN/m²
    if y <= 1e-9:
        return 0.0, Epy_ini
    p = min(Epy_ini * y, pu) if pu > 0 else Epy_ini * y
    return p, p / y


def analisis_py(*, EI, L, D, H, M0=0.0, cabeza="libre",
                tipo="arcilla", gamma=9.0, cu=50.0, eps50=0.01,
                phi=32.0, nh=5000.0, n_nodos=60, max_iter=60, tol=1e-5):
    """Resuelve el pilote lateral por diferencias finitas y curvas p-y.

    Args:
        EI: rigidez a flexión (kN·m²).
        L: longitud embebida (m).  D: diámetro (m).
        H: fuerza horizontal en la cabeza (kN).  M0: momento en la cabeza.
        cabeza: 'libre' o 'fija'.
        tipo: 'arcilla' o 'arena'.
        gamma: peso unitario efectivo del suelo (kN/m³).
        cu, eps50: arcilla.  phi, nh: arena.

    Returns:
        dict con perfiles z, y, M, V (listas) y los máximos.
    """
    if H <= 1e-9 and abs(M0) <= 1e-9:
        return {"aplica": False}

    n = int(max(20, n_nodos))
    h = L / n
    N = n + 1                       # nodos reales 0..n
    # Vector ampliado con 2 nodos fantasma por lado: índice_array = nodo_real + 2
    M = N + 4

    def _resolver(Epy):
        A = np.zeros((M, M))
        b = np.zeros(M)
        c4 = EI / h ** 4
        # Ecuaciones de nodos reales j=0..n  (fila = índice_array i=j+2)
        for j in range(N):
            i = j + 2
            A[i, i - 2] += c4
            A[i, i - 1] += -4.0 * c4
            A[i, i] += 6.0 * c4 + Epy[j]
            A[i, i + 1] += -4.0 * c4
            A[i, i + 2] += c4
        # ---- Condiciones de borde (4 filas: las de los fantasmas) ----
        # Cabeza (nodo real 0 → i=2). Momento M0 y cortante H.
        # Momento: EI/h²·(Y[1]-2Y[2]+Y[3]) = M0   (fila fantasma 1)
        A[1, 1] += EI / h ** 2
        A[1, 2] += -2.0 * EI / h ** 2
        A[1, 3] += EI / h ** 2
        b[1] = M0
        if str(cabeza).startswith("fij"):
            # Cabeza fija: pendiente nula (Y[3]-Y[1])/(2h)=0 → fila fantasma 0
            A[0, 1] += -1.0
            A[0, 3] += 1.0
            b[0] = 0.0
        else:
            # Cabeza libre: cortante V=-EI·y''' = H
            # y'''_0 = (Y[4]-2Y[3]+2Y[1]-Y[0])/(2h³)
            A[0, 4] += -EI / (2.0 * h ** 3)
            A[0, 3] += 2.0 * EI / (2.0 * h ** 3)
            A[0, 1] += -2.0 * EI / (2.0 * h ** 3)
            A[0, 0] += EI / (2.0 * h ** 3)
            b[0] = H
        # Punta (nodo real n → i=N+1). Momento=0 y cortante=0.
        A[M - 2, N] += EI / h ** 2
        A[M - 2, N + 1] += -2.0 * EI / h ** 2
        A[M - 2, N + 2] += EI / h ** 2
        b[M - 2] = 0.0
        A[M - 1, N + 3] += -EI / (2.0 * h ** 3)
        A[M - 1, N + 2] += 2.0 * EI / (2.0 * h ** 3)
        A[M - 1, N] += -2.0 * EI / (2.0 * h ** 3)
        A[M - 1, N - 1] += EI / (2.0 * h ** 3)
        b[M - 1] = 0.0
        Y = np.linalg.solve(A, b)
        return Y

    # Iteración no lineal sobre E_py
    Epy = np.full(N, (nh * 1.0 if tipo == "arena" else 1.0e4))
    y_real = np.zeros(N)
    for _ in range(max_iter):
        Y = _resolver(Epy)
        y_new = Y[2:2 + N]
        Epy_new = np.zeros(N)
        for j in range(N):
            z = j * h + 1e-4
            if tipo == "arena":
                _, e = _py_arena(z, y_new[j], phi=phi, nh=nh, gamma_ef=gamma, D=D)
            else:
                _, e = _py_arcilla(z, y_new[j], cu=cu, gamma_ef=gamma, D=D, eps50=eps50)
            Epy_new[j] = e
        # relajación para estabilidad
        Epy = 0.5 * Epy + 0.5 * Epy_new
        if np.max(np.abs(y_new - y_real)) < tol:
            y_real = y_new
            break
        y_real = y_new

    # Perfiles de momento y cortante (a partir de la deflexión)
    z_arr = np.array([j * h for j in range(N)])
    Yfull = _resolver(Epy)
    yv = Yfull[2:2 + N]
    Mv = np.zeros(N)
    Vv = np.zeros(N)
    for j in range(N):
        i = j + 2
        Mv[j] = EI * (Yfull[i - 1] - 2.0 * Yfull[i] + Yfull[i + 1]) / h ** 2
        Vv[j] = -EI * (Yfull[i + 2] - 2.0 * Yfull[i + 1]
                       + 2.0 * Yfull[i - 1] - Yfull[i - 2]) / (2.0 * h ** 3)

    # Normaliza el signo: deflexión positiva en la dirección de la carga.
    if yv[0] < 0:
        yv, Mv, Vv = -yv, -Mv, -Vv

    jmax = int(np.argmax(np.abs(Mv)))
    # profundidad donde el momento cae a ~10% del máximo (para el refuerzo)
    Mmax = abs(Mv[jmax])
    z_ref = L
    for j in range(jmax, N):
        if abs(Mv[j]) < 0.10 * Mmax:
            z_ref = z_arr[j]
            break
    return {
        "aplica": True, "tipo": tipo, "cabeza": "fija" if str(cabeza).startswith("fij") else "libre",
        "z": [round(float(v), 3) for v in z_arr],
        "y_mm": [round(float(v) * 1000.0, 3) for v in yv],
        "M_kNm": [round(float(v), 2) for v in Mv],
        "V_kN": [round(float(v), 2) for v in Vv],
        "y0_mm": round(float(yv[0]) * 1000.0, 2),
        "Mmax_kNm": round(float(Mmax), 1),
        "z_Mmax_m": round(float(z_arr[jmax]), 2),
        "Vmax_kN": round(float(np.max(np.abs(Vv))), 1),
        "z_refuerzo_m": round(float(z_ref), 2),
    }
