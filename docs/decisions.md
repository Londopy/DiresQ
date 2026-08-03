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
is written down in `limits.md` rather than argued away — and since the board
now shows when the sweep last ran, it is visible on the screen as well as in
the documentation. A flaw you can see is a different thing from a flaw you
have to be told about.

## The transport seam is a packet, not a radio

Our notes had LoRa on the roadmap. We still don't have radios, so we still
haven't built one.

What we did build is the thing that would have to be right first: the
*message*. `transport.py` encodes a check-in as 22 bytes and `/api/uplink`
accepts it as base64, going through exactly the same `record_checkin` as the
browser does. Both routes in end up at one function, so they can't drift
apart.

Twenty-two bytes clears every LoRa data rate except the very slowest, and we
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

## A queued report needs an id; a queued check-in gets one for free

Check-ins already carried a `client_id`, and it was easy to assume a report
could reuse the same trick unchanged. It can't, and the difference is worth
being precise about.

A check-in is idempotent by nature. It means *I am alive at this time and
place*. Sending it twice says the same thing twice, and the id is there to
keep the log tidy rather than to prevent harm. Losing one in flight costs a
timer that resets a minute later.

A report is not. Sending it twice creates **a second incident**, and duplicate
incidents are the convergence failure — six people at one address while the
next street has nobody — that this entire project exists to make visible. The
id stops being hygiene and starts being the safety property.

Which changes three things:

**It is minted before the first attempt, not in the retry path.** The check-in
queue tries the network first and writes to `localStorage` only when that
fails. A report is written down first and sent second. That ordering is the
whole design: a phone that dies mid-request, an app killed by the OS, a tab
closed in a panic — the retry after the restart carries the same id, because
the id was already on disk before anything could go wrong. There is a test
that reads `reportqueue.js` and fails if the two statements are the wrong way
round, because that bug is invisible at runtime and obvious in the source.

**It is checked server-side, before the `INSERT`.** Not by a client-side
guard, which the restart erases. Not by the `UNIQUE` constraint alone, which
only tells you about the collision after you have already tried to create it.
`create_report` looks the id up and hands back the report it already wrote.

**The plain form carries one too.** With JavaScript off there is no queue and
nothing to retry, but Back-then-Submit is the same double-file with a person
driving it. The server renders an id into the form. That created a second-order
problem — the service worker keeps a copy of the form so it can be opened with
no signal, and a cached form would hand one id to two genuinely different
reports, filing the second as a resend of the first. So `report_file.js`
replaces it on load, which is safe because a browser running the worker is by
definition running JavaScript.

## The classifier goes to the phone; duplicate detection stays on the server

The classifier is Python and it ran on the server. The person it was built for
— filing at 2am, frightened, untrained, being asked by a dropdown how bad
their own emergency is — is the likeliest of anyone to have no signal, because
a flood takes the towers out along with everything else. They were the one
person it never reached.

Three options, none free.

**Defer classification until sync and mark the priority provisional.** The one
we rejected first, because it helps nobody at the moment of filing. The
priority field is required; offline they still have to pick, still with no
help, and the server's later disagreement arrives long after the decision that
mattered. It fixes the record and not the person.

**Say nothing.** Defensible, and it is what we do for duplicates. But the
reason it is right for duplicates is precisely the reason it is wrong here —
see below.

**Port it, and we did.** With the one condition that makes it survivable:
`static/scripts/classify.js` is an evaluator, not a second classifier. The
corpus, the lexicons and the thresholds live in `classify.py` and nowhere
else; `flask --app app export-model` writes the trained counts to
`static/model/priority.json`, a test fails if the committed file has drifted
from what the code would generate today, and a parity test runs every corpus
line plus a dozen awkward cases through both implementations and fails on any
disagreement.

Two implementations of one model is a drift bug with a delay on it, and an
offline suggestion that quietly disagrees with the online one is *worse* than
no offline suggestion, because nothing on screen would say so. The parity test
is what buys the right to do this at all — and it paid for itself immediately:
it found that the words behind a suggestion were being ordered by
floating-point noise, `math.log` and `Math.log` disagreeing about the last bit
of the same expression. That was a real bug in the Python, reachable from any
machine, and it was invisible while there was only one implementation to look
at.

**Duplicate detection does not go.** It compares your description against the
reports everybody else has open right now, and that list is the exact thing
DiresQ refuses to keep on a device — a saved copy of who needs help is a lie
that gets more convincing the longer it sits there. The line falls out of the
same rule the service worker follows:

> A priority is a fact about the words you typed, and it travels.
> A duplicate is a fact about everybody else, and it does not.

So offline the panel shows the priority and says, in a sentence, that nothing
has checked whether somebody has already reported this. Not an empty list —
`duplicates: []` reads as *we looked and found none*, which is the one thing it
must not mean.

## Duplicates are checked when the report arrives, not while somebody types

The duplicate check used to live in `/api/suggest`, which is a live call made
while you type. Which meant it never ran for a report filed offline — and the
reports most likely to duplicate each other are exactly those.

The scenario, in full: two neighbours on the same street, both with no signal,
both file *"water rising on Kingsland"*. Neither can see the other's report,
because neither has a connection. Both sync. Two reports, one incident, six
people heading to one address. The check built to stop that was the one thing
that could not run.

So `link_duplicate` runs on arrival, for every report, however it got here.
Because reports are written one at a time, comparing against every open report
*at the moment this one is written* includes the ones that landed seconds
earlier in the same batch — not merely the ones that existed before anybody
went offline. That is the property the whole fix turns on.

**Distance is a veto, not a vote.** A flood on a road of the same name three
suburbs over shares all of its vocabulary and none of its incident, and text
alone cannot tell the two apart. So a match has to pass the text test first,
and being more than 500 m away is then allowed to say no. That radius is
chosen, not measured, and we would rather write that down than dress it up.

**It links; it never merges.** TF-IDF over a fifty-five line corpus is good
enough to be worth a coordinator's glance and nowhere near good enough to fold
one person's call for help into another person's row. Both reports stay in the
feed, both stay joinable, and the later one carries a line saying what it might
be a duplicate of and how alike. A false positive costs somebody a second of
reading. An automatic merge would cost somebody their report.

## Detecting a duplicate is worth nothing until the feed counts it as one

We shipped duplicate detection and then looked at what it had bought, which
was: a line of text on the second card. Both reports still sat in the feed as
separate rows. Three responders on one and three on the other rendered as two
comfortably staffed jobs.

That is the failure this project exists to expose, reproduced by the project.
**Three plus three looks fine. Six at one address is the thing.** The feed
whose entire purpose is to make convergence visible was hiding it in data it
had generated itself.

So reports linked by `dupe_of` collapse into one row. Four things had to be
true for that to be honest rather than convenient:

**Count people, not assignment rows.** The obvious implementation sums the
per-report counts, and one person who joined both duplicates becomes two
people. Inventing help that isn't there is the same lie as hiding help that
is, pointing the other way. So it counts distinct responders, and somebody en
route to one report and on scene at its twin counts once, at the further-along
status.

**The worst priority and the most cautious staffing win.** A duplicate filed
LOW must not be able to quieten a HIGH one, for exactly the reason one
responder shouting for help outranks three saying they have enough.

**The coverage-gap banner counts the incident once.** Two duplicates of one
flood with nobody going is *one street nobody is going to*. That banner is the
number we most want to be honest, and reporting it as two would inflate it.

**Nothing is merged.** The grouping is a view. Both reports stay open, both
stay individually linkable, both can still be joined and resolved on their
own, and the map still draws both pins — two people reporting one flood from
opposite ends of a street pinned two real places, and dropping one would be
inventing a certainty we don't have about which is right.

A lone report is an incident of one and renders exactly as it always did. The
common case is untouched, deliberately.

**The seed runs the real detector.** The demo shows a grouped incident on
first load, because a judge opening the hosted app for ninety seconds sees
nothing of this otherwise. But the seed does not set `dupe_of` — it inserts
two reports and calls `link_duplicate`, the same function the app calls when a
queued report lands. A demo that hand-writes its own evidence can show
something the software cannot produce, which is the failure this whole project
argues against, committed by the thing meant to demonstrate it.

That decision immediately earned itself: running the detector over reports
that already existed was the first time anything had, and it exposed a cycle.
`link_duplicate` skipped only the report it was called for, so both halves of
a pair linked to each other, the chain-walk hit its cycle guard, and the pair
silently stopped grouping. The invariant it relied on — a report is only ever
linked to an *older* one — was written in a docstring and enforced nowhere.

## A report says when it was written, not when it arrived

The check-in queue already solved this once, and a report needed the same
treatment for a sharper reason.

A check-in stamped on arrival silently cancels an overdue alarm: somebody
silent through their whole window comes back green the moment their phone
finds a bar. A report stamped on arrival is worse than silent — it is
*loud and wrong*. A description written forty minutes ago is a description of
a house that may already have been cleared, and rendering it as breaking news
sends the next available person to an address nobody needs to be at, while the
street that filed thirty seconds ago sits below it.

So reports carry both times. `created_at` is when it was written — a claim
from a client, bounded exactly like a check-in's, because a claim is what it
is. `received_at` is ours. The feed orders on `created_at`, which is the
honest place for it, and any report where the gap is big enough to matter says
so on the card and again on the page: *written 40 minutes ago, reached us
later — treat it as that old, not as new.*

The alternative was to show one time and pick which. Every version of that we
tried was a lie in one direction or the other.

## Resolving a report has to tell the people driving to it

Resolving clears everyone still attached. It told none of them.

Which means the app was quietly doing the exact thing it exists to prevent —
sending people to an address nobody needs them at — to its own responders. A
person who joined twenty minutes ago is in a car with the phone in a pocket.
They find out by refreshing a page they are not looking at.

Three decisions inside it:

**It does not expire.** A notice that clears itself after an hour is a notice
missed by precisely the person it was written for. It stays until they press
*Got it*.

**Whoever pressed Resolve is not told to stand down.** They were standing
there, they made the call, and the obvious implementation tells them anyway —
because resolving clears the resolver too. `cleared_reason` distinguishes *you
decided* from *this was decided for you*.

**It goes in `/api/me`, which means it survives being offline.** That endpoint
is the one thing the service worker may keep, and the bar for that is high: a
saved claim has to still be true later. A resolved report does not un-resolve.
So it qualifies, and it is the only thing on the offline page that can tell
somebody to turn the car around.

## The classifier had to be able to say "I can't read this"

Naive Bayes cannot abstain. Hand it words it has never seen and every class
falls back to its prior, and it still returns a label and a confidence.

Typed in Spanish, *"mi madre no puede respirar"* — my mother cannot breathe —
came back **LOW, at 51%, and was shown to the person filing it.** Katy is
roughly a third Hispanic or Latino, so this was never a hypothetical.

We could have added Spanish training data. Fifty-five examples in one language
is already a demonstration rather than a dataset; making it a hundred and ten
across two would have been worse at both. The honest move is not to widen what
it claims to read, it is to make it admit the edge of what it can.

So it abstains, and the form says why rather than going quiet — silence reads
as *no opinion, carry on*, and this is exactly the report where the dropdown
matters most.

**We were careful not to call it language detection.** The rule is *the model
has not seen these words*, which is also true of English full of unfamiliar
street names, and that gets refused too. Claiming to detect Spanish would be a
claim we cannot back; claiming not to recognise the vocabulary is just a fact
about the model.

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
- **Automatic merging of duplicate reports.** We detect them and link them.
  Merging on a fifty-five example model would eventually delete a real call
  for help, and the person it belonged to would never know.
- **Offline duplicate detection.** Not a limitation we ran out of time to
  fix — it would require keeping everybody else's open reports on the device,
  which is the one thing this app refuses to do. See above.
