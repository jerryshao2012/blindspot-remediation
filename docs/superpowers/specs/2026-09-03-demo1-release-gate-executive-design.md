# Demo 1 Release Gate Executive Presentation Design

## Approved Direction

Create a concise executive HTML deck for Demo 1, the `python-slugify` release gate demo, aimed at senior leadership.

By the end, Graham and EJ should understand that the Release Gate converts AI-generated code changes into an independent, auditable release decision because it checks scope, clean rebuilds, deterministic evidence, and human-accountable review rather than trusting the candidate agent's claim.

## Structure

The approved main story is four slides, designed to fit a 10 minute delivery:

1. Executive summary: condense the Release Gate architecture overview into one leadership-facing slide.
2. The `python-slugify` challenge: show why a small dependency migration has a wide blast radius across code, packaging, tox, and docs. Include Graphify as foundational codebase mapping context, not as a recorded gate check.
3. Live demonstration: guide a staged "cooking show" flow with prepped tabs, live environment execution where available, and saved receipts to avoid dead time.
4. Leadership takeaway: clarify that PASS means policy acceptance, not automatic merge; human accountability remains.

Technical details, screenshots, control runs, and source references belong in appendix slides.

## Source Constraints

- Use `release-gate/demo/release-gate-demo.html` as the executive source, compressed into one main slide.
- Use `docs/x1-behind-the-scenes.html` for Demo 1 proof details.
- Preserve the distinction between the September 2 known-good control replay and fresh AI-generated live output.
- Do not claim Graphify was part of the recorded September 2 gate execution unless supported elsewhere.
- Insert the new deck in `docs/presentations.html` immediately before `X1 - Behind the Scenes`.

## Visual Direction

Match the existing IBM-style HTML decks:

- Heebo for display/body copy and IBM Plex Mono for evidence labels.
- Light paper background, IBM blue accents, restrained green/amber/red verdict colors.
- Speaker notes and keyboard navigation included.
- Main slides stay sparse; presenter timing and talk track live in notes.
