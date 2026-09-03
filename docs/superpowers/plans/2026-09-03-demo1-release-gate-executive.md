# Demo 1 Release Gate Executive Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and register a concise executive HTML presentation for the `python-slugify` Release Gate demo.

**Architecture:** Add a self-contained HTML deck under `docs/` using the existing presentation visual system and inline CSS/JS. Update the presentation hub with one new card positioned before the detailed X1 walkthrough.

**Tech Stack:** Static HTML, inline CSS, inline JavaScript, existing local presentation patterns.

---

## Files

- Create: `docs/demo1-release-gate-executive.html`
- Modify: `docs/presentations.html`
- Reference: `release-gate/demo/release-gate-demo.html`
- Reference: `docs/x1-behind-the-scenes.html`

### Task 1: Create Executive Deck

- [ ] Build a four-slide main narrative with appendices.
- [ ] Include speaker notes with a 10 minute main run of show.
- [ ] Include keyboard navigation, progress, slide dots, fullscreen, and notes drawer.
- [ ] Use evidence labels and caveats from the source decks.

### Task 2: Register Deck In Hub

- [ ] Add a new card in `docs/presentations.html`.
- [ ] Place it immediately before `X1 - Behind the Scenes`.
- [ ] Keep existing deck entries unchanged.

### Task 3: Verify

- [ ] Check that the new file exists and the hub links to it.
- [ ] Inspect the generated HTML for slide count, source labels, and timing notes.
- [ ] Run a syntax-oriented smoke check over the HTML files.
