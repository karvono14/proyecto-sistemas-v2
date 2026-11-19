#!/usr/bin/env python3
"""Ejecuta las pruebas de docs/PRUEBAS.md contra el laboratorio local. Desde la RAÍZ del repo:

    python tests/run_tests.py --list
    python tests/run_tests.py A2 A3 B1              # pruebas concretas
    python tests/run_tests.py --cat A               # una categoría
    python tests/run_tests.py --all                 # todas menos las pesadas/destructivas
    python tests/run_tests.py B5 --b5-sizes 1000 10000 100000
    python tests/run_tests.py --all --reset-first   # parte de un laboratorio limpio

Resultados: tests/results/results.csv (una fila por ejecución) y tests/results/<ID>.csv (detalle).
Estados: PASS / FAIL (el sistema incumple) / INFO (medición, anota el valor) / SKIP / ERROR (falló el entorno).
"""
import argparse
import csv
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, "experiment")
import lab  # noqa: E402
import test_a, test_b, test_c, test_d, test_e, test_f, test_g  # noqa: E402,F401  (registran sus pruebas)
from framework import REGISTRY, run_one  # noqa: E402

FIELDS = ["test_id", "title", "started_utc", "status", "duration_s", "observed", "failures"]


def natural(tid: str):
    m = re.match(r"([A-Z]+)(\d+)", tid)
    return (m.group(1), int(m.group(2)))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ids", nargs="*")
    ap.add_argument("--cat", help="letra de la categoría (A a G)")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--reset-first", action="store_true", help="limpia el laboratorio (down -v) antes de empezar")
    ap.add_argument("--max-body-mb", type=int, default=1, help="A4: tamaño máximo de body a probar (MB)")
    ap.add_argument("--b5-sizes", type=int, nargs="+", default=[1000, 10000, 50000], help="B5: totales acumulados")
    ap.add_argument("--e5-sizes", type=int, nargs="+", default=[10000, 50000], help="E5: totales en el central")
    args = ap.parse_args()
    lab.OPTS.update(max_body_mb=args.max_body_mb, b5_sizes=args.b5_sizes, e5_sizes=args.e5_sizes)

    order = sorted(REGISTRY, key=natural)
    if args.list:
        for tid in order:
            s = REGISTRY[tid]
            flag = " [pesada/destructiva: se pide por ID]" if s["heavy"] or s["reset_after"] else ""
            print(f"{tid:4} {s['title']}{flag}")
        return
    if args.ids:
        chosen = args.ids
    elif args.cat:
        chosen = [t for t in order if t.startswith(args.cat.upper()) and not REGISTRY[t]["heavy"]]
    elif args.all:
        chosen = [t for t in order if not REGISTRY[t]["heavy"] and not REGISTRY[t]["reset_after"]]
    else:
        ap.error("indica IDs, --cat o --all (o --list)")
    unknown = [t for t in chosen if t not in REGISTRY]
    if unknown:
        sys.exit(f"pruebas desconocidas: {unknown}")

    if not os.path.exists(lab.COMPOSE_FILE):
        sys.exit(f"ejecuta desde la raíz del repo (no encuentro {lab.COMPOSE_FILE})")
    if args.reset_first:
        print("[tests] limpiando laboratorio...")
        lab.reset()
    else:
        lab.wait_ready()
        lab.ensure_users()

    os.makedirs(lab.RESULTS_DIR, exist_ok=True)
    out = os.path.join(lab.RESULTS_DIR, "results.csv")
    new = not os.path.exists(out)
    with open(out, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if new:
            w.writeheader()
        for tid in chosen:
            print(f"[{tid}] {REGISTRY[tid]['title']} ...", flush=True)
            row = run_one(tid)
            w.writerow(row)
            f.flush()
            print(f"    -> {row['status']} ({row['duration_s']} s) {row['observed']}")
            if row["failures"]:
                print(f"    !! {row['failures']}")
            if REGISTRY[tid]["reset_after"]:
                print("    (esta prueba altera datos/reloj: limpiando laboratorio)")
                lab.reset()
    print(f"\nResultados en {out}")


if __name__ == "__main__":
    main()
