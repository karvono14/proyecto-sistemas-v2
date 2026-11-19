"""CENTRAL SIMULADO para pruebas locales. NO es el oficial: es nuestra lectura del enunciado.
Estado solo en memoria: reiniciarlo pierde registro e historial (HIPÓTESIS)."""
import asyncio
import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import requests
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("central")
app = FastAPI(title="Central simulado (NO OFICIAL)")

FORWARD_RETRIES = int(os.environ.get("FORWARD_RETRIES", "3"))
FORWARD_TIMEOUT = float(os.environ.get("FORWARD_TIMEOUT", "2"))

lock = threading.Lock()
HEARTBEAT_INTERVAL = float(os.environ.get("HEARTBEAT_INTERVAL", "5"))
group_health: dict = {}   # server -> {"ok", "lamport", "checked_at", "fails"}
registry: dict = {}   # server -> url
messages: dict = {}   # id -> mensaje (historial de #general)
state = {"down": False, "delay_ms": 0, "delay_scope": "all", "force_status": 0, "lose_n": 0, "lose_s": 4.5, "forward": True}
attempts: dict = {}   # id -> veces que llegó un POST /messages con ese id (incluye duplicados y forzados)
FORWARD_WORKERS = int(os.environ.get("FORWARD_WORKERS", "32"))
pool = ThreadPoolExecutor(max_workers=FORWARD_WORKERS)


def heartbeat_loop():
    """Fig. 1 del enunciado: el central hace heartbeat hacia los grupos (GET /fed/health).
    SUPUESTO nuestro: solo se registra el estado; no se deja de reenviar a un grupo 'caído'."""
    while True:
        with lock:
            targets = list(registry.items())
        for name, url in targets:
            try:
                r = requests.get(f"{url}/fed/health", timeout=2)
                body = r.json() if r.status_code == 200 else {}
                ok = r.status_code == 200 and body.get("server") == name
                lamport = body.get("lamport") if isinstance(body, dict) else None
            except (requests.RequestException, ValueError):
                ok, lamport = False, None
            with lock:
                prev = group_health.get(name, {"fails": 0})
                group_health[name] = {"ok": ok, "lamport": lamport, "checked_at": time.time(),
                                      "fails": 0 if ok else prev["fails"] + 1}
            if not ok:
                log.warning("HEARTBEAT_FAIL server=%s url=%s", name, url)
        time.sleep(HEARTBEAT_INTERVAL)


threading.Thread(target=heartbeat_loop, daemon=True).start()


@app.middleware("http")
async def chaos(request: Request, call_next):
    """Fallos provocados por script: /_admin/down, /_admin/slow."""
    path = request.url.path
    if not path.startswith("/_admin"):
        if state["delay_ms"] and (state["delay_scope"] == "all" or path == "/messages"):
            await asyncio.sleep(state["delay_ms"] / 1000)
        if state["down"]:
            return JSONResponse(status_code=503, content={"detail": "central simulado caído"})
    return await call_next(request)


@app.exception_handler(RequestValidationError)
async def on_invalid(request: Request, exc: RequestValidationError):
    errors = [{"loc": list(e["loc"]), "msg": e["msg"], "type": e["type"]} for e in exc.errors()]
    log.warning("REJECT path=%s errors=%s", request.url.path, errors[:3])
    return JSONResponse(status_code=422, content={"detail": errors})


class Reg(BaseModel):
    server: StrictStr
    url: StrictStr


class Msg(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    id: StrictStr
    from_: StrictStr = Field(alias="from")
    origin: StrictStr
    lamport: StrictInt
    sent_at: StrictStr
    body: StrictStr


@app.post("/register")
def register(r: Reg):
    with lock:
        registry[r.server] = r.url
    log.info("REGISTER server=%s url=%s", r.server, r.url)
    return {"status": "registered"}


@app.post("/messages")
def post_message(m: Msg):
    msg = {"id": m.id, "from": m.from_, "origin": m.origin, "lamport": m.lamport,
           "sent_at": m.sent_at, "body": m.body}
    with lock:
        attempts[m.id] = attempts.get(m.id, 0) + 1
    if state["force_status"]:  # prueba: respuesta forzada (4xx/5xx) sin guardar
        return JSONResponse(status_code=state["force_status"], content={"detail": "forzado por prueba"})
    with lock:
        if msg["id"] in messages:
            log.info("DUPLICATE id=%s origin=%s", msg["id"], msg["origin"])
            return {"status": "duplicate"}  # idempotente: 200 sin efectos
        messages[msg["id"]] = msg
        targets = [(s, u) for s, u in registry.items() if s != msg["origin"]]  # todos menos el origen
    log.info("ACCEPT id=%s lamport=%s origin=%s -> %s", msg["id"], msg["lamport"], msg["origin"],
             [s for s, _ in targets])
    if state["forward"]:
        for s, u in targets:
            pool.submit(forward, s, u, msg)
    with lock:  # prueba: guardar y reenviar, pero tardar en responder (simula respuesta perdida)
        lose = state["lose_n"] > 0
        if lose:
            state["lose_n"] -= 1
    if lose:
        time.sleep(state["lose_s"])
    return {"status": "accepted"}


def forward(server: str, url: str, msg: dict) -> None:
    for attempt in range(FORWARD_RETRIES + 1):
        try:
            r = requests.post(f"{url}/fed/messages", json=msg, timeout=FORWARD_TIMEOUT)
            if r.status_code < 300:
                log.info("FORWARD_OK server=%s id=%s", server, msg["id"])
                return
            if r.status_code < 500:  # 4xx: no se reintenta
                log.error("FORWARD_REJECTED server=%s id=%s status=%s", server, msg["id"], r.status_code)
                return
        except requests.RequestException as e:
            log.warning("FORWARD_FAIL server=%s id=%s intento=%d %s", server, msg["id"], attempt + 1, type(e).__name__)
        time.sleep(min(8, 0.5 * 2 ** attempt))
    log.error("FORWARD_GIVEUP server=%s id=%s (el grupo debe recuperarlo por /history)", server, msg["id"])


@app.get("/history")
def history(since: int = 0):
    """HIPÓTESIS: 'since' exclusivo, orden (lamport, origin), forma {"messages": [...]}."""
    with lock:
        items = [m for m in messages.values() if m["lamport"] > since]
    items.sort(key=lambda m: (m["lamport"], m["origin"], m["id"]))
    return {"messages": items}


@app.get("/health")
def health():
    return {"status": "ok"}


# --- Control de fallos para las pruebas (no existen en el central real) ---------------
@app.post("/_admin/down")
def admin_down():
    state["down"] = True
    return state


@app.post("/_admin/up")
def admin_up():
    state.update({"down": False, "delay_ms": 0, "delay_scope": "all", "force_status": 0, "lose_n": 0, "forward": True})
    return state


@app.post("/_admin/slow")
def admin_slow(ms: int = 0, scope: str = "all"):
    """scope=all retrasa todo; scope=messages solo POST /messages (el heartbeat sigue sano)."""
    state["delay_ms"], state["delay_scope"] = ms, scope
    return state


@app.post("/_admin/forward")
def admin_forward(on: int = 1):
    """on=0: el central guarda los mensajes pero NO los reenvía (carga de historial en pruebas)."""
    state["forward"] = bool(on)
    return state


@app.post("/_admin/force-status")
def admin_force_status(code: int = 0):
    """POST /messages responde 'code' (400, 503...) sin guardar. 0 = desactivar."""
    state["force_status"] = code
    return state


@app.post("/_admin/lose-response")
def admin_lose_response(n: int = 1, s: float = 4.5):
    """Los próximos n POST /messages se procesan pero la respuesta tarda s segundos (el emisor expira)."""
    state["lose_n"], state["lose_s"] = n, s
    return state


@app.get("/_admin/attempts/{mid}")
def admin_attempts(mid: str):
    return {"id": mid, "attempts": attempts.get(mid, 0)}


@app.post("/_admin/forget-registry")
def admin_forget():
    with lock:
        registry.clear()  # simula un reinicio del central que pierde el registro
    return {"registry": {}}


@app.get("/_admin/state")
def admin_state():
    with lock:
        return {**state, "registry": dict(registry), "messages": len(messages), "groups": dict(group_health)}
