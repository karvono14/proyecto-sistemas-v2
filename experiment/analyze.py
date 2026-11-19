#!/usr/bin/env python3
"""Resume results.csv en una tabla (Markdown) y, si hay matplotlib, genera la gráfica.
Uso: python experiment/analyze.py [experiment/results/results.csv]"""
import csv
import os
import statistics
import sys
from collections import defaultdict

path = sys.argv[1] if len(sys.argv) > 1 else "experiment/results/results.csv"
rows = list(csv.DictReader(open(path, encoding="utf-8")))
if not rows:
    sys.exit("results.csv está vacío")


def f(x):
    return float(x) if x not in ("", None) else None


def fmt(vals):
    vals = [v for v in vals if v is not None]
    return "n/d" if not vals else f"{statistics.mean(vals):.1f} [{min(vals):g}–{max(vals):g}]"


groups = defaultdict(list)
for r in rows:
    groups[(r["history_sync"], f(r["rate_target_msg_s"]), f(r["down_s"]))].append(r)

print("| recuperación de historial | tasa (msg/s) | caída (s) | n | enviados | perdidos | "
      "duplicados descartados | reenvíos abandonados | recuperación (s) |")
print("|---|---|---|---|---|---|---|---|---|")
for (hs, rate, down), g in sorted(groups.items()):
    dup = [f(r["dup_discarded_fed"]) + f(r["dup_discarded_history"]) for r in g]
    print(f"| {hs} | {rate:g} | {down:g} | {len(g)} | {fmt([f(r['sent']) for r in g])} | "
          f"{fmt([f(r['missing']) for r in g])} | {fmt(dup)} | {fmt([f(r['forward_giveups']) for r in g])} | "
          f"{fmt([f(r['recovery_s']) for r in g])} |")
print("\nCada celda: media [mín–máx] sobre las repeticiones. Unidades: mensajes, salvo donde se indica.")

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
except ImportError:
    sys.exit("(matplotlib no instalado: pip install matplotlib para generar la gráfica)")

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.2))
NAMES = {"on": "con recuperación de historial", "off": "sin recuperación (control)"}
for (hs, rate) in sorted({(k[0], k[1]) for k in groups}, reverse=True):
    label = f"{NAMES.get(hs, hs)}, {rate:g} msg/s"
    downs = sorted({k[2] for k in groups if k[0] == hs and k[1] == rate})
    for ax, col in ((ax1, "missing"), (ax2, "recovery_s")):
        if col == "recovery_s" and hs != "on":
            continue  # sin recuperación el servidor no "se pone al día": el tiempo no tiene sentido
        xs, ys, pts = [], [], []
        for d in downs:
            vals = [f(r[col]) for r in groups[(hs, rate, d)] if f(r[col]) is not None]
            pts += [(d, v) for v in vals]
            if vals:
                xs.append(d)
                ys.append(statistics.mean(vals))
        if xs:
            line, = ax.plot(xs, ys, marker="o", label=label)
            ax.scatter([p[0] for p in pts], [p[1] for p in pts], s=16, alpha=.5, color=line.get_color())
ax1.set_xlabel("duración de la caída (s)")
ax1.set_ylabel("mensajes perdidos (unidades)")
ax1.set_title("Mensajes perdidos al final de la prueba")
ax2.set_xlabel("duración de la caída (s)")
ax2.set_ylabel("tiempo de recuperación (s)")
ax2.set_title("Recuperación (solo con historial activo)")
ax2.set_ylim(bottom=0)
ax1.set_ylim(bottom=-1)
for ax in (ax1, ax2):
    ax.grid(alpha=.3)
    ax.legend(fontsize=8)
fig.tight_layout()
out = os.path.join(os.path.dirname(path) or ".", "fig_resultados.png")
try:
    fig.savefig(out, dpi=150)
except OSError:
    out = "fig_resultados.png"
    fig.savefig(out, dpi=150)
print(f"\nGráfica guardada en {out}")
