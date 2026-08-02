# Decisions

Things we argued about, what we picked, and why. Written as we went, not
cleaned up afterwards.

---

## Many responders per report, not one

**The pivot.** We first modelled this as one responder claiming one report —
the dispatch model. Claim it, it's yours, nobody else can take it.

Then we looked at what actually happens. Kathmandu 2015 and Mexico City 1985:
hundreds of neighbours converging on single collapse sites. Harvey: whoever
had a boat went to whatever address they saw online. A claim lock would have
fought the thing that saves people.

**The real failure mode isn't collision, it's convergence.** Six people on one
street while the next one over has nobody. So we rebuilt around many
responders per report, and added a staffing signal so people on scene can say
"we have enough, go somewhere else."

Everything else in the app follows from this one change.

## The most cautious staffing signal wins

If two people on scene disagree about whether a site has enough help, we take
the one asking for more.

`need_more > adequate > overstaffed > stood_down`

An optimistic report must never be able to suppress a call for help. That's
the rule in any safety system and it's one comparison in code:

```python
return max(votes, key=STAFFING_ORDER.index)
```

The cost is real and we accepted it: one pessimistic responder can hold a
report at "needs more" when it doesn't. We'd rather over-send help than
under-send it.

## Staffing reorders the feed, but never across a severity band

Staffing had to affect the feed or the signal is decorative. But we didn't
want a low-priority report with six people shouting for help to bury a
high-priority one nobody has reached.

So staffing breaks ties **inside** a band. Within HIGH: asking for help,
then nobody on it, then covered, then overstaffed. A LOW report can never
outrank a HIGH one no matter how loud it is.

The alternative — staffing overriding severity outright — looks better on
camera. We picked the one we could defend.

## Overdue is computed when you read it, never stored

There is no background job marking people late. The board works it out on
every read: are you past your ETA, or past the default interval since your
last contact.

One less moving part. A cron job that dies silently is worse than no cron job,
because the board would look fine and nobody would be flagged.

## Free-text ETAs get refused, not guessed

You can type "back in a couple hours" when you join. It gets parsed with a
confidence floor, capped at four hours, and rounded up below five minutes.

If the parser isn't confident, **you get the default interval and a message**,
not a deadline it invented. This drives a safety timer — a wrong deadline is
worse than no deadline. Too early and the board cries wolf, too late and
somebody is missing for hours before anyone notices.

A refused ETA still lets you join. We never block someone from responding
because a parser was unsure.

## START triage instead of a severity dropdown

Picking HIGH/MEDIUM/LOW from a dropdown is a guess, and it means the same word
means different things to different people.

START is the protocol used at real multiple-casualty scenes: four observations
anyone can make without training or equipment. We wired it in as an optional
path from the report form — answer four questions, get a category that means
the same thing to everyone.

The dropdown still works. Not every report is a casualty.

## Login last

We built the whole core loop with an environment variable that fakes being
logged in, and did real auth near the end.

Auth is a solved problem with no demo value. Every hour spent on it early is
an hour the actual product doesn't exist. It also adds friction to every
manual test you run.

## Server-rendered pages, JSON on top

The pages are plain Flask templates. The board polls a JSON endpoint on top of
its own server-rendered first paint.

This wasn't planned — the frontend got built as templates before the API
existed, and rather than rewrite it we kept both. It turned out better than
what we planned: the board works with JavaScript off, and only the part that
needs to be live is live.

## Flask, not Quart

We're not doing anything async. Quart would have bought us nothing and cost us
every StackOverflow answer written about Flask.

## The server files a report when someone stays silent

A red row on the board only helps if somebody is looking at the board. In the
situation this app is for, the person who should be looking is themselves
knee-deep in water somewhere.

So once a responder is fifteen minutes past their deadline, the server stops
waiting to be noticed and files a report at their last known position. It's a
normal HIGH report — it sits in the feed, it can be joined, it can be
resolved. The board says someone is late; this says someone needs finding.

Fifteen minutes is a guess, but it's a bounded one. Shorter and every dropped
signal becomes a callout. Longer and the alarm arrives after it mattered.

Filed under the silent person's own name, because it is about them and there
is nobody else to attribute it to. One `auto_filed_for` column stops it
filing a second: while an open report points at someone, the alarm has
already been raised.

## The sweep rides on reads, not a scheduler

There's no cron job and no background thread. The check for silence runs when
somebody loads the feed, the board or the map.

A GET that writes is not lovely and we know it. The alternative is a timer
process, and a timer process that dies takes the alarm with it — silently,
which is the worst way for an alarm to fail. The sweep is idempotent, so
polling it a hundred times a minute changes nothing after the first.

It has one real flaw: if nobody opens the app at all, nothing is checked. That
is written down in `limits.md` rather than argued away.

## The transport seam is a packet, not a radio

Our notes had LoRa on the roadmap. We still don't have radios, so we still
haven't built one.

What we did build is the thing that would have to be right first: the
*message*. `transport.py` encodes a check-in as 14 bytes and `/api/uplink`
accepts it as base64, going through exactly the same `record_checkin` as the
browser does. Both routes in end up at one function, so they can't drift
apart.

Fourteen bytes clears every LoRa data rate except the very slowest, and we
have a test that fails if the layout ever grows past a payload we'd actually
get. That's a claim we can defend. "We support LoRa" is not.

## ICS-214 out, because that's the form that already exists

Every agency at a multi-agency scene keeps an ICS 214 Activity Log: who was
assigned, when, and what happened. They're filled in by hand, usually from
memory, usually hours late.

We already store every one of those events with a timestamp on it, so
producing the form is formatting rather than remembering. It also answers the
"why log responders at all" question in a way that doesn't need us to be
adopted by anyone: the output slots into paperwork that already exists.

## Coverage gap is counted separately from staffing

"Understaffed" and "nobody is coming" look similar on a dashboard and are not
the same problem. One needs more people; the other needs anyone at all.

The banner counts only reports where both counts are zero. Someone en route
and not yet arrived takes a report out of it, because a person on the way is
the thing we were missing.

## Things we chose not to build

- **The radio itself.** We built the packet and the endpoint that accepts it;
  we have no hardware, so we have not driven an SX1276 and won't claim to.
  Untested code isn't a feature — it's a file that looks like one.
- **Identity verification.** Anyone can register as a responder. Doing this
  properly needs real ID checks or organisational affiliation and there's no
  honest weekend version.
- **Chat.** It's a worse Discord.
- **Push notifications.** Permission prompts on camera, inconsistent across
  browsers, low payoff.
