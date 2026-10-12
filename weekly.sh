#!/usr/bin/env bash
#
# The weekly collection, for cron.
#
#   bash ./weekly.sh
#
# Crontab entry for Mondays at 07:00 (use absolute paths; cron has no PATH):
#   0 7 * * 1 cd /Users/victor/Documents/GitHub/eventRecommender && ./weekly.sh

set -u
cd "$(dirname "$0")"
mkdir -p data
exec .venv/bin/python src/weekly_run.py "$@" >> data/weekly.log 2>&1
