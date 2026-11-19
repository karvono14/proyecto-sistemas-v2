#!/usr/bin/env python3
"""Experimento (a): ¿cuántos mensajes se pierden o se duplican cuando el servidor del grupo
(gSPAa) se cae unos segundos?

Un script envía mensajes desde OTRO servidor (gSPAb) a tasa fija mientras gSPAa se mata
(docker compose kill = SIGKILL) y se vuelve a levantar. Después se cuentan los que faltan o sobran.

Ejecutar desde la RAÍZ del repo, con el laboratorio local arriba:
    docker compose -f docker-compose.local.yml up --build -d
    python experiment/run_experiment.py --down 2 5 10 --reps 3 --history-sync both
Requiere: pip install requests
"""
import argparse
import csv
import os
import re
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime, timezone

import requests

COMPOSE_FILE = "docker-compose.local.yml"
A, B = "http://localhost:8000", "http://localhost:8001"  # A = el que se cae; B = emisor
FIELDS = ["timestamp_utc", "history_sync", "rep", "rate_target_msg_s", "rate_real_msg_s", "down_s",
          "sent", "send_errors", "missing", "extra", "dup_stored", "dup_discarded_fed",
          "dup_discarded_history", "forward_giveups", "recovery_s", "lost_first_s", "lost_last_s"]


def dc(*args, env=None) -> str:
    """Ejecuta docker compose y devuelve stdout+stderr (los logs de Python salen por stderr)."""
    res = subprocess.run(["docker", "compose", "-f", COMPOSE_FILE, *args],
                         capture_output=True, text=True, env={**os.environ, **(env or {})})
    if res.returncode != 0:
        sys.exit(f"[experimento] falló: docker compose {' '.join(args)}\n{res.stderr}")
    return res.stdout + res.stderr


def status(url):
    try:
        r = requests.get(f"{url}/api/status", timeout=2)
        return r.json() if r.status_code == 200 else None
    except (requests.RequestException, ValueError):
        return None


def fetch_msgs(url):
    try:
        r = requests.get(f"{url}/api/messages", timeout=10)
        return r.json() if r.status_code == 200 else None
    except (requests.RequestException, ValueError):
        return None


def wait_ready(timeout=90):
    end = time.time() + timeout
    while time.time() < end:
        sa, sb = status(A), status(B)
        if sa and sb and not sa["central_down"] and not sb["central_down"] and sb["outbox"] == 0:
            return
        time.sleep(1)
    sys.exit("[experimento] los servidores no quedaron listos (¿está el laboratorio levantado?)")


def ensure_stack(history_sync: str) -> None:
    print(f"[experimento] preparando servidores (history_sync={history_sync})")
    dc("up", "-d", "--force-recreate", "server-a", env={"HISTORY_SYNC": "true" if history_sync == "on" else "false"})
    wait_ready()
    requests.post(f"{B}/api/users", json={"name": "emisor"}, timeout=3)  # 409 si ya existe: ok


class Sender(threading.Thread):
    """Envía a tasa fija por B. Guarda el id de cada mensaje que B confirmó (201)."""

    def __init__(self, rate: float, marker: str):
        super().__init__(daemon=True)
        self.interval, self.marker = 1.0 / rate, marker
        self.stop_evt = threading.Event()
        self.sent: dict = {}   # id -> instante de envío (epoch)
        self.errors = 0
        self.t0 = self.t1 = 0.0
        self.http = requests.Session()

    def run(self):
        self.t0 = time.time()
        i, next_t = 0, time.monotonic()
        while not self.stop_evt.is_set():
            try:
                r = self.http.post(f"{B}/api/messages", json={"user": "emisor", "body": f"{self.marker}-{i}"}, timeout=3)
                if r.status_code == 201:
                    self.sent[r.json()["id"]] = time.time()
                else:
                    self.errors += 1
            except requests.RequestException:
                self.errors += 1
            i += 1
            next_t += self.interval
            delay = next_t - time.monotonic()
            if delay > 0:
                self.stop_evt.wait(delay)
        self.t1 = time.time()


def run_rep(rep, rate, down, pre, post, history_sync, recovery_timeout) -> dict:
    marker = "exp" + uuid.uuid4().hex[:8]
    sender = Sender(rate, marker)
    sender.start()
    time.sleep(pre)

    dc("kill", "server-a")                       # caída abrupta (SIGKILL)
    t_kill = time.time()
    time.sleep(down)
    dc("start", "server-a")
    t_start = time.time()
    before = {i for i, t in list(sender.sent.items()) if t < t_start}  # enviados antes de volver

    # Mientras A vuelve: medir cuánto tarda en tener todo lo enviado antes de su regreso.
    recovery_s, t_end_post, deadline = None, t_start + post, t_start + recovery_timeout
    while time.time() < deadline:
        msgs = fetch_msgs(A)
        if recovery_s is None and msgs is not None and before <= {m["id"] for m in msgs}:
            recovery_s = round(time.time() - t_start, 2)
        if not sender.stop_evt.is_set() and time.time() >= t_end_post:
            sender.stop_evt.set()
        if recovery_s is not None and sender.stop_evt.is_set():
            break
        time.sleep(0.5)
    sender.stop_evt.set()
    sender.join()

    # Dar un último margen a lo que aún viaja y contar.
    sent_ids = set(sender.sent)
    while time.time() < deadline:
        msgs = fetch_msgs(A)
        if msgs is not None and sent_ids <= {m["id"] for m in msgs}:
            break
        time.sleep(1)
    msgs = fetch_msgs(A) or []
    mine = [m["id"] for m in msgs if m["body"].startswith(marker + "-")]
    # Diagnóstico: ¿cuándo (segundos desde la caída) se enviaron los mensajes que se perdieron?
    lost_t = sorted(sender.sent[i] - t_kill for i in (sent_ids - set(mine)))
    logs_a, logs_c = dc("logs", "--no-color", "server-a"), dc("logs", "--no-color", "central")
    dups = re.findall(r"DUPLICATE id=(\S+) lamport=\S+ via=(\w+)", logs_a)
    giveups = re.findall(r"FORWARD_GIVEUP server=gSPAa id=(\S+)", logs_c)
    return {
        "timestamp_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "history_sync": history_sync, "rep": rep, "rate_target_msg_s": rate,
        "rate_real_msg_s": round(len(sent_ids) / max(sender.t1 - sender.t0, 1e-9), 2),
        "down_s": down, "sent": len(sent_ids), "send_errors": sender.errors,
        "missing": len(sent_ids - set(mine)), "extra": len(set(mine) - sent_ids),
        "dup_stored": len(mine) - len(set(mine)),
        "dup_discarded_fed": sum(1 for i, v in dups if i in sent_ids and v == "fed"),
        "dup_discarded_history": sum(1 for i, v in dups if i in sent_ids and v == "history"),
        "forward_giveups": sum(1 for i in giveups if i in sent_ids),
        "recovery_s": "" if recovery_s is None else recovery_s,
        "lost_first_s": round(lost_t[0], 2) if lost_t else "",
        "lost_last_s": round(lost_t[-1], 2) if lost_t else "",
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rate", type=float, nargs="+", default=[10.0], help="tasa de envío (msg/s)")
    ap.add_argument("--down", type=float, nargs="+", default=[2, 5, 10], help="duración de la caída (s)")
    ap.add_argument("--reps", type=int, default=3, help="repeticiones por combinación (mínimo del enunciado: 3)")
    ap.add_argument("--pre", type=float, default=3.0, help="s de tráfico antes de la caída")
    ap.add_argument("--post", type=float, default=8.0, help="s de tráfico después de volver")
    ap.add_argument("--history-sync", choices=["on", "off", "both"], default="both",
                    help="off = grupo de control sin recuperación de historial")
    ap.add_argument("--recovery-timeout", type=float, default=60.0, help="espera máxima (s) a que A se ponga al día")
    ap.add_argument("--out", default="experiment/results/results.csv")
    args = ap.parse_args()

    if not os.path.exists(COMPOSE_FILE):
        sys.exit(f"[experimento] ejecuta desde la raíz del repo (no encuentro {COMPOSE_FILE})")
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    new_file = not os.path.exists(args.out)
    if not new_file:
        with open(args.out, encoding="utf-8") as fh:
            if fh.readline().strip().split(",") != FIELDS:
                sys.exit(f"[experimento] {args.out} tiene otra cabecera (versión anterior del script): usa otro --out")
    modes = ["on", "off"] if args.history_sync == "both" else [args.history_sync]
    try:
        with open(args.out, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS)
            if new_file:
                w.writeheader()
            for hs in modes:
                ensure_stack(hs)
                for rate in args.rate:
                    for down in args.down:
                        for rep in range(1, args.reps + 1):
                            wait_ready()
                            time.sleep(2)
                            row = run_rep(rep, rate, down, args.pre, args.post, hs, args.recovery_timeout)
                            w.writerow(row)
                            f.flush()
                            print(f"[{hs}] tasa={rate} caída={down}s rep={rep}: enviados={row['sent']} "
                                  f"perdidos={row['missing']} dup_descartados="
                                  f"{row['dup_discarded_fed']}+{row['dup_discarded_history']} "
                                  f"recuperación={row['recovery_s'] or 'n/d'}s")
    finally:
        ensure_stack("on")  # dejar el laboratorio con la recuperación de historial ACTIVADA


if __name__ == "__main__":
    main()
