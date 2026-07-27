#!/usr/bin/env bash
# Cria o venv (python3.12) na 1a vez, instala deps e abre o app.
set -euo pipefail
cd "$(dirname "$0")"

PY=python3.12
VENV=.venv

if [ ! -d "$VENV" ]; then
  echo "==> Criando venv com $PY ..."
  "$PY" -m venv "$VENV"
  "$VENV/bin/pip" install -U pip
  "$VENV/bin/pip" install -r requirements.txt
fi

# Garante que o pacote local em src/ é encontrado mesmo sem instalação.
export PYTHONPATH="$PWD/src${PYTHONPATH:+:$PYTHONPATH}"
exec "$VENV/bin/python" -m videotosprite "$@"
