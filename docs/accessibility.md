# Accessibility

The people most likely to need a tool like this are the people least likely to
have perfect vision, a steady hand, or a working mouse. So this got audited
rather than assumed.

Nine issues, three of them critical. Then four more when reports learned to
work offline and the form grew a status message somebody cannot afford to
miss. Then six more on the last day, when the audit finally read the
stylesheets instead of the palette and the report form instead of the pages
that already had tests.

Nineteen in total, six of them critical, all fixed, and all now held in place
by tests that run in CI — because an audit nobody can repeat is a claim, not a
result. The last six are the interesting ones: every one of them sat under a
passing test whose job was to catch exactly that.

---

## What was wrong

### Six stylesheets had no focus style at all

`board.css`, `actions.css`, `triage.css`, `nav.css`, `homepage.css` and
`map.css` defined no `:focus` anything. Tabbing through the accountability
board — the main screen of the app — gave **no indication of where you were**.

Fixed with one `:focus-visible` rule applied globally:

```css
a:focus-visible, button:focus-visible, input:focus-visible {
    outline: 3px solid #89b4fa;
    outline-offset: 2px;
}
```

`:focus-visible` rather than `:focus`, so keyboard users get the ring and
mouse users don't get one around every button they happen to click. There's a
`forced-colors` fallback for Windows High Contrast Mode, which throws our
palette away entirely.

*WCAG 2.4.7 Focus Visible — Level AA*

### Placeholders were doing the job of labels

Login, sign-up and both search boxes had a `placeholder` and no `<label>`.

Placeholders disappear the moment you type. A screen reader may not announce
them at all, and anyone returning to a half-filled form has nothing left to
tell them which box is which. Every input now has a real label, visually
hidden where the design didn't have room for one:

```html
<label class="visually-hidden" for="login-username">Username</label>
<input id="login-username" type="text" name="username" ...>
```

Hidden with the clip-path technique, not `display: none` — the latter removes
it from the accessibility tree, which defeats the point.

*WCAG 3.3.2 Labels or Instructions — Level AA*

### Two colours were unreadable

| Element | Foreground | Background | Ratio | Needed |
| --- | --- | --- | --- | --- |
| Capability tags | `#45475a` | `#313244` | **1.8:1** | 4.5:1 |
| Footer / legal text | `#6c7086` | `#1e1e2e` | **3.4:1** | 4.5:1 |

The first was effectively invisible. Both moved to `#a6adc8`, which reaches
5.65:1 and still reads as secondary text.

The rest of the palette did well — Catppuccin Mocha is a well-built theme.
Body text is 11.3:1, the red overdue state is 7.1:1, links are 7.8:1.

*WCAG 1.4.3 Contrast (Minimum) — Level AA*

### The board repainted silently every three seconds

The board replaces its whole list on each poll. To a screen reader that was
either nothing at all, or — with the wrong setting — an interruption every
three seconds forever.

It's now a labelled region with `aria-live="polite"`, so someone going overdue
is announced at the next natural pause rather than cutting across whatever is
being read.

Deliberately **not** `assertive`. Assertive interrupts immediately, and
something that interrupts every three seconds is something people switch off.

*WCAG 4.1.3 Status Messages — Level AA*

### No way to skip the navigation

Nine of ten pages had no `main` landmark, and none had a skip link. Every page
meant tabbing through the whole header first.

Both added everywhere. The skip link is the first thing in the tab order and
invisible until it has focus.

*WCAG 2.4.1 Bypass Blocks — Level A*

### Smaller things

- Touch targets under 44×44 on the nav and action buttons — these get tapped
  one-handed, in the rain, by someone who is not calm *(2.5.5)*

  Fixed at the time, and then almost undone twice. The rule sat in `a11y.css`
  with no test behind it, so anybody restyling could have deleted it silently.
  There is now one that reads the rule and fails if a named control drops out
  of it — plus a second that walks every `<button>` in every template and
  fails on any that is neither a submit, nor named in the shared rule, nor
  given 44px in its own stylesheet. That second test found `.location-btn`
  sitting at about 43px: "Use My Location", which is pressed outdoors, on a
  phone, by someone standing in the thing they are reporting.
- No `prefers-reduced-motion` handling *(2.3.3)*

### Found later, when reports learned to work offline

Filing a report with no signal added three live regions and a status message
somebody genuinely cannot afford to miss. A second audit over just that
surface found four things. Contrast passed everywhere — all nineteen new
foreground/background pairs clear 4.5:1, and every coloured border that
carries meaning clears 3:1 — but the announcing did not.

- **The status region was written to while it was still `hidden`** *(4.1.3)*.
  A live region that is hidden when its content changes is not reliably
  announced, so the one message that says *"saved on this phone, nobody has
  seen this"* could have arrived silently for the person least able to check
  the screen for themselves. It is unhidden first now, and a test reads the
  order of the two statements, because that bug is invisible at runtime.
- **Two live regions announced the same fact** *(4.1.3)*. The waiting-count
  pill and the status line both fired on submit, so a screen reader read the
  count and talked over the sentence that mattered. The pill is `aria-hidden`
  on this page: it is the visual copy of something already said aloud.
- **The suggestion panel repeated itself** *(4.1.3)*. It re-renders on every
  pause in typing, and rewriting identical markup into a live region reads the
  whole suggestion out again. Offline that now includes a paragraph explaining
  the duplicate check has not run — a paragraph read at somebody every few
  seconds while they are describing an emergency. It only writes when the
  answer has actually changed.
- **"Open it" was an inline-sized target** *(2.5.5)*. It is an action rather
  than a word in a sentence, so it does not get the inline exemption. 44px.

None of the four would have been caught by the contrast test or by looking at
the page. Colour was the easy part and it was already right.

### Found in the final audit, the day of submission

A third pass, reading the stylesheets rather than the palette and the report
form rather than the pages that already had tests. Six issues — three of text
nobody could read, three of controls with no name — and three of the six are
critical.

| Element | Foreground | Background | Ratio | Needed |
| --- | --- | --- | --- | --- |
| `.hint` on a report card | `#45475a` | `#313244` | **1.38:1** | 4.5:1 |
| `.hint` on the triage card | `#45475a` | `#181825` | **1.92:1** | 4.5:1 |
| `.match-block .hint` | `#6c7086` | `#313244` | **3.0:1** | 4.5:1 |

`.hint` is the small print under a field that explains how the field works —
*"Try 30 min, 2 hours, or leave it"*, and on the triage page *"A normal adult
is around 12–20"*, which is the reference the question cannot be answered
without. It was the text a first-time user needs most and it was the text
nobody could read. Nine instances across two pages.

The third row is the interesting one: `.match-block .hint` is more specific
than `.hint`, so fixing the base rule left it behind. A contrast fix can be
undone by specificity without anybody touching the colour.

*WCAG 1.4.3 Contrast (Minimum) — Level AA*

Then the labels. The earlier audit fixed login, sign-up and the search boxes,
and the test written to keep them fixed listed those four pages — so the
report form, the form this entire application exists to submit, was never
checked. It had four problems:

- **Subject, Priority and Description had `<label>` with no `for`**, not
  wrapping their control either. A screen reader announces an unnamed text
  box; the placeholder is the only clue, and it disappears on the first
  keystroke. This is the same finding as the first audit, on the page that
  matters most, eight weeks later. *(1.3.1, 3.3.2, 4.1.2)*
- **`<label>Location</label>` pointed at nothing at all.** It titles the
  picker — a button, a map and a readout — which is a group, not a field. A
  label with no control tells a screen reader a field is coming and then does
  not deliver one. It is a `<p class="field-label">` now. *(1.3.1)*
- **The breaths-per-minute input had no accessible name.** Its `<legend>`
  names the group, not the control. *(4.1.2)*
- **`<select>` and `<textarea>` were never checked by anything.** The label
  test only ever looked at `<input>`.

The lesson both halves share: the tests were written around the bug that was
found, not the rule that was broken. A test that lists pages will not cover
the page added next week, and a test that lists colours will not see the one
you are about to use.

## What was already right

Worth recording, because it was mostly by accident of building the boring way:

- Every page declared `lang="en"`
- Every `<img>` had alt text
- Flash messages already carried `role="alert"`
- Semantic HTML throughout — real `<button>`s in real `<form>`s, headings in
  order, no click handlers on `<div>`s
- **The entire app works with JavaScript disabled.** Every action is a plain
  form post. That is one of the largest accessibility properties a web app can
  have and we got it by refusing to build a single-page app.

## How it's enforced

`TestAccessibility`, plus the live-region checks in
`TestFilingOfflineIsHonestAboutIt` — run in CI on every push:

| Test | Catches |
| --- | --- |
| Every page declares a language | Missing `lang` |
| Every page has a skip link and a `main` | Regressions on new pages |
| Every page loads the focus stylesheet | Someone dropping the include |
| No `<img>` without `alt` | Images added later |
| No control named only by a placeholder | Parses the markup, matches `<label for>` and `aria-label` against every `<input>`, `<select>` and `<textarea>`, on six pages including the report form |
| No `<label for>` points at a control that isn't there | A label with no field is styled text that promises one |
| Board is polite, not assertive | A future "make it announce faster" |
| Contrast of the palette pairs | Computes the ratio from the hex and fails below 4.5:1 |
| No stylesheet sets text to an unreadable grey | Reads all fourteen stylesheets — the palette test could not see these |
| The status region is unhidden before it is written | A live region announcing nothing |
| Only one thing announces a queued report | Two regions talking over each other |
| The suggestion panel does not rewrite identical markup | A paragraph repeated at somebody every few seconds |

The contrast test does the WCAG relative-luminance maths rather than checking
names against an approved list, which is the right idea. For most of this
project it was also **checking the wrong thing**: the pairs were written out
by hand in the test, so it verified the palette and never once read a
stylesheet. Any class using a colour that wasn't on the list was invisible to
it, which is exactly how `.hint` sat at 1.38:1 for weeks under a test whose
whole job was contrast, passing.

There are two tests now. The original still checks the palette. A second one
reads every stylesheet, finds the greys that are unreadable on anything we put
behind them, and fails unless `a11y.css` demonstrably lifts that selector —
so a fix cannot be quietly undone by a more specific rule, which is the other
way this went wrong.

## What has not been done

**Nobody has used this with a screen reader.** Automated checks catch roughly
a third of real accessibility problems, and it's the easy third. Everything
above is markup and colour; none of it is the experience of actually
navigating the app with VoiceOver or NVDA.

**The map has no non-visual equivalent.** It's a Leaflet canvas. The board
carries the same information as text and the feed lists every report, so the
data is reachable another way — but nobody has confirmed that is *enough*,
and "there's another page with the same data" is a weaker answer than it
sounds.

**No testing with real assistive technology, at any level.** No switch access,
no voice control, no magnification beyond browser zoom.

**Zoom past 200% is unverified.** The layout is responsive and should reflow,
but it hasn't been checked at 400%, which is what 1.4.10 actually asks for.

If somebody with a genuine need for any of this wanted to tell us what we got
wrong, we'd rather know.
