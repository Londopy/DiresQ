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
| `POST` | `/api/checkin` | `lat`, `lng` | Resets your timer |

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
