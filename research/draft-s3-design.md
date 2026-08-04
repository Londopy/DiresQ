# §3 Design — first draft

Status: **first draft, unreviewed.** Prose is written to be cut. Every number
here was read out of the repository on the day of writing and must be re-checked
against it before submission.

Notation: `[CHECK]` marks a claim that is true of the system but that I have not
verified reads correctly to somebody outside the project. `[CUT?]` marks
something I suspect is too much detail for a WiP paper.

---

## 3. Design

DiresQ is a server-rendered web application: Flask, SQLite, no client framework,
no account approval step, and no dispatcher role. Thirty-three routes over six
tables. The stack is deliberately unremarkable, and we describe it only to
establish that nothing in what follows depends on infrastructure a volunteer
organisation would not already have. The contribution is not the stack.

Anyone can sign up. There is no verification of identity, no vetting, and no
administrator who admits people. This is not an oversight we intend to fix; it
is the condition the system is designed for. A tool that requires somebody to
approve you has reintroduced the coordinator whose absence is the entire
problem.

### 3.1 The mechanism

A report is a place that needs help. A responder who decides to go there joins
the report and, in doing so, states an expected time of arrival. The ETA is
bounded between five and 240 minutes and warns above 120 — not because longer
journeys are invalid, but because an unbounded ETA makes the subsequent
arithmetic meaningless. From that point the responder is expected to check in;
the interval defaults to thirty minutes.

If a responder stops checking in, they are marked overdue. Fifteen minutes past
that threshold, the system files a report *about them* — their last known
location becomes an incident in the same feed everyone else is reading. No human
decides this. No human is asked to notice.

This is the whole mechanism, and its only novel property is what triggers it.
Existing accountability systems escalate when a coordinator observes that
somebody has not reported in. We escalate on the observation itself being
absent. Silence is available in circumstances where a supervisor is not.

### 3.2 Five decisions, and what each one cost

The design is small enough that the interesting content is not the architecture
but the trade-offs. We describe five, each of which we got wrong first.

**Silence as the trigger.** The alternative designs all require somebody to be
watching: a dispatcher view, an alert queue, a supervisor role. Each of them
works, and each of them assumes the thing we cannot assume. Escalating on
absence needs nobody. The cost is that absence is ambiguous — a responder who
has stopped answering may be in trouble, or may have a dead phone, or may have
gone home without saying so. The system cannot tell these apart and does not
claim to. It reports *contact lost*, never *safe* or *unsafe*, and the interface
language was rewritten twice to stop implying otherwise.

**The switch has no scheduler.** Our first design ran the silence check as a
background job. We removed it. A scheduled task can die without anyone
noticing, and an alarm that has silently stopped is worse than no alarm, because
a green screen is read as a positive result rather than an absent one. The check
now runs on read: whenever anyone loads the accountability board, the sweep runs
first, rate-limited to once every thirty seconds.

This trades one dependency for another. A timer that might die becomes a check
that depends on being watched. We consider that the better failure — an
unwatched board is a situation where nobody is relying on the result — but the
substantive move is that we made the dependency **visible** rather than
documenting it. The board displays how long since the last sweep and turns amber
past five minutes. On a board somebody is actually watching, the number always
reads a few seconds, because the watching is what runs it. A limitation you can
see on screen is a different claim from one the user has to be told about.
`[CHECK: does this read as insight or as excuse-making?]`

**Status and contact are different facts.** What a responder last told us is one
thing; whether they are still answering is another. We conflated them, and the
result was a report page displaying "on scene" for somebody the accountability
board had forty-five minutes overdue. Anyone opening that report to decide
whether the address needed more help was counting a person who had gone silent
as help present. Both facts are now shown, and neither is inferred from the
other. Somebody who has explicitly cleared is not chased, because going home is
not going quiet.

The general form of this: in a system whose purpose is knowing where people are,
*self-reported state* and *liveness* must never be collapsed into one field,
however tempting the simplification is at the schema level.

**Refusing to cache claims about other people.** The offline layer keeps the
things you committed to — your own assignments, a queued report you filed
without signal — and refuses to keep the report feed or the accountability
board. A cached feed is a list of who needed help twenty minutes ago. Acting on
it sends somebody to an address that has been cleared, and the person reading it
has no way to know the difference between stale and current. A test fails if
either page is added to the service worker's shell list.

The generalisable claim, and the one we would defend: **correct-when-written and
correct-when-read are different guarantees**, and disaster data has an unusually
short half-life between them. Offline-first design literature tends to treat
availability as an unalloyed good. For a class of data it is not, and the
distinction is not about staleness tolerance but about whether a stale answer is
*actionable* — whether a user can be sent somewhere by it.

**Not storing triage answers.** The system includes a START triage helper that
orders which reports get attention first. The answers are health observations
about a person who did not consent and is likely in no position to. They are
used to compute an ordering and then discarded; nothing about a casualty's
breathing or perfusion is written to the database. The cost is that the ordering
cannot be audited after the fact, which is a real loss. We accepted it.
`[CUT? — may be a §5 limitation rather than a §3 decision.]`

### 3.3 Priority suggestion

A report can be given a suggested priority by a multinomial naive Bayes
classifier over a severity lexicon, trained on a small hand-labelled corpus and
validated by leave-one-out cross-validation with a floor asserted in continuous
integration.

We describe it in one paragraph deliberately. It is the least interesting
component and the one most likely to be mistaken for the contribution. It
suggests an ordering for human attention; it does not predict outcomes, assess
medical severity, or make any claim that survives the person reading the report
disagreeing with it. A model small enough to ship as a frozen table of word
counts is also small enough to run in the browser, which is why priority
suggestion works with no signal while the report feed deliberately does not.
`[CHECK: is one paragraph too dismissive for a reviewer who wants numbers? If
so the numbers go in a footnote, not the body.]`

### 3.4 What the design does not attempt

It does not summon help. No dispatcher reads it, it does not call emergency
services, and the disclaimer on every page is load-bearing rather than legal
decoration. It does not verify that anybody is who they say they are. It does
not know where anyone actually is — location is self-reported throughout. It
makes no claim that a responder is safe; only that we have or have not heard
from them.

These are stated here rather than only in §5 because a reader who reaches the
limitations section still holding the wrong model of the system has already
misread the design.
