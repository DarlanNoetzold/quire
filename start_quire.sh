#!/bin/bash
cd /home/umbrel/projetos/quire
if [ ! -d .venv ]; then
  python3 -m venv .venv
  .venv/bin/pip install --quiet --disable-pip-version-check -r requirements.txt
fi
mkdir -p data
PORT="${QUIRE_PORT:-8085}"
exec .venv/bin/uvicorn app.api:app --host 0.0.0.0 --port "$PORT"
