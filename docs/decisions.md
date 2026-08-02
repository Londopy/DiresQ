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

## Things we chose not to build

- **LoRa.** It's in our roadmap notes as roadmap only. We don't have radios,
  which means we couldn't test it, and untested code isn't a feature — it's a
  file that looks like one.
- **Identity verification.** Anyone can register as a responder. Doing this
  properly needs real ID checks or organisational affiliation and there's no
  honest weekend version.
- **Chat.** It's a worse Discord.
- **Push notifications.** Permission prompts on camera, inconsistent across
  browsers, low payoff.
