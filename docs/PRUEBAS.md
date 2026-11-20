# Pruebas y límites de la aplicación (grupo gSPAa) — categorías A a G

> **Estado:** pruebas A–G ejecutadas en el laboratorio local; ninguna con FAIL abierto (E6 falló una vez por la propia prueba y pasó al repetirla). Quedan **sin datos**: A1 (falta el script oficial), el reinicio del equipo de F2, la parte de descriptores y de disco lleno de E7. La columna **Esperado** conserva la hipótesis original;
> **Observado** resume lo medido. La categoría H (sesión de clase) se sustituye por `tests/sesion_local.py` y `docs/BITACORA.md`.
>
> **Ojo con el origen de los datos:** el laboratorio local usa un **central simulado** escrito por nosotros
> (`mock_central/`). Un resultado obtenido ahí vale para el simulado, no para el central del profesor. Pasar estas
> pruebas **no** sustituye al script de conformidad oficial.

## Cómo ejecutar

```bash
docker compose -f docker-compose.local.yml up --build -d
python tests/run_tests.py --list              # ver las pruebas
python tests/run_tests.py --cat A             # una categoría
python tests/run_tests.py A2 B1 C3            # pruebas concretas
python tests/run_tests.py --all --reset-first # todas (menos las pesadas), desde un laboratorio limpio
python tests/run_tests.py B5 --b5-sizes 1000 10000 100000   # medición pesada: se pide por ID
```

Requisitos: ejecutar desde la raíz del repo, `pip install requests`. Cada ejecución añade una fila a
`tests/results/results.csv` y las pruebas de medición escriben su detalle en `tests/results/<ID>.csv`.

Estados: **PASS** (cumple), **FAIL** (el sistema incumple el criterio), **INFO** (medición: anota el valor; los
criterios binarios de la prueba siguen aplicando), **SKIP**, **ERROR** (falló el entorno o el propio script, no
es un fallo del sistema).

Precondición común: laboratorio levantado y **en reposo** (nadie más enviando). B5 y C2 alteran datos o el reloj:
el ejecutor limpia el laboratorio (`down -v`) cuando terminan.

## Hallazgos por análisis del diseño (antes de ejecutar nada)

Al diseñar las pruebas aparecieron tres defectos del código de la etapa 3. Los comprobé con aritmética y
ordenamiento en Python, **no** contra Redis real. Ya están corregidos en esta entrega, y las pruebas C3, C2 y
B2/C1 existen para confirmar el comportamiento en el sistema real.

1. **Desempate por `origin` incorrecto.** El miembro del `zset` era `origin|id`. Como `|` es mayor que
   cualquier dígito o letra, `g10` quedaba **antes** que `g1` (con 10 o más grupos se rompe el orden
   `(lamport, origin)`). Corrección: separador `\x00`, menor que cualquier carácter. Prueba: **C3**.
2. **Precisión del reloj.** Redis ejecuta el script Lua con `double`; `2^53 + 1` no es representable
   (`float(2**53+1) == float(2**53)`), así que `max+1` dejaba de avanzar. Corrección: tope `lamport <= 2^53 - 2`.
   Prueba: **C2** (mide el comportamiento en los extremos).
3. **`GET /api/messages?since=0` ocultaba los mensajes con `lamport = 0`.** Corrección: `since <= 0` devuelve todo.

## Índice

| ID | Prueba | Auto | Verifica |
|---|---|---|---|
| A1 | Script de conformidad oficial | manual | req. 4–9 |
| A2 | Campos desconocidos se ignoran | sí | regla del protocolo |
| A3 | Campos faltantes / tipos inválidos → 4xx | sí | regla 4xx |
| A4 | Contenido: id, body vacío/largo, Unicode, control | sí | robustez |
| A5 | `from` ≠ `origin` | sí | consistencia del mensaje |
| A6 | 4xx del central: no se reintenta, queda en log | sí | req. 6, 11 |
| A7 | 5xx del central: se reintenta y se entrega *(añadida)* | sí | req. 6 |
| B1 | Mismo id 2/10/1000 veces | sí | req. 6 (idempotencia) |
| B2 | Duplicados concurrentes | sí | req. 6 |
| B3 | Respuesta 200 perdida | sí | req. 6 |
| B4 | Duplicado tras reinicio / SIGKILL | sí | req. 2, 6 |
| B5 | Crecimiento de la tabla de ids vistos | sí (pesada) | límite |
| C1 | Reglas de Lamport a mano | sí | req. 7 |
| C2 | Lamport en los extremos | sí (destructiva) | req. 7, límite |
| C3 | Mismo lamport, distinto origin | sí | req. 7 |
| C4 | Orden independiente de `sent_at` | sí | req. 7 |
| C5 | Ráfaga concurrente, mismo orden | sí | req. 7, interop. |
| D1 | Caída de mi servidor con tráfico | sí | req. 6, 9 |
| D2 | Caída del central, cola y reenvío | sí | req. 8 |
| D3 | SIGKILL en plena ráfaga | sí | req. 2, integridad |
| D4 | Reinicios repetidos (flapping) | sí | req. 9 |
| D5 | Partición de red | sí | req. 8, 9 |
| D6 | Central lento: backoff sin tormenta | sí | req. 6 |
| D7 | Central lento vs caído | sí | req. 8 |
| D8 | Falsos positivos del detector | sí | req. 8 |
| E1 | Rampa de tasa 1/10/100/1000 msg/s | sí (pesada) | límite |
| E2 | Ráfaga de 10 000 mensajes | sí (pesada) | límite |
| E3 | Cola de pendientes grande | sí (pesada) | req. 8, límite |
| E4 | Muchos usuarios y clientes | sí | límite |
| E5 | Historial grande (`/history?since=0`) | sí (pesada) | req. 9, límite |
| E6 | Backoff: tope y conservación | sí | req. 6 |
| E7 | Agotamiento de recursos | manual | límite |
| F1 | `down`/`up` con y sin `-v` | sí (destructiva) | req. 2 |
| F2 | `restart` | sí | req. 2 |
| F3 | Equipo limpio | manual (`clean_clone.sh`) | req. 1 |
| F4 | Variables de entorno faltantes/inválidas | sí | req. 1, 4 |
| F5 | Cambio de URL pública | sí | req. 4 |
| F6 | Renovación y pérdida del registro | sí | req. 4 |
| G1 | Entradas maliciosas | sí | robustez |
| G2 | JSON enorme o anidado | sí | robustez |
| G3 | `/fed/*` por un tercero; suplantación | sí | limitación |
| G4 | Límites de tamaño de petición | documental | límite |
| H | Interoperabilidad: sesión local de 4 grupos | `tests/sesion_local.py` | sec. 7 |

---

## A. Conformidad y protocolo

### A1 — Script de conformidad oficial completo
| Campo | Contenido |
|---|---|
| Objetivo | Confirmar que cumplimos el protocolo oficial, no solo nuestra lectura del enunciado. |
| Verifica | Requisitos 4–9 y todas las reglas de la sección 4 del enunciado. |
| Precondiciones | Tener la OpenAPI y el script oficiales; `protocol.py` y `models.py` ajustados a la OpenAPI; servidor accesible por el script. |
| Pasos | Ejecutar el script del profesor contra gSPAa. Guardar la salida completa en `docs/conformidad.txt`. |
| Esperado (hipótesis) | Pasa completo después de ajustar `protocol.py` y `models.py`. Antes de ajustar, es probable que fallen los formatos de respuesta. |
| Observado | No ejecutada: es manual y falta el script oficial. |
| Aprobado / fallo | Aprobado: todas las comprobaciones en verde. Fallo: cualquiera en rojo (cada una se convierte en un hallazgo). |
| Libro | 5.5 OpenAPI (p. 43): la especificación como contrato. |

### A2 — Campos desconocidos se ignoran sin error
| Campo | Contenido |
|---|---|
| Objetivo | Aceptar mensajes con campos extra sin fallar (compatibilidad con otras implementaciones). |
| Verifica | Regla: "los campos desconocidos se ignoran sin error". |
| Precondiciones | Laboratorio en reposo. |
| Pasos | `python tests/run_tests.py A2` — envía a `/fed/messages` un mensaje válido con tres campos extra (objeto, lista, número). |
| Esperado (hipótesis) | 200 y el mensaje queda guardado (sin los campos extra). |
| Observado | **PASS** (simulado). 200 y mensaje guardado. |
| Aprobado / fallo | Aprobado: 200 y guardado. Fallo: 4xx, 5xx o no guardado. |
| Libro | 5.6 Evolución (p. 45): compatibilidad hacia atrás de las APIs. |

### A3 — Campos faltantes o tipos inválidos
| Campo | Contenido |
|---|---|
| Objetivo | Rechazar mensajes mal formados con 4xx y sin efectos. |
| Verifica | Regla: 4xx no se reintenta; validación del formato de mensaje. |
| Precondiciones | Laboratorio en reposo. |
| Pasos | `python tests/run_tests.py A3` — 30 casos: cada campo ausente, tipos erróneos (`lamport` como texto, decimal, booleano, nulo, lista; `id` numérico…), y cuerpos que no son un objeto JSON. Detalle en `tests/results/A3.csv`. |
| Esperado (hipótesis) | Todos 4xx (422) y el contador de mensajes guardados no cambia. |
| Observado | **PASS** (simulado). 30 de 30 casos → 422; no se guardó ningún mensaje. |
| Aprobado / fallo | Aprobado: todos 4xx y nada guardado. Fallo: algún 2xx o 5xx, o se guardó algo. |
| Libro | 5.4 Códigos de estado (p. 42): 4xx = error del cliente, no se reintenta. |

### A4 — Contenido: id mal formado, body vacío o largo, Unicode, caracteres de control
| Campo | Contenido |
|---|---|
| Objetivo | Conocer cómo se comporta ante contenido extremo, y **medir** el tamaño máximo de body (no asumirlo). |
| Verifica | Robustez; decisiones H6 y H7 (validación estructural; `body` sin límite ni mínimo en lo entrante). |
| Precondiciones | Laboratorio en reposo. Para probar más de 1 MB: `--max-body-mb 10` (deja mensajes grandes en el historial; limpiar después). |
| Pasos | `python tests/run_tests.py A4` — `id` corto, vacío, con basura, en mayúsculas; `body` vacío; emojis, árabe y chino; `\x00`, `\x1f`, RLO (`\u202e`), saltos de línea; cuerpos de 1 KB a 1 MB (o más). Detalle en `tests/results/A4.csv`. |
| Esperado (hipótesis) | `id` malformado → 4xx. Unicode y control → 200 con ida y vuelta **exacta**. `body` vacío y `id` en mayúsculas → aceptados (se anota). Tamaño: sin tope en el servidor (nadie lo limita todavía). |
| Observado | **INFO** (simulado). `id` corto, vacío y con basura → 422. `id` en mayúsculas → 200, guardado tal cual (la deduplicación distingue mayúsculas: *hipótesis sin probar*). `body` vacío → 200 (H7 confirmada). Unicode, caracteres de control y 10 KB → 200 con ida y vuelta exacta. 1, 10, 100, 1000, 5000, 10000 y 50000 KB → 200 (50 MB en 0,94 s). **No se encontró ningún límite hasta 50 MB:** el servidor no impone tope de tamaño de petición (limitación a documentar en la categoría G). |
| Aprobado / fallo | Aprobado: `id` malformado → 4xx; Unicode y control con ida y vuelta exacta. Los demás son **INFO**: se documentan, y los que contradigan al protocolo oficial se llevan al foro (duda 5). |
| Libro | 5.4 (p. 42). |

### A5 — `from` que no coincide con `origin`
| Campo | Contenido |
|---|---|
| Objetivo | Rechazar mensajes cuyo `from` no es `usuario@origin`. |
| Verifica | Consistencia del mensaje (decisión H6, duda 6 del foro). |
| Precondiciones | Laboratorio en reposo. |
| Pasos | `python tests/run_tests.py A5` — `from=ana@g3` con `origin=g4`; `from` sin `@`; `from` sin usuario. |
| Esperado (hipótesis) | Los tres → 4xx. |
| Observado | **PASS** (simulado). Los tres casos → 422. |
| Aprobado / fallo | Aprobado: 4xx en los tres. Fallo: alguno aceptado. **Ojo:** si el protocolo oficial lo permite, el fallo es de nuestra regla y se corrige. |
| Libro | 5.4 (p. 42). |

### A6 — 4xx del central: no se reintenta y queda en el log
| Campo | Contenido |
|---|---|
| Objetivo | Comprobar que un rechazo definitivo del central no genera reintentos y se registra. |
| Verifica | Regla: "4xx no se reintenta y se registra"; requisitos 6 y 11. |
| Precondiciones | Central simulado arriba; usuario `tester` en gSPAa. |
| Pasos | `python tests/run_tests.py A6` — activa `force-status 400` en el central, envía un mensaje, espera 6 s, cuenta cuántas veces llegó el id al central y busca `SEND_REJECTED` en el log. Siempre restaura el central. |
| Esperado (hipótesis) | 1 intento en el central; contador `rejected` +1; el mensaje sale del outbox; línea `SEND_REJECTED id=… status=400` en el log. |
| Observado | **PASS** (simulado). 1 intento en el central; `rejected` +1; línea `SEND_REJECTED` en el log. |
| Aprobado / fallo | Aprobado: exactamente 1 intento y línea en el log. Fallo: más de 1 intento, mensaje que sigue en el outbox, o sin log. |
| Libro | 5.4 (p. 42); 27.2 Retry (p. 255): reintentar solo lo que puede tener éxito. |

### A7 — 5xx del central: se reintenta y se entrega al volver *(añadida)*
| Campo | Contenido |
|---|---|
| Objetivo | Complemento de A6: ante 5xx sí hay reintentos con backoff y, al normalizarse el central, el mensaje llega una sola vez. |
| Verifica | Requisito 6 (entrega al menos una vez). |
| Precondiciones | Como A6. |
| Pasos | `python tests/run_tests.py A7` — fuerza 503 durante 12 s, cuenta intentos y líneas `SEND_RETRY`, quita el 503 y espera la entrega en gSPAb. |
| Esperado (hipótesis) | ≥ 3 intentos en 12 s; el mensaje queda pendiente; tras quitar el 503 llega a gSPAb exactamente 1 vez y el outbox se vacía. |
| Observado | **PASS** (simulado). Dos corridas: 10 y 8 intentos en 12 s; el mensaje llegó 1,52 s y 4,56 s después de quitar el 503, con 1 copia en gSPAb. La variación viene del jitter del backoff. |
| Aprobado / fallo | Aprobado: lo anterior. Fallo: < 3 intentos, 0 o 2+ copias en gSPAb, o outbox que no se vacía. |
| Libro | 27.2 Retry y 27.2.1 (p. 255–256). |

---

## B. Idempotencia y deduplicación

### B1 — Mismo id 2, 10 y 1000 veces seguidas
| Campo | Contenido |
|---|---|
| Objetivo | Un id repetido tiene un solo efecto y siempre responde 200. |
| Verifica | Regla de idempotencia; requisito 6. |
| Precondiciones | Laboratorio en reposo. |
| Pasos | `python tests/run_tests.py B1` — por cada n ∈ {2, 10, 1000}: n envíos secuenciales del mismo mensaje; cuenta respuestas, copias guardadas y movimiento del reloj. Detalle en `tests/results/B1.csv`. |
| Esperado (hipótesis) | Todo 200; 1 copia; el reloj avanza una sola vez (`max(local, recibido)+1`) y los duplicados no lo mueven (H4). |
| Observado | **PASS** (simulado). Se cumplen los tres n (2, 10 y 1000); el detalle numérico está en `tests/results/B1.csv`. |
| Aprobado / fallo | Aprobado: lo anterior para los tres n. Fallo: respuesta ≠ 200, copias ≠ 1, o el reloj se mueve con duplicados. |
| Libro | 5.7 Idempotencia (p. 46); 23.2 Exactly-once (p. 223). |

### B2 — Duplicados concurrentes (condición de carrera)
| Campo | Contenido |
|---|---|
| Objetivo | Comprobar que la deduplicación es atómica cuando el mismo id llega en paralelo. |
| Verifica | Requisito 6. |
| Precondiciones | Laboratorio en reposo (el reloj se usa como contador). |
| Pasos | `python tests/run_tests.py B2` — 30 ids, cada uno enviado 20 veces desde 20 hilos en orden aleatorio (600 peticiones, `lamport=0`). |
| Esperado (hipótesis) | 30 guardados; el reloj avanza exactamente 30; todo 200. |
| Observado | **PASS** (simulado). 600 peticiones, 30 guardados, el reloj avanzó exactamente 30. |
| Aprobado / fallo | Aprobado: lo anterior. Fallo: más de 30 guardados o avance distinto de 30 (carrera). |
| Libro | 5.7 (p. 46): guardar el id y ejecutar la operación debe ser atómico (aquí, un script Lua). |

### B3 — Respuesta 200 perdida
| Campo | Contenido |
|---|---|
| Objetivo | Si la respuesta del central se pierde, el emisor reintenta y no se duplica. |
| Verifica | Requisito 6; Fig. 3 del enunciado. |
| Precondiciones | Central simulado arriba. |
| Pasos | `python tests/run_tests.py B3` — el central procesa el mensaje pero tarda más que el timeout en responder (`lose-response`); el emisor expira y reintenta con el mismo id. **Variante manual** con `tcpspy.py` del taller de sockets si se quiere el proxy real. |
| Esperado (hipótesis) | ≥ 2 intentos en el central; 1 copia en el central; 1 copia en gSPAb; outbox vacío. |
| Observado | **PASS** (simulado). 2 intentos; el mensaje llegó a gSPAb a los 3,55 s; 1 copia en el central y 1 en gSPAb. |
| Aprobado / fallo | Aprobado: lo anterior. Fallo: 1 solo intento (no se probó la pérdida), o copias ≠ 1. |
| Libro | 2.1 Fiabilidad (p. 18): retransmisión y confirmaciones; 27.1 Timeout (p. 253); 5.7 (p. 46). |

### B4 — Duplicado tras reiniciar el servidor
| Campo | Contenido |
|---|---|
| Objetivo | La deduplicación y el reloj sobreviven a `restart` y a `SIGKILL`. |
| Verifica | Requisitos 2 y 6. |
| Precondiciones | Laboratorio en reposo. |
| Pasos | `python tests/run_tests.py B4` — envía un mensaje, espera 2 s (para que AOF sincronice), reinicia Redis y servidor (`restart`; luego `kill -s SIGKILL`), reenvía el mismo id. |
| Esperado (hipótesis) | 200; 1 copia; el reloj no retrocede tras el reinicio y el duplicado no lo mueve. |
| Observado | **PASS**. `restart`: 1 copia, reloj 69→69→69. `SIGKILL`: 1 copia, reloj 75→75→75. |
| Aprobado / fallo | Aprobado: lo anterior en ambas variantes. Fallo: 2 copias, o el reloj retrocede. |
| Libro | 8.2 Relojes de Lamport (p. 65): para soportar crash-recovery se persiste el estado del reloj; cap. 6 (p. 57): modelo crash-recovery. |

### B5 — Crecimiento de la tabla de ids vistos *(pesada)*
| Campo | Contenido |
|---|---|
| Objetivo | **Medir** cuánta memoria de Redis consume cada mensaje (que es también un id visto). No se asume un límite. |
| Verifica | Límite del diseño: la tabla de ids no se purga nunca. |
| Precondiciones | Laboratorio limpio; se ejecuta sola (limpia al terminar). |
| Pasos | `python tests/run_tests.py B5 --b5-sizes 1000 10000 100000` — inserta mensajes únicos por `/fed/messages` (16 hilos) y lee `used_memory` de Redis tras cada tramo. Detalle en `tests/results/B5.csv`. |
| Esperado (hipótesis) | Crecimiento aproximadamente lineal; el valor de bytes por mensaje es lo que se mide. Cualquier extrapolación a 1 M de mensajes es hipótesis hasta medirla. |
| Observado | **INFO**. Con una sesión por hilo, 1 000 / 10 000 / 50 000 mensajes, todo 200: 620 / 421 / 390 B por mensaje en cada tramo (≈ 400 de media; 21,3 MB de Redis con 50 000) y 822–835 msg/s con 16 hilos. La corrida anterior (conexión nueva por petición) falló tras 28 229 peticiones con un `ConnectionResetError`, y el log del servidor mostraba 28 229 respuestas 200 y ningún error. Al reutilizar conexiones, el mismo tamaño pasa: el fallo era del cliente de prueba (causa probable: agotamiento de puertos efímeros, cuyo rango por defecto en Linux es de 28 232) y no del servidor. Cuerpos de 36 caracteres; la extrapolación a 1 M (≈ 400 MB) es hipótesis. |
| Aprobado / fallo | INFO: se documenta el valor. Fallo solo si alguna petición no da 200. |
| Libro | 23.2 (p. 223): deduplicar exige recordar los ids ya vistos. |

---

## C. Reloj de Lamport y orden

### C1 — Reglas de Lamport con casos escritos a mano
| Campo | Contenido |
|---|---|
| Objetivo | Verificar `reloj+1` al enviar y `max(local, recibido)+1` al recibir. |
| Verifica | Requisito 7. |
| Precondiciones | Laboratorio en reposo. |
| Pasos | `python tests/run_tests.py C1` — envío local; recepción con m > local, m = local, m < local, m = 0; reenvío del último (duplicado). |
| Esperado (hipótesis) | Cada caso deja el reloj en el valor calculado a mano; el mensaje conserva su lamport original; el duplicado no mueve el reloj. |
| Observado | **PASS**. Envío local, cuatro recepciones y duplicado coinciden con lo calculado a mano. |
| Aprobado / fallo | Aprobado: todos los valores coinciden. Fallo: cualquier diferencia. |
| Libro | 8.2 Relojes lógicos (p. 65). |

### C2 — Lamport en los extremos *(destructiva)*
| Campo | Contenido |
|---|---|
| Objetivo | **Medir** el comportamiento con negativos, 2^31, 2^32, 2^53 y mayores, en vez de asumirlo. |
| Verifica | Requisito 7; decisión H6. |
| Precondiciones | Laboratorio limpio; deja el reloj cerca de 2^53, así que el ejecutor limpia todo al terminar. |
| Pasos | `python tests/run_tests.py C2` — 11 valores (−1, 0, 2^31−1, 2^31, 2^32, 2^53−2, 2^53−1, 2^53, 2^63, 10^30, 1.5). Detalle en `tests/results/C2.csv`. |
| Esperado (hipótesis) | Aceptados hasta 2^53−2 con reloj = max+1 exacto; negativos, ≥ 2^53−1, mayores y decimales → 4xx sin mover el reloj. Ningún 5xx. |
| Observado | **PASS**. Aceptados y exactos hasta 2^53−2; rechazados sin mover el reloj los demás casos; ningún 5xx (detalle en `tests/results/C2.csv`). |
| Aprobado / fallo | Aprobado: ningún 5xx, aceptados con valores exactos, rechazados sin efecto. Fallo: 5xx, pérdida de precisión, o reloj movido por un rechazo. Si el protocolo oficial permite enteros de 64 bits, el tope 2^53−2 es limitación nuestra y se documenta. |
| Libro | 8.2 (p. 65). El tope es decisión de implementación, no del libro. |

### C3 — Mismo lamport y distinto origin
| Campo | Contenido |
|---|---|
| Objetivo | El desempate por `origin` es determinista y es el mismo en todos los servidores. |
| Verifica | Requisito 7: orden `(lamport, origin)`. |
| Precondiciones | Laboratorio en reposo. |
| Pasos | `python tests/run_tests.py C3` — mensajes con el **mismo** lamport y orígenes `g1`, `g1-b`, `g10`, `g2`, `g3`, entregados en orden aleatorio a gSPAa y a gSPAb. |
| Esperado (hipótesis) | Ambos listan `g1, g1-b, g10, g2, g3`. (Con el separador `\|` del código anterior habría salido `g1-b, g10, g1…`: ver hallazgo 1.) |
| Observado | **PASS**. Ambos servidores: `g1, g1-b, g10, g2, g3`. Confirma la versión **corregida**; la versión anterior (separador `\|`) no se ejecutó, así que ese defecto se demostró solo con Python. |
| Aprobado / fallo | Aprobado: ambos servidores en ese orden. Fallo: orden distinto en alguno. |
| Libro | 8.2 (p. 65–66): operaciones no relacionadas pueden compartir marca lógica. |

### C4 — Orden independiente de `sent_at` *(adaptada)*
| Campo | Contenido |
|---|---|
| Objetivo | Comprobar que el orden sigue al Lamport y no al reloj físico. |
| Verifica | Regla: "`sent_at` es informativo y nunca ordena". |
| Precondiciones | Laboratorio en reposo. |
| Pasos | `python tests/run_tests.py C4` — tres mensajes con lamport creciente pero `sent_at` en 2099, 1970 y 2026, entregados al revés. |
| Esperado (hipótesis) | Orden por lamport en ambos servidores. |
| Observado | **PASS**. Orden por lamport en ambos servidores. |
| Aprobado / fallo | Aprobado: orden por lamport. Fallo: cualquier otro. |
| Libro | 8.1 Relojes físicos (p. 63). |

**Adaptación explícita:** tu lista pide cambiar la hora del contenedor. Eso exige capacidades de administrador (`SYS_TIME`) y un contenedor comparte el reloj del equipo, así que cambiarlo afectaría a toda la máquina. Se sustituye por manipular `sent_at`, que es el único dato de reloj físico que viaja en el protocolo. Es **menos** que una prueba con relojes desajustados de verdad. Alternativa segura si se quiere: una máquina virtual aparte con la hora cambiada.

### C5 — Ráfaga concurrente desde dos grupos
| Campo | Contenido |
|---|---|
| Objetivo | Tras una ráfaga concurrente, ambos servidores muestran exactamente el mismo orden. |
| Verifica | Requisito 7 y la prueba de interoperabilidad "mismo orden". |
| Precondiciones | Laboratorio en reposo; central simulado arriba. |
| Pasos | `python tests/run_tests.py C5` — 100 mensajes desde gSPAa y 100 desde gSPAb, en paralelo (16 hilos); espera hasta 90 s la convergencia y compara los dos historiales. |
| Esperado (hipótesis) | 200 mensajes en cada servidor; misma secuencia de ids; orden `(lamport, origin, id)`. |
| Observado | **PASS** (simulado). 200 mensajes; convergencia en 0,54 s; mismo orden. |
| Aprobado / fallo | Aprobado: lo anterior. Fallo: no convergen en 90 s, o el orden difiere. |
| Libro | 8.2 (p. 65). |

---

## D. Fallos parciales y recuperación

### D1 — Caída de mi servidor con mensajes llegando
| Campo | Contenido |
|---|---|
| Objetivo | gSPAa cae 10 s con gSPAb enviando a 10 msg/s; al volver recupera todo sin duplicar. |
| Verifica | Requisitos 6 y 9. Es una repetición del experimento (a). |
| Precondiciones | Laboratorio en reposo. |
| Pasos | `python tests/run_tests.py D1` — usa el mismo procedimiento que `experiment/run_experiment.py` con caída de 10 s. |
| Esperado (hipótesis) | 0 perdidos, 0 duplicados almacenados, 0 de más. |
| Observado | **PASS** (simulado). Dos corridas: 228 y 226 enviados, 0 perdidos y 0 duplicados almacenados; recuperación en 1,12 s y 1,07 s; **115 y 114 duplicados descartados** (en la segunda, 83 por reenvío del central y 31 por `/history`). La recuperación con `since=0` reenvía el historial completo (causa probable, no medida). |
| Aprobado / fallo | Aprobado: lo anterior. Fallo: cualquier pérdida o duplicado almacenado. |
| Libro | Cap. 6 (p. 57): modelo crash-recovery; cap. 7 (p. 61). |

### D2 — Caída del central (simulada)
| Campo | Contenido |
|---|---|
| Objetivo | Detección por heartbeat tras K fallos, cola de pendientes y reenvío al volver. |
| Verifica | Requisito 8. |
| Precondiciones | Laboratorio en reposo. |
| Pasos | `python tests/run_tests.py D2` — `/_admin/down`; 2 mensajes antes de la detección y 3 después; mide el tiempo hasta `central_down`; restaura; espera el vaciado. |
| Esperado (hipótesis) | Detección ≈ K × intervalo (6 s con los valores por defecto) y como máximo `K·(intervalo+timeout)+2` = 14 s; outbox = 5; al volver, gSPAb recibe exactamente esos 5. |
| Observado | **PASS** (simulado). Detección en 5,08 s (límite esperado 14 s); outbox vaciado 2,03 s después de volver; gSPAb recibió los 5. |
| Aprobado / fallo | Aprobado: lo anterior. Fallo: no detecta, detecta tarde, pierde pendientes o duplica. |
| Libro | Cap. 7 (p. 61–62): detección de fallos; 27.2 (p. 255). |

### D3 — SIGKILL de Redis y servidor en plena ráfaga
| Campo | Contenido |
|---|---|
| Objetivo | Verificar integridad tras una caída brusca y **medir** cuántos mensajes confirmados (201) se pierden. |
| Verifica | Requisito 2; límite de `appendfsync everysec`. |
| Precondiciones | Laboratorio en reposo. |
| Pasos | `python tests/run_tests.py D3` — 8 hilos envían a gSPAa; a los 1,5 s `kill -s SIGKILL` de `redis-a` y `server-a`; se reinician; se espera que el historial se estabilice. |
| Esperado (hipótesis) | Integridad correcta (`/api/messages` da 200 y su tamaño = mensajes guardados; sin ids repetidos). Posible pérdida de mensajes confirmados que no llegaron al central (≈ ventana de 1 s de AOF); los que sí llegaron se recuperan por `/history`. |
| Observado | **INFO**. Cuatro corridas: 872, 965, 964 y 963 mensajes confirmados (201), con 0 perdidos en todas; integridad correcta. **Salvedad:** lo que ya llegó al central se recupera por `/history`, así que esta prueba no aísla la durabilidad de Redis. Corrección a mi hipótesis: a mi entender, un `SIGKILL` del proceso de Redis no pierde escrituras confirmadas (el sistema operativo ya las tiene); la ventana de `everysec` aplica a caídas del sistema o de energía, que esta prueba no reproduce. |
| Aprobado / fallo | Integridad: PASS/FAIL. Perdidos: **INFO**, se documenta. Variante opcional: `appendfsync always` en el compose y repetir para comparar. |
| Libro | 8.2 (p. 65): persistir el reloj para crash-recovery; cap. 6 (p. 57). |

### D4 — Reinicios repetidos y seguidos (flapping)
| Campo | Contenido |
|---|---|
| Objetivo | 8 ciclos de `kill`/`start` de gSPAa (1 s caído, 2 s arriba) con gSPAb enviando a 5 msg/s. |
| Verifica | Requisito 9. |
| Precondiciones | Laboratorio en reposo. |
| Pasos | `python tests/run_tests.py D4` |
| Esperado (hipótesis) | 0 faltantes tras la convergencia, sin ids repetidos, y gSPAa conectado al central al final. |
| Observado | **PASS** (simulado). 8 ciclos, 179 enviados, 0 faltantes, convergencia en 0,05 s. |
| Aprobado / fallo | Aprobado: lo anterior. Fallo: faltantes, repetidos o gSPAa desconectado. |
| Libro | Cap. 6 (p. 57). |

### D5 — Partición de red
| Campo | Contenido |
|---|---|
| Objetivo | Aislar gSPAa del central (sin cortarle Redis) y comprobar la convergencia al sanar. |
| Verifica | Requisitos 8 y 9. |
| Precondiciones | `docker-compose.local.yml` nuevo (red `front` separada de `back-a`). Se desconecta el contenedor con `docker network disconnect` y se reconecta con `--alias server-a`. |
| Pasos | `python tests/run_tests.py D5` — 5 mensajes de cada grupo durante la partición; mide detección; sana; espera convergencia. |
| Esperado (hipótesis) | gSPAa detecta la partición; mantiene 5 pendientes; tras sanar ambos servidores tienen los 10 mensajes en el mismo orden y sin repetidos. |
| Observado | **PASS** (simulado). Detección en 6,64 s; convergencia 1,29 s después de sanar. |
| Aprobado / fallo | Aprobado: lo anterior. Fallo: no converge en 120 s o diverge. Si el alias no se restaura, el central no alcanza a gSPAa y la prueba lo mostrará (anótalo). |
| Libro | 24.5 Fallos de red (p. 236); cap. 6 (p. 57): enlaces *fair-loss*. |

### D6 — Central lento: backoff acotado y sin tormenta de reintentos
| Campo | Contenido |
|---|---|
| Objetivo | Con el `POST /messages` más lento que el timeout, los reintentos crecen y se detienen en el tope. |
| Verifica | Requisito 6. |
| Precondiciones | Central simulado arriba. El heartbeat sigue sano (solo se retrasa `/messages`). |
| Pasos | `python tests/run_tests.py D6` — un mensaje con el central a 5 s por POST durante 45 s; lee las esperas de los `SEND_RETRY` del log; luego quita la lentitud. |
| Esperado (hipótesis) | ≥ 3 reintentos; ninguna espera > 8 s (tope); el heartbeat no marca caído; el mensaje llega 1 vez. Las esperas tienden a crecer (hay *jitter*, no es monótono). |
| Observado | **INFO** (simulado). Dos corridas: 9 reintentos (0,2 / 0,4 / 1,3 / 2,8 / 4,5 / 0,2 / 4,5 / 0,9 / 0,6 s) y 8 reintentos (0,2 / 0,2 / 0,3 / 4,0 / 7,1 / 0,7 / 5,8 / 2,9 s); máximo 7,1 s ≤ tope 8 s; el heartbeat no marcó caído; 1 copia en gSPAb. No hay tendencia creciente clara (jitter total, n pequeño). `intentos_llegados_al_central=0` en ambas: **no es válido**, es un artefacto reproducible del simulado. |
| Aprobado / fallo | Aprobado: lo anterior. Fallo: espera > tope, mensaje descartado, o duplicado en gSPAb. |
| Libro | 27.1 Timeout (p. 253); 27.2.1 Backoff (p. 256). |

### D7 — Central lento frente a central caído
| Campo | Contenido |
|---|---|
| Objetivo | Comprobar que el log distingue tres situaciones por el motivo del fallo. |
| Verifica | Requisito 8, 11. |
| Precondiciones | Laboratorio en reposo. **Reinicia el central simulado** (pierde registro e historial; los servidores se vuelven a registrar). |
| Pasos | `python tests/run_tests.py D7` — central lento (3 s), central que responde 503, central apagado (`docker compose stop`). |
| Esperado (hipótesis) | Motivos `timeout`, `http_503` y `conn_error` respectivamente. |
| Observado | **PASS** (simulado). `lento=timeout`, `responde_503=http_503`, `apagado=conn_error`. |
| Aprobado / fallo | Aprobado: cada modo muestra su motivo. Fallo: motivos iguales o ausentes. |
| Libro | Cap. 7 (p. 61–62). |

### D8 — Falsos positivos del detector
| Campo | Contenido |
|---|---|
| Objetivo | **Medir** desde qué latencia un central vivo pero lento se marca como caído. |
| Verifica | Requisito 8. |
| Precondiciones | Laboratorio en reposo. |
| Pasos | `python tests/run_tests.py D8` — latencias de 0,5 / 1 / 1,5 / 2,5 s en todas las rutas del central, 20 s cada una. Detalle en `tests/results/D8.csv`. |
| Esperado (hipótesis) | Sin falsos positivos con latencia ≤ 50 % del timeout de `/health` (1 s); con 2,5 s (> timeout de 2 s) se marca caído aunque el central esté vivo. El umbral exacto es lo que se mide. |
| Observado | **INFO** (simulado). Sin `CENTRAL_DOWN` con 500, 1000 y 1500 ms; con 2500 ms se marcó caído (1 evento) aunque el central estaba vivo. El umbral está entre 1,5 y 2,5 s, coherente con el timeout de 2 s; no se midió el punto exacto. |
| Aprobado / fallo | Aprobado: sin `CENTRAL_DOWN` con ≤ 1 s. Lo demás es **INFO**: documenta la limitación de un detector imperfecto. |
| Libro | Cap. 7 (p. 61–62): no existe un detector de fallos perfecto. |

---

---

## E. Carga y límites

### E1 — Rampa de tasa (1, 10, 100, 1000 msg/s) *(pesada)*
| Campo | Contenido |
|---|---|
| Objetivo | **Medir** latencia p50/p95/p99, errores y el punto de saturación de `POST /api/messages`. |
| Verifica | Límite de rendimiento; el envío al central es secuencial (1 hilo emisor). |
| Precondiciones | Laboratorio limpio (el ejecutor limpia al terminar). |
| Pasos | `python tests/run_tests.py E1` — 10 s por nivel, envío a hora programada (lazo abierto), 64 hilos. Detalle: `tests/results/E1.csv`. |
| Esperado (hipótesis) | El servidor local acepta más rápido de lo que el emisor entrega al central: el `outbox` crece a tasas altas y se vacía después. Hipótesis: el cuello es el hilo emisor (≈ 1/latencia por POST). |
| Observado | **INFO.** 1, 10 y 100 msg/s: 0 errores, tasa lograda 1,1 / 10,1 / 100,0 msg/s, p95 ≤ 7 ms (p99 ≤ 8,1 ms), `outbox` casi vacío al terminar (1, 1, 10). 1000 msg/s: 0 errores pero solo se logra **653,5 msg/s** (el generador no llega a la tasa pedida), p50 87,8 ms, p95 179,3 ms, p99 239,1 ms, y el `outbox` queda en **9 088** de 10 000. Vaciado total: 38,12 s ⇒ ≈ 238 msg/s hacia el central (9 088/38,12; cálculo propio). La degradación aparece a 1000 msg/s. *Hipótesis no aislada:* el cuello es el emisor secuencial; no se probó con otro número de hilos. (Contra el central **simulado**.) |
| Aprobado / fallo | INFO: se documenta la tasa en la que aparece degradación. FAIL solo si hay errores a 1 msg/s. |
| Libro | 27.1 (p. 253) timeouts; cap. 27 (límites y backpressure, solo como contexto). |

### E2 — Ráfaga de 10 000 mensajes *(pesada)*
| Campo | Contenido |
|---|---|
| Objetivo | Comprobar que una ráfaga no pierde mensajes aceptados y que gSPAb converge. |
| Verifica | Requisitos 5 y 6. |
| Precondiciones | Laboratorio limpio. |
| Pasos | `python tests/run_tests.py E2` — 10 000 mensajes con 32 hilos. |
| Esperado (hipótesis) | Todos los aceptados (201) llegan a gSPAb sin repetidos; la convergencia tarda lo que tarde el emisor en vaciar el outbox. |
| Observado | **INFO.** 10 000 enviados, 0 errores, 16,0 s (623 msg/s), p95 86,5 ms. gSPAb converge **38,48 s después** de terminar el envío. Coincide con E1: lo que limita es la entrega al central (≈ 240 msg/s), no la aceptación local. Contra el central simulado. |
| Aprobado / fallo | Aprobado: gSPAb recibe todos los aceptados. Errores y tiempos: INFO. |
| Libro | 27.2 Retry (p. 255). |

### E3 — Cola de pendientes grande tras caída larga del central *(pesada)*
| Campo | Contenido |
|---|---|
| Objetivo | **Medir** cómo crece el `outbox` (¿memoria o disco?) y cuánto tarda en vaciarse. |
| Verifica | Requisito 8. |
| Precondiciones | Laboratorio limpio. |
| Pasos | `python tests/run_tests.py E3` — central caído, 5 000 mensajes locales, `up`, espera del vaciado. |
| Esperado (hipótesis) | El `outbox` vive en Redis (disco/AOF), no en memoria del servidor: la memoria del servidor casi no crece; la de Redis sí. Se vacía sin pérdidas ni duplicados. |
| Observado | **INFO.** 5 000 pendientes con el central caído: Redis pasó de 1 233 016 B a 4 469 008 B (+3,24 MB ≈ 647 B por mensaje pendiente; cálculo propio) y el servidor de 39,71 a 41,62 MiB. Al volver el central se vació en 21,04 s (≈ 238 msg/s). La cola crece en Redis, no en la memoria del proceso. |
| Aprobado / fallo | Aprobado: 5 000 pendientes, vaciado completo y 5 000 en gSPAb. Memorias: INFO. |
| Libro | 27.2 (p. 255); cap. 7. |

### E4 — Muchos usuarios locales y clientes simultáneos
| Campo | Contenido |
|---|---|
| Objetivo | **Medir** creación de 1 000 usuarios y 100 clientes enviando y leyendo a la vez. |
| Verifica | Requisito 3. |
| Precondiciones | Laboratorio en reposo. |
| Pasos | `python tests/run_tests.py E4`. |
| Esperado (hipótesis) | Sin errores; latencia p95 baja (decenas de ms). |
| Observado | **INFO.** 1 000 usuarios creados en 1,7 s; 100 clientes simultáneos enviando 500 mensajes en 1,3 s, p95 = 156,6 ms. Sin errores. |
| Aprobado / fallo | Aprobado: 0 errores. Latencias: INFO. |
| Libro | — |

### E5 — Historial grande: `/history?since=0` y recuperación al reiniciar *(pesada)*
| Campo | Contenido |
|---|---|
| Objetivo | **Medir** el costo de recuperar con `since=0` cuando el central tiene 10 000 y 50 000 mensajes. |
| Verifica | Requisito 9; decisión H3 (pedir todo e ignorar duplicados). |
| Precondiciones | Laboratorio limpio. Usa `/_admin/forward` para cargar el central sin reenviar. Para 100 000: `--e5-sizes 10000 100000`. |
| Pasos | `python tests/run_tests.py E5`. Detalle: `tests/results/E5.csv`. |
| Esperado (hipótesis) | El tiempo de recuperación crece con el tamaño del historial (descarga y validación de todo cada vez). Es el costo de `since=0`. |
| Observado | **INFO.** 10 000 mensajes: `/history?since=0` 0,18 s, 1,77 MB; recuperación tras reiniciar 5,1 s (10 000 nuevos). 50 000 mensajes: 0,92 s, 8,89 MB; recuperación 17,2 s (40 000 nuevos y 10 000 duplicados descartados, 0 inválidos). Memoria del servidor 42,34 → 42,71 MiB. El costo crece con el historial (5× mensajes ⇒ 3,4× tiempo de recuperación, que incluye el arranque del contenedor); con `since=0` cada reinicio baja todo. |
| Aprobado / fallo | INFO: se documentan segundos y MB por tamaño. FAIL si la recuperación no termina en 15 min. |
| Libro | 23.2 (p. 223). |

### E6 — Backoff: tope de espera y conservación del mensaje
| Campo | Contenido |
|---|---|
| Objetivo | Confirmar el tope de 8 s y que, tras muchos reintentos, el mensaje **se conserva** (decisión H8). |
| Verifica | Requisito 6. |
| Precondiciones | Central simulado arriba. |
| Pasos | `python tests/run_tests.py E6` — fuerza 503 durante 75 s y lee los `SEND_RETRY`. |
| Esperado (hipótesis) | ≥ 8 reintentos, esperas ≤ 8 s, el mensaje sigue en el outbox y se entrega 1 vez al quitar el 503. No existe un número máximo de reintentos. |
| Observado | **PASS** (2.ª corrida): 26 reintentos en 75 s, espera máxima 6,87 s (≤ tope 8 s), mensaje entregado una sola vez. La 1.ª corrida falló solo en la aserción `outbox == antes + 1` (21 reintentos, 7,68 s). Se parchó la prueba (espera `outbox = 0` antes de medir) y al repetirla pasó, lo que es coherente con que el fallo fuera de la prueba y no del servidor; la causa exacta del primer fallo no se verificó. |
| Aprobado / fallo | Aprobado: lo anterior. Fallo: espera > tope o mensaje descartado. |
| Libro | 27.2.1 (p. 256). |

### E7 — Agotamiento de recursos (manual)
| Campo | Contenido |
|---|---|
| Objetivo | **Observar** qué pasa con memoria limitada, descriptores de archivo y disco lleno. |
| Precondiciones | Laboratorio limpio. Anota la versión de Docker y el sistema anfitrión. |
| Pasos | **Memoria:** `docker update --memory 64m --memory-swap 64m <contenedor server-a>` y repetir E2 (ráfaga). **Descriptores:** `docker run --ulimit nofile=64 …` (o `ulimit -n 64` dentro del contenedor) y repetir E4. **Disco lleno:** *solo en una máquina virtual o un volumen aparte*: llenar el volumen de `redis-a` y enviar un mensaje; **no** hacerlo en tu equipo de trabajo. |
| Esperado (hipótesis) | Con poca memoria, el servidor o Redis se reinician (OOM) y se recuperan; con pocos descriptores aparecen errores de conexión; con el disco lleno, Redis rechaza escrituras y el servidor responde 5xx. Nada de esto está verificado. |
| Observado | **Memoria (INFO, simulado):** con 32 MiB `server-a` **no arranca** (`OOMKilled=true`, exit 137, `reinicios=0`: no se reinicia solo porque el compose no define `restart`). Con 48 MiB también terminó con exit 137 a los pocos segundos (no se verificó `OOMKilled`). Con 64 MiB arranca y la ráfaga de 10 000 (E2) pasó: 0 errores, 16,7 s, convergencia 39,09 s. En reposo el servidor usa ≈ 43 MiB: el mínimo está entre 48 y 64 MiB. **Descriptores: sin resultado válido.** E4 dio INFO sin errores (p95 162,8 ms) en una corrida cuyo límite no se verificó (con `nofile=64` se esperaban errores, así que probablemente no estaba aplicado), y otra, tras recrear `server-a` con el override, terminó en ERROR (`localhost:8000 no responde /api/status`) sin que se haya visto el log. No se puede afirmar qué ocurre con 64 descriptores. **Disco lleno:** no ejecutada. |
| Aprobado / fallo | INFO: documentar qué falla y cómo se manifiesta (logs). |
| Libro | Cap. 27 (solo como contexto). |


---

## F. Persistencia y despliegue

### F1 — `down`/`up` con y sin borrar volúmenes *(destructiva)*
| Campo | Contenido |
|---|---|
| Objetivo | Saber qué sobrevive a cada comando. |
| Verifica | Requisito 2. |
| Precondiciones | Laboratorio en reposo; el ejecutor limpia al terminar. |
| Pasos | `python tests/run_tests.py F1`. |
| Esperado (hipótesis) | Sin `-v`: sobreviven usuarios, historial y reloj. Con `-v`: todo lo local desaparece (el historial se recupera del central). |
| Observado | **PASS.** Sin `-v`: sobreviven historial, usuarios y reloj. Con `-v`: se pierde todo lo local (el historial se recupera del central si `HISTORY_SYNC` está activo). |
| Aprobado / fallo | Aprobado: lo anterior. |
| Libro | 8.2 (p. 65): persistir el reloj. |

### F2 — `restart` y reinicio del equipo
| Campo | Contenido |
|---|---|
| Objetivo | Usuarios, historial y reloj sobreviven. |
| Verifica | Requisito 2. |
| Precondiciones | Laboratorio en reposo. |
| Pasos | `python tests/run_tests.py F2`. Reinicio del equipo (**manual**): reiniciar, `docker compose up -d`, repetir comprobaciones de F2. |
| Esperado (hipótesis) | Todo sobrevive (volumen + AOF). |
| Observado | **PASS** el `docker compose restart` (usuarios, historial y reloj sobreviven). **Reinicio del equipo (manual): sin pérdida observada.** Antes: `lamport=1`, `messages=1`. Después: `lamport=746`, `messages=746` y `POST /api/users` del usuario previo → 409 (seguía existiendo). *Salvedad:* entre ambas lecturas se ejecutó E4 (500 mensajes), así que las cifras no son iguales; solo muestran que ni el reloj ni los mensajes retrocedieron. No se mostró la búsqueda del mensaje marcado. |
| Aprobado / fallo | Aprobado: lo anterior. |
| Libro | Cap. 6 (p. 57). |

### F3 — Equipo limpio, un solo comando
| Campo | Contenido |
|---|---|
| Objetivo | Que clonar y levantar funcione sin pasos manuales. |
| Verifica | Requisito 1. |
| Precondiciones | Repo confirmado en git. Idealmente otro equipo o una VM sin imágenes previas. |
| Pasos | `bash tests/clean_clone.sh` (**manual**; anota el resultado). |
| Esperado (hipótesis) | Levanta con `docker compose up --build -d` y responde `/fed/health`. |
| Observado | **PASS.** Clon limpio desde git, `docker compose -f docker-compose.local.yml up --build -d`: los 5 contenedores arriba (redis sanos) y `GET /fed/health` respondió `{"server":"gSPAa","lamport":0}`. Sin pasos manuales. |
| Aprobado / fallo | Aprobado: sin pasos extra. Anotar cualquier paso manual que haya hecho falta. |
| Libro | — |

### F4 — Variables de entorno faltantes o inválidas
| Campo | Contenido |
|---|---|
| Objetivo | Mensaje claro y sin URLs del central en el código. |
| Verifica | Requisitos 1 y 4. |
| Precondiciones | Laboratorio levantado. |
| Pasos | `python tests/run_tests.py F4` — vacía cada variable obligatoria y pone valores inválidos; busca `http(s)://` en `server/app/*.py`. |
| Esperado (hipótesis) | Cada caso termina con `[config] …` nombrando la variable; sin URLs en el código. |
| Observado | **PASS.** Para `GROUP_NAME`, `PUBLIC_URL`, `CENTRAL_URL`, `REDIS_URL`, `REGISTER_INTERVAL` y `HEALTH_FAILURES` inválidas o ausentes el servidor termina con un mensaje claro. |
| Aprobado / fallo | Aprobado: lo anterior. |
| Libro | — |

### F5 — Cambio de URL pública y re-registro
| Campo | Contenido |
|---|---|
| Objetivo | Que un cambio de `PUBLIC_URL` se refleje en el central y los mensajes sigan llegando. |
| Verifica | Requisito 4. |
| Precondiciones | Laboratorio en reposo; usa `PUBLIC_URL_A` del compose local (se restaura al final). |
| Pasos | `python tests/run_tests.py F5`. |
| Esperado (hipótesis) | Re-registro en el arranque; gSPAa sigue recibiendo mensajes. |
| Observado | **PASS.** Al cambiar `PUBLIC_URL` (de `http://server-a:8000` a `http://proyecto-final-sistemas-server-a-1:8000`) el servidor se registró con la nueva URL en el arranque (0,0 s). |
| Aprobado / fallo | Aprobado: el central muestra la URL nueva y llegan mensajes. |
| Libro | 4 (p. 31): nombre → dirección con renovación (analogía). |

### F6 — Renovación periódica y pérdida del registro
| Campo | Contenido |
|---|---|
| Objetivo | Si el central pierde el registro (o reinicia), los grupos se registran de nuevo solos. |
| Verifica | Requisito 4. |
| Precondiciones | Laboratorio en reposo. Tarda ~1–2 min (renovación cada 30 s). |
| Pasos | `python tests/run_tests.py F6` — `/_admin/forget-registry` y reinicio del central. |
| Esperado (hipótesis) | Re-registro ≤ ~30 s tras olvidar; tras reiniciar el central, vuelven a registrarse y fluyen mensajes. |
| Observado | **PASS.** Si el central olvida el registro, el servidor se re-registra a los **30,21 s**; tras reiniciar el central, a los **29,18 s**. Es decir, depende del intervalo de renovación (`REGISTER_INTERVAL` = 30 s): hay hasta ~30 s sin registro. Contra el central simulado. |
| Aprobado / fallo | Aprobado: ambos casos. |
| Libro | 4 (p. 31) (analogía). |


---

## G. Seguridad básica y robustez

### G1 — Entradas maliciosas en `body` y `from`
| Campo | Contenido |
|---|---|
| Objetivo | Comprobar que los textos peligrosos se guardan como texto y no tienen efecto. |
| Verifica | Robustez. |
| Precondiciones | Laboratorio en reposo. |
| Pasos | `python tests/run_tests.py G1` — 10 cargas (SQL, XSS, secuencias ANSI, plantillas, rutas) por la API local y por `/fed`. |
| Esperado (hipótesis) | Ida y vuelta exacta, servidor vivo. Redis no interpreta SQL; el cliente es CLI, así que XSS no aplica; el riesgo real son secuencias ANSI en el terminal (el cliente debe filtrarlas: **revisar `client/cli.py`**). |
| Observado | **PASS.** 10 cargas (HTML, SQL, ANSI, etc.) se guardan como texto sin efectos. El riesgo real es el terminal del CLI, mitigado con `clean()` en el cliente. |
| Aprobado / fallo | Aprobado: ida y vuelta exacta y servidor vivo. |
| Libro | — |

### G2 — JSON enorme o anidado
| Campo | Contenido |
|---|---|
| Objetivo | Que un cuerpo hostil no tumbe el servidor. |
| Verifica | Robustez. |
| Precondiciones | Laboratorio en reposo. Si el servidor cae, reiniciarlo. |
| Pasos | `python tests/run_tests.py G2` — anidamiento 100 a 100 000 y un objeto con 200 000 claves. |
| Esperado (hipótesis) | Respuesta 4xx o 200, nunca caída. Posible 5xx por recursión (se anota). |
| Observado | **INFO.** Anidamiento 100 y 1 000 ⇒ 422; 10 000 y 100 000 ⇒ 400; objeto de 200 000 claves ⇒ 200. Servidor vivo en todos, 0 respuestas 5xx (`tests/results/G2.csv`). |
| Aprobado / fallo | Aprobado: el servidor sigue vivo. 5xx: INFO/hallazgo. |
| Libro | — |

### G3 — `/fed/*` por un tercero y suplantación (limitación documentada)
| Campo | Contenido |
|---|---|
| Objetivo | Documentar el riesgo: no hay autenticación. |
| Verifica | Limitación del protocolo (el enunciado no la define). |
| Precondiciones | Laboratorio en reposo. |
| Pasos | `python tests/run_tests.py G3` — mensaje con `origin` de otro grupo o del propio, sin ser el central. |
| Esperado (hipótesis) | Se aceptan. **No** se inventa ninguna regla: se documenta como limitación. |
| Observado | **INFO.** Se aceptan (200): suplantar a otro grupo, fingir ser el propio y `GET /fed/health` sin autenticación. Limitación: el protocolo no define autenticación y no se inventó ninguna. |
| Aprobado / fallo | INFO: cualquiera que alcance `/fed/*` puede inyectar mensajes con cualquier `origin`. |
| Libro | — |

### G4 — Límites de tamaño de petición
| Campo | Contenido |
|---|---|
| Objetivo | Documentar que no hay tope. |
| Verifica | Limitación. |
| Precondiciones | — |
| Pasos | Ver A4 (sin tope hasta 50 MB) y G2. |
| Esperado (hipótesis) | — |
| Observado | No hay prueba propia; ver A4 (50 MB aceptados en 0,94 s) y G2 (objeto de 200 000 claves aceptado). No hay tope de tamaño. |
| Aprobado / fallo | Documental. |
| Libro | — |

---

## H. Interoperabilidad (sustituida por una sesión local)

Cambio de planes: no hay sesión de clase. Se simula con 4 grupos que ejecutan **nuestro** servidor y el central simulado:

```bash
docker compose -f docker-compose.sesion.yml up --build -d
python tests/sesion_local.py        # escribe docs/BITACORA.md
```
**Resultado (central simulado, 4 grupos con nuestro servidor):** prueba 1 PASS (convergencia en 0,6 s, mismo orden en los 4) y prueba 2 PASS en los 4 turnos (recuperación 0,6–1,1 s, sin duplicados almacenados). Una primera corrida falló la prueba 1 y destapó un defecto real (ver tabla de límites), ya corregido y repetido. Detalle en `docs/BITACORA.md`.

Ejecuta las dos pruebas de la sección 7 del enunciado: **(1)** conversación global (4 grupos × 10 mensajes, mismo orden en todos) y **(2)** caída y recuperación por turnos de cada grupo, sin duplicados. Esto prueba que *nuestro código* converge; **no** prueba interoperabilidad con servidores de terceros. La bitácora se completa a mano (qué funcionó, qué falló, hallazgos).


## Tabla de límites (se completa con los resultados)

| Qué se probó | Dónde se rompe | Por qué | Qué se haría |
|---|---|---|---|
| Tamaño de `body` (A4) | **No se encontró** hasta 50 MB (50 MB en 0,94 s) | El servidor no impone tope de tamaño de petición | Limitar el tamaño de petición (categoría G) |
| Lamport extremo (C2) | Se rechaza desde 2^53−1 (tope nuestro); exacto hasta 2^53−2 | Redis calcula con `double` | Aritmética entera, o tope documentado |
| Tabla de ids vistos (B5) | ≈ 400 B por mensaje (50 000 mensajes: 21,3 MB de Redis, con cuerpos de 36 caracteres). Extrapolación a 1 M ≈ 400 MB (**no medida**) | No se purga nunca | Expirar ids antiguos o recuperar por `/history` |
| Pérdida en SIGKILL (D3) | **No observada**: 0 de unos 3 700 confirmados en 4 corridas | Un `SIGKILL` del proceso no suele perder lo ya confirmado; el riesgo está en caídas del sistema (hipótesis). Además, lo enviado al central se recupera por `/history` | `appendfsync always` si se exige durabilidad ante caída del sistema |
| Detector de fallos (D8) | Falso positivo con 2,5 s de latencia (sin él con ≤ 1,5 s) | Un detector perfecto es imposible; el timeout de `/health` es 2 s | Afinar timeout e intentos; reintentar con sondas en vez de pausar el emisor |
| Reinicio rápido del central (sesión local, prueba 1) | Un servidor perdió 30 de 40 mensajes: el central se reinició y borró su registro; el servidor solo vio 1 fallo de salud (< K=3) y no recuperó historial hasta reiniciar | La recuperación solo se disparaba al declarar el central caído o al arrancar | Corregido: tras cualquier fallo de salud seguido de éxito se re-registra y sincroniza. **Sigue abierto**: si el central se reinicia entre dos sondas (2 s) sin ningún fallo visible, se detecta hasta la renovación (≤ 30 s) y no se recupera historial |
| Memoria mínima (E7) | `server-a` no arranca con 32 MiB y con 48 MiB sale con 137; arranca con 64 MiB | Uso en reposo ≈ 43 MiB | Fijar un límite ≥ 128 MiB y añadir `restart: unless-stopped` (hoy un OOM deja el servidor caído) |
| Autenticación de `/fed/*` (G3) | Cualquiera puede inyectar mensajes con cualquier `origin` (**verificado en G3**: 200) | El protocolo no la define | Documentar como limitación; no inventar autenticación |
| Rendimiento (E1/E2/E3) | A 1000 msg/s pedidos se logran 653,5; con 10 000 mensajes la entrega al central va a ≈ 238 msg/s y tarda ≈ 38 s en converger (contra el central **simulado**) | Sospecha (no aislada): un solo hilo emisor, un POST a la vez | Emisor concurrente; medir variando hilos |
| Historial grande (E5) | 50 000 mensajes: 0,92 s de descarga (8,89 MB) y 17,2 s de recuperación tras reiniciar | `since=0` descarga todo en cada recuperación | Usar `since` con el último lamport (pendiente de la especificación) |

## Huecos que propongo cubrir en las categorías siguientes

- Orden de mensajes que llegan por `/history` con lamport menor al reloj local (¿se muestran donde corresponde?).
- Reinicio del **central real** con pérdida de registro (con el simulado: `/_admin/forget-registry`).
- Un grupo con nombre que contenga `@` o caracteres raros.
