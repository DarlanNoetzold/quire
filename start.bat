@echo off
cd /d "%~dp0"
title Quire
if not exist .venv (
  echo Creating virtual environment and installing dependencies...
  python -m venv .venv
  .venv\Scripts\pip install --quiet --disable-pip-version-check -r requirements.txt
)
echo Quire — local research library.
echo Ollama must be running (Ollama app installed on Windows).
echo Opening http://localhost:8000 ...
start http://localhost:8000
.venv\Scripts\python -m uvicorn app.api:app --reload --host 0.0.0.0 --port 8000
