-- DiresQ schema. Four tables: accounts, reports, assignments, checkins.
--
-- reports has no staffing column on purpose. Staffing is derived from the
-- votes of whoever is currently on scene, in app.py.

PRAGMA foreign_keys = ON;

-- Children first, parents last. Every table below must appear here, or
-- init-db half-runs and leaves the database in pieces.
DROP TABLE IF EXISTS checkins;
DROP TABLE IF EXISTS report_flags;
DROP TABLE IF EXISTS assignments;
DROP TABLE IF EXISTS reports;
DROP TABLE IF EXISTS accounts;


CREATE TABLE accounts (
    id              INTEGER PRIMARY KEY,
    username        TEXT    NOT NULL UNIQUE,
    hashed_password TEXT    NOT NULL,
    role            TEXT    NOT NULL
                            CHECK (role IN ('responder', 'reporter')),
    -- comma list: boat,truck,chainsaw,medical,generator
    capabilities    TEXT    NOT NULL DEFAULT '',
    created_at      TEXT    NOT NULL
);


CREATE TABLE reports (
    id          INTEGER PRIMARY KEY,
    subject     TEXT    NOT NULL,
    description TEXT    NOT NULL DEFAULT '',
    priority    TEXT    NOT NULL
                        CHECK (priority IN ('HIGH', 'MEDIUM', 'LOW')),
    lat         REAL    NOT NULL,
    lng         REAL    NOT NULL,
    status      TEXT    NOT NULL DEFAULT 'unassigned'
                        CHECK (status IN ('unassigned', 'active',
                                          'resolved', 'hidden')),
    needed      INTEGER,
    -- Community flags. At FLAG_THRESHOLD the report drops out of the feed,
    -- but stays visible to whoever filed it and anyone already on it.
    flags       INTEGER NOT NULL DEFAULT 0,
    sender      INTEGER NOT NULL REFERENCES accounts(id),
    -- Set when the server filed this itself because a responder went silent.
    -- Also what stops it filing a second one: an open report pointing at the
    -- same person means the alarm has already been raised.
    auto_filed_for INTEGER REFERENCES accounts(id),
    created_at  TEXT    NOT NULL
);

-- One flag per person per report.
CREATE TABLE report_flags (
    report_id  INTEGER NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
    account_id INTEGER NOT NULL REFERENCES accounts(id),
    created_at TEXT    NOT NULL,
    PRIMARY KEY (report_id, account_id)
);

CREATE INDEX idx_reports_status ON reports(status);
CREATE INDEX idx_reports_auto_filed ON reports(auto_filed_for);


-- Many responders to one report. No claim lock, by design.
CREATE TABLE assignments (
    id             INTEGER PRIMARY KEY,
    report_id      INTEGER NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
    responder      INTEGER NOT NULL REFERENCES accounts(id),

    status         TEXT    NOT NULL DEFAULT 'en_route'
                           CHECK (status IN ('en_route', 'on_scene', 'cleared')),

    -- Only counted while status = 'on_scene'.
    staffing_vote  TEXT    CHECK (staffing_vote IN ('need_more', 'adequate',
                                                    'overstaffed', 'stood_down')),

    eta            TEXT,   -- ISO8601
    eta_confidence REAL,   -- 0..1

    -- Set when someone marks themselves on scene but their last check-in is
    -- a long way from the report. Detection, not prevention.
    position_mismatch INTEGER NOT NULL DEFAULT 0,
    joined_at      TEXT    NOT NULL,

    -- When status last moved. Only the most recent one, so the activity log
    -- can say when someone arrived but not replay every step they took.
    status_changed_at TEXT,

    -- This constraint is what makes a double-join a 409.
    UNIQUE (report_id, responder)
);

CREATE INDEX idx_assignments_report ON assignments(report_id);
CREATE INDEX idx_assignments_responder ON assignments(responder);


CREATE TABLE checkins (
    id          INTEGER PRIMARY KEY,
    responder   INTEGER NOT NULL REFERENCES accounts(id),
    lat         REAL,
    lng         REAL,

    -- When the responder says they were there. For a check-in queued offline
    -- this is the time it was made, not the time it reached us. The overdue
    -- timer runs off this, so a late sync can't silently clear a red row.
    created_at  TEXT    NOT NULL,

    -- When the server actually got it. Ours, not the client's. The gap
    -- between the two is what tells a coordinator someone was out of contact.
    received_at TEXT    NOT NULL
);

CREATE INDEX idx_checkins_responder ON checkins(responder, created_at DESC);
