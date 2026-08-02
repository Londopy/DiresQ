# Security policy

DiresQ is a student project built at a hackathon. It has never been deployed
anywhere that matters and holds no real data. That shapes everything below.

If you find something, **open a public issue** — there is nothing to disclose
privately, because there is nothing at risk. If that ever changes, this file
changes with it.

## What's in scope

The code in this repository, and the hosted demo if one is running.

The demo is seeded with invented reports and rebuilt from scratch every time
the server restarts. There are no real accounts, no real addresses, and
nothing worth stealing. Every page on it says so.

## What we already know is wrong

Reporting these isn't necessary — they're deliberate, documented, and
explained in [docs/security.md](docs/security.md) and
[docs/limits.md](docs/limits.md):

- **No identity verification.** Anyone can register as a responder. There is
  no honest weekend version of ID checking, and a fake one would be worse than
  none because it looks like verification.
- **Locations are self-reported** and can be falsified. We detect
  *inconsistency* — claiming to be on scene from over 500 m away — not intent.
- **Three coordinated accounts can bury a real report** through community
  flagging. It is moderation, not verification.
- **No age gate.** Nothing asks.
- **`/api/uplink` is unauthenticated by session** — a radio gateway has no
  cookie. Packets are signed and counter-protected instead, and the endpoint
  is not something to expose to the internet.
- **`DIRESQ_DEV_USER` is a total auth bypass.** It exists for development, it
  is never set on the hosted demo, and there is a test that fails if it
  appears in the deployment config.
- **Login lockouts are held in memory** and reset when the process restarts.
  Deliberate: a lockout that survives a restart is one an attacker can make
  permanent by guessing at somebody on purpose.

## What we'd genuinely want to hear about

- A way to read or change another account's data
- A way to bypass the signature or counter on `/api/uplink`
- Stored or reflected XSS — Jinja autoescapes and there's a test, but tests
  only cover what we thought of
- SQL injection — every query is parameterised, same caveat
- Anything that lets an unauthenticated request write to the database

## What we fixed after finding it ourselves

Both are written up properly in [docs/security.md](docs/security.md), because
a security page listing only the things you got right is marketing.

**An open redirect on the login route.** `?next=` came straight from the query
string, so `?next=https://elsewhere` made our real login page hand you to
somebody else's site the moment you signed in successfully. The redirect
helper used everywhere else already checked this; the login route predated it.
Fixed with one `safe_next()` used by both, and three tests that try to escape.

**A replay hole in the radio protocol.** A signature proves who made a packet
and says nothing about when, so anyone who recorded one off the air could send
the same bytes later and move that pin. Packets now carry a counter, signed
along with everything else, and the server refuses anything not strictly
greater than the last it accepted. We had documented this as an open weakness
before fixing it.

## Supported versions

There is one version: `main`. Nothing is backported anywhere.

## Contact

Open an issue on [the repository](https://github.com/Skythe7/DiresQ).

We are two students and we would much rather be told than be right.
