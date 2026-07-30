---
version: 1
slug: "desktop-index-html"
primary_target: "desktop/index.html"
related_targets: ["desktop/styles.css","desktop/renderer.js","desktop/overlay.html"]
---

# Desktop shell

- Scope and mode: the main Windows desktop utility in Operate mode.
- Audience: Windows professionals and developers who want fast, private dictation into the app already in use; the shell must also communicate real product judgment to a recruiter.
- Job and primary actions: verify readiness, start push-to-talk or hands-free dictation, read live words, cancel safely, and recover the previous result.
- Proof and content: real live transcript state, recoverable on-device history, device-only usage totals, dictionary/snippets, and explicit local processing status.
- Constraints: keep the established workflows and element IDs, work at 760×600 through 960×720, stay keyboard and side-mouse accessible, and never invent usage or accuracy claims.
- Chosen direction: the familiar desktop-dictation canon executed as a premium broadcast-caption desk—deep aubergine ink, cool chalk-lavender, and a single parrot-chartreuse command signal; Schibsted Grotesk replaces the incumbent Segoe system.
- Approved comp: `.impeccable/mocks/parrot-caption-stage.png`.
- Memorable moment: the live transcript is the central typographic stage while the last three dictations remain visible as a narrow session-memory strip; a bottom transport keeps both dictation modes and recovery one glance away.
- Do not literalize: sample transcript/history text, speculative durations, or any generated-image wording. Render only real application state.
- Unresolved: code signing and a real-microphone release check remain distribution concerns.

## Implementation inventory

| Visible ingredient | Commitment | Medium |
| --- | --- | --- |
| Brand and navigation rail | Custom geometric P, four labeled destinations, local-processing footer | Semantic HTML + inline SVG + CSS |
| Typography | 32–36px view title, 20–22px live text, 14–16px working copy, 12–13px metadata | Bundled Schibsted Grotesk variable font |
| Live transcript stage | Owns the center and expands before secondary content | Semantic HTML + CSS |
| Session memory | Three latest real dictations with time and direct route to History | Existing renderer data + CSS |
| Dictation transport | Hands-free, hold shortcut, timer, cancel, and paste previous remain together | Existing controls + CSS |
| State expression | Text plus restrained semantic color; chartreuse is reserved for primary command/focus | Existing renderer state + CSS |
| History, Personalize, Settings | Same functional density and component vocabulary as Home | Existing semantic forms + CSS |
| Recording overlay | Compact dark caption strip with large readable state copy | Existing overlay DOM + CSS |
