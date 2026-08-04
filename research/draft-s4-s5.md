# §4 and §5 — first draft

Status: **first draft, unreviewed.** Same conventions as `draft-s3-design.md`:
`[CHECK]` = true but I cannot tell how it reads from outside; `[CUT?]` = suspect
it is too much for a WiP paper.

> **Correction to §3, found while writing this.** `draft-s3-design.md` says the
> switch "has no scheduler." That overstates it. There is no *internal
> background thread*, but `flask --app app sweep` runs the same check from cron
> or Task Scheduler — it is supported and optional, not absent. The honest claim
> is: *no in-process timer; an external scheduler is available and unrequired.*
> Fix §3 before either section is shown to anyone. This is exactly the kind of
> overstatement a reviewer catches and it would cost more than it gains.

---

## 4. What building it taught us

We report these as observations from construction, not as validated findings.
Each began as a specific bug or reversal and generalised afterwards.

### 4.1 Correct-when-written and correct-when-read are different guarantees

The offline layer was originally designed to cache what a user would want if
their signal dropped, which is nearly everything. We now cache almost nothing.

The rule we arrived at: **do not store anything that stops being true when it is
written.** Your own commitments — the assignment you accepted, a report you
filed with no signal — remain true offline, because they are statements about
you. The report feed and the accountability board are statements about other
people, and both decay. A cached feed is a list of who needed help twenty
minutes ago; a responder acting on it is dispatched to an address that has since
been cleared, with no way to distinguish that from a current one.

Offline-first design generally treats availability as an unalloyed good, with
staleness managed by tolerance windows and revalidation. We think the useful
distinction is not how stale the data is but whether a stale answer is
*actionable* — whether a user can be sent somewhere by it. Data that can move a
body should not be served from cache at all. A test fails if either page is
added to the service worker's shell list, because the rule is easy to forget and
the failure is silent.

### 4.2 An alarm that dies quietly is worse than no alarm

The silence check was first designed as a background thread inside the
application. We removed it. A timer that dies takes the alarm with it and leaves
the interface showing green, and a green screen is read as a positive result
rather than an absent one.

The check now runs on read — whenever anyone loads the accountability board,
rate-limited to once every thirty seconds. An external scheduler is supported
(`flask --app app sweep`) and deliberately optional: an external scheduler that
fails is at least visible to the machine running it, which an in-process timer
is not.

This does not remove the dependency, it relocates it. The system now works while
somebody is looking. We regard that as the better failure mode, because a board
nobody is watching is a situation where nobody is relying on the answer — but
the claim needs stating rather than assuming. `[CHECK]`

### 4.3 A limitation on screen is a different claim from a limitation in a file

The consequence of §4.2 is that the guarantee is conditional, and our first
response was to write that down in a limitations document. That is the standard
move and we now think it is insufficient.

The board displays how long since the last sweep — *checked 2s ago* beside the
live indicator, amber past five minutes, which is ten minutes before the
fifteen-minute escalation it drives. On a board somebody is watching it always
reads a few seconds, because the watching is what runs it. If it stops moving,
that is visible too.

The general form: **emergency software should surface its own liveness.** A user
deciding whether to trust a screen needs to know whether the thing behind it ran,
and that is a different question from whether the data looks reasonable. We would
extend this beyond our own system: any interface that reports on a periodic
check should display when the check last completed, not merely its result.

### 4.4 The pages built to be watched were the ones that broke under watching

The board, the map and the feed all run the silence check before answering, and
the check writes. SQLite's default journal mode lets one writer lock out every
reader. With several people watching a board that refreshes every three seconds,
a write could wait past its timeout and fail the entire response.

The pages whose purpose is to be watched continuously during an emergency were
precisely the pages that failed when watched continuously. The fix was
unremarkable — write-ahead logging, rate-limiting the sweep, catching the
failure rather than letting it become an error page. The lesson is not about
SQLite. It is that **making a read-only page write is a change of kind, not of
degree**, and in this system it converted the most-loaded pages into the most
fragile ones. `[CHECK: is the SQLite detail too specific? The general point may
survive without naming the database.]`

One deliberate detail: a failed sweep does not record itself as having run. The
timestamp goes stale and the board reports that in amber, which is true, because
a check we could not record is not a check we can claim.

### 4.5 Prose about a system lags the system `[CUT?]`

Our test suite verifies every count in our own documentation — routes, tables,
tests, lines — and fails when the prose and the repository disagree. It has
caught wrong numbers repeatedly, including several we wrote ourselves.

It has never once caught the more common error, which is a *sentence* that
describes a previous version of a behaviour. Four times a change landed and the
paragraph explaining it stayed a revision behind. Numbers are checkable and were
checked; claims are not, and were not.

We do not have a solution and offer this as an observation: automated
documentation checks create a real assurance about the class of statement they
can verify and no assurance whatever about the class they cannot, and the second
class is where the misleading statements live.

*(Include only if length allows. It is the most generalisable thing here and the
least connected to disaster response.)*

---

## 5. Limitations

The system has eighteen documented limitations, maintained as a first-class
document rather than an appendix. We summarise the ones that most constrain what
this paper claims.

**It has never been used in a real disaster.** Everything here is reasoned from
published accounts of Harvey, Kathmandu and Mexico City, and from published
triage protocol. None of it has been tested by somebody standing in water at two
in the morning. We believe the reasoning is sound; that is not the same as
knowing it works, and no part of this paper should be read as evidence that it
does.

**The switch depends on being run.** Described in §4.2. Neither the read-trigger
nor an external scheduler is guaranteed. A deployment nobody looks at and nobody
configures performs no checks.

**Overdue measures contact, not safety.** The system reports that it has not
heard from somebody. It cannot distinguish danger from a dead battery, and it
does not try. The interface language was revised twice to stop implying
otherwise, and this is the limitation most likely to be misread by a user in a
hurry.

**No identity verification.** Anyone can register. This is a design condition
rather than a defect — a system requiring approval has reintroduced the
coordinator whose absence is the problem — but it means the system cannot
distinguish a responder from someone claiming to be one.

**Location is self-reported** throughout. The map shows where people said they
were.

**One cautious responder can hold a report open**, which biases the system toward
over-reporting need. We prefer that direction and note that we chose it.

**Lockouts live in memory** and do not survive a restart.

### A position rather than a finding

The literature we build on treats converging volunteers as a population to be
managed: Kendra and Wachtendorf document access as negotiated legitimacy, with
credentialing, liability and security as the operative concerns, and volunteers
as a potential distraction that must outweigh its own cost. Our design treats
the volunteer as somebody owed an accounting.

These are different moral starting points, and the literature does not share
ours. We think ours is defensible — a person who walks into a hazard to help is
owed something regardless of whether an institution has authorised them — but it
is a position, not a result, and a reader is entitled to reject it and evaluate
the design on the field's own terms instead.

---

## Notes for revision

- Fix the §3 scheduler overstatement first.
- §4.5 is the strongest general claim and the weakest fit for an emergency
  management venue. Cut it before cutting anything else if length binds.
- §5 currently names seven of eighteen limitations. Check whether the CfP page
  limit allows more; if it does, add the triage-storage decision here and remove
  it from §3.
- Every number in §4.4 and §5 must be re-read out of the repository at
  submission time.
