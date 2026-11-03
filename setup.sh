#!/usr/bin/env bash
# One-time setup for macOS / Linux.   Usage:  ./setup.sh
set -euo pipefail
cd "$(dirname "$0")"

say()  { printf "\033[36m▸ %s\033[0m\n" "$*"; }
fail() { printf "\033[31m✖ %s\033[0m\n" "$*"; exit 1; }
OS="$(uname -s)"

# ── system tools ─────────────────────────────────────────────
need_brew() { command -v brew >/dev/null || fail "Install Homebrew first: https://brew.sh"; }
if ! command -v ffmpeg >/dev/null; then
  say "Installing ffmpeg …"
  if [ "$OS" = "Darwin" ]; then need_brew; brew install ffmpeg
  elif command -v apt-get >/dev/null; then sudo apt-get update && sudo apt-get install -y ffmpeg
  else fail "Please install ffmpeg with your package manager."; fi
fi
if ! command -v node >/dev/null; then
  say "Installing Node.js …"
  if [ "$OS" = "Darwin" ]; then need_brew; brew install node
  elif command -v apt-get >/dev/null; then sudo apt-get install -y nodejs npm
  else fail "Please install Node.js 18+ (https://nodejs.org)."; fi
fi

# yt-dlp now needs a JavaScript runtime (Deno) to solve YouTube's challenges. Not fatal if it can't be installed.
if ! command -v deno >/dev/null; then
  say "Installing Deno (needed by yt-dlp for YouTube) …"
  if [ "$OS" = "Darwin" ] && command -v brew >/dev/null; then brew install deno || true
  else printf "\033[33m! Please install Deno (https://docs.deno.com/runtime/getting_started/installation/); YouTube downloads may fail without it.\033[0m\n"; fi
fi

PY=""
for c in python3.12 python3.11 python3.13 python3.10 python3; do
  if command -v "$c" >/dev/null && "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)'; then PY="$c"; break; fi
done
[ -n "$PY" ] || fail "Python 3.10+ is required (macOS: brew install python@3.12)."
say "Using $($PY --version)"

# ── python env ───────────────────────────────────────────────
[ -d .venv ] || "$PY" -m venv .venv
.venv/bin/python -m pip install --upgrade pip -q
say "Installing Python packages (yt-dlp, faster-whisper / mlx-whisper, OpenCV) …"
.venv/bin/pip install -r requirements.txt -q

if command -v nvidia-smi >/dev/null && [ "$OS" = "Linux" ]; then
  say "NVIDIA GPU detected → installing CUDA libraries for faster-whisper …"
  .venv/bin/pip install -q nvidia-cublas-cu12 "nvidia-cudnn-cu12==9.*"
fi

# ── remotion ─────────────────────────────────────────────────
say "Installing Remotion (npm) …"
(cd remotion && npm install --no-audit --no-fund --loglevel=error && npx remotion browser ensure)

# ── assets + check ───────────────────────────────────────────
say "Downloading fonts + face model …"
./reels assets
chmod +x reels
./reels doctor
say "Setup complete. Open this folder in Claude Code and run:  /make-reels <youtube-url>"
