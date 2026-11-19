"""Categoría E: carga y límites."""
import re
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

import requests

import lab
from framework import Skip, test


def _pct(vals, p):
    if not vals:
        return None
    v = sorted(vals)
    return round(v[min(len(v) - 1, max(0, int(round(p / 100 * (len(v) - 1)))))], 1)


class _Poster:
    """POST /api/messages con una sesión por hilo; acumula latencias y errores."""
    def __init__(self, base, user, mk):
        self.base, self.user, self.mk = base, user, mk
        self.local, self.lock, self.lat, self.err = threading.local(), threading.Lock(), [], 0

    def one(self, i=0):
        s = getattr(self.local, "s", None) or requests.Session()
        self.local.s = s
        t0 = time.perf_counter()
        try:
            ok = s.post(self.base + "/api/messages", json={"user": self.user, "body": f"{self.mk}-{i}"},
                        timeout=15).status_code == 201
        except requests.RequestException:
            ok = False
        ms = (time.perf_counter() - t0) * 1000
        with self.lock:
            if ok:
                self.lat.append(ms)
            else:
                self.err += 1


def _burst(base, user, mk, n, workers):
    p, t0 = _Poster(base, user, mk), time.time()
    with ThreadPoolExecutor(workers) as ex:
        list(ex.map(p.one, range(n)))
    return p.lat, p.err, time.time() - t0


@test("E1", "Rampa de tasa (1, 10, 100, 1000 msg/s): latencia p50/p95/p99, errores, saturación", heavy=True, reset_after=True)
def e1(t):
    lab.ensure_user(lab.A, "tester")
    rows, dur = [], 10
    for rate in (1, 10, 100, 1000):
        p = _Poster(lab.A, "tester", "e1")
        with ThreadPoolExecutor(64) as ex:
            start, futs = time.perf_counter(), []
            for i in range(rate * dur):  # lazo abierto: se envía a la hora programada
                wait = start + i / rate - time.perf_counter()
                if wait > 0:
                    time.sleep(wait)
                futs.append(ex.submit(p.one, i))
            for f in futs:
                f.result()
            elapsed = time.perf_counter() - start
        rows.append({"tasa_objetivo_msg_s": rate, "ok": len(p.lat), "errores": p.err,
                     "tasa_lograda_msg_s": round(len(p.lat) / elapsed, 1), "p50_ms": _pct(p.lat, 50),
                     "p95_ms": _pct(p.lat, 95), "p99_ms": _pct(p.lat, 99), "outbox_al_terminar": lab.field(lab.A, "outbox")})
    drain = lab.wait_until(lambda: lab.field(lab.A, "outbox") == 0, 600, 2)
    for r in rows:
        r["vaciado_total_s"] = drain
    lab.write_csv("E1", rows)
    t.ok(rows[0]["errores"] == 0, "hubo errores con 1 msg/s")
    sat = next((r["tasa_objetivo_msg_s"] for r in rows if r["errores"] > 0 or
                r["tasa_lograda_msg_s"] < 0.9 * r["tasa_objetivo_msg_s"] or (r["p95_ms"] or 0) > 1000), None)
    t.note(primera_tasa_con_degradacion=sat, vaciado_outbox_s=drain, detalle="tests/results/E1.csv")
    t.info()


@test("E2", "Ráfaga de 10 000 mensajes: errores y convergencia en gSPAb", heavy=True, reset_after=True)
def e2(t):
    lab.ensure_user(lab.A, "ana")
    n, mk = 10000, lab.marker("E2")
    lat, errors, secs = _burst(lab.A, "ana", mk, n, 32)
    ok = n - errors
    conv = lab.wait_until(lambda: len(lab.ids_with(lab.B, mk)) == ok, 900, 3)
    t.ok(conv is not None, f"gSPAb no recibió los {ok} mensajes aceptados (tiene {len(lab.ids_with(lab.B, mk))})")
    t.note(enviados_ok=ok, errores=errors, segundos_envio=round(secs, 1), tasa_msg_s=round(ok / secs, 1),
           p95_ms=_pct(lat, 95), convergencia_tras_envio_s=conv)
    t.info()


@test("E3", "Cola de pendientes grande tras una caída larga del central", heavy=True, reset_after=True)
def e3(t):
    lab.ensure_user(lab.A, "tester")
    n, mk = 5000, lab.marker("E3")
    mem0, srv0 = lab.redis_mem("redis-a"), lab.container_mem("server-a")
    try:
        lab.admin("/_admin/down")
        lab.wait_until(lambda: lab.field(lab.A, "central_down") is True, 60)
        lat, errors, secs = _burst(lab.A, "tester", mk, n, 16)
        outbox = lab.field(lab.A, "outbox")
        mem1, srv1 = lab.redis_mem("redis-a"), lab.container_mem("server-a")
    finally:
        lab.admin("/_admin/up")
    drain = lab.wait_until(lambda: lab.field(lab.A, "outbox") == 0, 1800, 3)
    got = len(lab.ids_with(lab.B, mk))
    t.ok(errors == 0, f"{errors} envíos locales fallaron con el central caído")
    t.ok(outbox == n - errors, f"outbox={outbox}; esperaba {n - errors}")
    t.ok(drain is not None, "el outbox no se vació en 30 min")
    t.ok(got == n - errors, f"gSPAb recibió {got}; esperaba {n - errors}")
    t.note(pendientes=outbox, redis_antes_B=mem0, redis_con_cola_B=mem1, servidor_antes=srv0,
           servidor_con_cola=srv1, vaciado_s=drain)
    t.info()


@test("E4", "Muchos usuarios locales y clientes simultáneos")
def e4(t):
    tag = uuid.uuid4().hex[:6]
    names = [f"e4{tag}{i}" for i in range(1000)]
    t0 = time.time()
    with ThreadPoolExecutor(32) as ex:
        codes = list(ex.map(lambda n: requests.post(lab.A + "/api/users", json={"name": n}, timeout=10).status_code, names))
    create_s = round(time.time() - t0, 1)
    t.ok(all(c == 201 for c in codes), f"creación de usuarios: respuestas {sorted(set(codes))}")
    mk, lat, lock, errs = lab.marker("E4"), [], threading.Lock(), {"n": 0}

    def client(name):  # cada cliente envía 5 mensajes y lee el historial reciente
        s = requests.Session()
        try:
            for i in range(5):
                t1 = time.perf_counter()
                r = s.post(lab.A + "/api/messages", json={"user": name, "body": f"{mk}-{name}-{i}"}, timeout=15)
                with lock:
                    lat.append((time.perf_counter() - t1) * 1000)
                    errs["n"] += r.status_code != 201
            s.get(lab.A + "/api/messages", params={"since": max(lab.clock(lab.A) - 50, 0)}, timeout=30).raise_for_status()
        except requests.RequestException:
            with lock:
                errs["n"] += 1

    t1 = time.time()
    with ThreadPoolExecutor(100) as ex:
        list(ex.map(client, names[:100]))
    t.ok(errs["n"] == 0, f"{errs['n']} errores con 100 clientes simultáneos")
    t.note(usuarios_creados=1000, crear_s=create_s, clientes=100, mensajes=500, p95_ms=_pct(lat, 95),
           segundos=round(time.time() - t1, 1))
    t.info()


@test("E5", "Historial grande: costo de /history?since=0 y de la recuperación al reiniciar", heavy=True, reset_after=True)
def e5(t):
    rows, total = [], 0
    lab.admin("/_admin/forward", on=0)  # el central guarda pero no reenvía: solo se carga su historial
    try:
        for target in lab.OPTS["e5_sizes"]:
            local = threading.local()

            def load(i, base=total):
                s = getattr(local, "s", None) or requests.Session()
                local.s = s
                m = lab.make_msg(origin="gLOAD", user="carga", lamport=base + i + 1, body="e5-" + uuid.uuid4().hex)
                return s.post(lab.CENTRAL + "/messages", json=m, timeout=30).status_code

            with ThreadPoolExecutor(16) as ex:
                codes = list(ex.map(load, range(target - total)))
            t.ok(all(c == 200 for c in codes), f"carga hasta {target}: respuestas distintas de 200")
            total = target
            t0 = time.time()
            r = requests.get(lab.CENTRAL + "/history", params={"since": 0}, timeout=600)
            hist_s, hist_mb = time.time() - t0, len(r.content) / 1e6
            since = lab.utcnow_iso()
            t1 = time.time()
            lab.dc("restart", "server-a")
            sync_s = lab.wait_until(lambda: "HISTORY_SYNC" in lab.logs("server-a", since), 900, 1)
            line = lab.lines(lab.logs("server-a", since), "HISTORY_SYNC")
            rows.append({"mensajes_en_el_central": target, "history_s": round(hist_s, 2), "history_MB": round(hist_mb, 2),
                         "recuperacion_tras_reinicio_s": None if sync_s is None else round(time.time() - t1, 1),
                         "log": line[-1].split("INFO ")[-1] if line else "",
                         "memoria_servidor": lab.container_mem("server-a")})
    finally:
        lab.admin("/_admin/forward", on=1)
    lab.write_csv("E5", rows)
    t.ok(all(r["recuperacion_tras_reinicio_s"] is not None for r in rows), "la recuperación no terminó en 15 min")
    t.note(detalle="tests/results/E5.csv")
    t.info()


@test("E6", "Backoff: tope de espera; tras muchos reintentos el mensaje se conserva")
def e6(t):
    lab.ensure_user(lab.A, "tester")
    # pruebas previas (E4: 500 mensajes) pueden dejar pendientes que se vacían durante los 75 s;
    # sin esperar a outbox=0 el conteo "antes+1" mide ese vaciado, no el mensaje de E6
    lab.wait_until(lambda: (lab.status(lab.A) or {}).get("outbox") == 0, 60)
    before = lab.status(lab.A)
    lab.admin("/_admin/force-status", code=503)
    try:
        mid = lab.send(lab.A, "tester", lab.marker("E6"))["id"]
        time.sleep(75)
        delays = [float(re.search(r"proximo_en=([0-9.]+)s", ln).group(1))
                  for ln in lab.lines(lab.logs("server-a"), f"SEND_RETRY id={mid}")]
        t.ok(len(delays) >= 8, f"solo {len(delays)} reintentos en 75 s")
        t.ok(not delays or max(delays) <= lab.BACKOFF_CAP + 0.01, f"espera máxima {max(delays or [0])} > tope {lab.BACKOFF_CAP}")
        now = lab.field(lab.A, "outbox")
        t.ok(now == before["outbox"] + 1, f"outbox antes={before['outbox']} ahora={now}; se esperaba antes+1")
        t.note(reintentos=len(delays), espera_max_s=max(delays or [0]), nota="no hay máximo de reintentos: se conserva (H8)")
    finally:
        lab.admin("/_admin/force-status", code=0)
    done = lab.wait_until(lambda: sum(1 for m in lab.all_msgs(lab.B) if m["id"] == mid) == 1, 60)
    t.ok(done is not None, "no se entregó una sola vez tras quitar el 503")


@test("E7", "Agotamiento de recursos: disco lleno, memoria limitada, descriptores")
def e7(t):
    raise Skip("manual: ver el procedimiento de E7 en docs/PRUEBAS.md (altera límites de Docker)")
