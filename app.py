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
from pathlib import Path

from dotenv import load_dotenv
from flask import (
    Flask, flash, g, jsonify, redirect, render_template, request, session, url_for
)
from werkzeug.security import check_password_hash, generate_password_hash

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
               acc.username, acc.capabilities
        FROM assignments asg
        JOIN accounts acc ON acc.id = asg.responder
        WHERE asg.report_id = ?
        ORDER BY asg.joined_at
    """, (report_id,)).fetchall()]
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
        return render_template("report.html", report=None), 404
    return render_template("report.html", report=report)


@app.post("/report/<int:report_id>/rescue")
@login_required
def report_rescue(report_id: int):
    """Join a report. Anyone can, and any number of people can."""
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
               r.subject    AS report_subject,
               chk.created_at AS last_checkin,
               chk.lat      AS last_lat,
               chk.lng      AS last_lng
        FROM accounts acc
        LEFT JOIN assignments asg
               ON asg.responder = acc.id AND asg.status != 'cleared'
        LEFT JOIN reports r ON r.id = asg.report_id
        LEFT JOIN (
            SELECT responder, lat, lng, created_at,
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
            },
            "last_position": None if row["last_checkin"] is None else {
                "lat": row["last_lat"],
                "lng": row["last_lng"],
                "at": row["last_checkin"],
            },
        })

    board.sort(key=lambda r: (BOARD_ORDER.index(r["state"]),
                             -(r["minutes_since_contact"] or 0)))
    return board


def form_or_json(field: str) -> str:
    if request.is_json:
        return str((request.get_json(silent=True) or {}).get(field, "")).strip()
    return (request.form.get(field) or "").strip()


@app.post("/api/assignments/<int:assignment_id>/status")
@login_required
def api_assignment_status(assignment_id: int):
    """Advance your own assignment: en_route -> on_scene -> cleared."""
    wanted = form_or_json("status").lower()
    db = get_db()

    row = db.execute(
        "SELECT responder, status FROM assignments WHERE id = ?", (assignment_id,)
    ).fetchone()
    if row is None:
        return jsonify({"error": "no such assignment"}), 404
    if row["responder"] != current_user()["id"]:
        return jsonify({"error": "not your assignment"}), 403
    if wanted not in ALLOWED_TRANSITIONS[row["status"]]:
        return jsonify({
            "error": f"cannot go from {row['status']} to {wanted or 'nothing'}",
            "allowed": sorted(ALLOWED_TRANSITIONS[row["status"]]),
        }), 400

    if wanted == "cleared":
        # Leaving retracts your staffing vote: you can no longer see the scene.
        db.execute(
            "UPDATE assignments SET status = ?, staffing_vote = NULL WHERE id = ?",
            (wanted, assignment_id))
    else:
        db.execute("UPDATE assignments SET status = ? WHERE id = ?",
                   (wanted, assignment_id))
    db.commit()
    return jsonify({"id": assignment_id, "status": wanted})


@app.post("/api/reports/<int:report_id>/staffing")
@login_required
def api_report_staffing(report_id: int):
    """Vote on how staffed a scene is. On-scene responders only, because
    they are the only ones who can see it."""
    vote = form_or_json("staffing").lower()
    if vote not in STAFFING_ORDER:
        return jsonify({"error": "unknown staffing signal",
                        "allowed": list(STAFFING_ORDER)}), 400

    db = get_db()
    row = db.execute("""
        SELECT id, status FROM assignments
        WHERE report_id = ? AND responder = ?
    """, (report_id, current_user()["id"])).fetchone()

    if row is None:
        return jsonify({"error": "you have not joined this report"}), 403
    if row["status"] != "on_scene":
        return jsonify({"error": "only on-scene responders can set staffing",
                        "your_status": row["status"]}), 403

    db.execute("UPDATE assignments SET staffing_vote = ? WHERE id = ?",
               (vote, row["id"]))
    db.commit()
    return jsonify({"report_id": report_id,
                    "your_vote": vote,
                    "staffing": staffing_for(report_id)})


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
        return render_template("report.html", report=None), 404

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

    db = get_db()
    db.execute("""
        INSERT INTO checkins (responder, lat, lng, created_at)
        VALUES (?, ?, ?, ?)
    """, (current_user()["id"], lat, lng, now_iso()))
    db.commit()
    return jsonify({"ok": True, "at": now_iso()}), 201


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
