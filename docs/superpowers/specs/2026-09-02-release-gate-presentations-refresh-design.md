# Release Gate Presentations Refresh Design

## Context

The presentation set was last updated on 2026-08-28. Since then, the
`python-slugify` demo gained two newer Windows evidence sets:

- the 2026-09-01 automated three-verdict verification; and
- the 2026-09-02 production-style `PASS` run that deliberately did not invoke
  the hidden oracle.

The current presentations remain valid descriptions of the earlier benchmark
and oracle workflow, but they do not clearly distinguish that qualification
path from normal repository adoption. Several X1 slides also cite an older run
ID and an older baseline commit.

## Selected Design

Refresh the existing presentations in place. Preserve their IBM-blue visual
system, interactions, speaker-view behavior, and overall length. Reframe X1 so
the production/online workflow is the primary story while retaining hidden
oracle grading as a clearly labelled offline qualification mechanism.

The presentation must not imply that the September 2 candidate was generated
by Copilot. Its run log documents the Copilot workflow, but the recorded
candidate preparation applies the deterministic `pass.patch`. The deck should
state that an assistant or a calibrated control can produce the same four-file
candidate shape.

## Content Changes

### X1 Walkthrough

Update `docs/x1-behind-the-scenes.html` while preserving its 16-slide structure:

- cite the September 2 online run as the current primary evidence;
- use the current setup command and pinned upstream baseline
  `7b6d5d96c1995e6dccb39a19a13ba78d7d0a3ee4`;
- explain that Copilot receives the frozen task card without hints or oracle
  access, while the recorded September 2 candidate was reproduced with the
  deterministic pass control;
- update the verdict slide to run
  `20260902T153230Z-0b1d3f349b56` and its recorded `PASS` result;
- identify the three passing checks, four reviewed changed paths, and the
  non-gating `OBSERVABILITY_PATH_UNSAFE` warning;
- change the post-verdict story from an automatic oracle step to a production
  stop: inspect the evidence, review the diff, and decide whether to merge;
- retain hidden-oracle grading only as the offline lane used to calibrate the
  gate with known-answer controls; and
- state explicitly that `PASS` means policy acceptance and eligibility for
  human review, not proof of semantic correctness, merge, or deployment.

Speaker notes and source labels must follow the same distinction as the visible
slides.

### Executive Overview

Update `release-gate/demo/release-gate-demo.html` without adding slides:

- identify the online workflow as the normal production path;
- identify external oracle grading as benchmark-only qualification;
- cite the September 1 three-verdict Windows verification and September 2
  online `PASS` evidence where X1 is summarized; and
- preserve existing rate-limiter claims and bounded-repair content.

### Architecture Reference

Update `docs/architecture.html` to describe both operational modes accurately:

- online: assistant or control candidate, deterministic gate, evidence review,
  and human release decision without an oracle;
- offline: known-answer controls followed by external oracle grading; and
- replace the old X1 source run with the September 1 and September 2 logs.

Do not promote designed evidence-diversity or evidence-generation components to
implemented status.

### Presentation Hub and Root Entry

Update `docs/presentations.html` only where the X1 and executive card copy needs
the production/offline distinction. Keep the card count and deck durations
unchanged unless the HTML audit proves they are currently inaccurate.

Keep `index.html` as the lightweight redirect to the hub. No visual or
functional change is required there.

## Files Outside the Refresh

`docs/rate-limiter-behind-the-scenes.html` and
`docs/code-assistant-skill-plugin-development.html` require visual and link
verification but no content change unless that verification exposes a concrete
defect. The September updates do not invalidate their claims.

## Visual and Interaction Constraints

- Preserve each file's existing typography, color tokens, slide dimensions,
  navigation, notes drawer, and multi-screen speaker popup.
- Keep every slide within a 1280x720 viewport with no internal scrolling or
  clipped content.
- Prefer replacing stale copy over adding cards, panels, or a new slide.
- Do not add the Copilot screenshot unless it can replace existing content and
  remain legible without increasing slide density.
- Preserve reduced-motion behavior and direct-file operation.

## Verification

After editing:

1. Validate internal presentation links and referenced local assets.
2. Confirm slide counts and hub metadata agree.
3. Load every deck and the architecture reference in a browser at 1280x720.
4. Check every slide for clipping, overflow, unexpected wrapping, and console
   errors.
5. Exercise keyboard navigation and the speaker-notes entry point in the
   modified slide decks.
6. Run the existing presentation regression tests relevant to HTML structure,
   viewport fitting, and multi-screen popup behavior.
7. Run `graphify update .` after the final source edits.

## Non-Goals

- Redesigning the presentation theme or navigation system.
- Re-running the release-gate demos.
- Changing Release Gate runtime behavior, policy, or version.
- Removing offline oracle qualification or claiming that production
  repositories possess a hidden oracle.
- Adding deployment, merge, or security-attestation claims to a `PASS` verdict.
