# 10 preguntas difíciles (respuestas cortas; cap. = *Understanding Distributed Systems*)

1. **¿Por qué reintentar no duplica?** El `id` lo genera el origen y no cambia; el receptor guarda los ids vistos (Redis `HSETNX`, persistido) y responde 200 sin efectos. Guardar el id y aplicar el efecto es una operación atómica. (5.7, 23.2)
2. **¿Qué pasa si se pierde la respuesta 200?** El emisor no distingue "no llegó" de "llegó y se perdió la respuesta": reintenta con el mismo id y el receptor lo descarta (B3). (2.1, 5.7)
3. **¿Por qué no se usa `sent_at` para ordenar?** Cada máquina tiene su reloj físico, que se desajusta; el orden lo da Lamport. C4 lo prueba con `sent_at` en 1970 y 2099. (8.1, 8.2)
4. **¿Qué pasa si el central se cae en medio de un reenvío?** El mensaje ya está guardado en el historial del central; el grupo que no lo recibió lo recupera con `GET /history` al volver. En el experimento, lo que el central abandona es exactamente lo que se pierde sin recuperación. (7, 27.2)
5. **¿Qué garantiza el reloj de Lamport y qué no?** Si A ocurrió antes que B, `L(A) < L(B)`; lo contrario no vale: dos eventos no relacionados pueden compartir marca, por eso se desempata por `origin`. (8.2)
6. **¿Cómo detectan que el central está caído?** `GET /health` cada 2 s; "caído" tras 3 fallos seguidos. No hay detector perfecto: uno lento se confunde con uno caído (D8: falso positivo con 2,5 s de latencia). (7)
7. **¿Por qué backoff exponencial con *jitter* y tope?** Evita reintentos sincronizados y tormentas; el tope (8 s) acota la espera. Nunca se descarta un mensaje: se conserva (E6). (27.2.1)
8. **¿Por qué 4xx no se reintenta y 5xx sí?** Un 4xx indica un error del cliente que no mejora reintentando; un 5xx puede ser transitorio. (5.4)
9. **¿Qué sobrevive a un reinicio y por qué?** Usuarios, historial, ids vistos, reloj y outbox, porque viven en Redis con AOF en un volumen. El reloj persistido evita retroceder tras reiniciar. (8.2, cap. 6 crash-recovery)
10. **¿Qué no pueden afirmar de su validación?** Que interoperan con otros equipos: solo se probó contra un central simulado escrito por el grupo y 4 copias del mismo servidor. Tampoco se explica por qué el control pierde ≈ 33 mensajes con 10 s de caída (H-a2 refutada).
