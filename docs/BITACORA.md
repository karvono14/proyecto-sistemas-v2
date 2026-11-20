# Bitácora de la sesión de interoperabilidad **local**

> Central **simulado** y 4 grupos que ejecutan **nuestro** servidor. Prueba que nuestro código converge; **no** prueba interoperabilidad con implementaciones de otros equipos.

Fecha (UTC): 2026-11-19

## Resultados

| Prueba | Resultado | Detalle |
|---|---|---|
| 1. Conversación global (4 grupos × 10 mensajes) | PASS | convergencia 0.6 s |
| 2. Caída y recuperación de gSPAa | PASS | recuperación 1.1 s |
| 2. Caída y recuperación de gSPAb | PASS | recuperación 1.1 s |
| 2. Caída y recuperación de gSPAc | PASS | recuperación 0.6 s |
| 2. Caída y recuperación de gSPAd | PASS | recuperación 0.6 s |

## Registro de eventos

- `16:09:57` Esperando a que los 4 grupos se registren y queden conectados al central simulado
- `16:09:57` PRUEBA 1 conversación global: cada grupo escribe 10 mensajes a la vez (convde7b90)
- `16:09:58` convergencia: 0.6 s
- `16:09:58` PRUEBA 2 turno de gSPAa: apaga su servidor (SIGKILL); los demás escriben 20 mensajes
- `16:10:05` gSPAa vuelve
- `16:10:07` gSPAa recuperado en 1.1 s
- `16:10:07` PRUEBA 2 turno de gSPAb: apaga su servidor (SIGKILL); los demás escriben 20 mensajes
- `16:10:13` gSPAb vuelve
- `16:10:15` gSPAb recuperado en 1.1 s
- `16:10:15` PRUEBA 2 turno de gSPAc: apaga su servidor (SIGKILL); los demás escriben 20 mensajes
- `16:10:22` gSPAc vuelve
- `16:10:23` gSPAc recuperado en 0.6 s
- `16:10:23` PRUEBA 2 turno de gSPAd: apaga su servidor (SIGKILL); los demás escriben 20 mensajes
- `16:10:30` gSPAd vuelve
- `16:10:31` gSPAd recuperado en 0.6 s
- `16:10:31` Heartbeat del central a los grupos (GET /fed/health): {'gSPAb': True, 'gSPAa': True, 'gSPAc': True, 'gSPAd': False}

## Qué funcionó / qué falló / hallazgos

**Funcionó** (corrida final, central simulado): la conversación global converge en 0,6 s con el mismo orden en los 4 grupos, y los 4 grupos se recuperan tras `SIGKILL` en 0,6–1,1 s. En el log cada recuperación descarta duplicados (p. ej. gSPAb: `total=80 nuevos=20 duplicados=60`) y no hay `Traceback`.

**Falló en la primera corrida:** la prueba 1 dio FAIL (gSPAb vio 10 de 40 mensajes). Causa: el central se reinició y perdió el registro; gSPAb solo vio 1 fallo de salud (menos que K=3), no se declaró en caída y no recuperó historial. Se corrigió el servidor (re-registro y sincronización tras cualquier fallo corto) y se exige que los 4 grupos figuren en el registro del central antes de empezar. Tras el arreglo pasó.

**Hallazgos y límites:** (1) cada recuperación con `since=0` baja todo el historial y descarta la mayoría como duplicado; (2) sigue abierto el caso de un reinicio del central entre dos sondas sin fallo visible (hasta 30 s sin registro); (3) el `heartbeat` del central mostró `False` para el último grupo reiniciado: probablemente aún no se había sondeado tras volver (hipótesis, no verificada); (4) esto prueba que **nuestro** código converge, no interoperabilidad con servidores de otros equipos.

