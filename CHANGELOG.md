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
- Written decisions, build log, known limits and API reference under `docs/`.
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

### Changed

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
- Rebuilding the database on top of an existing one stopped halfway and left it
  in pieces, because a table had been added without a matching drop. The tables
  are now torn down in the order their foreign keys allow, and a test reads the
  schema and fails if anything is created that is never dropped.

### Security

- Passwords are hashed with `werkzeug.security`, never stored or logged in the
  clear.
- The session signing key is read from the environment and randomly generated
  when absent, never hardcoded.
- A failed sign-in returns the same message whether or not the account exists,
  so the form cannot be used to discover usernames.
- Continuous integration blocks any commit containing a database file, a
  hardcoded signing key, or `random` used where `secrets` belongs.
