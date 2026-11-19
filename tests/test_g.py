"""Categoría G: seguridad básica y robustez."""
import json

import requests

import lab
from framework import Skip, test

PAYLOADS = ["'; DROP TABLE messages;--", "\" OR 1=1 --", "<script>alert(1)</script>", "<img src=x onerror=alert(1)>",
            "\x1b[2J\x1b[H", "\x1b]0;titulo\x07", "{{7*7}}", "${jndi:ldap://x/a}", "../../etc/passwd", "%00%0d%0a"]


@test("G1", "Entradas maliciosas en body y from: se guardan como texto, sin efectos")
def g1(t):
    lab.ensure_user(lab.A, "tester")
    for body in PAYLOADS:
        c = lab.clock(lab.A)
        m = lab.send(lab.A, "tester", body)
        got = lab.find(lab.A, m["id"])
        t.ok(got is not None and got["body"] == body, f"local: {body!r} no hizo ida y vuelta exacta")
        e = lab.make_msg(origin="gTEST", user="x'--", lamport=c + 5, body=body)
        r = lab.fed_post(lab.A, e)
        got = lab.find(lab.A, e["id"]) if r.status_code == 200 else None
        t.ok(r.status_code == 200 and got is not None and got["body"] == body, f"/fed: {body!r} → {r.status_code}")
    t.ok(lab.status(lab.A) is not None, "el servidor dejó de responder")
    t.note(payloads=len(PAYLOADS), nota="Redis no interpreta SQL; el cliente es CLI: el riesgo real son secuencias ANSI")


@test("G2", "JSON con anidamiento profundo o enorme: el servidor sigue vivo")
def g2(t):
    rows = []

    def attempt(name, payload):
        try:
            code = lab.fed_post(lab.A, payload, raw=True).status_code
        except requests.RequestException as e:
            code = f"error:{type(e).__name__}"
        alive = lab.status(lab.A) is not None
        rows.append({"caso": name, "status": code, "servidor_vivo": alive})
        t.ok(alive, f"{name}: el servidor dejó de responder")

    for depth in (100, 1000, 10000, 100000):
        attempt(f"anidamiento_{depth}", "[" * depth + "]" * depth)
    big = lab.make_msg(lamport=lab.clock(lab.A) + 1, body="g2")
    big.update({f"k{i}": i for i in range(200_000)})
    attempt("objeto_200000_claves", json.dumps(big))
    lab.write_csv("G2", rows)
    t.note(detalle="tests/results/G2.csv", cinco_xx=sum(1 for r in rows if str(r["status"]).startswith("5")))
    t.info()


@test("G3", "/fed/* llamado por un tercero y suplantación de otro grupo (limitación documentada)")
def g3(t):
    mk, c = lab.marker("G3"), lab.clock(lab.A)
    r1 = lab.fed_post(lab.A, lab.make_msg(origin="gSPAb", user="ana", lamport=c + 1, body=mk + "-suplanta-gSPAb"))
    r2 = lab.fed_post(lab.A, lab.make_msg(origin="gSPAa", user="ana", lamport=c + 2, body=mk + "-finge-gSPAa"))
    h = requests.get(lab.A + "/fed/health", timeout=5)
    t.ok(max(r1.status_code, r2.status_code, h.status_code) < 500, "algún endpoint /fed/* dio 5xx")
    t.note(suplanta_otro_grupo=r1.status_code, finge_ser_el_propio=r2.status_code, fed_health_sin_auth=h.status_code,
           conclusion="se aceptan: el protocolo no define autenticación; limitación, no se inventó ninguna regla")
    t.info()


@test("G4", "Límites de tamaño de petición")
def g4(t):
    raise Skip("documental: A4 midió que no hay tope hasta 50 MB y G2 mide JSON enorme; ver 'Tabla de límites'")
