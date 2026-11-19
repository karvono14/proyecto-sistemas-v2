"""Categoría C: reloj de Lamport y orden."""
import random
import time
from concurrent.futures import ThreadPoolExecutor

import lab
from framework import test


@test("C1", "Reglas de Lamport con casos escritos a mano")
def c1(t):
    lab.ensure_user(lab.A, "tester")
    mk = lab.marker("C1")
    c = lab.clock(lab.A)
    msg = lab.send(lab.A, "tester", mk)
    t.ok(msg["lamport"] == c + 1, f"envío local: lamport del mensaje {msg['lamport']}; esperaba {c + 1}")
    t.ok(lab.clock(lab.A) == c + 1, "envío local: el reloj debía quedar en c+1")
    last = None
    for name, f in [("m > local", lambda c: c + 10), ("m == local", lambda c: c),
                    ("m < local", lambda c: max(c - 3, 0)), ("m = 0", lambda c: 0)]:
        c = lab.clock(lab.A)
        m = lab.make_msg(lamport=f(c), body=mk)
        lab.fed_post(lab.A, m)
        want, got = max(c, m["lamport"]) + 1, lab.clock(lab.A)
        t.ok(got == want, f"recibir {name}: reloj {got}; esperaba max({c},{m['lamport']})+1 = {want}")
        stored = lab.find(lab.A, m["id"])
        t.ok(stored is not None and stored["lamport"] == m["lamport"],
             f"recibir {name}: el mensaje debe conservar su lamport original")
        last = m
    c = lab.clock(lab.A)
    lab.fed_post(lab.A, last)
    t.ok(lab.clock(lab.A) == c, "un duplicado no debe mover el reloj (hipótesis H4)")
    t.note(casos="envío local + 4 recepciones + duplicado")


@test("C2", "Lamport en los extremos (negativo, 2^31, 2^53...): se MIDE el límite", reset_after=True)
def c2(t):
    cases = [(-1, False), (0, True), (2**31 - 1, True), (2**31, True), (2**32, True), (2**53 - 2, True),
             (2**53 - 1, False), (2**53, False), (2**63, False), (10**30, False), (1.5, False)]
    rows = []
    for v, accept in cases:
        before = lab.clock(lab.A)
        m = lab.make_msg(lamport=v, body=lab.marker("C2"))
        r = lab.fed_post(lab.A, m)
        after = lab.clock(lab.A)
        stored = lab.find(lab.A, m["id"]) if r.status_code == 200 else None
        row = {"lamport_enviado": v, "status": r.status_code, "reloj_antes": before, "reloj_despues": after,
               "lamport_guardado": None if stored is None else stored["lamport"]}
        rows.append(row)
        t.ok(r.status_code < 500, f"lamport={v}: error del servidor ({r.status_code})")
        if accept:
            t.ok(r.status_code == 200, f"lamport={v}: esperaba 200, obtuvo {r.status_code}")
            t.ok(after == max(before, v) + 1, f"lamport={v}: reloj {after}; esperaba {max(before, v) + 1}")
            t.ok(stored is not None and stored["lamport"] == v, f"lamport={v}: no se guardó exacto")
        else:
            t.ok(400 <= r.status_code < 500, f"lamport={v}: esperaba 4xx, obtuvo {r.status_code}")
            t.ok(after == before, f"lamport={v}: el reloj cambió con un mensaje rechazado")
    lab.write_csv("C2", rows)
    t.note(detalle="tests/results/C2.csv", tope_aceptado="2^53-2 (decisión nuestra, ver models.py)")


@test("C3", "Mismo lamport y distinto origin: desempate determinista (lamport, origin)")
def c3(t):
    big = max(lab.clock(lab.A), lab.clock(lab.B)) + 1000
    mk = lab.marker("C3")
    origins = ["g2", "g10", "g1", "g3", "g1-b"]
    msgs = [lab.make_msg(origin=o, lamport=big, body=mk) for o in origins]
    for base in (lab.A, lab.B):
        order = msgs[:]
        random.shuffle(order)
        for m in order:
            lab.fed_post(base, m)
    expected = sorted(origins)  # orden de cadenas = (origin) a igual lamport
    for name, base in (("gSPAa", lab.A), ("gSPAb", lab.B)):
        got = [m["origin"] for m in lab.with_marker(lab.all_msgs(base), mk)]
        t.ok(got == expected, f"{name}: orden {got}; esperaba {expected}")
        t.note(**{name: ",".join(got)})


@test("C4", "El orden no depende de sent_at (reloj físico adulterado)")
def c4(t):
    base = max(lab.clock(lab.A), lab.clock(lab.B)) + 10
    mk = lab.marker("C4")
    specs = [(base, "2099-12-31T23:59:59Z"), (base + 1, "1970-01-01T00:00:00Z"), (base + 2, "2026-06-01T12:00:00Z")]
    msgs = [lab.make_msg(lamport=lm, sent_at=sa, body=mk) for lm, sa in specs]
    for b in (lab.A, lab.B):
        for m in reversed(msgs):  # se entregan al revés
            lab.fed_post(b, m)
    for name, b in (("gSPAa", lab.A), ("gSPAb", lab.B)):
        got = [m["lamport"] for m in lab.with_marker(lab.all_msgs(b), mk)]
        t.ok(got == [s[0] for s in specs], f"{name}: orden {got}; esperaba por lamport {[s[0] for s in specs]}")
    t.note(nota="sustituye 'cambiar la hora del contenedor': solo se manipula sent_at (ver PRUEBAS.md)")


@test("C5", "Ráfaga concurrente desde dos grupos: mismo orden en ambos servidores")
def c5(t):
    lab.ensure_user(lab.A, "ana")
    lab.ensure_user(lab.B, "beto")
    n, mk = 100, lab.marker("C5")
    with ThreadPoolExecutor(16) as ex:
        fs = [ex.submit(lab.send, lab.A, "ana", f"{mk}-a{i}") for i in range(n)]
        fs += [ex.submit(lab.send, lab.B, "beto", f"{mk}-b{i}") for i in range(n)]
        for f in fs:
            f.result()
    t0 = time.time()
    conv = lab.wait_until(lambda: len(lab.ids_with(lab.A, mk)) == 2 * n and len(lab.ids_with(lab.B, mk)) == 2 * n, 90)
    t.ok(conv is not None, f"no convergieron en 90 s (a={len(lab.ids_with(lab.A, mk))}, b={len(lab.ids_with(lab.B, mk))})")
    la, lb = lab.with_marker(lab.all_msgs(lab.A), mk), lab.with_marker(lab.all_msgs(lab.B), mk)
    t.ok([m["id"] for m in la] == [m["id"] for m in lb], "el orden difiere entre gSPAa y gSPAb")
    expected = sorted(la, key=lambda m: (m["lamport"], m["origin"], m["id"]))
    t.ok([m["id"] for m in la] == [m["id"] for m in expected], "el orden no respeta (lamport, origin)")
    t.note(mensajes=2 * n, convergencia_s=conv, tiempo_total_s=round(time.time() - t0, 1))
