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

## What Kendra & Wachtendorf actually changes

It does not close the gap. It does something more useful: it tells us the gap
has a name in the literature, and that the field noticed it and moved on.

**Stop saying "nobody tracks the people who go in."** That is not defensible and
a reviewer will know it. The accurate version is:

> Convergence is well theorised — Fritz & Mathewson (1957) name the five
> personal converger types; Kendra & Wachtendorf add a sixth and reframe access
> as negotiated legitimacy. The established mechanism for handling converging
> helpers is **credentialing by an authority**. Credentialing presupposes an
> authority. Where none has arrived, no mechanism exists, and the literature
> does not propose one.

**The sentence that hands us the problem.** Kendra & Wachtendorf, summarising
Weick (1987) and Perrow (1977):

> "He also argues that experience with centralized direction, as in prior
> training or other socialization such as military service, is first required
> before decentralization can be effective. Yet the volunteers who appear to
> assist in the emergency response are, **virtually by definition, strangers to
> the response milieu**."

That is our problem statement, written by the field in 2001, with no technical
answer offered then or found since. A paper that opens on that sentence is
standing on the literature rather than around it.

**The finding that gives the design its argument:**

> "The most 'successful' volunteers — those who negotiated access and got past
> gatekeepers — were those who were able to work with minimal supervision by
> official emergency workers… the incorporation of these volunteers into the
> response required little or no effort on the part of emergency managers."

The scarce resource is *emergency-manager attention*. A volunteer who accounts
for themselves spends none of it. That reframes DiresQ from "a tool for
volunteers" to "a way for an unaffiliated helper to become legible without
costing the response anything" — which is the currency this paper says
determines who gets in.

**Vocabulary to adopt, because it is theirs:** response milieu, converger,
personal / informational / materiel convergence, ad hoc vs. affiliated
volunteer, negotiated legitimacy, emergent group (Stallings & Quarantelli 1985).

**Two caveats, recorded so they are not forgotten.** (1) The paper frames
volunteers as a *problem to be managed* — a security and liability risk to the
response. Our framing treats the volunteer as someone owed an accounting. Those
are different moral positions and the paper does not agree with ours; the
difference has to be argued, not assumed. (2) This is 2001 fieldwork at an
atypical event — crime scene and battlefield as well as disaster. Do not
generalise its security findings to a hurricane.

## Sources read

| Source | Claim | Evidence | Does not cover |
| --- | --- | --- | --- |
| Starbird & Palen, *Voluntweeters* (CHI 2011) | Digital volunteers self-organise after disaster with no prior structure. Fits Kreps & Bosworth's D/A/R/T model in an R→A→T→D order: Twitter itself is the *resource* that lets a stranger start. | 339 twitterers, 292,928 tweets (Haiti, Jan 10–Feb 1 2010); hand-coded 2,911 syntax tweets; 19 completed email interviews of 74 identified translators. | **Everyone in it is remote.** The population is defined as people helping from other continents. Nobody is in the hazard, so nobody needs accounting for. No safety mechanism, no check-in, no escalation — the problem does not arise. Organising runs on Twitter affordances (hashtags, @-addressivity) and interpersonal trust built over days, not on anything built for the purpose. |
| Starbird, *Crowdwork, Crisis and Convergence* (2012 diss.) | | | |
| Liu, *Crisis Crowdsourcing Framework* (CSCW 2014), 23(4):389–443 — **ABSTRACT ONLY. Paywalled at Springer (`meta-access: No`); no open-access copy found.** | A *design* framework for crowdsourcing systems: determine the why / who / what / when / where / how, then design the **STOP interfaces** — social, technological, organizational, policy — that manage the "articulation work" of coordinating across them. Built from vignettes tracing Haiti 2010 onward. | Vignettes plus synthesis of crisis informatics, disaster sociology and CSCW literature. Cannot assess the evidence properly without the body. | **Unknown — this is the open risk.** The framework tables (Table 3 and after) are behind the paywall and are exactly where a box that pre-empts us would live. What the abstract *does* show is directional: the arc described runs from spontaneous emergence toward "more established forms of public engagement" and being "integrated into official products and services." The organizational and policy interfaces presuppose an institution doing the crowdsourcing. Liu is USGS. That is the opposite direction from ours. |
| FEMA, *Managing Spontaneous Volunteers in Times of Disaster* | | | |
| ASPR TRACIE, Volunteer Management topic collection | | | |
| ERHMS framework (responder health monitoring) | | | |
| Fire service PAR / accountability software | | | |
| US 8995946 / 9497610 (personnel accountability patents) | | | |
| Kendra & Wachtendorf, *Rebel Food… Renegade Supplies* (DRC Preliminary Paper 316, 2001/02) — **read this, not the 2003 chapter.** Same authors, same fieldwork, adjacent argument; the 2003 book chapter is paywalled at Emerald. | Convergence at the WTC follows Fritz & Mathewson's types, plus a sixth (fans/supporters). Access to the *response milieu* is **negotiated legitimacy**, not a right. The volunteers who got in were those who could work unsupervised. | 750+ collective hours of field observation beginning within 48h of the attack; EOC, Javits Center, Family Assistance Center, command posts, staging areas; 500+ photographs. | **No technology of any kind.** Accountability appears only as *credentialing by an authority* — badge systems that 'evolved and intensified on almost a twice-daily basis.' The volunteer never accounts for themselves. And the volunteer's own safety is essentially absent: the hazard discussion concludes *keep untrained people out*, never *track the ones who go in*. Presupposes gatekeepers exist. |
| Kreps & Bosworth, *Organizing, Role Enactment, and Disaster* (1994) | | | *Found via Voluntweeters ref [9]. The D/A/R/T structural theory. Candidate theoretical frame.* |

## Liu 2014: what the abstract settles, and what it does not

**Settled.** Liu's contribution is a *framework for designing* crowdsourcing
systems, not a survey of systems that exist. That distinction matters more than
it sounds: a design framework cannot pre-empt a system's novelty the way a
catalogue could. It is a checklist to be applied, and applying it to DiresQ is a
thing we could do in the paper rather than a threat to be defended against.

**Also settled, and useful.** The trajectory Liu describes runs *toward*
formalisation — spontaneous emergence after Haiti, then "more established forms
of public engagement," then integration "into official products and services."
Two of the four STOP interfaces are *organizational* and *policy*. Both
presuppose an institution running the crowdsourcing effort. Liu writes from
USGS. This is the same assumption Kendra & Wachtendorf make from the other
direction, and it is now the second independent source pointing at it. Our
position — the interval before any institution exists — is the one place this
literature consistently does not reach.

**Not settled, and it is the live risk.** The framework's own tables are behind
the paywall. If a box exists that already describes self-service accountability
with no coordinator, it is in there. **Do not write §2 as though this is
resolved.**

**Two ways to close it, in order of speed:**

1. Email the author. Liu's address is on the paper: `sophialiu@usgs.gov`. She is
   a US government scientist; authors routinely send copies on request, and a
   high-school team saying plainly what they are building is a reasonable ask.
   Cost: one email, a few days.
2. Interlibrary loan through a school or public library.

Until one of those happens, §2's taxonomy paragraph stays marked `[UNREAD]`.

## Leads from Liu's citation list (99 citing papers, via EUSSET)

EUSSET's record for Liu is metadata-only — no full text — but it exposes every
paper that cites her. That list turned out to be worth more than the paper. Read
in this order:

**1. Kankanamge, Yigitcanlar, Goonetilleke & Kamruzzaman (2019), "Can volunteer
crowdsourcing reduce disaster risk? A systematic review of the literature,"
*IJDRR*.** `doi:10.1016/j.ijdrr.2019.101097`
A systematic review reads the field so we do not have to. Highest value per
hour of anything remaining on this list. If a system like ours exists, a
systematic review is where it will be named. **Read this before the Starbird
dissertation.**

**2. Auferbauer & Tellioğlu (2017), "Centralized Crowdsourcing in Disaster
Management," C&T.** `doi:10.1145/3083671.3083689`
The title addresses our exact axis. Either it argues centralisation is
necessary — in which case we have a named position to argue against, which is
better than arguing into a vacuum — or it has already explored the
decentralised alternative, in which case we need to know now. **This is the
remaining novelty risk, more than Liu herself.**

**3. Baker & Deham (2019), "For a short time, we were the best version of
ourselves: Hurricane Harvey and the ideal of community," *Int. J. Emergency
Services*.** `doi:10.1108/ijes-12-2018-0066`
Harvey is our motivating case and the outline flags every Harvey claim as
needing a source. This is that source, and it is peer-reviewed rather than
journalism.

**Also noted, lower priority:**

- Middelhoff et al. (2016), crowdsourcing field experiment simulating a flood in
  The Hague — `doi:10.1109/ict-dm.2016.7857212`. Relevant as *evaluation
  methodology*: a simulated event is how you evaluate a system like ours without
  waiting for a disaster. Read when we get serious about moving to CoRe.
- Park & Johnston (2017), framework for analysing digital volunteer
  contributions — `doi:10.1177/1461444817706877`.
- Alswailim, Hassanein & Zulkernine (2017), "A Participant Contribution Trust
  Scheme for Crisis Response Systems" — `doi:10.1109/glocom.2017.8253927`.
  Trust without a central authority. Adjacent to our problem from the security
  direction.
- dos Santos Rocha et al. (2017), "Improving the Involvement of Digital
  Volunteers in Disaster Management" — `doi:10.1007/978-3-319-68486-4_17`.
- Song, Zhang & Dolan (2020), self-organising processes of crowdsourcing,
  *Sustainability* — `doi:10.3390/su12051862`. MDPI, so open access.

**Note on strategy:** chasing Liu's PDF has become the wrong priority. Her
framework is a design checklist we can apply from the abstract. Items 1 and 2
above are where an actual collision with prior work would show up.

## Accessibility check — where the remaining papers actually are

### Open, full text, free

**Smith, Stephens, Robertson, Li & Murthy (2018), "Social Media in Citizen-Led
Disaster Response: Rescuer Roles, Coordination Challenges, and Untapped
Potential."** ISCRAM proceedings. NSF-PAR 10076203 →
`https://par.nsf.gov/servlets/purl/10076203`

**This is the §1 Harvey source, not Baker & Deham.** Semi-structured interviews
and photo elicitation on how wide-scale rescues actually happened in Greater
Houston in 2017. Citizens took one of three roles — **rescuer, dispatcher,
information compiler** — and the three coordination problems they hit were
**incomplete feedback loops**, unclear prioritisation, and communication
overload.

"Incomplete feedback loops" is our gap, named empirically, by people who
interviewed the volunteers. It is a stronger opening than anything we could
assert ourselves.

Two bonuses: it is an ISCRAM paper, so it is *also* a template for the venue we
are targeting; and it is a **Work in Progress** paper, so it shows what that
track accepts.

**Baker & Deham (2019).** NSF-PAR 10126439 →
`https://par.nsf.gov/servlets/purl/10126439`

Open, but **not what we assumed.** It is co-autoethnographic critical theory —
"ephemeral utopia", modernity as domination, institutions appropriating the
public's response. Its own limitations section says: *"This work produces theory
rather than engage in testing theory."* Do not mine it for Harvey facts or
numbers; there are none to mine. It is useful for one thing only, and it is a
good thing: it argues that institutions should *defer to the potentials of
publics rather than disdain and appropriate them*, which is a citable ally for
our §5 moral position against Kendra & Wachtendorf's framing.

### Metadata only — body still behind a paywall

**Auferbauer & Tellioğlu (2017).** EUSSET and TU Wien both hold metadata with an
empty fulltext field; ACM DL is canonical. TU Wien points at
`comtech.community/papers-full-and-short/` as a public copy, which did not
render for me — **worth trying by hand.**

**But the risk has dropped.** The full abstract is now in hand: crowdtasking is
described as *"a **centralized** form of crowdsourcing for crisis and disaster
management"*, with a prototype and a first field trial. Centralised by
declaration. That is the opposite pole from ours, which makes it a named
position to argue against rather than a claim that pre-empts us. Still read it —
their field trial is the evaluation method we want — but it is no longer the
thing most likely to sink the paper.

**Kankanamge et al. (2019).** QUT ePrints record exists at
`eprints.qut.edu.au/127136` and is indexed as having full text; the page would
not render for me. Try it directly.

### The finding that matters more than any single paper

**NSF-PAR is an open corpus for exactly this field.** US-funded crisis
informatics work is deposited there free, and browsing outward from one record
surfaced four more relevant papers in one page. **ISCRAM's own proceedings are
open access** on `ojs.iscram.org` as well. Between them, most of what §2 needs
is probably free and we have been assuming otherwise.

Also surfaced, all free on NSF-PAR, worth knowing:

- **Zhou et al. (2022), "VictimFinder: Harvesting rescue requests in disaster
  response from social media with BERT"** — 3,191 hand-labelled Harvey tweets,
  best model F1 0.919. This is the closest thing to a comparable for our
  classifier, and it is *far* stronger than ours. **Cite it in the classifier
  paragraph and be modest.** A reviewer who knows this paper and reads an
  immodest claim about our naive Bayes will not be gentle.
- Stephens et al. (2018), citizens sharing health information during a flood
  (ISCRAM).
- Mittal, Jahanian & Ramakrishnan (2020), ONSIDE — routing social media posts to
  the right first responders.
- Johnson et al. (2019), deep learning for hurricane image classification
  (ISCRAM).

## FEMA doctrine — read, and it underwrites the whole argument

*Managing Spontaneous Volunteers in Times of Disaster* (FEMA / Points of Light /
CNCS), participant materials. Open PDF via the Humanitarian Library.

This was the leg of the argument we had been **assuming rather than reading**.
§1 claimed "the field's answer is credentialing" on the strength of Kendra &
Wachtendorf watching badge systems appear at Ground Zero. That is an
observation. The doctrine is a prescription, and it says something sharper.

**It defines our user, in its own words:** unaffiliated volunteers are *"no part
of a recognized voluntary agency"*, *"often have no formal training in emergency
response"*, and are *"not officially invited to become involved."*

**It has absorbed the academic taxonomy.** *"Researchers have identified six
different groups of people that tend to converge"* — Fritz & Mathewson's five
plus the sixth Kendra & Wachtendorf added. Theory and doctrine are one lineage
here, which is useful connective tissue for §2.

**It names the operational task:** *"the helpers must be identified from among
the larger population of convergent individuals."*

**And its two mechanisms both presuppose an institution.** The Volunteer
Reception Centre processes arrivals, so it must first have been established. And
the primary mechanism is *prevention*:

> "Turn spontaneous unaffiliated volunteers into affiliated ones **before a
> disaster occurs.** People who make a pre-disaster decision to become disaster
> volunteers and take training to prepare themselves will NOT become
> spontaneous, unaffiliated volunteers after a disaster."

A training exercise asks how a community can *"keep your community members from
self-deploying"*. National service volunteers are described approvingly as
*"never self-deploy[ing], but wait[ing] to be called."*

**This is the strongest version of our gap and it is doctrinal, not inferred.**
Doctrine's answer to the person who decides at 2am that they have a boat is that
they should not exist. Handle it with respect — pre-affiliation genuinely works
— but the argument now stands on what the field prescribes rather than on what
we observed it doing.

**Still to read on the doctrine leg:** ASPR TRACIE's volunteer management topic
collection (their site did not render; try by hand). Barsky et al. (2007),
*"Managing volunteers: FEMA's Urban Search and Rescue programme and interactions
with unaffiliated responders"*, Disasters — surfaced in the same search, sounds
directly on point, not yet checked for access.

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
