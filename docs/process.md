# Process

What actually happened while building this, including the parts that went
wrong. Kept honest on purpose — a build log where nothing broke isn't a build
log, it's marketing.

---

## How we split it

Skythe took `/templates` and `/static`. Londo took `app.py`, the schema and
the API. Testing, demo and content were a third share that ended up
unclaimed partway through, and got absorbed into the other two.

The rule was: own your files, say something in Discord before touching
someone else's. That held for most of the build. The two times it didn't are
below.

Worth saying plainly, because it's the thing a two-person team learns fastest:
a three-way split that quietly becomes a two-way split is not a crisis, it's
Tuesday. What matters is noticing early enough to re-plan rather than
discovering it at the deadline.

## The plan didn't survive contact

Our doc said the backend would push stub endpoints returning fake JSON in the
first hour, and the frontend would build against those so nobody was blocked.

The backend didn't push those stubs. That's on Londo — the plan had one
dependency, it pointed at him, and he went and built the real thing instead of
the thing everyone else was waiting on.

Skythe, quite reasonably, did not sit and wait. She built five complete pages
in the time it would have taken to ask, and built them as **server-rendered
Jinja templates** rather than JavaScript fetching from an API — which, as it
turned out, was the better architecture, and is what the app still uses today.
The stubs would have been thrown away regardless.

The cost was that the contract ended up assumed on both sides rather than
agreed by either. Three names came out different:

| Frontend | Backend |
| --- | --- |
| `HIGH` / `MEDIUM` / `LOW` | integers 1–4 |
| `report.latitude` / `.longitude` | `lat` / `lng` |
| `staffing: needs_more` | `need_more` |

Found by reading the templates against the schema, not by anything breaking.
The frontend names won all three times, and that was the right call: the
templates were real, working software, and the schema was still a document
nobody had run. `HIGH`/`MEDIUM`/`LOW` is also just better than integers 1–4 —
nothing ever rendered a `3` to a human being.

The honest lesson isn't "the frontend should have waited." It's that the one
person who could have unblocked everybody didn't, and then the fix was to
adopt what she'd already got right.

## Five bugs found by tooling, not by reading code

This is the part we'd point at if someone asked what we learned. Four are
below; the fifth has its own section after them, because it's the strangest
one.

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

**A table that was created but never dropped.** `schema.sql` tears everything
down before rebuilding it. A table added late — `report_flags` — got its
`CREATE` and not its `DROP`. Rebuilding a database that already existed
dropped four tables, hit the fifth, and stopped, leaving it in pieces. The
next command then failed complaining about a *different* missing table, which
sent us looking in the wrong place entirely.

Found by running it on a real machine with real data in it. Every test had
been passing, because tests build from empty every time and empty is the one
case that works.

The fix was one line. The interesting part is the test we wrote after: it
reads `schema.sql`, pulls out every `CREATE TABLE` and every `DROP TABLE`, and
fails if anything appears in the first list and not the second. It can't be
made to pass by adding a drop for `report_flags` — only by keeping the whole
file consistent, including tables nobody has written yet.

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

## The one we found by reading

Adding guardrails to the login form meant reading the login route properly for
the first time since it was written, and the last line of it was:

```python
return redirect(request.args.get("next") or url_for("homepage"))
```

`next` comes from the query string, so it is whatever the link you clicked
says it is. `?next=https://somewhere-else` and our real login page, on our
real domain, hands you to somebody else's site the moment you sign in
successfully. That is the entire phishing trick, and we'd built it by
accident.

The redirect helper used everywhere else already checked this — `answer()`
only honours paths starting with `/`. The login route predated that helper and
never got the same treatment. Nothing found it because nothing was looking:
the tests asserted a successful login redirects, which it did.

Fixed with a `safe_next()` used by both, and three tests that try to escape:
an absolute URL, a protocol-relative `//host` one, and a normal `/board` that
still has to work.

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

Run it against a database that already has something in it. Tests start from
empty every time, so anything that only breaks on the *second* run — which is
every run the judges will do — is invisible to them by construction.

**Unblock other people before you build your own favourite part.** Every
mismatch in this document traces back to one person building the interesting
thing instead of the thing somebody else was waiting on. The stub endpoints
would have taken twenty minutes. Nobody was owed them by a schedule; they were
owed by the fact that another person's next four hours depended on them.

## What we'd keep

Owning files rather than owning features. Two people editing `app.py` and
`homepage.css` in parallel never once conflicted, because the boundary was a
path and not a job title.

Writing the limitations down while building, not afterwards. Half of
`limits.md` was written in the same hour as the code it describes, which is
the only time you actually remember what you decided not to handle.

Taking the other person's naming when theirs is already working. It cost the
backend three renames and settled an argument that could have run all
weekend.
