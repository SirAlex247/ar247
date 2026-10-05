"""Runner autónomo de la suite de pruebas CimX — NO requiere pytest.

    python tests/run_all.py

Descubre todas las funciones ``test_*`` de los módulos ``test_*.py`` en esta
carpeta, las ejecuta y reporta PASS/FALLA/ERROR. Devuelve código de salida 0
si todo pasa, 1 si hay algún fallo (apto para CI).

Si tienes pytest instalado, ``pytest tests/`` da una salida más rica; este
runner existe para poder validar sin instalar dependencias extra.
"""
import importlib
import os
import sys
import traceback

# conftest configura sys.path (python/) y el backend Agg de matplotlib.
sys.path.insert(0, os.path.dirname(__file__))
import conftest  # noqa: F401  (efecto secundario: configura el entorno)

MODULOS = [
    "test_combinaciones",
    "test_empujes",
    "test_estabilidad",
    "test_ccp14_muro",
    "test_muro_extras",
    "test_mse",
    "test_muro_anclado",
    "test_zapatas_tipos",
    "test_zapata_estructural",
    "test_placa",
    "test_placa_estructural",
    "test_caisson",
    "test_caisson_estructural",
    "test_pilote_dado_normas",
    "test_dado_estructural",
    "test_pilote_flexocompresion",
    "test_pilote_avanzado",
    "test_maquinas",
    "test_pipeline_muro",
    "test_modulos",
    "test_api",
    "test_das",
    "test_e2e_binario",
]


def main() -> int:
    ok = fallos = errores = saltados = 0
    for nombre_mod in MODULOS:
        try:
            mod = importlib.import_module(nombre_mod)
        except Exception as e:
            print(f"[ERROR IMPORT] {nombre_mod}: {e}")
            errores += 1
            continue

        tests = [(k, v) for k, v in sorted(vars(mod).items())
                 if k.startswith("test_") and callable(v)]
        print(f"\n=== {nombre_mod} ({len(tests)} pruebas) ===")
        for k, fn in tests:
            try:
                fn()
                ok += 1
                print(f"  PASS  {k}")
            except AssertionError as e:
                fallos += 1
                print(f"  FALLA {k}: {e}")
            except Exception as e:
                # Un SkipTest 'casero' (para test_das sin geometría) no es error.
                if type(e).__name__ == "_Saltar":
                    saltados += 1
                    print(f"  SKIP  {k}: {e}")
                else:
                    errores += 1
                    print(f"  ERROR {k}: {type(e).__name__}: {e}")
                    traceback.print_exc()

    total = ok + fallos + errores
    print("\n" + "=" * 60)
    print(f"RESULTADO: {ok}/{total} OK · {fallos} fallos · "
          f"{errores} errores · {saltados} saltados")
    print("=" * 60)
    return 0 if (fallos == 0 and errores == 0) else 1


if __name__ == "__main__":
    sys.exit(main())
