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
