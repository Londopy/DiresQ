-- DiresQ schema
-- Katy Youth Hacks 2026
--
-- Four tables: accounts, reports, assignments, checkins.
--
-- Two deliberate deviations from docs/project-doc.md:
--
--   1. reports.staffing does NOT exist as a column. Staffing is COMPUTED from
--      assignments.staffing_vote, taking the most conservative vote from anyone
--      currently on_scene (need_more > adequate > overstaffed > stood_down).
--      See "Limits We're Fixing #1". Building it this way now is free;
--      migrating to it later is not.
--
--   2. reports.priority is TEXT ('HIGH'|'MEDIUM'|'LOW'), not INTEGER 1..4,
--      to match the filter checkboxes in templates/homepage.html, the counters
--      in static/scripts/map.js, and the .priority.high/.medium/.low CSS.
--      NOTE: never ORDER BY priority directly -- alphabetically HIGH < LOW <
--      MEDIUM, which is wrong. Use the CASE rank in app.py (PRIORITY_RANK).

PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS checkins;
DROP TABLE IF EXISTS assignments;
DROP TABLE IF EXISTS reports;
DROP TABLE IF EXISTS accounts;


-- ---------------------------------------------------------------- accounts --
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


-- ----------------------------------------------------------------- reports --
CREATE TABLE reports (
    id          INTEGER PRIMARY KEY,
    subject     TEXT    NOT NULL,
    description TEXT    NOT NULL DEFAULT '',
    priority    TEXT    NOT NULL
                        CHECK (priority IN ('HIGH', 'MEDIUM', 'LOW')),

    -- Required for the map page. Nullable at the DB level only because
    -- templates/report_make.html has no location input yet -- once Skythe
    -- adds the map pin, tighten this to NOT NULL.
    lat         REAL,
    lng         REAL,

    status      TEXT    NOT NULL DEFAULT 'unassigned'
                        CHECK (status IN ('unassigned', 'active',
                                          'resolved', 'hidden')),
    needed      INTEGER,
    sender      INTEGER NOT NULL REFERENCES accounts(id),
    created_at  TEXT    NOT NULL
);

CREATE INDEX idx_reports_status ON reports(status);


-- ------------------------------------------------------------- assignments --
-- many responders : one report. This is the whole thesis -- no claim lock.
CREATE TABLE assignments (
    id             INTEGER PRIMARY KEY,
    report_id      INTEGER NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
    responder      INTEGER NOT NULL REFERENCES accounts(id),

    status         TEXT    NOT NULL DEFAULT 'en_route'
                           CHECK (status IN ('en_route', 'on_scene', 'cleared')),

    -- Only meaningful while status = 'on_scene'. People who are physically
    -- there are the only ones who know.
    staffing_vote  TEXT    CHECK (staffing_vote IN ('need_more', 'adequate',
                                                    'overstaffed', 'stood_down')),

    eta            TEXT,   -- ISO8601, parsed from free text via timefuzz
    eta_confidence REAL,   -- 0..1
    joined_at      TEXT    NOT NULL,

    -- no double-join. This constraint IS the 409.
    UNIQUE (report_id, responder)
);

CREATE INDEX idx_assignments_report ON assignments(report_id);
CREATE INDEX idx_assignments_responder ON assignments(responder);


-- ---------------------------------------------------------------- checkins --
-- Overdue is computed on read, never stored. No background job.
CREATE TABLE checkins (
    id         INTEGER PRIMARY KEY,
    responder  INTEGER NOT NULL REFERENCES accounts(id),
    lat        REAL,
    lng        REAL,
    created_at TEXT    NOT NULL
);

CREATE INDEX idx_checkins_responder ON checkins(responder, created_at DESC);
