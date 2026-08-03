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
import json
import secrets
import sqlite3
import uuid
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

import classify
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

# Ascending order of severity, so `max(..., key=PRIORITY_ORDER.index)` picks
# the worst. Used when several reports turn out to be one incident: a LOW
# duplicate must never be able to quieten a HIGH one, for the same reason the
# most cautious staffing signal wins.
PRIORITY_ORDER = ("LOW", "MEDIUM", "HIGH")

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
    r.received_at, r.client_id, r.dupe_of, r.dupe_score,
    dup.subject AS dupe_subject,
    a.username AS sender_name,
    COALESCE(SUM(asg.status = 'en_route'), 0) AS en_route_count,
    COALESCE(SUM(asg.status = 'on_scene'), 0) AS on_scene_count,
    {PRIORITY_RANK} AS priority_rank
"""


def age(item: dict) -> dict:
    """Say how old a report is, and whether it sat in a queue on the way here.

    A report written forty minutes ago and synced just now describes a house
    that may already have been cleared. The feed is not allowed to render that
    as something that has only just come in — the whole argument of this
    project is that a stale claim presented as a fresh one is worse than no
    claim at all.

    So both times travel with the report, along with the two numbers a person
    actually reads: how long ago it was written, and whether the gap between
    writing and arriving is big enough to mention.
    """
    written = parse_iso(item.get("created_at"))
    item["synced_late"] = late_sync(item.get("created_at"),
                                    item.get("received_at"))
    item["minutes_old"] = (
        None if written is None
        else max(0, int((datetime.now(timezone.utc) - written).total_seconds() // 60))
    )
    return item


def fetch_reports(include_resolved: bool = False) -> list[dict]:
    where = "" if include_resolved else "WHERE r.status NOT IN ('resolved', 'hidden')"
    rows = get_db().execute(f"""
        SELECT {REPORT_COLUMNS}
        FROM reports r
        JOIN accounts a ON a.id = r.sender
        LEFT JOIN assignments asg ON asg.report_id = r.id
        LEFT JOIN reports dup ON dup.id = r.dupe_of
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
        age(item)
        reports.append(item)

    # SQL ordered by priority; staffing is computed above, so the tie-break
    # has to happen here. Sort is stable, so equal keys keep the SQL order.
    reports.sort(key=lambda r: (-r["priority_rank"],
                                -FEED_RANK.get(r["staffing"], 1)))
    return reports


def incident_root(report_id: int, parent: dict[int, int | None]) -> int:
    """Follow `dupe_of` up to the report everything else is a duplicate of.

    `link_duplicate` always points a report at an older one, so these chains
    terminate. The `seen` guard is for the impossible case anyway: a cycle
    here would hang the feed, and the feed is the page somebody is staring at
    during a flood.
    """
    seen = set()
    while parent.get(report_id) is not None and report_id not in seen:
        seen.add(report_id)
        report_id = parent[report_id]
    return report_id


def group_incidents(reports: list[dict]) -> list[dict]:
    """Collapse reports that describe one incident into one row.

    This is the whole argument of the project, applied to its own data. We
    already detect that two reports are the same incident. Left ungrouped,
    six people spread across two duplicate rows renders as two comfortably
    staffed reports — and the feed, whose entire job is to make convergence
    visible, hides it. Three plus three looks fine. Six at one address is the
    thing we exist to show.

    So an incident carries:

      * **distinct** responders, not summed counts. One person who joined both
        duplicates is one person. Summing assignment rows would invent help
        that isn't there, which is the same lie in the other direction.
      * the most severe priority of its reports, and the most cautious
        staffing signal. A duplicate filed as LOW cannot quieten a HIGH one.
      * every report, still individually linkable. The grouping is a view. It
        does not merge anything, and either report can still be opened,
        joined and resolved on its own.

    A lone report becomes an incident of one and renders exactly as it always
    has, which is deliberate: nothing about the common case changes.
    """
    parent = {r["id"]: r["dupe_of"] for r in reports}
    open_ids = set(parent)

    # A report whose twin has been resolved is its own incident again — the
    # thing it pointed at is no longer somewhere anybody is going.
    for report_id, points_at in parent.items():
        if points_at not in open_ids:
            parent[report_id] = None

    clustered: dict[int, list[dict]] = {}
    for report in reports:
        clustered.setdefault(incident_root(report["id"], parent),
                             []).append(report)

    # Who is actually out, per incident. One query rather than one per row.
    crews: dict[int, dict[str, set]] = {}
    if reports:
        marks = ",".join("?" * len(open_ids))
        for row in get_db().execute(f"""
            SELECT report_id, responder, status FROM assignments
            WHERE report_id IN ({marks}) AND status != 'cleared'
        """, tuple(open_ids)):
            root = incident_root(row["report_id"], parent)
            crew = crews.setdefault(root, {"en_route": set(), "on_scene": set()})
            crew[row["status"]].add(row["responder"])

    incidents = []
    for root, members in clustered.items():
        members.sort(key=lambda r: r["id"])
        lead = next(r for r in members if r["id"] == root)
        crew = crews.get(root, {"en_route": set(), "on_scene": set()})

        # Somebody en route to one report and on scene at its duplicate is on
        # scene. Count them once, at the further-along status.
        on_scene = crew["on_scene"]
        en_route = crew["en_route"] - on_scene

        incidents.append({
            "id": root,
            "reports": members,
            "subject": lead["subject"],
            "description": lead["description"],
            "priority": max((r["priority"] for r in members),
                            key=PRIORITY_ORDER.index),
            "priority_rank": max(r["priority_rank"] for r in members),
            "en_route_count": len(en_route),
            "on_scene_count": len(on_scene),
            "staffing": resolve_staffing(
                [r["staffing"] for r in members
                 if r["staffing"] != "unstaffed"]),
            "duplicate_count": len(members),
            # The freshest thing anybody said about this incident. An older
            # duplicate must not make a report filed a minute ago look stale.
            "minutes_old": min((r["minutes_old"] for r in members
                                if r["minutes_old"] is not None), default=None),
            "synced_late": any(r["synced_late"] for r in members),
            # And the age of the report that actually arrived late, which is
            # not always the freshest one. The card says "written N minutes
            # ago, reached us later" — taking N from one report and the
            # lateness from another would be two true facts assembled into a
            # false sentence.
            "stale_minutes": min((r["minutes_old"] for r in members
                                  if r["synced_late"]
                                  and r["minutes_old"] is not None),
                                 default=None),
            "auto_filed_for": lead["auto_filed_for"],
        })

    incidents.sort(key=lambda i: (-i["priority_rank"],
                                  -FEED_RANK.get(i["staffing"], 1),
                                  -max(r["id"] for r in i["reports"])))
    return incidents


def coverage_gaps(incidents: list[dict] | None = None) -> list[dict]:
    """Incidents with nobody on the way and nobody there.

    Not the same as understaffed. These are the ones where the count is zero
    — nobody has even said they're coming — which is the failure the whole
    project exists to make visible.

    Counted per incident rather than per report. Two duplicates of one flood
    with nobody going is one street nobody is going to, and reporting it as
    two would inflate the number that is supposed to be the honest one.
    """
    if incidents is None:
        incidents = group_incidents(fetch_reports())
    return [i for i in incidents
            if not i["en_route_count"] and not i["on_scene_count"]]


@app.context_processor
def inject_demo_mode():
    """True on the hosted demo.

    A public instance of something that looks like an emergency service needs
    to say what it is, on the page, not only in the docs. It also warns that
    anything filed here is thrown away, so nobody types a real address into a
    database that resets when the server sleeps.
    """
    return {"demo_mode": os.environ.get("DIRESQ_DEMO") == "1"}


@app.context_processor
def inject_coverage_gap():
    # A callable, not a value: pages that don't show the banner shouldn't pay
    # for the query.
    def coverage_gap_count() -> int:
        if current_user() is None:
            return 0
        return len(coverage_gaps())
    return {"coverage_gap_count": coverage_gap_count}


def who_can_help(capabilities: list[str]) -> list[dict]:
    """Available responders who have each of these capabilities.

    "Available" means no assignment they haven't cleared. Somebody already on
    a job is not an answer to "who can take this one", and offering them as
    one is how you end up pulling a person off a scene they were needed at.

    This is the other half of what the classifier does. It reads a description
    and says *a boat is needed*; without this, that fact and the fact that
    three people have boats never meet, and a coordinator has to hold both in
    their head at two in the morning.
    """
    if not capabilities:
        return []

    rows = get_db().execute("""
        SELECT acc.username, acc.capabilities
        FROM accounts acc
        LEFT JOIN assignments asg
               ON asg.responder = acc.id AND asg.status != 'cleared'
        WHERE acc.role = 'responder' AND asg.id IS NULL
        ORDER BY acc.username
    """).fetchall()

    matches = []
    for capability in capabilities:
        free = [row["username"] for row in rows
                if capability in (row["capabilities"] or "").split(",")]
        matches.append({"capability": capability, "responders": free})
    return matches


def fetch_report(report_id: int) -> dict | None:
    row = get_db().execute(f"""
        SELECT {REPORT_COLUMNS}
        FROM reports r
        JOIN accounts a ON a.id = r.sender
        LEFT JOIN assignments asg ON asg.report_id = r.id
        LEFT JOIN reports dup ON dup.id = r.dupe_of
        WHERE r.id = ?
        GROUP BY r.id
    """, (report_id,)).fetchone()
    if row is None:
        return None

    item = dict(row)
    item["latitude"] = row["lat"]
    item["longitude"] = row["lng"]
    item["staffing"] = staffing_for(report_id)
    age(item)
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

    # What the description implies is needed, and who is free who has it.
    # Costs a classifier run — about a tenth of a millisecond — and one query.
    needed = classify.suggest(
        f"{item['subject']} {item['description']}").capabilities
    item["needs"] = needed
    item["matches"] = who_can_help(needed)

    return item


@app.get("/")
@login_required
def homepage():
    return render_template("homepage.html",
                           incidents=group_incidents(fetch_reports()))


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


# A service worker can only control pages at or below its own path, so this
# has to be served from the root rather than from /static/ where the file
# actually lives. Serving it from /static/scripts/sw.js would give it a scope
# of /static/scripts/ and it would control nothing.
@app.get("/sw.js")
def service_worker():
    response = send_from_directory(app.static_folder + "/scripts", "sw.js")
    response.headers["Content-Type"] = "application/javascript"
    # Don't let a browser hold on to an old worker for a year.
    response.headers["Cache-Control"] = "no-cache"
    # Set here rather than left to the after_request default, because what a
    # worker is allowed to fetch is decided by the headers on this response.
    response.headers["Content-Security-Policy"] = WORKER_CONTENT_SECURITY_POLICY
    return response


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


def link_duplicate(report_id: int) -> dict | None:
    """Look for an open report describing the same incident, and link to it.

    Run on arrival, for every report, however it got here. That timing is the
    whole point. The duplicate check used to live in `/api/suggest`, which is
    a live call made while somebody types — so a report written offline was
    never checked at all, and two neighbours on the same street with no signal
    both filed "water rising on Kingsland", both synced, and six people went
    to one address while the next street had nobody. That is the precise
    failure this project exists to prevent, and the check that was built to
    stop it was the one thing that could not run.

    Running it here fixes both halves. The comparison is against every open
    report *at the moment this one is written*, which — because reports are
    written one at a time — includes the ones that arrived seconds earlier in
    the same sync batch, not merely the ones that existed before anyone went
    offline.

    It links. It never merges. TF-IDF over a fifty-five line corpus is good
    enough to be worth a coordinator's glance and nowhere near good enough to
    fold somebody's call for help into somebody else's row. The later report
    points at the earlier one; both stay in the feed, both stay joinable.
    """
    db = get_db()
    mine = db.execute("""
        SELECT id, subject, description, lat, lng FROM reports WHERE id = ?
    """, (report_id,)).fetchone()
    if mine is None:
        return None

    # Only ever point backwards, at a report that arrived before this one.
    #
    # `incident_root` assumes that and says so, but nothing enforced it, and
    # the assumption is only free while this runs exactly once per report at
    # insert time. Run it over a table that already has both halves of a pair
    # in it — which the demo seed does — and the two link to each other. The
    # cycle guard in `incident_root` then quietly hands back two different
    # roots and the pair never groups: the duplicate detector working
    # perfectly, and the feed showing nothing, with no error anywhere.
    #
    # Ids are handed out in arrival order, so `id <` is that invariant.
    others = db.execute("""
        SELECT id, subject, description, lat, lng
        FROM reports
        WHERE id < ? AND status NOT IN ('resolved', 'hidden')
              AND auto_filed_for IS NULL
        ORDER BY id
    """, (report_id,)).fetchall()

    # Distance is a veto, not a vote. Two reports have to read alike first;
    # being nearby cannot make unrelated wording into a duplicate, but being
    # three suburbs apart is enough to say two similar sentences are two
    # different incidents.
    near = []
    for row in others:
        away = metres_between(mine["lat"], mine["lng"], row["lat"], row["lng"])
        if away is None or away <= DUPLICATE_RADIUS_M:
            near.append({"id": row["id"], "subject": row["subject"],
                         "description": row["description"]})

    text = f"{mine['subject']} {mine['description']}"
    matches = classify.duplicates(text, near, limit=1)
    if not matches:
        return None

    best = matches[0]
    db.execute("UPDATE reports SET dupe_of = ?, dupe_score = ? WHERE id = ?",
               (best["id"], best["score"], report_id))
    db.commit()
    return best


def claim_existing_report(client_id: str | None, sender: int) -> dict:
    """Whose report is this id, now that the INSERT has lost the race?

    Called only from the IntegrityError path. Two outcomes and they are very
    different: our own retry, which is a success, or an id that genuinely
    belongs to another account, which is a 409. Guessing wrong in the first
    direction throws a report away.
    """
    row = get_db().execute("""
        SELECT id, sender, created_at, received_at FROM reports
        WHERE client_id = ?
    """, (client_id,)).fetchone()

    if row is None or row["sender"] != sender:
        return {"ok": False, "error": "that report id belongs to someone else"}

    return {"ok": True, "duplicate": True, "id": row["id"],
            "created_at": row["created_at"],
            "received_at": row["received_at"],
            "synced_late": late_sync(row["created_at"], row["received_at"])}


def create_report(*, subject: str, description: str, priority: str,
                  lat: float, lng: float, sender: int,
                  written_at: datetime, client_id: str | None) -> dict:
    """Write a report, once, and say what we made of it.

    Both ways in end up here — the form on the page and the offline queue —
    so the two cannot drift apart about what filing a report means.

    `client_id` is what makes sending twice safe. It is generated in the
    browser and written to disk *before* the first attempt, so it survives the
    phone dying mid-send: the retry after a restart carries the same id, and
    this finds it and hands back the report it already wrote. Without that, a
    connection flickering at the wrong moment files a second incident, and a
    second incident is the convergence failure with extra steps.

    The check is here, server-side, before the INSERT — not a client-side
    guard, which a restart erases, and not a UNIQUE constraint alone, which
    tells you about the collision only after you have already tried to create
    it.
    """
    db = get_db()

    if client_id:
        seen = db.execute("""
            SELECT id, created_at, received_at FROM reports
            WHERE client_id = ? AND sender = ?
        """, (client_id, sender)).fetchone()
        if seen is not None:
            return {"ok": True, "duplicate": True, "id": seen["id"],
                    "created_at": seen["created_at"],
                    "received_at": seen["received_at"],
                    "synced_late": late_sync(seen["created_at"],
                                             seen["received_at"])}

    received = datetime.now(timezone.utc)
    try:
        cur = db.execute("""
            INSERT INTO reports
                (subject, description, priority, lat, lng,
                 status, sender, client_id, created_at, received_at)
            VALUES (?, ?, ?, ?, ?, 'unassigned', ?, ?, ?, ?)
        """, (subject, description, priority, lat, lng, sender,
              client_id or None,
              written_at.isoformat(timespec="seconds"),
              received.isoformat(timespec="seconds")))
    except sqlite3.IntegrityError:
        # The lookup above and this INSERT are two statements, so two retries
        # of the *same* report can both pass the check and one of them lands
        # here. Assuming that means somebody else's id was the bug: the loser
        # got a 409, the outbox reads any 4xx as "the server looked at this
        # and said no forever", and dropped the report. A flapping connection
        # would have deleted somebody's call for help and told them the wrong
        # reason for it.
        #
        # So look again before accusing anyone. If the row that beat us is
        # ours, the id did exactly its job.
        db.rollback()
        return claim_existing_report(client_id, sender)
    db.commit()

    report_id = cur.lastrowid
    return {
        "ok": True,
        "duplicate": False,
        "id": report_id,
        "created_at": written_at.isoformat(timespec="seconds"),
        "received_at": received.isoformat(timespec="seconds"),
        "synced_late": (received - written_at).total_seconds() > LATE_SYNC_SECONDS,
        # Checked now, against everything open including whatever else just
        # arrived. See link_duplicate.
        "possible_duplicate": link_duplicate(report_id),
    }


def report_fields(source) -> tuple[dict, str | None]:
    """Pull a report out of a form or a JSON body, and say what's wrong."""
    fields = {
        "subject": (source.get("subject") or "").strip(),
        "description": (source.get("description") or "").strip(),
        "priority": (source.get("priority") or "").strip().upper(),
        "lat": to_float(source.get("lat")),
        "lng": to_float(source.get("lng")),
    }

    if not fields["subject"]:
        return fields, "Subject is required"
    if fields["priority"] not in PRIORITIES:
        return fields, "Priority must be HIGH, MEDIUM or LOW"
    if fields["lat"] is None or fields["lng"] is None:
        # The hidden lat/lng inputs carry `required`, but hidden inputs are
        # exempt from browser validation, so an untouched map still submits.
        return fields, "Click the map to set a location"
    # A coordinate off the globe is stored happily by SQLite and served
    # happily by the API, and then Leaflet projects it somewhere off the
    # canvas — so the report exists, counts toward the totals, and is the one
    # thing that never appears on the map. The feed and the map disagree and
    # nothing anywhere says why.
    if not (-90 <= fields["lat"] <= 90) or not (-180 <= fields["lng"] <= 180):
        return fields, "That location is not on Earth. Pick it again."
    return fields, None


def to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


@app.route("/report/new", methods=["GET", "POST"])
@login_required
def report_new():
    if request.method == "POST":
        fields, problem = report_fields(request.form)
        if problem:
            flash(problem)
            return render_template("report_make.html",
                                   client_id=new_client_id(),
                                   form=request.form), 400

        # The form carries an id too, rendered into the page. Without
        # JavaScript there is no queue and nothing to retry, but a browser
        # back-button and a second Submit is the same double-file with a
        # person driving it, and this catches that as well.
        written_at, when_problem = claimed_time(
            (request.form.get("written_at") or "").strip())
        if when_problem:
            flash(when_problem)
            return render_template("report_make.html",
                                   client_id=new_client_id(),
                                   form=request.form), 400

        result = create_report(
            **fields, sender=current_user()["id"], written_at=written_at,
            client_id=(request.form.get("client_id") or "").strip()[:64] or None)

        if not result["ok"]:
            flash(result["error"])
            return render_template("report_make.html",
                                   client_id=new_client_id(),
                                   form=request.form), 409

        return redirect(url_for("report_detail", report_id=result["id"]))

    return render_template("report_make.html", client_id=new_client_id())


def new_client_id() -> str:
    """A fresh id for a form that has not been filled in yet."""
    return f"srv-{uuid.uuid4()}"


@app.post("/api/reports")
@login_required
def api_report_create():
    """File a report, from the queue or from anything else that speaks JSON.

    Same code as the form, so the offline path cannot quietly mean something
    different from the online one. What it adds is the two things a queued
    report needs and a live one doesn't: an id that makes resending free, and
    a `written_at` so the feed knows this describes forty minutes ago.
    """
    payload = request.get_json(silent=True) or {}
    fields, problem = report_fields(payload)
    if problem:
        return jsonify({"error": problem}), 400

    written_at, when_problem = claimed_time(str(payload.get("written_at") or ""))
    if when_problem:
        return jsonify({"error": when_problem}), 400

    client_id = str(payload.get("client_id") or "").strip()[:64] or None
    result = create_report(**fields, sender=current_user()["id"],
                           written_at=written_at, client_id=client_id)
    if not result["ok"]:
        return jsonify(result), 409

    result["url"] = url_for("report_detail", report_id=result["id"])
    # 200 for one we already had, 201 for one we wrote. The queue treats both
    # as done — that is the point of the id.
    return jsonify(result), 200 if result["duplicate"] else 201


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
# so a coordinator can see someone was out of contact. Reports use the same
# figure: one that was written a while before it arrived is described as such
# rather than allowed to look like it just came in.
LATE_SYNC_SECONDS = 60

# How far apart two reports can be and still be the same incident.
#
# Chosen, not measured — say so plainly. Two neighbours on one street are tens
# of metres apart; a flood on a road of the same name three suburbs over is a
# different incident with the same vocabulary, and text alone cannot tell them
# apart. 500 m is wide enough for a street and its junctions and narrow enough
# that "Kingsland" in two different places does not collapse into one row.
#
# It only ever *suppresses* a link. A pair that is close but reads differently
# is still two reports, because the text test has to pass first.
DUPLICATE_RADIUS_M = 500

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
                 status, sender, auto_filed_for, created_at, received_at)
            VALUES (?, ?, 'HIGH', ?, ?, 'unassigned', ?, ?, ?, ?)
        """, (
            f"No contact from {row['username']} for {silent} minutes",
            f"Filed automatically. {row['username']} was working "
            f"\"{row['report_subject']}\" and has not checked in since their "
            f"deadline passed. Pin is their {where}. Nobody has confirmed "
            f"they are alright — this needs a person, not a refresh.",
            lat, lng, row["responder"], row["responder"], now_iso(), now_iso(),
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


# Content Security Policy. Everything comes from us, except Leaflet's script
# and CSS and the OpenStreetMap tiles, which are named explicitly rather than
# allowed by a wildcard.
#
# No 'unsafe-eval'. 'unsafe-inline' is here for styles only, because Leaflet
# sets inline styles on every tile it positions and there is no way to run it
# without that. Scripts do not get it, which is the half that stops injected
# markup from executing.
#
# Both spellings of the tile host are listed. OpenStreetMap is retiring the
# a/b/c subdomains, and a redirect from `a.tile.` to the bare `tile.` is
# re-checked against the policy — so naming only the wildcard would fail the
# day they switch it on, silently, and only for tiles that redirect.
CONTENT_SECURITY_POLICY = "; ".join([
    "default-src 'self'",
    "script-src 'self' https://unpkg.com",
    "style-src 'self' 'unsafe-inline' https://unpkg.com",
    "img-src 'self' data: "
        "https://tile.openstreetmap.org https://*.tile.openstreetmap.org",
    "connect-src 'self'",
    "font-src 'self'",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
])


# The service worker gets its own policy, and it has to.
#
# A worker inherits its CSP from the headers on its own script, and every
# fetch() a worker makes is checked against `connect-src` — not `img-src`,
# even when the thing it is fetching is an image the page was allowed to load
# directly. Serving sw.js with the page policy above therefore forbade the
# worker from fetching tiles at all.
#
# The failure was invisible on first paint: until the worker claims the page,
# tiles are fetched by the page itself and img-src lets them through. Panning
# afterwards routed every new tile through the worker, where the fetch threw
# and the handler turned it into a 504, so the map went grey in the middle of
# somebody using it.
#
# Narrower than the page policy, not wider: a worker that only fetches tiles
# should be allowed to fetch tiles and nothing else.
WORKER_CONTENT_SECURITY_POLICY = "; ".join([
    "default-src 'none'",
    "script-src 'self'",
    "connect-src 'self' "
        "https://tile.openstreetmap.org https://*.tile.openstreetmap.org",
])


@app.after_request
def security_headers(response):
    """Headers that cost nothing and close whole categories of attack.

    Absence of these is the first thing an automated scanner reports, and
    every one of them is a single line that turns a class of bug into a
    non-issue.
    """
    response.headers.setdefault("Content-Security-Policy",
                                CONTENT_SECURITY_POLICY)

    # Stop the browser guessing that a .txt is really a script.
    response.headers.setdefault("X-Content-Type-Options", "nosniff")

    # Nobody has any business framing this. frame-ancestors in the CSP says
    # the same thing to modern browsers; this is for the older ones.
    response.headers.setdefault("X-Frame-Options", "DENY")

    # Reports name real addresses. Don't leak the URL of the page somebody
    # was looking at to whatever they click through to.
    response.headers.setdefault("Referrer-Policy",
                                "strict-origin-when-cross-origin")

    # We ask for location. Nothing else, and nothing at all from a frame.
    response.headers.setdefault(
        "Permissions-Policy",
        "geolocation=(self), camera=(), microphone=(), payment=()")

    # Only meaningful over HTTPS, and only set there — sending it from
    # localhost would pin a developer's browser to https://127.0.0.1.
    if os.environ.get("DIRESQ_HTTPS_ONLY") == "1":
        response.headers.setdefault(
            "Strict-Transport-Security", "max-age=31536000; includeSubDomains")

    return response


@app.before_request
def escalate_silence():
    if (request.method == "GET"
            and request.endpoint in SWEEP_ON
            and current_user() is not None):
        sweep_silent_responders()


def claimed_time(raw: str) -> tuple[datetime, str | None]:
    """When something says it happened. Empty means now.

    Used by check-ins and by reports, because both can sit in a queue and both
    lie about their age if you stamp them on arrival. A check-in stamped on
    arrival silently cancels an overdue alarm; a report stamped on arrival
    reads as a house that needs help right now when it may have been cleared
    half an hour ago.

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
        # 'self', because you decided. Nothing to announce.
        db.execute("UPDATE assignments SET status = ?, staffing_vote = NULL, "
                   "status_changed_at = ?, cleared_reason = 'self' "
                   "WHERE id = ?",
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

    # Everyone still attached is done here — and, unlike somebody clearing
    # themselves, they did not decide that. Mark why, so the app can tell
    # them. Before this, a person driving to an address that had just been
    # cleared was cleared off it silently and found out by refreshing a page
    # they were not looking at. Sending people where they are not needed is
    # the failure this project exists to prevent; it was doing it to its own
    # responders.
    #
    # The person pressing the button is excluded: they are standing there,
    # they made the decision, and telling them to stand down would be absurd.
    db.execute("""
        UPDATE assignments SET status = 'cleared', staffing_vote = NULL,
                               status_changed_at = ?,
                               cleared_reason = CASE WHEN responder = ?
                                                     THEN 'self' ELSE 'resolved' END
        WHERE report_id = ? AND status != 'cleared'
    """, (now_iso(), user["id"], report_id))
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


# No login wall. Someone should be able to read what this is and isn't before
# they hand it any information, and a person who has just found the app in a
# real emergency should reach "call 911" without making an account first.
@app.get("/disclaimer")
def disclaimer_page():
    return render_template("disclaimer.html")


@app.post("/api/suggest")
@login_required
def api_suggest():
    """Read a description and suggest how bad it is, and what's needed.

    A suggestion, never a decision — nothing here writes to a report. It comes
    back with the words that caused it, because a coordinator deciding where
    to send a boat is owed a reason and not a number.

    Also flags reports that look like the same incident. Duplicates are how
    six people end up at one address while a street nearby has nobody.

    This is the courteous early warning, not the safety net. It only runs
    while somebody is online and typing. The check that actually has to hold
    runs in `link_duplicate` when the report is written, because the reports
    most likely to duplicate each other are the ones filed offline by
    neighbours who could not see each other's.
    """
    text = form_or_json("text")
    result = classify.suggest(text).as_dict()

    # Only compare against things somebody could still go to.
    open_reports = [
        {"id": r["id"], "subject": r["subject"], "description": r["description"]}
        for r in fetch_reports()
    ]
    result["duplicates"] = classify.duplicates(text, open_reports)
    return jsonify(result)


@app.get("/api/model/priority.json")
def api_model_export():
    """The trained model, for a browser that has to classify without us.

    Served from the app as well as from `static/model/priority.json` so the
    committed artifact can be checked against a live one. The static copy is
    what the service worker keeps; this is what tells you the static copy is
    stale.
    """
    return jsonify(classify.export_model())


@app.get("/api/model")
def api_model():
    """What the classifier is, including what it's bad at."""
    return jsonify(classify.model_card())


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


@app.get("/api/incidents")
@login_required
def api_incidents():
    """The feed, with duplicates of one incident collapsed into one row.

    Separate from `/api/reports` rather than replacing it. The map wants every
    report, because two people reporting the same flood from opposite ends of
    a street pinned two real places and dropping one would be inventing
    certainty we don't have. The feed wants the incident, because that is what
    somebody decides where to drive from.
    """
    incidents = group_incidents(fetch_reports())
    # The nested report rows are only needed by the page that renders them.
    return jsonify([{k: v for k, v in i.items() if k != "reports"}
                    | {"report_ids": [r["id"] for r in i["reports"]]}
                    for i in incidents])


@app.get("/api/reports")
def api_reports():
    return jsonify(fetch_reports())


@app.get("/api/responders")
@login_required
def api_responders():
    return jsonify(fetch_responders())


@app.get("/api/me")
@login_required
def api_me():
    """Your own commitments, and nothing else.

    This exists so the app has something honest to show with no network.

    The service worker is not allowed to cache the feed — a saved list of who
    needs help is a claim about the world that stops being true the moment it
    is written, and showing somebody a stale one in a disaster is worse than
    showing them nothing. The board has the same problem.

    Your own state does not have that problem. Which report you committed to,
    when you said you would check in, and where you last were are facts about
    you, and they stay true whether or not you can reach a server. So this is
    the one thing worth keeping on the device.
    """
    me = current_user()
    row = get_db().execute("""
        SELECT asg.id, asg.status, asg.joined_at, asg.eta,
               r.id AS report_id, r.subject, r.priority, r.lat, r.lng
          FROM assignments asg
          JOIN reports r ON r.id = asg.report_id
         WHERE asg.responder = ? AND asg.status != 'cleared'
           AND r.status NOT IN ('resolved', 'hidden')
         ORDER BY asg.joined_at DESC LIMIT 1
    """, (me["id"],)).fetchone()

    seen = get_db().execute(
        "SELECT lat, lng, created_at FROM checkins "
        "WHERE responder = ? ORDER BY created_at DESC LIMIT 1",
        (me["id"],)).fetchone()

    assignment = None
    if row is not None:
        due = deadline_for(row["joined_at"], row["eta"],
                           seen["created_at"] if seen else None)
        assignment = {
            "id": row["id"],
            "status": row["status"],
            "report_id": row["report_id"],
            "subject": row["subject"],
            "priority": row["priority"],
            "joined_at": row["joined_at"],
            "check_in_by": due.isoformat(timespec="seconds") if due else None,
        }

    return jsonify({
        "username": me["username"],
        "capabilities": [c for c in (me["capabilities"] or "").split(",") if c],
        "assignment": assignment,
        # A job you were on your way to that somebody has since closed.
        #
        # This belongs here, in the one response the service worker is allowed
        # to keep, precisely because of what it is: a fact about *you* and a
        # commitment that has ended. Unlike the feed it does not rot — a
        # report that was resolved stays resolved — so a cached copy is still
        # true with no signal. It is the only thing on the offline page that
        # can tell somebody to turn the car around.
        "stand_down": stand_down_for(me["id"]),
        "last_position": None if seen is None else {
            "lat": seen["lat"], "lng": seen["lng"], "at": seen["created_at"],
        },
        # When the server answered. The offline page shows this so nobody
        # mistakes a cached copy for a live one.
        "as_of": now_iso(),
    })


def stand_down_for(account_id: int) -> dict | None:
    """A report this person was going to that somebody else has closed.

    Returns None once they have acknowledged it, and None if they cleared
    themselves — that was their own decision and needs no announcement.

    Deliberately not time-limited. A notice that expires on its own is a
    notice missed by exactly the person it was written for: somebody driving,
    with the phone in their pocket, who will look at it in twenty minutes.
    """
    row = get_db().execute("""
        SELECT asg.id, asg.status_changed_at,
               r.id AS report_id, r.subject, r.lat, r.lng
          FROM assignments asg
          JOIN reports r ON r.id = asg.report_id
         WHERE asg.responder = ?
           AND asg.cleared_reason = 'resolved'
           AND asg.stand_down_seen_at IS NULL
         ORDER BY asg.status_changed_at DESC LIMIT 1
    """, (account_id,)).fetchone()
    if row is None:
        return None

    closed = parse_iso(row["status_changed_at"])
    return {
        "assignment_id": row["id"],
        "report_id": row["report_id"],
        "subject": row["subject"],
        "at": row["status_changed_at"],
        "minutes_ago": None if closed is None else max(
            0, int((datetime.now(timezone.utc) - closed).total_seconds() // 60)),
    }


@app.context_processor
def inject_stand_down():
    # A callable, so pages that never render the banner don't pay for the
    # query. Same shape as overdue_count().
    def stand_down():
        user = current_user()
        return None if user is None else stand_down_for(user["id"])
    return {"stand_down": stand_down}


@app.post("/api/standdown/<int:assignment_id>/ack")
@login_required
def api_stand_down_ack(assignment_id: int):
    """"I've seen it." Stops the notice, and only for the person it is about."""
    db = get_db()
    row = db.execute("SELECT responder FROM assignments WHERE id = ?",
                     (assignment_id,)).fetchone()
    if row is None:
        return answer({"error": "no such assignment"}, 404, "No such assignment")
    if row["responder"] != current_user()["id"]:
        return answer({"error": "not your assignment"}, 403,
                      "That is not yours to dismiss")

    db.execute("UPDATE assignments SET stand_down_seen_at = ? WHERE id = ?",
               (now_iso(), assignment_id))
    db.commit()
    return answer({"ok": True, "id": assignment_id}, 200, "")


@app.get("/offline")
def offline_page():
    """Shown when a navigation fails because there is no network.

    Served normally too, so it can be cached ahead of time — a page you can
    only reach when offline is a page the browser has never been able to
    store.
    """
    return render_template("offline.html")


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
        # Same race as create_report, same fix: the lookup above and this
        # INSERT are two statements, so our own retry can land here. Look
        # again before calling it somebody else's — the queue drops anything
        # the server answers 4xx to, and a check-in is the message that says
        # you are alive.
        db.rollback()
        seen = db.execute("""
            SELECT responder, created_at, received_at FROM checkins
            WHERE client_id = ?
        """, (client_id,)).fetchone()
        if seen is None or seen["responder"] != responder_id:
            return {"ok": False,
                    "error": "that check-in id belongs to someone else"}
        return {
            "ok": True,
            "duplicate": True,
            "at": seen["created_at"],
            "received_at": seen["received_at"],
            "synced_late": late_sync(seen["created_at"], seen["received_at"]),
        }
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

    db = get_db()
    who = db.execute(
        "SELECT id, node_key, last_uplink FROM accounts WHERE id = ?",
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

    # A valid signature proves the packet was written by somebody with the
    # key. It does not prove it was written *now* — a recording of one is
    # byte-identical. The counter is what makes it fresh: strictly greater
    # than anything already accepted, or it has been seen before.
    if checkin.counter <= who["last_uplink"]:
        return jsonify({
            "error": "replayed or out-of-order packet",
            "counter": checkin.counter,
            "last_accepted": who["last_uplink"],
        }), 409

    # Recorded before the check-in is written, so a crash between the two
    # loses a check-in rather than reopening the window.
    db.execute("UPDATE accounts SET last_uplink = ? WHERE id = ?",
               (checkin.counter, who["id"]))
    db.commit()

    # The packet carries an age, not a timestamp — a node running off a
    # battery in a flood is the last clock you want to trust.
    happened_at = (datetime.now(timezone.utc)
                   - timedelta(minutes=checkin.age_minutes))

    result = record_checkin(checkin.responder_id, checkin.lat, checkin.lng,
                            happened_at)
    result["responder_id"] = checkin.responder_id
    result["counter"] = checkin.counter
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
    # Two responders deliberately left unassigned. A board where everybody is
    # busy has nothing to say when a report needs a boat, and a real one
    # always has somebody between jobs.
    ("r.castillo", "responder", "boat,swiftwater,medical"),
    ("t.oyelaran", "responder", "chainsaw,truck,generator"),
    # Two more with boats, who went to the *second* report of the flood on
    # Katy Fort Bend Rd without knowing somebody was already inside it. They
    # exist to make the duplicate cost something. See SEED_REPORTS.
    ("p.adeyemi", "responder", "boat,medical"),
    ("h.lindqvist", "responder", "boat,swiftwater"),
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

    # The same flood as the first report, filed by the neighbour across the
    # street, fifty metres away. She had no signal, so she wrote it forty
    # minutes ago and it only reached us now — the eighth number is when it
    # arrived, as opposed to when it was written.
    #
    # Two reports, one house. Ungrouped, that reads as two jobs: one with a
    # person inside asking for help, and one with nobody going that the
    # coverage-gap banner would count as an uncovered street. Two more people
    # with boats set off for the second one without knowing anybody was
    # already there.
    #
    # Nothing here writes `dupe_of`. The seed runs the same arrival-time
    # detector the app runs, so if that ever stops working the demo stops
    # showing the grouped card rather than quietly faking it.
    ("Water over the porch on Katy Fort Bend, two upstairs",
     "Across the street from us. Water is over the porch and into the house, "
     "and there are two adults who have gone up to the second floor. No boat "
     "on this street that I can see. Wrote this when it started and could not "
     "send it.",
     "HIGH", 29.7861, -95.8240, "kiyan", 40, 0),
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

    # The duplicate of the flood. Two people with boats on their way to a
    # house londo has been standing in for over an hour, because to them it
    # was a different report with nobody on it. This is the convergence the
    # whole project is about, and until the feed grouped the two reports it
    # was invisible in our own data.
    (8, "p.adeyemi",    "en_route", None,      9,  20, None),
    (8, "h.lindqvist",  "en_route", None,      6,  15, None),
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
                     status, sender, created_at, received_at)
                VALUES (?, ?, ?, ?, ?, 'unassigned', ?, ?, ?)
            """, (subject, desc, priority, lat, lng, sender,
                  now_iso(), now_iso()))

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
        for subject, desc, priority, lat, lng, filed_by, minutes, *late \
                in SEED_REPORTS:
            # Most reports reached us when they were written. One didn't —
            # an eighth number says how long ago it actually arrived.
            arrived = late[0] if late else minutes
            cur = db.execute("""
                INSERT INTO reports
                    (subject, description, priority, lat, lng,
                     status, sender, created_at, received_at)
                VALUES (?, ?, ?, ?, ?, 'unassigned', ?, ?, ?)
            """, (subject, desc, priority, lat, lng, who[filed_by],
                  ago(minutes), ago(arrived)))
            report_ids.append(cur.lastrowid)

        db.commit()

        # Run the real duplicate check, in arrival order, exactly as the app
        # does when a queued report lands. Writing `dupe_of` by hand here
        # would let the demo show a grouped card the software could not
        # actually produce, which is the one thing a demo must never do.
        for report_id in sorted(report_ids,
                                key=lambda rid: db.execute(
                                    "SELECT received_at FROM reports WHERE id = ?",
                                    (rid,)).fetchone()["received_at"]):
            link_duplicate(report_id)

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


# Where the browser's copy of the trained model lives. Committed, because a
# phone with no signal cannot run a build step, and because the service worker
# has to be able to name it in SHELL_FILES.
MODEL_FILE = Path(__file__).with_name("static") / "model" / "priority.json"


@app.cli.command("export-model")
def export_model_command() -> None:
    """Write the trained classifier out for the browser to use offline.

    The corpus lives in classify.py and stays there. This only ships the
    counts it produced, so there is one place to edit a training example and
    one command to run afterwards. A test fails if the committed file has
    drifted from what classify.py would generate today, which is the part that
    stops "regenerate the model" from becoming a step people forget.
    """
    MODEL_FILE.parent.mkdir(parents=True, exist_ok=True)
    MODEL_FILE.write_text(
        json.dumps(classify.export_model(), indent=1, sort_keys=True) + "\n",
        encoding="utf-8")
    size = MODEL_FILE.stat().st_size
    print(f"wrote {MODEL_FILE.relative_to(Path(__file__).parent)} "
          f"({size // 1024} KB)")


if __name__ == "__main__":
    app.run(debug=True)
