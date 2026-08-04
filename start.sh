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
# Worker count comes from the host, not from us. The classifier trains at
# import, so every worker carries its own copy — small, but not free, and on a
# 512 MB free instance two copies is enough to matter. Render announces the
# number it sized the box for (`WEB_CONCURRENCY=1`); hardcoding --workers 2
# silently overrode that, and a container killed four seconds after boot looks
# exactly like a health check that never passed. Take the host's number.
#
# Threads handle the board and feed polling, which is almost all waiting on
# SQLite rather than computing, so they cost far less than workers do.
exec gunicorn app:app \
    --bind "0.0.0.0:${PORT:-10000}" \
    --workers "${WEB_CONCURRENCY:-2}" \
    --threads 4 \
    --timeout 30 \
    --access-logfile - \
    --error-logfile -
