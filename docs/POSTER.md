# Póster A1 vertical — estructura (8 secciones, enunciado sec. 8)

Regla: más figuras que texto, frases cortas, sin código largo; título legible a varios metros; entregar también en PDF.

| # | Sección | Contenido | Fuente en el repo |
|---|---|---|---|
| 1 | Título, integrantes, grupo | "Pérdidas ante la caída de un servidor en un chat distribuido" · gSPAa · 3 integrantes | — |
| 2 | Pregunta e hipótesis | ¿Cuántos mensajes se pierden o duplican si el servidor del grupo se cae unos segundos? H-a1, H-a2, H-a3 (escritas **antes** de medir) | `experiment/README.md` |
| 3 | Arquitectura | Diagrama de contenedores, redes, volúmenes y conexión con el central | `docs/ARQUITECTURA.md` |
| 4 | Método | `SIGKILL` de gSPAa de 2/5/10 s, gSPAb enviando a 10 msg/s, 3 repeticiones por caso, grupo de control sin recuperación | `experiment/README.md` |
| 5 | Resultados | Figura de pérdidas y de recuperación **con unidades** + tabla | `experiment/results/fig_resultados.png`, `experiment/RESULTADOS.md` |
| 6 | Interoperabilidad | Sesión **local** de 4 grupos (nuestro servidor + central simulado): qué convergió; **decir explícitamente que no es interoperabilidad con terceros** | `docs/BITACORA.md` |
| 7 | Limitaciones y conclusiones | Tabla de límites; hipótesis refutada (H-a2) y la no explicada (≈ 33 perdidos); central simulado | `docs/PRUEBAS.md` |
| 8 | Referencias | Vitillo, *Understanding Distributed Systems* (caps. 2, 5, 6, 7, 8, 23, 27); enunciado del proyecto | — |

**Mensajes clave (solo lo medido):** con recuperación, 0 pérdidas y 0 duplicados almacenados en 18/18 repeticiones; sin ella, 2,3 / 25 / 33 pérdidas (≈ 1,6 / 14 / 15 %) con caídas de 2 / 5 / 10 s; la recuperación tarda ≈ 1–1,6 s; cada recuperación con `since=0` descarta decenas de duplicados.
**No decir:** que interoperamos con otros equipos, ni explicar el ≈ 33 con una causa concreta, ni extrapolar a otras tasas o al central real.
