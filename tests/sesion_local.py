#!/usr/bin/env python3
"""Sesión de interoperabilidad LOCAL (sustituye a la sesión de clase): 4 grupos con NUESTRO servidor
y el central simulado. Ejecuta las dos pruebas de la sección 7 del enunciado y escribe la bitácora.

    docker compose -f docker-compose.sesion.yml up --build -d
    python tests/sesion_local.py            # escribe docs/BITACORA.md
Requiere: pip install requests. Desde la raíz del repo.
"""
import subprocess
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import requests

COMPOSE = "docker-compose.sesion.yml"
GROUPS = {"gSPAa": 8000, "gSPAb": 8001, "gSPAc": 8002, "gSPAd": 8003}
URL = {g: f"http://localhost:{p}" for g, p in GROUPS.items()}
OUT = "docs/BITACORA.md"
LOG, RESULTS = [], []


def now():
    return datetime.now(timezone.utc).strftime("%H:%M:%S")


def say(msg):
    LOG.append(f"- `{now()}` {msg}")
    print(f"[{now()}] {msg}", flush=True)


def dc(*a):
    r = subprocess.run(["docker", "compose", "-f", COMPOSE, *a], capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"docker compose {' '.join(a)}: {r.stderr}")


def status(g):
    try:
        r = requests.get(URL[g] + "/api/status", timeout=2)
        return r.json() if r.status_code == 200 else None
    except (requests.RequestException, ValueError):
        return None


def msgs(g):
    r = requests.get(URL[g] + "/api/messages", timeout=60)
    r.raise_for_status()
    return r.json()


def wait(pred, timeout):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            if pred():
                return round(time.time() - t0, 1)
        except (requests.RequestException, KeyError, ValueError):
            pass
        time.sleep(0.5)
    return None


def registered():
    """Los 4 grupos figuran en el registro del central (no basta con que ellos crean estarlo)."""
    reg = requests.get("http://localhost:9000/_admin/state", timeout=3).json().get("registry", {})
    return all(g in reg for g in GROUPS)


def ready():
    return registered() and all((s := status(g)) and s["central_down"] is False and s["outbox"] == 0 for g in GROUPS)


def mine(g, mk):
    return [m for m in msgs(g) if mk in m["body"]]


def compare(mk, expected, groups=None):
    """Mismo conjunto, mismo orden, sin repetidos, orden (lamport, origin) en todos."""
    problems, ref = [], None
    for g in groups or GROUPS:
        got = mine(g, mk)
        ids = [m["id"] for m in got]
        if len(ids) != len(set(ids)):
            problems.append(f"{g}: ids repetidos")
        if len(ids) != expected:
            problems.append(f"{g}: {len(ids)} mensajes, esperaba {expected}")
        if got != sorted(got, key=lambda m: (m["lamport"], m["origin"], m["id"])):
            problems.append(f"{g}: no respeta (lamport, origin)")
        if ref is None:
            ref = ids
        elif ids != ref:
            problems.append(f"{g}: orden distinto al de gSPAa")
    return problems


def send(g, user, body):
    r = requests.post(URL[g] + "/api/messages", json={"user": user, "body": body}, timeout=10)
    r.raise_for_status()


def main():
    say("Esperando a que los 4 grupos se registren y queden conectados al central simulado")
    if wait(ready, 180) is None:
        sys.exit("los grupos no quedaron listos: ¿levantaste docker-compose.sesion.yml?")
    for g in GROUPS:
        requests.post(URL[g] + "/api/users", json={"name": "u"}, timeout=5)

    # Prueba 1 (sec. 7): conversación global, mismo orden en todos
    mk = "conv" + uuid.uuid4().hex[:6]
    say(f"PRUEBA 1 conversación global: cada grupo escribe 10 mensajes a la vez ({mk})")
    with ThreadPoolExecutor(16) as ex:
        list(ex.map(lambda a: send(a[0], "u", f"{mk}-{a[0]}-{a[1]}"), [(g, i) for g in GROUPS for i in range(10)]))
    conv = wait(lambda: not compare(mk, 40), 90)
    probs = compare(mk, 40)
    say(f"convergencia: {conv} s" if conv is not None else f"NO convergió: {probs}")
    RESULTS.append(("1. Conversación global (4 grupos × 10 mensajes)", not probs, f"convergencia {conv} s" if conv else "; ".join(probs)))

    # Prueba 2 (sec. 7): caída y recuperación por turnos
    for g in GROUPS:
        mk = "turno" + uuid.uuid4().hex[:6]
        others = [x for x in GROUPS if x != g]
        say(f"PRUEBA 2 turno de {g}: apaga su servidor (SIGKILL); los demás escriben 20 mensajes")
        dc("kill", "server-" + g[-1])
        for i in range(20):
            send(others[i % 3], "u", f"{mk}-{i}")
            time.sleep(0.15)
        time.sleep(3)
        say(f"{g} vuelve")
        dc("start", "server-" + g[-1])
        rec = wait(lambda: not compare(mk, 20), 120)
        probs = compare(mk, 20)
        say(f"{g} recuperado en {rec} s" if rec is not None else f"{g} NO se recuperó: {probs}")
        RESULTS.append((f"2. Caída y recuperación de {g}", not probs, f"recuperación {rec} s" if rec else "; ".join(probs)))
        wait(ready, 120)

    hb = requests.get("http://localhost:9000/_admin/state", timeout=5).json().get("groups", {})
    say(f"Heartbeat del central a los grupos (GET /fed/health): { {k: v['ok'] for k, v in hb.items()} }")
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("# Bitácora de la sesión de interoperabilidad **local**\n\n")
        f.write("> Central **simulado** y 4 grupos que ejecutan **nuestro** servidor. Prueba que nuestro código converge; "
                "**no** prueba interoperabilidad con implementaciones de otros equipos.\n\n")
        f.write(f"Fecha (UTC): {datetime.now(timezone.utc):%Y-%m-%d}\n\n## Resultados\n\n| Prueba | Resultado | Detalle |\n|---|---|---|\n")
        for name, ok, det in RESULTS:
            f.write(f"| {name} | {'PASS' if ok else 'FAIL'} | {det} |\n")
        f.write("\n## Registro de eventos\n\n" + "\n".join(LOG) + "\n\n## Qué funcionó / qué falló / hallazgos\n\n_(completar a mano tras leer los logs: `docker compose -f docker-compose.sesion.yml logs`)_\n")
    print(f"\nBitácora en {OUT}")


if __name__ == "__main__":
    main()
