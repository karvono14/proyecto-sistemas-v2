"""Categoría F: persistencia y despliegue."""
import glob
import re
import time

import requests

import lab
from framework import Skip, test


def _prepare(tag):
    lab.ensure_user(lab.A, "tester")
    mid = lab.send(lab.A, "tester", lab.marker(tag))["id"]
    lab.wait_until(lambda: any(m["id"] == mid for m in lab.all_msgs(lab.B)), 30)
    time.sleep(2)  # que AOF (everysec) sincronice
    return mid, lab.clock(lab.A)


@test("F1", "docker compose down/up con y sin borrar volúmenes: qué sobrevive", reset_after=True)
def f1(t):
    mid, c = _prepare("F1")
    lab.dc("down")
    lab.dc("up", "-d")
    lab.wait_ready(180)
    t.ok(lab.find(lab.A, mid) is not None, "sin -v: el mensaje no sobrevivió")
    t.ok(lab.clock(lab.A) >= c, "sin -v: el reloj retrocedió")
    t.ok(requests.post(lab.A + "/api/users", json={"name": "tester"}, timeout=5).status_code == 409, "sin -v: el usuario no sobrevivió")
    lab.dc("down", "-v")
    lab.dc("up", "-d")
    lab.wait_ready(180)
    t.ok(lab.find(lab.A, mid) is None, "con -v: el mensaje seguía ahí")
    t.note(sin_v="sobrevive historial, usuarios y reloj", con_v="se pierde todo lo local")


@test("F2", "docker compose restart: usuarios, historial y reloj sobreviven")
def f2(t):
    mid, c = _prepare("F2")
    lab.dc("restart")
    lab.wait_ready(180)
    t.ok(lab.find(lab.A, mid) is not None, "el mensaje no sobrevivió al restart")
    t.ok(lab.clock(lab.A) >= c, "el reloj retrocedió")
    t.ok(requests.post(lab.A + "/api/users", json={"name": "tester"}, timeout=5).status_code == 409, "el usuario no sobrevivió")
    t.note(reinicio_del_equipo="manual: reiniciar el equipo, `docker compose up -d` y repetir las comprobaciones")


@test("F3", "Equipo limpio: clonar y levantar con un solo comando")
def f3(t):
    raise Skip("manual: ejecutar `bash tests/clean_clone.sh` y anotar el resultado")


@test("F4", "Variables de entorno faltantes o inválidas: error claro; sin URL del central en el código")
def f4(t):
    cases = [("GROUP_NAME=", "GROUP_NAME"), ("PUBLIC_URL=", "PUBLIC_URL"), ("CENTRAL_URL=", "CENTRAL_URL"),
             ("REDIS_URL=", "REDIS_URL"), ("REGISTER_INTERVAL=abc", "REGISTER_INTERVAL"), ("HEALTH_FAILURES=x", "HEALTH_FAILURES")]
    for env, name in cases:
        out = lab.dc("run", "--rm", "--no-deps", "-T", "-e", env, "server-a", both=True, check=False)
        t.ok("[config]" in out and name in out, f"{env}: no hay un mensaje claro que nombre {name}")
        t.note(**{env.split("=")[0]: "mensaje claro" if "[config]" in out else "SIN mensaje claro"})
    hits = [f"{f}:{i}" for f in glob.glob("server/app/*.py")
            for i, ln in enumerate(open(f, encoding="utf-8"), 1)
            if re.search(r"https?://", ln) and not ln.lstrip().startswith("#")]
    t.ok(not hits, f"URLs escritas en el código: {hits}")


@test("F5", "Cambio de la URL pública del servidor y re-registro")
def f5(t):
    old = lab.admin("/_admin/state", "GET")["registry"].get("gSPAa")
    new = f"http://{lab.container_name('server-a')}:8000"
    try:
        lab.dc("up", "-d", "--force-recreate", "server-a", env={"PUBLIC_URL_A": new})
        lab.wait_ready(120)
        ok = lab.wait_until(lambda: lab.admin("/_admin/state", "GET")["registry"].get("gSPAa") == new, 30)
        t.ok(ok is not None, "el central no registró la URL nueva")
        lab.ensure_user(lab.B, "beto")
        mid = lab.send(lab.B, "beto", lab.marker("F5"))["id"]
        t.ok(lab.wait_until(lambda: any(m["id"] == mid for m in lab.all_msgs(lab.A)), 30) is not None,
             "gSPAa no recibió mensajes con la URL nueva")
        t.note(url_anterior=old, url_nueva=new, re_registro_s=ok)
    finally:
        lab.dc("up", "-d", "--force-recreate", "server-a")
        lab.wait_ready(120)


@test("F6", "Registro: renovación periódica y re-registro si el central pierde su registro")
def f6(t):
    both = lambda: {"gSPAa", "gSPAb"} <= set(lab.admin("/_admin/state", "GET")["registry"])
    lab.admin("/_admin/forget-registry")
    r1 = lab.wait_until(both, 60, 1)  # renovación cada 30 s por defecto
    t.ok(r1 is not None, "tras olvidar el registro, los grupos no se re-registraron en 60 s")
    lab.dc("restart", "central")
    r2 = lab.wait_until(both, 90, 1)
    t.ok(r2 is not None, "tras reiniciar el central, los grupos no se re-registraron en 90 s")
    lab.wait_ready(180)
    lab.ensure_user(lab.B, "beto")
    mid = lab.send(lab.B, "beto", lab.marker("F6"))["id"]
    t.ok(lab.wait_until(lambda: any(m["id"] == mid for m in lab.all_msgs(lab.A)), 30) is not None,
         "no fluyen mensajes tras el re-registro")
    t.note(re_registro_tras_olvidar_s=r1, re_registro_tras_reinicio_s=r2)
