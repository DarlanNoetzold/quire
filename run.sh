#!/bin/bash
cd "$(dirname "$0")"
if [ ! -d .venv ]; then
  echo "Criando ambiente virtual e instalando dependências..."
  python3 -m venv .venv
  .venv/bin/pip install --quiet --disable-pip-version-check -r requirements.txt
fi
mkdir -p data
echo "Quire — biblioteca de pesquisa local."
echo "Ollama precisa estar rodando (ollama serve ou aplicativo instalado)."
echo "Abra: http://localhost:8000"
echo "Log: data/uvicorn.log"
exec .venv/bin/uvicorn app.api:app --reload --host 0.0.0.0 --port 8000 >> data/uvicorn.log 2>&1
