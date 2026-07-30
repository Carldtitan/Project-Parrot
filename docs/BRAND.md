# Parrot brand

Parrot uses one literal bird mark across the desktop shell, tray, installer,
release assets, and future marketing. The source of truth is
`desktop/assets/brand/parrot-mark.svg`.

## Mark construction

The mark is drawn on a 64 × 64 unit grid and faces right, toward the text Parrot
returns to the active application.

- The dark head, chest, and long body form the vertical stroke of a hidden `P`.
- The pale face and coral beak complete the bowl without drawing a letter.
- Two tail feathers keep the silhouette recognizable below 24 px.
- The eye is the only circular detail. It must remain dark with a pale catchlight.
- The wing is the only chartreuse region. Coral is reserved for the beak and
  recording or destructive states in the product.

The geometry is flat SVG: no gradient, blur, outline, font, mask, embedded
bitmap, or generated-image dependency. Do not trace, redraw, or decorate it.

## Palette

| Role | Hex |
| --- | --- |
| Jungle | `#123F35` |
| Leaf | `#4F9A58` |
| Wing | `#C7EE57` |
| Wing shadow | `#78B844` |
| Macaw coral | `#FF7259` |
| Beak shadow | `#E85143` |
| Feather white | `#F4F6E9` |

## Reproduction

Render the installer and application icon from the canonical SVG:

```powershell
node scripts\render_brand_icon.cjs .build\icon.png 256
```

The renderer uses a fixed 10.5% inset and a 22.5% app-tile corner radius. It is
deterministic and is called automatically by `scripts/package_desktop.ps1`.
The committed 512 px `parrot-app-icon.png` is the tray source and can be
regenerated with the same script.

## Clear space and size

Keep clear space equal to the eye diameter around the standalone mark. Do not
render the full-color mark smaller than 16 px. At 16–20 px, pair it with the
pale app tile so the body and tail remain distinct.

## Wordmark

The wordmark is live text, never paths. Set `Parrot` in the product typeface at
740 weight with tight, restrained tracking. The bird sits to its left; do not
place the name inside or under the mark.
