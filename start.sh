#!/usr/bin/env bash
# Convenience launcher for local development.
# Copies .env.example -> .env if missing, then runs the bot.
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -f .env ]; then
    echo "[i] .env not found — copying from .env.example"
    cp .env.example .env
    echo "[!] Open .env and fill in API_ID / API_HASH / BOT_TOKEN,"
    echo "    then re-run: ./start.sh"
    exit 1
fi

# Make sure deps are installed
if ! python -c "import telethon, requests, bs4, lxml, dotenv" 2>/dev/null; then
    echo "[i] Installing dependencies..."
    pip install --user -r requirements.txt
fi

echo "[i] Starting bot..."
python bot.py
