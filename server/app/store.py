import json
import logging
import time

import redis

from . import config

log = logging.getLogger("chat")
r = redis.Redis.from_url(config.REDIS_URL, decode_responses=True)

K_LAMPORT, K_USERS = "lamport", "users"
K_MESSAGES, K_HISTORY = "messages", "history"
K_OUTBOX, K_ATTEMPTS, K_REJECTED = "outbox", "attempts", "rejected"

# Mensaje PROPIO: guardar + encolar en el outbox, todo atómico.
_SAVE_LOCAL = r.register_script("""
if redis.call('HSETNX', KEYS[1], ARGV[1], ARGV[2]) == 1 then
  redis.call('ZADD', KEYS[2], ARGV[3], ARGV[4])
  redis.call('ZADD', KEYS[3], ARGV[5], ARGV[1])
  return 1
end
return 0
""")

# Mensaje RECIBIDO: si el id es nuevo, guardarlo y fijar reloj = max(local, recibido)+1.
# Devuelve -1 si era duplicado (sin ningún efecto: HIPÓTESIS H4).
_RECEIVE = r.register_script("""
if redis.call('HSETNX', KEYS[1], ARGV[1], ARGV[2]) == 0 then
  return -1
end
redis.call('ZADD', KEYS[2], ARGV[3], ARGV[4])
local cur = tonumber(redis.call('GET', KEYS[3]) or '0')
local nxt = math.max(cur, tonumber(ARGV[3])) + 1
redis.call('SET', KEYS[3], nxt)
return nxt
""")


def get_lamport() -> int:
    return int(r.get(K_LAMPORT) or 0)


def next_lamport() -> int:
    return r.incr(K_LAMPORT)  # regla: incrementar ANTES de enviar


def _member(msg: dict) -> str:
    # Desempate por origin = orden lexicográfico (bytes) del miembro del zset. El separador debe ser MENOR que
    # cualquier carácter de un origin; con "|" el orden era incorrecto ("g10" quedaba antes que "g1").
    return f"{msg['origin']}\x00{msg['id']}"


def save_local(msg: dict) -> bool:
    created = _SAVE_LOCAL(
        keys=[K_MESSAGES, K_HISTORY, K_OUTBOX],
        args=[msg["id"], json.dumps(msg, ensure_ascii=False), msg["lamport"], _member(msg), time.time()],
    )
    log.info("SAVED id=%s lamport=%s from=%s (pendiente de envío)", msg["id"], msg["lamport"], msg["from"])
    return bool(created)


def receive(msg: dict, via: str) -> bool:
    """Devuelve True si el mensaje era nuevo, False si era duplicado."""
    res = _RECEIVE(
        keys=[K_MESSAGES, K_HISTORY, K_LAMPORT],
        args=[msg["id"], json.dumps(msg, ensure_ascii=False), msg["lamport"], _member(msg)],
    )
    if res == -1:
        log.info("DUPLICATE id=%s lamport=%s via=%s (descartado, sin efectos)", msg["id"], msg["lamport"], via)
        return False
    log.info("RECV id=%s lamport=%s from=%s via=%s reloj_local=%s",
             msg["id"], msg["lamport"], msg["from"], via, res)
    return True


def history_since(since: int) -> list:
    """since <= 0: todo el historial (incluye lamport 0). since > 0: lamport estrictamente mayor (API nuestra)."""
    lo = "-inf" if since <= 0 else f"({since}"
    members = r.zrangebyscore(K_HISTORY, lo, "+inf")
    if not members:
        return []
    # Tolera miembros del formato antiguo "origin|id" (datos de versiones previas del laboratorio).
    ids = [m.rsplit("\x00", 1)[-1] if "\x00" in m else m.rsplit("|", 1)[-1] for m in members]
    return [json.loads(x) for x in r.hmget(K_MESSAGES, ids)]


# --- Outbox: mensajes propios pendientes de confirmar por el central -----------
# zset: puntaje = instante del próximo intento. Se borra SOLO al recibir un 2xx o un 4xx.
def outbox_due(limit: int = 50) -> list:
    return r.zrangebyscore(K_OUTBOX, "-inf", time.time(), start=0, num=limit)


def outbox_size() -> int:
    return r.zcard(K_OUTBOX)


def rejected_size() -> int:
    return r.hlen(K_REJECTED)


def get_message(mid: str):
    raw = r.hget(K_MESSAGES, mid)
    return json.loads(raw) if raw else None


def outbox_attempts(mid: str) -> int:
    return int(r.hget(K_ATTEMPTS, mid) or 0)


def outbox_done(mid: str) -> None:
    r.zrem(K_OUTBOX, mid)
    r.hdel(K_ATTEMPTS, mid)


def outbox_retry(mid: str, delay: float) -> int:
    attempts = r.hincrby(K_ATTEMPTS, mid, 1)
    r.zadd(K_OUTBOX, {mid: time.time() + delay})
    return attempts


def outbox_reject(mid: str, reason: str) -> None:
    r.hset(K_REJECTED, mid, reason)  # queda registrado, no se reintenta
    outbox_done(mid)


def outbox_release_all() -> None:
    """El central volvió: todo lo pendiente se reintenta ya y el backoff reinicia."""
    now = time.time()
    late = {mid: now for mid, score in r.zrange(K_OUTBOX, 0, -1, withscores=True) if score > now}
    if late:
        r.zadd(K_OUTBOX, late)
    r.delete(K_ATTEMPTS)
