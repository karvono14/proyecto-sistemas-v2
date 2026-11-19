"""Utilidades comunes de las pruebas (laboratorio local: docker-compose.local.yml)."""
import csv
import os
import subprocess
import time
import uuid
from datetime import datetime, timezone

import requests

COMPOSE_FILE = "docker-compose.local.yml"
A = os.environ.get("LAB_A", "http://localhost:8000")          # gSPAa: el servidor bajo prueba
B = os.environ.get("LAB_B", "http://localhost:8001")          # gSPAb: segundo grupo
CENTRAL = os.environ.get("LAB_CENTRAL", "http://localhost:9000")  # central SIMULADO
RESULTS_DIR = os.environ.get("LAB_RESULTS", "tests/results")
OPTS = {"max_body_mb": 1, "b5_sizes": [1000, 10000, 50000], "e5_sizes": [10000, 50000]}

# Valores por defecto de server/app/config.py. Si cambias variables en el compose, actualízalos aquí.
REQUEST_TIMEOUT, HEALTH_TIMEOUT, HEALTH_INTERVAL, HEALTH_FAILURES, BACKOFF_CAP = 3.0, 2.0, 2.0, 3, 8.0


# --- docker -----------------------------------------------------------------------------------
def dc(*args, env=None, both=False, check=True) -> str:
    """docker compose. both=True devuelve stdout+stderr (necesario para leer logs)."""
    res = subprocess.run(["docker", "compose", "-f", COMPOSE_FILE, *args], capture_output=True, text=True,
                         env={**os.environ, **(env or {})})
    if check and res.returncode != 0:
        raise RuntimeError(f"docker compose {' '.join(args)} falló: {res.stderr.strip()}")
    return res.stdout + res.stderr if both else res.stdout


def docker(*args) -> str:
    res = subprocess.run(["docker", *args], capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"docker {' '.join(args)} falló: {res.stderr.strip()}")
    return res.stdout.strip()


def logs(service: str, since: str = None) -> str:
    args = ["logs", "--no-color"] + (["--since", since] if since else []) + [service]
    return dc(*args, both=True)


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def lines(text: str, needle: str) -> list:
    return [ln for ln in text.splitlines() if needle in ln]


def container_id(service: str) -> str:
    return dc("ps", "-q", service).strip().splitlines()[0]


def network_of(service: str, suffix: str) -> str:
    """Nombre real de la red (<proyecto>_<suffix>) a la que está unido el contenedor del servicio."""
    names = docker("inspect", "-f", "{{range $k,$v := .NetworkSettings.Networks}}{{$k}} {{end}}",
                   container_id(service)).split()
    match = [n for n in names if n.endswith("_" + suffix)]
    if not match:
        raise RuntimeError(f"{service} no está en una red '*_{suffix}' (¿usas el docker-compose.local.yml nuevo?)")
    return match[0]


def container_name(service: str) -> str:
    return docker("inspect", "-f", "{{.Name}}", container_id(service)).lstrip("/")


def container_mem(service: str) -> str:
    """Memoria del contenedor según docker stats (p. ej. '45MiB')."""
    return docker("stats", "--no-stream", "--format", "{{.MemUsage}}", container_id(service)).split("/")[0].strip()


def redis_mem(service: str = "redis-a") -> int:
    out = dc("exec", "-T", service, "redis-cli", "info", "memory")
    for ln in out.splitlines():
        if ln.startswith("used_memory:"):
            return int(ln.split(":")[1])
    raise RuntimeError("no pude leer used_memory de Redis")


# --- servidores ---------------------------------------------------------------------------------
def status(base: str):
    try:
        r = requests.get(base + "/api/status", timeout=2)
        return r.json() if r.status_code == 200 else None
    except (requests.RequestException, ValueError):
        return None


def field(base: str, key: str):
    s = status(base)
    return None if s is None else s[key]


def clock(base: str) -> int:
    v = field(base, "lamport")
    if v is None:
        raise RuntimeError(f"{base} no responde /api/status")
    return v


def all_msgs(base: str) -> list:
    r = requests.get(base + "/api/messages", timeout=60)
    r.raise_for_status()
    return r.json()


def find(base: str, mid: str):
    return next((m for m in all_msgs(base) if m["id"] == mid), None)


def with_marker(msgs: list, mk: str) -> list:
    return [m for m in msgs if mk in m["body"]]


def ids_with(base: str, mk: str) -> list:
    return [m["id"] for m in with_marker(all_msgs(base), mk)]


def marker(tid: str) -> str:
    return f"{tid}-{uuid.uuid4().hex[:8]}"


def new_id() -> str:
    return str(uuid.uuid4())


def make_msg(origin="gTEST", user="u", lamport=1, body="x", id=None, sent_at="2026-01-01T00:00:00Z") -> dict:
    return {"id": id or new_id(), "from": f"{user}@{origin}", "origin": origin, "lamport": lamport,
            "sent_at": sent_at, "body": body}


def fed_post(base: str, payload, raw: bool = False):
    """POST /fed/messages como lo haría el central. raw=True envía el texto tal cual."""
    if raw:
        return requests.post(base + "/fed/messages", data=payload, headers={"content-type": "application/json"},
                             timeout=30)
    return requests.post(base + "/fed/messages", json=payload, timeout=30)


def ensure_user(base: str, name: str) -> None:
    requests.post(base + "/api/users", json={"name": name}, timeout=5)  # 409 si ya existe: ok


def ensure_users() -> None:
    for base, u in ((A, "ana"), (A, "tester"), (B, "beto"), (B, "emisor")):
        ensure_user(base, u)


def send(base: str, user: str, body: str) -> dict:
    r = requests.post(base + "/api/messages", json={"user": user, "body": body}, timeout=10)
    r.raise_for_status()
    return r.json()


# --- central simulado ---------------------------------------------------------------------------
def admin(path: str, method: str = "POST", **params) -> dict:
    r = requests.request(method, CENTRAL + path, params=params, timeout=10)
    r.raise_for_status()
    return r.json()


def attempts(mid: str) -> int:
    return admin(f"/_admin/attempts/{mid}", "GET")["attempts"]


def central_history() -> list:
    return requests.get(CENTRAL + "/history", timeout=30).json()["messages"]


# --- esperas y resultados -------------------------------------------------------------------------
def wait_until(pred, timeout: float, step: float = 0.5):
    """Devuelve los segundos que tardó en cumplirse pred, o None si expiró."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            if pred():
                return round(time.time() - start, 2)
        except (requests.RequestException, KeyError, TypeError, ValueError):
            pass
        time.sleep(step)
    return None


def wait_stable(fn, quiet: float = 6.0, timeout: float = 90.0):
    """Espera a que fn() deje de cambiar durante 'quiet' segundos; devuelve el último valor."""
    start, last, since = time.time(), None, time.time()
    while time.time() - start < timeout:
        try:
            cur = fn()
        except (requests.RequestException, KeyError, ValueError):
            cur = None
        if cur != last:
            last, since = cur, time.time()
        elif time.time() - since >= quiet:
            return last
        time.sleep(1)
    return last


def wait_ready(timeout: float = 120.0) -> None:
    ok = wait_until(lambda: all(s and s["central_down"] is False and s["outbox"] == 0
                                for s in (status(A), status(B))), timeout, 1.0)
    if ok is None:
        raise RuntimeError("los servidores no quedaron listos (¿está el laboratorio levantado?)")


def reset() -> None:
    """Laboratorio limpio: borra volúmenes (usuarios, historial, reloj) y vuelve a levantar."""
    dc("down", "-v")
    dc("up", "-d")
    wait_ready(180)
    ensure_users()


def write_csv(name: str, rows: list) -> str:
    os.makedirs(RESULTS_DIR, exist_ok=True)
    path = os.path.join(RESULTS_DIR, f"{name}.csv")
    keys = list(dict.fromkeys(k for r in rows for k in r))
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)
    return path
