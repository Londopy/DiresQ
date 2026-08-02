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
- [x] Try to break it — done as a test class, `TestTryingToBreakIt`. Empty
      forms, denied GPS, junk coordinates, script tags, a semicolon and a
      DROP TABLE, double-join, resolve twice, flag your own report, moving
      someone else's assignment, a report id of `banana`. One real bug came
      out of it. Still worth doing once by hand in a browser.

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
- [ ] `banner.css` — the coverage gap banner at the top of the feed, and the
      `auto` badge on a report the server filed itself.
- [ ] `authform.css` — Caps Lock warning, the show/hide password button, the
      hint lines under the sign-up fields.
- [ ] `disclaimer.css` — the `/disclaimer` page, plus the red safety note
      above the report form and beside the triage result.
- [ ] Responder pins on the map. Data is already in `/api/responders`.
- [ ] Phone width, everywhere. Nobody has looked.
- [ ] Role picker on signup — everyone is a responder right now.

**Two things that changed under her feet, both additive:**

- `templates/report.html` loads `report.js` as `type="module"` now, because it
  imports the offline queue. Nothing else changed about it.
- `a11y.css` is linked on every page and is the one stylesheet not to freely
  restyle — it holds the focus rings, the skip link and two contrast fixes.
  Overriding a colour in it will fail a test, on purpose.

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
- [x] **Astro site.** Built under `site/`, pages generated from `docs/` at
      build time. Still needs Pages switched on in the repo settings — see
      below.
- [ ] **Turn on GitHub Pages.** Settings → Pages → Source: *GitHub Actions*.
      The `pages.yml` workflow deploys on every push that touches `site/` or
      `docs/`. It will fail until this is switched on, and the error doesn't
      say why.
- [ ] **Commit `site/package-lock.json`.** Run `npm install` in `site/` once
      and commit the lockfile. The workflow copes without one, but `npm ci` is
      faster and stricter, and `cache: npm` can only be turned back on in
      `pages.yml` once the lockfile exists.

## Done since the list was written

- [x] Dead man's switch. Fifteen minutes past deadline, not ten — ten made
      every dropped signal a callout.
- [x] ICS-214 activity log export, from `/board`.
- [x] Coverage gap banner on the feed.
- [x] Transport seam: `transport.py` plus `/api/uplink`, now signed per node,
      plus `tools/gateway.py` to feed it from a pipe or a serial port.
- [x] `flask --app app sweep`, so the dead man's switch can run on a schedule
      rather than on somebody having a tab open.
- [x] Login and sign-up guardrails, and the open redirect they turned up.

## Worth doing if there's time

- [ ] Role picker on signup. Everyone is a responder right now.
- [ ] **Queue reports offline too**, not just check-ins. Harder — a report
      filed offline may need reconciling against one somebody else already
      filed for the same thing.
- [ ] A counter in the uplink packet, closing the replay hole. Two more bytes
      and a table of the last packet accepted per node.

## Not doing

- LoRa. No radios, so it can't be tested, and untested code isn't a feature.
  It's a roadmap line in the video.
- Identity verification. No honest weekend version.
- Chat, push notifications, dark mode, OAuth.

## Housekeeping

- [x] Reconcile the project doc — differences written up in
      `docs/project-doc-errata.md`, exact old/new. Someone still has to paste
      the corrections into the actual doc; I can only write the list.
- [x] Hardware is out of scope. The Cardputer section vanished between doc
      versions and nobody said so out loud; recorded in the errata. We have no
      device, so there is nothing to film. `tools/gateway.py` is the same idea
      without one.
- [ ] Tell Skythe about `nav.css`, `actions.css`, `triage.css`, `credits.css` —
      new stylesheets she may want to bring in line.
- [ ] At the end: `patchnotes CHANGELOG.md bump 1.0.0`, `git tag v1.0.0`,
      `git push --tags`.
