# Contributing

Thanks for looking. This is a hackathon project that outgrew the hackathon, so
the rules here are short and mostly about one thing: **nothing in this
repository should claim more than it can back up.**

By taking part you agree to the [Code of Conduct](CODE_OF_CONDUCT.md).

## Getting it running

```bash
git clone https://github.com/Skythe7/DiresQ.git
cd DiresQ

python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux

pip install -r requirements-dev.txt

flask --app app init-db         # destructive: drops everything
flask --app app seed            # loads an incident already in progress
flask --app app run --debug
```

Python 3.10 or newer. No database server, no Node, no Docker — the database is
a file. [docs/install.md](docs/install.md) has the longer version, including
how to see each feature actually working.

Node 22 is only needed for the documentation site under `site/` and for two
test helpers that run the browser-side classifier.

## Before you open a pull request

```bash
pytest -q
```

That is the whole gate. It runs in about ninety seconds and it is not
decorative — it will fail you for things you would not expect, which is the
point.

## The four rules

**1. A fix comes with a test that fails without it.**

Not a test that exercises the area. A test that goes red when you revert your
change and green when you restore it. Please actually try that; it takes
thirty seconds and it is the difference between a test and a comment.

**2. Numbers in prose must be true.**

`TestTheDocsAreNotOutOfDate` reads the README and the docs, pulls out every
count — tests, routes, tables, indexes, lines of code, total lines written —
and checks them against the repository. If you add a route or a test, a
documentation test will fail until the prose agrees. That is deliberate. It
has caught a wrong number more than a dozen times, including several written
by the people who added the check.

The frozen table near the top of the README is exempt and must stay that way.
It is a snapshot of the fourteen-hour build window and is *supposed* to
disagree with the repository as it stands.

**3. If you weaken a guarantee, say so in `docs/limits.md`.**

[limits.md](docs/limits.md) is the most important file here. A limitation that
is written down is a design decision; the same limitation undocumented is a
lie by omission. If your change means something no longer holds — or holds
only under conditions that were not there before — the page needs a paragraph
before the pull request is done.

The reverse counts too. If you close a limitation, move it to *"Limits we
closed, and how"* rather than deleting it.

**4. Don't cache anything that stops being true when it is written.**

The offline layer keeps your own commitments and refuses to keep claims about
other people. A cached report feed is a list of who needed help twenty minutes
ago, and acting on it sends somebody to an address that was cleared. The rule
and the reasoning are in [docs/offline.md](docs/offline.md), and a test fails
if the feed or the board is added to the service worker's shell list.

## Style

Ruff for Python; it runs in CI. Beyond that:

- **Comments explain why, not what.** The code already says what it does. The
  comment should say what happened when somebody tried it the other way.
- **Commit subjects only** — no bodies. Say what changed in one line. The
  reasoning belongs in a comment next to the code, where it will still be
  found in a year.
- `app.py` is one file on purpose, and the index in its docstring is checked
  against the section banners by a test. If you add a section, add it to both.

## Changelog

Entries go in `CHANGELOG.md` under `## [Unreleased]`, written for somebody who
uses the app rather than somebody who wrote it. "Fixed the CSP on the worker"
is not an entry; "the map went grey a moment after it loaded" is.

Releases are cut with [patchnotes](https://github.com/Londopy/patchnotes):

```bash
patchnotes CHANGELOG.md bump 1.0.3
git add CHANGELOG.md CITATION.cff && git commit -m "Release 1.0.3"

git push                      # push the commits FIRST
git tag v1.0.3                # then tag what is actually on the remote
git push --tags
```

Push before you tag. A tag names one commit, and the release workflow builds
from whatever that commit contains — see the note in the README about how
v1.0.1 shipped without its launcher scripts.

## Security

Please don't open a pull request that quietly fixes a vulnerability. Read
[SECURITY.md](SECURITY.md) first — it explains what is in scope, and what we
already know is wrong and have written down.

## What this project will not accept

- **Anything that makes DiresQ look like it can summon help.** It cannot. It
  does not call 911, no dispatcher reads it, and the disclaimer on every page
  is load-bearing rather than legal decoration.
- **Medical advice.** The triage helper runs START to order who gets reached
  first. It does not treat anybody, and it must not start implying it does.
- **Storing the triage answers.** They are health observations about a person
  who never consented and is probably not in a position to. The reasoning is
  in [limits.md](docs/limits.md).
- **A number in the documentation that nothing checks**, where a check is
  possible. If you find one, that is a bug, and a welcome pull request.
