"""Registro mínimo de pruebas y objeto T para aserciones y notas."""
import time
from datetime import datetime, timezone

REGISTRY: dict = {}


class Skip(Exception):
    pass


class T:
    def __init__(self, tid: str):
        self.id, self.fails, self.notes, self.kind = tid, [], [], "PASS"

    def ok(self, cond, msg: str) -> bool:
        if not cond:
            self.fails.append(msg)
        return bool(cond)

    def note(self, **kv) -> None:
        self.notes.append(" ".join(f"{k}={v}" for k, v in kv.items()))

    def info(self) -> None:
        """Prueba de MEDICIÓN: sin criterio binario para el valor medido (los t.ok siguen aplicando)."""
        self.kind = "INFO"


def test(tid: str, title: str, heavy: bool = False, reset_after: bool = False):
    """heavy: no corre en --all (hay que pedirla). reset_after: deja datos/reloj alterados; se limpia el lab después."""
    def deco(fn):
        REGISTRY[tid] = {"id": tid, "title": title, "fn": fn, "heavy": heavy, "reset_after": reset_after}
        return fn
    return deco


def run_one(tid: str) -> dict:
    spec, t = REGISTRY[tid], T(tid)
    started, t0 = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), time.time()
    try:
        spec["fn"](t)
        status = "FAIL" if t.fails else t.kind
    except Skip as e:
        status = "SKIP"
        t.notes.append(str(e))
    except Exception as e:  # error del propio test o del entorno: no es un FAIL del sistema
        status = "ERROR"
        t.fails.append(f"{type(e).__name__}: {e}")
    return {"test_id": tid, "title": spec["title"], "started_utc": started, "status": status,
            "duration_s": round(time.time() - t0, 1), "observed": " | ".join(t.notes),
            "failures": " | ".join(t.fails)}
