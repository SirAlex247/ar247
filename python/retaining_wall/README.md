# retaining_wall — Diseño de Muros de Contención NSR-10

Sistema modular en Python para el análisis y diseño de muros de contención
en voladizo conforme a la **NSR-10 (Colombia)**, basado en la teoría clásica
de Rankine/Coulomb y Mononobe-Okabe.

## Estructura del proyecto

```
retaining_wall/
├── __init__.py                 # Exports de alto nivel
├── muro_proyecto.py            # 👈 ARCHIVO QUE DEBES EDITAR Y EJECUTAR
├── models/                     # Entidades del dominio
│   ├── __init__.py
│   ├── material.py             # Concreto, AceroRefuerzo
│   ├── muro.py                 # GeometriaMuro, MuroContencion, CondicionesCarga
│   └── suelo.py                # Suelo
├── core/                       # Motores de cálculo
│   ├── __init__.py
│   ├── geometria.py            # Descomposición en áreas, H' efectivo
│   ├── suelos.py               # Capacidad de carga (Meyerhof/Vesic/Hansen)
│   ├── empujes.py              # Rankine, Coulomb, Mononobe-Okabe
│   ├── cargas.py               # Agregación y categorización de cargas
│   ├── combinaciones.py        # Combinaciones NSR-10 (B.2.3 y B.2.4)
│   ├── estabilidad.py          # FS volcamiento, deslizamiento, capacidad, e
│   └── diseno_estructural.py   # Diseño flexión/cortante NSR-10 Título C
└── utils/                      # Utilidades transversales
    ├── __init__.py
    ├── unidades.py             # Conversión SI ↔ otras unidades
    └── validaciones.py         # Excepciones y validadores del dominio
```

## Requisitos

- Python 3.10 o superior.
- Sin dependencias externas.

## Uso rápido

1. Abre el archivo `muro_proyecto.py`.
2. Edita los valores en la sección "PARÁMETROS DE ENTRADA".
3. Desde la terminal, en la carpeta que contiene a `retaining_wall/`, ejecuta:

   ```
   python -m retaining_wall.muro_proyecto
   ```

Ver la guía detallada `GUIA_DE_USO.md` para instrucciones paso a paso.

## Unidades internas

| Magnitud                      | Unidad  |
|-------------------------------|---------|
| Longitud                      | m       |
| Fuerza                        | kN      |
| Presión / esfuerzo del suelo  | kPa     |
| Peso específico               | kN/m³   |
| Esfuerzo de materiales        | MPa     |
| Ángulos (API pública)         | grados  |
| Momento                       | kN·m    |

## Verificaciones implementadas

| Verificación                         | FS mínimo   |
|--------------------------------------|-------------|
| Volcamiento respecto a la puntera    | FS ≥ 2.0    |
| Deslizamiento a lo largo de la base  | FS ≥ 1.5    |
| Capacidad portante                   | FS ≥ 3.0    |
| Excentricidad                        | abs(e)≤B/6  |

## Combinaciones NSR-10 incluidas

- ELU (B.2.4): 1.4(D+H), 1.2D+1.6L+1.6Lsc+1.6H, 1.2D+1.0E+1.0L+1.0H, 0.9D+1.0E+0.9H
- ELS (B.2.3): D+H+L+Lsc, D+0.7E+H
- Geotécnicas: cargas característica y sísmica sin mayorar

## Diseño estructural (NSR-10 Título C)

- Flexión: cálculo de rho requerida, rho mínima (C.10.5) y rho máxima (0.75·rho_b).
- Cortante: Vc = 0.17·λ·√f'c·b·d (C.11.2.1.1), phi = 0.75.
- Factores de reducción: phi_flexión = 0.90, phi_cortante = 0.75.
