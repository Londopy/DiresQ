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

## It has never been used in a real disaster

Everything here is reasoned from accounts of Harvey, Kathmandu and Mexico
City, and from published triage protocol. None of it has been tested by
someone standing in water at 2am.

We think the reasoning is sound. That is not the same as knowing it works.
