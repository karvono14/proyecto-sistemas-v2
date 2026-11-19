# Resultados del experimento (a): pérdidas y duplicados ante la caída de gSPAa

**Datos:** `experiment/results/final.csv` (18 repeticiones). **Figura:** `fig_resultados.png`.
**Condiciones:** central **simulado**; 10 msg/s desde gSPAb; caída de gSPAa con `SIGKILL` de 2, 5 y 10 s;
3 repeticiones por caso; laboratorio limpio; recuperación medida con consultas cada 0,5 s (incertidumbre ≈ ±0,5 s).

## Tabla (media [mín–máx], en mensajes salvo donde se indica)

| Recuperación de historial | Caída (s) | Enviados | Perdidos | % perdido | Duplicados descartados | Recuperación (s) |
|---|---|---|---|---|---|---|
| con | 2 | 144 | **0** [0–0] | 0 % | 67 [66–67] | 1,2 [1,03–1,38] |
| con | 5 | 176 | **0** [0–0] | 0 % | 69 [67–72] | 1,1 [1,05–1,10] |
| con | 10 | 228 | **0** [0–0] | 0 % | 115 [114–115] | 1,3 [1,12–1,62] |
| sin (control) | 2 | 146 | 2,3 [0–6] | 1,6 % | 0 | n/d |
| sin (control) | 5 | 175 | 25 [24–26] | 14,3 % | 0 | n/d |
| sin (control) | 10 | 224 | 33 [33–33] | 14,7 % | 0 | n/d |

Duplicados **almacenados** y mensajes de más: 0 en las 18 repeticiones.

## Hipótesis frente a resultados

| Hipótesis | Resultado |
|---|---|
| H-a1: con recuperación, 0 pérdidas | **Confirmada** (9 de 9 en laboratorio limpio; 18 de 18 contando la primera tanda) |
| H-a2: sin recuperación, pérdidas ≈ tasa × (caída − 3,5 s) | **Refutada.** Predicha: 0 / 15 / 65. Observada: 2,3 / 25 / 33 |
| H-a3: 0 duplicados almacenados, algunos descartados | **Confirmada** |

## Hallazgos

1. **La pérdida sin recuperación es exactamente lo que el central abandona:** en las 9 repeticiones del control,
   mensajes perdidos = reenvíos abandonados por el central. La recuperación por `/history` repara todos.
2. **Recuperación en ≈ 1–1,6 s**, aparentemente independiente de la duración de la caída (3 repeticiones por caso:
   no está demostrado).
3. **Costo de recuperar con `since=0`:** 67–115 duplicados descartados por repetición (el servidor vuelve a recibir lo
   que ya tenía). Es correcto, pero crece con el historial; pendiente de preguntar al profesor qué `since` usar.

## Hipótesis descartada: el tamaño del grupo de hilos del central simulado

Sospechaba que el 33 del control con 10 s de caída venía de los 32 hilos con que el central simulado reenvía. Se probó
cambiando `FORWARD_WORKERS` (sin recuperación, caída de 10 s, 3 repeticiones cada una):

| Hilos del central | Perdidos |
|---|---|
| 8 | 33, 34, 33 |
| 32 (por defecto) | 33, 33, 33 |
| 128 | 33, 33, 33 |

La pérdida **no depende** del tamaño del grupo de hilos: la hipótesis queda refutada. Sigue **sin explicación** por
qué la pérdida se estabiliza en ≈ 33 (≈ 3,3 s de tráfico) cuando la caída pasa de 5 s (25) a 10 s (33). Para averiguarlo,
el script ahora anota cuándo, en segundos desde la caída, se enviaron el primer y el último mensaje perdido
(`lost_first_s`, `lost_last_s`). Es una corrida corta (≈ 2,5 min), con laboratorio limpio:

```bash
python experiment/run_experiment.py --down 10 --reps 3 --history-sync off --recovery-timeout 20 --out experiment/results/diag.csv
```

En el póster no atribuyas esa cifra a una causa: di solo que depende del comportamiento de reenvío del central.

## Procedencia y descartes

- `results.csv` (primera tanda): se hizo con un laboratorio con historial muy grande (restos de la prueba A4). Su
  `recovery_s` (4,4–6,7 s) y la dispersión del control a 5 s (1, 6 y 29 perdidos) **no se usan**: con laboratorio limpio
  el control dio 24, 25 y 26. El mecanismo exacto de esa diferencia no está establecido.
- `recuperacion.csv` (con recuperación) y `control.csv` (sin recuperación), ambos en laboratorio limpio, forman `final.csv`.

## Qué se puede y qué no decir en el póster

- Se puede: con el central simulado, a 10 msg/s, cada caída del servidor de 2 a 10 s se recuperó sin pérdidas ni
  duplicados almacenados; sin recuperación se perdió entre 0 y 15 % de los mensajes.
- No se puede: extrapolar a otras tasas, a Redis caído, o al central real; ni dar `recovery_s` con precisión de décimas.
  Hay que repetir la medición contra el central real en la sesión de interoperabilidad.
