# Disclaimer

DiresQ was built in three days by two students at Katy Youth Hacks 2026, and
also submitted to STEMist Hacks IV. It has never been used in a real disaster,
and it is not a product.

Read this before doing anything with it that matters.

---

## It is not an emergency service

**DiresQ does not contact 911, emergency services, or any agency.** Nothing in
this app dispatches anybody.

Filing a report puts a card on a screen that other volunteers may or may not
be looking at. If somebody is in danger, **call 911 first.** Use this
afterwards, if at all.

This is the failure with real consequences: a person in trouble files a report
and believes help is now coming. It isn't. Everything else on this page is
smaller than that.

## The triage helper is not medical advice

DiresQ includes a helper that runs **START** (Simple Triage And Rapid
Treatment), a real protocol used at real mass-casualty incidents. It asks four
questions and returns a category.

What that category means: *who should be reached first.* It orders attention.

What it does not mean:

- It does not tell you what to do when you get there.
- It does not diagnose anything.
- It does not replace a paramedic, a nurse, or a doctor.
- It is not a substitute for training. START is taught in a classroom for a
  reason.

The categories include **Deceased**, and the software will return it. A piece
of software built by teenagers over a weekend is not a competent judge of
whether a person has died. Treat that output as a prompt to get a qualified
person there, never as a conclusion.

**Nothing you type into the triage helper is stored.** The answers go to the
server, produce a category, and are discarded — they are never written to the
database and never associated with your account or with anyone else's. That is
deliberate: they concern somebody who is in no position to consent to being
recorded. There is a test that fails if a future change starts storing them.

## Nobody is verified

Anyone can create an account and mark themselves a responder. There are no ID
checks, no organisational affiliation, no vetting of any kind.

A name on the board means somebody typed that name. It does not mean they are
trained, insured, equipped, or who they say they are.

Doing this properly needs real identity verification, and there is no honest
weekend version of it — so we did not build a fake one. An email confirmation
would be worse than nothing, because it looks like verification without being
it.

## Locations are self-reported

Coordinates come from whatever the browser hands over, or from a tap on a map.
Somebody can sit at home and check in claiming to be on scene.

We detect inconsistency, not intent: marking yourself on scene when your last
check-in was over 500 m from the report raises a flag. Someone determined can
still lie, and no amount of client-side code changes that.

Do not use a pin on this map as proof that anybody is anywhere.

## The overdue timer measures contact, not safety

A red row means nobody has heard from that person recently. That is all it
means.

Someone can check in while trapped. Someone can go silent because their phone
died in their pocket. The timer tells you when to *start asking*, and that is
the entire claim.

## Reports name real places

If this were deployed, reports would contain the addresses of people who are
having the worst day of their lives, alongside the fact that they are alone,
or unwell, or unable to leave. That is sensitive information about vulnerable
people.

The app tells search engines to index nothing, and nothing is deliberately
published. That is not the same as being secure, and it should not be treated
as such.

## If you deploy this

Don't, without reading this list first — none of it is done:

- No identity verification for responders
- No privacy notice, and no lawful basis identified for processing location
  data about identifiable people
- No age gate on sign-up
- No data retention policy; nothing is ever deleted
- `/api/uplink` accepts signed radio packets but cannot detect a replayed one
- Session lockouts are held in memory and reset when the process restarts
- Built and tested by three people, none of whom are professionals

Anyone deploying this for real should talk to a lawyer and to an actual
emergency management professional first, and should assume the list above is
incomplete.

## Warranty

The software is provided under the Apache Licence 2.0, without warranty of any
kind and without condition. See [LICENSE](../LICENSE) and [NOTICE](../NOTICE).

Sections 7 and 8 of that licence are the relevant ones: no warranty, and no
liability for damages of any kind arising from use of the work.

The authors are not liable for any outcome arising from anyone's use of it. We
mean that in the ordinary sense as well as the legal one: this is student work
about a serious subject, and we would rather say so plainly than have somebody
find out the hard way.

---

*Not legal advice. Written by the people who built it, not by a lawyer.*
