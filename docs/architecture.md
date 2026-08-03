# Architecture

How DiresQ is put together, for someone who has the source open.

`decisions.md` covers *what* we chose and what it cost. This is the *how*: the
data model, what runs on a request, where the sharp edges are, and the point
at which each design stops working. Written for a reader who wants to find
something in the code, or take it apart.

---

## Shape

Flask, SQLite through the `sqlite3` module, Jinja templates rendered on the
server, and a small amount of JavaScript that layers on top. Roughly 4,000
lines of Python across six modules, 33 routes, five tables, 537 test
functions.

```
                browser ──── forms (no JS needed) ────┐
                   │                                  │
                   └──── fetch / JSON ────────────────┤
                                                      ▼
    radio ─► tools/gateway.py ─► POST /api/uplink ─► app.py ─► SQLite
                                                      ▲
                              cron ─► flask sweep ────┘
```

Three ways in, one set of rules. The uplink and the browser both end at
`record_checkin()`; if they ever disagree about what a check-in means, it will
be because somebody wrote a second copy of that function.

### Why no ORM

Every query in this app is either a lookup by primary key or one specific
aggregate over four tables. An ORM earns its keep when the query shapes are
unknown at design time. Ours were known by the second hour, and the two that
matter — the feed ordering and the board — are both easier to read as SQL than
as a query builder pretending to be English.

The cost is real and worth naming: no migrations. `init-db` drops everything
and rebuilds. That's fine for a hackathon and would not survive a week of
production, where the first schema change means somebody writing `ALTER TABLE`
by hand.

### Why nothing is stored that can be derived

The two things this app is *for* — whether someone is overdue, and how staffed
a report is — are both computed when read. Neither is a column.

Stored state has to be kept true by something. That something is a background
job, and a background job that dies takes the truth with it, silently, while
every page keeps rendering a green board. Deriving costs a query and removes
an entire class of failure where the database says one thing and reality says
another.

The limit is arithmetic: it's a query per read, and at some number of
responders that stops being free. That number is far above anything one town
produces.

---

## Data model

Five tables. `schema.sql` is 177 lines and is the shortest useful description
of the app.

```
accounts ──┬── reports ──┬── assignments ──┐
           │             └── report_flags  │
           └── checkins ◄──────────────────┘
```

**`accounts`** — username, hashed password, role, comma-separated
capabilities, and `node_key`: a per-responder secret used to sign radio
packets. Null until issued, and an unsigned packet is refused, so a missing
key fails closed.

**`reports`** — the thing that needs doing. `priority` is `HIGH`/`MEDIUM`/
`LOW` as text with a CHECK constraint, not an integer scale. `auto_filed_for`
is non-null when the server filed it because somebody went quiet; it doubles
as the idempotency key for the dead man's switch. There is no `staffing`
column — see below.

**`assignments`** — many responders to one report. `UNIQUE (report_id,
responder)` is what makes a double-join impossible; the join route catches
`IntegrityError` and flashes rather than erroring, because joining twice is a
double-tap, not a fault. `staffing_vote` lives here rather than on the report,
which is what lets disagreement be represented at all.

**`checkins`** — two timestamps, deliberately. `created_at` is when the
responder says they were there; `received_at` is when we got it. The overdue
timer runs off the first. `client_id` is UNIQUE and set by the browser before
sending, so a retry is recognised instead of logged twice.

**`report_flags`** — one row per person per report, `PRIMARY KEY (report_id,
account_id)`. The counter on `reports.flags` is a denormalised convenience;
this table is the truth.

### Deletion

There isn't any. Reports are `hidden` or `resolved`, assignments are
`cleared`, and nothing is removed. In an accountability tool the record of
what happened is the product.

---

## The two interesting computations

### Staffing resolution

A report's staffing state is the **most cautious** vote among people currently
on scene:

```python
STAFFING_ORDER = ("stood_down", "overstaffed", "adequate", "need_more")

def resolve_staffing(votes):
    ranked = [v for v in votes if v in STAFFING_ORDER]
    if not ranked:
        return "unstaffed"
    return max(ranked, key=STAFFING_ORDER.index)
```

Max, not majority and not average. Four people saying "we're fine" cannot
outvote one person saying "we need help", because the failure mode we care
about is a call for help getting drowned out. It is a deliberately
asymmetric rule and it has a known cost: one pessimist can hold a report near
the top of the feed. That trade is in `limits.md`.

Votes only count while `status = 'on_scene'`. Clearing sets the vote to NULL —
you can no longer see the scene, so you no longer get an opinion about it.

### Feed ordering

Two keys, and the order they are applied in is the whole point.

```python
reports.sort(key=lambda r: (-r["priority_rank"],
                            -FEED_RANK.get(r["staffing"], 1)))
```

Priority first, always. Staffing is a tie-break **inside** a band and never
across one, so six people shouting for help at a blocked driveway can never
sort above a trapped family nobody has seen.

Within a band the order is `need_more` → `unstaffed` → `adequate` →
`overstaffed`. Note that *nobody on it* outranks *adequately covered*: a gap
is worse than a queue, which is the entire thesis of the project expressed as
a sort key.

Priority itself is ranked in SQL rather than sorted as text, because
alphabetically `HIGH < LOW < MEDIUM` — a bug that looks like working code:

```sql
CASE r.priority WHEN 'HIGH' THEN 3 WHEN 'MEDIUM' THEN 2 ELSE 1 END
```

The SQL does the priority ordering, Python does the staffing tie-break, and
Python's sort is stable, so equal keys keep the order SQL gave them.

---

## What happens on a request

1. `before_request` runs the silence sweep, but only for GETs on five
   endpoints and only when somebody is signed in.
2. The view calls `get_db()`, which lazily opens a connection on `g` with
   `row_factory = Row` and `PRAGMA foreign_keys = ON`.
3. Context processors make `current_user`, `overdue_count()` and
   `coverage_gap_count()` available to every template. The last two are
   *callables*, so a page that doesn't render the badge doesn't pay for the
   query.
4. `teardown_appcontext` closes the connection.

### A GET that writes

The sweep is the ugly bit and it should be argued rather than hidden.

There is no scheduler inside the app. A timer thread that dies takes the alarm
with it — the worst possible failure for something whose only job is noticing
that a person has gone quiet. So the check rides along on page loads, and
`flask --app app sweep` exposes the same function for cron.

It is idempotent: an open report with `auto_filed_for` set to somebody means
the alarm has already been raised, so polling it a hundred times a minute
changes nothing after the first. Two concurrent requests could in principle
both file — SQLite's write lock makes that a narrow window, and the cost is a
duplicate report rather than a lost one, which is the right way round.

### Forms and JSON from one endpoint

Every action endpoint answers both:

```python
def answer(payload, status, message, report_id=None):
    if request.is_json:
        return jsonify(payload), status
    if message:
        flash(message)
    target = request.form.get("next")
    if target and target.startswith("/"):
        return redirect(target)
    ...
```

Send JSON, get JSON. Post a plain form, get a redirect and a flashed message.
That's what lets every button work with JavaScript switched off without
maintaining two code paths.

The `next` check is not decoration. The same pattern was missing from the
login route and made it an open redirect — a real login page on a real domain
that hands you to somebody else's site. See `process.md`.

---

## Trust boundaries

Three inputs, three different levels of trust, handled differently.

**The session.** `current_user()` is the only thing that decides who you are
in the browser. `DIRESQ_DEV_USER` bypasses it entirely and is a full auth
bypass for development.

**Client-claimed time.** `happened_at` on a check-in is a claim, so it's
bounded: more than two minutes ahead is rejected, more than twelve hours old
is rejected, slightly ahead is clamped to now rather than stored in the
future. Without the bound, a client could hold its own row green forever.

**Radio packets.** No session at all. The responder id inside the packet is
read *only* to choose which key to verify against; nothing is written until
four bytes of HMAC over the body match. Unknown account and unkeyed account
return the same 404, so the endpoint can't be used to enumerate ids.

What none of this stops is someone lying about *where* they are. We detect
inconsistency instead: marking yourself on scene when your last check-in was
over 500 m away raises `position_mismatch` on the board. Detection, not
prevention — no client-side code fixes a determined liar.

---

## Performance, and where it stops working

Honest numbers, because "it's fast" is not an engineering claim.

**`fetch_reports()` is N+1.** One query for the reports, then
`staffing_for(id)` per report. At the scale of one town's incidents that is
tens of queries against a local SQLite file — microseconds. At a thousand open
reports it's a thousand round trips and would need folding into a single
`GROUP BY` with the resolution moved into SQL, or a lateral join.

We left it because the fix costs readability now for a scale we do not have,
and the shape of the fix is obvious when it's needed.

**`fetch_responders()` is one query** with a `ROW_NUMBER() OVER (PARTITION BY
responder ORDER BY created_at DESC)` window to pick each person's latest
check-in. Indexed by `idx_checkins_responder (responder, created_at DESC)`.
This one scales fine.

**Polling.** The board polls every 3 seconds, the feed every 4. Each poll is a
full recompute. For a handful of coordinators that's nothing; for a hundred
concurrent viewers it's a hundred recomputes every three seconds, and the
answer is server-sent events or a short-lived cache, not a bigger machine.

**One writer.** SQLite serialises writes. Fine for a town, wrong for a state,
and the migration is Postgres — the queries are ordinary enough that little
would change beyond the connection.

**Five indexes**: reports by status, reports by `auto_filed_for`, assignments
by report and by responder, check-ins by `(responder, created_at DESC)`.

---

## Testing

537 test functions, which parametrisation expands into over six hundred
cases. Each gets a throwaway database
via `tmp_path`, so order never matters and a failure can't poison the next
test.

Two seeds, kept apart on purpose:

- `seed_minimal()` — three accounts, five untouched reports. What the tests
  run against.
- `seed_data()` — the demo: an incident already two hours old, somebody 47
  minutes out of contact.

They were one function until improving the demo broke five tests. Tests
asserting on demo content means the demo can't be improved without arguing
with the test suite about what a number means.

Some of the more useful tests don't test behaviour at all:

- One parses `schema.sql` and fails if any table is created without a matching
  `DROP`. It can't be satisfied by fixing one table — only by keeping the file
  consistent, including tables nobody has written yet.
- One flips **every single bit** of a signed packet — all 144 of them — and
  requires every one to be rejected.
- `TestTryingToBreakIt` is the adversarial pass: empty forms, denied GPS, a
  `DROP TABLE` in a subject line, script tags, someone else's assignment, a
  report id of `banana`. It found a real bug.

CI runs lint (errors only, not style), the suite, and a boot check that starts
a real server and curls it — because the test client skips the WSGI layer and
the static handler, and "all tests pass but it won't start" is a thing that
happens.

---

## Module map

| File | Lines | What it owns |
| --- | --- | --- |
| `app.py` | 2,620 | Routes, queries, the rules, CLI commands |
| `classify.py` | 805 | The classifier, its corpus, and the browser export |
| `transport.py` | 204 | The radio packet: layout, signing, verification |
| `eta.py` | 175 | Free-text ETA parsing behind a confidence gate |
| `triage.py` | 85 | START triage, mapped onto report priority |
| `tools/gateway.py` | 136 | Forwards packets from a pipe or a serial port |
| `schema.sql` | 177 | Five tables, six indexes, all the constraints |

`app.py` is one file on purpose. Blueprints buy separation of concerns at the
cost of indirection, and at 2,600 lines with 33 routes the concerns aren't
separable in a way that would help anyone reading it. The point at which to
split it is when two people need to edit different parts of it at once, and
that hasn't happened.

It is, however, the file most likely to be the first thing a maintainer
complains about, and they would not be wrong. The natural seams are the CLI
commands, the packet handling, and the ICS-214 builder — none of which need
to see a route.

### Third-party, and our own

Flask, python-dotenv, and three libraries Londo published before this project:
**timefuzz** (fuzzy time parsing), **vitalscore** (START triage scoring), and
**pygeospy**. `patchnotes`, also his, validates the changelog in CI.

Haversine distance is inlined rather than imported — one function, six lines,
no reason to take a dependency for it.
