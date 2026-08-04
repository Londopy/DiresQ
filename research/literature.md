# Literature matrix

Working notes for a possible paper. **This file is not a claim about DiresQ.**
It exists to find out whether there is a contribution here, and it is allowed
to conclude that there is not.

One row per source: what it claims, what evidence backs it, and what it does
not cover. The third column is the only one that becomes a paper.

Rule set before starting, so it cannot be bent later: **if three sources
already make our argument, we change the argument rather than the wording.**

---

## Status: one paper read, and it widened the gap rather than closing it

**Starbird & Palen is read.** It is the foundational paper on volunteers
self-organising after a disaster, and it contains nothing about keeping track
of anybody — because every person in it is safe at a desk on another continent.
That is not an oversight in the paper. It is the paper's scope: "digital
volunteers," remote by definition.

So the sharper version of our question is not *"has anyone done peer-to-peer
accountability?"* It is:

> The self-organising sequence Starbird & Palen document — resource, then
> activity, then task, then domain — was observed among volunteers who were
> never in danger. What changes when the same sequence runs among people who
> are physically inside the hazard? Accountability becomes a requirement rather
> than a nicety, and there is no coordinator to provide it.

That framing has a theoretical home (Kreps & Bosworth's D/A/R/T), a documented
empirical precursor, and a gap the precursor cannot cover by construction.
DiresQ is a *resource* in exactly Kreps & Bosworth's sense — the thing a
stranger picks up to start organising — aimed at the population the existing
work excludes.

**Two useful things fell out of its reference list**, both added to the table
below: Kendra & Wachtendorf on *physical* convergers and legitimacy at the WTC
(ref 8), which is the nearest prior work found so far, and Fritz & Mathewson
1957 (ref 4), which was already on the search list and is now confirmed as the
origin citation everyone routes through.

**Still unverified**, and the reason the searches below are not yet ticked:
one paper cannot establish that a gap exists. It can only establish that this
paper does not fill it.

## Earlier status: two searches in, the claim had narrowed twice

The Devpost story says *"we couldn't find one that keeps a list of the people
walking into it."* That is not going to survive review. Two rounds of
searching have found:

1. **Spontaneous volunteer management is established doctrine.** FEMA has a
   publication on it. ASPR TRACIE has a topic collection. Volunteer Reception
   Centers, credentialing, and deployment logging are standard practice, and
   commercial software does it.
2. **Responder accountability is a mature technical field.** Fire services run
   PAR (Personnel Accountability Report) processes. Commercial accountability
   software tracks responder location in real time. There are granted US
   patents on interlinking electronic identities for personnel tracking at an
   incident scene.
3. **The self-deployment problem is already named.** Practitioner literature
   describes uncontrolled self-deployment — volunteers going straight to a
   damaged neighbourhood without accountability — as a known hazard.

So the problem is real *and already recognised*. That is the honest position.

### What might still be left

Every system found so far assumes **a command structure exists**: an incident
commander running accountability, a reception centre issuing credentials, an
organisation accepting the volunteer. The Harvey boat owner has none of those,
and is the person the doctrine describes as the problem to be prevented rather
than the user to be served.

The candidate gap, stated narrowly enough to be defensible:

> Accountability mechanisms for disaster response assume an organisational
> structure — incident command, credentialing, a reception centre. Volunteers
> who self-deploy bypass all three by definition. Can accountability be made
> *peer-to-peer and self-service*, so that it functions with no dispatcher and
> no command structure at all?

The dead man's switch is the mechanism for that: escalation triggered by
**silence** rather than by a coordinator noticing.

**This is still unverified.** It needs the searches below run before anyone
writes it down as fact.

---

## Sources read

| Source | Claim | Evidence | Does not cover |
| --- | --- | --- | --- |
| Starbird & Palen, *Voluntweeters* (CHI 2011) | Digital volunteers self-organise after disaster with no prior structure. Fits Kreps & Bosworth's D/A/R/T model in an R→A→T→D order: Twitter itself is the *resource* that lets a stranger start. | 339 twitterers, 292,928 tweets (Haiti, Jan 10–Feb 1 2010); hand-coded 2,911 syntax tweets; 19 completed email interviews of 74 identified translators. | **Everyone in it is remote.** The population is defined as people helping from other continents. Nobody is in the hazard, so nobody needs accounting for. No safety mechanism, no check-in, no escalation — the problem does not arise. Organising runs on Twitter affordances (hashtags, @-addressivity) and interpersonal trust built over days, not on anything built for the purpose. |
| Starbird, *Crowdwork, Crisis and Convergence* (2012 diss.) | | | |
| Liu, *Crisis Crowdsourcing Framework* (CSCW 2014) | | | |
| FEMA, *Managing Spontaneous Volunteers in Times of Disaster* | | | |
| ASPR TRACIE, Volunteer Management topic collection | | | |
| ERHMS framework (responder health monitoring) | | | |
| Fire service PAR / accountability software | | | |
| US 8995946 / 9497610 (personnel accountability patents) | | | |
| Kendra & Wachtendorf, *Reconsidering Convergence and Converger* (2003) | | | *Found via Voluntweeters ref [8]. On physical convergers and legitimacy at the WTC. Not yet read — likely the closest prior work to our problem.* |
| Kreps & Bosworth, *Organizing, Role Enactment, and Disaster* (1994) | | | *Found via Voluntweeters ref [9]. The D/A/R/T structural theory. Candidate theoretical frame.* |

## Searches still to run

- [ ] ISCRAM proceedings: "spontaneous volunteer", "convergence",
      "accountability", "self-deployment"
- [ ] Does anything cover accountability **without** an incident commander?
- [ ] Fritz & Mathewson (1957) on convergence — the origin of the term, and
      whether physical convergence is still being studied or whether the field
      moved to informational convergence after 2010
- [ ] Crowdsource Rescue and similar Harvey-era tools: what did they actually
      track, and is there any write-up of it?
- [ ] Prior art search on the two patents above — how close do they get?

## Honest outcomes, ranked by likelihood

1. **The gap is real but small.** A short design paper at a student venue or
   ISCRAM, positioned as peer-to-peer accountability for the unaffiliated.
2. **The gap is already occupied.** Somebody has built or studied this. The
   project stays a good system and a good story, and is not a paper.
3. **The gap is real and open.** Worth a proper venue — and would need user or
   expert evaluation before submission, which does not exist yet.

Outcome 2 is not a failure. Finding out early is the entire point of doing
this step first.
