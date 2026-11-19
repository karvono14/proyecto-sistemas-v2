import argparse
import re
import threading
import time

import requests

GREEN, YELLOW, RESET = "\033[32m", "\033[33m", "\033[0m"
# Quita secuencias de escape y caracteres de control del texto de OTROS usuarios (prueba G1):
# un mensaje con "\x1b[2J" podría borrar o falsear el terminal de quien lo lee.
_CTRL = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)?|\x1b.|[\x00-\x08\x0b-\x1f\x7f‪-‮⁦-⁩]")


def clean(text: str) -> str:
    return _CTRL.sub("", text)


def poll(server: str, group: str, seen: set):
    """Pide el historial cada segundo e imprime lo que no ha visto."""
    while True:
        try:
            for m in requests.get(f"{server}/api/messages", timeout=3).json():
                if m["id"] in seen:
                    continue
                seen.add(m["id"])
                mine = m["origin"] == group
                color, mark = (GREEN, " ") if mine else (YELLOW, "*")  # * = otro grupo
                print(f"\r{color}{mark}[{m['lamport']}] {clean(m['from'])}: {clean(m['body'])}{RESET}")
        except requests.RequestException as e:
            print(f"\r[cliente] sin conexión con el servidor: {e}")
        time.sleep(1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--server", default="http://localhost:8000")
    ap.add_argument("--user", required=True)
    args = ap.parse_args()

    group = requests.get(f"{args.server}/api/info", timeout=3).json()["group"]
    requests.post(f"{args.server}/api/users", json={"name": args.user}, timeout=3)  # 409 si ya existe: ok
    print(f"Conectado como {args.user}@{group}. Escribe y pulsa Enter (Ctrl+C sale). * = otro grupo.")

    threading.Thread(target=poll, args=(args.server, group, set()), daemon=True).start()
    while True:
        body = input()
        if not body.strip():
            continue
        r = requests.post(f"{args.server}/api/messages", json={"user": args.user, "body": body}, timeout=3)
        if r.status_code != 201:
            print(f"[cliente] error {r.status_code}: {r.text}")


if __name__ == "__main__":
    main()
