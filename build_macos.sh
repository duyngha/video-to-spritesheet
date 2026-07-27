#!/usr/bin/env bash
# Gera um app macOS nativo (.app) em build/macos usando `flet build`.
#
# Requisitos:
#   - Flutter SDK no PATH        (https://docs.flutter.dev/get-started/install)
#   - venv já criado (rode ./run.sh uma vez, ou crie com python3.12)
#
# ffmpeg/ffprobe NÃO são embutidos no .app. Em runtime o app procura os binários
# no PATH e nos diretórios usuais (/opt/homebrew/bin, /usr/local/bin, …); se não
# achar, mostra um aviso com o botão "Instalar ffmpeg", que baixa builds estáticos
# para ~/.videotosprite/bin (~40MB). `brew install ffmpeg` também resolve.
#
# A 1ª build baixa/compila bastante coisa e pode levar vários minutos.
set -euo pipefail
cd "$(dirname "$0")"

VENV=.venv
[ -d "$VENV" ] || { echo "venv não encontrado — rode ./run.sh primeiro."; exit 1; }

# Apple Silicon apenas: o rembg puxa pymatting -> numba/llvmlite, que não têm
# wheels x86_64 instaláveis a partir de um host arm64 (o pip tenta compilar e
# quebra). Para uma build universal seria preciso rodar num Mac Intel.
ARCH="${ARCH:-arm64}"

# O plugin screen_retriever_macos (target macOS 10.14) conflita com o produto
# FlutterFramework do Swift Package Manager (exige 10.15), quebrando a build do
# Xcode. Desligar o SPM no Flutter mantém tudo no CocoaPods e resolve.
flutter config --no-enable-swift-package-manager >/dev/null 2>&1 || true

echo "==> flet build macos (arch: $ARCH — pode demorar na 1ª vez)…"
echo "    Obs.: na 1ª vez o flet pode instalar a versão fixada do Flutter SDK"
echo "    (~1.5GB) — responda 'y' ao prompt."
"$VENV/bin/flet" build macos \
  --arch "$ARCH" \
  --project "VideoToSprite" \
  --product "VideoToSprite" \
  "$@"

echo "==> Pronto. App em: build/macos/"
open build/macos 2>/dev/null || true
