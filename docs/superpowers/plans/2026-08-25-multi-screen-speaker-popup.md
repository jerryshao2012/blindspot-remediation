# Multi-Screen Speaker Popup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make both standalone HTML presentation decks reliably open speaker notes on a secondary display from `file://`, with an activation-safe permission flow and explicit fallback feedback.

**Architecture:** Each deck keeps its self-contained `PresenterNotes` controller and popup document. Both controllers receive the same screen-access state machine: warm already-granted access, request undecided access without opening after an asynchronous boundary, and open only from a fresh synchronous activation once placement is known. A Python test extracts the real class by stable neighboring-class boundaries, evaluates it in Node, and constructs it normally with browser-boundary stubs.

**Tech Stack:** Standalone HTML/CSS/JavaScript, Window Management API, Permissions API, Python `pytest`, Node.js.

**Execution note:** Implemented in the current workspace after the implementation subagent hit a usage limit. Focused simulated browser coverage passes for both decks. The full `release-gate/tests` suite was run and exposed pre-existing release documentation/version-sync failures outside this popup scope; those failures are not addressed by this plan.

---

### Task 1: Protect the Existing Work and Establish a Trusted Harness

**Files:**
- Create: `release-gate/tests/test_presentation_multi_screen_popup.py`
- Inspect: `docs/code-assistant-skill-plugin-development.html`
- Inspect: `release-gate/demo/release-gate-demo.html`

- [ ] **Step 1: Record and inspect the initial working-tree state**

Run:

```bash
git status --short
git diff -- docs/code-assistant-skill-plugin-development.html release-gate/demo/release-gate-demo.html
```

Expected: both deck files are already modified, and their pre-existing changes are the user's attempted async Window Management implementation. Treat those edits as feature input, do not discard them, and compare the final whole-file diff against this baseline before staging. If any unrelated change is discovered, use `git add -p` at the final step.

- [ ] **Step 2: Extract each real controller using its stable next-class boundary**

Avoid lexical parsing entirely. The current files have unambiguous boundaries:

```python
DECKS = {
    Path("docs/code-assistant-skill-plugin-development.html"): "class InlineEditor",
    Path("release-gate/demo/release-gate-demo.html"): "class PresentationEditor",
}

def extract_presenter_notes(path: Path, end_marker: str) -> str:
    source = path.read_text(encoding="utf-8")
    start = source.index("class PresenterNotes")
    end = source.index(end_marker, start)
    controller = source[start:end]
    assert controller.count("class PresenterNotes") == 1
    return controller
```

The Node test program appends `globalThis.PresenterNotes = PresenterNotes;` and evaluates the result. Add a harness self-test for both decks that evaluates the complete extracted class and asserts `typeof PresenterNotes === "function"` before adding behavior assertions.

- [ ] **Step 3: Build minimal real-constructor browser stubs**

Implement reusable JavaScript `EventTargetStub`, `ClassListStub`, document elements for every ID read by the constructor, a document/window event registry, popup geometry, `alert`, `setInterval`, `clearInterval`, controlled `setTimeout`, and a presentation object with `slides`, `currentSlide`, `typing()`, `next()`, `previous()`, and `goTo()`.

Instantiate with `new PresenterNotes(presentation)`. At this pre-change checkpoint, assert only that the current class constructs and its existing pop-out button, keyboard, and `beforeunload` bindings work. Do not assert future `notesStatus`, state fields, or screen warm-up behavior here, and do not bypass the constructor.

- [ ] **Step 4: Run the extraction/constructor harness and establish GREEN**

Run:

```bash
uv run --project release-gate --group dev python -m pytest release-gate/tests/test_presentation_multi_screen_popup.py -q -k harness
```

Expected: PASS for both decks before production changes. Harness errors must be fixed before behavior tests are written.

### Task 2: Write the Activation-Safe Behavior Contract (RED)

**Files:**
- Modify: `release-gate/tests/test_presentation_multi_screen_popup.py`
- Test: `docs/code-assistant-skill-plugin-development.html`
- Test: `release-gate/demo/release-gate-demo.html`

- [ ] **Step 1: Model transient activation at the promise boundary**

Use a controlled deferred `getScreenDetails()` promise. The test helper's explicit `resolve()` and `reject()` functions set `activation = false` immediately before settling the promise. The `window.open()` stub records the call only when activation is true and otherwise returns `null`. This ordering ensures controller promise callbacks cannot open a window with stale activation.

- [ ] **Step 2: Add explicit parameterized state tests for both decks**

Create focused tests, rather than one aggregate assertion. Prefix state-only cases `test_state_`; they may call `requestScreenAccess()` directly and cover transitions, operation ownership, generation invalidation, target selection, labels, messages, and proof that asynchronous completion never opens. Prefix end-to-end opening/placement cases `test_popup_`; these stay RED until Task 5. Cover:

- unsupported `getScreenDetails()` enters resolved fallback;
- missing or throwing Permissions query with `getScreenDetails()` enters `needs-permission`;
- initialization never opens a popup;
- the real constructor resolves `notesStatus`, initializes all screen-state fields, and begins the appropriate warm-up;
- already-granted warm-up permits one-click synchronous open;
- activation during `checking` or `requesting` neither opens nor duplicates requests;
- prompted grant reaches `ready` but requires a fresh activation;
- prompted denial reaches `fallback` but requires a fresh activation;
- prompted one-screen result reaches `fallback` but requires a fresh activation;
- identity-equal and bounds-equal current screens are not selected;
- negative secondary coordinates are preserved in `window.open()` features;
- keyboard `N` uses the same activation-safe path as the button;
- permission changes map `prompt` → `needs-permission`, `denied` → `fallback`, and `granted` → `checking` plus warm-up, without opening;
- a prompted permission `change: granted` fired before the active details promise resolves preserves that user-request operation and reaches `ready` when it resolves;
- both `screenschange` and `currentscreenchange` recompute without opening;
- a stale warm-up result cannot restore access after invalidation;
- `moveTo()` and `resizeTo()` reinforcement receive the target geometry;
- finite `screenX`/`screenY` are preferred, with fallback to finite `screenLeft`/`screenTop`;
- placement at each exact 8-pixel tolerance boundary succeeds and the next pixel outside warns;
- absent finite popup coordinates does not produce a false clamping warning;
- correct placement clears obsolete status and clamped placement shows the exact stable warning;
- blocked popup opens the existing notes drawer.

- [ ] **Step 3: Add exact UI contract tests**

Target `#notesStatus` specifically and assert its `role="status"` and `aria-live="polite"` attributes without restricting other legitimate live regions. Assert labels and stable messages:

```text
checking/requesting: Checking displays…
needs-permission: ↗ Pop out
ready/fallback: Open speaker view
ready after prompt: Display access ready. Activate again to open speaker view.
single-screen fallback: A second display is unavailable; speaker view will open here.
unsupported/denied fallback: Display access unavailable; speaker view will open here.
clamped: The browser kept speaker view on this display. Move it to the other display manually.
```

- [ ] **Step 4: Run the behavior contract and verify RED**

Run:

```bash
uv run --project release-gate --group dev python -m pytest release-gate/tests/test_presentation_multi_screen_popup.py -q
```

Expected: harness cases remain GREEN; behavior and markup cases FAIL because the state machine and `#notesStatus` do not exist.

### Task 3: Add the Presenter Status Surface (GREEN for Markup)

**Files:**
- Modify: `docs/code-assistant-skill-plugin-development.html` in `.notes-actions` styles and notes drawer markup
- Modify: `release-gate/demo/release-gate-demo.html` in `.notes-actions` styles and notes drawer markup
- Test: `release-gate/tests/test_presentation_multi_screen_popup.py`

- [ ] **Step 1: Add the live status beside the pop-out control**

Insert inside `.notes-actions`, immediately before `#notesPopoutBtn`:

```html
<span class="notes-status" id="notesStatus" role="status" aria-live="polite"></span>
```

Add compact inline styling using each deck's existing tokens:

```css
.notes-status {
  display: none;
  max-width: 24rem;
  color: var(--muted);
  font-size: 0.72rem;
  line-height: 1.25;
}
.notes-status.visible { display: inline; }
```

- [ ] **Step 2: Run the targeted UI tests**

Run:

```bash
uv run --project release-gate --group dev python -m pytest release-gate/tests/test_presentation_multi_screen_popup.py -q -k status_markup
```

Expected: markup cases PASS. Behavior-label cases remain RED and are deliberately excluded until Task 4.

### Task 4: Implement the Race-Safe Screen-Access State Machine

**Files:**
- Modify: `docs/code-assistant-skill-plugin-development.html` in `PresenterNotes`
- Modify: `release-gate/demo/release-gate-demo.html` in `PresenterNotes`
- Test: `release-gate/tests/test_presentation_multi_screen_popup.py`

- [ ] **Step 1: Initialize state and stable listener identities**

Both constructors resolve `notesStatus` and initialize:

```javascript
this.screenAccessState = "checking";
this.screenDetails = null;
this.screenPermission = null;
this.targetScreen = null;
this.screenAccessPromise = null;
this.screenAccessGeneration = 0;
this.placementCheckTimer = null;
this.handleScreenTopologyChange = () => this.recomputeTargetScreen();
this.handleScreenPermissionChange = () => this.onScreenPermissionChange();
void this.initializeScreenAccess();
```

The main-window unload handler increments the generation, removes permission/topology listeners, clears placement timers, and closes the popup as it does today.

- [ ] **Step 2: Implement complete cache lifecycle helpers**

`clearScreenDetails()` removes both topology listeners from the prior live object, clears `screenDetails` and `targetScreen`, and increments `screenAccessGeneration`. `cacheScreenDetails(details, generation)` does nothing unless `generation === screenAccessGeneration`, replaces prior topology listeners using the stable bound functions, then calls the atomic `recomputeTargetScreen()` transition.

`sameScreen(a, b)` returns true for object identity or identical `left`, `top`, `width`, and `height`. `selectTargetScreen(details)` selects the first candidate that is neither identity-equal nor bounds-equal to `currentScreen`; negative coordinates remain untouched.

`recomputeTargetScreen()` atomically selects the candidate and updates state, label, and status without opening a window. A candidate enters `ready` and shows `Display access ready. Activate again to open speaker view.` No candidate enters `fallback` and shows `A second display is unavailable; speaker view will open here.` This same transition handles initial one-screen warm-up, topology loss, and topology gain.

- [ ] **Step 3: Implement exact label/status mapping**

`setScreenStatus(message)` controls only status text/visibility. A separate `renderScreenAccessState()` sets:

```javascript
const labels = {
  checking: "Checking displays…",
  requesting: "Checking displays…",
  "needs-permission": "↗ Pop out",
  ready: "Open speaker view",
  fallback: "Open speaker view"
};
```

- [ ] **Step 4: Implement initialization and permission transitions with generation guards**

`initializeScreenAccess()` uses `{name: "window-management"}` defensively. Unsupported API or known denial enters `fallback`; `prompt`, missing Permissions API, or a throwing query while `getScreenDetails()` exists enters `needs-permission`; granted permission enters `checking` and starts `loadScreenDetails(generation)`.

`onScreenPermissionChange()` maps `prompt` to `needs-permission` and `denied` to `fallback`, clearing cached details and showing `Display access unavailable; speaker view will open here.` A `granted` event that occurs while the user-initiated `requestScreenAccess()` operation is active preserves that operation's generation and lets its result become the granted warm-up; it must not start a competing request. A `granted` event with no active user request clears stale details, enters `checking`, and starts a guarded background warm-up. Neither it nor topology listeners open a window.

Every async completion captures its starting generation and confirms both that generation and, when available, current permission state before caching. A stale result exits without mutating state. Use `screenAccessPromise` to prevent duplicate in-flight calls and clear it only if it still refers to that operation. The prompted-grant ownership rule above is covered by a controlled test where `change: granted` fires before the details promise resolves, proving the preserved operation reaches `ready` rather than remaining in `checking`.

- [ ] **Step 5: Implement prompt acquisition without popup creation**

Activation in `needs-permission` synchronously enters `requesting`, starts one guarded `getScreenDetails()` operation, and returns. Its completion maps multiple screens to `ready` plus the ready message, one screen to `fallback` plus the second-display-unavailable message, and rejection to `fallback` plus the display-access-unavailable message; it updates the exact label but never calls `window.open()`. Unsupported and known-denied initialization use the same display-access-unavailable fallback message.

- [ ] **Step 6: Run state and race tests**

Run:

```bash
uv run --project release-gate --group dev python -m pytest release-gate/tests/test_presentation_multi_screen_popup.py -q -k test_state_
```

Expected: state-only transition, race, selection, label, message, and no-async-open tests PASS for both decks. `test_popup_*` cases remain RED and are deliberately excluded until Task 5.

### Task 5: Implement Synchronous Placement and Delayed Verification

**Files:**
- Modify: `docs/code-assistant-skill-plugin-development.html` in `PresenterNotes.openPopup()`
- Modify: `release-gate/demo/release-gate-demo.html` in `PresenterNotes.openPopup()`
- Test: `release-gate/tests/test_presentation_multi_screen_popup.py`

- [ ] **Step 1: Make `openPopup()` synchronous and state-gated**

Preserve the existing-popup focus branch. `checking` and `requesting` only report progress. `needs-permission` starts the request and returns. Only resolved `ready` or `fallback` computes geometry and calls `window.open()` immediately in the current activation. Keep each deck's existing popup name and drawer fallback.

For `ready`, derive coordinates from the cached target using nullish checks so negative values survive. For `fallback`, derive them from `window.screen`. Add `popup=yes` to the feature string.

- [ ] **Step 2: Reinforce placement deterministically**

Clear any prior `placementCheckTimer`. Capture the newly opened popup in `const openedPopup`. Call `moveTo(left, top)` and `resizeTo(width, height)` immediately and after 100 ms only while `this.popupWindow === openedPopup && !openedPopup.closed`.

- [ ] **Step 3: Verify the captured popup after 350 ms**

Verify only `ready` placement. Prefer a pair where both `screenX` and `screenY` are finite; otherwise use a pair where both `screenLeft` and `screenTop` are finite. If neither pair is finite, leave status unchanged and do not warn.

With tolerance `t = 8`, placement succeeds exactly when:

```javascript
x >= target.left - t && x < target.left + target.width + t &&
y >= target.top - t && y < target.top + target.height + t
```

This is half-open at the expanded maximum. Success clears obsolete placement status. Failure shows exactly `The browser kept speaker view on this display. Move it to the other display manually.` The callback only inspects `openedPopup` when it is still the current popup. Clear the timer on popup unload and main unload.

- [ ] **Step 4: Run the full focused suite and verify GREEN**

Run:

```bash
uv run --project release-gate --group dev python -m pytest release-gate/tests/test_presentation_multi_screen_popup.py -q
```

Expected: all parameterized cases PASS for both decks.

### Task 6: Full Verification, Graph Refresh, and Local Main Commit

**Files:**
- Verify: `docs/code-assistant-skill-plugin-development.html`
- Verify: `release-gate/demo/release-gate-demo.html`
- Verify: `release-gate/tests/test_presentation_multi_screen_popup.py`
- Refresh but do not stage: ignored `graphify-out/`

- [ ] **Step 1: Add executable structural checks to the focused test file**

Add tests that evaluate each complete extracted class in Node, compile the full inline script body with `new Function(scriptText)`, parse all HTML `id` attributes, assert no duplicate IDs, and assert exactly one correctly attributed `#notesStatus` per deck.

Run:

```bash
uv run --project release-gate --group dev python -m pytest release-gate/tests/test_presentation_multi_screen_popup.py -q
```

Expected: PASS.

- [ ] **Step 2: Run relevant repository tests**

Run:

```bash
uv run --project release-gate --group dev python -m pytest release-gate/tests -q
```

Expected: PASS.

- [ ] **Step 3: Perform available Chromium smoke verification**

Open each absolute `file://` URL in headed Chromium. Verify the deck renders, Pop out remains interactive, a denied or single-display fallback stays usable, and no console errors occur. With two displays exposed to the browser, additionally verify prompt-then-fresh-activation placement, close/reopen, and clamping feedback. If automation cannot expose two physical displays, explicitly report that limitation and rely on the activation-aware simulated cross-display suite for that branch.

- [ ] **Step 4: Refresh the required project graph without staging ignored output**

Run:

```bash
graphify update .
git status --short
```

Expected: graph update succeeds. `graphify-out/` remains ignored and untracked, so do not force-add it.

- [ ] **Step 5: Compare against the initial deck diff and inspect final staging**

Run `git diff --check` and inspect the complete diff. Confirm that the pre-existing target-file edits were the attempted implementation now intentionally replaced. Stage only:

```bash
git add docs/code-assistant-skill-plugin-development.html release-gate/demo/release-gate-demo.html release-gate/tests/test_presentation_multi_screen_popup.py docs/superpowers/plans/2026-08-25-multi-screen-speaker-popup.md
git diff --cached --check
git diff --cached --stat
git diff --cached
```

If the baseline inspection found unrelated hunks in either deck, use `git add -p` instead of whole-file staging.

- [ ] **Step 6: Commit locally on `main` only after verification**

```bash
git commit -m "fix: place speaker popup on secondary display"
```

Do not push. The implementation commit occurs only after all available verification passes.
