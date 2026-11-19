"""Categoría D: fallos parciales y recuperación."""
import re
import threading
import time

import requests

import lab
from framework import Skip, test


def _ids_in(base, mk):
    return {m["id"] for m in lab.with_marker(lab.all_msgs(base), mk)}


@test("D1", "Caída de mi servidor 10 s con tráfico entrante: sin pérdidas ni duplicados")
def d1(t):
    import run_experiment as rx  # el mismo procedimiento del experimento (a)
    lab.ensure_user(lab.B, "emisor")
    row = rx.run_rep(1, 10.0, 10.0, 3.0, 8.0, "on", 60.0)
    lab.write_csv("D1", [row])
    t.ok(row["missing"] == 0, f"mensajes perdidos: {row['missing']}")
    t.ok(row["dup_stored"] == 0, f"duplicados almacenados: {row['dup_stored']}")
    t.ok(row["extra"] == 0, f"mensajes de más: {row['extra']}")
    t.note(enviados=row["sent"], recuperacion_s=row["recovery_s"], duplicados_descartados=
           row["dup_discarded_fed"] + row["dup_discarded_history"])


@test("D2", "Central caído (simulado): detección por heartbeat, cola de pendientes y reenvío al volver")
def d2(t):
    lab.ensure_user(lab.A, "tester")
    mk, ids = lab.marker("D2"), []
    try:
        lab.admin("/_admin/down")
        for i in range(2):
            ids.append(lab.send(lab.A, "tester", f"{mk}-{i}")["id"])
        detect = lab.wait_until(lambda: lab.field(lab.A, "central_down") is True, 60)
        limite = lab.HEALTH_FAILURES * (lab.HEALTH_INTERVAL + lab.HEALTH_TIMEOUT) + 2
        t.ok(detect is not None, "gSPAa nunca marcó el central como caído")
        t.ok(detect is not None and detect <= limite, f"detección en {detect} s; límite esperado {limite} s")
        for i in range(2, 5):
            ids.append(lab.send(lab.A, "tester", f"{mk}-{i}")["id"])
        t.ok(lab.field(lab.A, "outbox") == 5, f"outbox={lab.field(lab.A, 'outbox')}; esperaba 5 pendientes")
    finally:
        lab.admin("/_admin/up")
    drain = lab.wait_until(lambda: lab.field(lab.A, "outbox") == 0 and lab.field(lab.A, "central_down") is False, 90)
    t.ok(drain is not None, "el outbox no se vació tras volver el central")
    got = [m["id"] for m in lab.with_marker(lab.all_msgs(lab.B), mk)]
    t.ok(sorted(got) == sorted(ids), f"gSPAb recibió {len(got)} mensajes; esperaba exactamente 5 sin duplicados")
    t.note(deteccion_s=detect, vaciado_tras_volver_s=drain)


@test("D3", "SIGKILL de Redis y servidor en plena ráfaga: integridad y ventana de pérdida")
def d3(t):
    lab.ensure_user(lab.A, "ana")
    mk, acked, lock, killed = lab.marker("D3"), set(), threading.Lock(), threading.Event()

    def worker(w):
        s, i = requests.Session(), 0
        while not killed.is_set() and i < 3000:
            try:
                r = s.post(lab.A + "/api/messages", json={"user": "ana", "body": f"{mk}-{w}-{i}"}, timeout=3)
                if r.status_code == 201:
                    with lock:
                        acked.add(r.json()["id"])
            except requests.RequestException:
                pass
            i += 1

    threads = [threading.Thread(target=worker, args=(w,), daemon=True) for w in range(8)]
    for th in threads:
        th.start()
    time.sleep(1.5)
    lab.dc("kill", "-s", "SIGKILL", "redis-a", "server-a")
    killed.set()
    for th in threads:
        th.join()
    lab.dc("start", "redis-a", "server-a")
    lab.wait_ready(180)
    # La sincronización de historial ocurre justo después de volver: esperar a que el conteo se estabilice.
    lab.wait_stable(lambda: len(lab.ids_with(lab.A, mk)), quiet=6, timeout=90)
    r = requests.get(lab.A + "/api/messages", timeout=60)
    t.ok(r.status_code == 200, f"GET /api/messages dio {r.status_code}: historial inconsistente (hash vs zset)")
    full = r.json() if r.status_code == 200 else []
    st = lab.status(lab.A)
    t.ok(st is not None and len(full) == st["messages"],
         f"historial listado={len(full)} vs mensajes guardados={st and st['messages']}")
    present = {m["id"] for m in lab.with_marker(full, mk)}
    lost = acked - present
    ids = [m["id"] for m in lab.with_marker(full, mk)]
    t.ok(len(ids) == len(set(ids)), "hay ids repetidos en el historial")
    t.note(confirmados_201=len(acked), presentes_tras_recuperar=len(present & acked),
           perdidos_confirmados=len(lost), nota="si perdidos>0 es la ventana de appendfsync everysec")
    t.info()  # los perdidos se MIDEN; la integridad (t.ok) sí es criterio


@test("D4", "Reinicios repetidos y seguidos (flapping) con tráfico entrante")
def d4(t):
    import run_experiment as rx
    lab.ensure_user(lab.B, "emisor")
    mk = lab.marker("D4")
    sender = rx.Sender(5.0, mk)
    sender.start()
    time.sleep(2)
    for _ in range(8):
        lab.dc("kill", "server-a")
        time.sleep(1)
        lab.dc("start", "server-a")
        time.sleep(2)
    sender.stop_evt.set()
    sender.join()
    sent = set(sender.sent)
    ok = lab.wait_until(lambda: sent <= _ids_in(lab.A, mk), 90)
    got = [m["id"] for m in lab.with_marker(lab.all_msgs(lab.A), mk)]
    t.ok(ok is not None, f"faltan {len(sent - set(got))} de {len(sent)} mensajes tras 90 s")
    t.ok(len(got) == len(set(got)), "hay ids repetidos en el historial")
    t.ok(lab.field(lab.A, "central_down") is False, "gSPAa no quedó conectado al central")
    t.note(ciclos=8, enviados=len(sent), faltantes=len(sent - set(got)), convergencia_s=ok)


@test("D5", "Partición de red: gSPAa sin ruta al central; al sanar, convergencia del historial")
def d5(t):
    try:
        net = lab.network_of("server-a", "front")
    except RuntimeError as e:
        raise Skip(str(e))
    cid = lab.container_id("server-a")
    lab.ensure_user(lab.A, "ana")
    lab.ensure_user(lab.B, "beto")
    mk, healed = lab.marker("D5"), False
    lab.docker("network", "disconnect", net, cid)
    try:
        for i in range(5):
            lab.send(lab.A, "ana", f"{mk}-a{i}")   # quedan en el outbox
            lab.send(lab.B, "beto", f"{mk}-b{i}")  # el central intenta reenviarlos a gSPAa y no puede
        detect = lab.wait_until(lambda: lab.field(lab.A, "central_down") is True, 90)
        t.ok(detect is not None, "gSPAa no detectó la partición")
        time.sleep(8)  # el central simulado abandona sus reenvíos a gSPAa (~3.5 s)
        t.ok(lab.field(lab.A, "outbox") == 5, f"outbox={lab.field(lab.A, 'outbox')}; esperaba 5")
    finally:
        lab.docker("network", "connect", "--alias", "server-a", net, cid)
        healed = True
    conv = lab.wait_until(lambda: len(_ids_in(lab.A, mk)) == 10 and len(_ids_in(lab.B, mk)) == 10 and
                          lab.field(lab.A, "outbox") == 0, 120)
    t.ok(conv is not None, f"sin convergencia: a={len(_ids_in(lab.A, mk))}, b={len(_ids_in(lab.B, mk))} (esperaba 10 y 10)")
    la, lb = [m["id"] for m in lab.with_marker(lab.all_msgs(lab.A), mk)], [m["id"] for m in lab.with_marker(lab.all_msgs(lab.B), mk)]
    t.ok(la == lb, "el orden difiere entre servidores tras sanar")
    t.ok(len(la) == len(set(la)), "ids repetidos en gSPAa")
    t.note(deteccion_s=detect, convergencia_tras_sanar_s=conv, red=net)


@test("D6", "Central lento en POST: backoff acotado y sin tormenta de reintentos")
def d6(t):
    lab.ensure_user(lab.A, "tester")
    mk = lab.marker("D6")
    lab.admin("/_admin/slow", ms=int((lab.REQUEST_TIMEOUT + 2) * 1000), scope="messages")
    try:
        mid = lab.send(lab.A, "tester", mk)["id"]
        time.sleep(45)
        retries = lab.lines(lab.logs("server-a"), f"SEND_RETRY id={mid}")
        delays = [float(re.search(r"proximo_en=([0-9.]+)s", ln).group(1)) for ln in retries]
        n_central = lab.attempts(mid)
        t.ok(len(delays) >= 3, f"solo {len(delays)} reintentos registrados en 45 s")
        t.ok(not delays or max(delays) <= lab.BACKOFF_CAP + 0.01, f"espera máxima {max(delays or [0])} > tope {lab.BACKOFF_CAP}")
        t.ok(lab.field(lab.A, "central_down") is False, "el heartbeat marcó caído un central con /health sano")
        t.note(reintentos=len(delays), esperas_s=",".join(f"{d:.1f}" for d in delays), intentos_llegados_al_central=n_central)
    finally:
        lab.admin("/_admin/up")
    done = lab.wait_until(lambda: any(m["id"] == mid for m in lab.all_msgs(lab.B)), 60)
    copies = sum(1 for m in lab.all_msgs(lab.B) if m["id"] == mid)
    t.ok(done is not None, "no se entregó tras quitar la lentitud")
    t.ok(copies == 1, f"gSPAb tiene {copies} copias; esperaba 1")
    t.info()


@test("D7", "Central lento vs caído: el detector distingue el motivo")
def d7(t):
    expected = [("lento", "timeout"), ("responde_503", "http_503"), ("apagado", "conn_error")]
    for name, token in expected:
        since = lab.utcnow_iso()
        try:
            if name == "lento":
                lab.admin("/_admin/slow", ms=int((lab.HEALTH_TIMEOUT + 1) * 1000), scope="all")
            elif name == "responde_503":
                lab.admin("/_admin/down")
            else:
                lab.dc("stop", "central")
            time.sleep(lab.HEALTH_FAILURES * (lab.HEALTH_INTERVAL + lab.HEALTH_TIMEOUT) + 4)
            reasons = set(re.findall(r"HEALTH_FAIL motivo=(\w+)", lab.logs("server-a", since)))
        finally:
            if name == "apagado":
                lab.dc("start", "central")
            else:
                lab.admin("/_admin/up")
        t.ok(token in reasons, f"modo {name}: motivos vistos {sorted(reasons)}; esperaba {token}")
        t.note(**{name: ",".join(sorted(reasons)) or "ninguno"})
        lab.wait_ready(120)


@test("D8", "Falsos positivos del detector: central vivo pero lento, ¿cuándo se marca caído?")
def d8(t):
    rows = []
    try:
        for ms in (500, 1000, 1500, 2500):
            since = lab.utcnow_iso()
            lab.admin("/_admin/slow", ms=ms, scope="all")
            saw_down, end = False, time.time() + 20
            while time.time() < end:
                saw_down = saw_down or lab.field(lab.A, "central_down") is True
                time.sleep(0.5)
            downs = lab.logs("server-a", since).count("CENTRAL_DOWN")
            lab.admin("/_admin/up")
            lab.wait_until(lambda: lab.field(lab.A, "central_down") is False, 60)
            rows.append({"latencia_central_ms": ms, "timeout_health_ms": int(lab.HEALTH_TIMEOUT * 1000),
                         "marcado_caido": saw_down, "eventos_CENTRAL_DOWN": downs})
            if ms <= lab.HEALTH_TIMEOUT * 1000 * 0.5:
                t.ok(downs == 0, f"latencia {ms} ms (<= 50% del timeout): falso positivo")
    finally:
        lab.admin("/_admin/up")
    lab.write_csv("D8", rows)
    t.note(detalle="tests/results/D8.csv")
    t.info()
