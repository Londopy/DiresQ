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
| Radio hardware and firmware | **Not built.** We have no radios |
| Serial mode of the gateway | **Written, never run.** No hardware to run it against |
| Map tiles kept once seen | **Built.** Capped, no pre-fetching |

If you read nothing else: **check-ins survive having no signal, and the map
keeps drawing where you have already been.** Reports, the feed and the board
still need a connection. The radio is not built.

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

### Still missing

The queue covers check-ins. Filing a *report* offline does not work — that
needs the same treatment and a way to reconcile a report that may already
exist. Check-ins came first because they are the message that says you are
alive.

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

**Nothing else is cached.** Not the feed, not the API, not a report. A cached
report list is a lie about who currently needs help, and check-ins already
have the queue. There's a test that fails if either is added to the shell
list.

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
