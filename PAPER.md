# "Can We Account for Everyone?" Silence-Triggered Escalation for Volunteers Who Self-Deploy

**London Chowdhury** and **Jesslyn Caroline**

> **DRAFT — NOT FOR SUBMISSION.** Assembled automatically from the section
> drafts in `research/`, which remain authoritative. Four items must be resolved
> first; see *Outstanding before submission* at the end.

**Keywords:** crisis informatics; spontaneous volunteers; convergence;
unaffiliated volunteers; accountability; self-deployment; offline-first design

## Abstract

Convergence, the spontaneous movement of people toward a disaster, has been
documented since Fritz and Mathewson (1957). Practice manages converging
volunteers through credentialing: reception centres, badge systems, and
pre-disaster affiliation. Each presupposes an institution that has either
already arrived or reached the volunteer months beforehand. In the interval
before either holds, people are already going in, and no accountability
mechanism covers them. Interviewing Hurricane Harvey rescuers, Smith et al.
(2018) record a dispatcher asking whether "we [can] account for everyone."

We report the design of DiresQ, an open-source system attempting
accountability for unaffiliated volunteers with no coordinator. It escalates
on silence rather than supervision: a responder states an expected arrival
time and checks in periodically, and if they stop, the system files a report
about them without anyone deciding to.

DiresQ has no users, no field deployment, and no evaluation. We contribute a
design rationale, five design trade-offs stated with their costs, and five failure modes encountered during construction.

## 1. Introduction

When a disaster is large enough, people go toward it. This is among the oldest
findings in disaster sociology. Fritz and Mathewson named it in 1957 —
*"the informal, spontaneous movement of people, messages, and supplies toward
the disaster area"* — and catalogued five kinds of person who arrive: the
returnees, the anxious, the helpers, the curious, and the exploiters. Their
report is subtitled *A Problem in Social Control*, and the observation it opens
with has not dated: convergence *"brings needed aid to many victims, but at the
same time the resultant congestion makes organization and control of the rescue
and relief efforts more difficult."* Kendra and
Wachtendorf (2002), studying the response to the World Trade Center attack,
added a sixth and reframed the central question. Access to what they call the *response
milieu* is not granted; it is negotiated. A volunteer's admission depends on
whether the people already inside can afford them.

The mechanism the field has developed for that negotiation is **credentialing**.
Volunteer reception centres, badge systems, affiliation with a recognised
organisation: these convert an unknown arrival into an accountable one. They
work. At the World Trade Center, identification requirements *"evolved and
intensified on almost a twice-daily basis"* as the response matured.

Practitioner doctrine is more explicit still, and defines our population for us.
FEMA's guidance on managing spontaneous volunteers describes unaffiliated
volunteers as those who are *"no part of a recognized voluntary agency"*, who
*"often have no formal training in emergency response"*, and who — the phrase is
theirs — are *"not officially invited to become involved."* It adopts the
academic taxonomy directly, noting that *"researchers have identified six
different groups of people that tend to converge"*, and identifies the
operational task: *"the helpers must be identified from among the larger
population of convergent individuals."*

The doctrine offers two mechanisms for doing that identification, and both
presuppose an institution. The first is the Volunteer Reception Centre, which
processes arrivals — and must therefore have been established. The second, and
the one the guidance treats as primary, is prevention:

> "Turn spontaneous unaffiliated volunteers into affiliated ones **before a
> disaster occurs.** People who make a pre-disaster decision to become disaster
> volunteers and take training to prepare themselves will NOT become
> spontaneous, unaffiliated volunteers after a disaster."

The same materials pose, as a training exercise, the question of how a community
can *"keep your community members from self-deploying"*, and describe organised
national service volunteers approvingly as members who *"never self-deploy, but
wait to be called."*

We take this seriously rather than dismissively: pre-affiliation plainly works,
and a trained volunteer who arrives when called is better for everyone than one
who does not. But both mechanisms require an institution — one that reached the
volunteer months beforehand, or one that has arrived and opened a reception
centre. Neither covers the person who decides at two in the morning, on the
night, that they have a boat. Doctrine's answer to that person is that they
should not exist. They do exist, in thousands, and the events that produce them
are the events where the institution is least able to arrive.

Kendra and Wachtendorf state the resulting tension directly, summarising Weick
and Perrow on decentralised coordination: effective decentralisation presupposes
prior socialisation into an organisation's norms, *"yet the volunteers who
appear to assist in the emergency response are, virtually by definition,
strangers to the response milieu."* The literature names the problem and, so far
as we have found, proposes no mechanism for the interval before command exists.

Hurricane Harvey makes the interval concrete. In August 2017 flooding in the
Greater Houston area affected an estimated 30,000–40,000 homes, and city
officials and FEMA publicly asked citizens with boats to help reach people
trapped inside them (Smith et al., 2018). Thousands came. They organised through
Zello, a push-to-talk application, along with Facebook groups, NextDoor, ad hoc
Google spreadsheets, and applications written during the event itself.
Interviewing twenty of these volunteers, Smith et al. found at least twenty
distinct groups with, between them, *"no way to seamlessly share information and
coordinate activity."* Affiliation was nominal: membership of the loose "Cajun
Navy" was *"fleeting"*, leadership *"fluid and dispersed"*, boundaries unclear.

What went wrong is documented in the volunteers' own words. One dispatcher
described the coordination problem exactly:

> "it became overwhelming just trying to keep track of who was going out who was
> coming back who was out on a boat, **can we account for everyone**, and who's
> in their house and it was a mess." — Gary, in Smith et al. (2018)

The gap this paper addresses is not one we inferred. It was stated by a person
who was in it.

Smith et al. name three coordination failures — incomplete feedback loops,
unclear prioritisation, and communication overload — and close by calling for
*"the design of intuitive systems that can quickly be mastered by the novice
social media user."* This paper is an attempt at one narrow part of that.

Two details from that study bear directly on the design that follows. First, the
accountability function was being performed — badly — by *families*: rescuers
reported phones "constantly blowing up" with relatives asking *"are you okay,
are you okay, are you okay."* Somebody was always going to ask the question; the
question simply had nowhere to be answered. Second, volunteers' phones were
destroyed by rain and floodwater in numbers large enough that many replaced them
afterwards — which is direct evidence that silence and danger are genuinely
different things, and that any system escalating on silence will produce false
alarms.

This paper reports the design of **DiresQ**, a system that attempts
accountability for such volunteers without a coordinator. Its central move is to
escalate on **silence** rather than on supervision: a responder states an
expected arrival time and checks in periodically, and if they stop, the system
files a report about them automatically. Nobody has to notice.

We are explicit about what this paper is not. DiresQ has never been used in a
real disaster. It has no users, no deployment beyond a public demonstration
instance, and no evaluation. We report a design, the reasoning behind five
specific trade-offs, and the failure modes we encountered building it — several
of which we consider more transferable than the system itself. Readers looking
for evidence that this approach works will not find it here, and we would
regard any such reading as a misuse of the paper.

## 2. Background and related work

### 2.1 Convergence

People moving toward a disaster is one of the field's oldest documented
behaviours. Fritz and Mathewson (1957) named it *convergence behavior* —
*"the informal, spontaneous movement of people, messages, and supplies toward
the disaster area"* — and observed that it *"brings needed aid to many victims,
but at the same time the resultant congestion makes organization and control of
the rescue and relief efforts more difficult."* They separate movement *"toward
the struck area from the outside — external convergence"* from *"movement toward
specific points within a given disaster-related area or zone — internal
convergence"*, distinguish three forms (personal, informational, materiel), and
catalogue five types of personal converger: the returnees, the anxious, the
helpers, the curious, and the exploiters.

It is worth noting that the founding treatment frames convergence as a control
problem — its subtitle is *A Problem in Social Control* — and that this framing
has been remarkably durable. The paper's own position is stated in §5.

Kendra and Wachtendorf (2002), studying the response to the World Trade Center
attack across more than 750 collective hours of field observation, added a sixth
— supporters or fans — and, more importantly for us, reframed the question.
Access to what they term the *response milieu* is not a status a volunteer
holds but one they negotiate.

The taxonomy has passed into practice. FEMA's guidance on managing spontaneous
volunteers reproduces it directly, noting that *"researchers have identified six
different groups of people that tend to converge"*, and derives an operational
task from it: *"the helpers must be identified from among the larger population
of convergent individuals."* Theory and doctrine here are a single
lineage rather than two literatures, which is why we cite them together.

DiresQ's users are helpers, converging externally and then internally.

### 2.2 Legitimacy, credentialing, and what both presuppose

Kendra and Wachtendorf's central finding concerns who gets in. (We cite their
Disaster Research Center preliminary paper throughout, because it is the text
we read; the 2003 book chapter develops the same fieldwork and is listed in the
references for completeness.) At the World
Trade Center, identification requirements *"evolved and intensified on almost a
twice-daily basis"*, and volunteers became *"another group that needed to be
accounted for, and therefore potentially a distraction that outweighed their
utility."* The volunteers who succeeded in gaining access were those who
*"were able to work with minimal supervision by official emergency workers"* —
whose incorporation *"required little or no effort on the part of emergency
managers."*

We take the scarce resource in that account to be emergency-manager attention,
and it is the frame we design against: a volunteer who accounts for themselves
spends none of it.

Doctrine's mechanisms for conferring legitimacy are the Volunteer Reception
Centre and, prior to any event, pre-affiliation — *"turn spontaneous unaffiliated
volunteers into affiliated ones before a disaster occurs."* Both
presuppose an institution: one that has arrived and opened a centre, or one that
reached the volunteer months earlier. We develop the consequence in §1 and do
not repeat it here.

### 2.3 Digital volunteers, and why they need no accounting for

Starbird and Palen (2011) provide the foundational study of volunteers
self-organising through technology after a disaster, examining 292,928 tweets
and interviewing nineteen of the "voluntweeters" who emerged after the 2010
Haiti earthquake. They read the phenomenon through Kreps and Bosworth's
structural theory, finding a resource → activity → task → domain progression in
which the *resource* — Twitter, and the individual capacities it made usable —
is what lets a stranger begin.

The distinction that matters for this paper is one their scope makes for us:
their volunteers are remote by definition. The population is people helping from
other continents. No participant is in the hazard, so no participant needs
accounting for, and no mechanism for doing so appears in the paper. This is not
a gap in their work. It is the boundary of ours.

Our question is what changes when that same self-organising sequence runs among
people who are physically inside the hazard. Accountability stops being optional
and there is still nobody to provide it.

### 2.4 Citizen-led response in practice

Smith et al. (2018) interviewed twenty participants in the citizen-led rescues
during Hurricane Harvey and found three roles — rescuer, dispatcher, information
compiler — distributed across at least twenty distinct groups with *"no way to
seamlessly share information and coordinate activity."* They report three
coordination failures: incomplete feedback loops, unclear prioritisation, and
communication overload.

Incomplete feedback loops is our problem under another name. Their account of it
is mechanical rather than motivational: rescue platforms depended on someone
manually marking a case closed, and in practice the case number was forgotten,
the phone was destroyed, or a different boat reached the address first. The loop
stayed open not because anyone neglected it but because closing it required an
action at exactly the moment nobody had attention to spare.

We note two of their findings as constraints on our design rather than support
for it. First, their participants wanted *more* coordination: one dispatcher
argued that *"people that are trained to do that need to be in charge of
prioritizing calls and assigning."* Second, over-convergence was itself a
failure mode — boats were turned away from neighbourhoods that already had too
many. We return to both in §5.

### 2.5 Systems for crisis crowdsourcing

Liu (2014) offers the field's most developed design framework, organising a
crowdsourcing system around why / who / what / when / where / how, and around
the social, technological, organisational and policy interfaces that manage the
articulation work of coordinating across them. We note that two of
those four interfaces presuppose an organisation conducting the effort, and that
the trajectory the framework describes runs toward formalisation and integration
*"into official products and services."* Our position is upstream of that
trajectory rather than opposed to it.

Auferbauer and Tellioğlu (2017) describe *crowdtasking*, presented explicitly as
*"a centralized form of crowdsourcing for crisis and disaster management"*, with
a prototype and a first field trial. It is the clearest statement
of the opposite design position to ours, and we cite it as such: where
crowdtasking assumes an organisation able to task a registered crowd, we assume
neither the organisation nor the registration.

Kankanamge et al. (2019) provide a systematic review of volunteer crowdsourcing
in disaster risk reduction. We have not obtained the full text and
therefore make no claim about its findings; it is listed here because a reader
working in this area will expect to see it and should know we are aware of it.

Technical work on the classification side is considerably more advanced than
ours. Zhou et al. (2022) fine-tune BERT variants over a hand-labelled corpus of
Hurricane Harvey tweets to identify rescue requests, and substantially outperform
the earlier baselines they compare against. Our own priority suggestion (§3.3) is a naive
Bayes classifier over a small hand-labelled corpus, and is not competitive with
this work, nor intended to be: it exists to run in a browser with no network,
which is a different constraint rather than a weaker attempt at the same one.

### 2.6 Where this leaves the gap

Convergence is thoroughly theorised. Legitimacy is theorised and operationalised.
Digital volunteering is well studied among remote participants. Crowdsourcing
systems have a design framework and at least one field-trialled centralised
implementation. Classification of rescue requests is a mature technical problem.

What we have not found, in the literature or the doctrine, is a mechanism for
accounting for physically converging helpers during the interval before an
institution exists to do it. Doctrine's answer is that those people should have
been affiliated beforehand. The academic literature describes their arrival as a
management problem. Neither addresses the person already in the water.

That interval is this paper's subject, and the design in §3 is one attempt at it.

## 3. Design

DiresQ is a server-rendered web application: Flask, SQLite, no client framework,
no account approval step, and no dispatcher role. Thirty-three routes over six
tables. The stack is deliberately unremarkable, and we describe it only to
establish that nothing in what follows depends on infrastructure a volunteer
organisation would not already have. The contribution is not the stack.

Anyone can sign up. There is no verification of identity, no vetting, and no
administrator who admits people. This is not an oversight we intend to fix; it
is the condition the system is designed for. A tool that requires somebody to
approve you has reintroduced the coordinator whose absence is the entire
problem.

### 3.1 The mechanism

A report is a place that needs help. A responder who decides to go there joins
the report and, in doing so, states an expected time of arrival. The ETA is
bounded between five and 240 minutes and warns above 120 — not because longer
journeys are invalid, but because an unbounded ETA makes the subsequent
arithmetic meaningless. From that point the responder is expected to check in;
the interval defaults to thirty minutes.

If a responder stops checking in, they are marked overdue. Fifteen minutes past
that threshold, the system files a report *about them* — their last known
location becomes an incident in the same feed everyone else is reading. No human
decides this. No human is asked to notice.

This is the whole mechanism, and its only novel property is what triggers it.
Existing accountability systems escalate when a coordinator observes that
somebody has not reported in. We escalate on the observation itself being
absent. Silence is available in circumstances where a supervisor is not.

### 3.2 Five decisions, and what each one cost

The design is small enough that the interesting content is not the architecture
but the trade-offs. We describe five, each of which we got wrong first.

**Silence as the trigger.** The alternative designs all require somebody to be
watching: a dispatcher view, an alert queue, a supervisor role. Each of them
works, and each of them assumes the thing we cannot assume. Escalating on
absence needs nobody. The cost is that absence is ambiguous — a responder who
has stopped answering may be in trouble, or may have a dead phone, or may have
gone home without saying so. The system cannot tell these apart and does not
claim to. It reports *contact lost*, never *safe* or *unsafe*, and the interface
language was rewritten twice to stop implying otherwise.

**No in-process timer.** Our first design ran the silence check on a background
thread inside the application. We removed it. A thread that dies takes the alarm
with it and leaves the interface showing green, and a green screen is read as a
positive result rather than an absent one. The check now runs on read: whenever
anyone loads the accountability board, the sweep runs first, rate-limited to
once every thirty seconds. An *external* scheduler is supported and optional
(`flask --app app sweep` from cron or Task Scheduler) — deliberately external,
because an external scheduler that fails is at least visible to the machine
running it, which an in-process timer is not.

This trades one dependency for another. A timer that might die becomes a check
that depends on being watched. We consider that the better failure — an
unwatched board is a situation where nobody is relying on the result — but the
substantive move is that we made the dependency **visible** rather than
documenting it. The board displays how long since the last sweep and turns amber
past five minutes. On a board somebody is actually watching, the number always
reads a few seconds, because the watching is what runs it. A limitation you can
see on screen is a different claim from one the user has to be told about.

**Status and contact are different facts.** What a responder last told us is one
thing; whether they are still answering is another. We conflated them, and the
result was a report page displaying "on scene" for somebody the accountability
board had forty-five minutes overdue. Anyone opening that report to decide
whether the address needed more help was counting a person who had gone silent
as help present. Both facts are now shown, and neither is inferred from the
other. Somebody who has explicitly cleared is not chased, because going home is
not going quiet.

The general form of this: in a system whose purpose is knowing where people are,
*self-reported state* and *liveness* must never be collapsed into one field,
however tempting the simplification is at the schema level.

**Refusing to cache claims about other people.** The offline layer keeps the
things you committed to — your own assignments, a queued report you filed
without signal — and refuses to keep the report feed or the accountability
board. A cached feed is a list of who needed help twenty minutes ago. Acting on
it sends somebody to an address that has been cleared, and the person reading it
has no way to know the difference between stale and current. A test fails if
either page is added to the service worker's shell list.

The generalisable claim, and the one we would defend: **correct-when-written and
correct-when-read are different guarantees**, and disaster data has an unusually
short half-life between them. Offline-first design literature tends to treat
availability as an unalloyed good. For a class of data it is not, and the
distinction is not about staleness tolerance but about whether a stale answer is
*actionable* — whether a user can be sent somewhere by it.

**Not storing triage answers.** The system includes a START triage helper that
orders which reports get attention first. The answers are health observations
about a person who did not consent and is likely in no position to. They are
used to compute an ordering and then discarded; nothing about a casualty's
breathing or perfusion is written to the database. The cost is that the ordering
cannot be audited after the fact, which is a real loss. We accepted it.

### 3.3 Priority suggestion

A report can be given a suggested priority by a multinomial naive Bayes
classifier over a severity lexicon, trained on a small hand-labelled corpus and
validated by leave-one-out cross-validation with a floor asserted in continuous
integration.

We describe it in one paragraph deliberately. It is the least interesting
component and the one most likely to be mistaken for the contribution. It
suggests an ordering for human attention; it does not predict outcomes, assess
medical severity, or make any claim that survives the person reading the report
disagreeing with it. A model small enough to ship as a frozen table of word
counts is also small enough to run in the browser, which is why priority
suggestion works with no signal while the report feed deliberately does not.

### 3.4 What the design does not attempt

It does not summon help. No dispatcher reads it, it does not call emergency
services, and the disclaimer on every page is load-bearing rather than legal
decoration. It does not verify that anybody is who they say they are. It does
not know where anyone actually is — location is self-reported throughout. It
makes no claim that a responder is safe; only that we have or have not heard
from them.

These are stated here rather than only in §5 because a reader who reaches the
limitations section still holding the wrong model of the system has already
misread the design.

## 4. What building it taught us

We report these as observations from construction, not as validated findings.
Each began as a specific bug or reversal and generalised afterwards.

### 4.1 Correct-when-written and correct-when-read are different guarantees

The offline layer was originally designed to cache what a user would want if
their signal dropped, which is nearly everything. We now cache almost nothing.

The rule we arrived at: **do not store anything that stops being true when it is
written.** Your own commitments — the assignment you accepted, a report you
filed with no signal — remain true offline, because they are statements about
you. The report feed and the accountability board are statements about other
people, and both decay. A cached feed is a list of who needed help twenty
minutes ago; a responder acting on it is dispatched to an address that has since
been cleared, with no way to distinguish that from a current one.

Offline-first design generally treats availability as an unalloyed good, with
staleness managed by tolerance windows and revalidation. We think the useful
distinction is not how stale the data is but whether a stale answer is
*actionable* — whether a user can be sent somewhere by it. Data that can move a
body should not be served from cache at all. A test fails if either page is
added to the service worker's shell list, because the rule is easy to forget and
the failure is silent.

### 4.2 An alarm that dies quietly is worse than no alarm

The silence check was first designed as a background thread inside the
application. We removed it. A timer that dies takes the alarm with it and leaves
the interface showing green, and a green screen is read as a positive result
rather than an absent one.

The check now runs on read — whenever anyone loads the accountability board,
rate-limited to once every thirty seconds. An external scheduler is supported
(`flask --app app sweep`) and deliberately optional: an external scheduler that
fails is at least visible to the machine running it, which an in-process timer
is not.

This does not remove the dependency, it relocates it. The system now works while
somebody is looking. We regard that as the better failure mode, because a board
nobody is watching is a situation where nobody is relying on the answer — but
the claim needs stating rather than assuming.

### 4.3 A limitation on screen is a different claim from a limitation in a file

The consequence of §4.2 is that the guarantee is conditional, and our first
response was to write that down in a limitations document. That is the standard
move and we now think it is insufficient.

The board displays how long since the last sweep — *checked 2s ago* beside the
live indicator, amber past five minutes, which is ten minutes before the
fifteen-minute escalation it drives. On a board somebody is watching it always
reads a few seconds, because the watching is what runs it. If it stops moving,
that is visible too.

The general form: **emergency software should surface its own liveness.** A user
deciding whether to trust a screen needs to know whether the thing behind it ran,
and that is a different question from whether the data looks reasonable. We would
extend this beyond our own system: any interface that reports on a periodic
check should display when the check last completed, not merely its result.

### 4.4 The pages built to be watched were the ones that broke under watching

The board, the map and the feed all run the silence check before answering, and
the check writes. SQLite's default journal mode lets one writer lock out every
reader. With several people watching a board that refreshes every three seconds,
a write could wait past its timeout and fail the entire response.

The pages whose purpose is to be watched continuously during an emergency were
precisely the pages that failed when watched continuously. The fix was
unremarkable — write-ahead logging, rate-limiting the sweep, catching the
failure rather than letting it become an error page. The lesson is not about
SQLite. It is that **making a read-only page write is a change of kind, not of
degree**, and in this system it converted the most-loaded pages into the most
fragile ones.

One deliberate detail: a failed sweep does not record itself as having run. The
timestamp goes stale and the board reports that in amber, which is true, because
a check we could not record is not a check we can claim.

### 4.5 Prose about a system lags the system

Our test suite verifies every count in our own documentation — routes, tables,
tests, lines — and fails when the prose and the repository disagree. It has
caught wrong numbers repeatedly, including several we wrote ourselves.

It has never once caught the more common error, which is a *sentence* that
describes a previous version of a behaviour. Four times a change landed and the
paragraph explaining it stayed a revision behind. Numbers are checkable and were
checked; claims are not, and were not.

We do not have a solution and offer this as an observation: automated
documentation checks create a real assurance about the class of statement they
can verify and no assurance whatever about the class they cannot, and the second
class is where the misleading statements live.

## 5. Limitations

The system has eighteen documented limitations, maintained as a first-class
document rather than an appendix. We summarise the ones that most constrain what
this paper claims.

**It has never been used in a real disaster.** Everything here is reasoned from
published accounts of Harvey, Kathmandu and Mexico City, and from published
triage protocol. None of it has been tested by somebody standing in water at two
in the morning. We believe the reasoning is sound; that is not the same as
knowing it works, and no part of this paper should be read as evidence that it
does.

**The switch depends on being run.** Described in §4.2. Neither the read-trigger
nor an external scheduler is guaranteed. A deployment nobody looks at and nobody
configures performs no checks.

**Overdue measures contact, not safety.** The system reports that it has not
heard from somebody. It cannot distinguish danger from a dead battery, and it
does not try. The interface language was revised twice to stop implying
otherwise, and this is the limitation most likely to be misread by a user in a
hurry.

**No identity verification.** Anyone can register. This is a design condition
rather than a defect — a system requiring approval has reintroduced the
coordinator whose absence is the problem — but it means the system cannot
distinguish a responder from someone claiming to be one.

**Location is self-reported** throughout. The map shows where people said they
were.

**One cautious responder can hold a report open**, which biases the system toward
over-reporting need. We prefer that direction and note that we chose it.

**Lockouts live in memory** and do not survive a restart.

**The volunteers we claim to serve asked for the opposite.** Smith et al. (2018)
interviewed twenty Harvey rescuers and dispatchers, and the structural complaint
that came back was a wish for *more* coordination, not less. One dispatcher, on
being unable to prioritise calls: *"people that are trained to do that need to be
in charge of prioritizing calls and assigning."* Another described sending boats
away because too many had converged on one neighbourhood.

This is the strongest available argument against our design, and it comes from
the population the design is for. We do not think it defeats the argument — the
wish for a trained coordinator does not summon one, and the interval before one
exists is exactly our subject — but a reader should weigh it. A system that
makes self-deployment easier and better-accounted-for may also make it more
attractive, and Smith et al. document a response that suffered from too many
boats as well as too little information.

### A position rather than a finding

The literature we build on treats converging volunteers as a population to be
managed: Kendra and Wachtendorf document access as negotiated legitimacy, with
credentialing, liability and security as the operative concerns, and volunteers
as a potential distraction that must outweigh its own cost. Our design treats
the volunteer as somebody owed an accounting.

These are different moral starting points, and the literature does not share
ours. We think ours is defensible — a person who walks into a hazard to help is
owed something regardless of whether an institution has authorised them — but it
is a position, not a result, and a reader is entitled to reject it and evaluate
the design on the field's own terms instead.

## 6. Future work

The obvious next step is the one we have not taken: contact with people who do
this work. Five structured interviews with volunteer-response coordinators —
people who have run a reception centre, or turned volunteers away, or gone in
unaffiliated themselves — would test the assumption the whole design rests on,
which is that the interval before credentialing exists is a real operational gap
rather than an artefact of how we read the literature.

Beyond that, a simulated-event walkthrough is the tractable route to evaluation
without waiting for a disaster; the crisis informatics community has precedent
for this. It would let us observe whether the silence mechanism produces
escalations at useful times, or whether it mostly produces false alarms from
people whose phones died — a distinction we currently cannot make.

Two smaller questions we would want answered. Whether the fifteen-minute
escalation delay is anywhere near right; we chose it by reasoning, not by
measurement, and it is the kind of parameter that ought to come from data.
And whether making system liveness visible on screen — the sweep timestamp
described in §4.3 — actually changes how much a user trusts what they are
reading, or whether it is a designer's satisfaction that no user notices.

We are aware that all of this describes work requiring access to a professional
community that two secondary-school students do not have. We would welcome
collaboration, and we mention it here rather than in an acknowledgement because
it is a limitation on the research, not a courtesy.

## References

*Format to the venue's template when it is known. Alphabetical for now.*

Auferbauer D, Tellioğlu H. Centralized Crowdsourcing in Disaster Management:
Findings and Implications. In: *Proceedings of the 8th International Conference
on Communities and Technologies (C&T '17)*; 2017 Jun 26–30; Troyes, France. New
York: ACM Press; 2017. p. 173–182. DOI: 10.1145/3083671.3083689

Baker ND, Deham M. For a short time, we were the best version of ourselves:
Hurricane Harvey and the ideal of community. *International Journal of Emergency
Services*. 2019. DOI: 10.1108/IJES-12-2018-0066. Open access via NSF-PAR 10126439.

Federal Emergency Management Agency. *Managing Spontaneous Volunteers in Times
of Disaster: The Synergy of Structure* — participant materials. Washington DC:
FEMA / Points of Light Foundation.

Fritz CE, Mathewson JH. *Convergence Behavior in Disasters: A Problem in Social
Control*. Committee on Disaster Studies. Washington DC: National Academy of
Sciences – National Research Council; 1957.

Kankanamge N, Yigitcanlar T, Goonetilleke A, Kamruzzaman M. Can volunteer
crowdsourcing reduce disaster risk? A systematic review of the literature.
*International Journal of Disaster Risk Reduction*. 2019;35:101097.
DOI: 10.1016/j.ijdrr.2019.101097

Kendra JM, Wachtendorf T. *Rebel Food… Renegade Supplies: Convergence after the
World Trade Center Attack*. Preliminary Paper 316. Newark DE: Disaster Research
Center, University of Delaware; 2002.

Kendra JM, Wachtendorf T. Reconsidering Convergence and Converger Legitimacy in
Response to the World Trade Center Disaster. In: *Terrorism and Disaster: New
Threats, New Ideas*. Research in Social Problems and Public Policy, vol. 11;
2003. p. 97–122. DOI: 10.1016/S0196-1152(03)11007-1

Liu SB. Crisis Crowdsourcing Framework: Designing Strategic Configurations of
Crowdsourcing for the Emergency Management Domain. *Computer Supported
Cooperative Work (CSCW)*. 2014;23(4–6):389–443. DOI: 10.1007/s10606-014-9204-3

Smith WR, Robertson BW, Murthy D, Stephens KK, Li J. Social Media in
Citizen-Led Disaster Response: Rescuer Roles, Coordination Challenges, and
Untapped Potential. In: *Proceedings of the 15th ISCRAM Conference*; 2018 May;
Rochester NY. p. 639–648. Open access via NSF-PAR 10076203.

Starbird K, Palen L. "Voluntweeters": Self-Organizing by Digital Volunteers in
Times of Crisis. In: *Proceedings of CHI 2011*; 2011 May 7–12; Vancouver BC.

Zhou B, Zou L, Mostafavi A, Lin B, Yang M, Gharaibeh N, Cai H, Abedin J,
Mandal D. VictimFinder: Harvesting rescue requests in disaster response from
social media with BERT. *Computers, Environment and Urban Systems*.
2022;95:101824. DOI: 10.1016/j.compenvurbsys.2022.101824

**Cited through other authors, not read directly.** Kreps & Bosworth (1994) via
Starbird & Palen; Weick (1987) and Perrow (1977) via Kendra & Wachtendorf;
Stallings & Quarantelli (1985) via Kendra & Wachtendorf and Smith et al. Each
must be read or explicitly marked as reported-by before submission.

---

## Outstanding before submission

**1. Which Kendra & Wachtendorf.** Every quotation attributed to them here — the
twice-daily badge escalation, volunteers as "another group that needed to be
accounted for", the "minimal supervision" finding, and the Weick/Perrow
"strangers to the response milieu" sentence — was read in **Preliminary Paper
316 (2002)**, not the 2003 book chapter. The chapter is the more citable work
and we have not read it. **Cite PP 316 for every quotation, or obtain the
chapter and re-verify each one.** Citing the chapter for words read elsewhere
would be precisely the failure §5 argues against.

**2. Three sources still unread.** Liu (2014), Auferbauer & Tellioğlu (2017) and
Kankanamge et al. (2019) are cited only for positions their abstracts state
outright. Zhou et al. (2022) is Bronze open access and readable in a browser —
verify the F1 of 0.919 and the 3,191-tweet corpus there before printing them.

**3. AI usage disclosure.** To be written by the authors in Overleaf.

**4. Second author review.** At assembly, only the first author had read this
document.

## Assembly notes

Generated from `research/draft-*.md`; editorial annotations (`[CHECK]`,
`[CUT?]`, source-confidence markers) were stripped. Body length at assembly:
about 5,300 words, before the venue's page limit is known. §4.5 is retained —
the abstract's count of five failure modes assumes it stays.
