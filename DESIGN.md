---
name: Parrot
description: A private Windows dictation tool expressed as a live broadcast-caption desk.
colors:
  ink: "#29232d"
  ink-strong: "#17131c"
  muted: "#746c79"
  muted-strong: "#564e5c"
  canvas: "#f3f0f5"
  surface: "#fbf9fc"
  surface-subtle: "#ebe7ee"
  surface-hover: "#e4dfe8"
  line: "#dcd5e0"
  line-strong: "#c5bdca"
  sidebar: "#1c1721"
  sidebar-muted: "#aca3b4"
  sidebar-active: "#fbf9fc"
  accent: "#d9ff57"
  accent-hover: "#c7ee3d"
  accent-soft: "#efffc1"
  accent-ink: "#3c4b00"
  success: "#16815a"
  warning: "#b66a19"
  danger: "#c84046"
  danger-hover: "#b43339"
  danger-soft: "#fdebed"
typography:
  display:
    fontFamily: "Schibsted Grotesk, Arial, sans-serif"
    fontSize: "clamp(30px, 4vw, 38px)"
    fontWeight: 720
    lineHeight: 1.02
    letterSpacing: "-0.05em"
  transcript:
    fontFamily: "Schibsted Grotesk, Arial, sans-serif"
    fontSize: "clamp(21px, 2.5vw, 27px)"
    fontWeight: 470
    lineHeight: 1.48
    letterSpacing: "-0.026em"
  title:
    fontFamily: "Schibsted Grotesk, Arial, sans-serif"
    fontSize: "17px"
    fontWeight: 690
    letterSpacing: "-0.025em"
  body:
    fontFamily: "Schibsted Grotesk, Arial, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.5
  navigation:
    fontFamily: "Schibsted Grotesk, Arial, sans-serif"
    fontSize: "14px"
    fontWeight: 570
  button:
    fontFamily: "Schibsted Grotesk, Arial, sans-serif"
    fontSize: "13px"
    fontWeight: 680
  label:
    fontFamily: "Schibsted Grotesk, Arial, sans-serif"
    fontSize: "12px"
    fontWeight: 650
  eyebrow:
    fontFamily: "Schibsted Grotesk, Arial, sans-serif"
    fontSize: "11px"
    fontWeight: 720
    letterSpacing: "0.12em"
  input:
    fontFamily: "Schibsted Grotesk, Arial, sans-serif"
    fontSize: "15px"
    fontWeight: 400
rounded:
  compact: "7px"
  control: "8px"
  medium: "9px"
  stage: "16px"
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
  dictation-transport:
    backgroundColor: "{colors.ink-strong}"
    textColor: "{colors.sidebar-active}"
    rounded: "{rounded.stage}"
    padding: "16px 18px"
    height: "88px"
  overlay:
    backgroundColor: "{colors.ink-strong}"
    textColor: "{colors.sidebar-active}"
    padding: "0 13px 0 8px"
    height: "58px"
---

# Design System: Parrot

## Overview

**Creative North Star: "The Caption Stage"**

Parrot is a broadcast-caption desk for live speech: focused, editorial, and visibly local. An aubergine rail anchors the application, a chalk-lavender field keeps the room quiet, and parrot chartreuse marks the command that matters now. Live words occupy the largest typographic surface while recent takes remain close enough to recover without turning the experience into a dashboard.

The interface behaves as one composed instrument. A light caption stage and its dark bottom transport form a single silhouette; rules, not nested cards, organize the rest of the product. Schibsted Grotesk gives headings a compact editorial snap and keeps working text human and readable across the minimum and standard window sizes.

**Key Characteristics:**

- Deep aubergine rail and transport against a chalk-lavender desktop field.
- Parrot chartreuse reserved for commands, focus, and the active rail tick.
- Large live-caption typography paired with restrained uppercase eyebrows.
- One composed caption stage with session memory at its right edge.
- Editorial rules, compact controls, explicit text states, and local-processing cues.

## Colors

The palette moves between aubergine ink and chalk-lavender fields, with a high-energy chartreuse command channel and restrained semantic state colors.

### Primary

- **Parrot Chartreuse:** Starts hands-free dictation, confirms primary form actions, marks the active rail destination, and signals local availability.
- **Pressed Chartreuse:** Hover state for primary actions.
- **Chartreuse Wash:** Background feedback for low-emphasis text actions.
- **Moss Ink:** Accessible text actions placed on light fields and copy placed against chartreuse.

### Secondary

- **Ready Green:** Ready engine status.
- **Working Amber:** Starting, processing, formatting, setup, and sample-preview state.
- **Recording Coral:** Recording, cancellation, destructive actions, and errors.
- **Deep Recording Coral:** Hover state for solid destructive actions.
- **Coral Wash:** Low-emphasis destructive hover feedback.

### Neutral

- **Aubergine Ink:** Default body and control copy.
- **Deep Aubergine:** Highest-emphasis text, the transport, and the overlay.
- **Plum Note:** Descriptions, timestamps, and secondary metadata.
- **Plum Label:** Durable labels and quiet controls.
- **Chalk Lavender:** Main application canvas.
- **Caption White:** Live stage, fields, and rail-active copy.
- **Lavender Veil:** Subtle neutral surface.
- **Lavender Hover:** Neutral row-action hover feedback.
- **Editorial Rule:** Default section and row dividers.
- **Strong Rule:** Input and control borders.
- **Night Aubergine:** Persistent navigation rail.
- **Rail Plum:** Inactive rail and overlay secondary copy.
- **Rail Paper:** Active navigation and high-emphasis dark-surface copy.

### Named Rules

**The One Command Signal Rule.** Chartreuse identifies the actionable or current command channel; it never becomes a decorative field color.

**The State Has Meaning Rule.** Ready green, working amber, and recording coral are semantic and always accompanied by readable state text.

## Typography

**Display Font:** Schibsted Grotesk (with Arial and sans-serif fallbacks)
**Body Font:** Schibsted Grotesk (with Arial and sans-serif fallbacks)
**Label/Mono Font:** Cascadia Mono (with Consolas and monospace fallbacks, diagnostics only)

**Character:** The bundled Schibsted Grotesk variable font is editorial without feeling precious. Tight display tracking makes view titles decisive, while the lower-weight caption role lets live speech feel open and continuous. Monospace is limited to diagnostic output.

### Hierarchy

- **Display** (720, clamp 30–38px, 1.02): One decisive title per view.
- **Transcript** (470, clamp 21–27px, 1.48): Live or last-completed dictated text; the central reading voice.
- **Title** (690, 17px, tight tracking): Caption, memory, settings, and subsection headings.
- **Body** (400, 14px, 1.5): Explanations, history entries, and supporting copy up to 64 characters wide.
- **Navigation** (570, 14px): Persistent rail destinations.
- **Button** (680, 13px): Primary, secondary, text, and transport actions.
- **Label** (650, 12px): Field names, status, settings descriptions, and metadata.
- **Eyebrow** (720, 11px, 0.12em, uppercase): Editorial orientation above the live stage and memory.

### Named Rules

**The Caption Owns Scale Rule.** Live transcript text is the largest working content on screen; settings and metadata never compete with it.

**The Editorial Label Rule.** Use uppercase, tracked eyebrows only to orient a region, never as repeated decoration or body copy.

## Layout

The desktop shell uses a 184px labeled rail and a fluid workspace above a 48px draggable status bar. Main views are centered within an 1180px maximum and use 38px side padding at the standard size. The Home view fills the available height: the live caption stage expands first, session memory occupies a 258px right column, and an 88px transport locks to the stage bottom.

Other views retain the same editorial field rather than reproducing the stage. History is a full-width ruled list; Personalize uses two 1fr columns with a 38px gap; Settings uses a 210px explanatory column beside fluid fields. The recurrent rhythm is 8–16px within controls, 24px between related regions, and 38px at major column and section boundaries.

At 980px and below, the rail contracts to 74px and exposes destination names through keyboard-accessible tooltips; session memory narrows to 230px and settings use a 180px explanatory column. At 780px and below, the view padding becomes 24px, memory narrows to 200px and shows only the most recent take, transport labels compact, personalization becomes one column, and settings fields stack.

**The Center Voice, Right Memory Rule.** On the live surface, the caption always receives the flexible center while recoverable session memory holds a narrower right edge.

**The One Transport Rule.** Hands-free, push-to-talk guidance, timer, recovery, and cancellation belong to one bottom control band.

## Elevation & Depth

Parrot is editorial and mostly flat. One-pixel rules structure lists and forms; tonal shifts separate the rail, caption surface, memory strip, and transport. Shadows are limited to the composed stage, its active chartreuse command, keyboard focus, collapsed-rail tooltips, and the floating overlay.

### Shadow Vocabulary

- **Focus halo** (`0 0 0 3px rgba(138, 165, 34, 0.36)`): Keyboard focus and active fields.
- **Caption float** (`0 18px 48px rgba(35, 27, 40, 0.08)`): Light lift beneath the live stage.
- **Transport float** (`0 18px 48px rgba(35, 27, 40, 0.12)`): Slightly stronger grounding below the dark transport.
- **Primary command** (`0 8px 20px rgba(121, 147, 27, 0.2)`): Chartreuse hands-free action at rest.
- **Floating overlay** (`0 16px 38px rgba(13, 9, 15, 0.34)`): Non-focus-stealing recording overlay above other applications.

### Named Rules

**The Instrument, Not Cards Rule.** Elevate the caption stage as one instrument; persistent rows, settings sections, and history remain flat and rule-led.

## Shapes

The signature silhouette is a 16px composite: the caption stage owns the top corners and the transport owns the bottom corners. Standard buttons and fields use compact 7–9px rounding, while the primary dictation action uses an 11px corner and the overlay uses 13px. Circular geometry is reserved for state dots and switch thumbs; toggle tracks are fully rounded. The active rail destination is marked by a narrow chartreuse edge tick rather than a filled pill.

**The Composite Stage Rule.** The light stage and dark transport must read as one object; never separate them into independent floating cards.

**The Editorial Edge Rule.** Use borders and edge ticks for hierarchy before introducing additional rounded containers.

## Components

### Buttons

- **Shape:** Standard actions use compact 8px corners and a 38px minimum height; the signature hands-free command is 50px tall with 11px corners.
- **Primary:** Parrot Chartreuse with Deep Aubergine copy and 16px horizontal padding.
- **Hover / Focus:** Primary actions shift to Pressed Chartreuse; all controls use the chartreuse focus halo, and pressed standard buttons move down by one pixel.
- **Secondary / Text / Destructive:** Secondary actions remain transparent with a Strong Rule border; text actions use Moss Ink and Chartreuse Wash; recording and destructive actions use the coral channel.

### Chips

- **Style:** Learned terms use a Caption White field, Editorial Rule border, compact 7px corners, and a muted repetition count.
- **State:** Chips report learned local vocabulary; they do not behave as promotional badges or primary navigation.

### Cards / Containers

- **Corner Style:** Only the composed caption-stage instrument uses the 16px container radius.
- **Background:** The live field uses Caption White; session memory uses a slightly darker lavender field; the transport uses Deep Aubergine.
- **Shadow Strategy:** Stage and transport use the caption and transport shadows as one silhouette.
- **Border:** Editorial Rule defines the stage seam, memory division, and row structure.
- **Internal Padding:** The live field uses 27–30px; memory uses 16–27px; transport uses 16px vertically and 18px horizontally.

### Inputs / Fields

- **Style:** Caption White fill, Strong Rule border, 8px control corners, and 42px height for single-line fields.
- **Focus:** Border shifts toward chartreuse and receives the focus halo.
- **Error / Disabled:** Disabled actions reduce opacity; destructive feedback uses coral rather than the command accent.

### Navigation

The Night Aubergine rail uses 43px rows with 9px corners, Rail Plum copy at rest, Rail Paper on hover and active states, and a 3px chartreuse edge tick for the current destination. Below 980px, icons remain visible and dark tooltips reveal labels on hover or keyboard focus.

### Caption Stage

The live field is the flexible center of Home and carries the largest working type. Its right-side session memory shows recent takes and a compact two-by-two usage grid. During recording, a 4px inset coral rule appears on the live edge while text labels also announce the state.

### Dictation Transport

The dark bottom band keeps the chartreuse hands-free action, push-to-talk shortcut, timer, paste recovery, and cancellation in one scan line. At the compact breakpoint, secondary labels shorten and mutually exclusive recovery or cancellation actions preserve space.

### Toggle Rows

Settings toggles pair a 13px title and 12px description with a 40×23px track. Checked state uses a darker chartreuse-derived green, and keyboard focus uses the standard halo.

### Recording Overlay

The overlay is a 58px Deep Aubergine strip with 13px corners, a 42px signal tile, readable state and mode text, and the floating-overlay shadow. Chartreuse represents non-recording work; coral plus white meter bars represents active recording.

## Do's and Don'ts

### Do:

- **Do** give live speech the flexible center and largest working type.
- **Do** keep chartreuse concentrated on the current command, focus, active rail tick, and local signal.
- **Do** keep session memory visible beside the live caption at supported desktop widths.
- **Do** use editorial rules and shared edges to organize history, settings, and personalization.
- **Do** pair every colored state with explicit text, visible keyboard focus, and reduced-motion behavior.
- **Do** preserve the single composed silhouette between the live stage and bottom transport.

### Don't:

- **Don't** split the caption stage, memory, and transport into separate rounded cards.
- **Don't** reintroduce the generic cool-gray, cobalt, and Segoe dashboard identity.
- **Don't** use decorative gradients, ornamental waveforms, badge collections, or oversized AI-marketing headlines.
- **Don't** fill every active navigation item or content section with a rounded pill.
- **Don't** place engine, model, thread, or diagnostic controls before everyday dictation behavior.
- **Don't** copy another dictation product's branding, assets, wording, colors, or pixel-level layout.
