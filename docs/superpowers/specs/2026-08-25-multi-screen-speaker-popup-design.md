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

Use a small permission-and-placement state machine shared structurally by both standalone decks. Its access state is one of `checking`, `needs-permission`, `requesting`, `ready`, or `fallback`:

1. On initialization, enter `checking` and query the `window-management` permission when the Permissions API supports it. If permission is already granted, asynchronously obtain and cache `ScreenDetails`, then enter `ready` when another display exists or `fallback` when it does not. Permission state `prompt`, or an unavailable/failing Permissions query when `getScreenDetails()` exists, enters `needs-permission`. Known denial or an unsupported Window Management API enters `fallback`. Initialization never opens a window.
2. If the presenter activates the control while `checking` is in flight, do not open a window; show that display access is still being checked. Repeated activations while `checking` or `requesting` do not start duplicate requests.
3. On a presenter action in `needs-permission`, enter `requesting` and call `getScreenDetails()`. Whether that asynchronous request resolves to multiple screens, one screen, denial, or error, it only caches the resulting `ready` or `fallback` state. It never calls `window.open()` after the asynchronous boundary. The control then asks for a fresh click or keypress.
4. On a presenter action when state is `ready`, call `window.open()` synchronously using the cached target display's available coordinates and dimensions. On a presenter action when state is a previously resolved `fallback`, synchronously open a normal current-display popup. Keep `moveTo()` and `resizeTo()` as compatibility reinforcement after creation.
5. Treat a screen as the current screen when it is the same object as `currentScreen` **or** has identical `left`, `top`, `width`, and `height` bounds. Select the first candidate that satisfies neither equivalence test; do not assume array position alone identifies the secondary display. Negative `left` or `top` coordinates are valid.
6. Subscribe to `screenschange` and `currentscreenchange` on the live `ScreenDetails` object and recompute the target. Subscribe to the permission object's `change` event and clear cached details when permission is no longer granted. A permission change to `prompt` enters `needs-permission`, `denied` enters `fallback`, and `granted` enters `checking` while details warm. A topology or permission change never opens a window on its own.
7. After the final compatibility move attempt, sample `screenX`/`screenY`, falling back to `screenLeft`/`screenTop`. Treat placement as successful when that point is inside the target's `[left, left + width)` and `[top, top + height)` bounds with an 8 CSS-pixel tolerance for browser chrome. If it is outside, keep the usable popup open but warn that the browser or OS kept it on another display and that it can be moved manually.
8. If popup creation itself is blocked, preserve the existing in-page notes drawer fallback.

Both decks retain their existing popup document, navigation, timer, and keyboard behavior. Only permission acquisition, target selection, opening, and placement feedback change.

## User Experience

- First use with undecided permission: the presenter activates Pop out or presses `N`, approves the browser prompt, and sees a short instruction to activate the control again.
- Second activation: the notes popup opens on the cached secondary display.
- Later uses while permission remains granted: screen details are warmed during initialization, so one activation normally opens the popup.
- While access is being checked, the control reads `Checking displays…`. After an asynchronous result it reads `Open speaker view` and the status asks for a fresh activation.
- Add a dedicated presenter-status element beside the pop-out control with `role="status"` and `aria-live="polite"`. Both decks use this surface for stable messages: `Display access ready. Activate again to open speaker view.`, `A second display is unavailable; speaker view will open here.`, and `The browser kept speaker view on this display. Move it to the other display manually.`
- Unsupported, denied, single-screen, or clamped placement leaves the popup usable and gives the presenter a specific explanation instead of silently claiming secondary-display success.

## Testing

Add a lightweight regression test that extracts and executes the presentation controller logic with browser APIs stubbed at their boundaries. Run the same assertions against both HTML files:

- permission acquisition does not call `window.open()` in the same interaction;
- a subsequent activation opens with the selected secondary display coordinates;
- target selection does not choose `currentScreen`;
- a one-screen or unsupported environment uses the documented fallback;
- a blocked popup retains the existing drawer fallback;
- both decks keep equivalent placement behavior.

The state-machine cases cover already-granted warm-up opening in one activation; an activation while initialization is in flight; denied, prompted, and one-screen outcomes requiring a fresh activation; permission and topology invalidation; negative secondary-display coordinates; correct placement producing no warning; and clamped placement producing the stable warning. The harness models activation explicitly so an attempted `window.open()` after an asynchronous boundary fails, proving that the implementation uses a fresh synchronous activation.

Manual verification should cover direct `file://` opening in a Chromium browser with two displays, including first permission, second activation, reuse after closing the popup, and a denied-permission fallback.

## Non-Goals

- Requiring a local HTTP server.
- Automatically moving the main presentation into fullscreen on another display.
- Reworking speaker-note layout, slide navigation, or timer behavior.
- Adding non-Chromium multi-screen APIs that do not exist.
