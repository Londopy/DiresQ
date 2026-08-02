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
| Check-in packet format | **Built.** 18 bytes, signed, tested |
| Uplink endpoint | **Built.** `POST /api/uplink`, verifies before writing |
| Gateway program | **Built.** `tools/gateway.py`, tested over a pipe |
| Backdated check-ins | **Built.** The server judges a check-in on when it was made |
| Node key issue and rotation | **Built.** `flask --app app node-key <user>` |
| Radio hardware and firmware | **Not built.** We have no radios |
| Serial mode of the gateway | **Written, never run.** No hardware to run it against |
| Browser offline queue | **Not built.** This is the big one |
| Offline map tiles | **Not built** |

If you read nothing else: **the offline queue does not exist.** The server is
ready for one. Nothing in the browser queues anything today. Close the tab
with no signal and the check-in is gone.

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

`transport.py`. A check-in is fourteen bytes:

| Bytes | Field |
| --- | --- |
| 1 | protocol version |
| 1 | packet type |
| 2 | responder id |
| 4 | latitude × 100000 |
| 4 | longitude × 100000 |
| 2 | age in minutes |

Plus four bytes of signature: **eighteen total.**

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

Eighteen bytes does not fit DR0. If it had to, the check-in would need
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

**What it does not stop:** *replay*. Somebody who records a valid packet off
the air can send it again later and move that pin. Fixing that needs a
counter in the packet and a record of the last one accepted — another two
bytes and a table. It is the first thing we'd add.

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
one button. Press it, it reads the GPS, packs eighteen bytes, signs them with
its key, transmits, sleeps.

We don't have the parts, so we haven't written the firmware. Untested
firmware in the repo would look like a feature and be a liability.

---

## The offline queue

**Not built.** The half that is built is the half that's easy to get wrong,
so it's worth being precise about which half.

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

### What is missing

Everything in the browser:

- Catch a failed `fetch` and put the check-in in `localStorage` with the time
  it was made.
- Retry on `online`, and on a timer.
- Show the person how many are queued — a queue you can't see is a queue you
  don't trust.
- Drop anything older than the twelve-hour bound instead of sending it to be
  rejected.
- Handle the same check-in arriving twice, because "did that send?" is the
  question a flaky connection is built to make unanswerable.

That last one is the trap. The obvious implementation double-writes on a
retry, and the fix is a client-generated id on each check-in that the server
treats as unique. We haven't built it, so it isn't in the schema, and adding
it later is a migration.

### Offline map tiles

Also not built. A service worker caching tiles cache-first would let the map
work in an area you'd already looked at.

Note the ceiling: **a tile cache can only ever cover where you have already
been.** It cannot pre-fetch somewhere you've never looked, which is often
exactly where the disaster is. And bulk-downloading tiles to get around that
is forbidden by the OpenStreetMap tile usage policy — so if you want real
offline coverage of an area, you need your own tile server or an offline
format like MBTiles, which is a different project.

---

## If we carried on

In the order we'd actually do them:

1. **The browser queue.** The biggest gap, and the server is already waiting
   for it.
2. **A counter in the packet**, closing the replay hole.
3. **Deduplication ids on check-ins**, which the queue needs anyway.
4. **One node**, built and carried around Katy to find out what the range
   really is, because published LoRa range figures and a suburb with trees
   and houses in it are two different things.
5. **Tiles**, last, because tiles without the queue is backwards.
