# Project doc errata

The planning doc was written before the code, and in the places where the two
disagree, the code is right — it's the thing that runs. This is the list of
edits to apply to the doc so it stops describing an app we didn't build.

Not part of the published site. It exists so that anyone reading the doc
alongside the repo doesn't waste twenty minutes on a difference that was
settled days ago.

---

## Priority is words, not numbers

**Doc, schema section:**

```
priority INTEGER NOT NULL -- 1 low .. 4 critical
```

**Code, `schema.sql`:**

```sql
priority TEXT NOT NULL CHECK (priority IN ('HIGH', 'MEDIUM', 'LOW'))
```

Three bands, not four, and words rather than integers. Skythe's templates were
already written against `HIGH`/`MEDIUM`/`LOW` before the schema existed, and
the interface never used a numeric scale — nothing rendered "3" to anyone.
Taking her names cost nothing and removed a translation layer that only
existed to be got wrong.

Everywhere the doc says **priority 4**, read **HIGH**. Everywhere it says
**priority 1**, read **LOW**.

Sorting is by an explicit rank in SQL, because ordering the words
alphabetically puts HIGH below LOW.

## Staffing is not a column

**Doc, reports table:**

```
staffing TEXT NOT NULL DEFAULT 'unstaffed'
```

There is no such column. Staffing is computed at read time from the votes of
whoever is currently on scene, taking the most cautious one.

The doc contradicts itself here — the "staffing conflict" section further down
already says it becomes computed rather than stored. That's the version that
got built. Delete the column from the table listing.

The values are unchanged: `unstaffed`, `need_more`, `adequate`,
`overstaffed`, `stood_down`.

## The reports table listing

**Doc:** *"Reports table (id, subject, description, priority, lat, lng,
status, staffing, needed, sender, created_at)"*

**Actual:** `id, subject, description, priority, lat, lng, status, needed,
flags, sender, auto_filed_for, created_at`

`staffing` is gone (above). `flags` and `auto_filed_for` were added later, for
community flagging and the dead man's switch.

`needed` exists but nothing writes to it. The staffing signal turned out to
answer the same question better — a number typed by whoever filed the report
is a guess, and a signal from someone standing there is an observation.

## `?min_priority=2` is not a thing

**Doc:** `GET /api/reports ?min_priority=2&status=unassigned`

`/api/reports` takes no query parameters. It returns every open report,
already sorted, and the feed filters in the browser. With the number of
reports one town produces, a server-side filter would be a parameter to
validate for no gain.

## The dead man's switch: fifteen minutes, not ten

**Doc:** *"+10 min with no check-in → the app auto-creates a new report"*

Built at **fifteen** minutes past their deadline. Ten made every dropped
signal a callout, which is how a useful alarm becomes one people learn to
ignore.

Note also *past their deadline*, not past their last check-in. Someone who
said "back in two hours" gets two hours plus fifteen minutes.

**Doc:** *"a `source = 'auto_overdue'` column and a nullable
`about_responder` FK"*

Built as one column, `auto_filed_for`, holding the account id. It does both
jobs: non-null means the server filed it, and the id says who it's about. It's
also what stops a second one being filed — while an open report points at
someone, the alarm has already been raised.

The report is filed under that person's own name, since it is about them and
there's nobody else to attribute it to.

## Hardware was dropped, and nobody said so

The first version of the doc had a Cardputer section: a field device sending
check-ins over serial, with a pre-recorded demo segment at 2:15 and a
contingency if it misbehaved on camera. The updated doc has no Cardputer in it
at all.

That was never decided out loud, it just stopped being written down. Recording
it now: **no hardware.** We have no device, so there is nothing to film.

What replaced it is `tools/gateway.py` — the same idea without the device. It
reads packets from a pipe or a serial port and forwards them, which is exactly
what a Cardputer would have talked to. The serial path is written and has
never been run, because there's nothing to plug in. See `offline.md`.

## LoRa: still roadmap, but less of it than before

**Doc:** *"LoRa — roadmap only, do not build"*

Still true of the radio. Not true of everything around it any more: the packet
format, the signing, the endpoint and the gateway are all built and tested.
What's missing is the hardware and the firmware.

The doc's roadmap line in the video script — *"LoRa mesh as the third
transport"* — is fine to keep, as long as it's said as a roadmap item and not
as something we demonstrated.

## Things the doc doesn't mention because they came later

- Community flagging: one flag each, hidden at three, still visible to whoever
  filed it and anyone already on their way
- Position mismatch: marking yourself on scene from over 500 m away raises a
  flag on the board
- Backdated check-ins, so one queued offline is judged on when it was made
- The coverage gap banner
- ICS-214 export
- The triage helper running START
- The credits page, which is not linked from anywhere
