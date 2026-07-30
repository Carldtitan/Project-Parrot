# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Parrot is for Windows users who dictate frequently into other applications and
want a private, local-first alternative to cloud dictation products. Developers
are a primary long-term audience because they need accurate handling of code,
identifiers, technical vocabulary, and long prompts.

The product is also a portfolio-quality demonstration for recruiters, but the
recruiter demo must show a credible daily-use tool rather than a demo-only
interface.

## Product Purpose

Parrot turns speech into text in the application the user is already working
in. Its normal state is a background tray process. A compact window provides
live feedback, recovery, history, statistics, vocabulary, snippets, shortcut
configuration, and settings when the user chooses to open it.

Success means dictation starts immediately, remains understandable while the
user speaks, produces clean text, and can be cancelled or recovered without
losing work.

## Positioning

Parrot provides polished, system-wide Windows dictation while keeping speech
recognition and optional text cleanup on the user's machine.

## Operating Context

- Users dictate into editors, terminals, IDEs, browsers, messaging apps, email,
  and documents.
- Push-to-talk remains the primary interaction, with an optional hands-free
  mode.
- The tray and non-focus-stealing recording overlay remain part of normal use.
- The main window is opened for live feedback, recent transcript recovery,
  vocabulary, snippets, statistics, shortcuts, and advanced settings.
- The interface should feel immediately familiar to users of modern dictation
  products without copying another company's protected branding or exact visual
  expression.

## Capabilities and Constraints

- Windows 10 and 11 on x64 are the current supported platform.
- Speech recognition runs locally. A GPU is not required.
- The default transcription engine is Parakeet TDT 0.6B v3 through ONNX Runtime,
  with faster-whisper `small.en` as a fallback.
- Optional formatting runs through a local Ollama model and must preserve a safe
  raw-transcript fallback.
- Required dictation controls include push-to-talk, hands-free mode,
  configurable shortcuts, cancellation, and recovery or repaste of the previous
  transcript.
- Required text intelligence includes filler cleanup, spoken corrections,
  dictated list formatting, a personal dictionary, learned vocabulary, and
  reusable voice snippets.
- Required workflow support includes developer-aware text handling, safeguards
  for long sessions, persistent transcript history, and local usage statistics.
- Privacy and live transcription are non-negotiable.
- Clipboard restoration and insertion into the previously focused application
  must remain reliable.
- Cross-platform clients, accounts, cloud sync, and team administration are not
  part of the current Windows milestone.

## Brand Commitments

- The product name is Parrot.
- Product language is direct, calm, concise, and technically credible.
- Wispr Flow is a usability reference for interaction familiarity, not a source
  to copy assets, wording, colors, icons, or pixel-level layouts.
- Parrot must have its own visual identity and make local processing visible
  without turning privacy into decorative marketing.

## Evidence on Hand

- The repository contains a working Rust audio, hotkey, transcription, cleanup,
  and insertion engine.
- The Electron shell includes a tray process, live transcript window, and
  non-focus-stealing overlay.
- Local benchmark reports exist under `benchmarks/`.
- A reproducible Windows installer and rolling GitHub release workflow are
  documented.
- There are no customer testimonials, adoption numbers, or commercial claims;
  future surfaces must not fabricate them.

## Product Principles

1. Dictate where the work already is.
2. Never lose a user's words.
3. Keep the common path quiet and immediate.
4. Make powerful controls discoverable without putting them in the way.
5. Local processing is a product mechanism, not a badge collection.

## Accessibility & Inclusion

Keyboard operation, visible focus, clear state changes, reduced-motion support,
and readable contrast are required. Controls must not rely on color alone.
