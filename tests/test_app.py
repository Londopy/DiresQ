"""Smoke tests for the routes plus unit tests for the two rules that matter.

    pip install -r requirements-dev.txt
    pytest -q

Each test gets its own throwaway database, so order never matters and a
failing test can't poison the next one.
"""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app as diresq  # noqa: E402


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(diresq, "DATABASE", str(tmp_path / "test.db"))
    # Skip the login redirect; TestLogin covers auth separately.
    monkeypatch.setenv("DIRESQ_DEV_USER", "londo")
    diresq.init_db()
    with diresq.app.app_context():
        diresq.seed_data()
    return diresq.app.test_client()


@pytest.fixture
def anon(tmp_path, monkeypatch):
    monkeypatch.setattr(diresq, "DATABASE", str(tmp_path / "test.db"))
    monkeypatch.delenv("DIRESQ_DEV_USER", raising=False)
    diresq.init_db()
    with diresq.app.app_context():
        diresq.seed_data()
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
