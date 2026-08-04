# §1 and §6 — first draft

Status: **first draft, unreviewed.**

> **Harvey material is now sourced.** Every figure and quotation in §1 comes from
> Smith, Robertson, Murthy, Stephens & Li (2018), *"Social Media in Citizen-Led
> Disaster Response: Rescuer Roles, Coordination Challenges, and Untapped
> Potential"*, Proceedings of the 15th ISCRAM Conference, pp. 639–648. Open
> access via NSF-PAR 10076203. Nothing here is written from memory.
>
> Baker & Deham (2019) was the intended source and turned out to be critical
> theory with no Harvey specifics to cite. It is still useful — see §5.

---

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

---

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

---

## Notes for revision

- Harvey paragraph **written from Smith et al. (2018)**, ISCRAM 15, NSF-PAR
  10076203. Every figure and quotation above is from that paper. Re-verify the
  30,000–40,000 homes figure against their wording before submission — they
  attribute it loosely and we should not sharpen it.
- **A complication we must not hide, for §5.** The volunteers in Smith et al.
  wanted *more* structure, not less. Harriett: *"people that are trained to do
  that need to be in charge of prioritizing calls and assigning."* That is an
  argument against a coordinator-free design, made by the population we claim to
  serve. It must appear in the limitations, stated as plainly as this, or a
  reviewer who has read Smith et al. will conclude we read it selectively.
- §1 currently quotes Kendra & Wachtendorf twice. One quotation is stronger than
  two; consider paraphrasing the credentialing one and keeping the Weick/Perrow
  sentence verbatim, since that one is doing structural work.
- §6's last paragraph is a judgement call. It is honest and it may read as either
  disarming or as an excuse. Ask a reader who is not us.
- "Secondary-school students" vs "high school students" — pick one and match the
  spelling convention of the venue.
