# DiresQ paper — build bundle

Upload the whole folder to Overleaf (New Project -> Upload Project -> zip).

    arxiv.tex        preprint build (SocArXiv). Set this as the main document.
    workshop.tex     stub for a conference/workshop build; swap in the venue's
                     class file when the CfP publishes one
    content.tex      the paper body. Venue-neutral. Edit prose HERE only.
    references.bib   11 entries, 10 of them cited (see note 1)
    figures/         empty; see figures/README.md for the one figure worth adding

`content.tex` is included by both wrappers, so the text has one source of truth
and changing venue does not mean copying the paper.

## Read before submitting

This bundle is a **draft**. Four things are outstanding; another was fixed on
4 August 2026 and is recorded below so the change is visible.

**Verified to build.** pdfLaTeX + BibTeX + pdfLaTeX x2 completes with no errors,
no BibTeX warnings, and no undefined references. 11 pages.

## 1. Citations — DONE (4 Aug 2026)

The prose used to name sources in text without any `\cite{}`, so BibTeX produced
an empty References section. That is fixed. Both wrappers now load
`natbib` with `\bibliographystyle{plainnat}`, and the named mentions in
`content.tex` are `\citet{}` / `\citep{}` commands, so "Fritz and Mathewson
(1957)" is now generated from the .bib and cannot drift from it.

Ten entries are cited and appear in the References list:

    fritz1957      kendra2002     kendra2003*    starbird2011
    smith2018      fema_msv       liu2014        auferbauer2017
    kankanamge2019 zhou2022

`*` via `\nocite`, because the prose says it is listed for completeness.

**`baker2019` is in the .bib but is not cited anywhere**, so it does not appear
in the References. It was intended for Section 5 and the assembled text does not
use it. Cite it or delete the entry — an uncited entry is invisible, which means
nobody will notice it is wrong.

Two smaller fixes made at the same time:

- **The abstract was printing twice.** It was in both `arxiv.tex` and
  `content.tex`, which compiles without error. The abstract and keywords now
  live only in the wrappers, where they belong — venue classes disagree about
  where the abstract goes, which is the reason for the wrapper split.
- **`fema_msv` has `year = {n.d.}`.** The participant materials carry no
  publication date and a guessed year is worse than none. Pin it down before
  final submission. It cites as "FEMA's guidance ... (n.d.)".

If the venue supplies a class file, use theirs instead of `article` — and check
whether it already loads a citation package, since loading `natbib` twice will
error.

## 2. Author block (added 4 Aug 2026)

London's affiliation, email and ORCID are on the title page. Jesslyn is listed
as an author with no affiliation, by her choice.

The title block is built by hand rather than with `authblk`. `authblk` was tried
first and is wrong for this paper: given an author with no affiliation marker it
silently attaches them to the previous `\affil`, which put Jesslyn at Cal Poly.
If a venue class requires `authblk`, give every author an explicit marker.

**Section 6 says "two secondary-school students."** The title page now claims a
university affiliation. Those two statements cannot both be right, and
SocArXiv's red-flag list includes "enterprise misrepresentation (e.g., false or
misleading description of the research project)." Fix one of them:

- if the work was done in secondary school and London has since started at Cal
  Poly, say that — e.g. "this work was carried out while the authors were
  secondary-school students"; it is accurate and it is not a weakness
- if that sentence is simply out of date, rewrite it

The sentence is `content.tex`, in Section 6, last paragraph.

## 3. Kendra & Wachtendorf — cite 2002, not 2003

Every quotation attributed to them was read in **Preliminary Paper 316 (2002)**
(`kendra2002`), not the 2003 book chapter (`kendra2003`), which is paywalled and
unread. Both are in the .bib. **Quote `kendra2002`.** `kendra2003` is there so a
reader can find the published version, and its `note` field says so.

## 4. Three sources cited from abstracts only

`liu2014`, `auferbauer2017`, `kankanamge2019` — each cited only for a position
its abstract states outright, never for a finding. **A Cal Poly login very
likely clears all three**: Springer (Liu), the ACM Digital Library (Auferbauer)
and Elsevier/ScienceDirect (Kankanamge, Zhou) are standard university
subscriptions. Try the library proxy before anything else. `kankanamge2019` is a
systematic review in this exact area; if a competing system exists, that is
where it would be named.

`zhou2022` is Bronze open access — free to read at the DOI. The F1 and corpus
figures were removed from the text because they could not be verified; put them
back if you read it, they are more persuasive than the prose.

## 5. Statement on the use of generative AI

`content.tex` ends with two versions before the bibliography. **Use one, delete
the other.**

**Version A** is accurate for the text as it stands: the prose was drafted by a
model and appears substantially as generated.

**Version B** becomes accurate once you have rewritten the prose yourselves. It
describes literature search, retrieval and organisation — which is what
SocArXiv's AI Policy (8 March 2026) explicitly permits, provided it is disclosed
and the authors attest to verifying sources.

**Why this matters for SocArXiv specifically.** Their policy lists as
unacceptable: *"generating text which is used verbatim (including whole
paragraphs and sections)."* Version A describes exactly that. It is provided so
the statement is honest, not because it will pass moderation. The policy also
says *"failure to disclose, or implausible disclosures, are grounds for
rejection"* — so an understated version is worse than either.

The route to a paper SocArXiv will accept runs through rewriting the prose. The
research, argument, sources and design are already yours; the sentences are not.

**Also required by SocArXiv:** the submitting author needs a publicly viewable
**ORCID** linked from their OSF profile, with a name matching the paper. Free,
a few minutes, at orcid.org.

---

## Building

Set `arxiv.tex` as the main document in Overleaf's menu. Compile with pdfLaTeX.
Overleaf runs BibTeX automatically; from a terminal the sequence is
`pdflatex` -> `bibtex` -> `pdflatex` -> `pdflatex`.

Converted from `PAPER.md` via pandoc; section drafts in `research/` remain
authoritative.
