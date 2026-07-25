# Pruebas de CimX

Suite que valida el **motor de cálculo que la app ejecuta realmente** (empujes,
estabilidad, pipeline de muros voladizo/gravedad, y los módulos pilote/zapata/
dado), más el motor de combinaciones NSR-10.

## Cómo correrlas

**Sin instalar nada** (runner autónomo, apto para CI):

```bash
python tests/run_all.py
```

**Con pytest** (salida más rica, si lo tienes instalado):

```bash
pytest
```

> En este equipo el intérprete con las dependencias es
> `C:\Users\user\AppData\Local\Python\bin\python.exe`. El `python` a secas
> puede resolver al stub de Microsoft Store y fallar.

## Qué cubre cada archivo

| Archivo | Tipo | Qué verifica |
|---|---|---|
| `test_combinaciones.py` | unidad | Motor NSR-10 B.2.3/B.2.4 (viento, sismo 100/30, envolventes) |
| `test_empujes.py` | analítico | Ka/Kp Rankine, Coulomb→Rankine, Mononobe-Okabe, fuerzas — contra fórmula cerrada |
| `test_estabilidad.py` | invariantes | Equilibrio de presiones, `B'`, `FS=ΣMR/ΣMo`, y monotonicidad física |
| `test_pipeline_muro.py` | caracterización | Congela salidas de voladizo y gravedad (detecta regresiones) |
| `test_modulos.py` | caracterización | Pilote / zapata / dado end-to-end + identidades |
| `test_das.py` | validación externa | Ejemplos 8.1 y 8.2 de Braja Das (**pendiente de geometría**) |

- **Analítico / invariante**: se contrasta contra la fórmula o una identidad
  física exacta. No depende de la salida del programa.
- **Caracterización**: congela el valor actual (baseline capturado con
  `_capture.py`). Si un cambio de fórmula altera un número, la prueba falla a
  propósito para que el cambio sea consciente. Para regenerar el baseline:
  `python tests/_capture.py`.

## Completar la validación contra Das (`test_das.py`)

Los parámetros de suelo del Ej. 8.1 ya están confirmados (φ=30°, α=10°). Falta
la **geometría de la figura del libro**: abrir `test_das.py` y reemplazar los
`None` de `DAS_8_1` y `DAS_8_2` por las cotas exactas. En cuanto no queden
`None`, las pruebas dejan de saltarse y comparan el FS de volcamiento contra el
valor publicado (2.95 y 2.67) con tolerancia `TOL_FS`.
