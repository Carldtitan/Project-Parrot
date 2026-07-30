---
version: 1
slug: "desktop-index-html"
primary_target: "desktop/index.html"
related_targets: ["desktop/styles.css","desktop/renderer.js","desktop/overlay.html","desktop/assets/brand/parrot-mark.svg"]
---

# Desktop shell

- Scope and mode: the main Windows desktop utility in Operate mode.
- Audience: Windows professionals and developers who want fast, private dictation into the app already in use; the shell must also communicate real product judgment to a recruiter.
- Job and primary actions: verify readiness, start push-to-talk or hands-free dictation, read live words, cancel safely, and recover the previous result.
- Proof and content: real live transcript state, recoverable on-device history, device-only usage totals, dictionary/snippets, and explicit local processing status.
- Constraints: keep the established workflows and element IDs, work at 760×600 through the 1080×760 launch size, stay keyboard and side-mouse accessible, and never invent usage or accuracy claims.
- Chosen direction: a user-pinned literal-parrot identity—geometric right-facing bird, jungle chassis, mineral work surface, leaf command signal, macaw-coral recording state, and Onest typography—applied to a restrained familiar dictation shell.
- Approved direction: direct execution from the user’s literal-parrot brief after further option rounds were explicitly rejected; the canonical vector and rendered application are the authority.
- Memorable moment: the bird perches at the edge of the user’s work while the live transcript remains the visual center and the attached dark-green transport keeps every dictation control in one line.
- Do not literalize: sample transcript/history text, speculative durations, or generated-image wording. Render only real application state.
- Unresolved: code signing and a human-speaking release capture remain distribution concerns.

## Verification

- Home at 1080×760 and 760×600, compact Settings, recording, and the floating overlay were captured from Electron.
- The 760×600 surface retains start, shortcut, timer, recovery, and recording cancellation without horizontal or fixed-shell scrolling.
- The independent finish review passed after recording text reached 4.66:1 contrast and dedicated 16 px/32 px optical tray assets replaced automatic downscaling.
- Unit tests cover canonical SVG constraints and deterministic standard and optical icon geometry.
- The desktop workflow passes end to end in preview mode; the OS clipboard assertion reports unavailable in the current desktop session while copy IPC completion remains verified.

## Implementation inventory

| Visible ingredient | Commitment | Medium |
| --- | --- | --- |
| Literal parrot identity | One 64-unit right-facing geometric bird; head/body imply a hidden P; fixed jungle, leaf, wing, face, and coral shapes | Canonical SVG in `desktop/assets/brand/parrot-mark.svg` |
| App and installer icon | Pale mineral tile around the canonical vector with a fixed 10.5% inset | Deterministic Playwright renderer |
| Tray icon | Optical crop at exact 16 px and 32 px, combined as native 1×/2× representations | Generated PNGs from the canonical SVG |
| Brand and navigation rail | Literal mark, live wordmark, four destinations, chartreuse selection spine, local-processing footer | Semantic HTML + SVG image + CSS |
| Typography | 34px view title, 25px live text, 14–15px working copy, 10–13px metadata | Bundled Onest variable font |
| Live transcript stage | Pale central surface with a restrained bird watermark; expands before secondary content | Semantic HTML + CSS |
| Session memory | Recent real dictations, time, and compact local usage totals at the right edge | Existing renderer data + CSS |
| Dictation transport | Jungle-green attached perch with leaf primary command, shortcut, timer, recovery, and coral cancellation/finish | Existing controls + CSS |
| State expression | Text plus semantic green, amber, or coral; recording never relies on color alone | Existing renderer state + CSS |
| History, Personalize, Settings | Same mineral fields, Onest hierarchy, rule-led sections, and standard controls | Existing semantic forms + CSS |
| Recording overlay | Literal bird tile, explicit state/mode copy, status dot, and restrained listening motion | Existing overlay DOM + CSS |
