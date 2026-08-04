# Literature matrix

Working notes for a possible paper. **This file is not a claim about DiresQ.**
It exists to find out whether there is a contribution here, and it is allowed
to conclude that there is not.

One row per source: what it claims, what evidence backs it, and what it does
not cover. The third column is the only one that becomes a paper.

Rule set before starting, so it cannot be bent later: **if three sources
already make our argument, we change the argument rather than the wording.**

---

## Status: two searches in, the claim has narrowed twice

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
| Starbird & Palen, *Voluntweeters* (CHI 2011) | | | |
| Starbird, *Crowdwork, Crisis and Convergence* (2012 diss.) | | | |
| Liu, *Crisis Crowdsourcing Framework* (CSCW 2014) | | | |
| FEMA, *Managing Spontaneous Volunteers in Times of Disaster* | | | |
| ASPR TRACIE, Volunteer Management topic collection | | | |
| ERHMS framework (responder health monitoring) | | | |
| Fire service PAR / accountability software | | | |
| US 8995946 / 9497610 (personnel accountability patents) | | | |

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
