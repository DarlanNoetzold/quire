#!/bin/bash
cd "$(dirname "$0")"
if [ ! -d .venv ]; then
  echo "Creating virtual environment and installing dependencies..."
  python3 -m venv .venv
  .venv/bin/pip install --quiet --disable-pip-version-check -r requirements.txt
fi
mkdir -p data
echo "Quire — local research library."
echo "Ollama must be running (ollama serve or the desktop app)."
echo "Open: http://localhost:8000"
echo "Log: data/uvicorn.log"
exec .venv/bin/uvicorn app.api:app --reload --host 0.0.0.0 --port 8000 >> data/uvicorn.log 2>&1
