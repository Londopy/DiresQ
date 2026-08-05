# Filming the mechanism

DiresQ's central claim is that a report files itself about a responder who has
gone quiet. On a real clock that takes forty-five minutes and nothing visible
happens for forty-four of them. `DIRESQ_DEMO_SPEED` scales the clock so the
whole sequence plays out on camera, using the production escalation code
unchanged.

## Run it

```bash
export DIRESQ_DEMO_SPEED=60          # 1 real second = 1 incident minute
flask --app app init-db
flask --app app seed
flask --app app run
```

Open `/board`, signed in as `londo` / `diresq`. The banner turns itself on and
states the speed — that is deliberate and should stay in frame. A page showing
accelerated time has to say so, for the same reason the board shows how long
since the last sweep.

## What happens, and when

The clock starts when the **server process** starts, not when you seed. Seed
and film in the same sitting or the numbers will have run away from you.

At 60×, counting from page load:

| Real time | On screen |
| --- | --- |
| 0s | `n.farrow` — *due in 5 min*, EN ROUTE |
| ~5s | farrow's row turns **red**, OVERDUE |
| ~9s | `h.lindqvist` follows, then adeyemi, skythe |
| **~20s** | **"No contact from n.farrow for 20 minutes" appears in the feed** |

That last row is the shot. Nobody clicked anything.

`s.reyes` is already red at seed and escalates on the first sweep — that is the
"before" state, not a bug. It is what a board looks like when the thing has
already happened to somebody.

## Choosing a speed

Two numbers set the pacing, both in `app.py`:

- `DEFAULT_CHECKIN_MINUTES = 30` and the seeded ETA put farrow's deadline
  **5 incident-minutes** after load
- `SILENT_ESCALATE_MINUTES = 15` is the silence the server waits out

So at speed *S*: **red at 300/S seconds, report at 1200/S seconds.**

| Speed | To red | To the auto-report | Use |
| --- | --- | --- | --- |
| 30 | 10s | 40s | a slow, legible walkthrough |
| **60** | **5s** | **20s** | **the default; fits a 90-second video** |
| 120 | 2.5s | 10s | a tight cut, countdown barely readable |
| 180 | 1.7s | 6.7s | too fast to watch — the board polls every 3s |

Above ~120 the three-second board refresh becomes the limit: the countdown
jumps by more than it counts down, which looks broken rather than fast.

## The shot list

1. **Cold open on the red board.** No titles, no "hi we're team DiresQ". First
   frame is a board with a red row.
2. Voiceover over that frame — the Harvey dispatcher, from Smith et al. (2018):
   *"can we account for everyone."*
3. Cut back to a fresh load. `n.farrow`, EN ROUTE, *due in 5 min*, counting.
4. Hold. Let it turn red on camera. Do not cut away.
5. Hold again. The feed gains a report titled **"No contact from n.farrow for
   20 minutes"**, pinned at their last check-in.
6. Only now, thirty seconds of what's underneath: offline queue, signed radio
   packets, 591 tests.

Steps 3–5 are the product. Everything before is framing and everything after is
evidence.

## Before you record

- [ ] `DIRESQ_DEMO_SPEED` is set **in the shell that runs the server**, not the
      one that seeds — it is read once at import
- [ ] re-seed immediately before recording (`init-db` then `seed`)
- [ ] the banner is visible in frame at least once
- [ ] window is wide enough that the countdown and the feed are both on screen,
      so the causal link is visible in one shot rather than assembled in the cut

## Never set this in production

`DIRESQ_DEMO_SPEED` must be unset or `1` anywhere real. At any other value every
deadline, escalation and elapsed-time display in the app is wrong by that
factor. The default is 1, an unparseable value falls back to 1, and `0` is
rejected because it would stop time.

Login lockout and the ICS-214 export filename deliberately stay on the real
clock — the first is a security control, the second names a file on somebody's
disk.
