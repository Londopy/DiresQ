#!/usr/bin/env bash
# Boot script for the hosted demo.
#
# The free tier throws the filesystem away when the instance sleeps, so the
# database has to be rebuilt on every wake. That is not a workaround — it is
# what you want from a demo. Every visitor arrives at the same incident, two
# hours old, with somebody already forty-seven minutes overdue, rather than
# whatever the previous visitor left behind.
set -euo pipefail

echo "building database"
flask --app app init-db
flask --app app seed

# gunicorn, not the Flask dev server. The dev server is single-threaded, says
# so in a warning on every boot, and would serve one visitor at a time.
#
# Two workers on 512 MB: the classifier trains at import, so each worker
# carries its own copy — small, but not free. Threads handle the board and
# feed polling, which is almost all waiting on SQLite rather than computing.
exec gunicorn app:app \
    --bind "0.0.0.0:${PORT:-10000}" \
    --workers 2 \
    --threads 4 \
    --timeout 30 \
    --access-logfile - \
    --error-logfile -
