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

## Nothing works offline in the browser yet

Check-ins, reports and the board all need a connection. In a disaster, that's
exactly what you don't have.

The server side is ready: a check-in can say when it was really made, and the
overdue timer uses that rather than when it arrived, so a queued one can't
clear a red row it never earned. There is also a signed radio packet and a
gateway that forwards it.

**The queue itself is not built.** Close the tab with no signal and the
check-in is gone. Neither are cached map tiles, and a tile cache can only ever
cover where you've already been — it can't pre-fetch somewhere you have never
looked, which is often where the disaster is.

The full accounting of which parts exist is in [offline.md](offline.md), and
it is deliberately blunt.

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

## An uplink packet can be replayed

`/api/uplink` takes a check-in as bytes rather than as a logged-in browser,
because a radio gateway has no session and no cookie. The responder is named
inside the packet, and every packet carries four bytes of HMAC over its body,
checked against that responder's key before anything is written. An unsigned
or wrongly-signed packet is refused.

What that does not stop is a *replay*: somebody who records a valid packet off
the air can send the same bytes again later and move that pin. Closing it
needs a counter in the packet and a record of the last one accepted — two more
bytes and a table.

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

## It has never been used in a real disaster

Everything here is reasoned from accounts of Harvey, Kathmandu and Mexico
City, and from published triage protocol. None of it has been tested by
someone standing in water at 2am.

We think the reasoning is sound. That is not the same as knowing it works.
