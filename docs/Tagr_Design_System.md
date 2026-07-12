# Tagr — Design System

A monochrome, editorial design language. Photo-first, quiet, confident. No color noise — contrast and typography do all the work.

---

## 1. Color

Pure grayscale. No brand color. Hierarchy comes from value (light/dark), not hue.

| Token | Hex | Use |
|---|---|---|
| `--black` | `#0A0A0A` | Primary background (dark surfaces), primary text on light |
| `--ink-90` | `#1C1C1C` | Card surfaces on dark backgrounds |
| `--ink-70` | `#3A3A3A` | Secondary dark surface |
| `--gray-50` | `#8A8A8A` | Muted text, captions, timestamps |
| `--gray-30` | `#C7C7C7` | Dividers, disabled states |
| `--gray-10` | `#EFEFEF` | Light surface / card background |
| `--white` | `#FFFFFF` | Primary text on dark, primary background (light mode) |
| `--overlay` | `rgba(0,0,0,0.45)` | Scrim over photos for text legibility |
| `--glass` | `rgba(255,255,255,0.06)` | Frosted glass fill (on dark) |
| `--glass-border` | `rgba(255,255,255,0.14)` | Glass panel edge |

**Photography**: all photo surfaces are rendered in grayscale/duotone (black → white), never in color. This keeps every image visually consistent regardless of what's actually in it, and keeps focus on the faces/people — which is the product's entire point — rather than on scenery color.

**Accent restraint**: there is no accent color. Emphasis is done with weight (bold vs regular), scale (large vs small), and fill (solid black pill vs outline). A single unread-state dot is the only "signal" mark in the system, rendered in pure white on dark / black on light — never colored.

---

## 2. Typography

Three typefaces, each with one clear job. No overlap in purpose.

| Role | Typeface | Weight(s) | Used for |
|---|---|---|---|
| **Display** | Fraunces (italic, opsz 9–144) | 700–900 | Wordmark, hero headlines, screen titles |
| **Structural caps** | Oswald | 500–600 | Section eyebrows, nav labels, condensed all-caps headers (e.g. "GALLERY", "REVIEW TAGS") |
| **Body / UI** | Inter | 400–700 | Body copy, buttons, list items, timestamps, form fields |

**Type scale:**
- Display hero (wordmark): 52px, italic, -0.02em tracking
- Screen title (Fraunces): 24px, 700
- Structural caps (Oswald): 12–19px, +0.02–0.1em tracking, uppercase
- Body: 13–13.5px, 400–600
- Caption / meta: 10.5–11.5px, `--gray-50`

**Rule:** Fraunces italic is reserved for moments that should feel editorial and considered (wordmark, headlines). Oswald caps are reserved for structural navigation labels — never for body copy. Never mix Fraunces and Oswald in the same text block.

---

## 3. Iconography

- Style: line icons only, 1.8px stroke, rounded caps/joins, no fills except for the single active/selected state
- Source language: consistent with Feather/Lucide-style geometry (simple, minimal, geometric)
- Size: 18px default (nav/buttons), 14px inline (compact contexts like heart-on-card)
- Color: always `currentColor` — white on dark surfaces, black on light surfaces, never colored
- No emoji, ever, anywhere in product UI

**Core icon set needed:**
`search` · `heart (outline + filled)` · `chevron-left` · `check` · `bell` · `more-horizontal` · `plus` · `user` · `users` · `camera` · `settings` · `compass`

---

## 4. Iconography of Faces (signature system element)

Face-tag pins on photos are the one recurring signature shape in the product:
- Circular, 30px, frosted glass fill (`--glass` + blur), 1.5px white border
- Single-letter initial centered, white text, 11px bold
- No color-coding by person — every pin looks identical in style; only the initial changes
- On tap/expand, becomes a full name chip: rounded pill, glass fill, small dot indicator + name

This consistency is deliberate: since the product's core trust question is "is this really me being tagged," the UI should never let tag styling itself feel arbitrary or flashy — it should feel neutral and systematic, like a caption, not a badge.

---

## 5. Surfaces & Elevation

Two elevation languages depending on context:

**Glass (dark mode, over photos):**
```
background: rgba(255,255,255,0.06–0.11)
backdrop-filter: blur(22–26px) saturate(150%)
border: 1px solid rgba(255,255,255,0.14)
```

**Flat (light mode, list contexts):**
```
background: var(--gray-10) or var(--white)
border: none
shadow: 0 2px 10px rgba(0,0,0,0.06)
```

Never mix glass-blur elevation with heavy drop shadows — pick one language per screen based on whether the background is a photo (glass) or a flat surface (shadow).

---

## 6. Shape Language

- Corner radius scale: 14px (small chips/buttons) · 18–20px (list items) · 24–26px (cards/photos) · 100px (pills, primary buttons, floating nav)
- Buttons are always full pill (100px radius) — this is the one shape rule with zero exceptions
- Cards/photos use large continuous radii (24–26px), never sharp corners
- Avatars and face-pins are always perfect circles

---

## 7. Component Notes

**Primary button**: solid fill (white on dark screens, black on light screens), full pill, bold label, no icon unless functionally necessary.

**Pill badge** (e.g. "3 tagged", "Just you"): glass fill on photos, 20px radius, 10.5px semibold label, always short (1–3 words).

**Bottom navigation**: floating pill, glass fill, overlaps content rather than docking flush to the screen edge — reinforces the "photo-first" feel where chrome recedes.

**Notification row**: flat glass row, square-ish thumbnail (16px radius, not circular — distinguishes "photo" thumbnails from "person" avatars, which are circular), single unread dot only when unread.

---

## 8. Voice Alongside the Visuals

Match the quiet visual tone in copy:
- Screen titles: short, structural, capitalized normally except nav labels (Oswald caps handles the "shouting" register visually, so copy itself stays calm: "Review tags," not "REVIEW YOUR TAGS NOW")
- Buttons: active verbs, plain language — "Capture my face," "Confirm tags," not "Submit" or "Proceed"
- Empty/error states: state what happened and what to do next, no exclamation points, no filler

---

## 9. What This System Deliberately Avoids

- Any brand accent color — monochrome only, forever, at every screen
- Gradients used decoratively (gradients are only used to simulate photographic tonal range, never as flat color-block backgrounds)
- Emoji as icons or UI elements
- Mixing display serif and structural caps typefaces in the same line
- Sharp/hard corners anywhere in the interface
- Drop shadows on frosted-glass surfaces (pick one elevation language per surface)
