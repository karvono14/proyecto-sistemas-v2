import os
import sys


def require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        sys.exit(f"[config] Falta la variable de entorno obligatoria: {name}")
    return value


def optional_env(name: str, default, cast):
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return cast(raw)
    except ValueError:
        sys.exit(f"[config] Valor inválido en {name}={raw!r} (se esperaba {cast.__name__})")


# Obligatorias (requisitos 1 y 4: nada de URLs en el código)
GROUP_NAME = require_env("GROUP_NAME")
PUBLIC_URL = require_env("PUBLIC_URL")
CENTRAL_URL = require_env("CENTRAL_URL").rstrip("/")
REDIS_URL = require_env("REDIS_URL")

# Ajustables. Los valores por defecto son decisiones NUESTRAS, no del enunciado.
MAX_BODY_CHARS = optional_env("MAX_BODY_CHARS", 2000, int)        # solo mensajes locales
REQUEST_TIMEOUT = optional_env("REQUEST_TIMEOUT", 3.0, float)     # s, POST al central
HEALTH_TIMEOUT = optional_env("HEALTH_TIMEOUT", 2.0, float)       # s, GET /health
HEALTH_INTERVAL = optional_env("HEALTH_INTERVAL", 2.0, float)     # s entre heartbeats
HEALTH_FAILURES = optional_env("HEALTH_FAILURES", 3, int)         # fallos seguidos => "caído"
REGISTER_INTERVAL = optional_env("REGISTER_INTERVAL", 30.0, float)  # s entre renovaciones
HISTORY_TIMEOUT = optional_env("HISTORY_TIMEOUT", 30.0, float)    # s, GET /history
BACKOFF_INITIAL = optional_env("BACKOFF_INITIAL", 0.5, float)     # s
BACKOFF_CAP = optional_env("BACKOFF_CAP", 8.0, float)             # s

# SOLO para el experimento (grupo de control). Debe quedar en "true" en el entregable:
# con "false" se incumple el requisito 9 (recuperación de historial).
HISTORY_SYNC = optional_env("HISTORY_SYNC", "true", str).strip().lower() in ("1", "true", "yes", "on")
