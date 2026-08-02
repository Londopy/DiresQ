# DiresQ

Disaster response tracker. Logs the volunteers going in, not just where the
disaster is.

All notable changes to this project are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com), versioning follows
[Semantic Versioning](https://semver.org).

## [Unreleased]

### Added

- File a report from your phone: what is happening, how bad it is, and where.
  The location comes from tapping a map or from your device's GPS, so it works
  when you cannot name the street you are standing on.
- A feed of every open report, worst first. Each card shows how many people are
  already on their way and how many have arrived, so a report nobody has
  touched is visible as such.
- Search and filter the feed by severity.
- Open any report to see everything known about it, including every responder
  currently assigned to it rather than a single named rescuer.
- Join a report. Any number of people can join the same one. There is no claim
  lock, because in a real disaster the failure is convergence, not collision.
- Move yourself through en route, on scene, and cleared as you go, so the board
  reflects where people actually are. Buttons on the report page drive all of
  it: respond with an ETA, mark yourself on scene, signal staffing, check in,
  and resolve. Plain forms, so they work with JavaScript off.
- The report page lists everyone on it with their status and staffing vote, and
  only offers you the actions you are actually allowed to take.
- A real not-found page instead of an empty report.
- Once on scene, tell everyone else how staffed it is: needs more help,
  adequate, overstaffed, or stood down. Only people physically there can set
  this, because only they can see it.
- The accountability board at `/board`: every responder, what they are doing,
  where they were last seen, and how long since anyone heard from them. Anyone
  overdue sorts to the top and their row turns red. The page refreshes itself
  every three seconds, so someone going overdue appears without anyone
  touching the screen. It renders server-side first, so it still works with
  JavaScript switched off.
- Check in to reset your timer and update your position. A check-in can say
  when it was really made, so one queued while offline is judged on when it
  happened rather than when it synced. The board shows both times and marks
  the ones that arrived late.
- The feed refreshes itself, so a card reorders when someone two streets away
  changes their staffing signal.
- Flag a report as fake. One flag each; at three it drops out of the feed but
  stays visible to whoever filed it and anyone already on their way.
- Marking yourself on scene when your last check-in was over 500 m from the
  report raises a position mismatch on the board. It catches honest errors and
  lazy faking, not someone determined to lie.
- A triage helper for when you cannot judge how bad something is. Four
  questions anyone can answer without training or equipment, run through
  START, the protocol used at real multiple-casualty scenes. It returns a
  category, the severity that files the report as, and a plain-English reason.
  The severity dropdown still works; not every report is a casualty.
- When a responder stays silent fifteen minutes past their deadline, the
  server stops waiting to be noticed and files a report itself, at their last
  known position, marked as automatic. It behaves like any other report: it
  can be joined and resolved. Only ever one per person while it is open.
- A banner at the top of the feed counting the reports nobody is going to.
  Distinct from understaffed: it counts only the ones where nobody has said
  they are coming at all.
- Check-ins can arrive as bytes instead of as a browser. A check-in packs into
  twenty-two bytes, which fits a LoRa payload with room to spare, and `POST
  /api/uplink` accepts one from something that has no session to log in with.
  Both routes in go through the same code, so they cannot drift apart. The
  radio itself is not built.
- Every radio check-in is signed. Each responder gets a key when their account
  is made, and a packet that isn't signed with it is refused before anything
  is written. There is no transport security on a radio link, so the message
  has to prove where it came from on its own.
- A gateway program that forwards packets from a pipe or a serial port. It
  keeps listening through line noise, truncated packets, forged signatures and
  the server being unreachable, because a gateway that stops on the first bad
  line is a gateway that is down.
- `flask --app app sweep` files reports for anyone gone quiet, so the alarm
  can be put on a schedule instead of depending on somebody having a tab open.
- `flask --app app node-key <username>` shows or rotates a responder's radio
  key.
- Check in with no signal. The check-in is kept on your phone and sent when
  there is a connection again, judged on the moment you pressed the button
  rather than the moment it arrived. A pill in the corner says how many are
  waiting, because a queue you cannot see is a queue you do not trust.
- Sending the same check-in twice is free. Each one carries an id made before
  it is sent, so a retry after a dropped connection is recognised rather than
  logged again, and resending an old one cannot make it look recent.
- A written account of what works without a network and what does not, with a
  table saying plainly which parts are built.
- Export an ICS-214 Activity Log — the form agencies already keep at a
  multi-agency scene — built from logged records rather than from memory.
  Every assignment, arrival, check-in and automatic alert, in time order.
- A documentation site under `site/`, built from the same `docs/` files that
  live in the repo, so the two can never disagree. Twelve pages, including why
  this was built, how to run it, what the security model does and does not
  cover, and what the accessibility audit found, with
  a light that follows the cursor and transitions between pages that leave the
  header where it is. All of the movement switches off for anyone who has
  asked their system for less of it.
- Tagging a version builds a GitHub release, with the notes taken from the
  changelog rather than from commit subjects, and refuses to publish if the
  tests or the changelog check fail.
- It can be hosted from one file in the repo, so the deployment is reviewable
  rather than living in somebody's dashboard. The database is rebuilt on every
  boot, which means every visitor arrives at the same incident with somebody
  already overdue instead of whatever the last person left behind.
- A banner on every page of the hosted copy, saying it is a demo, that nothing
  in it is real, and asking people not to type a real address into something
  that looks like an emergency service and is not one.
- A disclaimer, readable without an account, saying plainly that DiresQ does
  not contact emergency services and that the triage helper orders attention
  rather than giving medical advice. The report form carries the warning above
  its first field, and the triage result carries it beside the category.
- The report form reads what you type and suggests how bad it is and what
  equipment is needed, showing the words that led it there. It stops adjusting
  the dropdown the moment you set one yourself, says nothing below the
  confidence it needs, and never writes anything — the person filing the
  report decides. Runs on the machine serving the page in about a tenth of a
  millisecond, with no model file and no network.
- It also notices when a description matches a report somebody has already
  filed, and offers a link to it. Duplicate reports are how six people end up
  at one address while a street nearby has nobody.
- A report page now says what the job needs and who is free who has it —
  "boat: 1 available, r.castillo". The description is read for the equipment,
  the board already knows who is idle, and before this those two facts never
  met. Anybody already out is excluded, because offering them is how you pull
  somebody off a scene they were needed at. When nobody free has the
  equipment, it says that instead of staying quiet.
- A social preview card, drawn from the palette by a script rather than by
  hand, so it can be regenerated when the wording changes.
- The map keeps the tiles it has already drawn, so it still shows where you
  have been when the network goes. It does not download an area in advance —
  that would only help somewhere you have never looked, which is usually where
  the disaster is, and the OpenStreetMap usage policy forbids it. The cache is
  capped, and nothing about the feed or the API is kept, because a stale list
  of who needs help is worse than no list.
- `GET /api/model` says what the classifier is, what it was trained on, and
  what it is bad at. Public and unauthenticated, because anyone should be able
  to find out what the software is doing to their report.
- Written decisions, build log, architecture notes, known limits and API
  reference under `docs/`. The architecture notes name the point at which each
  design stops working, rather than only what it does.
- An icon, and a `robots.txt` that keeps the whole site out of search results.
  Live reports name real addresses; none of it should be findable.
- A Board link on the feed, the map and every report page. It turns red and
  shows a count the moment anyone goes overdue, so you learn somebody is late
  wherever you happen to be rather than only while watching the board.
- Report cards say how many people are on their way and how many have arrived,
  and carry the staffing signal when someone on scene has set one. A report
  nobody has gone to reads "0 responding".
- Give a free-text ETA when you join, so the board knows when to expect you.
  Plain durations work the way people type them: "30 min", "2 hrs", "half an
  hour", "back in a couple hours", or just "45". The parser refuses anything
  it is not confident about rather than guessing, caps intervals at four
  hours, and rounds anything under five minutes up. A refused ETA still lets
  you join, on the default interval.
- A README covering setup, configuration, every route, the design decisions
  and the known limitations.
- Resolve a report when it is handled. Open to whoever filed it and to anyone
  on scene, since those are the only people in a position to know. Resolving
  clears everyone still attached and drops it out of the feed.
- A map of every located report. It opens centred on the newest one, zoomed out
  just far enough that everything else is still on screen, so the thing that
  brought you to the map is in the middle of it.
- Sign up and sign in, with passwords stored hashed.
- Seed data that loads an incident already two hours old: eight Katy-area
  reports, responders en route and on scene, staffing already signalled, and
  one person forty-seven minutes out of contact. The board is red and the feed
  tells the story the moment you open it, instead of looking like an empty
  to-do list.

- A severity lexicon in front of the priority classifier, covering the
  categories a triage protocol treats as immediate: airway and breathing,
  circulation, entrapment, hazardous material, structural collapse,
  dependence on powered medical equipment, and moving water on a person. When
  one matches, the matched phrase is shown as the reason. The phrases were
  written from the START protocol rather than from the reports we measure on,
  because a word list tuned against its own test set scores well and teaches
  nothing.
- The classifier is now measured by leave-one-out cross-validation in the test
  suite, and the build fails if held-out accuracy drops below 68%. A test also
  asserts no lexicon phrase ever fires on a report labelled something else,
  and that the corpus size quoted in the docs matches the corpus.
- A demo loop in the README: five responders on scene, one goes quiet, the
  board turns red, and the report DiresQ files on their behalf appears in the
  feed.
- `.gitattributes`, so the repository stores LF regardless of what anyone's
  editor does. Without it the next commit from a Windows machine touched 39
  files and changed 10,462 lines without altering a character of content.
- DiresQ installs to a phone. A web app manifest, maskable icons for Android,
  an iOS touch icon, and a translucent status bar — added to your home screen
  it opens without browser chrome and behaves like an app, which matters for
  something meant to be held in one hand in bad weather.
- An offline page that shows your own commitments and nothing else: the report
  you took, when you are due to check in, and where you last were. It renders
  from `/api/me`, the one response the service worker is allowed to keep.
  The feed and the accountability board are deliberately never cached — they
  are claims about other people that stop being true the moment they are
  written, and a stale copy of "who needs help" sends somebody to an address
  that was cleared twenty minutes ago. A test asserts the list of cached URLs
  is exactly `["/api/me"]`, and another fails if any other responder's name
  appears in it. The reasoning is written up in `docs/offline.md`.
- `GET /api/me` — your own state, for the above.

### Changed

- Equipment is now read from the wording with a word list rather than a
  classifier. The classifier version was confidently wrong — "power line down,
  still arcing" came back needing a chainsaw, because one training example
  mentioned a branch on a power line — and it asked for all five kinds of
  equipment on any long report. The word list is less clever, names the word
  that matched, and is wrong in ways somebody can see and fix. Priority is
  still classified, where the maths earns its place.
- Two responders in the seeded incident are deliberately left free. A board
  where everybody is busy has nothing to say when a report needs a boat.

- Staffing reorders the feed. Within a severity band, a report asking for help
  sorts first, one with nobody on it next, then covered, then overstaffed.
  Staffing never crosses a band, so a minor report cannot bury a critical one
  no matter how many people ask for help on it.
- Where responders on scene disagree about staffing, the most cautious signal
  wins. Someone reporting "we have enough" can never suppress someone else
  asking for more.
- Severity is HIGH, MEDIUM or LOW throughout, replacing an earlier numeric
  scale that the interface never used.
- Whether someone is overdue is worked out when the board is read, not tracked
  by a background job. There is no timer process to crash.
- Report coordinates are named `lat` and `lng` end to end.
- Leaving a scene retracts your staffing vote, since you can no longer see it.
- The map used to open over Indonesia regardless of where the reports were.

### Fixed

- Reports could be filed with no location at all. The location fields were
  marked required, but browsers do not validate hidden fields, so an untouched
  map submitted silently and the report never appeared on the map.
- Error messages were written but never displayed. A rejected sign-in or an
  incomplete report form appeared to do nothing at all.
- Timestamps sent by a browser were unreadable on Python 3.10. The format
  every browser produces ends in `Z`, which Python only learned to parse in
  3.11 — so every queued check-in would have worked on the machine this was
  written on and been rejected anywhere older.
- The app could not be used by keyboard alone. Six stylesheets defined no
  focus outline at all, so tabbing through the accountability board gave no
  indication of where you were. There is now a visible focus ring on every
  control on every page.
- Sign-in, sign-up and both search boxes had no labels, only placeholder text
  — which disappears the moment you type and may never be announced by a
  screen reader at all. Every input has a real label now.
- Two colours were effectively unreadable: capability tags at 1.8:1 against
  their background, and the footer at 3.4:1. Both moved to a tone that passes.
- No page could be skipped into, and nine of ten had no main landmark, so
  reaching the content meant tabbing the whole header every time.
- The board replaced its contents every three seconds without telling anyone.
  It now announces changes politely, so a screen reader is not interrupted
  mid-sentence on every refresh.
- Buttons and links that get tapped in the rain were under the size a thumb
  can reliably hit.
- Movement did not stop for anyone whose system asks for less of it.
- Pressing resolve twice said "only the reporter or someone on scene can
  resolve this" — because resolving clears you off the report, and so takes
  away the right you had just used. It now says it is already resolved, which
  is what actually happened.
- Rebuilding the database on top of an existing one stopped halfway and left it
  in pieces, because a table had been added without a matching drop. The tables
  are now torn down in the order their foreign keys allow, and a test reads the
  schema and fails if anything is created that is never dropped.

- The priority classifier was reported as accurate on the strength of a
  measurement taken on its own training data, where it scored 100%. Held out
  properly it scored 45%, against 36% for always guessing the commonest
  label, and it called "child not breathing properly" a MEDIUM. The severity
  lexicon above is the fix; held-out accuracy is now 75%. Every document
  quoting the old figure has been corrected, along with the corpus size, which
  was written down as 65 examples and had always been 55.
- Responder positions failing to load left a map that looked complete with
  every responder pin silently missing. It now says so.
- The service worker was registered from `map.js`, so anyone who installed
  DiresQ from the accountability board had no offline support at all until
  they happened to open the map. It now registers on every page.
- The suggestion panel showed the classifier's internal stems rather than the
  words somebody typed: "Suggested from: ris, upstair, fast" instead of
  "rising, upstairs, fast". The point of showing the reasoning is that a
  person can look at it and disagree, and nobody argues with something they
  have read as three typos. Stems are now mapped back to the first word in
  the report that produced them, and a test asserts every reason shown
  appears in the text it came from.
- The worked example in the classifier documentation described a different
  sentence than the one printed above it — a confidence and a set of reasons
  that belonged to some earlier phrasing. It had been copied into the demo
  video from there. A test now runs the documented example through the code
  and fails if the page and the software disagree.

### Security

- Report subjects and responder names are no longer interpolated into map
  popup markup. A report titled with an image tag and an `onerror` handler
  would have run in the browser of every coordinator who opened that pin, and
  coordinators hold the sessions worth stealing. Both popups are now built
  from text nodes, which cannot be parsed as markup, and a test fails the
  build if any user-supplied field is ever placed inside a template literal
  containing a tag. Usernames were already restricted to safe characters at
  signup, but a line is not secure because of a rule enforced in another file.
- A radio packet can no longer be replayed. A signature proves who made a
  packet and says nothing about when, so anyone who recorded one off the air
  could send the same bytes later and move that pin. Packets now carry a
  counter, signed along with everything else, and anything not strictly
  greater than the last accepted from that node is refused. Gaps are fine — a
  node out of range for an hour comes back higher; only going backwards is
  suspicious. We had this written down as an open weakness before fixing it.
- Security headers on every response: a content policy that refuses inline
  and evaluated script, no MIME sniffing, no framing, a referrer policy that
  keeps report addresses out of outbound links, and permissions limited to
  location. HTTPS strict transport is sent only when the site is actually
  served over HTTPS, since sending it from a laptop pins that browser to a
  local address for a year.
- A security policy at the root of the repository, saying what is in scope,
  what we already know is wrong, and what we fixed after finding it
  ourselves.

- Signing in could be made to bounce you to another website. The address to
  return to was taken from the link you arrived on and used without being
  checked, which turns a real login page on a real domain into a working
  phishing page. Only same-site paths are accepted now.
- Repeated wrong passwords lock a username for a few minutes, counted per
  name so being guessed at cannot lock anybody else out.
- Passwords are capped at a sensible length, since the hash is deliberately
  slow and a very long one is a way to make the server do work.
- Usernames must be ordinary characters, and one that differs from an existing
  account only by capitalisation is refused — on a board where names are how
  you tell people apart, two similar ones is a mix-up waiting to happen.
- Session cookies are marked HttpOnly and SameSite, and HTTPS-only when the
  environment says the site is served over HTTPS.
- A Caps Lock warning, a show-password button and a live check that the two
  password boxes agree, so a rejected sign-in is something you can see coming.
- Passwords are hashed with `werkzeug.security`, never stored or logged in the
  clear.
- The session signing key is read from the environment and randomly generated
  when absent, never hardcoded.
- A failed sign-in returns the same message whether or not the account exists,
  so the form cannot be used to discover usernames.
- Continuous integration blocks any commit containing a database file, a
  hardcoded signing key, or `random` used where `secrets` belongs.
