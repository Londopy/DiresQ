# Working without a network

The single most awkward fact about DiresQ is that it needs the internet, and
a disaster is the thing that takes the internet away. Cell towers have around
four to eight hours of battery. After Harvey, parts of Katy had no usable
mobile data for days.

So this page is the honest accounting of that problem: what is built, what is
half-built, and what is not built at all. It is deliberately blunt, because
the failure mode we're most worried about with our own project is claiming
more than we did.

---

## Status at a glance

| | State |
| --- | --- |
| Check-in packet format | **Built.** 22 bytes, signed, counter-protected |
| Uplink endpoint | **Built.** `POST /api/uplink`, verifies before writing |
| Gateway program | **Built.** `tools/gateway.py`, tested over a pipe |
| Backdated check-ins | **Built.** The server judges a check-in on when it was made |
| Node key issue and rotation | **Built.** `flask --app app node-key <user>` |
| Browser offline queue | **Built.** Check-ins survive having no signal |
| Deduplication of retries | **Built.** Client ids, so resending is free |
| Filing a report with no signal | **Built.** Written to the device first, sent later |
| Reports cannot arrive twice | **Built.** Id minted before the first attempt, checked before the `INSERT` |
| Priority suggestion with no signal | **Built.** The same trained model, evaluated in the browser |
| Duplicate detection offline | **Deliberately not built.** It needs everyone else's reports; see below |
| Duplicate detection on arrival | **Built.** Including against the rest of the same sync batch |
| Backdated reports | **Built.** A report says when it was written, and the feed says so |
| Radio hardware and firmware | **Not built.** We have no radios |
| Serial mode of the gateway | **Written, never run.** No hardware to run it against |
| Map tiles kept once seen | **Built.** Capped, no pre-fetching |

If you read nothing else: **check-ins and reports both survive having no
signal, the app suggests a priority without a server, and the map keeps
drawing where you have already been.** The feed and the board still need a
connection, on purpose. The radio is not built.

---

## What "LoRa support" would actually mean

LoRa is a long-range, very low-bandwidth radio. A few kilometres in a town,
tens of kilometres with line of sight, on hardware that costs about $12 and
runs for days on a battery. It is not a replacement for the internet — it is
a replacement for *one small message getting out*.

Which is convenient, because one small message is exactly what a check-in is.

Building it properly is four separate jobs:

1. **A message small enough to send.** Done.
2. **A way to prove the message is genuine.** Done.
3. **A gateway that hands received messages to the server.** Done, minus the
   serial port we can't test.
4. **A node: a radio, a GPS, a battery, a button, and firmware.** Not done.

We did the three that are software and stopped at the one that is hardware,
rather than writing firmware we could never run and calling it a feature.

### The message

`transport.py`. A check-in body is eighteen bytes:

| Bytes | Field |
| --- | --- |
| 1 | protocol version |
| 1 | packet type |
| 2 | responder id |
| 4 | latitude × 100000 |
| 4 | longitude × 100000 |
| 2 | age in minutes |
| 4 | counter, strictly increasing per node |

Plus four bytes of signature: **twenty-two total.**

Two details worth defending.

**Coordinates are integers scaled by 100000.** Five decimal places is about
1.1 m at the equator. That's far finer than a phone GPS manages in heavy rain,
and it halves what a float would cost.

**The packet carries an age, not a timestamp.** Four bytes saved, but mainly:
a battery-powered node that has been asleep in a flood is the last clock you
want to trust. "This happened nine minutes ago" survives a device whose sense
of the date is nonsense. The server does the arithmetic against its own clock.

The size budget matters and it's easy to get wrong:

| Link | Max application payload |
| --- | --- |
| LoRaWAN US915 DR0 | 11 bytes |
| LoRaWAN US915 DR1 | 53 bytes |
| Meshtastic | 237 bytes |
| Raw SX1276 | 255 bytes |

We designed against 53, the second-smallest, and there is a test that fails if
the layout ever outgrows it. Designing against the 255-byte figure is how you
discover at the demo that your packet doesn't fit.

Twenty-two bytes does not fit DR0. If it had to, the check-in would need
splitting across two packets, and we'd rather say that than pretend.

### The signature

On the web, HTTPS proves who you're talking to. On a radio there is no such
thing. Anyone with a $12 module can listen to the whole channel and transmit
on it, so the packet has to carry its own proof.

Each responder gets a 32-byte key, generated when their account is created,
kept in the `node_key` column. The packet carries four bytes of HMAC-SHA256
over the whole body — version byte included, so nobody can talk the server
down to an older format by flipping one bit.

`POST /api/uplink` reads the responder id out of the packet **only** to decide
whose key to check against. Nothing is written until the signature matches.
Comparison is constant-time.

Four bytes is 32 bits. A blind forgery gets through roughly once in four
billion attempts. That is not a serious cryptographic margin, and we're
choosing it knowingly: a full 32-byte tag would be more than twice the size of
the message it protects, on a link where bytes are the scarce thing.

**Replay is handled.** Every packet carries a 32-bit counter, signed along
with the rest of the body, and the server refuses anything not strictly
greater than the last it accepted from that node. Recording a packet off the
air and sending it again returns a 409 and writes nothing.

Four bytes rather than two, deliberately. Sixteen bits wraps after 65,535
messages and wrap handling on a replay defence is exactly the kind of
subtlety that becomes the hole. Thirty-two bits lasts about eight thousand
years at one check-in a minute; when a node genuinely runs out it needs a new
key, which is a rotation somebody performs rather than something the protocol
quietly papers over.

Gaps are fine — a node out of range for an hour comes back with a much higher
counter and is accepted. Only going backwards is refused.

**Key distribution is a person typing.** `flask --app app node-key alice`
prints a key; you put it in that node. That's the whole mechanism. It works
for a county-sized volunteer group and would not survive a real deployment.

### The gateway

`tools/gateway.py` is the piece that would sit next to the radio, and it knows
nothing about radios. It reads base64 packets one per line and posts them.

```bash
# forward whatever a radio module prints over USB
python tools/gateway.py listen --serial COM3

# forward a pipe — same code path, no hardware
python tools/gateway.py listen < packets.txt

# build and send one, as a specific responder
python tools/gateway.py send --responder 4 --key <hex> \
    --lat 29.7858 --lng -95.8244 --age 3
```

It survives things a radio link does constantly: line noise that isn't
base64, truncated packets, packets signed with the wrong key, and the server
being unreachable. None of those stop it listening — a gateway that exits on
one bad line is a gateway that's down.

Serial mode needs `pyserial`, which is deliberately not in
`requirements.txt`: nothing else needs it and we cannot test it. The stdin
path needs nothing and is what the tests exercise.

### The node

Not built. It would be an ESP32 with an SX1276, a GPS module, a battery and
one button. Press it, it reads the GPS, packs twenty-two bytes, signs them with
its key, transmits, sleeps.

We don't have the parts, so we haven't written the firmware. Untested
firmware in the repo would look like a feature and be a liability.

---

## The offline queue

Built, for check-ins only. Press the button with no signal and it goes into
`localStorage`, then onto the wire when there is one.

Three things make that safe rather than merely optimistic.

**It carries the time it was made.** Not the time it sent. Without this the
overdue timer would restart from the sync, so somebody silent through their
whole window comes back green the moment their phone finds a bar — the alarm
that correctly fired gets cancelled by the network recovering. See below.

**It carries an id made before it is sent.** *"Did that send?"* is the exact
question a flaky connection exists to make unanswerable, and the honest answer
is to stop caring: retrying is free because the server recognises an id it
already has and tells you about the row it wrote the first time, rather than
writing a second. It does not touch the original timestamp either, so
resending an old check-in cannot make it look recent.

**It is visible.** A pill in the corner says how many are waiting. A queue you
cannot see is a queue you do not trust, and this one has to be trusted in the
dark, in the rain, by somebody who is not thinking about software.

### What gets dropped, and when

- Anything older than twelve hours, because the server refuses those anyway.
  Better to drop it locally than send it to be rejected.
- Anything the server answers 4xx to — it looked at it and said no, and it
  will say no again forever.
- Nothing on a 5xx or a network failure. Those stop the flush where it is
  rather than hammering, and everything still queued stays queued.

### The bug that isn't obvious

`new Date().toISOString()` produces `2026-08-02T07:00:00.000Z`. Python only
learned to parse that trailing `Z` in 3.11. On a machine with 3.13 — which is
what this was written on — every queued check-in works. On 3.10 every single
one is rejected as an unreadable timestamp.

That is the worst shape a bug can have: correct on the developer's laptop,
broken in deployment, and silent in between. Found by posting the exact string
a browser sends rather than the one a Python test would naturally write.

## Filing a report with no signal

Built, and it is a different problem from the check-in queue in one way that
matters enough to justify a second module.

**A check-in sent twice is harmless. A report sent twice is a second
incident** — and duplicate incidents are the convergence failure this whole
project exists to make visible. So `reportqueue.js` is an outbox, not a retry
buffer, and the order is the design:

1. mint an id and write the report to `localStorage`
2. only then touch the network
3. only delete it once the server has said, in so many words, that it has it —
   either *I wrote this* or *I already had this*

Because step 1 happens before step 2, the id is on disk before anything can go
wrong. A phone that dies mid-request, a browser killed by the OS, a tab closed
in a panic: the retry after the restart carries the same id, the server
recognises it and hands back the report it already wrote. A client-side guard
would have been erased by the restart. A `UNIQUE` constraint on its own would
only complain once the duplicate had already been attempted. The check is
server-side, before the `INSERT`, in `create_report`.

There is a test that reads `reportqueue.js` and fails if the save and the send
are the wrong way round — that bug is invisible at runtime and obvious in the
source, so the source is where it is checked.

**With JavaScript off** there is no queue, but Back-then-Submit is the same
double-file with a person driving it, so the server renders an id into the
form as well.

### What the interface promises, and what it doesn't

A report that has been queued is **not** described as sent. The status line
says *"Saved on this phone. Not sent yet — there is no connection, so nobody
has seen this,"* it repeats *if this is life-threatening, call 911 now*, and a
pill in the corner counts what is waiting. If `localStorage` refuses us
entirely, the module gets out of the way and lets the plain form post happen,
because a report that cannot be written down must not be promised.

### Reaching the form at all

An offline queue you cannot open the form for does nothing, so the service
worker keeps a copy of `/report/new` once you have actually opened it —
lazily, not at install, because the page needs a session and `addAll` rejects
atomically. It is a blank form: it says nothing about who needs help, so it
passes the rule at the top of this page. The one thing it does carry, the
server-minted id, would go stale in a cache and hand one id to two different
reports — so it is replaced on load.

## The classifier, on the phone

The suggestion exists for somebody filing at 2am from a flooded house. That
person is the likeliest of anyone to have no signal, and until this shipped
they were the one person it never reached: it was Python, on a server, over a
network that was gone.

`flask --app app export-model` writes the trained model — word counts,
lexicons, thresholds — to `static/model/priority.json`, about 8 KB.
`static/scripts/classify.js` evaluates it. The service worker keeps both,
under the same rule as the stylesheets: **a trained model is a frozen table of
word counts, not a claim about the world right now.** There is a test that
fails if any field in it starts to look like live data.

There is one corpus and it is in `classify.py`. The browser gets the model,
never the training data — also tested.

### The parity test, and what it caught

Two implementations of one model is a drift bug with a delay on it, and an
offline suggestion that quietly disagrees with the online one is worse than no
offline suggestion, because nothing on screen would say so. So `tools/parity.mjs`
runs the shipped `classify.js` under node, and a test pushes every line of the
corpus plus a dozen awkward cases through both, failing on any disagreement.

It paid for itself on the first run. The words shown behind a suggestion were
being ranked by an edge score computed with `math.log`, and two words that are
*exactly* as telling as each other — mathematically identical — came out
differing in the fifteenth decimal place. CPython and V8 rounded that last bit
differently, so the two implementations showed a coordinator different
explanations for the same sentence. That was a real bug in the Python,
reachable on any machine, and it was unfindable while there was only one
implementation to look at. Ties are now rounded flat and broken alphabetically.

### What deliberately does not go offline

**Duplicate detection.** It compares your description against the reports
everyone else has open right now, and that list is precisely what this app
refuses to keep on a device. The line is the same one the service worker
follows everywhere else:

> A priority is a fact about the words you typed, and it travels.
> A duplicate is a fact about everybody else, and it does not.

So offline the panel shows the priority and says, in a sentence, that nothing
has checked whether somebody has already reported this, and that the server
will when it sends. Not an empty list — `duplicates: []` reads as *we looked
and found none*, which is the one thing it must not mean.

## Duplicates are caught when the reports arrive

The duplicate check used to run only while somebody was online and typing,
which meant it never ran for a report filed offline — and those are the
reports most likely to duplicate each other.

Two neighbours on the same street, both with no signal, both file *"water
rising on Kingsland"*. Neither can see the other's report. Both sync. Two
reports for one incident, six people heading to one address, and the check
built to prevent exactly that was the one thing that could not run.

`link_duplicate` now runs on arrival, for every report, however it got here.
Because reports are written one at a time, comparing against every open report
*at the moment this one is written* includes the ones that landed seconds
earlier in the same batch. That is the property the fix turns on, and there is
a test that files three at once and checks each was compared against the ones
beside it.

Two guards on top of the text similarity:

- **Distance is a veto.** More than 500 m apart and it is a different
  incident, however alike the wording. A flood on a road of the same name
  three suburbs over shares all its vocabulary and none of its emergency.
  That radius is chosen, not measured.
- **Resolved reports are not candidates.** Linking to something already dealt
  with sends nobody anywhere.

**It links; it never merges.** Both reports stay open and both stay joinable.
TF-IDF over fifty-five examples is worth a coordinator's glance and nowhere
near good enough to fold one person's call for help into another's.

**The feed then counts them as one incident**, which is the part that actually
buys anything. Two reports of one flood with three responders each renders as
two comfortably staffed rows, and the feed whose job is to make convergence
visible would be hiding it in its own data. Grouped, it reads *6 responding to
1 incident*, counts each person once even if they joined both, and counts once
in the coverage-gap banner. See [decisions.md](decisions.md) for the four
things that had to be true for that to be honest rather than convenient.

## A report says when it was written

The same fix as the check-in queue, for a sharper reason.

A check-in stamped on arrival silently cancels an overdue alarm. A report
stamped on arrival is worse than silent, it is loud and wrong: a description
written forty minutes ago is a description of a house that may already have
been cleared, and rendering it as breaking news sends the next available
person to an address nobody needs to be at.

So a report carries `created_at` — when it was written, a client claim bounded
exactly like a check-in's — and `received_at`, which is ours. The feed orders
on the first, which is the honest place for it, and where the gap is big
enough to matter the card says so:

> **Written 40 minutes ago, reached us later.** Filed with no signal. It may
> already have been dealt with.

### When a report runs out of time

Twelve hours, matching what the server will accept. Past that it cannot be
sent, and the first version of this simply filtered it out of the queue on the
next read — silently, and without ever removing it from storage.

That was the project's own argument used against it. Somebody pressed submit,
read *"saved on this phone"*, and half a day later the report was gone with
nothing anywhere saying so — the exact silent disappearance the board exists
to prevent, happening inside the thing that promised to keep it.

Now it moves to its own key and the next time the report form opens, before
anything else, the page says a report never sent, when it was written, and
**what it said** — the queue is the only place those words still exist. It
stays on screen until the person presses "I've read this". It does not offer a
retry, because the server would refuse it and be right to. It offers the text
back and the decision.

`MAX_AGE_HOURS` in the browser and `MAX_BACKDATE_HOURS` on the server have to
agree, in two languages, with nothing else connecting them — so a test reads
both and fails if they drift.

### Still missing

Everything in the queue is a *new* report. A report **edited** offline, or
resolved offline, still needs a connection — that needs conflict rules we
haven't earned the right to guess at yet.

### What the server already does

`POST /api/checkin` accepts an optional `happened_at`:

```json
{ "lat": 29.7858, "lng": -95.8244, "happened_at": "2026-08-02T03:15:00+00:00" }
```

This exists because of a bug that would otherwise be invisible. Without it,
a check-in made at 14:20 and synced at 15:20 gets stamped 15:20 — so the
overdue timer restarts from the sync, and a responder who was silent through
their entire window comes back green the moment their phone reconnects. The
alarm that correctly fired gets silently cancelled by their phone finding a
bar of signal.

So the timer runs off `happened_at`. It's a claim from a client, so it's
bounded: more than two minutes in the future is rejected, more than twelve
hours old is rejected, slightly-ahead is clamped to now rather than stored in
the future. Both times are kept, and the board marks rows that arrived late,
so a coordinator can see somebody was out of contact rather than just seeing
a green row.

### Map tiles

Built, and narrower than it sounds.

`static/scripts/sw.js` is a service worker that serves map tiles cache-first.
A tile we already have is always as good as one we would fetch — a road is in
the same place next week — so the map keeps drawing with no connection, in
the area you have already looked at.

It is registered from the map page only, and only over HTTPS or localhost,
because browsers refuse to register a worker anywhere else. During development
over a LAN address it quietly does nothing.

**The cache is capped** at 1,200 tiles, roughly 20 MB, oldest evicted first.
Somebody's phone is not ours to fill.

**Nothing that describes other people is cached.** Not the feed, not the
board, not a report. A cached report list is a lie about who currently needs
help. There's a test that fails if either is added to the shell list.

What *is* kept alongside the tiles: the app's own files, the trained
classifier, and one page — the blank report form, so the offline queue has
something to be reached through. All three pass the same test: they say
nothing about who needs help right now.

Note the ceiling, which no amount of code moves: **a tile cache can only ever
cover where you have already been.** It cannot pre-fetch somewhere you have
never looked, which is often exactly where the disaster is. Bulk downloading
an area to get around that is explicitly forbidden by the OpenStreetMap tile
usage policy and gets real users blocked — there's a test that fails if
somebody adds it. Real offline coverage needs your own tile server or an
offline format like MBTiles, which is a different project.

So the honest description is: **the map keeps working where you have already
been.** That is worth having and it is not an offline map.

---

## What we keep on the phone, and what we refuse to

DiresQ installs. Add it to your home screen and it opens without browser
chrome, with its own icon, and it keeps working with the radio off. That
raised a question we had to answer properly rather than by default:

**when there is no network, what should the app show you?**

The tempting answer is *everything it had a minute ago*. Cache the feed, cache
the board, and the app looks like it still works. We didn't, and the reason is
the whole argument of this project.

A cached feed is a **claim about other people, frozen at a moment that has
passed.** Somebody reading one in a flood drives to an address that was
cleared twenty minutes ago, while the street that filed thirty seconds later
is invisible to them — and nothing on screen tells them which is which. The
board has the same problem in a worse form: a saved row saying a responder is
fine is exactly the reassurance the dead man's switch exists to withhold.

So the rule the service worker follows is:

> **Keep what stays true with no network. Refuse to keep what stops being true
> the moment it is written.**

Sorted by that rule:

| | Kept? | Why |
| --- | --- | --- |
| Map tiles you've loaded | Yes | The road is where it was last week |
| Stylesheets, scripts, icons | Yes | They are the app, not a claim about the world |
| **Your own assignment** | **Yes** | You committed to it. No server can un-commit you while you're out of contact |
| Your check-in deadline | Yes | Derived from when you joined and when you last checked in — both already past |
| Your last known position | Yes | It is a record of where you were, not where you are |
| Queued check-ins | Yes | Yours, unsent, and timestamped when you pressed the button |
| **Queued reports** | **Yes** | Yours, unsent, carrying the id that stops them arriving twice |
| The trained classifier | Yes | A frozen table of word counts. It describes English, not Katy |
| The blank report form | Yes | An empty form. Without it the queue has no door |
| The report feed | **No** | A list of who needs help, and it is wrong within a minute |
| The accountability board | **No** | Other people's safety, and a stale copy is reassuring in exactly the wrong way |
| Which reports look like duplicates | **No** | It is a fact about everybody else's reports, so it cannot travel. The server checks on arrival |

That is what `/api/me` is for. It returns your own state and nobody else's,
and it is the only *response* the worker is allowed to store — there's a test
asserting the list of cached URLs is exactly `["/api/me"]`, another asserting
the only page it keeps is `/report/new`, and another that fails if any other
responder's name appears in the payload.

Offline, you get the job you took, when you're due to check in, where you last
were, and a line saying when that was saved. Where the live feed would be,
there is a sentence explaining that it is not saved to this device and why.

**An honest empty space beats a convincing stale one.** That is the same
reason the classifier says nothing below 45% confidence, and the same reason
the ETA parser refuses a guess rather than inventing a deadline.

---

## If we carried on

In the order we'd actually do them:

1. **Queue reports too**, not just check-ins. Harder, because a report filed
   offline may need reconciling against one somebody else already filed for
   the same thing.
2. **Signing the packet with a longer tag**, once there is bandwidth budget to
   spend on it. Four bytes is a deliberate trade, not a comfortable one.
3. **One node**, built and carried around Katy to find out what the range
   really is, because published LoRa range figures and a suburb with trees
   and houses in it are two different things.
4. **Tiles**, last. Tiles before the queue would have been backwards.
