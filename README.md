# Chat distribuido entre grupos — grupo gSPAa (UIS · Sistemas Distribuidos)

Servidor de chat en contenedores (Python + FastAPI + Redis) que se conecta a un servidor central y comparte la sala
global `#general`. **Estado de la validación:** todo se probó contra un **central simulado** escrito por nosotros
(`mock_central/`), a partir del enunciado; **no** contra el central ni el script de conformidad del profesor.
El protocolo provisional (`server/app/protocol.py`, `models.py`) se da por definitivo por decisión del grupo.

## Levantar

Laboratorio local (central simulado + 2 grupos, un solo comando, sin configurar nada):
```bash
docker compose -f docker-compose.local.yml up --build -d
curl localhost:8000/fed/health        # {"server":"gSPAa","lamport":...}
python client/cli.py --user ana       # cliente (pip install requests)
```
Un grupo contra un central externo:
```bash
cp .env.example .env     # editar GROUP_NAME, PUBLIC_URL, CENTRAL_URL
docker compose up --build -d
```
Sesión de 4 grupos: `docker compose -f docker-compose.sesion.yml up --build -d && python tests/sesion_local.py`.
Limpiar todo: `docker compose -f docker-compose.local.yml down -v`.

## Variables de entorno (servidor)
| Variable | Por defecto | Significado |
|---|---|---|
| `GROUP_NAME` (obligatoria) | — | nombre del grupo (`gSPAa`) |
| `PUBLIC_URL` (obligatoria) | — | URL con la que el central alcanza este servidor |
| `CENTRAL_URL` (obligatoria) | — | URL del central; nunca está en el código |
| `REDIS_URL` (obligatoria) | — | almacenamiento |
| `HEALTH_INTERVAL` / `HEALTH_FAILURES` | 2 s / 3 | heartbeat y fallos seguidos para marcar el central caído |
| `HEALTH_TIMEOUT` / `REQUEST_TIMEOUT` / `HISTORY_TIMEOUT` | 2 / 3 / 30 s | timeouts de `/health`, `POST /messages`, `/history` |
| `BACKOFF_INITIAL` / `BACKOFF_CAP` | 0,5 / 8 s | backoff exponencial con tope |
| `REGISTER_INTERVAL` | 30 s | renovación del registro |
| `MAX_BODY_CHARS` | 2000 | límite de `body` solo para mensajes **locales** |
| `HISTORY_SYNC` | true | **solo para el experimento**: `false` desactiva la recuperación de historial (incumple el req. 9) |

## Estructura
`server/` servidor · `client/` CLI · `mock_central/` central simulado · `experiment/` experimento (a) ·
`tests/` pruebas · `demo/` guion del video · `docs/` `PRUEBAS.md`, `ARQUITECTURA.md`, `BITACORA.md`, `POSTER.md`, `PREGUNTAS.md`.

## Decisiones de diseño (todas con su concepto del libro, *Understanding Distributed Systems*)
| Decisión | Por qué | Cap. |
|---|---|---|
| Un mensaje se guarda y se encola en el *outbox* en una sola operación atómica (script Lua en Redis) | si el proceso cae entre ambas, no queda un mensaje a medias | 5.7 |
| Entrega al menos una vez: el mensaje sale del outbox solo con un 2xx (o un 4xx, que se registra) | no hay *exactly-once*; se simula con reintentos + idempotencia | 27.2, 23.2 |
| Deduplicación por `id` en Redis (`HSETNX`), persistida | reintentar nunca duplica, ni siquiera tras reiniciar | 5.7 |
| 5xx o sin respuesta → reintento; 4xx → no se reintenta y se registra | un 4xx no mejora reintentando | 5.4 |
| `timeout` en toda llamada; backoff exponencial con tope y *jitter* | evita esperar para siempre y reintentos sincronizados | 27.1, 27.2.1 |
| `GET /health` periódico; "caído" tras K fallos seguidos; el log distingue `timeout` / `http_5xx` / `conn_error` | un detector perfecto no existe: lento ≠ caído | 7 |
| Reloj de Lamport persistido: `incr` antes de enviar; `max(local, recibido)+1` al recibir | orden sin reloj global; sobrevive a reinicios | 8.2 |
| `sent_at` nunca ordena | los relojes físicos no sirven entre máquinas | 8.1 |
| Orden `(lamport, origin)` con separador `\x00` en el `zset` | desempate determinista en todos los servidores | 8.2 |
| Al arrancar y al volver de una caída: registro + `GET /history?since=0` | recuperar lo perdido; duplicados descartados por id (costo medido: ver `experiment/RESULTADOS.md`) | 6, 7 |

## Límites conocidos
Ver la tabla de límites en `docs/PRUEBAS.md`. Los principales: sin autenticación en `/fed/*` (el protocolo no la define),
sin tope de tamaño de petición, la tabla de ids vistos no se purga (≈ 400 B por mensaje en Redis), la recuperación usa
`since=0`, y un central lento (> 2 s en `/health`) se marca como caído.
