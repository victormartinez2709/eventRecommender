#!/usr/bin/env bash
#
# Runs the whole collection in the background and logs everything.
#
#   ./collect.sh
#
# Safe to interrupt and re-run: the crawler keeps its state in the database,
# so a second run picks up exactly where the first one stopped.

set -u
cd "$(dirname "$0")"

LOG="data/collect.log"
mkdir -p data

if [ ! -d .venv ]; then
  echo "No .venv found. Run: python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
  exit 1
fi

# Use the venv's interpreter directly, so this works whether or not the venv
# is activated in the shell that launches it (and under nohup, where it isn't).
PY=".venv/bin/python"

{
  echo "==============================================================="
  echo "collection started $(date)"
  echo "==============================================================="

  echo ">>> creating database if needed"
  "$PY" src/db.py

  echo ">>> resolving seed artists from seeds.txt"
  "$PY" src/seed_names.py

  echo ">>> crawling artists and events (expands through event lineups)"
  "$PY" src/crawl.py

  echo ">>> normalizing into tables"
  "$PY" src/normalize.py

  echo "==============================================================="
  echo "collection finished $(date)"
  echo "==============================================================="
} >> "$LOG" 2>&1

echo "Done. Full log in $LOG"
