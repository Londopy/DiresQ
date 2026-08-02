"""Puts the database into a known state for recording.

Recording the accountability board going red is awkward, because by the time
you press record the seed data is already red. This winds a responder's clock
so the row flips a chosen number of seconds from now, while the camera is
running.

    python tools/demo_state.py --in 12

Then load /board and wait. The row turns red on its own, the page is polling
every three seconds, and about fifteen minutes of app-time later the dead
man's switch files the report — except we lie about the deadline, so it lands
right after.

    python tools/demo_state.py --reset     # back to the seeded incident

Everything here writes to the same database the app reads. It is a recording
aid, not part of the app, and nothing imports it.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app as diresq  # noqa: E402

# Who the shot is about. Same person the seed makes overdue, so the story in
# the GIF matches the story in the README.
SUBJECT = "s.reyes"


def connect() -> sqlite3.Connection:
    db = sqlite3.connect(diresq.DATABASE)
    db.row_factory = sqlite3.Row
    return db


def arm(seconds: int) -> None:
    """Set the subject's last contact so they go overdue in N seconds."""
    db = connect()
    row = db.execute("SELECT id FROM accounts WHERE username = ?",
                     (SUBJECT,)).fetchone()
    if row is None:
        raise SystemExit(f"no account called {SUBJECT} — run `flask --app app seed`")

    now = datetime.now(timezone.utc)
    # Overdue is last contact plus the default interval, so to go red in N
    # seconds the last check-in has to be that interval minus N ago.
    contact = now - timedelta(minutes=diresq.DEFAULT_CHECKIN_MINUTES,
                              seconds=-seconds)

    changed = db.execute(
        "UPDATE checkins SET created_at = ?, received_at = ? WHERE responder = ?",
        (contact.isoformat(timespec="seconds"),
         contact.isoformat(timespec="seconds"), row["id"])).rowcount

    if not changed:
        raise SystemExit(f"{SUBJECT} has no check-ins to wind back")

    # Clear any alarm already raised, or the switch will decide it has
    # already done its job and file nothing.
    db.execute("DELETE FROM reports WHERE auto_filed_for = ?", (row["id"],))
    db.commit()

    print(f"{SUBJECT} goes overdue in {seconds}s "
          f"({contact.isoformat(timespec='seconds')})")
    print("Open /board and start recording. The row turns red on its own.")


def reset() -> None:
    """Drop anything the switch filed, so the next take starts clean."""
    db = connect()
    gone = db.execute("DELETE FROM reports WHERE auto_filed_for IS NOT NULL").rowcount
    db.commit()
    print(f"removed {gone} auto-filed report(s)")
    print("Run `flask --app app seed` for a completely fresh incident.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--in", dest="seconds", type=int, default=12,
                        help="seconds from now that the row should go red")
    parser.add_argument("--reset", action="store_true",
                        help="delete auto-filed reports and stop")
    args = parser.parse_args()

    reset() if args.reset else arm(args.seconds)


if __name__ == "__main__":
    main()
