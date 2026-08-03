# Demo video — shooting script

Target: **2:50**. Hard ceiling 3:00. The offline section at 2:10 is the one
that earns the extra twenty seconds — it is the only part of the video where
the app does something a viewer does not expect.

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

## 2:10 — 2:45 · Offline

**The best thirty seconds in the video. Rehearse this one. Everything else is
a page you point at; this is the only part where the app does something a
viewer does not expect.**

**Setup before you roll:** open `/report/new` **once with the network on**, so
the service worker has stored the form. Then DevTools → Network → tick
**Offline**. Leave the Network tab visible in shot so nobody thinks you faked
it.

**On screen:** `/report/new`, loaded with the network off.

> This is the app with the network switched off. Not degraded — off.

**Type into the description box: *"water rising on Kingsland, two adults
upstairs, can't get out"*. Wait for the suggestion panel.**

> It still reads what I wrote and suggests HIGH, and tells me it decided that
> from *rising*, *upstairs*. That's the same classifier, the same trained
> model, running on the phone — because the person filing at 2am from a
> flooded house is the person most likely to have no signal, and they were the
> one person it never used to reach.

**Point at the grey box underneath.**

> And it says what it *can't* do. It hasn't checked whether somebody already
> reported this, because that needs everybody else's reports and we refuse to
> keep those on a phone. It doesn't show an empty list — an empty list would
> read as "we checked, there's nothing".

**Press Submit.**

> Saved on this phone. Not sent. Nobody has seen it.

**Untick Offline. Wait for it to sync, then go to `/`.**

> Now watch the feed.

**Point at the card.**

> *Written four minutes ago, reached us later* — because it describes a house
> as it was four minutes ago, and a card that renders that as breaking news
> sends somebody to an address that's already been cleared.
>
> And: *two reports, one incident.* My neighbour filed the same flood while
> they had no signal either. Neither of us could see the other's report.
> Both synced, both got compared on arrival, and the feed put them in one row.
>
> Three responders on each used to read as two comfortably staffed jobs.
> Now it reads **six people going to one address** — which is the entire
> reason this project exists.

**Beat. That's the closing argument.**

If the sync is slow on camera, cut between "not sent" and the feed. Don't sit
watching a pill.

---

## 2:45 — 3:00 · Close

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
| Offline sync takes ages | Cut between "not sent" and the feed |
| `/report/new` won't load offline | The worker only keeps it after you've opened it once **online**. Do that before ticking Offline |
| No suggestion panel offline | Same cause — the model is cached on first online load. Reload the form once with the network on |
| Only one report in the group | File the neighbour's report first, from the same street, before you roll |
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

---

# The README GIF

A separate, shorter thing. **25 seconds, no sound, loops forever.**

Record it **after** the video, not before. Same app state, same setup, and by
then you'll have clicked through it four times and know exactly where
everything is. Doing the GIF first is how the video ends up not existing.

## What it has to do

It has one job: make somebody scrolling past stop, and understand that **a
report appeared that nobody filed.**

No narration, no captions, no cursor waving about. It should look like the app
doing something by itself, because that is literally what is happening.

## Setup

```bash
python tools/demo_state.py --in 12
```

That winds `s.reyes`'s clock so the row goes red twelve seconds from now,
while you're recording. `--reset` clears auto-filed reports between takes.

Then load `/board` and start the recorder.

## The three beats

| Time | Shot | What the eye catches |
| --- | --- | --- |
| 0–7s | **Feed**, slow scroll | Amber banner: *"3 reports with nobody going."* A card with four responders sitting *below* one with none |
| 7–16s | **Board** | `s.reyes` flips green to **red**, on its own, nobody touching anything |
| 16–25s | **Feed** again | New HIGH card at the top: *"No contact from s.reyes for 47 minutes"*, with the `auto` badge |

It loops back to the calm feed, which makes the red feel like it is happening
*again*. That's the product in one loop with no words.

## Settings

- **ScreenToGif** (Windows, free) — record, trim and export in one place, and
  it will drop frames to hit a size target.
- **Crop out all browser chrome.** No tabs, no address bar. It is a picture of
  an app, not of Firefox.
- **~1100px wide, 12 fps.** Keep it under 5 MB — GitHub allows 10 but anything
  larger loads slowly and people scroll past while it thinks.
- Hold the last frame about a second before it loops, so the auto-filed card
  registers before it cuts.

## In the README

Directly under the badge block, inside the existing `<div align="center">`:

```markdown
<img src="docs/demo.gif"
     alt="The accountability board turning red when a responder stops checking
          in, and the report DiresQ files automatically at their last known
          position"
     width="820">
```

The alt text matters. It is the only version of the demo a screen reader user
gets, and it is the sentence you want a judge to read anyway.

## If you only have time for 15 seconds

Cut the feed scroll. Run red → auto-report. That's still the whole thesis, and
a shorter loop gets watched twice.

## A second GIF, only if there's time

The classifier, 10 seconds: type *"water rising fast, grandmother upstairs and
cannot walk"* into the report box and let the suggestion appear —
`HIGH · 95% sure · boat`, with the words that caused it.

It's a good shot because the reasoning is visible, which is the whole argument
for not using a language model. But it's second priority. The board going red
is the project; this is a feature.
