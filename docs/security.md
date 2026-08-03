# Security

What DiresQ defends against, what it doesn't, and the one thing we shipped
that was properly wrong.

Not a security audit — nobody qualified has looked at this. It's an honest
account of the threat model we built to, and where we know it stops.

---

## Who we're defending against

Three people, roughly, in increasing order of trouble:

**Somebody being careless.** Typing their password with Caps Lock on, joining
the same report twice, filing a report with no location. Most of the work is
here, and most of it isn't security so much as not punishing people for being
stressed.

**Somebody being a nuisance.** Flagging real reports as fake, claiming to be
on scene from their sofa, guessing at another volunteer's password. Handled by
making it visible rather than impossible.

**Somebody with a radio.** The one genuinely adversarial case, because a LoRa
link has no transport security at all. Anyone with a $12 module can hear the
whole channel and transmit on it.

What we are explicitly *not* defending against is a determined attacker with
time. This is a hackathon project. If it mattered, it would need a real
review.

## Passwords and sessions

Hashed with `werkzeug.security` — scrypt by default — and never stored,
logged, or echoed back.

A failed sign-in returns the same message whether or not the account exists.
Different messages turn a login form into a free tool for discovering
usernames.

Passwords are capped at 128 characters. The hash is deliberately slow, so an
uncapped field is a way to make the server do arbitrary work for one request.

Sessions are signed with a key read from the environment. Absent one, a random
key is generated each boot, which signs everybody out on every restart —
annoying by design, so nobody ships a hardcoded default by accident. Cookies
are `HttpOnly` and `SameSite=Lax`, and `Secure` when `DIRESQ_HTTPS_ONLY=1`.

Eight wrong guesses locks a username for five minutes. The counter lives in
memory, not the database — deliberately, because a lockout that survives a
restart is one an attacker can make permanent by guessing at somebody on
purpose.

## The one we got properly wrong

The login route ended with this:

```python
return redirect(request.args.get("next") or url_for("homepage"))
```

`next` comes from the query string, so it is whatever the link you clicked
says it is. `?next=https://somewhere-else` gives you a **real login page, on
our real domain, that hands you to an attacker's site the moment you
successfully sign in.** That is the entire phishing setup, and we built it by
accident.

The helper used by every other redirect already checked this — `answer()` only
honours paths starting with `/`. The login route predated that helper and
never got the same treatment. Nothing caught it because nothing was looking:
the tests asserted that a successful login redirects, which it did.

Fixed with a `safe_next()` used by both, and three tests that try to escape:
an absolute URL, a protocol-relative `//host`, and an ordinary `/board` that
still has to work.

The lesson is not "validate redirects." It's that **a security rule applied in
one place is a security rule you haven't applied.** We had the right code and
one route that never got it.

## Radio packets

`/api/uplink` accepts a check-in as bytes from something with no session — a
gateway has no cookie, only a packet it heard. So the packet carries its own
proof.

Each responder gets a 32-byte key when their account is created. Every packet
carries four bytes of HMAC-SHA256 over its body, and the **version byte is
signed too**, so nobody can talk the server down to an older format by
flipping one bit.

The responder id inside the packet is read *only* to decide whose key to check
against. Nothing is written until the signature matches, compared in constant
time. An account that doesn't exist and an account with no key give the same
404, so the endpoint can't be used to enumerate valid ids.

One test flips every single bit of a sealed packet — all 144 — and requires
every one to be rejected.

**Four bytes is 32 bits.** A blind forgery gets through roughly once in four
billion attempts. That's a deliberate trade on a link where a full 32-byte tag
would be twice the size of the message it protects, and it's written down
rather than glossed.

**Replay is not solved.** Somebody who records a valid packet off the air can
send the same bytes again later and move that pin. Closing it needs a counter
in the packet and a record of the last one accepted — two more bytes and a
table. It's the first thing we'd add.

**Key distribution is a person typing.** `flask --app app node-key alice`
prints a key and you put it in that node. That works for a volunteer group and
would not survive a real deployment.

## What the database can't be talked into

Every query is parameterised. There is no string formatting anywhere near
SQL, and one of the adversarial tests files a report with the subject
`'; DROP TABLE reports; --` and then asserts the row count went **up** by one
and the feed still renders.

Jinja autoescapes by default, so `<script>alert(1)</script>` as a report
subject renders as text. Also tested, because "autoescaping is on" is the sort
of thing that stops being true when somebody reaches for `|safe`.

Foreign keys are enforced with `PRAGMA foreign_keys = ON` — off by default in
SQLite, which surprises people.

## Response headers, and the one that fought the map

Every response carries a Content Security Policy, `X-Content-Type-Options`,
`Referrer-Policy` and friends. The policy names Leaflet's CDN for scripts and
styles and the OpenStreetMap hosts for images, rather than opening either
category with a wildcard. `script-src` never gets `'unsafe-inline'`; styles do,
because Leaflet writes an inline `style` on every tile it positions, and that
is the half that does not make injected markup executable.

The service worker gets **its own, narrower policy**, and it has to. A worker
is governed by the headers on its own script, and every `fetch()` it makes is
judged against `connect-src` — never `img-src`, even when the thing it is
fetching is an image the page beside it is allowed to load directly. Serving
`/sw.js` with the page policy therefore forbade the worker from fetching map
tiles at all.

That failure was almost perfectly disguised. Until the worker claims the page,
tiles are fetched by the page itself and `img-src` lets them through, so the
map always painted correctly and then went grey as soon as somebody moved it.
It looked like a rendering bug, and it was an access-control decision working
exactly as written.

Two things worth taking from it. A policy tight enough to be worth having is
tight enough to break something, and the breakage will not look like a policy
error. And a security header applied globally by an `after_request` hook lands
on responses that are not pages — workers, manifests, JSON — where the same
directives mean different things.

## What CI refuses to let through

Three checks, on every push:

- **gitleaks** for committed secrets
- **bandit** and **pip-audit** for known-vulnerable patterns and dependencies
- A pattern check for a hardcoded `SECRET_KEY`, a committed `.db` file, or
  `random` used where `secrets` belongs

That last one has its own story: the original was a shell `grep` whose quoting
broke inside a YAML block scalar, so the job exited 2 having **searched
nothing**. It failed safely, but a check that looks like it's protecting you
and isn't is worse than no check. Rewritten in Python and tested against a
deliberately broken file to prove it still catches a real one.

## Things we chose not to defend

Written down rather than quietly hoped over:

| | |
| --- | --- |
| **Identity** | Anyone can register as a responder. There is no honest weekend version of ID checking, and a fake one — email confirmation, say — would be worse than nothing, because it looks like verification |
| **Location** | Self-reported and spoofable. We detect *inconsistency* — claiming to be on scene from over 500 m away raises a flag — not intent |
| **Flagging** | Three coordinated accounts can bury a real report. It's community moderation, not verification |
| **Age** | No age gate. Nothing asks |
| **The uplink endpoint** | Signed, but unauthenticated by design and not something to expose to the internet |

## If you find something

Open an issue, or say so in the repo. We would genuinely rather know than be
right. Nothing here is deployed and there is no user data at risk, so there's
nothing to disclose privately — but if that changes, this page changes with
it.
