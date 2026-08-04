# §1 and §6 — first draft

Status: **first draft, unreviewed.**

> **`[SOURCE NEEDED]` marks a factual claim about the world that I have not
> verified.** Every one must be sourced or cut before this is posted anywhere.
> The outline's rule stands: no number about Harvey that we have not read in a
> source. Baker & Deham (2019), *"For a short time, we were the best version of
> ourselves: Hurricane Harvey and the ideal of community"*, is the intended
> source and is unread.

---

## 1. Introduction

When a disaster is large enough, people go toward it. This is among the
oldest findings in disaster sociology: Fritz and Mathewson named the behaviour
*convergence* in 1957 and catalogued five kinds of person who arrive —
returnees, the anxious, helpers, the curious, and exploiters. Kendra and
Wachtendorf, studying the response to the World Trade Center attack, added a
sixth and reframed the central question. Access to what they call the *response
milieu* is not granted; it is negotiated. A volunteer's admission depends on
whether the people already inside can afford them.

The mechanism the field has developed for that negotiation is **credentialing**.
Volunteer reception centres, badge systems, affiliation with a recognised
organisation: these convert an unknown arrival into an accountable one. They
work. At the World Trade Center, identification requirements *"evolved and
intensified on almost a twice-daily basis"* as the response matured.

Credentialing presupposes a credentialer. Somebody must be present with the
authority to issue the badge, the roster to record it in, and the attention to
spare. In the first hours of a sudden-onset event — and in events where formal
response never fully arrives — none of those exist, and people are already
going in.

Kendra and Wachtendorf state the resulting tension directly, summarising Weick
and Perrow on decentralised coordination: effective decentralisation presupposes
prior socialisation into an organisation's norms, *"yet the volunteers who
appear to assist in the emergency response are, virtually by definition,
strangers to the response milieu."* The literature names the problem and, so far
as we have found, proposes no mechanism for the interval before command exists.

`[SOURCE NEEDED — the Harvey paragraph. Intended shape: private boat owners
self-deploying into flooded Houston neighbourhoods, organising through social
media, with no roster and nobody counting them out. Every specific in this
paragraph — how many, how organised, what went wrong — must come from Baker &
Deham (2019) or an equally citable source. Do not write it from memory or from
news recollection.]`

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

- The Harvey paragraph is the single blocking item in §1. Read Baker & Deham
  first, then write it, then check every specific against the paper.
- §1 currently quotes Kendra & Wachtendorf twice. One quotation is stronger than
  two; consider paraphrasing the credentialing one and keeping the Weick/Perrow
  sentence verbatim, since that one is doing structural work.
- §6's last paragraph is a judgement call. It is honest and it may read as either
  disarming or as an excuse. Ask a reader who is not us.
- "Secondary-school students" vs "high school students" — pick one and match the
  spelling convention of the venue.
