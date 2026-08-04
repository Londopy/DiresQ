# §2 Background and related work — first draft

Status: **first draft, unreviewed.**

> **Citation honesty markers used below.**
> `[FULL]` — read in full.
> `[ABSTRACT]` — abstract only; cited **only** for a position the abstract
> states outright, never for a finding.
> `[SECONDARY]` — cited through another author's summary, not read directly.
>
> Every `[ABSTRACT]` and `[SECONDARY]` must either become `[FULL]` or have its
> sentence weakened before submission. They are listed at the foot of this file.

---

## 2. Background and related work

### 2.1 Convergence

People moving toward a disaster is one of the field's oldest documented
behaviours. Fritz and Mathewson (1957) named it *convergence* and separated
*external* convergence — movement toward the affected area from outside — from
*internal* convergence, movement toward particular points within it. They
further distinguished personal, informational, and materiel convergence, and
catalogued five kinds of personal converger: returnees, the anxious, helpers,
the curious, and exploiters. `[SECONDARY]`

Kendra and Wachtendorf (2003), studying the response to the World Trade Center
attack across more than 750 collective hours of field observation, added a sixth
— supporters or fans — and, more importantly for us, reframed the question.
Access to what they term the *response milieu* is not a status a volunteer
holds but one they negotiate. `[FULL]`

The taxonomy has passed into practice. FEMA's guidance on managing spontaneous
volunteers reproduces it directly, noting that *"researchers have identified six
different groups of people that tend to converge"*, and derives an operational
task from it: *"the helpers must be identified from among the larger population
of convergent individuals."* `[FULL]` Theory and doctrine here are a single
lineage rather than two literatures, which is why we cite them together.

DiresQ's users are helpers, converging externally and then internally.

### 2.2 Legitimacy, credentialing, and what both presuppose

Kendra and Wachtendorf's central finding concerns who gets in. At the World
Trade Center, identification requirements *"evolved and intensified on almost a
twice-daily basis"*, and volunteers became *"another group that needed to be
accounted for, and therefore potentially a distraction that outweighed their
utility."* The volunteers who succeeded in gaining access were those who
*"were able to work with minimal supervision by official emergency workers"* —
whose incorporation *"required little or no effort on the part of emergency
managers."* `[FULL]`

We take the scarce resource in that account to be emergency-manager attention,
and it is the frame we design against: a volunteer who accounts for themselves
spends none of it.

Doctrine's mechanisms for conferring legitimacy are the Volunteer Reception
Centre and, prior to any event, pre-affiliation — *"turn spontaneous unaffiliated
volunteers into affiliated ones before a disaster occurs."* `[FULL]` Both
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
is what lets a stranger begin. `[FULL]`

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
communication overload. `[FULL]`

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
articulation work of coordinating across them. `[ABSTRACT]` We note that two of
those four interfaces presuppose an organisation conducting the effort, and that
the trajectory the framework describes runs toward formalisation and integration
*"into official products and services."* Our position is upstream of that
trajectory rather than opposed to it.

Auferbauer and Tellioğlu (2017) describe *crowdtasking*, presented explicitly as
*"a centralized form of crowdsourcing for crisis and disaster management"*, with
a prototype and a first field trial. `[ABSTRACT]` It is the clearest statement
of the opposite design position to ours, and we cite it as such: where
crowdtasking assumes an organisation able to task a registered crowd, we assume
neither the organisation nor the registration.

Kankanamge et al. (2019) provide a systematic review of volunteer crowdsourcing
in disaster risk reduction. `[ABSTRACT]` We have not obtained the full text and
therefore make no claim about its findings; it is listed here because a reader
working in this area will expect to see it and should know we are aware of it.

Technical work on the classification side is considerably more advanced than
ours. Zhou et al. (2022) fine-tune BERT variants over 3,191 hand-labelled tweets
from Hurricane Harvey to identify rescue requests, reporting an F1 of 0.919 for
their best model. `[ABSTRACT]` Our own priority suggestion (§3.3) is a naive
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

---

## Citation debts to clear before submission

**`[SECONDARY]` — Fritz & Mathewson (1957).** Cited through Kendra &
Wachtendorf's summary and FEMA's. The five types and the external/internal and
personal/informational/materiel distinctions are consistent across both
secondary sources, which is reassuring but is not the same as having read the
original. It is a 1957 National Academy of Sciences / National Research Council
committee report; try the National Academies Press and HathiTrust. **Either read
it or attribute it explicitly as reported by Kendra & Wachtendorf.**

**`[ABSTRACT]` — Liu (2014).** Paywalled at Springer; abstract read, framework
tables unseen. Every sentence citing Liu above is a restatement of her abstract.
Acceptable as written; would not be acceptable if we described what the
framework's dimensions contain.

**`[ABSTRACT]` — Auferbauer & Tellioğlu (2017).** ACM DL; abstract read. We cite
only their self-description as centralised, which their abstract states in those
words. **Read before submission anyway** — their field trial is the evaluation
design §6 proposes, and we should not describe the nearest neighbouring system
from its abstract if we can avoid it.

**`[ABSTRACT]` — Kankanamge et al. (2019).** Cited as existing, with an explicit
statement that we make no claim about its findings. This is honest but weak; a
systematic review in our exact area that we have not read is the most likely
place for a reviewer to find something we missed.

**`[ABSTRACT]` — Zhou et al. (2022).** The F1 figure and corpus size are from
the abstract. Verify both against the paper before printing them.

## Notes for revision

- §2.3's last two paragraphs carry the paper's central argument. They should
  probably move to §1 and leave §2.3 purely descriptive — decide once §1 and §2
  are read end to end together.
- §2.5 currently reads as a list. If length allows, restructure around the axis
  that actually matters — whether the system assumes an organisation — rather
  than around who wrote what.
- Check whether ISCRAM's template wants related work as §2 or folded into §1.
