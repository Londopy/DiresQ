# Tasks

Shared list. Ordered by what actually blocks the submission, not by what's
fun. Anyone can take anything — say so in Discord first if it's in someone
else's files.

Build cutoff: **______** (doc says at least 3h before submission — pick a
number and put it here)

---

## Do these first

- [ ] **Run the demo yourself, end to end.** Not the test client — a real
      browser, real login, `DIRESQ_DEV_USER` unset. Nobody has ever done this.
      File a report, join it, go on scene, mark overstaffed, wait for the
      timer, check in. Write down anything that looks wrong.
- [ ] **Record the demo video.** 2–3 min. Script is in the project doc. The
      Astro site is gated on this existing, and it's what you're judged on.
- [ ] Rehearse it three times and time it. First take is always too long.
- [ ] Test at phone width. Nobody has looked at this on a small screen.
- [ ] Try to break it: empty forms, GPS denied, double-join, silly input,
      resolve twice, flag your own report.

## Demo and submission

Currently unclaimed — Londo picking these up unless someone says otherwise.

- [ ] Seed content that reads like real Katy incidents. The five in `seed_data`
      are fine but thin — real street names, believable descriptions.
- [ ] Demo video script, written out line by line before recording.
- [ ] Slides, if the format needs them.
- [ ] Screenshots for the README.
- [ ] Devpost writeup — tagline, about, tags, links.

## Skythe — frontend

Londo scaffolded these to match the Catppuccin variables, but they've never
been through a designer. They're functional, not designed. Restyle freely,
move markup, rename classes — the backend doesn't care what any of it looks
like.

- [ ] `/board` — `board.css`. The hero screen and the last shot of the video.
      Overdue rows should be impossible to miss.
- [ ] Report page actions — `actions.css`. Join, status, staffing buttons,
      check in, resolve.
- [ ] `/triage` — `triage.css`. Four questions, wants to feel calm and fast.
- [ ] `/credits` — `credits.css`. The hidden page.
- [ ] `nav.css` — the Board link and its overdue badge, on every page.
- [ ] Responder pins on the map. Data is already in `/api/responders`.
- [ ] Phone width, everywhere. Nobody has looked.
- [ ] Role picker on signup — everyone is a responder right now.

## Still unbuilt

- [ ] **Responder pins on the map.** Board shows coordinates, map doesn't plot
      them. Your 1:40 beat says "last known position". Data is already in
      `/api/responders`.
- [ ] **Offline queue** *(frontend — Skythe unless she'd rather not)*.
      Check-ins queue in localStorage, sync on reconnect. Real differentiator
      and a scripted beat at 2:00.
- [ ] **Offline map tiles** *(frontend)*. Service worker, cache-first. Only
      after the queue works — tiles without the queue is backwards. Do NOT
      bulk-download tiles, the OSM usage policy forbids it.
- [ ] **Astro site.** Content is already written in `docs/`. Mostly a deploy
      job. First thing to cut.

## Worth doing if there's time

- [ ] Dead man's switch: 10 min after someone goes overdue, auto-file a report
      at their last known position. This is the thesis finishing itself.
- [ ] ICS-214 activity log export. Produces a form a real agency files.
- [ ] Coverage gap banner: "nobody is going here" on the report with zero
      responders furthest from anyone.
- [ ] Transport seam — check-ins from a pipe or serial, proving the app takes
      input from something that isn't a browser. The honest version of the
      LoRa idea.
- [ ] Role picker on signup. Everyone is a responder right now.

## Not doing

- LoRa. No radios, so it can't be tested, and untested code isn't a feature.
  It's a roadmap line in the video.
- Identity verification. No honest weekend version.
- Chat, push notifications, dark mode, OAuth.

## Housekeeping

- [ ] Reconcile the project doc — it still has the old `severity` / `needs`
      vocabulary and integer priorities in places.
- [ ] Decide whether hardware is in scope. The newer doc dropped the Cardputer
      section entirely and nobody said whether that was deliberate.
- [ ] Tell Skythe about `nav.css`, `actions.css`, `triage.css`, `credits.css` —
      new stylesheets she may want to bring in line.
- [ ] At the end: `patchnotes CHANGELOG.md bump 1.0.0`, `git tag v1.0.0`,
      `git push --tags`.
