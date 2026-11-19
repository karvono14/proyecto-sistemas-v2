#!/usr/bin/env bash
# F3 (manual): ¿se levanta en un equipo limpio con un solo comando y sin pasos manuales?
# Uso (con todo confirmado en git):  bash tests/clean_clone.sh
set -euo pipefail
SRC="$(git rev-parse --show-toplevel)"; TMP="$(mktemp -d)"
echo "[F3] clonando en $TMP"; git clone --quiet "$SRC" "$TMP/repo"; cd "$TMP/repo"
echo "[F3] levantando el laboratorio local (un solo comando)"
docker compose -f docker-compose.local.yml up --build -d
sleep 10
echo "[F3] /fed/health:"; curl -fsS http://localhost:8000/fed/health; echo
docker compose -f docker-compose.local.yml ps
docker compose -f docker-compose.local.yml down -v
echo "[F3] anota el resultado en docs/PRUEBAS.md (F3)"
