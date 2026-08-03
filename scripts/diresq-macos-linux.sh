#!/usr/bin/env bash
#
# DiresQ — run it on your own machine.
#
# macOS and Linux, any processor. There is nothing compiled in this project,
# so there is no Intel build and no Apple Silicon build: it is Python source,
# and Python source does not have an architecture. If it runs on your machine
# at all, this is the file that runs it.
#
# Two ways to use it, and it works out which by itself:
#
#   * Downloaded on its own from the Releases page — it fetches the source for
#     the version it was published with, into a folder beside itself.
#   * Sitting inside a clone of the repository — it uses the checkout it is
#     in, so you can run your own working copy.
#
# Everything it installs goes in a virtual environment inside the project
# folder. Delete the folder and nothing is left behind.
#
#     chmod +x diresq-macos-linux.sh
#     ./diresq-macos-linux.sh
#
set -euo pipefail

REPO="Skythe7/DiresQ"

# The workflow rewrites this when it attaches the script to a release, so a
# downloaded copy pins the version it shipped with rather than drifting to
# whatever main happens to be that day.
VERSION="__VERSION__"

PORT="${PORT:-5000}"

say()  { printf '\n\033[1;34m==>\033[0m %s\n' "$1"; }
die()  { printf '\n\033[1;31mx\033[0m %s\n\n' "$1" >&2; exit 1; }

# ---------------------------------------------------------------- python ---
# 3.10 is the floor because CI tests 3.10 and 3.12, and a version nobody has
# ever run this on is not a version we are going to claim support for.
find_python() {
    for candidate in python3.12 python3.11 python3.10 python3 python; do
        if command -v "$candidate" >/dev/null 2>&1; then
            if "$candidate" -c 'import sys; sys.exit(0 if sys.version_info[:2] >= (3,10) else 1)' 2>/dev/null; then
                echo "$candidate"
                return 0
            fi
        fi
    done
    return 1
}

PYTHON="$(find_python)" || die "DiresQ needs Python 3.10 or newer.
   macOS:  brew install python@3.12
   Ubuntu: sudo apt install python3 python3-venv
   Or:     https://www.python.org/downloads/"

say "Using $("$PYTHON" --version 2>&1)"

# ----------------------------------------------------------------- source ---
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ -f "$here/app.py" ]; then
    project="$here"
elif [ -f "$here/../app.py" ]; then
    project="$(cd "$here/.." && pwd)"
else
    # Standing on its own, so go and get the code.
    ref="$VERSION"
    case "$ref" in
        __VERSION__) ref="main" ;;      # running from a copy nobody stamped
        v*)          ;;                 # already a tag
        *)           ref="v$ref" ;;
    esac

    project="$here/diresq-${ref}"

    if [ -d "$project" ]; then
        say "Source already here: $project"
    else
        say "Downloading DiresQ $ref"
        tarball="https://github.com/$REPO/archive/refs/tags/$ref.tar.gz"
        [ "$ref" = "main" ] && tarball="https://github.com/$REPO/archive/refs/heads/main.tar.gz"

        tmp="$(mktemp -d 2>/dev/null)" \
            || die "Could not create a temporary directory. Is the disk full?"
        trap 'rm -rf "$tmp"' EXIT

        command -v curl >/dev/null 2>&1 || die "curl is needed to download the source."
        curl -fsSL "$tarball" -o "$tmp/diresq.tar.gz" \
            || die "Could not download $tarball
   Check the tag exists, or clone the repository instead:
   git clone https://github.com/$REPO"

        mkdir -p "$project"
        tar -xzf "$tmp/diresq.tar.gz" -C "$project" --strip-components=1
    fi
fi

cd "$project"
say "Project: $project"

# -------------------------------------------------------------- packages ---
venv="$project/.venv"

if [ ! -d "$venv" ]; then
    say "Creating a virtual environment"
    "$PYTHON" -m venv "$venv" \
        || die "Could not create a virtual environment.
   On Debian and Ubuntu this usually means: sudo apt install python3-venv"
fi

# Everything from here uses the venv's interpreter directly rather than
# `activate`, because activating changes a shell this script does not own.
VPY="$venv/bin/python"

say "Installing dependencies"
"$VPY" -m pip install --quiet --upgrade pip
"$VPY" -m pip install --quiet -r requirements.txt

# -------------------------------------------------------------- database ---
# Rebuilt every run, on purpose. This is a demo of an emergency tool: you want
# to open it and find the same incident two hours old with somebody already
# overdue, not whatever you left behind last time.
say "Building the database"
DB="$project/diresq.db"
[ -f "$DB" ] && rm -f "$DB"

"$VPY" -m flask --app app init-db
"$VPY" -m flask --app app seed

# ------------------------------------------------------------------- run ---
cat <<BANNER

  DiresQ is starting.

    http://127.0.0.1:$PORT

    Sign in as   londo / diresq

  Nothing in it is real. Please don't type a real address into something
  that looks like an emergency service and is not one.

  Ctrl-C to stop.

BANNER

# Give the server a moment before the browser goes looking for it.
( sleep 2
  if   command -v open    >/dev/null 2>&1; then open    "http://127.0.0.1:$PORT"
  elif command -v xdg-open >/dev/null 2>&1; then xdg-open "http://127.0.0.1:$PORT"
  fi ) >/dev/null 2>&1 &

# The Flask development server, deliberately. gunicorn does not run on every
# platform this script targets, and this is one person on their own laptop —
# the case the dev server is actually correct for. The hosted demo uses
# gunicorn; see start.sh.
exec "$VPY" -m flask --app app run --port "$PORT"
