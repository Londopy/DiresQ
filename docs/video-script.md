# Demo video — shooting script

Target: **2:30**. Hard ceiling 3:00.

Read this once, rehearse twice, record on the third. Do not read it word for
word on camera — read it until you know the beats, then talk.

**Before you start:**

```bash
flask --app app init-db
flask --app app seed
flask --app app run
```

Note: `run`, **not** `--debug`. The reloader prints noise mid-take. Shrink or
move the terminal off-screen — the feed polls every four seconds and a
scrolling wall of `GET /api/reports 200` looks like something is wrong.

Browser: one window, no bookmarks bar, no other tabs. Zoom 110% so text reads
on a laptop screen. Sign in as `londo` / `diresq` **before** you hit record.

---

## 0:00 — 0:20 · The problem

**On screen:** just you, or a black title card reading *DiresQ*. No app yet.

> During Hurricane Harvey, civilians in fishing boats rescued thousands of
> people. Some of them drowned doing it.
>
> Every disaster app I could find maps the disaster. None of them track the
> people going *into* it. Nobody logs that a volunteer went out, nobody knows
> where they are, and nobody knows when to start worrying.
>
> That's what we built.

**Do not skip this.** Twenty seconds of problem is what makes the next two
minutes mean anything. A demo that opens on a UI is a demo about a UI.

---

## 0:20 — 0:45 · The feed, and the gap

**On screen:** cut to `/` — the feed, already loaded.

> This is a live incident. Eight reports.

**Point at the amber banner.**

> Three of these have nobody going to them. Not understaffed — nobody has said
> they're coming at all.

**Scroll so the Mayde Creek card is visible next to an untouched one.**

> Here's a car in a creek with four people on it. And sitting *above* it,
> higher up the feed, is a report nobody has touched.
>
> That ordering is deliberate. Within a severity band, a gap outranks a queue.

**Beat. Let it sit for a second.** This is the smartest thing in the app and
it's easy to blow past.

---

## 0:45 — 1:15 · Join, and the ETA

**On screen:** click the top HIGH report → detail page.

> I've got a boat, so I'll take this one.

**Type `30 min` in the ETA box. Say it out loud as you type.**

> I type thirty minutes the way I'd actually say it. That's not a dropdown —
> it's parsed, and if it isn't confident it refuses rather than guessing,
> because a wrong deadline is worse than none.

**Click join. The card updates.**

> Now it says one en route. Anyone opening the app sees this report is
> covered, and goes somewhere that isn't.

---

## 1:15 — 1:50 · The board

**On screen:** `/board`.

> This is the part that doesn't exist anywhere else. Everyone who's out, what
> they're doing, and how long since anyone heard from them.

**Point at the red row — `s.reyes`.**

> Sam went to a roof job forty-seven minutes ago and hasn't checked in since.
> Nobody had to notice that. The row went red on its own, and the page
> refreshes itself, so it would have gone red with nobody watching.

**Scroll to show the last known position on that row.**

> Last known position. That's where you'd start looking.

---

## 1:50 — 2:10 · The dead man's switch

**On screen:** back to `/` — the feed.

> But a red row only helps if somebody's looking at the board.

**Point at the auto-filed report — *"No contact from s.reyes for 47 minutes"* —
with the `auto` badge.**

> So after fifteen minutes past a deadline, the server stops waiting to be
> noticed and files a report *about the responder*, at their last known
> position. Nobody filed this. It's in the feed like any other job, and
> somebody can go and find him.
>
> The app that tracks the people going in now sends help back out for them.

**This is the emotional peak of the video. Slow down. Don't rush the last
line.**

---

## 2:10 — 2:25 · Offline

**On screen:** a report page you're joined to. DevTools open, Network tab
visible, **Offline** ticked.

> One more thing. This is the app with the network switched off.

**Press *Check in*. The button reads "Saved — will send". Pill appears
bottom-left.**

> It's kept on the phone with the time I pressed the button — not the time it
> eventually sends. That matters: otherwise a responder who was silent for an
> hour comes back green the moment their phone finds signal, and the alarm
> that correctly fired gets cancelled by the network recovering.

**Untick Offline. Within fifteen seconds the pill disappears.**

> And back.

If the sync is slow on camera, cut. Don't sit watching a pill.

---

## 2:25 — 2:40 · Close

**On screen:** either the board, or the docs site.

> It's not an emergency service and it says so on every page. It's never been
> used in a real disaster. The limitations are written down in the repo,
> including the ones we couldn't fix.
>
> Everything a responder does gets logged, so it exports an ICS-214 — the
> activity log agencies already keep — built from records instead of memory.
>
> Two of us, three days.

**End card:** repo URL + the docs site URL. Hold three seconds.

---

## Things that will go wrong

| Problem | Fix |
| --- | --- |
| Feed shows 5 reports, board empty | Old database. `init-db` then `seed` |
| Terminal scrolling in shot | Move it off-screen before recording |
| Auto-filed report not there yet | Load `/board` once — the sweep runs on page load |
| Offline sync takes ages | Cut it. Or run `flask --app app sweep` beforehand |
| Nervous, rushing | You are. Everyone does. Slow down 20% |

## What to cut if you're over time

In this order:

1. The ETA parsing detail (0:45–1:15) — trim to just "I type it how I'd say it"
2. The ICS-214 line in the close
3. The last-known-position beat on the board

**Never cut:** the problem statement, the gap-outranks-queue beat, or the dead
man's switch. Those three are the project.

## Recording notes

- **One take per section**, not one take for the whole thing. Stitch after.
  Trying to nail 2:30 in one pass is how you end up at 3am with twelve bad
  takes.
- **Talk 15% slower than feels natural.** It always sounds rushed on playback.
- Silence while something loads is fine. Filler words are not.
- If you fluff a line, pause two seconds and say it again — easy to cut.
- Record the voiceover separately if reading and clicking at once is hard.
  Screen capture first, narrate over it second.
