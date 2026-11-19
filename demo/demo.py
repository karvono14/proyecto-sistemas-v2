#!/usr/bin/env python3
"""Demo para el video (≈ 3 min): conversación entre dos grupos, fallo y recuperación.
    docker compose -f docker-compose.local.yml up --build -d
    python demo/demo.py            # Enter avanza cada paso; --auto avanza solo
Para mostrar los logs, abre en otra terminal:  docker compose -f docker-compose.local.yml logs -f server-a server-b
"""
import subprocess
import sys
import time

import requests

A, B = "http://localhost:8000", "http://localhost:8001"
AUTO = "--auto" in sys.argv


def step(txt):
    print(f"\n\033[1;36m== {txt}\033[0m")
    if not AUTO:
        input("   [Enter] ")
    else:
        time.sleep(2)


def dc(*a):
    subprocess.run(["docker", "compose", "-f", "docker-compose.local.yml", *a], check=True, capture_output=True)


def post(base, path, body):
    return requests.post(base + path, json=body, timeout=10)


def show(base, name, last=8):
    print(f"   Historial de {name} (orden lamport, origin):")
    for m in requests.get(base + "/api/messages", timeout=10).json()[-last:]:
        print(f"     [{m['lamport']:>3}] {m['from']}: {m['body']}")


for u, b in (("ana", A), ("beto", B)):
    post(b, "/api/users", {"name": u})
step("1. Ana (gSPAa) y Beto (gSPAb) conversan a través del central")
post(A, "/api/messages", {"user": "ana", "body": "hola desde gSPAa"})
time.sleep(1)
post(B, "/api/messages", {"user": "beto", "body": "hola desde gSPAb"})
time.sleep(1.5)
show(A, "gSPAa")
show(B, "gSPAb")
step("2. FALLO: matamos el servidor de gSPAa (SIGKILL) mientras Beto sigue escribiendo")
dc("kill", "server-a")
for i in range(6):
    post(B, "/api/messages", {"user": "beto", "body": f"mensaje {i} con gSPAa caído"})
    time.sleep(0.5)
show(B, "gSPAb (gSPAa está caído)", 4)
step("3. RECUPERACIÓN: levantamos gSPAa; recupera lo perdido con GET /history")
dc("start", "server-a")
for _ in range(60):
    try:
        if len(requests.get(A + "/api/messages", timeout=2).json()) == len(requests.get(B + "/api/messages", timeout=2).json()) >= 8:
            break
    except requests.RequestException:
        pass
    time.sleep(0.5)
show(A, "gSPAa recuperado")
a, b = (requests.get(x + "/api/messages", timeout=10).json() for x in (A, B))
print("\n   ¿Mismos mensajes, mismo orden, sin repetidos?", [m["id"] for m in a] == [m["id"] for m in b] and len({m['id'] for m in a}) == len(a))
step("4. CENTRAL CAÍDO (simulado): los mensajes quedan pendientes y se entregan al volver")
requests.post("http://localhost:9000/_admin/down", timeout=5)
post(A, "/api/messages", {"user": "ana", "body": "escrito con el central caído"})
time.sleep(8)
print("   Estado de gSPAa:", {k: v for k, v in requests.get(A + "/api/status", timeout=5).json().items() if k in ("central_down", "outbox")})
requests.post("http://localhost:9000/_admin/up", timeout=5)
time.sleep(6)
print("   Estado tras volver:", {k: v for k, v in requests.get(A + "/api/status", timeout=5).json().items() if k in ("central_down", "outbox")})
show(B, "gSPAb", 3)
