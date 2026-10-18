@echo off
cd /d "%~dp0"
if not exist .venv (
  echo Criando ambiente virtual e instalando dependencias...
  python -m venv .venv
  .venv\Scripts\pip install --quiet --disable-pip-version-check -r requirements.txt
)
echo Ollama precisa estar rodando (app Ollama instalado no Windows).
echo Abra: http://localhost:8000
.venv\Scripts\python -m uvicorn app.api:app --host 0.0.0.0 --port 8000
