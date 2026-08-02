# API

Pages are server-rendered Flask templates. Anything under `/api` returns JSON.
Everything except `/login`, `/signup` and `/credits` needs a session.

---

## Pages

| Method | Route | |
| --- | --- | --- |
| `GET` | `/` | Report feed, sorted worst first |
| `GET` | `/board` | Accountability board, refreshes every 3s |
| `GET` | `/map` | Every located report as a pin |
| `GET` | `/triage` | START triage helper |
| `GET` `POST` | `/report/new` | File a report |
| `GET` | `/report/<id>` | One report and everyone assigned to it |
| `GET` `POST` | `/login` `/signup` | |
| `POST` | `/logout` | |

## Reports

| Method | Route | Body | |
| --- | --- | --- | --- |
| `GET` | `/api/reports` | | The feed as JSON |
| `POST` | `/report/<id>/rescue` | `eta_text` *(optional)* | Join. Any number of people can |
| `POST` | `/report/<id>/resolve` | | Close it. Reporter or on-scene only |
| `POST` | `/api/reports/<id>/staffing` | `staffing` | On-scene responders only |

`staffing` is one of `need_more`, `adequate`, `overstaffed`, `stood_down`.

Where responders disagree, the most cautious wins. The report's staffing is
derived from votes, never stored.

## Responders

| Method | Route | Body | |
| --- | --- | --- | --- |
| `GET` | `/api/responders` | | The board |
| `POST` | `/api/assignments/<id>/status` | `status` | Your own assignment only |
| `POST` | `/api/checkin` | `lat`, `lng`, `happened_at`, `client_id` *(all optional)* | Resets your timer |

`status` moves forward only: `en_route` → `on_scene` → `cleared`. Anything
else is a 400. Clearing retracts your staffing vote.

### What a board row looks like

```json
{
  "id": 1,
  "username": "londo",
  "capabilities": ["boat", "medical"],
  "state": "overdue",
  "overdue": true,
  "minutes_since_contact": 47,
  "assignment": {
    "id": 3,
    "report_id": 1,
    "report_subject": "Water rising, 2 trapped",
    "status": "on_scene",
    "staffing_vote": "need_more",
    "eta": "2026-08-02T03:15:00+00:00",
    "joined_at": "2026-08-02T02:28:00+00:00"
  },
  "last_position": { "lat": 29.7858, "lng": -95.8244, "at": "..." }
}
```

`state` is `overdue`, `on_scene`, `en_route` or `available`, and rows arrive
already sorted in that order. Switch on that one field — don't recompute the
overdue rule client-side, and don't re-sort.

### Queued check-ins

A check-in made offline should say when it was really made, not when it
reached the server:

```json
{ "lat": 29.7858, "lng": -95.8244, "happened_at": "2026-08-02T03:15:00+00:00" }
```

Without it the timer would run from the sync time, so a responder who was
silent through their whole window would come back green the moment their
phone reconnected. The overdue calculation uses `happened_at`.

Send a `client_id` with it and resending is free:

```json
{ "lat": 29.7858, "lng": -95.8244, "client_id": "b2c1...", "happened_at": "..." }
```

The first one is a `201`. The same id again is a `200` with
`"duplicate": true` and the times from the row already written — the original
timestamp is not touched, so a retry can't make an old check-in look recent.
The same id from a different account is a `409`.

Ids are trimmed to 64 characters. A check-in without one is never treated as
a duplicate, so plain form posts with JavaScript off behave as before.

It's a client claim, so it's bounded: more than two minutes in the future is
rejected, more than 12 hours old is rejected, and anything slightly ahead is
clamped to now rather than stored in the future.

The server records both times. `last_position` on the board carries `at`
(when it was made), `received_at` (when we got it) and `synced_late`, so a
coordinator can see someone was out of contact rather than just seeing a
green row.

### Check-ins over a radio

| Method | Route | Body |
| --- | --- | --- |
| `POST` | `/api/uplink` | `packet` — base64 of an 18-byte signed check-in |

The same check-in, arriving as bytes instead of as a browser. A gateway has no
session, so the responder is named inside the packet and the packet is signed.

The id is read first, but only to decide whose key to check against — nothing
is written until the four-byte HMAC over the body matches that responder's
`node_key`. Get a key with `flask --app app node-key <username>`.

The layout, from `transport.py`:

| Bytes | Field |
| --- | --- |
| 1 | protocol version |
| 1 | packet type (1 = check-in) |
| 2 | responder id |
| 4 | latitude × 100000 |
| 4 | longitude × 100000 |
| 2 | age in minutes |
| 4 | HMAC-SHA256 over all of the above, truncated |

Eighteen bytes total, against a 53-byte budget — the smallest LoRa payload we
were willing to design for. Coordinates land within about a metre. The version
byte is signed too, so nobody can talk the server down to an older format.

It carries an *age*, not a timestamp: a node running off a battery in a flood
is the last clock you want to trust. The server subtracts it from now, and the
result goes through the same overdue rules as any other check-in.

A malformed or wrongly-signed packet is a 400 with a reason, not an error.
Radio links corrupt things, and so does anyone poking at the endpoint; that's
expected traffic.

An account that doesn't exist and an account with no key both answer 404 with
the same message, so the endpoint can't be used to find out which responder
ids are real.

`tools/gateway.py` speaks this, from a pipe or a serial port. What it cannot
do is replay protection — see [offline.md](offline.md).

## Export

| Method | Route | |
| --- | --- | --- |
| `GET` | `/export/ics214` | Activity log as CSV |

ICS 214 is the activity log an agency already keeps at a multi-agency scene.
Built from records rather than memory: every assignment, arrival, check-in and
auto-filed alert, in time order, with the resources-assigned table filled in
from who actually went out.

## Triage

| Method | Route | Body |
| --- | --- | --- |
| `POST` | `/api/triage` | `can_walk`, `breathing`, `respiratory_rate`, `has_radial_pulse`, `follows_commands` |

Returns the START category, the severity it maps to, and a plain-English
reason:

```json
{
  "priority": "Immediate",
  "severity": "HIGH",
  "explanation": "Breathing, circulation or responsiveness is outside safe limits..."
}
```

Only `can_walk` is always required. START stops as soon as it has an answer,
so the later fields aren't asked once the category is decided.

## Forms or JSON

The action endpoints answer both. Send JSON and you get JSON back. Post a
plain HTML form and you get a redirect plus a flashed message, so the buttons
work with JavaScript switched off.

A form post can include a `next` field to say where to return to. Only
same-site paths are honoured — anything starting with a scheme is ignored.

## Status codes

`200` ok · `201` created · `302` redirect · `400` bad input ·
`401` not signed in · `403` not yours · `404` not found

Joining a report you've already joined is not an error. It flashes a message
and redirects — the UNIQUE constraint on `(report_id, responder)` is what
makes a double-join impossible.
