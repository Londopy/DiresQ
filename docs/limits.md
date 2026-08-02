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

## Nothing works offline yet

Check-ins, reports and the board all need a connection. In a disaster, that's
exactly what you don't have.

The server side is ready: a check-in can say when it was really made, and the
overdue timer uses that rather than when it arrived, so a queued one can't
clear a red row it never earned. The queue itself, and cached map tiles, are
not built.

Tiles can only ever cover where you've already been — a cache can't pre-fetch
somewhere you've never looked.

## Spam control is flagging, not verification

Anyone can flag a report as fake, once each. At three flags it drops out of
the feed — but stays visible to whoever filed it and to anyone already on
their way, because being outvoted by three strangers shouldn't strand someone
who is already driving there.

That's community moderation, not verification. Three coordinated accounts can
bury a real report, and one determined person with three accounts is not a
hard problem to have.

## START triage orders attention, not treatment

The triage helper runs a real protocol and gives a real category. It decides
who gets reached first. It is not medical advice, it doesn't tell you what to
do when you get there, and it doesn't replace a clinician.

## The uplink endpoint is unauthenticated

`/api/uplink` takes a check-in as bytes rather than as a logged-in browser,
because a radio gateway has no session and no cookie — it has a packet it
heard and a socket to hand it over on. The responder is identified from
inside the packet.

Which means anyone who can reach that endpoint can move a pin. It exists to
prove the message shape is right, not to face the internet. Doing it properly
needs a shared key per node and a signature over the packet, which is another
four bytes and a key distribution problem we haven't solved.

## The dead man's switch needs somebody to open the app

The check for silence runs when a page is loaded, not on a timer. If nobody
opens DiresQ at all, nothing is swept and no report is filed.

In practice, one browser left on the board polls every three seconds, which
is enough. But "someone has a tab open" is a dependency, and it should be
written down as one rather than assumed.

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
