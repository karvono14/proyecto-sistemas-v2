# Experimento (a): pérdidas y duplicados ante la caída del servidor del grupo

## Pregunta
¿Cuántos mensajes se pierden o se duplican cuando el servidor del grupo (gSPAa) se cae unos segundos
mientras otro servidor (gSPAb) le envía mensajes a tasa fija?

## Hipótesis (escritas ANTES de medir; falsables)
- **H-a1.** Con recuperación de historial activada, los mensajes perdidos al final son **0** para todas las
  duraciones de caída probadas.
- **H-a2.** Sin recuperación de historial (control), se pierden los mensajes que el central simulado
  deja de reenviar: aproximadamente `tasa × max(0, caída − ~3.5 s)`. El 3.5 s sale de la configuración
  del central simulado (4 intentos con esperas de 0.5, 1 y 2 s) y es **específico del simulado**.
- **H-a3.** Los duplicados **almacenados** son 0 por diseño (el id es clave de un hash de Redis). Habrá
  duplicados **descartados** (mensajes que llegan por reenvío del central y otra vez por `/history`).

## Qué se mide (por repetición)
| Columna | Definición |
|---|---|
| `sent` | mensajes que gSPAb confirmó con 201 |
| `missing` | enviados que NO están en el historial de gSPAa al final |
| `extra` | mensajes de la prueba en gSPAa que no figuran como enviados |
| `dup_stored` | ids repetidos dentro del historial de gSPAa |
| `dup_discarded_fed/history` | veces que gSPAa recibió un id ya conocido y lo descartó (líneas `DUPLICATE` del log) |
| `forward_giveups` | reenvíos que el central simulado abandonó (solo existe en el simulado) |
| `recovery_s` | segundos desde `docker compose start` hasta que gSPAa tiene todo lo enviado antes de volver |

## Método
1. `kill` (SIGKILL) del contenedor `server-a`; espera `down_s`; `start`.
2. gSPAb envía a tasa fija durante `pre` s + caída + `post` s.
3. Se repite `--reps` veces (mínimo del enunciado: 3) por cada combinación de tasa y duración.
4. Grupo de control: `--history-sync off` desactiva SOLO la recuperación de historial de gSPAa.
   El script siempre deja el laboratorio con la recuperación **activada** al terminar.

## Cómo ejecutarlo
```bash
docker compose -f docker-compose.local.yml up --build -d
python experiment/run_experiment.py --down 2 5 10 --reps 3 --history-sync both
python experiment/analyze.py
```
Opcional (suma en la evaluación): varía `--rate 5 20` o `--down 2 5 10 20`.

## Validez y límites
- Los resultados valen para el **central simulado** y para Redis con `appendfsync everysec`. Hay que repetir
  la medición contra el central real en la sesión de interoperabilidad antes de ponerlos en el póster.
- `docker compose kill` mata el servidor, no Redis. No se mide la caída de Redis.
- Todo corre en una sola máquina: la latencia de red es casi nula y no representa la sala de clase.
- `down_s` es nominal: el tiempo real incluye lo que tarden `kill` y `start`.
