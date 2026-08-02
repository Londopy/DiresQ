"""DiresQ -- Katy Youth Hacks 2026.

Backend skeleton: connection helper + the six routes templates/ already needs.

    python -m venv .venv && .venv\\Scripts\\activate     (Windows)
    pip install -r requirements.txt
    flask --app app init-db
    flask --app app seed
    flask --app app run --debug

Then http://127.0.0.1:5000

Login is deliberately bypassable while the core loop is being built --
see DIRESQ_DEV_USER below. Per work etiquette: login lands last.
"""

from __future__ import annotations

import os
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from functools import wraps

from flask import (
    Flask, flash, g, jsonify, redirect, render_template, request, session, url_for
)
from werkzeug.security import check_password_hash, generate_password_hash

# --------------------------------------------------------------------------- #
# config
# --------------------------------------------------------------------------- #

DATABASE = os.environ.get("DIRESQ_DB", "diresq.db")

# Default check-in interval when a responder gives no ETA. Doc open question
# suggested 30 min; that is the answer until someone says otherwise.
DEFAULT_CHECKIN_MINUTES = 30

# ETA guardrails ("Limits We're Fixing #2"). The timer is a safety mechanism --
# a 12-hour interval is not a check-in, it's an off switch.
ETA_MIN_MINUTES = 5
ETA_WARN_MINUTES = 120
ETA_MAX_MINUTES = 240

PRIORITIES = ("HIGH", "MEDIUM", "LOW")

# Strings sort wrong alphabetically (HIGH < LOW < MEDIUM). Always rank via this.
PRIORITY_RANK = """
    CASE r.priority WHEN 'HIGH' THEN 3 WHEN 'MEDIUM' THEN 2 ELSE 1 END
"""

# Most conservative wins. need_more always beats adequate -- an optimistic
# report must never suppress a call for help.
STAFFING_ORDER = ("stood_down", "overstaffed", "adequate", "need_more")

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("DIRESQ_SECRET_KEY") or secrets.token_hex(32)


# --------------------------------------------------------------------------- #
# db
# --------------------------------------------------------------------------- #

def get_db() -> sqlite3.Connection:
    """One connection per request, torn down in close_db."""
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE, detect_types=sqlite3.PARSE_DECLTYPES)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(exc=None) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


# --------------------------------------------------------------------------- #
# auth
# --------------------------------------------------------------------------- #

def current_user() -> sqlite3.Row | None:
    """Logged-in account, or the dev override.

    Set DIRESQ_DEV_USER=londo to work on the core loop without logging in.
    Unset it before the demo.
    """
    uid = session.get("user_id")
    if uid is None:
        dev = os.environ.get("DIRESQ_DEV_USER")
        if not dev:
            return None
        return get_db().execute(
            "SELECT * FROM accounts WHERE username = ?", (dev,)
        ).fetchone()
    return get_db().execute("SELECT * FROM accounts WHERE id = ?", (uid,)).fetchone()


def login_required(view):
    @wraps(view)
    def wrapped(*a, **kw):
        if current_user() is None:
            return redirect(url_for("login", next=request.path))
        return view(*a, **kw)
    return wrapped


@app.context_processor
def inject_user():
    return {"current_user": current_user()}


# --------------------------------------------------------------------------- #
# staffing (computed, never stored)
# --------------------------------------------------------------------------- #

def resolve_staffing(votes) -> str:
    """Most conservative vote from anyone currently on scene.

    No votes at all -> 'unstaffed'. This is one comparison, and it is the
    difference between a safety system and a popularity contest.
    """
    ranked = [v for v in votes if v in STAFFING_ORDER]
    if not ranked:
        return "unstaffed"
    return max(ranked, key=STAFFING_ORDER.index)


def staffing_for(report_id: int) -> str:
    rows = get_db().execute(
        "SELECT staffing_vote FROM assignments "
        "WHERE report_id = ? AND status = 'on_scene'",
        (report_id,),
    ).fetchall()
    return resolve_staffing([r["staffing_vote"] for r in rows])


def is_overdue(joined_at: str, eta: str | None, last_checkin: str | None) -> bool:
    """Computed on read. A responder is overdue if now > eta, or -- with no
    eta -- if it has been longer than the default interval since their last
    contact (a check-in if they have one, otherwise when they joined)."""
    now = datetime.now(timezone.utc)
    deadline = parse_iso(eta)
    if deadline is None:
        last = parse_iso(last_checkin) or parse_iso(joined_at)
        if last is None:
            return False
        deadline = last + timedelta(minutes=DEFAULT_CHECKIN_MINUTES)
    return now > deadline


# --------------------------------------------------------------------------- #
# queries
# --------------------------------------------------------------------------- #

REPORT_COLUMNS = f"""
    r.id, r.subject, r.description, r.priority, r.lat, r.lng,
    r.status, r.needed, r.sender, r.created_at,
    a.username AS sender_name,
    COALESCE(SUM(asg.status = 'en_route'), 0) AS en_route_count,
    COALESCE(SUM(asg.status = 'on_scene'), 0) AS on_scene_count,
    {PRIORITY_RANK} AS priority_rank
"""


def fetch_reports(include_resolved: bool = False) -> list[dict]:
    """Feed order: priority desc, then newest first."""
    where = "" if include_resolved else "WHERE r.status NOT IN ('resolved', 'hidden')"
    rows = get_db().execute(f"""
        SELECT {REPORT_COLUMNS}
        FROM reports r
        JOIN accounts a ON a.id = r.sender
        LEFT JOIN assignments asg ON asg.report_id = r.id
        {where}
        GROUP BY r.id
        ORDER BY priority_rank DESC, r.created_at DESC
    """).fetchall()

    reports = []
    for row in rows:
        item = dict(row)
        item["staffing"] = staffing_for(row["id"])
        # map.js reads latitude/longitude; the schema stores lat/lng.
        item["latitude"] = row["lat"]
        item["longitude"] = row["lng"]
        reports.append(item)
    return reports


def fetch_report(report_id: int) -> dict | None:
    row = get_db().execute(f"""
        SELECT {REPORT_COLUMNS}
        FROM reports r
        JOIN accounts a ON a.id = r.sender
        LEFT JOIN assignments asg ON asg.report_id = r.id
        WHERE r.id = ?
        GROUP BY r.id
    """, (report_id,)).fetchone()
    if row is None:
        return None

    item = dict(row)
    item["latitude"] = row["lat"]
    item["longitude"] = row["lng"]
    item["staffing"] = staffing_for(report_id)
    item["responders"] = [dict(x) for x in get_db().execute("""
        SELECT asg.id, asg.status, asg.eta, asg.staffing_vote, asg.joined_at,
               acc.username, acc.capabilities
        FROM assignments asg
        JOIN accounts acc ON acc.id = asg.responder
        WHERE asg.report_id = ?
        ORDER BY asg.joined_at
    """, (report_id,)).fetchall()]
    return item


# --------------------------------------------------------------------------- #
# routes -- the six templates/ needs
# --------------------------------------------------------------------------- #

@app.get("/")
@login_required
def homepage():
    return render_template("homepage.html", reports=fetch_reports())


@app.get("/map")
@login_required
def map_page():
    # tojson cannot serialise sqlite3.Row -- fetch_reports returns dicts.
    located = [r for r in fetch_reports() if r["latitude"] is not None]
    return render_template("map.html", reports=located)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""

        row = get_db().execute(
            "SELECT * FROM accounts WHERE username = ?", (username,)
        ).fetchone()

        # One generic message, both branches -- never leak which usernames exist.
        if row is None or not check_password_hash(row["hashed_password"], password):
            flash("Invalid username or password")
            return render_template("login.html"), 401

        session.clear()
        session["user_id"] = row["id"]
        return redirect(request.args.get("next") or url_for("homepage"))

    return render_template("login.html")


@app.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/report/new", methods=["GET", "POST"])
@login_required
def report_new():
    if request.method == "POST":
        subject = (request.form.get("subject") or "").strip()
        priority = (request.form.get("priority") or "").strip().upper()
        description = (request.form.get("description") or "").strip()

        # report_make.html has no location input yet. Accept it when it appears;
        # until then reports file fine but will not appear on the map.
        lat = request.form.get("lat", type=float)
        lng = request.form.get("lng", type=float)

        if not subject:
            flash("Subject is required")
        elif priority not in PRIORITIES:
            flash("Priority must be HIGH, MEDIUM or LOW")
        else:
            db = get_db()
            cur = db.execute("""
                INSERT INTO reports
                    (subject, description, priority, lat, lng,
                     status, sender, created_at)
                VALUES (?, ?, ?, ?, ?, 'unassigned', ?, ?)
            """, (subject, description, priority, lat, lng,
                  current_user()["id"], now_iso()))
            db.commit()
            return redirect(url_for("report_detail", report_id=cur.lastrowid))

        return render_template("report_make.html"), 400

    return render_template("report_make.html")


@app.get("/report/<int:report_id>")
@login_required
def report_detail(report_id: int):
    report = fetch_report(report_id)
    if report is None:
        return render_template("report.html", report=None), 404
    return render_template("report.html", report=report)


@app.post("/report/<int:report_id>/rescue")
@login_required
def report_rescue(report_id: int):
    """The rescue button in report.html == 'join' in the API spec.

    Anyone can join. That is the point -- no claim lock, many responders
    per report.
    """
    db = get_db()
    user = current_user()

    if db.execute("SELECT 1 FROM reports WHERE id = ?", (report_id,)).fetchone() is None:
        return render_template("report.html", report=None), 404

    try:
        db.execute("""
            INSERT INTO assignments (report_id, responder, status, joined_at)
            VALUES (?, ?, 'en_route', ?)
        """, (report_id, user["id"], now_iso()))
    except sqlite3.IntegrityError:
        # UNIQUE(report_id, responder) -- already joined. 409, not an error page.
        flash("You have already joined this report")
        return redirect(url_for("report_detail", report_id=report_id))

    db.execute(
        "UPDATE reports SET status = 'active' WHERE id = ? AND status = 'unassigned'",
        (report_id,),
    )
    db.commit()
    return redirect(url_for("report_detail", report_id=report_id))


# --------------------------------------------------------------------------- #
# one JSON endpoint, so the 3s polling has somewhere to land later
# --------------------------------------------------------------------------- #

@app.get("/api/reports")
def api_reports():
    return jsonify(fetch_reports())


# --------------------------------------------------------------------------- #
# cli
# --------------------------------------------------------------------------- #

@app.cli.command("init-db")
def init_db_command() -> None:
    """Drop and recreate every table. Destructive, on purpose."""
    with app.app_context():
        with open("schema.sql", encoding="utf-8") as fh:
            get_db().executescript(fh.read())
        get_db().commit()
    print(f"initialised {DATABASE}")


@app.cli.command("seed")
def seed_command() -> None:
    """A handful of Katy-area reports. An empty board looks broken."""
    accounts = [
        ("londo", "responder", "boat,medical"),
        ("skythe", "responder", "truck,chainsaw"),
        ("kiyan", "reporter", ""),
    ]
    reports = [
        ("Water rising, 2 trapped", "Second floor, water at porch level.",
         "HIGH", 29.7858, -95.8244),
        ("Tree on driveway, elderly resident", "Cannot get the car out.",
         "MEDIUM", 29.7752, -95.8103),
        ("Roof damage, family of 4", "Tarp needed before the next band.",
         "MEDIUM", 29.7961, -95.7890),
        ("Power line down across Kingsland", "Sparking. Nobody near it.",
         "HIGH", 29.7834, -95.8321),
        ("Fence collapsed, dog loose", "Not urgent, reporting for the record.",
         "LOW", 29.7690, -95.8012),
    ]

    with app.app_context():
        db = get_db()
        for username, role, caps in accounts:
            db.execute("""
                INSERT OR IGNORE INTO accounts
                    (username, hashed_password, role, capabilities, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (username, generate_password_hash("diresq"), role, caps, now_iso()))

        sender = db.execute(
            "SELECT id FROM accounts WHERE username = 'kiyan'"
        ).fetchone()["id"]

        for subject, desc, priority, lat, lng in reports:
            db.execute("""
                INSERT INTO reports
                    (subject, description, priority, lat, lng,
                     status, sender, created_at)
                VALUES (?, ?, ?, ?, ?, 'unassigned', ?, ?)
            """, (subject, desc, priority, lat, lng, sender, now_iso()))

        db.commit()
    print(f"seeded {len(accounts)} accounts, {len(reports)} reports "
          f"(password for all: diresq)")


if __name__ == "__main__":
    app.run(debug=True)
