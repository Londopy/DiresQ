# Known limits

What DiresQ doesn't do. Every item names what we *did* build before naming
what we didn't, because "we didn't have time" isn't a limitation, it's an
excuse.

A system with no stated limitations isn't a system without limitations. It's
one nobody checked.

---

## No identity verification

Anyone can register and mark themselves a responder. There is no check that
you are who you say you are.

Solving this properly needs real ID checks or affiliation with an
organisation that already vets people. There is no honest weekend version, and
a fake one — an email confirmation, say — would be worse than nothing because
it looks like verification without being it.

## Location is self-reported

Check-ins record whatever coordinates the browser hands us. Someone can sit at
home and file a check-in claiming to be on scene.

We detect *inconsistency*, not intent. Marking yourself on scene when your
last check-in was more than 500 metres from the report raises a mismatch flag
on the board. The radius is generous because phone GPS is poor in bad weather
and a false accusation is worse than a missed one.

Someone determined can still lie about where they are. No amount of
client-side code fixes that.

## One cautious responder can hold a report open

Staffing resolves to the most cautious signal, so a single person saying
"needs more help" outweighs everyone else saying it's covered.

That's deliberate — the alternative lets an optimistic report suppress a call
for help — but it does mean one person can keep a report near the top of the
feed when it doesn't need to be there.

## The overdue timer measures contact, not safety

A responder is flagged when nobody has heard from them. That's not the same as
being in trouble, and it isn't the same as being fine.

Someone with a dead battery flags identically to someone in a flooded
basement. Someone hurt but able to tap a button doesn't flag at all. The timer
tells you when to *start asking*, and that's all we claim for it.

## The feed and the board never work offline, on purpose

Check-ins and new reports both survive having no signal. Both are kept on the
phone with the time they were made, sent when a connection returns, and carry
an id so a retry is recognised rather than filed twice. The classifier runs on
the phone too, so the priority suggestion reaches somebody filing at 2am with
the towers down.

**The feed and the board still need a connection, and always will.** They are
claims about other people that stop being true the moment they are saved, and
a stale one sends somebody to an address that was cleared twenty minutes ago.
Offline they are absent rather than wrong.

**Duplicate detection cannot run offline either**, for the same reason: it
compares your description against everybody else's open reports. So between
filing a report offline and it syncing, nothing has checked whether somebody
has already reported the same thing — and the form says so rather than showing
an empty list, which would read as *checked, found none*. The server runs the
check when the report lands, against everything open including whatever else
arrived in the same batch.

**Editing or resolving a report still needs a connection.** Only new reports
queue. Reconciling an edit against whatever happened while you were away needs
conflict rules we have not earned the right to guess at.

Map tiles are cached only where you have already looked. A tile cache cannot
pre-fetch somewhere you have never been, which is often exactly where the
disaster is.

The full accounting is in [offline.md](offline.md), and it is deliberately
blunt about which parts exist.

## Spam control is flagging, not verification

Anyone can flag a report as fake, once each. At three flags it drops out of
the feed — but stays visible to whoever filed it and to anyone already on
their way, because being outvoted by three strangers shouldn't strand someone
who is already driving there.

That's community moderation, not verification. Three coordinated accounts can
bury a real report, and one determined person with three accounts is not a
hard problem to have.

## Triage answers are never stored

The helper runs START on four observations and returns a category. The answers
themselves are computed and discarded — never written to the database, never
attached to an account.

They are health observations about a third person who is in no position to
consent to being recorded, so the safest amount to keep is none. There are
tests that fail if any request to `/api/triage` writes a row, and if the
schema ever grows a column that looks like one of the answers.

## START triage orders attention, not treatment

The triage helper runs a real protocol and gives a real category. It decides
who gets reached first. It is not medical advice, it doesn't tell you what to
do when you get there, and it doesn't replace a clinician.

## The radio protocol, and what is left in it

`/api/uplink` takes a check-in as bytes rather than as a logged-in browser,
because a radio gateway has no session and no cookie. The responder is named
inside the packet, and every packet carries four bytes of HMAC over its body,
checked against that responder's key before anything is written. An unsigned
or wrongly-signed packet is refused.

Replay used to be the open hole here, and it is closed. Every packet carries a
counter, signed with everything else, and the server refuses anything not
strictly greater than the last it accepted — so recording a valid packet off
the air and sending it again gets a 409 rather than a moved pin.

What remains is the size of the signature.

Four bytes of signature is 32 bits, so a blind forgery gets through about once
in four billion tries. That's a deliberate trade against a link where a full
32-byte tag would be twice the size of the message. Key distribution is a
person reading `flask --app app node-key alice` and typing it into a node,
which works at the size of a volunteer group and not beyond it.

## The dead man's switch depends on being run

The check for silence runs when a page is loaded. `flask --app app sweep` runs
the same check from cron or Task Scheduler, so it doesn't have to depend on a
browser — but somebody has to set that up, and if neither happens, nothing is
swept and no report is filed.

There is deliberately no background thread. A timer inside the app that dies
takes the alarm with it, silently, which is the worst way for an alarm to
fail. An external scheduler failing is at least visible to the machine running
it.

It also can't tell the difference between a phone that died and a person who
is hurt. It files the same report either way, which is the right failure —
sending someone to check on a flat battery costs an hour, and the other
mistake costs more than that.

## The activity log is only as complete as what we timestamp

The ICS-214 export is built from real records, not typed up afterwards, but
it can only report what the database dates. Joining, arriving, clearing and
every check-in have times. Resolving a report and changing a staffing signal
do not — they're logged against the record they belong to, and the export
says so at the bottom rather than inventing a time.

## Lockouts live in memory

Repeated failed logins lock a username for a few minutes. The counter is a
dictionary in the process, so it resets when the server restarts and it isn't
shared if you ever run more than one worker.

That's deliberate at this size: a lockout that survives restarts is a lockout
an attacker can make permanent by guessing at somebody on purpose. It is
still not real rate limiting, and it does nothing about a distributed attempt.

## Anyone can sign up at any age

There is no age gate. Nothing asks, and nothing stops a child creating an
account and marking themselves a responder.

For a hackathon demo that is a non-issue. Deployed publicly it is a real one —
both because of what it would mean to send a minor towards a flood, and
because collecting personal data from under-13s in the US brings obligations
we have not met.

## Accessibility is checked, not audited

The markup is tested against the parts of WCAG 2.1 AA that can be tested:
language, landmarks, skip links, labels on every input, alt text, live-region
politeness, and the contrast ratio of every colour pair used for real text.
Those tests run in CI.

What has **not** happened is a person using a screen reader on it. Automated
checks catch roughly a third of real accessibility problems, and the third
they catch is the easy third. The map in particular is a Leaflet canvas with
no non-visual equivalent — the board carries the same information as text,
but nobody has confirmed that is enough.

## Limits we closed, and how

Kept here rather than deleted, because a limitations page that only ever grows
is not being maintained.

| Was | Now |
| --- | --- |
| Nothing worked offline | Check-ins queue on the phone and sync with the time they were made |
| Reports could not be filed offline | They queue too, carry an id that stops a retry filing a second incident, and say when they were written |
| The classifier could not reach anyone without signal | The same trained model runs in the browser |
| Duplicates were only checked while somebody was online and typing | Checked on arrival, against the rest of the same sync batch |
| The radio endpoint was unauthenticated | Every packet is signed per node and verified before anything is written |
| The dead man's switch needed somebody to have a tab open | `flask --app app sweep` runs it from cron |
| Signing in could bounce you to another website | Only same-site paths accepted |

## It has never been used in a real disaster

Everything here is reasoned from accounts of Harvey, Kathmandu and Mexico
City, and from published triage protocol. None of it has been tested by
someone standing in water at 2am.

We think the reasoning is sound. That is not the same as knowing it works.
