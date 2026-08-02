# DiresQ

Disaster response tracker. Logs the volunteers going in, not just where the
disaster is.

All notable changes to this project are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com), versioning follows
[Semantic Versioning](https://semver.org).

## [Unreleased]

### Added
- Flask backend with SQLite storage and a four-table schema: accounts,
  reports, assignments, checkins.
- Report feed sorted by priority, then most recent, with en-route and
  on-scene responder counts per report.
- Report creation with a Leaflet map for setting the location, by map click
  or by browser geolocation.
- Report detail page listing every responder currently assigned.
- Join a report. Any number of responders can join the same one.
- Map page showing every located report as a pin.
- Login with hashed passwords, and a shared generic failure message so the
  endpoint does not reveal which usernames exist.
- `GET /api/reports` returning the feed as JSON.
- Seed command with Katy-area reports and three test accounts.
- `DIRESQ_DEV_USER` environment variable to bypass login during development.
- Test suite covering every route, the four invalid report submissions, joining
  and double-joining, login failure modes, staffing resolution and overdue.
- GitHub Actions: tests and a boot check on every push, advisory linting,
  changelog validation, and security scanning.
- Flashed messages are rendered on the login, report creation and report
  detail pages.
- Sign up, with checks on username length and availability, password length
  and confirmation, and role. New accounts are signed in on creation.
- `GET /api/responders`, the accountability board. Every responder with their
  current assignment, last known position, minutes since contact, and a single
  `state` field of overdue, on scene, en route or available. Sorted worst
  first, so anyone overdue is the first row.
- `POST /api/checkin` records a responder's position and resets their timer.
- `.env` support via python-dotenv, with a documented `.env.example`. Real
  environment variables take precedence over the file.

### Changed
- Priority is stored as `HIGH`, `MEDIUM` or `LOW` rather than an integer
  scale, matching the filter controls and map counters in the frontend.
- Staffing state is derived from the votes of responders currently on scene
  rather than stored on the report. Where votes disagree the most cautious
  one wins, so an optimistic signal can never suppress a request for help.
- Report location fields renamed to `lat` and `lng` across the frontend.
- Database setup and seeding are plain functions the CLI commands wrap, so
  tests can call them directly. The schema path resolves against the
  application file rather than the working directory.
- `pygeospy` is marked Windows-only in `requirements.txt`. It publishes no
  Linux wheel or sdist, so installing it unconditionally broke CI.

### Fixed
- Reports could be submitted with no location. The hidden latitude and
  longitude inputs carried `required`, but hidden inputs are exempt from
  browser constraint validation, so an untouched map still submitted. The
  server now rejects these, and both columns are `NOT NULL`.
- Error messages were never shown. Five `flash()` calls had no template
  rendering `get_flashed_messages()`, so a rejected login or an incomplete
  report form appeared to do nothing at all.

### Security
- Secret key is read from `DIRESQ_SECRET_KEY` and falls back to
  `secrets.token_hex`, never a hardcoded value.
- Passwords are stored with `werkzeug.security.generate_password_hash`.
