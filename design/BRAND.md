# switchdeck brand

The mark is called **the Deck**. Three cards fanned from a single corner, the front one solid: one of several, currently active. The name already carries the image, so the mark uses it.

Everything here inherits `design/tokens.json` and the account palette. switchdeck shares turquoise with uebersicht-claude-tokens by design; the symbol, not the colour, carries identity.

---

## Construction

The symbol is drawn on a **96 unit grid**. Card: 44 x 30, radius 6, base position x 26, y 46.

| Element | Geometry |
|---|---|
| Back cards | base card, stroke 6, filled with the ground colour, rotated -17 and -34 degrees about (26,80) |
| Front card | base card, solid accent fill |
| Optical centre | 48, 56 |

Back cards are filled with the ground so each occludes the one behind it; the fan reads as stacked cards, not crossing outlines.

**The one deliberate inconsistency.** Monochrome uses two cards, not three: the front card solid, one outlined card behind it at translate(9,-11) rotate(-8). Three overlapping outlines in a single colour collapse into noise below 24px; two survive. The menu bar template uses the two-card construction.

---

## Colour

Tokens only.

| Context | Ground | Back cards | Front card |
|---|---|---|---|
| Light | `bg` `#F7F5F2` | `text` stroke, `bg` fill | `accent` `#0F7D74` |
| Dark | `bg` `#1C1B1D` | `text` stroke, `bg` fill | `accent` `#2FD4C4` |
| Template (menu bar) | transparent | black, alpha only | black, alpha only |

---

## Clear space and minimum sizes

Clear space on all four sides equals the card radius times two (12 grid units).

| Asset | Minimum |
|---|---|
| Symbol, colour | 16 px |
| Symbol, monochrome (two-card) | 18 px |
| Horizontal lockup | 180 px wide |

---

## Files

```
design/
  logo/       symbol light, dark, mono black, mono white; tiles; wordmark; lockups
  app-icons/  macos/AppIcon.appiconset (10 PNGs)
  menubar/    SwitchdeckTemplate.svg, .pdf, and 18pt PNGs at 1x 2x 3x, pure alpha
  github/     readme banners 1400x400, social preview 1280x640, avatar 400x400
  web/        og 1200x630, favicon set, apple touch icon, PWA icons
```

Filenames carry pixel dimensions for raster deliverables.

---

## Do not

1. Do not stretch, rotate, or shear the mark.
2. Do not recolour outside the tokens above.
3. Do not add shadows, gradients, glows, or strokes.
4. Do not add a fourth card or badge a count on the fan.
5. Do not outline the front card; solid is what reads as active.
6. Do not rebuild the wordmark in live type; it is outlined geometry.

---

## Rebuilding the assets

Every file is generated from the same 96 unit geometry. If the mark changes, regenerate rather than hand-editing individual sizes.

*Mark designed 2026-07-28. Built by Claude (Anthropic), directed by Shashank Karpal.*
