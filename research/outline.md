# Paper outline — preprint first, reviewed venue second

## Plan

**1. SocArXiv preprint.** Free, no endorsement system (unlike arXiv), no
institutional affiliation required — an OSF account and a working email is the
whole gate. Moderation is a five-point check that the work is scholarly and
correctly categorised; it is explicitly not peer review. Disciplinary fit is
good: this paper cites disaster sociology and crisis informatics, which is where
SocArXiv lives. Gives a citable, timestamped, permanent record with a DOI.

*Note: the **generalist** OSF Preprints server was suspended indefinitely in
October 2025. Community servers including SocArXiv are unaffected and open.
Submit to SocArXiv specifically, not to "OSF Preprints".*

**2. A reviewed venue afterwards.** A preprint is not peer review and does not
give us the thing we actually want. JORS states outright that preprinting is not
previous publication, and conference venues generally agree — so posting first
costs nothing. Candidates, in order: ISCRAM WiP (pending the attendance and
cost question), a CHI/CSCW/ICT4D workshop, JORS with an APC waiver requested in
the cover letter.

**Do not post to SocArXiv until §2 is written.** The entire point of the
literature review was to avoid claiming novelty that is not there. Posting
publicly with that claim unverified is the specific failure we have been working
to prevent, and a preprint is permanent.

## Status

| Section | State |
| --- | --- |
| 1. Introduction | drafted — **blocked** on the Harvey source |
| 2. Background and related work | **not started — blocked** on 3 unread papers |
| 3. Design | drafted; scheduler overstatement fixed |
| 4. What building it taught us | drafted |
| 5. Limitations | drafted |
| 6. Future work | drafted |
| Abstract | write last |

---

## Target venue notes — ISCRAM Work in Progress track

Target: **ISCRAM 2027, WiP track.** The 2026 deadlines were 9 Jan (CoRe) and
23 Feb (WiP/PiP); the 2027 call is not published yet, so assume
**January–February 2027** and confirm when it appears. Length and template are
set by the CfP — do not guess them, and do not start formatting until it is out.

WiP is the right track precisely because it does not require evaluation. Do not
submit to CoRe. We would be desk-rejected on the evaluation section and would
deserve it.

**This file is an outline, not a draft.** Sections marked `[NO EVIDENCE]` are
things we would currently have to make up. They stay empty or get cut.

---

## The claim, in the form it has to survive review

Not *"nobody tracks the people who go in."* That is false and a reviewer will
know it.

> Convergence of unaffiliated helpers is well theorised (Fritz & Mathewson 1957;
> Kendra & Wachtendorf 2003). The established mechanism for managing them is
> **credentialing by an authority**, which presupposes that an authority has
> arrived. In the interval before it does — and in events where it never
> meaningfully does — there is no accountability mechanism at all, and the
> literature proposes none. We report the design of a system that attempts
> accountability without a coordinator, using **silence rather than a
> supervisor** as the escalation trigger, and we report what that design costs.

Contribution type: **design and rationale**, plus the failure modes we found
building it. Not a validated result.

---

## Title candidates

1. *Accounting for the Unaffiliated: Silence-Triggered Escalation for Volunteers
   Who Self-Deploy*
2. *Nobody Is Coming to Check: Designing Volunteer Accountability Without a
   Coordinator*
3. *Legible Without a Gatekeeper: A Self-Service Accountability Tool for
   Converging Helpers*

(1) is the most ISCRAM-ish. (2) is better writing and risks sounding like a blog
post. Decide late.

---

## Abstract — skeleton, ~150 words

Problem (convergence is old, credentialing presupposes an authority) → gap (the
interval before command exists) → what we built (one sentence) → mechanism
(silence, not supervision) → what we are *not* claiming (no deployment, no
users) → what the paper offers (design rationale and enumerated limits).

Write this last.

---

## 1. Introduction

Open on the Weick/Perrow tension as Kendra & Wachtendorf state it — that
decentralisation presupposes prior socialisation, and that converging volunteers
are *"virtually by definition, strangers to the response milieu."* That is the
problem statement, already written by the field, and it earns us the right to
be in the conversation.

Then the interval argument: credentialing is the answer, credentialing needs a
credentialer, and the first hours have neither.

Motivating case: Hurricane Harvey, private boat owners self-deploying. **Verify
every factual claim about Harvey before it goes in.** Do not use a number we
have not sourced.

State plainly, in the introduction and not buried: no deployment, no users, no
evaluation.

## 2. Background and related work

- **Convergence.** Fritz & Mathewson (1957) — five personal converger types,
  external vs. internal convergence, personal/informational/materiel. Our users
  are *helpers*, converging externally then internally.
- **Legitimacy.** Kendra & Wachtendorf — access is negotiated, not granted. The
  key finding for us: the volunteers who got through were those who *"were able
  to work with minimal supervision."* The scarce resource is emergency-manager
  attention.
- **Digital volunteers.** Starbird & Palen (2011) — self-organising follows
  resource → activity → task → domain. Note explicitly that their population is
  remote by definition and therefore never needs accounting for. This is the
  hinge of our argument; say it in one clear sentence, not three.
- **Doctrine.** FEMA spontaneous-volunteer guidance, ASPR TRACIE, Volunteer
  Reception Centres. Practitioner sources belong here — citing doctrine
  alongside literature is what makes a systems paper credible to this audience.
- **Taxonomy.** Liu (2014), crisis crowdsourcing framework. `[UNREAD]` — read
  before writing this section and find out which box we are already in. If we
  fit a box cleanly, say so and argue the design is the contribution, not the
  idea.
- `[UNREAD]` Starbird dissertation (2012), convergence chapters.
- `[UNREAD]` Prior-art check on the two personnel-accountability patents.

## 3. Design

The system: Flask, SQLite, server-rendered, no account approval, no dispatcher.
33 routes, 6 tables. State the stack in two sentences and move on — the stack is
not the contribution.

**The mechanism.** A responder joining a report gives an ETA (bounded 5–240
minutes, warned above 120). Check-in interval defaults to 30 minutes. Silence
past the threshold marks them overdue; `SILENT_ESCALATE_MINUTES = 15` past that
files a report *about them*. No human decides this.

**The design decisions worth a paragraph each** — each of these is a real
trade-off we made and can defend:

1. **Silence as the trigger.** A coordinator noticing is the thing we cannot
   assume. Absence of a signal is available where presence of a supervisor is
   not.
2. **The switch has no scheduler.** It runs on read — whenever anyone loads the
   board. This is deliberate: a timer can die silently, and a check nobody runs
   is worse than no check. Cost: it depends on being watched. We made that cost
   *visible* on the board rather than documenting it in a file nobody reads
   (`SWEEP_EVERY_SECONDS = 30`; the board shows how long since the last sweep
   and turns amber past five minutes).
3. **Status and contact are different facts.** What someone last told us is not
   whether they are still answering. Conflating them lets a page show "on scene"
   for someone forty-five minutes silent. Both are displayed; neither is
   inferred from the other.
4. **Refusing to cache claims about other people.** The offline layer keeps your
   own commitments and refuses the report feed and the board. A cached feed is a
   list of who needed help twenty minutes ago, and acting on it sends someone to
   an address already cleared. A test fails if either is added to the service
   worker shell.
5. **Not storing triage answers.** They are health observations about a person
   who never consented and is probably not in a position to.

**Classifier**: multinomial naive Bayes, severity lexicon, LOOCV with a CI floor
asserted at 0.68. Keep this *short*. It is the least interesting part of the
system and the part most likely to attract a reviewer who wants it to be
something it isn't. One paragraph. Frame it as triage ordering, not prediction.

## 4. What building it taught us

This is the section that makes a WiP paper worth reading, and the one we can
actually fill. Candidates, all real:

- The offline layer taught the caching rule the hard way — the interesting
  finding is that *correct-when-written* and *correct-when-read* are different
  guarantees, and disaster data has a short half-life between them.
- The dead man's switch started as a scheduled job in design and became
  read-triggered because we could not honestly promise the scheduler would run.
- Making a limitation visible on screen is a different claim from documenting
  it. Argue this generally: emergency software should surface its own liveness.
- Contention: three pages that exist to be watched all wrote to the database on
  read, and broke under exactly the load they were built for.

## 5. Limitations

`docs/limits.md` — 18 named limitations, already written, already honest.
This is our strongest section and most papers' weakest. Lead with the two that
hurt most:

- **It has never been used in a real disaster.**
- **The dead man's switch depends on being run.**

Then no identity verification, self-reported location, overdue measures contact
not safety, one cautious responder can hold a report open, lockouts live in
memory.

Add the one Kendra & Wachtendorf forces us to confront: **the literature treats
converging volunteers as a risk to be managed; we treat them as people owed an
accounting.** That is a moral position, not a finding, and the paper has to own
it rather than assume the reader shares it.

## 6. Future work

Honest and small. Five structured interviews with volunteer-response
coordinators would move this from WiP toward CoRe. Say that as a plan, not an
aspiration.

---

## Before submission — checklist

- [ ] **Get Liu (2014) full text — paywalled, abstract read, framework tables unseen.**
      Email `sophialiu@usgs.gov` for a copy, or interlibrary loan. This is the
      last real novelty risk; §2 stays `[UNREAD]` until it is closed.
- [ ] Read Starbird dissertation convergence chapters
- [ ] Prior-art check on the two accountability patents
- [ ] Verify every Harvey factual claim against a source
- [ ] Confirm ISCRAM 2027 CfP: deadline, track, page limit, template
- [ ] Decide authorship order with Sky, in writing, before drafting
- [ ] Disclose AI assistance per venue policy — check whether ISCRAM has one;
      assume disclosure is required and write it either way
- [ ] Re-check every number in the paper against the repository at submission
      time. The doc tests catch numbers in our own files; they will not catch a
      stale number in a PDF.

## What would make this a CoRe paper instead

Real users, or expert interviews, or a deployment. Nothing else. No amount of
additional literature converts a design paper into an empirical one.
