# Process

What actually happened while building this, including the parts that went
wrong. Kept honest on purpose — a build log where nothing broke isn't a build
log, it's marketing.

---

## How we split it

Skythe took `/templates` and `/static`. Londo took `app.py`, the schema and
the API. Kiyan took testing, demo and content.

The rule was: own your files, say something in Discord before touching
someone else's. That held for most of the build. The two times it didn't are
below.

## The plan didn't survive contact

Our doc said the backend would push stub endpoints returning fake JSON in the
first hour, and the frontend would build against those so nobody was blocked.

That's not what happened. Skythe built five complete pages before the backend
existed — and built them as **server-rendered Jinja templates**, not as
JavaScript fetching from an API. So the stubs would have been ignored.

She unblocked herself by guessing variable names and carrying on, which
worked, but it meant the contract was assumed rather than agreed. We paid for
that in three separate mismatches:

| She wrote | Backend had |
| --- | --- |
| `HIGH` / `MEDIUM` / `LOW` | integers 1–4 |
| `report.latitude` / `.longitude` | `lat` / `lng` |
| `staffing: needs_more` | `need_more` |

All three were found by reading her templates against the schema, not by
anything breaking. We took her names in every case — the templates were real
and working, the schema was still just a document.

## Three bugs found by tooling, not by reading code

This is the part we'd point at if someone asked what we learned.

**Error messages that went nowhere.** The backend was calling `flash()` in
five places — bad login, missing subject, no map pin, double-join. No template
rendered `get_flashed_messages()`. Every one of those messages was thrown
away, so a rejected form just sat there looking frozen.

Found by a test asserting the login page said *why* it rejected you. Nobody
would have caught this by clicking around, because the page looks fine — it
just silently does nothing.

**A required field that wasn't.** The report form marked its hidden latitude
and longitude inputs `required`. Hidden inputs are exempt from browser
validation, so an untouched map submitted anyway and the report saved with no
coordinates — invisible on the map, forever.

Found by a parametrised test that tried submitting with the map never clicked.

**CI that couldn't install our own dependency.** `pygeospy` published a single
Windows wheel. `pip install -r requirements.txt` worked on both our machines
and died on ubuntu, before a single check ran. Found the first time CI ran.

## The security check that failed for the wrong reason

Our security workflow greps for a hardcoded `SECRET_KEY`. The pattern needed
both quote characters, and escaping that inside a YAML block scalar produced
an unterminated string. Bash exited 2 and the job went red.

It never searched anything. A check that looks like it's protecting you and
isn't is worse than no check, so we rewrote both patterns in Python where
there's no shell quoting to get wrong — and tested it against a deliberately
broken file to prove it still catches a real one.

It failed *safely*, which is the right direction for a check to fail in. But
we only knew that because we went and looked.

## The two times we crossed into each other's files

Both with a heads-up first, both minimal.

Londo added the flash block to three templates — that was fixing a bug he'd
caused by sending messages nowhere. Later, with Skythe's okay, he built the
accountability board as three new files and added a nav link, keeping the
styles in a separate stylesheet so none of hers were touched.

The rule that made this work: **new files are free, edits to someone else's
files need a message first.**

## What we'd do differently

Agree the field names in writing before either side starts. Not the endpoints,
not the schema — just the names and shapes. It's fifteen minutes and it would
have saved all three mismatches above.

Write the first test earlier. The test suite found two real bugs within
minutes of existing, both of which had been sitting there for hours looking
like working features.
