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
    -- Shared secret for this person's radio node, hex. Signs uplink packets.
    -- Null until they have one, and an unsigned packet is refused, so the
    -- absence of a key fails closed.
    node_key        TEXT,
    -- Highest packet counter accepted from this node. Anything not strictly
    -- greater is a replay: somebody recorded a valid packet off the air and
    -- sent it again. Starts at zero, and the first real packet is 1.
    last_uplink     INTEGER NOT NULL DEFAULT 0,
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

    -- Made by the browser before the report is sent, and written to disk
    -- before the first attempt, so it is the same id after a browser restart.
    --
    -- A check-in sent twice is harmless. A report sent twice is a second
    -- incident, and a second incident is six people at one address while the
    -- next street has nobody — the exact failure this project exists to
    -- prevent. So this is UNIQUE, and checked before the row is written
    -- rather than after.
    --
    -- Null for anything that never went through the queue.
    client_id   TEXT    UNIQUE,

    -- When it was WRITTEN. For a report filed offline this is the moment
    -- somebody typed it, not the moment their phone found signal. A report
    -- written forty minutes ago describes a house that may already be
    -- cleared, and the feed has to be able to say so.
    created_at  TEXT    NOT NULL,

    -- When the server actually got it. Ours, not the client's. The gap
    -- between the two is the staleness, and it is shown rather than hidden.
    received_at TEXT    NOT NULL,

    -- Another open report that looks like the same incident, and how alike.
    -- A link, never a merge: the TF-IDF check is good enough to be worth
    -- showing and nowhere near good enough to delete somebody's call for
    -- help on. Set on arrival, so a report that synced from a queue is
    -- checked against everything that arrived alongside it.
    -- SET NULL rather than the default: if the report being pointed at ever
    -- goes away, what remains is a report with no twin, not a broken row. It
    -- also means DROP TABLE during a schema rebuild doesn't trip over the
    -- table's reference to itself.
    dupe_of     INTEGER REFERENCES reports(id) ON DELETE SET NULL,
    dupe_score  REAL
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
CREATE INDEX idx_reports_dupe_of ON reports(dupe_of);


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

    -- Why this assignment ended. 'self' when they cleared themselves, which
    -- needs no announcement — they were there and they decided.
    --
    -- 'resolved' is the one that matters: somebody closed the report while
    -- this person was still driving to it. Until this column existed, that
    -- happened silently. The whole project is about not sending people to an
    -- address nobody needs them at, and the app was doing it to its own
    -- responders — clearing them off a job and leaving them to find out by
    -- refreshing a page they were not looking at.
    cleared_reason TEXT CHECK (cleared_reason IN ('self', 'resolved')),

    -- When they acknowledged being stood down. Null means they have not seen
    -- it, so it keeps showing. A notice that dismisses itself on a timer is a
    -- notice somebody in a car misses.
    stand_down_seen_at TEXT,

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

    -- Made by the browser before the check-in is sent, so a retry carries the
    -- same one. "Did that send?" is the question a flaky connection exists to
    -- make unanswerable; this is how the answer stops mattering.
    -- Null for anything that never went through the queue.
    client_id   TEXT    UNIQUE,

    -- When the responder says they were there. For a check-in queued offline
    -- this is the time it was made, not the time it reached us. The overdue
    -- timer runs off this, so a late sync can't silently clear a red row.
    created_at  TEXT    NOT NULL,

    -- When the server actually got it. Ours, not the client's. The gap
    -- between the two is what tells a coordinator someone was out of contact.
    received_at TEXT    NOT NULL
);

CREATE INDEX idx_checkins_responder ON checkins(responder, created_at DESC);
