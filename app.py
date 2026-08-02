"""DiresQ backend.

    python -m venv .venv && .venv\\Scripts\\activate
    pip install -r requirements.txt
    flask --app app init-db
    flask --app app seed
    flask --app app run --debug

Set DIRESQ_DEV_USER=londo to skip the login wall while building.
"""

from __future__ import annotations

import os
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from functools import wraps
from math import atan2, cos, radians, sin, sqrt
from pathlib import Path

from dotenv import load_dotenv
from flask import (
    Flask, flash, g, jsonify, redirect, render_template, request, session, url_for
)
from werkzeug.security import check_password_hash, generate_password_hash

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

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("DIRESQ_SECRET_KEY") or secrets.token_hex(32)


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
    if not value:
        return None
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


def is_overdue(joined_at: str, eta: str | None, last_checkin: str | None) -> bool:
    """Derived at read time so there's no cron job to forget to start."""
    now = datetime.now(timezone.utc)
    deadline = parse_iso(eta)
    if deadline is None:
        last = parse_iso(last_checkin) or parse_iso(joined_at)
        if last is None:
            return False
        deadline = last + timedelta(minutes=DEFAULT_CHECKIN_MINUTES)
    return now > deadline


REPORT_COLUMNS = f"""
    r.id, r.subject, r.description, r.priority, r.lat, r.lng,
    r.status, r.needed, r.sender, r.created_at,
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

        row = get_db().execute(
            "SELECT * FROM accounts WHERE username = ?", (username,)
        ).fetchone()

        # Same message whether the user exists or the password was wrong,
        # otherwise this endpoint enumerates accounts for free.
        if row is None or not check_password_hash(row["hashed_password"], password):
            flash("Invalid username or password")
            return render_template("login.html"), 401

        session.clear()
        session["user_id"] = row["id"]
        return redirect(request.args.get("next") or url_for("homepage"))

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

        if len(username) < 3:
            flash("Username must be at least 3 characters")
        elif taken:
            flash("That username is taken")
        elif len(password) < 8:
            flash("Password must be at least 8 characters")
        elif password != confirm:
            flash("Passwords do not match")
        elif role not in ("responder", "reporter"):
            flash("Role must be responder or reporter")
        else:
            cur = db.execute("""
                INSERT INTO accounts
                    (username, hashed_password, role, capabilities, created_at)
                VALUES (?, ?, ?, '', ?)
            """, (username, generate_password_hash(password), role, now_iso()))
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
        db.execute(
            "UPDATE assignments SET status = ?, staffing_vote = NULL WHERE id = ?",
            (wanted, assignment_id))
    else:
        db.execute("UPDATE assignments SET status = ? WHERE id = ?",
                   (wanted, assignment_id))

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

    on_scene = db.execute("""
        SELECT 1 FROM assignments
        WHERE report_id = ? AND responder = ? AND status = 'on_scene'
    """, (report_id, user["id"])).fetchone()

    if report["sender"] != user["id"] and on_scene is None:
        flash("Only the reporter or someone on scene can resolve this")
        return redirect(url_for("report_detail", report_id=report_id))

    if report["status"] == "resolved":
        flash("Already resolved")
        return redirect(url_for("report_detail", report_id=report_id))

    db.execute("UPDATE reports SET status = 'resolved' WHERE id = ?", (report_id,))
    # Everyone still attached is done here.
    db.execute("""
        UPDATE assignments SET status = 'cleared', staffing_vote = NULL
        WHERE report_id = ? AND status != 'cleared'
    """, (report_id,))
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

    received = datetime.now(timezone.utc)
    db = get_db()
    db.execute("""
        INSERT INTO checkins (responder, lat, lng, created_at, received_at)
        VALUES (?, ?, ?, ?, ?)
    """, (current_user()["id"], lat, lng,
          happened_at.isoformat(timespec="seconds"),
          received.isoformat(timespec="seconds")))
    db.commit()

    late = (received - happened_at).total_seconds() > LATE_SYNC_SECONDS
    return answer({"ok": True,
                   "at": happened_at.isoformat(timespec="seconds"),
                   "received_at": received.isoformat(timespec="seconds"),
                   "synced_late": late},
                  201,
                  "Queued check-in synced." if late else "Checked in. Timer reset.")


# Resolved against this file, not the working directory, so pytest can run
# from anywhere.
SCHEMA = Path(__file__).with_name("schema.sql")


def init_db() -> None:
    """Drop every table and rebuild. Wipes the database."""
    with app.app_context():
        get_db().executescript(SCHEMA.read_text(encoding="utf-8"))
        get_db().commit()


def seed_data() -> tuple[int, int]:
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
    return len(accounts), len(reports)


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


if __name__ == "__main__":
    app.run(debug=True)
