import logging
import random
import threading
import time

import requests
from pydantic import ValidationError

from . import config, models, protocol, store

log = logging.getLogger("chat")
_http_sup = requests.Session()     # una sesión por hilo (keep-alive, sin compartir estado)
_http_send = requests.Session()
_stop = threading.Event()

# Estado del central visto desde aquí. Arranca "caído" hasta el primer health OK:
# así el arranque y la vuelta de una caída siguen EXACTAMENTE el mismo camino.
state = {"down": True, "needs_sync": config.HISTORY_SYNC}


def _url(path: str) -> str:
    return config.CENTRAL_URL + path


def backoff_delay(attempt: int) -> float:
    """Backoff exponencial con tope y jitter (libro, 27.2.1):
    delay = random(0, min(cap, initial * 2^attempt))."""
    return random.uniform(0, min(config.BACKOFF_CAP, config.BACKOFF_INITIAL * 2 ** min(attempt, 30)))


# --- Registro --------------------------------------------------------------------
def register() -> bool:
    try:
        resp = _http_sup.post(_url(protocol.REGISTER_PATH), json=protocol.register_body(),
                              timeout=config.REQUEST_TIMEOUT)
    except requests.RequestException as e:
        log.warning("REGISTER_FAIL error=%s", type(e).__name__)
        return False
    if resp.status_code < 300:
        log.info("REGISTER_OK status=%s", resp.status_code)
        return True
    log.warning("REGISTER_FAIL status=%s body=%s", resp.status_code, resp.text[:200])
    return False


# --- Detección de fallos (heartbeat hacia el central) --------------------------------
def central_alive():
    """Devuelve (vivo, motivo). Distingue 'timeout' (lento) de 'conn_error' (caído)."""
    try:
        resp = _http_sup.get(_url(protocol.HEALTH_PATH), timeout=config.HEALTH_TIMEOUT)
    except requests.Timeout:
        return False, "timeout"
    except requests.RequestException:
        return False, "conn_error"
    return resp.status_code < 300, f"http_{resp.status_code}"


# --- Recuperación de historial --------------------------------------------------------
def sync_history() -> bool:
    try:
        resp = _http_sup.get(_url(protocol.HISTORY_PATH), params={"since": protocol.HISTORY_SINCE},
                             timeout=config.HISTORY_TIMEOUT)
        resp.raise_for_status()
        items = protocol.parse_history(resp.json())
    except (requests.RequestException, ValueError) as e:
        log.warning("HISTORY_FAIL error=%s", e)
        return False
    new = dup = bad = 0
    for raw in items:
        try:
            msg = models.IncomingMessage.model_validate(raw).to_dict()
        except ValidationError:
            bad += 1
            log.warning("DROP_INVALID via=history id=%s", raw.get("id") if isinstance(raw, dict) else None)
            continue
        if store.receive(msg, via="history"):
            new += 1
        else:
            dup += 1
    log.info("HISTORY_SYNC since=%s total=%d nuevos=%d duplicados=%d invalidos=%d",
             protocol.HISTORY_SINCE, len(items), new, dup, bad)
    return True


def supervisor():
    fails, last_register = 0, 0.0
    while not _stop.is_set():
        try:
            alive, why = central_alive()
            if alive:
                had_fails, fails = fails, 0
                if state["down"] or had_fails:
                    # También con fallos cortos (< HEALTH_FAILURES): un reinicio rápido del central pudo
                    # borrar el registro y hacernos perder mensajes sin que llegáramos a declararlo caído.
                    if state["down"]:
                        log.info("CENTRAL_UP")
                    else:
                        log.info("CENTRAL_RECOVERED tras %d fallo(s) corto(s): se re-registra y recupera historial", had_fails)
                    state["down"] = False
                    # El central pudo perder el registro: registrarse de nuevo y reintentar lo pendiente.
                    last_register = time.time() if register() else 0.0
                    store.outbox_release_all()
                    state["needs_sync"] = config.HISTORY_SYNC
                elif time.time() - last_register >= config.REGISTER_INTERVAL:
                    last_register = time.time() if register() else 0.0  # renovación periódica
                if state["needs_sync"] and sync_history():
                    state["needs_sync"] = False
            else:
                fails += 1
                log.warning("HEALTH_FAIL motivo=%s (%d/%d)", why, fails, config.HEALTH_FAILURES)
                if fails >= config.HEALTH_FAILURES and not state["down"]:
                    state["down"] = True
                    log.error("CENTRAL_DOWN tras %d fallos seguidos", fails)
        except Exception:
            log.exception("SUPERVISOR error inesperado")
        _stop.wait(config.HEALTH_INTERVAL)


# --- Envío con reintentos (entrega al menos una vez) ------------------------------------
def _retry(mid: str, msg: dict, reason: str) -> None:
    delay = backoff_delay(store.outbox_attempts(mid))
    attempts = store.outbox_retry(mid, delay)
    log.warning("SEND_RETRY id=%s lamport=%s intento=%d proximo_en=%.2fs motivo=%s",
                mid, msg["lamport"], attempts, delay, reason)


def _send_one(mid: str) -> None:
    msg = store.get_message(mid)
    if msg is None:
        store.outbox_done(mid)
        return
    try:
        resp = _http_send.post(_url(protocol.MESSAGES_PATH), json=protocol.message_body(msg),
                               timeout=config.REQUEST_TIMEOUT)
    except requests.RequestException as e:
        _retry(mid, msg, type(e).__name__)  # sin respuesta: se reintenta
        return
    if resp.status_code < 300:
        store.outbox_done(mid)
        log.info("SEND_OK id=%s lamport=%s status=%s", mid, msg["lamport"], resp.status_code)
    elif resp.status_code >= 500:
        _retry(mid, msg, f"http_{resp.status_code}")  # 5xx: se reintenta
    else:  # 4xx (y 3xx): NO se reintenta, se registra
        store.outbox_reject(mid, f"{resp.status_code} {resp.text[:200]}")
        log.error("SEND_REJECTED id=%s lamport=%s status=%s body=%s",
                  mid, msg["lamport"], resp.status_code, resp.text[:200])


def sender():
    while not _stop.is_set():
        try:
            if state["down"]:
                _stop.wait(0.5)  # con el central caído los mensajes esperan en el outbox
                continue
            due = store.outbox_due()
            if not due:
                _stop.wait(0.1)
                continue
            for mid in due:
                if state["down"]:
                    break
                _send_one(mid)
        except Exception:
            log.exception("SENDER error inesperado")
            _stop.wait(1)


def start() -> None:
    if not config.HISTORY_SYNC:
        log.warning("HISTORY_SYNC=false: recuperación de historial DESACTIVADA (solo para el experimento)")
    for fn in (supervisor, sender):
        threading.Thread(target=fn, name=fn.__name__, daemon=True).start()


def stop() -> None:
    _stop.set()
