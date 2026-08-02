# Why we built this

Every disaster app tells you where the disaster is. We could not find one that
tracked the people going into it.

---

## The gap

During Hurricane Harvey, civilians in fishing boats pulled thousands of people
out of flooded houses across south-east Texas. The Cajun Navy is the famous
name for it, but most of them were just people with a boat and a truck who
drove towards the water because someone they knew was in it.

Some of them died doing it.

The tools that exist serve the incident. Crowdsourced maps show where the
water is. Social media shows who is asking for help. Agencies have dispatch
systems for their own personnel, and those systems assume you are on a roster,
carrying a radio, and answerable to an incident commander.

A neighbour with a jon boat is none of those things. Nobody logs that they
went out. Nobody knows where they are. **Nobody knows when to start worrying.**

If somebody stops answering their phone in the middle of a flood, the honest
current answer is that you find out when they don't come home.

## Convergence, not collision

The second problem took us longer to see, and it changed how the whole app
works.

Our first design had one responder claim one report, like a dispatch system —
a claim lock, so two people don't both drive to the same address.

Then we read about Kathmandu in 2015 and Mexico City in 1985. In both, huge
numbers of untrained volunteers converged on a handful of visible collapse
sites while other sites nearby had nobody at all. People dug at the building
that was on television.

The failure mode in a real disaster is not two people going to the same
address. It is **six hundred people going to the same address** because it is
the one with a photograph attached, while a street two blocks away has nobody.

A claim lock fights the wrong problem. Worse, it would fight the *right*
behaviour — sometimes a collapse genuinely needs forty people.

So we deleted it. Any number of responders can join any report. Instead of
preventing convergence, DiresQ makes it **visible**: every card says how many
people are already on it, the people on scene can signal that a site is
overstaffed, and a report nobody has committed to sorts *above* one that is
merely short-handed.

That last rule is the whole thesis expressed as a sort key. A gap is worse
than a queue.

## What we would not do

We decided early that the fastest way to make this dangerous was to make it
look more capable than it is.

**No identity verification.** Anyone can sign up. Doing it properly needs real
ID checks or organisational affiliation, and there is no honest weekend
version. An email confirmation would be *worse than nothing*, because it looks
like verification without being it.

**No dispatch.** DiresQ does not contact 911 and never implies that it has.
The one failure with real consequences is somebody filing a report and
believing help is now coming.

**No claim to work offline that we hadn't earned.** Check-ins queue on the
phone and survive having no signal. Reports do not. The radio packet is built
and signed and tested; the radio is not. Every one of those distinctions is
written down rather than blurred.

**No stored triage answers.** The triage helper runs a real protocol on
observations about somebody who is in no position to consent to being
recorded. The answers produce a category and are thrown away. There are tests
that fail if a future change starts keeping them.

## Why the accountability board is the product

Everything else in DiresQ is how you get to one screen.

The board lists everyone who is out, what they are doing, where they were last
seen, and how long since anyone heard from them. Overdue sorts to the top and
turns red, and the page refreshes itself, so somebody going overdue appears
without anyone touching anything.

Then, because a red row only helps if somebody is *looking* at the board, a
responder who stays silent fifteen minutes past their deadline gets a report
filed about them automatically, at their last known position. It joins the
feed like any other report. Other volunteers can go and find them.

That is the sentence the whole project exists to finish: **the app that tracks
the people going in now sends help back out for them.**

## Why it's built the way it is

Boring on purpose. Flask, SQLite, server-rendered HTML, and JavaScript that
only ever adds to a page that already works without it.

Every button is a plain form. Every page renders on the server. If the
JavaScript fails — old phone, bad connection, one syntax error — the app still
functions. That is not nostalgia; a tool for the worst day of someone's life
should not depend on a bundle loading.

Nothing that can be derived is stored. Whether a responder is overdue and how
staffed a report is are both computed when read, never written to a column.
Stored state needs a background job to keep it true, and a background job that
dies takes the truth with it — silently, while every page keeps rendering a
green board.

The complete reasoning is in [Architecture](architecture.md) and
[Decisions](decisions.md).

## What it isn't

It is a hackathon project. It has never been used in a real disaster, and it
should not be until somebody who does this professionally has taken it apart.

[Limits](limits.md) is the list of what it doesn't do, and
[Disclaimer](disclaimer.md) is what to read before letting anyone near it.

We wrote those pages before we were asked for them, because the failure we
were most worried about was our own project overstating itself — and the
subject is people who might get hurt.
