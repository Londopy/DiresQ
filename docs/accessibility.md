# Accessibility

The people most likely to need a tool like this are the people least likely to
have perfect vision, a steady hand, or a working mouse. So this got audited
rather than assumed.

Nine issues, three of them critical. All fixed, and all now held in place by
tests that run in CI — because an audit nobody can repeat is a claim, not a
result.

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

`TestAccessibility` — 48 cases, run in CI on every push:

| Test | Catches |
| --- | --- |
| Every page declares a language | Missing `lang` |
| Every page has a skip link and a `main` | Regressions on new pages |
| Every page loads the focus stylesheet | Someone dropping the include |
| No `<img>` without `alt` | Images added later |
| No input named only by a placeholder | Parses the markup, matches `<label for>` and `aria-label` against every `<input>` |
| Board is polite, not assertive | A future "make it announce faster" |
| Contrast of every pair used for real text | Computes the ratio from the hex and fails below 4.5:1 |

The contrast test is the one worth looking at — it doesn't check a list of
approved colours, it does the WCAG relative-luminance maths and asserts the
result. Change a colour to something unreadable and the suite fails.

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
