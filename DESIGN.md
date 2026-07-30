---
name: Parrot
description: A quiet, local-first Windows voice utility for dictating into the app already in use.
colors:
  ink: "#20242a"
  ink-strong: "#111419"
  muted: "#696f79"
  muted-strong: "#505660"
  canvas: "#f6f7f9"
  surface: "#ffffff"
  surface-subtle: "#eef0f4"
  surface-hover: "#e8eaf0"
  line: "#dfe2e8"
  line-strong: "#c9cdd6"
  sidebar: "#171a20"
  sidebar-muted: "#9ba1ad"
  sidebar-active: "#f5f6f8"
  accent: "#5865f2"
  accent-hover: "#4753d8"
  accent-soft: "#e9ebff"
  success: "#16845b"
  warning: "#b96b18"
  danger: "#c13e43"
  danger-soft: "#fdebec"
typography:
  display:
    fontFamily: "Segoe UI Variable Text, Segoe UI, system-ui, sans-serif"
    fontSize: "24px"
    fontWeight: 720
    letterSpacing: "-0.025em"
  transcript:
    fontFamily: "Segoe UI Variable Text, Segoe UI, system-ui, sans-serif"
    fontSize: "17px"
    fontWeight: 480
    lineHeight: 1.55
    letterSpacing: "-0.012em"
  title:
    fontFamily: "Segoe UI Variable Text, Segoe UI, system-ui, sans-serif"
    fontSize: "14px"
    fontWeight: 680
    letterSpacing: "-0.01em"
  body:
    fontFamily: "Segoe UI Variable Text, Segoe UI, system-ui, sans-serif"
    fontSize: "12px"
    fontWeight: 400
    lineHeight: 1.5
  navigation:
    fontFamily: "Segoe UI Variable Text, Segoe UI, system-ui, sans-serif"
    fontSize: "13px"
    fontWeight: 600
  label:
    fontFamily: "Segoe UI Variable Text, Segoe UI, system-ui, sans-serif"
    fontSize: "11px"
    fontWeight: 650
  button:
    fontFamily: "Segoe UI Variable Text, Segoe UI, system-ui, sans-serif"
    fontSize: "12px"
    fontWeight: 650
  input:
    fontFamily: "Segoe UI Variable Text, Segoe UI, system-ui, sans-serif"
    fontSize: "14px"
    fontWeight: 400
rounded:
  tag: "6px"
  compact: "7px"
  chip: "8px"
  control: "9px"
  navigation: "10px"
  action: "12px"
  full: "99px"
spacing:
  micro: "3px"
  tight: "6px"
  control: "8px"
  row: "12px"
  layout: "20px"
  section: "28px"
components:
  button-primary:
    backgroundColor: "{colors.accent}"
    textColor: "{colors.surface}"
    typography: "{typography.button}"
    rounded: "{rounded.control}"
    padding: "0 14px"
    height: "34px"
  button-primary-hover:
    backgroundColor: "{colors.accent-hover}"
    textColor: "{colors.surface}"
  button-secondary:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    typography: "{typography.button}"
    rounded: "{rounded.control}"
    padding: "0 13px"
    height: "34px"
  button-record:
    backgroundColor: "{colors.accent}"
    textColor: "{colors.surface}"
    typography: "{typography.label}"
    rounded: "{rounded.action}"
    padding: "0 13px"
    height: "48px"
    width: "108px"
  input:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    typography: "{typography.input}"
    rounded: "{rounded.control}"
    padding: "0 10px"
    height: "36px"
  navigation-item:
    backgroundColor: "transparent"
    textColor: "{colors.sidebar-muted}"
    typography: "{typography.navigation}"
    rounded: "{rounded.navigation}"
    padding: "0 11px"
    height: "40px"
  navigation-item-active:
    backgroundColor: "rgba(255, 255, 255, 0.12)"
    textColor: "{colors.surface}"
  overlay:
    backgroundColor: "{colors.sidebar}"
    textColor: "{colors.sidebar-active}"
    rounded: "{rounded.action}"
    padding: "0 12px"
    height: "58px"
---

# Design System: Parrot

## Overview

**Creative North Star: "The Quiet Command Rail"**

Parrot is a professional native productivity tool that recedes until the user speaks. Its world combines an ink navigation rail with a cool paper workspace and a single confident cobalt action, creating the feeling of a focused Windows utility rather than a marketing dashboard or decorative AI demo.

The system is compact, direct, and visibly local. Readiness, live dictation, recovery, personalization, and settings follow one continuous command surface; hierarchy comes from typography, tonal contrast, and precise dividers instead of stacked cards. Rounded geometry is reserved for controls and the small recording overlay.

**Key Characteristics:**

- Ink-and-cool-paper desktop shell with a compact persistent rail.
- Cobalt interaction color used for the current primary action and focus.
- Flat, divider-led content regions with restrained control rounding.
- Direct status language and a persistent local-processing signal.
- Dense but readable Segoe UI typography suited to a Windows utility.

## Colors

The palette pairs cool near-neutrals with a saturated cobalt command color, then reserves green, amber, and red for explicit system state.

### Primary

- **Command Cobalt:** The primary dictation action, checked controls, text actions, and keyboard focus.
- **Pressed Cobalt:** Hovered primary actions.
- **Cobalt Mist:** Low-emphasis hover feedback behind text actions.

### Secondary

- **Local Green:** Ready and private-on-device status.
- **Working Amber:** Loading, processing, formatting, and setup status.
- **Recording Red:** Active recording, cancellation, destructive actions, and errors.
- **Red Wash:** Low-emphasis destructive hover feedback.

### Neutral

- **Terminal Black:** Highest-emphasis headings and transcript text.
- **Command Ink:** Default body and control text.
- **Graphite Label:** Secondary controls and durable labels.
- **Slate Annotation:** Descriptions, timestamps, and metadata.
- **Cool Paper:** The continuous application canvas.
- **Utility White:** Inputs and secondary controls that need separation from the canvas.
- **Cool Surface:** Secondary-control hover fill.
- **Hover Wash:** Neutral row-action hover fill.
- **Hairline:** Default section and row dividers.
- **Keyline:** Input borders and stronger structural rules.
- **Night Rail:** Persistent navigation and overlay ground.
- **Rail Slate:** Inactive navigation and overlay secondary copy.
- **Rail White:** Active navigation and high-emphasis overlay copy.

### Named Rules

**The One Cobalt Action Rule.** Use cobalt to identify the current primary action or focus, not to decorate entire sections.

**The State Has Meaning Rule.** Green means ready, amber means working, and red means recording, destructive action, or failure; never use these colors ornamentally.

## Typography

**Display Font:** Segoe UI Variable Text (with Segoe UI and system sans-serif fallbacks)

**Body Font:** Segoe UI Variable Text (with Segoe UI and system sans-serif fallbacks)

**Label/Mono Font:** Cascadia Mono (with Consolas and monospace fallbacks, diagnostics only)

**Character:** The single Windows-native sans-serif family keeps the product familiar and fast, while high-confidence weights create hierarchy without oversized display type. Monospace appears only where diagnostic content benefits from fixed alignment.

### Hierarchy

- **Display** (720, 24px, tight tracking): One page title per view.
- **Transcript** (480, 17px, 1.55): Live or last-completed dictated text.
- **Title** (680, 14px, tight tracking): Section and dictation headings.
- **Body** (400, 12px, 1.5): Explanations, history text, and concise supporting copy.
- **Navigation** (600, 13px): Persistent rail destinations.
- **Label** (650, 11px): Status, field names, toggle titles, and compact control copy.
- **Button** (650, 12px): Primary, secondary, text, and destructive actions.

### Named Rules

**The Native Voice Rule.** Use Segoe UI for every user-facing surface; reserve monospace for diagnostics and never use it as an AI-themed accent.

**The Compact Confidence Rule.** Establish hierarchy with weight and spacing before increasing type size; page titles stay compact and transcript text gets the most reading room.

## Layout

The desktop shell uses a fixed 190px Night Rail and a fluid workspace. A 44px status bar spans the workspace, while each view is centered inside a 960px maximum and uses 36px horizontal padding. Home proceeds vertically from readiness to dictation, live transcript, recent recovery, and device statistics in one uninterrupted surface.

The spacing rhythm is compact: 6–12px inside controls and rows, 20px between tightly related blocks, and 28px between major regions. Rows use one-pixel dividers and content aligns to shared left edges. At 820px and below, the rail collapses to 72px, text labels become hover and focus tooltips, view padding narrows to 28px, and multi-column personalization content becomes a single column.

**The Continuous Workspace Rule.** Dictation and transcript regions share the canvas and are separated by rules; do not wrap them in independent cards.

**The Recovery-in-View Rule.** The first viewport keeps readiness, both dictation modes, live text, recent recoverable work, and local usage totals visible together at the normal window size.

## Elevation & Depth

Parrot is flat by default. Tonal contrast and one-pixel dividers establish the shell, sections, and rows. Shadows are reserved for temporary or strongly interactive elements: the primary recording action, focus rings, toggle thumbs, compact navigation tooltips, and the floating overlay.

### Shadow Vocabulary

- **Focus halo** (`0 0 0 3px rgba(88, 101, 242, 0.22)`): Keyboard focus and active input focus.
- **Raised action** (`0 8px 16px rgba(88, 101, 242, 0.2)`): The resting hands-free action; it lifts slightly on hover.
- **Floating overlay** (`0 16px 38px rgba(11, 13, 17, 0.3)`): The non-focus-stealing recording overlay.
- **Compact tooltip** (`0 8px 20px rgba(0, 0, 0, 0.25)`): Collapsed rail labels only.

### Named Rules

**The Flat-by-Default Rule.** Persistent content stays flat; elevation communicates focus, a primary live action, or a temporary floating layer.

## Shapes

The form language is restrained and functional. Large content regions remain rectangular and open, while buttons, inputs, navigation items, and compact utility elements use gently rounded corners from 7px to 12px. Fully rounded geometry appears only on toggle tracks and circular status indicators.

**The Controls Own the Corners Rule.** Rounded corners belong to interactive controls and the compact overlay, never to stacked content containers.

## Components

### Buttons

- **Shape:** Compact controls use gently rounded corners; the hands-free action uses the larger action radius.
- **Primary:** Command Cobalt with white copy, a 34px control height, and restrained horizontal padding.
- **Hover / Focus:** Primary actions deepen to Pressed Cobalt; all variants use the cobalt focus halo. Pressed buttons move down by one pixel.
- **Secondary / Text / Destructive:** Secondary actions use Utility White with a keyline; text actions use cobalt on a transparent ground; destructive actions use Recording Red and Red Wash.

### Chips

- **Style:** Learned vocabulary uses small Utility White rectangles with a Hairline border and the chip radius.
- **State:** Chips display a term and muted repetition count; they communicate learned data, not navigation or promotional status.

### Cards / Containers

- **Corner Style:** Persistent content containers are not card-shaped.
- **Background:** Major regions share Cool Paper; Utility White is limited to form controls and secondary actions.
- **Shadow Strategy:** No shadow at rest; reference the flat-by-default rule.
- **Border:** One-pixel Hairline and Keyline dividers define sections and rows.
- **Internal Padding:** Section rhythm follows the layout scale rather than padded card shells.

### Inputs / Fields

- **Style:** Utility White fill, Keyline border, 9px control radius, and 36px height for single-line controls.
- **Focus:** Border changes to Command Cobalt and receives the focus halo.
- **Error / Disabled:** Disabled buttons reduce opacity; destructive treatment uses Recording Red rather than generic accent color.

### Navigation

The Night Rail uses 40px navigation rows, 10px corners, muted icons and labels at rest, a translucent white fill for the active destination, and a softer translucent fill on hover. The compact rail retains icons and reveals destination names through dark tooltips on hover or keyboard focus.

### Dictation Console

The console is a divider-led row containing the 48px hands-free action, push-to-talk shortcut instruction, timer, and cancellation. During recording, the action changes from Command Cobalt to Recording Red and uses a restrained breathing shadow; live state is also expressed in text so color is never the only signal.

### Recording Overlay

The overlay is a 58px Night Rail bar with 12px corners, a compact three-bar signal, direct state copy, and an uppercase interaction-mode label. It floats above other applications without adopting the full navigation shell.

## Do's and Don'ts

### Do:

- **Do** keep the common path visible as readiness, push-to-talk, hands-free, live transcript, recovery, and local usage.
- **Do** use one-pixel dividers and shared alignment to organize persistent content.
- **Do** keep cobalt concentrated on the primary action, checked state, text action, and focus.
- **Do** pair every colored status indicator with clear text.
- **Do** preserve keyboard focus, reduced-motion behavior, and readable secondary copy.

### Don't:

- **Don't** rebuild the workspace as stacked cards, floating panels, or badge collections.
- **Don't** use cream, ornamental gradients, decorative waveforms, or oversized AI-style headlines.
- **Don't** hide hands-free dictation behind an unlabeled icon.
- **Don't** surface engine, model, thread, or diagnostic controls before common dictation behavior.
- **Don't** copy another dictation product's branding, assets, wording, colors, or pixel-level layout.
