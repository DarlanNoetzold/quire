#!/usr/bin/env bash
# Quire 1.24 — instalador e inicializador em um comando.
#
# Uso local (dentro do repositório):   ./install.sh
# Uso remoto (baixa a release):        QUIRE_VERSION=v1.24 ./install.sh
#
# Variáveis:
#   QUIRE_DIR      diretório de instalação        (padrão: ~/quire)
#   QUIRE_VERSION  tag a baixar                   (padrão: v1.24)
#   QUIRE_PORT     porta HTTP                     (padrão: 8000)
#   QUIRE_HOST     endereço de escuta             (padrão: 0.0.0.0)
#   QUIRE_NO_START 1 = instala sem iniciar        (padrão: 0)
#   QUIRE_FORCE    1 = sobrescreve instalação     (padrão: 0)
#   GITHUB_TOKEN   token para repositório privado (opcional)
set -euo pipefail

REPO="DarlanNoetzold/quire"
VERSION="${QUIRE_VERSION:-v1.24}"
TARGET="${QUIRE_DIR:-$HOME/quire}"
PORT="${QUIRE_PORT:-8000}"
HOST="${QUIRE_HOST:-0.0.0.0}"
NO_START="${QUIRE_NO_START:-0}"
FORCE="${QUIRE_FORCE:-0}"

log() { printf '\033[1;36m[quire]\033[0m %s\n' "$*"; }
die() { printf '\033[1;31m[quire]\033[0m %s\n' "$*" >&2; exit 1; }

command -v python3 >/dev/null 2>&1 || die "python3 não encontrado. Instale Python 3.10 ou superior."
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' \
  || die "Python 3.10 ou superior é necessário (encontrado: $(python3 -V 2>&1))."

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$SCRIPT_DIR/app/api.py" ]; then
  TARGET="$SCRIPT_DIR"
  log "Instalando a partir do diretório local: $TARGET"
elif [ -f "$TARGET/app/api.py" ] && [ "$FORCE" != "1" ]; then
  log "Instalação existente encontrada em $TARGET (use QUIRE_FORCE=1 para sobrescrever)."
else
  command -v curl >/dev/null 2>&1 || die "curl não encontrado."
  [ -e "$TARGET" ] && [ "$FORCE" != "1" ] && [ -n "$(ls -A "$TARGET" 2>/dev/null)" ] \
    && die "$TARGET não está vazio. Use QUIRE_FORCE=1 para sobrescrever ou QUIRE_DIR para outro caminho."
  log "Baixando Quire $VERSION de github.com/$REPO ..."
  tmp="$(mktemp -d)"
  trap 'rm -rf "$tmp"' EXIT
  auth=()
  [ -n "${GITHUB_TOKEN:-}" ] && auth=(-H "Authorization: token $GITHUB_TOKEN")
  curl -fsSL ${auth[@]+"${auth[@]}"} \
    "https://codeload.github.com/$REPO/tar.gz/refs/tags/$VERSION" -o "$tmp/quire.tar.gz" \
    || die "Falha ao baixar $VERSION. Repositório privado? Defina GITHUB_TOKEN."
  mkdir -p "$tmp/src" "$TARGET"
  tar -xzf "$tmp/quire.tar.gz" -C "$tmp/src" --strip-components=1
  cp -a "$tmp/src/." "$TARGET/"
  log "Código extraído em $TARGET"
fi

cd "$TARGET"
mkdir -p data/pdfs

if [ ! -x .venv/bin/python ]; then
  log "Criando ambiente virtual (.venv) ..."
  python3 -m venv .venv || die "Falha ao criar o venv. No Debian/Ubuntu: sudo apt install python3-venv"
fi

log "Instalando dependências ..."
.venv/bin/pip install --quiet --disable-pip-version-check --upgrade pip >/dev/null 2>&1 || true
.venv/bin/pip install --quiet --disable-pip-version-check -r requirements.txt \
  || die "Falha ao instalar dependências."

cat > "$TARGET/quire" <<'LAUNCHER'
#!/usr/bin/env bash
# Quire — controle do servidor local (gerado pelo install.sh).
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORT="${QUIRE_PORT:-8000}"
HOST="${QUIRE_HOST:-0.0.0.0}"
PID_FILE="$DIR/data/quire.pid"
LOG_FILE="$DIR/data/quire.log"

running() { [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; }

case "${1:-start}" in
  start)
    if running; then echo "Quire já está rodando (pid $(cat "$PID_FILE")) em http://localhost:$PORT"; exit 0; fi
    mkdir -p "$DIR/data"
    cd "$DIR"
    nohup .venv/bin/uvicorn app.api:app --host "$HOST" --port "$PORT" >> "$LOG_FILE" 2>&1 &
    echo $! > "$PID_FILE"
    for _ in $(seq 1 60); do
      if curl -fsS "http://127.0.0.1:$PORT/api/health" >/dev/null 2>&1; then
        echo "Quire iniciado em http://localhost:$PORT (pid $(cat "$PID_FILE"))"; exit 0
      fi
      sleep 1
    done
    echo "Quire não respondeu em 60s. Veja: $LOG_FILE" >&2; exit 1 ;;
  stop)
    if running; then kill "$(cat "$PID_FILE")" && rm -f "$PID_FILE" && echo "Quire parado."; else echo "Quire não está rodando."; fi ;;
  restart) "$0" stop; sleep 1; "$0" start ;;
  status)
    if running; then echo "Rodando (pid $(cat "$PID_FILE")) em http://localhost:$PORT"; else echo "Parado."; fi ;;
  logs) tail -n "${2:-80}" -f "$LOG_FILE" ;;
  open) command -v xdg-open >/dev/null 2>&1 && xdg-open "http://localhost:$PORT" || echo "http://localhost:$PORT" ;;
  *) echo "Uso: quire {start|stop|restart|status|logs|open}" >&2; exit 2 ;;
esac
LAUNCHER
chmod +x "$TARGET/quire"

if [ -d "$HOME/.local/bin" ] && [ -w "$HOME/.local/bin" ]; then
  ln -sf "$TARGET/quire" "$HOME/.local/bin/quire"
  log "Comando 'quire' disponível em ~/.local/bin (adicione ao PATH se necessário)."
fi

if [ "$NO_START" = "1" ]; then
  log "Instalação concluída. Inicie com: $TARGET/quire start"
  exit 0
fi

"$TARGET/quire" start
log "Interface: http://localhost:$PORT"
log "Parar: $TARGET/quire stop   |   Logs: $TARGET/quire logs"
