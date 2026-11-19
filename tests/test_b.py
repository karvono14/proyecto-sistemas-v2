"""Categoría B: idempotencia y deduplicación."""
import random
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

import requests

import lab
from framework import test


@test("B1", "Mismo id 2, 10 y 1000 veces seguidas: un solo efecto y siempre 200")
def b1(t):
    rows = []
    for n in (2, 10, 1000):
        c0 = lab.clock(lab.A)
        m = lab.make_msg(lamport=c0 + 5, body=lab.marker(f"B1x{n}"))
        codes, c1, t0 = [], None, time.time()
        with requests.Session() as s:
            for i in range(n):
                codes.append(s.post(lab.A + "/fed/messages", json=m, timeout=30).status_code)
                if i == 0:
                    c1 = lab.clock(lab.A)
        elapsed = time.time() - t0
        c2 = lab.clock(lab.A)
        stored = sum(1 for x in lab.all_msgs(lab.A) if x["id"] == m["id"])
        t.ok(all(c == 200 for c in codes), f"n={n}: hubo respuestas distintas de 200: {sorted(set(codes))}")
        t.ok(stored == 1, f"n={n}: {stored} copias guardadas; esperaba 1")
        t.ok(c1 == c0 + 6, f"n={n}: reloj tras el primero = {c1 - c0} sobre c0; esperaba 6 (max(c0, c0+5)+1)")
        t.ok(c2 == c1, f"n={n}: los duplicados movieron el reloj ({c2 - c1})")
        rows.append({"n": n, "guardados": stored, "reloj_tras_primero": c1 - c0, "reloj_tras_todos": c2 - c0,
                     "segundos": round(elapsed, 2)})
    lab.write_csv("B1", rows)
    t.note(detalle="tests/results/B1.csv")


@test("B2", "Duplicados concurrentes (condición de carrera): un efecto por id")
def b2(t):
    n_ids, k = 30, 20
    mk = lab.marker("B2")
    msgs = [lab.make_msg(lamport=0, body=f"{mk}-{i}") for i in range(n_ids)]
    jobs = [m for m in msgs for _ in range(k)]
    random.shuffle(jobs)
    c0 = lab.clock(lab.A)
    with ThreadPoolExecutor(20) as ex:
        codes = list(ex.map(lambda m: lab.fed_post(lab.A, m).status_code, jobs))
    stored = len(lab.with_marker(lab.all_msgs(lab.A), mk))
    delta = lab.clock(lab.A) - c0
    t.ok(all(c == 200 for c in codes), f"respuestas distintas de 200: {sorted(set(codes))}")
    t.ok(stored == n_ids, f"guardados={stored}; esperaba {n_ids}")
    t.ok(delta == n_ids, f"el reloj avanzó {delta}; esperaba {n_ids} (uno por id nuevo)")
    t.note(peticiones=len(jobs), ids=n_ids, guardados=stored, avance_reloj=delta)


@test("B3", "Respuesta 200 perdida: el emisor reintenta y el central no duplica")
def b3(t):
    lab.ensure_user(lab.A, "tester")
    lab.admin("/_admin/lose-response", n=1, s=lab.REQUEST_TIMEOUT + 1.5)
    try:
        mid = lab.send(lab.A, "tester", lab.marker("B3"))["id"]
        done = lab.wait_until(lambda: lab.field(lab.A, "outbox") == 0 and
                              any(m["id"] == mid for m in lab.all_msgs(lab.B)), 60)
    finally:
        lab.admin("/_admin/lose-response", n=0)
    t.ok(done is not None, "el mensaje no se entregó a gSPAb en 60 s")
    n = lab.attempts(mid)
    in_central = sum(1 for m in lab.central_history() if m["id"] == mid)
    in_b = sum(1 for m in lab.all_msgs(lab.B) if m["id"] == mid)
    t.ok(n >= 2, f"el central recibió {n} intento(s); esperaba >= 2 (si es 1 no se probó la respuesta perdida)")
    t.ok(in_central == 1, f"el central guardó {in_central} copias; esperaba 1")
    t.ok(in_b == 1, f"gSPAb tiene {in_b} copias; esperaba 1")
    t.note(intentos=n, entregado_tras_s=done)


@test("B4", "Duplicado tras reiniciar el servidor (restart y SIGKILL): la deduplicación persiste")
def b4(t):
    for variante in ("restart", "sigkill"):
        c0 = lab.clock(lab.A)
        m = lab.make_msg(lamport=c0 + 5, body=lab.marker(f"B4{variante}"))
        t.ok(lab.fed_post(lab.A, m).status_code == 200, f"{variante}: primer envío no dio 200")
        c1 = lab.clock(lab.A)
        time.sleep(2)  # que el AOF (appendfsync everysec) alcance a sincronizar
        if variante == "restart":
            lab.dc("restart", "redis-a", "server-a")
        else:
            lab.dc("kill", "-s", "SIGKILL", "redis-a", "server-a")
            lab.dc("start", "redis-a", "server-a")
        lab.wait_ready(180)
        c2 = lab.clock(lab.A)
        r = lab.fed_post(lab.A, m)
        c3 = lab.clock(lab.A)
        stored = sum(1 for x in lab.all_msgs(lab.A) if x["id"] == m["id"])
        t.ok(r.status_code == 200, f"{variante}: reenvío tras reinicio dio {r.status_code}")
        t.ok(stored == 1, f"{variante}: {stored} copias tras reinicio; esperaba 1")
        t.ok(c2 >= c1, f"{variante}: el reloj retrocedió tras el reinicio ({c1} -> {c2})")
        t.ok(c3 == c2, f"{variante}: el duplicado movió el reloj ({c2} -> {c3})")
        t.note(**{variante: f"copias={stored} reloj {c1}->{c2}->{c3}"})


@test("B5", "Crecimiento de la tabla de ids vistos (bytes de Redis por mensaje)", heavy=True, reset_after=True)
def b5(t):
    prev_n, prev_mem, rows = 0, lab.redis_mem("redis-a"), []
    local = threading.local()

    def post_one(_):
        # Una sesión por hilo (conexión reutilizada). Abrir una conexión nueva por petición agota los puertos
        # efímeros del cliente (TIME_WAIT) hacia las ~28 000 peticiones: ese fue el ERROR de la primera versión.
        s = getattr(local, "s", None) or requests.Session()
        local.s = s
        m = lab.make_msg(lamport=0, body="b5-" + uuid.uuid4().hex)
        return s.post(lab.A + "/fed/messages", json=m, timeout=30).status_code

    for target in lab.OPTS["b5_sizes"]:
        todo = target - prev_n
        t0 = time.time()
        with ThreadPoolExecutor(16) as ex:
            codes = list(ex.map(post_one, range(todo)))
        elapsed = time.time() - t0
        mem = lab.redis_mem("redis-a")
        t.ok(all(c == 200 for c in codes), f"hasta {target}: hubo respuestas distintas de 200")
        rows.append({"mensajes_totales": target, "usado_redis_bytes": mem,
                     "bytes_por_mensaje_en_este_tramo": round((mem - prev_mem) / max(todo, 1), 1),
                     "segundos": round(elapsed, 1), "mensajes_por_s": round(todo / max(elapsed, 1e-9), 1)})
        prev_n, prev_mem = target, mem
    lab.write_csv("B5", rows)
    t.note(detalle="tests/results/B5.csv")
    t.info()
