"""Categoría A: conformidad y protocolo."""
import time

import requests

import lab
from framework import Skip, test

REQUIRED = ["id", "from", "origin", "lamport", "sent_at", "body"]


@test("A1", "Script de conformidad oficial completo")
def a1(t):
    raise Skip("manual: se ejecuta el script oficial del profesor (aún no disponible) y se anexa su salida")


@test("A2", "Campos desconocidos se ignoran sin error")
def a2(t):
    m = lab.make_msg(lamport=lab.clock(lab.A) + 1, body=lab.marker("A2"))
    m.update({"campo_nuevo": {"a": 1}, "otro": [1, 2, 3], "version": 2})
    r = lab.fed_post(lab.A, m)
    t.ok(r.status_code == 200, f"esperaba 200, obtuvo {r.status_code}")
    got = lab.find(lab.A, m["id"])
    t.ok(got is not None, "el mensaje no quedó guardado")
    t.note(status=r.status_code, guardado=got is not None)


@test("A3", "Campos faltantes o tipos inválidos: 4xx y nada guardado")
def a3(t):
    mk = lab.marker("A3")
    wrong = {"id": [123, None, ["x"]], "from": [5, None], "origin": [7, None, ""],
             "lamport": ["5", 5.5, True, None, [1]], "sent_at": [5, None], "body": [5, None, ["x"]]}
    cases = []
    for f in REQUIRED:
        m = lab.make_msg(lamport=1, body=mk)
        del m[f]
        cases.append((f"falta:{f}", m, False))
    for f, vals in wrong.items():
        for v in vals:
            m = lab.make_msg(lamport=1, body=mk)
            m[f] = v
            cases.append((f"{f}={v!r}", m, False))
    for raw in ["no es json", "[]", "{}", "null", "123", '"texto"']:
        cases.append((f"crudo:{raw}", raw, True))
    before = lab.status(lab.A)["messages"]
    rows = []
    for name, payload, raw in cases:
        r = lab.fed_post(lab.A, payload, raw=raw)
        rows.append({"caso": name, "status": r.status_code})
        t.ok(400 <= r.status_code < 500, f"{name}: esperaba 4xx, obtuvo {r.status_code}")
    after = lab.status(lab.A)["messages"]
    t.ok(after == before, f"se guardaron {after - before} mensajes inválidos")
    lab.write_csv("A3", rows)
    t.note(casos=len(cases), detalle="tests/results/A3.csv")


@test("A4", "Contenido: id mal formado, body vacío/largo, Unicode, caracteres de control")
def a4(t):
    c, rows = lab.clock(lab.A), []

    def case(name, expect, **over):
        m = lab.make_msg(lamport=c + 1)
        m["body"] = lab.marker("A4")
        m.update(over)
        r = lab.fed_post(lab.A, m)
        got = lab.find(lab.A, m["id"]) if r.status_code == 200 else None
        rt = got is not None and got["body"] == m["body"] and got["id"] == m["id"]
        rows.append({"caso": name, "status": r.status_code, "guardado": got is not None, "ida_y_vuelta_exacta": rt})
        if expect == "4xx":
            t.ok(400 <= r.status_code < 500, f"{name}: esperaba 4xx, obtuvo {r.status_code}")
        elif expect == "ok":
            t.ok(r.status_code == 200 and rt, f"{name}: esperaba 200 y ida y vuelta exacta (status={r.status_code})")

    case("id_corto", "4xx", id="abc")
    case("id_vacio", "4xx", id="")
    case("id_uuid_con_basura", "4xx", id=lab.new_id() + "x")
    case("id_uuid_mayusculas", None, id=lab.new_id().upper())  # solo se observa (¿dedup distingue mayúsculas?)
    case("body_vacio", None, body="")                          # decisión H7: solo se observa
    case("unicode", "ok", body="Hola ñ áéíóú 你好 😀🚀 العربية")
    case("control", "ok", body="a\x00b\x01c\x1fd\u202ee\r\n\t")
    case("body_10k", "ok", body="x" * 10_000)

    # El límite de tamaño NO se asume: se mide (sube hasta --max-body-mb o hasta el primer fallo).
    sizes_kb = [1, 10, 100, 1000] + [s * 1000 for s in (5, 10, 50) if s <= lab.OPTS["max_body_mb"]]
    max_ok = 0
    for kb in sizes_kb:
        m = lab.make_msg(lamport=c + 1, body="x" * (kb * 1000))
        t0 = time.time()
        try:
            r = lab.fed_post(lab.A, m)
            status = r.status_code
        except requests.RequestException as e:
            status = f"error:{type(e).__name__}"
        rows.append({"caso": f"body_{kb}KB", "status": status, "guardado": status == 200,
                     "ida_y_vuelta_exacta": "", "segundos": round(time.time() - t0, 2)})
        if status != 200:
            break
        max_ok = kb
    lab.write_csv("A4", rows)
    t.note(max_body_kb_aceptado=max_ok, detalle="tests/results/A4.csv")
    t.info()


@test("A5", "from que no coincide con origin: 4xx")
def a5(t):
    c = lab.clock(lab.A)
    for name, frm, origin in [("from_de_otro_grupo", "ana@g3", "g4"), ("from_sin_arroba", "ana", "g3"),
                              ("from_sin_usuario", "@g3", "g3")]:
        m = lab.make_msg(lamport=c + 1, body=lab.marker("A5"))
        m["from"], m["origin"] = frm, origin
        r = lab.fed_post(lab.A, m)
        t.ok(400 <= r.status_code < 500, f"{name}: esperaba 4xx, obtuvo {r.status_code}")
        t.note(**{name: r.status_code})


@test("A6", "4xx del central: no se reintenta y queda en el log")
def a6(t):
    lab.ensure_user(lab.A, "tester")
    before = lab.status(lab.A)
    lab.admin("/_admin/force-status", code=400)
    try:
        mid = lab.send(lab.A, "tester", lab.marker("A6"))["id"]
        seen = lab.wait_until(lambda: lab.field(lab.A, "rejected") == before["rejected"] + 1, 15)
        t.ok(seen is not None, "el servidor no registró el rechazo (rejected no aumentó)")
        time.sleep(6)  # margen: si hubiera reintentos, aparecerían aquí
        n = lab.attempts(mid)
        t.ok(n == 1, f"el central recibió {n} intentos; esperaba 1")
        t.ok(lab.field(lab.A, "outbox") == before["outbox"], "el mensaje sigue en el outbox")
        t.ok(any(mid in ln for ln in lab.lines(lab.logs("server-a"), "SEND_REJECTED")),
             "no hay SEND_REJECTED con el id en el log")
        t.note(intentos_en_el_central=n)
    finally:
        lab.admin("/_admin/force-status", code=0)


@test("A7", "5xx del central: se reintenta con backoff y se entrega al volver")
def a7(t):
    lab.ensure_user(lab.A, "tester")
    before = lab.status(lab.A)
    lab.admin("/_admin/force-status", code=503)
    try:
        mid = lab.send(lab.A, "tester", lab.marker("A7"))["id"]
        time.sleep(12)
        n = lab.attempts(mid)
        retries = lab.lines(lab.logs("server-a"), f"SEND_RETRY id={mid}")
        t.ok(n >= 3, f"el central recibió {n} intentos en 12 s; esperaba >= 3")
        t.ok(len(retries) >= 2, f"solo {len(retries)} líneas SEND_RETRY en el log")
        t.ok(lab.field(lab.A, "outbox") == before["outbox"] + 1, "el mensaje no quedó pendiente en el outbox")
    finally:
        lab.admin("/_admin/force-status", code=0)
    delivered = lab.wait_until(lambda: any(m["id"] == mid for m in lab.all_msgs(lab.B)), 60)
    t.ok(delivered is not None, "el mensaje no llegó a gSPAb tras quitar el 5xx")
    copies = sum(1 for m in lab.all_msgs(lab.B) if m["id"] == mid)
    t.ok(copies == 1, f"gSPAb tiene {copies} copias; esperaba 1")
    t.ok(lab.wait_until(lambda: lab.field(lab.A, "outbox") == before["outbox"], 30) is not None,
         "el outbox no se vació")
    t.note(intentos_en_12s=n, entregado_tras_s=delivered, copias_en_b=copies)
