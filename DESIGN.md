---
name: Parrot
description: A local Windows dictation tool expressed as a quiet bird perched at the edge of work.
colors:
  ink: "#29483f"
  ink-strong: "#143a31"
  muted: "#596f67"
  muted-strong: "#4d685f"
  canvas: "#edf3ee"
  surface: "#fbfcf8"
  surface-subtle: "#e5ede6"
  surface-hover: "#dce8de"
  line: "#d4ded5"
  line-strong: "#bdccbf"
  sidebar: "#103a31"
  sidebar-muted: "#a9c1b5"
  sidebar-active: "#f4f7ed"
  accent: "#c7ee57"
  accent-hover: "#b8df45"
  accent-soft: "#eaf7c8"
  accent-ink: "#24451f"
  success: "#36875b"
  warning: "#bd782f"
  danger: "#ce4437"
  danger-hover: "#b83a30"
  danger-soft: "#fcebe7"
  brand-jungle: "#123f35"
  brand-leaf: "#4f9a58"
  brand-tail-bright: "#91cf4e"
  brand-wing-shadow: "#78b844"
  brand-coral: "#ff7259"
  brand-coral-shadow: "#e85143"
  brand-feather: "#f4f6e9"
typography:
  display:
    fontFamily: "Onest, Arial, sans-serif"
    fontSize: "34px"
    fontWeight: 720
    lineHeight: 1.08
    letterSpacing: "-0.03em"
  transcript:
    fontFamily: "Onest, Arial, sans-serif"
    fontSize: "25px"
    fontWeight: 480
    lineHeight: 1.48
    letterSpacing: "-0.018em"
  title:
    fontFamily: "Onest, Arial, sans-serif"
    fontSize: "17px"
    fontWeight: 690
    letterSpacing: "-0.025em"
  body:
    fontFamily: "Onest, Arial, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.5
  navigation:
    fontFamily: "Onest, Arial, sans-serif"
    fontSize: "14px"
    fontWeight: 570
  button:
    fontFamily: "Onest, Arial, sans-serif"
    fontSize: "13px"
    fontWeight: 680
  label:
    fontFamily: "Onest, Arial, sans-serif"
    fontSize: "12px"
    fontWeight: 650
  metadata:
    fontFamily: "Onest, Arial, sans-serif"
    fontSize: "11px"
    fontWeight: 640
  input:
    fontFamily: "Onest, Arial, sans-serif"
    fontSize: "15px"
    fontWeight: 400
rounded:
  compact: "7px"
  control: "8px"
  medium: "9px"
  brand-tile: "10px"
  feather: "13px 13px 13px 5px"
  overlay: "15px"
  stage: "18px"
  full: "99px"
spacing:
  micro: "4px"
  tight: "8px"
  control: "12px"
  block: "16px"
  region: "24px"
  section: "38px"
components:
  button-primary:
    backgroundColor: "{colors.accent}"
    textColor: "{colors.ink-strong}"
    typography: "{typography.button}"
    rounded: "{rounded.control}"
    padding: "0 16px"
    height: "38px"
  button-primary-hover:
    backgroundColor: "{colors.accent-hover}"
    textColor: "{colors.ink-strong}"
  button-secondary:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    typography: "{typography.button}"
    rounded: "{rounded.control}"
    padding: "0 14px"
    height: "38px"
  button-record:
    backgroundColor: "{colors.accent}"
    textColor: "{colors.ink-strong}"
    typography: "{typography.button}"
    rounded: "{rounded.feather}"
    padding: "0 15px"
    height: "50px"
    width: "118px"
  input:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    typography: "{typography.input}"
    rounded: "{rounded.control}"
    padding: "0 11px"
    height: "42px"
  navigation-item:
    backgroundColor: "transparent"
    textColor: "{colors.sidebar-muted}"
    typography: "{typography.navigation}"
    rounded: "{rounded.medium}"
    padding: "0 11px"
    height: "43px"
  caption-stage:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.stage}"
  dictation-perch:
    backgroundColor: "{colors.sidebar}"
    textColor: "{colors.sidebar-active}"
    rounded: "{rounded.stage}"
    padding: "16px 18px"
    height: "88px"
  overlay:
    backgroundColor: "{colors.sidebar}"
    textColor: "{colors.sidebar-active}"
    rounded: "{rounded.overlay}"
    padding: "0 13px 0 8px"
    height: "58px"
---

# Design System: Parrot

## Overview

**Creative North Star: "The Perched Caption"**

Parrot is the quiet bird at the edge of work: present, recognizable, and ready to catch speech without asking the user to enter a separate AI world. A literal geometric parrot anchors the forest rail, pale mineral surfaces hold the live text, and a dark-green perch carries every dictation control.

The system is calm and editorial rather than dashboard-like. Live words own the largest working type; recent takes remain visible at the right edge; thin rules organize secondary views. The bird appears as the canonical mark, as a faint watermark on the caption field, and as the signal inside the floating overlay without becoming decorative clutter.

**Key Characteristics:**

- Literal right-facing geometric parrot with a hidden P silhouette.
- Jungle-green rail and control perch against pale mineral fields.
- Leaf and wing chartreuse reserved for commands, focus, and readiness.
- Coral beak color echoed only in recording and destructive states.
- Onest typography, ruled secondary views, and clipped feather-like control corners.

## Colors

The product palette grows directly from the bird: jungle and leaf greens, a chartreuse wing, coral beak accents, and feather-white mineral surfaces.

### Primary

- **Wing Chartreuse:** The bird wing, primary commands, active rail tick, focus channel, and local-ready indicator.
- **Pressed Wing:** Hover state for primary commands.
- **Wing Wash:** Low-emphasis text-action feedback.
- **Forest Ink:** Accessible copy paired with chartreuse and low-emphasis actions on pale fields.

### Secondary

- **Ready Leaf:** Ready engine status.
- **Working Ochre:** Starting, processing, formatting, setup, and preview state.
- **Recording Coral:** Recording, cancellation, destructive actions, and errors.
- **Deep Recording Coral:** Hover state for destructive actions.
- **Coral Mist:** Low-emphasis destructive feedback.

### Tertiary

- **Mark Jungle:** Head, chest, body, eye, and hidden P in the canonical bird.
- **Mark Leaf:** Long tail feather.
- **Bright Tail:** Forward tail feather.
- **Wing Shadow:** Secondary wing plane.
- **Macaw Coral:** Beak highlight.
- **Beak Shadow:** Lower beak plane.
- **Feather White:** Face, catchlight, and canonical icon tile relationship.

### Neutral

- **Canopy Ink:** Default body and control copy.
- **Deep Canopy:** Highest-emphasis text.
- **Moss Note:** Descriptions, timestamps, and metadata.
- **Moss Label:** Durable labels and quiet controls.
- **Mineral Field:** Main application canvas.
- **Feather Surface:** Live stage and form fields.
- **Pale Leaf Surface:** Subtle neutral regions.
- **Leaf Hover:** Neutral row-action feedback.
- **Stem Rule:** Default section and row dividers.
- **Strong Stem:** Form and control borders.
- **Forest Rail:** Persistent navigation and dictation perch.
- **Rail Sage:** Inactive navigation and dark-surface secondary copy.
- **Rail Feather:** Active navigation and high-emphasis dark-surface copy.

### Named Rules

**The Plumage Has Jobs Rule.** Chartreuse marks commands and readiness, coral marks recording or destructive state, and neither becomes an ornamental field color.

**The Bird Is the Brand Rule.** Use the canonical full-color SVG; never trace, recolor, outline, animate, or redraw its geometry.

## Typography

**Display Font:** Onest (with Arial and sans-serif fallbacks)

**Body Font:** Onest (with Arial and sans-serif fallbacks)

**Label/Mono Font:** Cascadia Mono (with Consolas and monospace fallbacks, diagnostics only)

**Character:** The bundled Onest variable family is round enough to feel approachable and controlled enough for a native productivity tool. Tight display tracking gives headings confidence, while the lighter caption weight lets speech remain open and readable. Monospace is limited to diagnostics.

### Hierarchy

- **Display** (720, 34px, 1.08): One view title.
- **Transcript** (480, 25px, 1.48): Live or last-completed dictated text.
- **Title** (690, 17px, tight tracking): Caption, memory, settings, and subsection headings.
- **Body** (400, 14px, 1.5): Supporting copy and history content up to 64 characters wide.
- **Navigation** (570, 14px): Persistent rail destinations.
- **Button** (680, 13px): Primary, secondary, text, and perch actions.
- **Label** (650, 12px): Field names, statuses, and settings descriptions.
- **Metadata** (640, 11px): Timestamps, preview notes, and compact supporting information.

### Named Rules

**The Caption Owns Scale Rule.** Live transcript text is the largest working content; settings and metadata never compete with it.

**The Live Wordmark Rule.** Set “Parrot” as live Onest text at weight 740 beside the mark; never convert it to paths or place it inside the bird tile.

## Layout

The desktop shell uses a 184px labeled forest rail and a fluid workspace above a 48px draggable status bar. Main views are centered within an 1180px maximum with 38px side padding. Home fills the available height: the live caption expands first, session memory occupies a 258px right column, and an 88px dark-green perch locks to the bottom.

History remains a full-width ruled list; Personalize uses two equal columns with a 38px gap; Settings uses a 210px explanatory column beside fluid fields. The recurrent rhythm is 8–16px inside controls, 24px between related regions, and 38px at major columns and sections.

At 980px and below, the rail contracts to 74px and exposes destination names through keyboard-accessible tooltips; memory narrows to 230px. At 780px and below, view padding becomes 24px, memory narrows to 200px and shows only the newest take, transport labels compact, and multi-column forms stack.

**The Center Voice, Right Memory Rule.** Live speech receives the flexible center while recoverable session memory holds the narrower right edge.

**The One Perch Rule.** Hands-free, push-to-talk guidance, timer, recovery, and cancellation belong to one dark-green bottom band.

## Elevation & Depth

Parrot is mostly flat and rule-led. Tonal greens separate the rail, caption surface, memory strip, and perch. Shadows are limited to the composed live instrument, its primary command, keyboard focus, collapsed-rail tooltips, and the floating overlay.

### Shadow Vocabulary

- **Focus halo** (`0 0 0 3px rgba(103, 148, 64, 0.3)`): Keyboard focus and active fields.
- **Caption float** (`0 18px 48px rgba(20, 58, 49, 0.08)`): Light lift beneath the caption stage.
- **Perch float** (`0 18px 48px rgba(16, 58, 49, 0.16)`): Grounding beneath the dark-green control band.
- **Primary feather** (`0 8px 20px rgba(86, 119, 33, 0.22)`): Chartreuse hands-free action at rest.
- **Floating bird** (`0 16px 38px rgba(7, 35, 28, 0.34)`): Non-focus-stealing overlay above other applications.

### Named Rules

**The Instrument, Not Cards Rule.** Elevate the caption and perch as one instrument; persistent rows, settings, and history remain flat.

## Shapes

The signature live instrument uses an 18px composite radius: the pale stage owns the top corners and the forest perch owns the bottom corners. Standard controls use 7–10px rounding. The hands-free action is clipped like a feather, with 13px corners and a 5px lower-left cut; the overlay uses 15px corners and an 11px bird tile. Circles are reserved for state dots, the bird eye, and switch thumbs.

The canonical bird is flat geometric SVG on a 64-unit grid. Its right-facing dark body hides a P, the pale face and coral beak complete the bowl, and two long tail feathers protect recognition. Standard icon tiles use a 10.5% inset and 22.5% corner radius; 16–20px tray use requires the optical crop.

**The Perched Silhouette Rule.** The caption and control perch read as one object; never split them into independent cards.

**The Feather Cut Rule.** Asymmetric clipping belongs to the primary dictation action, not every control.

## Components

### Buttons

- **Shape:** Standard actions use 8px corners and a 38px minimum height; the signature hands-free command is 50px tall with a 13/5px feather cut.
- **Primary:** Wing Chartreuse with Deep Canopy copy and 16px horizontal padding.
- **Hover / Focus:** Primary actions shift to Pressed Wing; all controls use the green focus halo, and pressed standard actions move down one pixel.
- **Secondary / Text / Destructive:** Secondary actions remain transparent with a Strong Stem border; text actions use Forest Ink and Wing Wash; destructive actions use coral.

### Chips

- **Style:** Learned terms use Feather Surface, a Stem Rule border, compact 7px corners, and a muted repetition count.
- **State:** Chips report learned local vocabulary; they are not promotional badges or navigation.

### Cards / Containers

- **Corner Style:** Only the composed caption instrument uses the 18px container radius.
- **Background:** The live field uses Feather Surface, memory uses a pale leaf field, and the perch uses Forest Rail.
- **Shadow Strategy:** Caption and perch use paired shadows as one silhouette.
- **Border:** Stem Rule defines the memory seam and row structure.
- **Internal Padding:** Live text uses 27–30px; memory uses 16–27px; perch uses 16px by 18px.

### Inputs / Fields

- **Style:** Feather Surface fill, Strong Stem border, 8px corners, and 42px height.
- **Focus:** Border shifts toward leaf green and receives the focus halo.
- **Error / Disabled:** Disabled actions reduce opacity; destructive feedback uses coral rather than chartreuse.

### Navigation

The Forest Rail uses 43px rows with 9px corners, Rail Sage copy at rest, Rail Feather on hover and active states, and a 3px chartreuse edge tick for the current destination. The literal bird sits in a pale 34px tile above the live Onest wordmark. Below 980px, icons remain and tooltips reveal labels on hover or focus.

### Parrot Mark

Use the canonical SVG as the sole bird source for shell, overlay, tray, installer, and release assets. Keep clear space equal to the eye diameter. Do not render the standard full-color mark below 24px; use the optical tray crop at 16–20px.

### Caption Stage

The live field is the flexible center and carries the largest working type. A very low-opacity canonical bird watermark perches at its lower-right edge. During recording, a 4px inset coral rule appears while text also announces the state.

### Dictation Perch

The forest bottom band keeps the chartreuse hands-free action, push-to-talk shortcut, timer, recovery, and cancellation in one scan line. Compact widths shorten labels and preserve the mutually relevant action.

### Toggle Rows

Settings toggles pair a 13px title and 12px description with a 40×23px fully rounded track. Checked state uses leaf green; keyboard focus uses the standard halo.

### Recording Overlay

The overlay is a 58px Forest Rail strip with 15px corners and an 11px bird tile. The canonical mark itself is the signal: recording wraps it with a coral ring while readable state and mode text remain present.

## Do's and Don'ts

### Do:

- **Do** use the canonical literal bird consistently across shell, overlay, tray, installer, and release assets.
- **Do** give live speech the flexible center and largest working type.
- **Do** keep chartreuse concentrated on commands, focus, active rail tick, and local readiness.
- **Do** use coral only for the beak, recording, destructive actions, and errors.
- **Do** organize secondary views with mineral fields, shared edges, and thin stem rules.
- **Do** preserve visible keyboard focus, text state labels, reduced-motion behavior, and the optical tray crop.

### Don't:

- **Don't** trace, recolor, animate, outline, or decorate the canonical bird.
- **Don't** split caption, memory, and perch into separate rounded cards.
- **Don't** return to an anonymous gray-and-blue dictation dashboard.
- **Don't** use gradients, ornamental waveforms, badge collections, or oversized AI-marketing headlines.
- **Don't** apply the feather cut to ordinary controls or fill active navigation with pills.
- **Don't** copy another dictation product's branding, assets, wording, colors, or pixel-level layout.
