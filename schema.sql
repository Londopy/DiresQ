-- DiresQ schema. Four tables: accounts, reports, assignments, checkins.
--
-- reports has no staffing column on purpose. Staffing is derived from the
-- votes of whoever is currently on scene, in app.py.

PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS checkins;
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
    sender      INTEGER NOT NULL REFERENCES accounts(id),
    created_at  TEXT    NOT NULL
);

CREATE INDEX idx_reports_status ON reports(status);


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
    joined_at      TEXT    NOT NULL,

    -- This constraint is what makes a double-join a 409.
    UNIQUE (report_id, responder)
);

CREATE INDEX idx_assignments_report ON assignments(report_id);
CREATE INDEX idx_assignments_responder ON assignments(responder);


CREATE TABLE checkins (
    id         INTEGER PRIMARY KEY,
    responder  INTEGER NOT NULL REFERENCES accounts(id),
    lat        REAL,
    lng        REAL,
    created_at TEXT    NOT NULL
);

CREATE INDEX idx_checkins_responder ON checkins(responder, created_at DESC);
