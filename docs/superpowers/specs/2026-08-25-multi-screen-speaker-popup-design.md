# Multi-Screen Speaker Popup Design

## Context

The two standalone presentation decks expose a speaker-notes popup:

- `docs/code-assistant-skill-plugin-development.html`
- `release-gate/demo/release-gate-demo.html`

They must continue to work when opened directly with `file://`. The current implementation asks for Window Management permission, chooses another display when available, and calls `window.open()` with that display's coordinates. In practice, Chrome can clamp the popup to the current display. The flow treats that result as success and gives the presenter no way to distinguish a real secondary-display placement from a fallback.

## Root Cause

The implementation combines two separately gated operations in one asynchronous interaction:

1. `getScreenDetails()` may pause for a permission decision.
2. `window.open()` needs a valid user activation and is responsible for the actual placement.

The code also falls back to the current screen whenever detailed screen information is absent, denied, unsupported, or reports fewer than two displays. Because the fallback is silent, a clamped or unavailable cross-screen placement looks like a successful secondary-screen popup.

## Selected Design

Use a small permission-and-placement state machine shared structurally by both standalone decks.

1. On initialization, query the `window-management` permission when the Permissions API supports it. If permission is already granted, asynchronously cache `ScreenDetails` so the next presenter action can open the popup synchronously.
2. On the first presenter action when details are not cached, request `getScreenDetails()`. If permission is granted and another display exists, cache the selected target and change the control to clearly request one more click or keypress to open on that display. Do not pretend a popup was placed during this permission step.
3. On the next presenter action, call `window.open()` synchronously, using the cached target display's available coordinates and dimensions. Keep `moveTo()` and `resizeTo()` as compatibility reinforcement after creation.
4. Select the first display whose identity or full bounds differ from `currentScreen`; do not assume array position alone identifies the secondary display.
5. After opening, compare the popup's reported screen position with the target display bounds. If placement is outside the target, keep the usable popup open but show a concise warning that the browser or OS kept it on the current display and that it can be moved manually.
6. If the API is unsupported, permission is denied, or only one display is visible, open a normal popup on the current display and communicate that cross-screen placement was unavailable. Preserve the existing in-page notes drawer when popup creation itself is blocked.

Both decks retain their existing popup document, navigation, timer, and keyboard behavior. Only permission acquisition, target selection, opening, and placement feedback change.

## User Experience

- First use with undecided permission: the presenter activates Pop out or presses `N`, approves the browser prompt, and sees a short instruction to activate the control again.
- Second activation: the notes popup opens on the cached secondary display.
- Later uses while permission remains granted: screen details are warmed during initialization, so one activation normally opens the popup.
- Unsupported or clamped placement: the popup remains usable and the deck provides a specific explanation instead of silently claiming secondary-display success.

## Testing

Add a lightweight regression test that extracts and executes the presentation controller logic with browser APIs stubbed at their boundaries. Run the same assertions against both HTML files:

- permission acquisition does not call `window.open()` in the same interaction;
- a subsequent activation opens with the selected secondary display coordinates;
- target selection does not choose `currentScreen`;
- a one-screen or unsupported environment uses the documented fallback;
- a blocked popup retains the existing drawer fallback;
- both decks keep equivalent placement behavior.

Manual verification should cover direct `file://` opening in a Chromium browser with two displays, including first permission, second activation, reuse after closing the popup, and a denied-permission fallback.

## Non-Goals

- Requiring a local HTTP server.
- Automatically moving the main presentation into fullscreen on another display.
- Reworking speaker-note layout, slide navigation, or timer behavior.
- Adding non-Chromium multi-screen APIs that do not exist.
