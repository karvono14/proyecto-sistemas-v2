# Bitácora de la sesión de interoperabilidad **local**

> Central **simulado** y 4 grupos que ejecutan **nuestro** servidor. Prueba que nuestro código converge; **no** prueba interoperabilidad con implementaciones de otros equipos.

Fecha (UTC): 2026-11-19

## Resultados

| Prueba | Resultado | Detalle |
|---|---|---|
| 1. Conversación global (4 grupos × 10 mensajes) | PASS | convergencia 0.6 s |
| 2. Caída y recuperación de gSPAa | PASS | recuperación 0.5 s |
| 2. Caída y recuperación de gSPAb | PASS | recuperación 1.1 s |
| 2. Caída y recuperación de gSPAc | PASS | recuperación 1.1 s |
| 2. Caída y recuperación de gSPAd | PASS | recuperación 0.6 s |

## Registro de eventos

- `15:26:59` Esperando a que los 4 grupos se registren y queden conectados al central simulado
- `15:26:59` PRUEBA 1 conversación global: cada grupo escribe 10 mensajes a la vez (conva3a233)
- `15:27:00` convergencia: 0.6 s
- `15:27:00` PRUEBA 2 turno de gSPAa: apaga su servidor (SIGKILL); los demás escriben 20 mensajes
- `15:27:07` gSPAa vuelve
- `15:27:08` gSPAa recuperado en 0.5 s
- `15:27:08` PRUEBA 2 turno de gSPAb: apaga su servidor (SIGKILL); los demás escriben 20 mensajes
- `15:27:15` gSPAb vuelve
- `15:27:17` gSPAb recuperado en 1.1 s
- `15:27:17` PRUEBA 2 turno de gSPAc: apaga su servidor (SIGKILL); los demás escriben 20 mensajes
- `15:27:23` gSPAc vuelve
- `15:27:26` gSPAc recuperado en 1.1 s
- `15:27:26` PRUEBA 2 turno de gSPAd: apaga su servidor (SIGKILL); los demás escriben 20 mensajes
- `15:27:32` gSPAd vuelve
- `15:27:34` gSPAd recuperado en 0.6 s
- `15:27:34` Heartbeat del central a los grupos (GET /fed/health): {'gSPAb': True, 'gSPAc': True, 'gSPAd': False, 'gSPAa': True}

## Qué funcionó / qué falló / hallazgos

_(completar a mano tras leer los logs: `docker compose -f docker-compose.sesion.yml logs`)_
