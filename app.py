"""DiresQ backend.

    python -m venv .venv && .venv\\Scripts\\activate
    pip install -r requirements.txt
    flask --app app init-db
    flask --app app seed
    flask --app app run --debug

Set DIRESQ_DEV_USER=londo to skip the login wall while building.
"""

from __future__ import annotations

import base64
import binascii
import csv
import io
import os
import re
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from functools import wraps
from math import atan2, cos, radians, sin, sqrt
from pathlib import Path

import click
from dotenv import load_dotenv
from flask import (
    Flask, Response, flash, g, jsonify, redirect, render_template, request,
    send_from_directory, session, url_for
)
from werkzeug.security import check_password_hash, generate_password_hash

import transport
import triage
from eta import parse_eta

# Must run before anything reads os.environ. Real environment variables win
# over .env, so CI and your shell always override the file.
load_dotenv(Path(__file__).with_name(".env"))

DATABASE = os.environ.get("DIRESQ_DB", "diresq.db")

# How long a responder has to check in when they didn't give an ETA.
DEFAULT_CHECKIN_MINUTES = 30

# A 12-hour check-in interval isn't a check-in, it's an off switch.
ETA_MIN_MINUTES = 5
ETA_WARN_MINUTES = 120
ETA_MAX_MINUTES = 240

PRIORITIES = ("HIGH", "MEDIUM", "LOW")

# Never ORDER BY priority directly: alphabetically HIGH < LOW < MEDIUM.
PRIORITY_RANK = """
    CASE r.priority WHEN 'HIGH' THEN 3 WHEN 'MEDIUM' THEN 2 ELSE 1 END
"""

# Ascending order of caution. An optimistic responder must never be able to
# drown out someone asking for help, so we take the max, not the average.
STAFFING_ORDER = ("stood_down", "overstaffed", "adequate", "need_more")

USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9._-]{3,32}$")

# werkzeug will happily hash a megabyte of text and take its time doing it.
# Nobody's real password is this long.
MAX_PASSWORD_LENGTH = 128
MIN_PASSWORD_LENGTH = 8

# Wrong guesses allowed before a username is locked out for a while. Counted
# in memory, so it resets on restart — see docs/limits.md.
MAX_LOGIN_ATTEMPTS = 8
LOGIN_LOCKOUT_MINUTES = 5

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("DIRESQ_SECRET_KEY") or secrets.token_hex(32)
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    # Lax, not Strict: the login form posts across a redirect and Strict eats
    # the cookie. Lax still blocks the cross-site POSTs that matter.
    SESSION_COOKIE_SAMESITE="Lax",
    # Only over HTTPS in production. The dev server is plain HTTP, so honour
    # the flag rather than hardcoding it and breaking localhost.
    SESSION_COOKIE_SECURE=os.environ.get("DIRESQ_HTTPS_ONLY") == "1",
)

# username -> (failures, locked until). Deliberately not in the database: a
# lockout that survives a restart is a lockout an attacker can make permanent.
LOGIN_FAILURES: dict[str, tuple[int, datetime]] = {}


def safe_next(target: str | None) -> str | None:
    """Only same-site paths. Anything else is somebody else's website.

    `?next=https://elsewhere/` on a login page is the classic phishing setup:
    a real login on a real domain that hands you off afterwards.
    """
    if not target or not target.startswith("/") or target.startswith("//"):
        return None
    return target


def login_locked(username: str) -> int:
    """Minutes remaining on a lockout, or 0."""
    failures, until = LOGIN_FAILURES.get(username, (0, datetime.min))
    if failures < MAX_LOGIN_ATTEMPTS:
        return 0
    remaining = (until - datetime.now(timezone.utc).replace(tzinfo=None))
    if remaining.total_seconds() <= 0:
        LOGIN_FAILURES.pop(username, None)
        return 0
    return max(1, int(remaining.total_seconds() // 60) + 1)


def note_login_failure(username: str) -> None:
    failures = LOGIN_FAILURES.get(username, (0, datetime.min))[0] + 1
    until = (datetime.now(timezone.utc).replace(tzinfo=None)
             + timedelta(minutes=LOGIN_LOCKOUT_MINUTES))
    LOGIN_FAILURES[username] = (failures, until)


def get_db() -> sqlite3.Connection:
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
    """Read an ISO timestamp, including the shape browsers actually send.

    `new Date().toISOString()` gives "2026-08-02T07:00:00.000Z". Python only
    learned to read that trailing Z in 3.11, so on anything older every
    check-in the offline queue sent would be rejected as unreadable — on the
    developer's machine it would work fine and in deployment it would not.
    """
    if not value:
        return None
    if value.endswith(("Z", "z")):
        value = value[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def current_user() -> sqlite3.Row | None:
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


@app.context_processor
def inject_overdue_count():
    """Overdue count for the nav badge, on every page.

    One query per render. Fine with a handful of responders, would need
    caching with more.
    """
    def overdue_count() -> int:
        if current_user() is None:
            return 0
        return sum(1 for r in fetch_responders() if r["overdue"])
    return {"overdue_count": overdue_count}


def resolve_staffing(votes) -> str:
    """Most cautious vote from anyone on scene, or 'unstaffed' if nobody voted."""
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


def deadline_for(joined_at: str, eta: str | None,
                 last_checkin: str | None) -> datetime | None:
    """When we expect to hear from someone next.

    Their ETA if they gave one, otherwise the default interval counted from
    whichever of their last check-in or their joining is more recent.
    """
    deadline = parse_iso(eta)
    if deadline is not None:
        return deadline
    last = parse_iso(last_checkin) or parse_iso(joined_at)
    if last is None:
        return None
    return last + timedelta(minutes=DEFAULT_CHECKIN_MINUTES)


def is_overdue(joined_at: str, eta: str | None, last_checkin: str | None) -> bool:
    """Derived at read time so there's no cron job to forget to start."""
    deadline = deadline_for(joined_at, eta, last_checkin)
    return deadline is not None and datetime.now(timezone.utc) > deadline


REPORT_COLUMNS = f"""
    r.id, r.subject, r.description, r.priority, r.lat, r.lng,
    r.status, r.needed, r.sender, r.auto_filed_for, r.created_at,
    a.username AS sender_name,
    COALESCE(SUM(asg.status = 'en_route'), 0) AS en_route_count,
    COALESCE(SUM(asg.status = 'on_scene'), 0) AS on_scene_count,
    {PRIORITY_RANK} AS priority_rank
"""


def fetch_reports(include_resolved: bool = False) -> list[dict]:
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
        # map.js reads latitude/longitude. Drop these two lines once it doesn't.
        item["latitude"] = row["lat"]
        item["longitude"] = row["lng"]
        reports.append(item)

    # SQL ordered by priority; staffing is computed above, so the tie-break
    # has to happen here. Sort is stable, so equal keys keep the SQL order.
    reports.sort(key=lambda r: (-r["priority_rank"],
                                -FEED_RANK.get(r["staffing"], 1)))
    return reports


def coverage_gaps(reports: list[dict] | None = None) -> list[dict]:
    """Open reports with nobody on the way and nobody there.

    Not the same as understaffed. These are the ones where the count is zero
    — nobody has even said they're coming — which is the failure the whole
    project exists to make visible.
    """
    if reports is None:
        reports = fetch_reports()
    return [r for r in reports
            if not r["en_route_count"] and not r["on_scene_count"]]


@app.context_processor
def inject_coverage_gap():
    # A callable, not a value: pages that don't show the banner shouldn't pay
    # for the query.
    def coverage_gap_count() -> int:
        if current_user() is None:
            return 0
        return len(coverage_gaps())
    return {"coverage_gap_count": coverage_gap_count}


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
               asg.position_mismatch,
               acc.username, acc.capabilities, acc.id AS account_id
        FROM assignments asg
        JOIN accounts acc ON acc.id = asg.responder
        WHERE asg.report_id = ?
        ORDER BY asg.joined_at
    """, (report_id,)).fetchall()]

    # What the person looking at this page is allowed to press. Working it out
    # here keeps the permission rules in one place instead of scattered
    # through the template.
    user = current_user()
    mine = next((r for r in item["responders"]
                 if user and r["account_id"] == user["id"]), None)

    item["mine"] = mine
    item["can_join"] = bool(user) and mine is None
    item["next_status"] = (
        sorted(ALLOWED_TRANSITIONS[mine["status"]])[0]
        if mine and ALLOWED_TRANSITIONS[mine["status"]] else None
    )
    item["can_set_staffing"] = bool(mine) and mine["status"] == "on_scene"
    item["can_check_in"] = bool(mine) and mine["status"] != "cleared"
    item["can_resolve"] = bool(user) and item["status"] != "resolved" and (
        item["sender"] == user["id"]
        or (mine is not None and mine["status"] == "on_scene")
    )
    return item


@app.get("/")
@login_required
def homepage():
    return render_template("homepage.html", reports=fetch_reports())


@app.get("/map")
@login_required
def map_page():
    # tojson can't serialise sqlite3.Row, so fetch_reports hands back dicts.
    located = [r for r in fetch_reports() if r["latitude"] is not None]
    return render_template("map.html", reports=located)


# Browsers ask for both of these on every page whether you have them or not.
# No template shares a <head>, so serving them here beats adding a link tag to
# nine files — and it keeps the console clean while we're recording.
@app.get("/favicon.ico")
def favicon():
    return send_from_directory(app.static_folder + "/images", "favicon.ico")


@app.get("/robots.txt")
def robots():
    # Live reports name real addresses. None of it should be searchable.
    return "User-agent: *\nDisallow: /\n", 200, {"Content-Type": "text/plain"}


@app.get("/board")
@login_required
def board():
    # Rendered server-side so the page works without JS; board.js then polls
    # /api/responders and re-renders on its own.
    return render_template("board.html", responders=fetch_responders())


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""

        locked = login_locked(username)
        if locked:
            flash(f"Too many attempts. Try again in {locked} minutes.")
            return render_template("login.html"), 429

        # Long enough to be a denial of service rather than a password.
        if len(password) > MAX_PASSWORD_LENGTH:
            flash("Invalid username or password")
            return render_template("login.html"), 401

        row = get_db().execute(
            "SELECT * FROM accounts WHERE username = ?", (username,)
        ).fetchone()

        # Same message whether the user exists or the password was wrong,
        # otherwise this endpoint enumerates accounts for free.
        if row is None or not check_password_hash(row["hashed_password"], password):
            note_login_failure(username)
            flash("Invalid username or password")
            return render_template("login.html"), 401

        LOGIN_FAILURES.pop(username, None)
        session.clear()
        session["user_id"] = row["id"]
        # Straight from the query string, so it has to be checked. Otherwise
        # /login?next=https://not-us.example is a working phishing page on our
        # own domain.
        return redirect(safe_next(request.args.get("next")) or url_for("homepage"))

    return render_template("login.html")


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        confirm = request.form.get("confirm_password") or ""
        # signup.html has no role selector yet. One account can do both jobs,
        # so responder is the safe default.
        role = (request.form.get("role") or "responder").strip().lower()

        db = get_db()
        taken = db.execute(
            "SELECT 1 FROM accounts WHERE username = ?", (username,)
        ).fetchone()

        # Someone signing up as "Londo" when "londo" exists is a mix-up
        # waiting to happen on a board where names are how you tell people
        # apart.
        similar = db.execute(
            "SELECT 1 FROM accounts WHERE username = ? COLLATE NOCASE",
            (username,)).fetchone()

        if not USERNAME_PATTERN.match(username):
            flash("Usernames are 3-32 characters: letters, numbers, . _ -")
        elif taken or similar:
            flash("That username is taken")
        elif len(password) < MIN_PASSWORD_LENGTH:
            flash(f"Password must be at least {MIN_PASSWORD_LENGTH} characters")
        elif len(password) > MAX_PASSWORD_LENGTH:
            flash(f"Password must be under {MAX_PASSWORD_LENGTH} characters")
        elif password.lower() in ("password", "diresq", username.lower()):
            flash("Pick a password that isn't a guess")
        elif password != confirm:
            flash("Passwords do not match")
        elif role not in ("responder", "reporter"):
            flash("Role must be responder or reporter")
        else:
            # Responders get a node key up front. Nobody has a radio yet, but
            # handing one out later means a second flow to build and forget.
            cur = db.execute("""
                INSERT INTO accounts
                    (username, hashed_password, role, capabilities,
                     node_key, created_at)
                VALUES (?, ?, ?, '', ?, ?)
            """, (username, generate_password_hash(password), role,
                  transport.new_node_key() if role == "responder" else None,
                  now_iso()))
            db.commit()
            session.clear()
            session["user_id"] = cur.lastrowid
            return redirect(url_for("homepage"))

        return render_template("signup.html"), 400

    return render_template("signup.html")


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
        lat = request.form.get("lat", type=float)
        lng = request.form.get("lng", type=float)

        if not subject:
            flash("Subject is required")
        elif priority not in PRIORITIES:
            flash("Priority must be HIGH, MEDIUM or LOW")
        elif lat is None or lng is None:
            # The hidden lat/lng inputs carry `required`, but hidden inputs are
            # exempt from browser validation, so an untouched map still submits.
            flash("Click the map to set a location")
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
        return render_template("notfound.html"), 404
    return render_template("report.html", report=report)


@app.post("/report/<int:report_id>/rescue")
@login_required
def report_rescue(report_id: int):
    """Join a report. Anyone can, and any number of people can."""
    db = get_db()
    user = current_user()

    if db.execute("SELECT 1 FROM reports WHERE id = ?", (report_id,)).fetchone() is None:
        return render_template("notfound.html"), 404

    # Optional free-text ETA. A rejected one still lets you join; you just get
    # the default interval instead of a deadline nobody was sure about.
    eta_iso = eta_confidence = None
    eta_text = (request.form.get("eta_text") or "").strip()
    if eta_text:
        parsed = parse_eta(eta_text)
        if parsed.accepted:
            eta_iso = parsed.when.isoformat(timespec="seconds")
            eta_confidence = parsed.confidence
            if parsed.warning:
                flash(parsed.warning)
        else:
            flash(f"{parsed.message} Using the default "
                  f"{DEFAULT_CHECKIN_MINUTES} minute interval.")

    try:
        db.execute("""
            INSERT INTO assignments
                (report_id, responder, status, eta, eta_confidence, joined_at)
            VALUES (?, ?, 'en_route', ?, ?, ?)
        """, (report_id, user["id"], eta_iso, eta_confidence, now_iso()))
    except sqlite3.IntegrityError:
        # UNIQUE(report_id, responder) fired. Already joined, not an error.
        flash("You have already joined this report")
        return redirect(url_for("report_detail", report_id=report_id))

    db.execute(
        "UPDATE reports SET status = 'active' WHERE id = ? AND status = 'unassigned'",
        (report_id,),
    )
    db.commit()
    return redirect(url_for("report_detail", report_id=report_id))


# Worst first. This is the order the board renders in.
BOARD_ORDER = ("overdue", "on_scene", "en_route", "available")

# How staffing moves a report in the feed, high sorts first. Applied as a
# tie-break inside a priority band, never across one: six people shouting for
# help at a blocked driveway must not bury a trapped family nobody has seen.
# Nobody-on-it outranks covered, because that gap is the entire thesis.
FEED_RANK = {
    "need_more": 3,
    "unstaffed": 2,
    "adequate": 1,
    "overstaffed": 0,
    "stood_down": 0,
}

# How far from a report you can be while claiming to be on scene, in metres.
# Generous on purpose: phone GPS is bad in bad weather, and a false accusation
# is worse than a missed one.
ON_SCENE_RADIUS_M = 500

# Flags needed before a report drops out of the feed.
FLAG_THRESHOLD = 3

# A check-in queued offline can say when it was really made. Bounds on that
# claim: clocks drift a bit, so allow a little future, and anything older than
# the cap is too stale to be worth trusting.
CLOCK_SKEW_SECONDS = 120
MAX_BACKDATE_HOURS = 12

# Gap between "I checked in" and "we received it" that counts as a late sync,
# so a coordinator can see someone was out of contact.
LATE_SYNC_SECONDS = 60

# How far past their deadline someone has to be before the server stops
# waiting for a human to notice and files a report about them itself. Counted
# from the deadline, not from their last check-in, so someone who said "back
# in two hours" gets two hours plus this, not this.
SILENT_ESCALATE_MINUTES = 15


def metres_between(lat1, lng1, lat2, lng2) -> float | None:
    """Great-circle distance. Haversine, so no dependency for one sum."""
    if None in (lat1, lng1, lat2, lng2):
        return None
    r = 6371000
    p1, p2 = radians(lat1), radians(lat2)
    dp = radians(lat2 - lat1)
    dl = radians(lng2 - lng1)
    a = sin(dp / 2) ** 2 + cos(p1) * cos(p2) * sin(dl / 2) ** 2
    return 2 * r * atan2(sqrt(a), sqrt(1 - a))


# One direction only. You cannot un-arrive at a scene.
ALLOWED_TRANSITIONS = {
    "en_route": {"on_scene"},
    "on_scene": {"cleared"},
    "cleared": set(),
}


def fetch_responders() -> list[dict]:
    """The accountability board: who is out, where, and who is late.

    Each row carries a single `state` field so the frontend switches on one
    value instead of recomputing the rules.
    """
    rows = get_db().execute("""
        SELECT acc.id, acc.username, acc.capabilities,
               asg.id       AS assignment_id,
               asg.report_id,
               asg.status   AS assignment_status,
               asg.eta, asg.joined_at, asg.staffing_vote,
               asg.position_mismatch,
               r.subject    AS report_subject,
               chk.created_at AS last_checkin,
               chk.received_at AS last_received,
               chk.lat      AS last_lat,
               chk.lng      AS last_lng
        FROM accounts acc
        LEFT JOIN assignments asg
               ON asg.responder = acc.id AND asg.status != 'cleared'
        LEFT JOIN reports r ON r.id = asg.report_id
        LEFT JOIN (
            SELECT responder, lat, lng, created_at, received_at,
                   ROW_NUMBER() OVER (PARTITION BY responder
                                      ORDER BY created_at DESC) AS rn
            FROM checkins
        ) chk ON chk.responder = acc.id AND chk.rn = 1
        WHERE acc.role = 'responder'
        ORDER BY acc.username, asg.joined_at DESC
    """).fetchall()

    now = datetime.now(timezone.utc)
    board, seen = [], set()

    for row in rows:
        # A responder can be on two reports at once; show the latest.
        if row["id"] in seen:
            continue
        seen.add(row["id"])

        overdue = False
        minutes = None
        if row["assignment_id"] is not None:
            overdue = is_overdue(row["joined_at"], row["eta"], row["last_checkin"])
            contact = parse_iso(row["last_checkin"]) or parse_iso(row["joined_at"])
            if contact is not None:
                minutes = int((now - contact).total_seconds() // 60)

        if row["assignment_id"] is None:
            state = "available"
        elif overdue:
            state = "overdue"
        else:
            state = row["assignment_status"]

        board.append({
            "id": row["id"],
            "username": row["username"],
            "capabilities": [c for c in (row["capabilities"] or "").split(",") if c],
            "state": state,
            "overdue": overdue,
            "minutes_since_contact": minutes,
            "assignment": None if row["assignment_id"] is None else {
                "id": row["assignment_id"],
                "report_id": row["report_id"],
                "report_subject": row["report_subject"],
                "status": row["assignment_status"],
                "staffing_vote": row["staffing_vote"],
                "eta": row["eta"],
                "joined_at": row["joined_at"],
                "position_mismatch": bool(row["position_mismatch"]),
            },
            "last_position": None if row["last_checkin"] is None else {
                "lat": row["last_lat"],
                "lng": row["last_lng"],
                "at": row["last_checkin"],
                "received_at": row["last_received"],
                # True when it reached us well after it was made, i.e. it sat
                # in a queue while they were offline.
                "synced_late": late_sync(row["last_checkin"],
                                         row["last_received"]),
            },
        })

    board.sort(key=lambda r: (BOARD_ORDER.index(r["state"]),
                             -(r["minutes_since_contact"] or 0)))
    return board


def late_sync(made_at: str | None, received_at: str | None) -> bool:
    """Did this check-in reach us well after it was made?"""
    made, got = parse_iso(made_at), parse_iso(received_at)
    if made is None or got is None:
        return False
    return (got - made).total_seconds() > LATE_SYNC_SECONDS


def sweep_silent_responders() -> list[int]:
    """File a report for anyone who has gone quiet and stayed quiet.

    A red row on the board only helps if somebody is looking at the board. If
    a responder is this far past their deadline, the assumption that someone
    will notice has already failed, so the server files a report at their last
    known position and lets it compete for attention like any other.

    Filed under their own name, because it is about them and there is nobody
    else to attribute it to. The `auto_filed_for` column is what keeps it to
    one: while an open report points at someone, we don't file another.
    """
    db = get_db()
    rows = db.execute("""
        SELECT asg.responder, asg.joined_at, asg.eta,
               acc.username,
               r.subject       AS report_subject,
               r.lat           AS report_lat,
               r.lng           AS report_lng,
               chk.created_at  AS last_checkin,
               chk.lat         AS last_lat,
               chk.lng         AS last_lng
        FROM assignments asg
        JOIN accounts acc ON acc.id = asg.responder
        JOIN reports  r   ON r.id = asg.report_id
        LEFT JOIN (
            SELECT responder, lat, lng, created_at,
                   ROW_NUMBER() OVER (PARTITION BY responder
                                      ORDER BY created_at DESC) AS rn
            FROM checkins
        ) chk ON chk.responder = asg.responder AND chk.rn = 1
        WHERE asg.status != 'cleared'
    """).fetchall()

    now = datetime.now(timezone.utc)
    filed = []

    for row in rows:
        deadline = deadline_for(row["joined_at"], row["eta"], row["last_checkin"])
        if deadline is None:
            continue
        if now < deadline + timedelta(minutes=SILENT_ESCALATE_MINUTES):
            continue

        already = db.execute("""
            SELECT 1 FROM reports
            WHERE auto_filed_for = ? AND status NOT IN ('resolved', 'hidden')
        """, (row["responder"],)).fetchone()
        if already:
            continue

        # Their last check-in if they sent one, otherwise the scene they said
        # they were going to. The second is a guess, and the description says
        # so, because sending people to the wrong place is its own emergency.
        seen = parse_iso(row["last_checkin"])
        if row["last_lat"] is not None:
            lat, lng = row["last_lat"], row["last_lng"]
            where = "last known position"
        else:
            lat, lng = row["report_lat"], row["report_lng"]
            where = "the scene they were heading to, no position ever received"

        silent = int((now - (seen or parse_iso(row["joined_at"]) or now))
                     .total_seconds() // 60)

        db.execute("""
            INSERT INTO reports
                (subject, description, priority, lat, lng,
                 status, sender, auto_filed_for, created_at)
            VALUES (?, ?, 'HIGH', ?, ?, 'unassigned', ?, ?, ?)
        """, (
            f"No contact from {row['username']} for {silent} minutes",
            f"Filed automatically. {row['username']} was working "
            f"\"{row['report_subject']}\" and has not checked in since their "
            f"deadline passed. Pin is their {where}. Nobody has confirmed "
            f"they are alright — this needs a person, not a refresh.",
            lat, lng, row["responder"], row["responder"], now_iso(),
        ))
        filed.append(db.execute("SELECT last_insert_rowid() AS id")
                     .fetchone()["id"])

    if filed:
        db.commit()
    return filed


# Pages where it's worth checking whether anyone has gone quiet. There is no
# scheduler — deliberately, since a timer process that dies takes the alarm
# with it — so the sweep rides along on reads instead. A GET that writes is
# not lovely, but it is idempotent, and the alternative is a cron job nobody
# starts.
SWEEP_ON = {"homepage", "board", "map_page", "api_reports", "api_responders"}


@app.before_request
def escalate_silence():
    if (request.method == "GET"
            and request.endpoint in SWEEP_ON
            and current_user() is not None):
        sweep_silent_responders()


def claimed_time(raw: str) -> tuple[datetime, str | None]:
    """When a check-in says it happened. Empty means now.

    The value comes from the client, so it's a claim, not a fact. We bound it:
    barely in the future is clock drift, far in the future or very old is
    either a broken device or someone playing games.
    """
    now = datetime.now(timezone.utc)
    if not raw:
        return now, None

    when = parse_iso(raw)
    if when is None:
        return now, "Could not read that timestamp."
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)

    if (when - now).total_seconds() > CLOCK_SKEW_SECONDS:
        return now, "That check-in is dated in the future."
    if (now - when).total_seconds() > MAX_BACKDATE_HOURS * 3600:
        return now, f"Too old to accept, over {MAX_BACKDATE_HOURS} hours."

    # Slightly ahead is a drifting clock, not a lie. Don't let it sit in the
    # future, but don't reject it either.
    return min(when, now), None


def position_looks_wrong(report_id: int, account_id: int) -> bool:
    """Is this person's last check-in nowhere near the report they claim to be at?

    Catches honest mistakes and lazy faking. Anyone determined can still lie
    about where they are, and no amount of code fixes that.
    """
    db = get_db()
    report = db.execute("SELECT lat, lng FROM reports WHERE id = ?",
                        (report_id,)).fetchone()
    checkin = db.execute("""
        SELECT lat, lng FROM checkins
        WHERE responder = ? ORDER BY created_at DESC LIMIT 1
    """, (account_id,)).fetchone()

    if report is None or checkin is None:
        return False  # No claim to check against yet.

    away = metres_between(report["lat"], report["lng"],
                          checkin["lat"], checkin["lng"])
    return away is not None and away > ON_SCENE_RADIUS_M


def form_or_json(field: str) -> str:
    if request.is_json:
        return str((request.get_json(silent=True) or {}).get(field, "")).strip()
    return (request.form.get(field) or "").strip()


def answer(payload: dict, status: int, message: str, report_id: int | None = None):
    """Reply as JSON to fetch, or bounce back to the page for a form post.

    The buttons are plain forms so they work with JavaScript off. Same
    endpoints still return JSON when something asks for it.
    """
    if request.is_json:
        return jsonify(payload), status
    if message:
        flash(message)
    target = request.form.get("next")
    if target and target.startswith("/"):
        return redirect(target)
    if report_id is not None:
        return redirect(url_for("report_detail", report_id=report_id))
    return redirect(url_for("homepage"))


@app.post("/api/assignments/<int:assignment_id>/status")
@login_required
def api_assignment_status(assignment_id: int):
    """Advance your own assignment: en_route -> on_scene -> cleared."""
    wanted = form_or_json("status").lower()
    db = get_db()

    row = db.execute(
        "SELECT report_id, responder, status FROM assignments WHERE id = ?",
        (assignment_id,),
    ).fetchone()
    if row is None:
        return answer({"error": "no such assignment"}, 404, "No such assignment")
    if row["responder"] != current_user()["id"]:
        return answer({"error": "not your assignment"}, 403,
                      "That is not your assignment", row["report_id"])
    if wanted not in ALLOWED_TRANSITIONS[row["status"]]:
        return answer({
            "error": f"cannot go from {row['status']} to {wanted or 'nothing'}",
            "allowed": sorted(ALLOWED_TRANSITIONS[row["status"]]),
        }, 400, f"Cannot go from {row['status']} to {wanted or 'nothing'}",
            row["report_id"])

    if wanted == "cleared":
        # Leaving retracts your staffing vote: you can no longer see the scene.
        db.execute("UPDATE assignments SET status = ?, staffing_vote = NULL, "
                   "status_changed_at = ? WHERE id = ?",
                   (wanted, now_iso(), assignment_id))
    else:
        db.execute("UPDATE assignments SET status = ?, status_changed_at = ? "
                   "WHERE id = ?", (wanted, now_iso(), assignment_id))

    if wanted == "on_scene":
        db.execute("UPDATE assignments SET position_mismatch = ? WHERE id = ?",
                   (int(position_looks_wrong(row["report_id"],
                                             current_user()["id"])),
                    assignment_id))
    db.commit()
    return answer({"id": assignment_id, "status": wanted}, 200,
                  f"You are now {wanted.replace('_', ' ')}", row["report_id"])


@app.post("/api/reports/<int:report_id>/staffing")
@login_required
def api_report_staffing(report_id: int):
    """Vote on how staffed a scene is. On-scene responders only, because
    they are the only ones who can see it."""
    vote = form_or_json("staffing").lower()
    if vote not in STAFFING_ORDER:
        return answer({"error": "unknown staffing signal",
                       "allowed": list(STAFFING_ORDER)}, 400,
                      "Unknown staffing signal", report_id)

    db = get_db()
    row = db.execute("""
        SELECT id, status FROM assignments
        WHERE report_id = ? AND responder = ?
    """, (report_id, current_user()["id"])).fetchone()

    if row is None:
        return answer({"error": "you have not joined this report"}, 403,
                      "Join this report before signalling staffing", report_id)
    if row["status"] != "on_scene":
        return answer({"error": "only on-scene responders can set staffing",
                       "your_status": row["status"]}, 403,
                      "Only people on scene can set staffing", report_id)

    db.execute("UPDATE assignments SET staffing_vote = ? WHERE id = ?",
               (vote, row["id"]))
    db.commit()
    return answer({"report_id": report_id,
                   "your_vote": vote,
                   "staffing": staffing_for(report_id)}, 200,
                  f"Marked {vote.replace('_', ' ')}", report_id)


@app.post("/report/<int:report_id>/resolve")
@login_required
def report_resolve(report_id: int):
    """Close a report.

    Allowed for whoever filed it, and for anyone currently on scene. The
    reporter knows when their own problem is handled; the people standing
    there can see that it is. Nobody else has grounds.
    """
    db = get_db()
    user = current_user()

    report = db.execute(
        "SELECT sender, status FROM reports WHERE id = ?", (report_id,)
    ).fetchone()
    if report is None:
        return render_template("notfound.html"), 404

    # Checked before permission, because resolving clears you off the report
    # and so takes away the right you just used. Pressing the button twice
    # would otherwise answer "you are not allowed to do that", which is a
    # confusing thing to be told about something you did ten seconds ago.
    if report["status"] == "resolved":
        flash("Already resolved")
        return redirect(url_for("report_detail", report_id=report_id))

    on_scene = db.execute("""
        SELECT 1 FROM assignments
        WHERE report_id = ? AND responder = ? AND status = 'on_scene'
    """, (report_id, user["id"])).fetchone()

    if report["sender"] != user["id"] and on_scene is None:
        flash("Only the reporter or someone on scene can resolve this")
        return redirect(url_for("report_detail", report_id=report_id))

    db.execute("UPDATE reports SET status = 'resolved' WHERE id = ?", (report_id,))
    # Everyone still attached is done here.
    db.execute("""
        UPDATE assignments SET status = 'cleared', staffing_vote = NULL,
                               status_changed_at = ?
        WHERE report_id = ? AND status != 'cleared'
    """, (now_iso(), report_id))
    db.commit()
    return redirect(url_for("homepage"))


@app.post("/report/<int:report_id>/flag")
@login_required
def report_flag(report_id: int):
    """Flag a report as fake. One per person, hidden at FLAG_THRESHOLD.

    Hidden is not deleted: whoever filed it and anyone already on it still
    see it, because being outvoted by three strangers shouldn't strand
    someone who is already on their way.
    """
    db = get_db()
    user = current_user()

    if db.execute("SELECT 1 FROM reports WHERE id = ?", (report_id,)).fetchone() is None:
        if request.is_json:
            return jsonify({"error": "no such report"}), 404
        return render_template("notfound.html"), 404

    try:
        db.execute("""
            INSERT INTO report_flags (report_id, account_id, created_at)
            VALUES (?, ?, ?)
        """, (report_id, user["id"], now_iso()))
    except sqlite3.IntegrityError:
        return answer({"error": "already flagged"}, 409,
                      "You already flagged this", report_id)

    db.execute("UPDATE reports SET flags = flags + 1 WHERE id = ?", (report_id,))
    row = db.execute("SELECT flags, status FROM reports WHERE id = ?",
                     (report_id,)).fetchone()

    if row["flags"] >= FLAG_THRESHOLD and row["status"] not in ("resolved", "hidden"):
        db.execute("UPDATE reports SET status = 'hidden' WHERE id = ?", (report_id,))
    db.commit()

    return answer({"report_id": report_id, "flags": row["flags"],
                   "hidden": row["flags"] >= FLAG_THRESHOLD},
                  200, "Flagged. Thanks.", report_id)


@app.get("/triage")
@login_required
def triage_page():
    return render_template("triage.html", questions=triage.QUESTIONS)


@app.post("/api/triage")
@login_required
def api_triage():
    """Run START on four observations and return the severity it implies."""
    data = request.get_json(silent=True) or request.form

    def flag(name):
        value = data.get(name)
        if value in (None, "", "unknown"):
            return None
        return str(value).lower() in ("1", "true", "yes", "on")

    can_walk = flag("can_walk")
    breathing = flag("breathing")

    if can_walk is None:
        return jsonify({"error": "answer whether they can walk"}), 400

    rate = data.get("respiratory_rate")
    try:
        rate = None if rate in (None, "", "unknown") else int(rate)
    except (TypeError, ValueError):
        return jsonify({"error": "breaths per minute must be a number"}), 400

    # "Not breathing" and "breathing at an unknown rate" are different answers.
    if breathing is False:
        rate = None
    elif breathing and rate is None:
        return jsonify({"error": "give a rough breaths per minute"}), 400

    result = triage.assess(
        can_walk=can_walk,
        respiratory_rate=rate,
        has_radial_pulse=flag("has_radial_pulse"),
        follows_commands=flag("follows_commands"),
    )
    return jsonify({
        "priority": result.priority,
        "severity": result.severity,
        "explanation": result.explanation,
    })


def stamp(value: str | None) -> str:
    """ICS forms want date and time in separate, human columns."""
    when = parse_iso(value)
    return "" if when is None else when.strftime("%m/%d/%Y %H:%M")


def ics214_rows() -> list[list[str]]:
    """Build an ICS 214 Activity Log out of what the database already knows.

    ICS 214 is the form an incident actually runs on — every agency at a
    multi-agency scene keeps one, and afterwards it's the document that says
    who was there and what they did. Coordinators fill these in by hand,
    usually from memory, usually hours late.

    We have every one of these events with a timestamp already, so producing
    the form is a formatting problem rather than a remembering problem. That
    is most of the argument for logging responders at all.
    """
    db = get_db()
    now = datetime.now(timezone.utc)

    responders = db.execute("""
        SELECT acc.username, acc.capabilities, MIN(asg.joined_at) AS first_seen
        FROM accounts acc
        JOIN assignments asg ON asg.responder = acc.id
        GROUP BY acc.id
        ORDER BY first_seen
    """).fetchall()

    # Everything with a time on it, in one list, sorted at the end.
    events: list[tuple[str, str]] = []

    for row in db.execute("""
        SELECT r.subject, r.priority, r.created_at, r.status, r.auto_filed_for,
               acc.username
        FROM reports r JOIN accounts acc ON acc.id = r.sender
    """).fetchall():
        if row["auto_filed_for"] is not None:
            events.append((row["created_at"],
                           f"AUTOMATIC: {row['subject']} — no human filed this"))
        else:
            events.append((row["created_at"],
                           f"{row['priority']} report filed by "
                           f"{row['username']}: {row['subject']}"))
        if row["status"] == "resolved":
            # Resolving isn't timestamped separately, so it's logged against
            # the report rather than given a time we'd be making up.
            events.append((row["created_at"], f"RESOLVED: {row['subject']}"))

    for row in db.execute("""
        SELECT acc.username, asg.status, asg.joined_at, asg.status_changed_at,
               asg.eta, asg.position_mismatch, r.subject
        FROM assignments asg
        JOIN accounts acc ON acc.id = asg.responder
        JOIN reports  r   ON r.id = asg.report_id
    """).fetchall():
        eta = f" (ETA {stamp(row['eta'])})" if row["eta"] else ""
        events.append((row["joined_at"],
                       f"{row['username']} assigned to {row['subject']}{eta}"))
        if row["status_changed_at"]:
            moved = {"on_scene": "arrived on scene at",
                     "cleared": "cleared from"}.get(row["status"], "updated")
            events.append((row["status_changed_at"],
                           f"{row['username']} {moved} {row['subject']}"))
        if row["position_mismatch"]:
            events.append((row["status_changed_at"] or row["joined_at"],
                           f"FLAG: {row['username']} reported on scene at "
                           f"{row['subject']} from over "
                           f"{ON_SCENE_RADIUS_M} m away"))

    for row in db.execute("""
        SELECT acc.username, c.created_at, c.received_at, c.lat, c.lng
        FROM checkins c JOIN accounts acc ON acc.id = c.responder
    """).fetchall():
        where = ("" if row["lat"] is None
                 else f" at {row['lat']:.5f}, {row['lng']:.5f}")
        late = " [synced late]" if late_sync(row["created_at"],
                                             row["received_at"]) else ""
        events.append((row["created_at"],
                       f"{row['username']} checked in{where}{late}"))

    events.sort()
    started = events[0][0] if events else now_iso()

    rows = [
        ["ICS 214 - ACTIVITY LOG"],
        [],
        ["1. Incident Name", "DiresQ activation - Katy, TX"],
        ["2. Operational Period", "From", stamp(started),
         "To", now.strftime("%m/%d/%Y %H:%M")],
        ["3. Name", current_user()["username"],
         "ICS Position", "Resource Unit Leader",
         "Home Agency", "DiresQ (volunteer)"],
        [],
        ["4. Resources Assigned"],
        ["Name", "ICS Position", "Home Agency", "First Assigned"],
    ]
    for row in responders:
        rows.append([row["username"],
                     row["capabilities"].replace(",", " / ") or "Unassigned",
                     "DiresQ (volunteer)",
                     stamp(row["first_seen"])])

    rows += [[], ["5. Activity Log"], ["Date/Time", "Notable Activities"]]
    rows += [[stamp(when), what] for when, what in events]

    rows += [
        [],
        ["6. Prepared by", current_user()["username"],
         "Position", "Resource Unit Leader",
         "Date/Time", now.strftime("%m/%d/%Y %H:%M")],
        [],
        ["Generated by DiresQ from logged activity. Times are UTC. Report "
         "resolution and staffing changes are not separately timestamped and "
         "are logged against the record they belong to."],
    ]
    return rows


@app.get("/export/ics214")
@login_required
def export_ics214():
    buffer = io.StringIO()
    csv.writer(buffer).writerows(ics214_rows())
    stamped = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
    return Response(
        buffer.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition":
                 f'attachment; filename="ICS-214-diresq-{stamped}.csv"'},
    )


# Not linked from anywhere. Whoever goes looking has earned it.
@app.get("/credits")
def credits_page():
    return render_template("credits.html")


@app.get("/api/reports")
def api_reports():
    return jsonify(fetch_reports())


@app.get("/api/responders")
@login_required
def api_responders():
    return jsonify(fetch_responders())


def record_checkin(responder_id: int, lat, lng, happened_at: datetime,
                   client_id: str | None = None) -> dict:
    """Write a check-in and say what we made of it.

    Every route in ends up here — the phone, and the radio. If they ever
    disagree about what a check-in means, it will be because someone added a
    second copy of this function.

    `client_id` makes it safe to send the same check-in twice. A queued one
    gets retried whenever the connection flickers, and without this a bad
    signal would fill the log with duplicates of one person standing still.
    Sending it again is not an error and doesn't write a second row — it just
    tells you about the one already there.
    """
    db = get_db()

    if client_id:
        seen = db.execute("""
            SELECT created_at, received_at FROM checkins
            WHERE client_id = ? AND responder = ?
        """, (client_id, responder_id)).fetchone()
        if seen is not None:
            return {
                "ok": True,
                "duplicate": True,
                "at": seen["created_at"],
                "received_at": seen["received_at"],
                "synced_late": late_sync(seen["created_at"],
                                         seen["received_at"]),
            }

    received = datetime.now(timezone.utc)
    try:
        db.execute("""
            INSERT INTO checkins
                (responder, lat, lng, client_id, created_at, received_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (responder_id, lat, lng, client_id or None,
              happened_at.isoformat(timespec="seconds"),
              received.isoformat(timespec="seconds")))
    except sqlite3.IntegrityError:
        # Two retries landing at the same moment. The id is UNIQUE across the
        # table, so somebody else's is a 409 rather than a silent overwrite.
        db.rollback()
        return {"ok": False, "error": "that check-in id belongs to someone else"}
    db.commit()

    return {
        "ok": True,
        "duplicate": False,
        "at": happened_at.isoformat(timespec="seconds"),
        "received_at": received.isoformat(timespec="seconds"),
        "synced_late":
            (received - happened_at).total_seconds() > LATE_SYNC_SECONDS,
    }


@app.post("/api/checkin")
@login_required
def api_checkin():
    lat = request.form.get("lat", type=float)
    lng = request.form.get("lng", type=float)
    if request.is_json:
        payload = request.get_json(silent=True) or {}
        lat = payload.get("lat", lat)
        lng = payload.get("lng", lng)

    # A check-in that sat in an offline queue says when it was really made.
    # Without this the timer would run from the moment it synced, so a row
    # that should still be red would quietly go green.
    happened_at, error = claimed_time(form_or_json("happened_at"))
    if error:
        return answer({"error": error}, 400, error)

    client_id = form_or_json("client_id")[:64] or None
    result = record_checkin(current_user()["id"], lat, lng, happened_at,
                            client_id)
    if not result["ok"]:
        return answer(result, 409, result["error"])

    if result["duplicate"]:
        message = "Already had that one."
    elif result["synced_late"]:
        message = "Queued check-in synced."
    else:
        message = "Checked in. Timer reset."
    return answer(result, 200 if result["duplicate"] else 201, message)


@app.post("/api/uplink")
def api_uplink():
    """A check-in that arrived as bytes rather than as a logged-in browser.

    This is the seam for a radio. A LoRa gateway has no session and no cookie
    — it has a packet it heard and a socket to hand it over on — so this
    endpoint identifies the responder from inside the packet instead.

    Which means it is unauthenticated, and anyone who can reach it can move a
    pin. That is the honest state of it: see docs/limits.md. It exists to
    prove the shape is right, not to be exposed to the internet.
    """
    raw = form_or_json("packet")
    if not raw:
        return jsonify({"error": "no packet"}), 400

    try:
        packet = base64.b64decode(raw, validate=True)
    except (binascii.Error, ValueError):
        return jsonify({"error": "packet is not valid base64"}), 400

    # The id inside the packet only chooses which key to check against.
    # Nothing is trusted until the signature says it can be.
    try:
        claimed = transport.responder_in(packet)
    except transport.PacketError as err:
        return jsonify({"error": str(err)}), 400

    who = get_db().execute("SELECT id, node_key FROM accounts WHERE id = ?",
                           (claimed,)).fetchone()

    # Same answer whether the account doesn't exist or has no key. Otherwise
    # this endpoint tells you which responder ids are real.
    if who is None or not who["node_key"]:
        return jsonify({"error": "unknown or unkeyed responder"}), 404

    try:
        body = transport.unseal(packet, who["node_key"])
        checkin = transport.unpack_checkin(body)
    except transport.PacketError as err:
        # Radio links corrupt things, and so does anyone poking at this. A bad
        # packet is expected traffic, not an incident: say what was wrong and
        # drop it.
        return jsonify({"error": str(err)}), 400

    # The packet carries an age, not a timestamp — a node running off a
    # battery in a flood is the last clock you want to trust.
    happened_at = (datetime.now(timezone.utc)
                   - timedelta(minutes=checkin.age_minutes))

    result = record_checkin(checkin.responder_id, checkin.lat, checkin.lng,
                            happened_at)
    result["responder_id"] = checkin.responder_id
    result["bytes"] = len(packet)
    return jsonify(result), 201


# Resolved against this file, not the working directory, so pytest can run
# from anywhere.
SCHEMA = Path(__file__).with_name("schema.sql")


def init_db() -> None:
    """Drop every table and rebuild. Wipes the database."""
    with app.app_context():
        get_db().executescript(SCHEMA.read_text(encoding="utf-8"))
        get_db().commit()


# An incident already two hours old, not a fresh empty board. Everything below
# is timed relative to now, so the demo looks live whenever you seed it.
#
# Two pairs are doing the real work:
#   Kingsland (nobody on it) sits ABOVE Mayde Creek (four people, overstaffed)
#   Sam has been silent 47 minutes and is red before you touch anything
SEED_ACCOUNTS = [
    # username, role, capabilities, password
    ("londo",    "responder", "boat,medical"),
    ("skythe",   "responder", "truck,chainsaw"),
    ("kiyan",    "reporter",  ""),
    ("m.torres", "responder", "boat,swiftwater"),
    ("j.okafor", "responder", "truck,chainsaw,generator"),
    ("d.nguyen", "responder", "medical"),
    ("s.reyes",  "responder", "boat,medical"),
    ("a.whitlock", "reporter", ""),
]

# subject, description, priority, lat, lng, filed_by, minutes_ago
SEED_REPORTS = [
    ("Water rising, two adults and a dog upstairs",
     "1400 block Katy Fort Bend Rd. Water was at the porch an hour ago, now "
     "it's over the first step inside. They've gone up to the second floor. "
     "Nobody has a boat on this street.",
     "HIGH", 29.7858, -95.8244, "a.whitlock", 96),

    ("Power line down across Kingsland, sparking",
     "Across both lanes just past the school. Still arcing. Two cars turned "
     "around, one drove over it. Nobody is standing traffic off.",
     "HIGH", 29.7834, -95.8321, "kiyan", 71),

    ("Elderly man, oxygen concentrator, power out 3 hrs",
     "22100 Highland Knolls. Tank backup won't last the night and his "
     "daughter can't get through on the roads.",
     "HIGH", 29.7433, -95.7688, "a.whitlock", 58),

    ("Car in the water at Mayde Creek crossing",
     "Driver got out and is on the bank. Vehicle is going nowhere. Needs "
     "someone to close the road before the next person tries it.",
     "MEDIUM", 29.7961, -95.7890, "kiyan", 84),

    ("Roof peeled back, family of four inside",
     "5300 Fry Rd. Tarp would hold it until morning. They're dry for now but "
     "the next band is due around two.",
     "MEDIUM", 29.8011, -95.7205, "a.whitlock", 47),

    ("Tree across driveway, can't get the car out",
     "Not hurt, not flooding, just stuck. Chainsaw job. Happy to wait.",
     "MEDIUM", 29.7752, -95.8103, "kiyan", 39),

    ("Storm drain blocked, water backing up Green Trails",
     "Ankle deep and climbing at the low end. Might be nothing, might be four "
     "houses in an hour.",
     "MEDIUM", 29.7529, -95.7402, "a.whitlock", 25),

    ("Fence down, two dogs loose on Westheimer Pkwy",
     "Reporting so somebody has a record of it. Please don't send anyone.",
     "LOW", 29.7690, -95.8012, "kiyan", 18),
]

# report index, responder, status, staffing vote, joined how long ago,
# eta minutes from joining (None = default interval), last check-in mins ago
SEED_ASSIGNMENTS = [
    # Mayde Creek: four people on a job that needs two. This is the point.
    (3, "m.torres", "on_scene", "overstaffed", 74, None, 6),
    (3, "j.okafor", "on_scene", "overstaffed", 68, None, 9),
    (3, "d.nguyen", "on_scene", None,          61, None, 4),
    (3, "skythe",   "en_route", None,          12, 25,   None),

    # Water rising: one person, asking for help, nobody else coming.
    (0, "londo",    "on_scene", "need_more",   80, None, 11),

    # Oxygen: someone en route with a sensible ETA.
    (2, "a.whitlock", "en_route", None,        20, 30,   14),

    # Roof: Sam went, and nobody has heard from him since.
    (4, "s.reyes",  "on_scene", None,          62, None, 47),
]


def seed_minimal() -> tuple[int, int]:
    """Three accounts, five untouched reports, nobody responding.

    What the tests run against. Kept separate from the demo seed so that
    making the demo look better can't quietly change what the tests mean.
    """
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
                    (username, hashed_password, role, capabilities,
                     node_key, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (username, generate_password_hash("diresq"), role, caps,
                  transport.new_node_key(), now_iso()))

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
    return len(accounts), len(reports)


def seed_data() -> tuple[int, int]:
    """Load a disaster already in progress.

    Seeding an empty board makes the app look like a to-do list. Seeding it
    mid-incident shows what it's for.
    """
    now = datetime.now(timezone.utc)

    def ago(minutes):
        return (now - timedelta(minutes=minutes)).isoformat(timespec="seconds")

    with app.app_context():
        db = get_db()

        for username, role, caps in SEED_ACCOUNTS:
            db.execute("""
                INSERT OR IGNORE INTO accounts
                    (username, hashed_password, role, capabilities,
                     node_key, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (username, generate_password_hash("diresq"), role, caps,
                  transport.new_node_key(), ago(240)))

        who = {r["username"]: r["id"] for r in
               db.execute("SELECT id, username FROM accounts").fetchall()}

        report_ids = []
        for subject, desc, priority, lat, lng, filed_by, minutes in SEED_REPORTS:
            cur = db.execute("""
                INSERT INTO reports
                    (subject, description, priority, lat, lng,
                     status, sender, created_at)
                VALUES (?, ?, ?, ?, ?, 'unassigned', ?, ?)
            """, (subject, desc, priority, lat, lng, who[filed_by], ago(minutes)))
            report_ids.append(cur.lastrowid)

        for idx, username, status, vote, joined, eta_mins, checkin in SEED_ASSIGNMENTS:
            report_id = report_ids[idx]
            eta = None
            if eta_mins is not None:
                eta = (now - timedelta(minutes=joined)
                       + timedelta(minutes=eta_mins)).isoformat(timespec="seconds")

            # Someone still en route hasn't changed status since joining, so
            # they get no stamp. The others arrived a few minutes after they
            # set off, which is what the activity log will show.
            moved = None if status == "en_route" else ago(max(joined - 8, 0))

            db.execute("""
                INSERT INTO assignments
                    (report_id, responder, status, staffing_vote,
                     eta, eta_confidence, joined_at, status_changed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (report_id, who[username], status, vote, eta,
                  0.95 if eta else None, ago(joined), moved))

            db.execute(
                "UPDATE reports SET status = 'active' WHERE id = ? "
                "AND status = 'unassigned'", (report_id,))

            if checkin is not None:
                # Scatter positions near the report so the map has something.
                report = db.execute(
                    "SELECT lat, lng FROM reports WHERE id = ?", (report_id,)
                ).fetchone()
                jitter = (hash(username) % 9 - 4) / 5000
                db.execute("""
                    INSERT INTO checkins
                        (responder, lat, lng, created_at, received_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (who[username], report["lat"] + jitter,
                      report["lng"] - jitter, ago(checkin), ago(checkin)))

        db.commit()
    return len(SEED_ACCOUNTS), len(SEED_REPORTS)


@app.cli.command("init-db")
def init_db_command() -> None:
    """Drop every table and rebuild. Wipes the database."""
    init_db()
    print(f"initialised {DATABASE}")


@app.cli.command("seed")
def seed_command() -> None:
    """Load test accounts and Katy-area reports."""
    n_accounts, n_reports = seed_data()
    print(f"seeded {n_accounts} accounts, {n_reports} reports "
          f"(password for all: diresq)")


@app.cli.command("sweep")
def sweep_command() -> None:
    """File reports for anyone who has gone quiet.

    The same sweep that runs when a page is loaded. Having it as a command
    means it can be put on cron or Task Scheduler, so the alarm doesn't depend
    on somebody having a tab open:

        */5 * * * *  cd /srv/diresq && flask --app app sweep
    """
    with app.app_context():
        filed = sweep_silent_responders()
    if not filed:
        print("nobody is overdue past the escalation window")
    else:
        print(f"filed {len(filed)} report(s): {', '.join(map(str, filed))}")


@app.cli.command("node-key")
@click.argument("username")
@click.option("--rotate", is_flag=True, help="Replace the existing key.")
def node_key_command(username: str, rotate: bool) -> None:
    """Show or replace the radio key for one responder.

    The key goes in that person's node, and nothing else. Printing it here is
    the whole distribution mechanism, which is honest about the scale we are
    at — see docs/offline.md.
    """
    with app.app_context():
        db = get_db()
        row = db.execute("SELECT id, node_key FROM accounts WHERE username = ?",
                         (username,)).fetchone()
        if row is None:
            raise click.ClickException(f"no account called {username}")

        if rotate or not row["node_key"]:
            key = transport.new_node_key()
            db.execute("UPDATE accounts SET node_key = ? WHERE id = ?",
                       (key, row["id"]))
            db.commit()
        else:
            key = row["node_key"]

    print(f"responder id : {row['id']}")
    print(f"node key     : {key}")


if __name__ == "__main__":
    app.run(debug=True)
