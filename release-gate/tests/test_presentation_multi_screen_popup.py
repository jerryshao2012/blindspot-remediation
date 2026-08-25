from __future__ import annotations

import json
import re
import subprocess
from html.parser import HTMLParser
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
DECKS = {
    ROOT / "docs/code-assistant-skill-plugin-development.html": "class InlineEditor",
    ROOT / "release-gate/demo/release-gate-demo.html": "class PresentationEditor",
}


def extract_presenter_notes(path: Path, end_marker: str) -> str:
    source = path.read_text(encoding="utf-8")
    start = source.index("class PresenterNotes")
    end = source.index(end_marker, start)
    controller = source[start:end]
    assert controller.count("class PresenterNotes") == 1
    return controller


def inline_scripts(path: Path) -> list[str]:
    source = path.read_text(encoding="utf-8")
    return re.findall(r"<script(?:\s[^>]*)?>(.*?)</script>", source, re.DOTALL | re.IGNORECASE)


class IdParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: list[str] = []
        self.notes_status_attrs: list[dict[str, str | None]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = dict(attrs)
        if "id" in attr_map:
            self.ids.append(attr_map["id"] or "")
        if attr_map.get("id") == "notesStatus":
            self.notes_status_attrs.append(attr_map)


NODE_HARNESS = r"""
const fs = require("fs");
const vm = require("vm");
const payload = JSON.parse(fs.readFileSync(0, "utf8"));

function makeEventTarget() {
  return {
    listeners: {},
    addEventListener(type, handler) {
      (this.listeners[type] ||= []).push(handler);
    },
    removeEventListener(type, handler) {
      this.listeners[type] = (this.listeners[type] || []).filter((item) => item !== handler);
    },
    dispatch(type, event = {}) {
      for (const handler of this.listeners[type] || []) handler(event);
    },
  };
}

class ClassListStub {
  constructor() { this.values = new Set(); }
  add(...items) { for (const item of items) this.values.add(item); }
  remove(...items) { for (const item of items) this.values.delete(item); }
  toggle(item, force) {
    const enabled = force === undefined ? !this.values.has(item) : Boolean(force);
    if (enabled) this.values.add(item);
    else this.values.delete(item);
    return enabled;
  }
  contains(item) { return this.values.has(item); }
}

function makeElement(id = "") {
  const target = makeEventTarget();
  return Object.assign(target, {
    id,
    type: "",
    className: "",
    dataset: {},
    style: { values: {}, setProperty(name, value) { this.values[name] = value; } },
    classList: new ClassListStub(),
    attributes: {},
    children: [],
    textContent: "",
    innerHTML: "",
    closed: false,
    setAttribute(name, value) { this.attributes[name] = String(value); },
    getAttribute(name) { return this.attributes[name]; },
    appendChild(child) { this.children.push(child); return child; },
    querySelector(selector) {
      if (selector === ".speaker-notes") return this.notes || null;
      if (selector === ".eyebrow") return { textContent: this.dataset.eyebrow || "Eyebrow" };
      if (selector === "h1, h2") return { textContent: this.dataset.title || "Slide" };
      if (selector === "p") return { textContent: "Preview" };
      return null;
    },
    querySelectorAll() { return []; },
  });
}

function makeDocument() {
  const target = makeEventTarget();
  const ids = [
    "notesDrawer", "notesTitle", "notesContent", "slideTarget", "sessionTimer",
    "timerToggle", "notesPopoutBtn", "notesClose", "notesStatus",
  ];
  const elements = Object.fromEntries(ids.map((id) => [id, makeElement(id)]));
  elements.notesDrawer.classList = new ClassListStub();

  const doc = Object.assign(target, {
    body: { classList: new ClassListStub() },
    elements,
    documentElement: { outerHTML: "" },
    open() {},
    close() {},
    write(html) {
      this.html = html;
      for (const id of html.matchAll(/id="([^"]+)"/g)) {
        this.elements[id[1]] ||= makeElement(id[1]);
      }
    },
    createElement(tag) {
      const el = makeElement("");
      el.tagName = tag.toUpperCase();
      return el;
    },
    getElementById(id) { return this.elements[id] || null; },
    querySelector(selector) {
      if (selector === ".edit-banner") return makeElement("editBanner");
      return null;
    },
    querySelectorAll(selector) {
      if (selector === ".slide-nav-item") {
        return Object.values(this.elements).filter((el) => el.className === "slide-nav-item");
      }
      return [];
    },
  });
  return doc;
}

function makeSlide(index) {
  const slide = makeElement(`slide-${index + 1}`);
  const notes = makeElement(`notes-${index + 1}`);
  notes.dataset.duration = "02:00";
  notes.innerHTML = `<p>Slide ${index + 1} notes</p>`;
  notes.querySelector = (selector) => selector === "p" ? { textContent: `Slide ${index + 1} notes` } : null;
  slide.dataset.title = `Slide ${index + 1}`;
  slide.notes = notes;
  return slide;
}

function makePermission(state) {
  const permission = makeEventTarget();
  permission.state = state;
  permission.setState = (next) => {
    permission.state = next;
    permission.dispatch("change", { target: permission });
  };
  return permission;
}

function makeDeferred() {
  let resolve;
  let reject;
  const promise = new Promise((res, rej) => {
    resolve = (value) => { globalThis.__activation = false; res(value); };
    reject = (error) => { globalThis.__activation = false; rej(error); };
  });
  return { promise, resolve, reject };
}

function makeWindow(options = {}) {
  const target = makeEventTarget();
  const timeouts = [];
  const win = Object.assign(target, {
    screen: { availLeft: 0, availTop: 0, availWidth: 1440, availHeight: 900, left: 0, top: 0, width: 1440, height: 900 },
    screenLeft: 0,
    screenTop: 0,
    screenX: 0,
    screenY: 0,
    Date,
    console,
    Promise,
    Object,
    Math,
    Array,
    String,
    Number,
    Boolean,
    Error,
    JSON,
    globalThis: null,
    __activation: false,
    __opens: [],
    __alerts: [],
    __timeouts: timeouts,
    alert() {},
    setInterval() { return 1; },
    clearInterval() {},
    setTimeout(handler, delay) {
      const item = { handler, delay, cleared: false };
      timeouts.push(item);
      return item;
    },
    clearTimeout(item) {
      if (item) item.cleared = true;
    },
    runTimers(delay) {
      for (const timer of [...timeouts]) {
        if (!timer.cleared && timer.delay === delay) timer.handler();
      }
    },
    open(url, name, features) {
      this.__opens.push({ url, name, features, activation: this.__activation });
      if (!this.__activation || options.blockPopup) return null;
      const popupDoc = makeDocument();
      const popup = Object.assign(makeEventTarget(), {
        name,
        features,
        document: popupDoc,
        closed: false,
        moveCalls: [],
        resizeCalls: [],
        focusCalls: 0,
        screenX: options.popupScreenX,
        screenY: options.popupScreenY,
        screenLeft: options.popupScreenLeft,
        screenTop: options.popupScreenTop,
        moveTo(left, top) { this.moveCalls.push([left, top]); },
        resizeTo(width, height) { this.resizeCalls.push([width, height]); },
        focus() { this.focusCalls += 1; },
        close() { this.closed = true; },
      });
      return popup;
    },
  });
  win.alert = (message) => { win.__alerts.push(message); };
  win.globalThis = win;
  return win;
}

async function flush() {
  for (let i = 0; i < 10; i += 1) {
    await Promise.resolve();
  }
}

function install(options = {}) {
  const doc = makeDocument();
  const win = makeWindow(options);
  win.document = doc;
  win.window = win;
  win.navigator = {};
  win.location = { hash: "" };
  win.history = { replaceState() {} };
  win.localStorage = { getItem() { return null; }, setItem() {} };
  win.URL = { createObjectURL() { return "blob:test"; }, revokeObjectURL() {} };
  win.Blob = function Blob() {};
  win.Node = function Node() {};
  win.HTMLElement = function HTMLElement() {};
  win.document = doc;
  win.globalThis = win;
  if (options.permissionState !== undefined) {
    const permission = makePermission(options.permissionState);
    win.__permission = permission;
    win.navigator.permissions = {
      query(args) {
        win.__permissionQueries = (win.__permissionQueries || []);
        win.__permissionQueries.push(args);
        if (options.permissionThrows) return Promise.reject(new Error("permission query failed"));
        return Promise.resolve(permission);
      },
    };
  } else if (options.permissionThrows) {
    win.navigator.permissions = {
      query() { return Promise.reject(new Error("permission query failed")); },
    };
  }
  if (options.details || options.deferredDetails || options.deferredDetailsQueue) {
    win.getScreenDetails = () => {
      win.__detailsCalls = (win.__detailsCalls || 0) + 1;
      if (options.deferredDetailsQueue) return options.deferredDetailsQueue.shift().promise;
      return options.deferredDetails ? options.deferredDetails.promise : Promise.resolve(options.details);
    };
  }
  vm.createContext(win);
  vm.runInContext(payload.controller + "\nglobalThis.PresenterNotes = PresenterNotes;", win);
  const slides = [makeSlide(0), makeSlide(1), makeSlide(2)];
  const presentation = {
    slides,
    currentSlide: 0,
    demoStatus: { textContent: "demo" },
    demoStep: 0,
    typing() { return false; },
    next() { this.currentSlide += 1; },
    previous() { this.currentSlide -= 1; },
    goTo(index) { this.currentSlide = index; },
  };
  const notes = new win.PresenterNotes(presentation);
  return { win, doc, notes, presentation };
}

function stateSnapshot(notes, win) {
  return {
    state: notes.screenAccessState,
    label: notes.popoutButton && notes.popoutButton.textContent,
    status: notes.notesStatus && notes.notesStatus.textContent,
    statusVisible: notes.notesStatus && notes.notesStatus.classList.contains("visible"),
    opens: win.__opens.length,
    detailsCalls: win.__detailsCalls || 0,
    permissionQueries: win.__permissionQueries || [],
  };
}

async function scenario(name) {
  const primary = { left: 0, top: 0, width: 1440, height: 900, availLeft: 0, availTop: 0, availWidth: 1440, availHeight: 900 };
  const secondary = { left: -1920, top: 0, width: 1920, height: 1080, availLeft: -1920, availTop: 0, availWidth: 1920, availHeight: 1080 };
  const oneScreen = { screens: [primary], currentScreen: primary };
  const twoScreens = { screens: [primary, secondary], currentScreen: primary };

  if (name === "construct") {
    const ctx = install();
    return {
      type: typeof ctx.win.PresenterNotes,
      clickHandlers: ctx.doc.getElementById("notesPopoutBtn").listeners.click.length,
      keyHandlers: ctx.doc.listeners.keydown.length,
      unloadHandlers: ctx.win.listeners.beforeunload.length,
    };
  }
  if (name === "unsupported") {
    const ctx = install();
    await flush();
    return stateSnapshot(ctx.notes, ctx.win);
  }
  if (name === "permission_missing_with_api") {
    const ctx = install({ details: twoScreens });
    await flush();
    return stateSnapshot(ctx.notes, ctx.win);
  }
  if (name === "permission_throwing_with_api") {
    const ctx = install({ details: twoScreens, permissionThrows: true });
    await flush();
    return stateSnapshot(ctx.notes, ctx.win);
  }
  if (name === "granted_ready_open") {
    const ctx = install({ details: twoScreens, permissionState: "granted", popupScreenX: -1900, popupScreenY: 20 });
    await flush();
    ctx.win.__activation = true;
    const popup = ctx.notes.openPopup();
    ctx.win.__activation = false;
    ctx.win.runTimers(100);
    ctx.win.runTimers(350);
    return {
      ...stateSnapshot(ctx.notes, ctx.win),
      resultIsPopup: popup === ctx.notes.popupWindow,
      features: ctx.win.__opens[0]?.features || "",
      moveCalls: ctx.notes.popupWindow?.moveCalls || [],
      resizeCalls: ctx.notes.popupWindow?.resizeCalls || [],
      warning: ctx.notes.notesStatus.textContent,
    };
  }
  if (name === "needs_permission_fresh_activation") {
    const deferred = makeDeferred();
    const ctx = install({ deferredDetails: deferred });
    await flush();
    ctx.win.__activation = true;
    const first = ctx.notes.openPopup();
    ctx.win.__activation = false;
    deferred.resolve(twoScreens);
    await first;
    await flush();
    const afterFirst = stateSnapshot(ctx.notes, ctx.win);
    ctx.win.__activation = true;
    const second = ctx.notes.openPopup();
    ctx.win.__activation = false;
    return { afterFirst, secondOpened: second === ctx.notes.popupWindow, opens: ctx.win.__opens.length };
  }
  if (name === "needs_permission_denied") {
    const deferred = makeDeferred();
    const ctx = install({ deferredDetails: deferred });
    await flush();
    ctx.win.__activation = true;
    const first = ctx.notes.openPopup();
    ctx.win.__activation = false;
    deferred.reject(new Error("denied"));
    await first;
    await flush();
    const afterFirst = stateSnapshot(ctx.notes, ctx.win);
    ctx.win.__activation = true;
    const second = ctx.notes.openPopup();
    ctx.win.__activation = false;
    return { afterFirst, secondOpened: second === ctx.notes.popupWindow };
  }
  if (name === "one_screen") {
    const deferred = makeDeferred();
    const ctx = install({ deferredDetails: deferred });
    await flush();
    ctx.win.__activation = true;
    const first = ctx.notes.openPopup();
    ctx.win.__activation = false;
    deferred.resolve(oneScreen);
    await first;
    await flush();
    const afterFirst = stateSnapshot(ctx.notes, ctx.win);
    ctx.win.__activation = true;
    const second = ctx.notes.openPopup();
    ctx.win.__activation = false;
    return { afterFirst, secondOpened: second === ctx.notes.popupWindow };
  }
  if (name === "keyboard_n") {
    const ctx = install({ details: twoScreens, permissionState: "granted", popupScreenX: -1900, popupScreenY: 20 });
    await flush();
    ctx.win.__activation = true;
    ctx.doc.dispatch("keydown", { key: "N", target: {}, preventDefault() { this.prevented = true; } });
    ctx.win.__activation = false;
    return { opens: ctx.win.__opens.length, name: ctx.win.__opens[0]?.name || "" };
  }
  if (name === "permission_changes") {
    const ctx = install({ details: twoScreens, permissionState: "prompt" });
    await flush();
    ctx.win.__permission.setState("denied");
    await flush();
    const denied = stateSnapshot(ctx.notes, ctx.win);
    ctx.win.__permission.setState("prompt");
    await flush();
    const prompt = stateSnapshot(ctx.notes, ctx.win);
    ctx.win.__permission.setState("granted");
    await flush();
    const granted = stateSnapshot(ctx.notes, ctx.win);
    return { denied, prompt, granted };
  }
  if (name === "active_grant_preserves_request") {
    const deferred = makeDeferred();
    const ctx = install({ deferredDetails: deferred, permissionState: "prompt" });
    await flush();
    ctx.win.__activation = true;
    const first = ctx.notes.openPopup();
    ctx.win.__activation = false;
    ctx.win.__permission.setState("granted");
    await flush();
    const callsBeforeResolve = ctx.win.__detailsCalls || 0;
    deferred.resolve(twoScreens);
    await first;
    await flush();
    return { callsBeforeResolve, snapshot: stateSnapshot(ctx.notes, ctx.win) };
  }
  if (name === "granted_warmup_deduplicates") {
    const deferred = makeDeferred();
    const ctx = install({ deferredDetails: deferred, permissionState: "granted" });
    await flush();
    ctx.notes.startWarmScreenDetails();
    ctx.notes.startWarmScreenDetails();
    const callsBeforeResolve = ctx.win.__detailsCalls || 0;
    deferred.resolve(twoScreens);
    await flush();
    return { callsBeforeResolve, snapshot: stateSnapshot(ctx.notes, ctx.win) };
  }
  if (name === "stale_inflight_does_not_capture_fresh_request") {
    const staleDeferred = makeDeferred();
    const freshDeferred = makeDeferred();
    const ctx = install({ deferredDetailsQueue: [staleDeferred, freshDeferred], permissionState: "granted" });
    await flush();
    const initialCalls = ctx.win.__detailsCalls || 0;
    ctx.win.__permission.setState("prompt");
    await flush();
    ctx.win.__activation = true;
    const request = ctx.notes.openPopup();
    ctx.win.__activation = false;
    const callsAfterFreshRequest = ctx.win.__detailsCalls || 0;
    staleDeferred.resolve(twoScreens);
    await flush();
    const afterStale = stateSnapshot(ctx.notes, ctx.win);
    freshDeferred.resolve(twoScreens);
    await request;
    await flush();
    return { initialCalls, callsAfterFreshRequest, afterStale, final: stateSnapshot(ctx.notes, ctx.win) };
  }
  if (name === "topology_and_stale") {
    const firstDetails = { screens: [primary, secondary], currentScreen: primary };
    const ctx = install({ details: firstDetails, permissionState: "granted" });
    await flush();
    const initial = stateSnapshot(ctx.notes, ctx.win);
    const staleGeneration = ctx.notes.screenAccessGeneration;
    ctx.notes.clearScreenDetails();
    ctx.notes.cacheScreenDetails(firstDetails, staleGeneration);
    const stale = stateSnapshot(ctx.notes, ctx.win);
    const staleTarget = ctx.notes.targetScreen;
    const newSecondary = { left: 1440, top: 0, width: 1280, height: 720, availLeft: 1440, availTop: 0, availWidth: 1280, availHeight: 720 };
    ctx.notes.cacheScreenDetails({ screens: [primary, newSecondary], currentScreen: primary }, ctx.notes.screenAccessGeneration);
    firstDetails.dispatch && firstDetails.dispatch("screenschange");
    return { initial, stale, staleTarget, targetLeft: ctx.notes.targetScreen.left, opens: ctx.win.__opens.length };
  }
  if (name === "topology_events") {
    const details = Object.assign(makeEventTarget(), { screens: [primary, secondary], currentScreen: primary });
    const ctx = install({ details, permissionState: "granted" });
    await flush();
    const initial = stateSnapshot(ctx.notes, ctx.win);
    details.screens = [primary];
    details.dispatch("screenschange");
    const afterScreensChange = stateSnapshot(ctx.notes, ctx.win);
    const rightSecondary = { left: 1440, top: 0, width: 1280, height: 720, availLeft: 1440, availTop: 0, availWidth: 1280, availHeight: 720 };
    details.screens = [primary, rightSecondary];
    details.currentScreen = primary;
    details.dispatch("currentscreenchange");
    return { initial, afterScreensChange, final: stateSnapshot(ctx.notes, ctx.win), targetLeft: ctx.notes.targetScreen.left, opens: ctx.win.__opens.length };
  }
  if (name === "bounds_equal_exclusion") {
    const sameBounds = { left: 0, top: 0, width: 1440, height: 900, availLeft: 0, availTop: 0, availWidth: 1440, availHeight: 900 };
    const ctx = install({ details: { screens: [sameBounds, secondary], currentScreen: primary }, permissionState: "granted" });
    await flush();
    return { targetLeft: ctx.notes.targetScreen?.left, state: ctx.notes.screenAccessState };
  }
  if (name === "placement_warning") {
    const ctx = install({ details: twoScreens, permissionState: "granted", popupScreenX: 20, popupScreenY: 0 });
    await flush();
    ctx.win.__activation = true;
    ctx.notes.openPopup();
    ctx.win.__activation = false;
    ctx.win.runTimers(350);
    return stateSnapshot(ctx.notes, ctx.win);
  }
  if (name === "placement_no_false_warning") {
    const ctx = install({ details: twoScreens, permissionState: "granted" });
    await flush();
    ctx.win.__activation = true;
    ctx.notes.openPopup();
    ctx.win.__activation = false;
    ctx.win.runTimers(350);
    return stateSnapshot(ctx.notes, ctx.win);
  }
  if (name === "placement_pair_fallback") {
    const ctx = install({ details: twoScreens, permissionState: "granted", popupScreenX: -1900, popupScreenLeft: 20, popupScreenTop: 0 });
    await flush();
    ctx.win.__activation = true;
    ctx.notes.openPopup();
    ctx.win.__activation = false;
    ctx.win.runTimers(350);
    return stateSnapshot(ctx.notes, ctx.win);
  }
  if (name === "placement_tolerance_boundary") {
    const inside = install({ details: twoScreens, permissionState: "granted", popupScreenX: 7, popupScreenY: 0 });
    await flush();
    inside.win.__activation = true;
    inside.notes.openPopup();
    inside.win.__activation = false;
    inside.win.runTimers(350);

    const outside = install({ details: twoScreens, permissionState: "granted", popupScreenX: 8, popupScreenY: 0 });
    await flush();
    outside.win.__activation = true;
    outside.notes.openPopup();
    outside.win.__activation = false;
    outside.win.runTimers(350);
    return { inside: stateSnapshot(inside.notes, inside.win), outside: stateSnapshot(outside.notes, outside.win) };
  }
  if (name === "blocked_popup") {
    const ctx = install({ details: twoScreens, permissionState: "granted", blockPopup: true });
    await flush();
    ctx.win.__activation = true;
    const result = ctx.notes.openPopup();
    ctx.win.__activation = false;
    return { result, drawerOpen: ctx.notes.isOpen, alerts: ctx.win.__alerts.length };
  }
  throw new Error(`Unknown scenario: ${name}`);
}

scenario(payload.scenario).then(
  (result) => process.stdout.write(JSON.stringify(result)),
  (error) => {
    process.stderr.write(error && error.stack || String(error));
    process.exit(1);
  },
);
"""


def run_node(path: Path, scenario: str) -> dict:
    payload = {
        "controller": extract_presenter_notes(path, DECKS[path]),
        "scenario": scenario,
    }
    completed = subprocess.run(
        ["node", "-e", NODE_HARNESS],
        cwd=ROOT,
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    return json.loads(completed.stdout)


@pytest.mark.parametrize("path", DECKS)
def test_harness_extracts_and_constructs_real_presenter_notes(path: Path) -> None:
    result = run_node(path, "construct")

    assert result == {
        "type": "function",
        "clickHandlers": 1,
        "keyHandlers": 1,
        "unloadHandlers": 1,
    }


@pytest.mark.parametrize("path", DECKS)
def test_complete_inline_scripts_compile(path: Path) -> None:
    scripts = inline_scripts(path)
    assert scripts
    for script in scripts:
        subprocess.run(["node", "-e", f"new Function({json.dumps(script)});"], check=True)


@pytest.mark.parametrize("path", DECKS)
def test_status_markup_has_single_exact_live_region_before_popout(path: Path) -> None:
    source = path.read_text(encoding="utf-8")
    parser = IdParser()
    parser.feed(source)

    assert len(parser.ids) == len(set(parser.ids))
    assert parser.notes_status_attrs == [
        {"class": "notes-status", "id": "notesStatus", "role": "status", "aria-live": "polite"}
    ]
    assert source.index('id="notesStatus"') < source.index('id="notesPopoutBtn"')
    assert ".notes-status" in source


@pytest.mark.parametrize("path", DECKS)
def test_state_unsupported_api_enters_resolved_fallback_without_opening(path: Path) -> None:
    result = run_node(path, "unsupported")

    assert result["state"] == "fallback"
    assert result["label"] == "Open speaker view"
    assert result["status"] == "Display access unavailable; speaker view will open here."
    assert result["statusVisible"] is True
    assert result["opens"] == 0


@pytest.mark.parametrize("scenario", ["permission_missing_with_api", "permission_throwing_with_api"])
@pytest.mark.parametrize("path", DECKS)
def test_state_undecided_permission_requires_user_activation(path: Path, scenario: str) -> None:
    result = run_node(path, scenario)

    assert result["state"] == "needs-permission"
    assert result["label"] == "↗ Pop out"
    assert result["opens"] == 0


@pytest.mark.parametrize("path", DECKS)
def test_popup_granted_warmup_opens_synchronously_on_secondary_with_negative_coordinates(path: Path) -> None:
    result = run_node(path, "granted_ready_open")

    assert result["state"] == "ready"
    assert result["resultIsPopup"] is True
    assert "popup=yes" in result["features"]
    assert "left=-1880" in result["features"]
    assert "top=40" in result["features"]
    assert result["moveCalls"] == [[-1880, 40], [-1880, 40]]
    assert result["resizeCalls"] == [[1040, 800], [1040, 800]]
    assert result["warning"] == ""


@pytest.mark.parametrize("path", DECKS)
def test_state_prompted_grant_reaches_ready_but_needs_fresh_activation(path: Path) -> None:
    result = run_node(path, "needs_permission_fresh_activation")

    assert result["afterFirst"]["state"] == "ready"
    assert result["afterFirst"]["status"] == "Display access ready. Activate again to open speaker view."
    assert result["afterFirst"]["opens"] == 0
    assert result["secondOpened"] is True
    assert result["opens"] == 1


@pytest.mark.parametrize("scenario,message", [
    ("needs_permission_denied", "Display access unavailable; speaker view will open here."),
    ("one_screen", "A second display is unavailable; speaker view will open here."),
])
@pytest.mark.parametrize("path", DECKS)
def test_state_prompted_fallback_requires_fresh_activation(path: Path, scenario: str, message: str) -> None:
    result = run_node(path, scenario)

    assert result["afterFirst"]["state"] == "fallback"
    assert result["afterFirst"]["status"] == message
    assert result["afterFirst"]["opens"] == 0
    assert result["secondOpened"] is True


@pytest.mark.parametrize("path", DECKS)
def test_popup_keyboard_n_uses_same_activation_safe_open_path(path: Path) -> None:
    result = run_node(path, "keyboard_n")

    assert result == {"opens": 1, "name": "SpeakerNotesWindow"} or result == {
        "opens": 1,
        "name": "ReleaseGateSpeakerNotes",
    }


@pytest.mark.parametrize("path", DECKS)
def test_state_permission_changes_remap_without_opening(path: Path) -> None:
    result = run_node(path, "permission_changes")

    assert result["denied"]["state"] == "fallback"
    assert result["denied"]["status"] == "Display access unavailable; speaker view will open here."
    assert result["prompt"]["state"] == "needs-permission"
    assert result["granted"]["state"] == "ready"
    assert result["granted"]["opens"] == 0


@pytest.mark.parametrize("path", DECKS)
def test_state_permission_grant_preserves_active_user_request(path: Path) -> None:
    result = run_node(path, "active_grant_preserves_request")

    assert result["callsBeforeResolve"] == 1
    assert result["snapshot"]["state"] == "ready"
    assert result["snapshot"]["opens"] == 0


@pytest.mark.parametrize("path", DECKS)
def test_state_granted_warmup_deduplicates_in_flight_screen_details(path: Path) -> None:
    result = run_node(path, "granted_warmup_deduplicates")

    assert result["callsBeforeResolve"] == 1
    assert result["snapshot"]["state"] == "ready"
    assert result["snapshot"]["detailsCalls"] == 1
    assert result["snapshot"]["opens"] == 0


@pytest.mark.parametrize("path", DECKS)
def test_state_stale_inflight_screen_details_does_not_capture_fresh_request(path: Path) -> None:
    result = run_node(path, "stale_inflight_does_not_capture_fresh_request")

    assert result["initialCalls"] == 1
    assert result["callsAfterFreshRequest"] == 2
    assert result["afterStale"]["state"] == "requesting"
    assert result["afterStale"]["opens"] == 0
    assert result["final"]["state"] == "ready"
    assert result["final"]["opens"] == 0


@pytest.mark.parametrize("path", DECKS)
def test_state_topology_invalidation_ignores_stale_generation_without_opening(path: Path) -> None:
    result = run_node(path, "topology_and_stale")

    assert result["initial"]["state"] == "ready"
    assert result["staleTarget"] is None
    assert result["targetLeft"] == 1440
    assert result["opens"] == 0


@pytest.mark.parametrize("path", DECKS)
def test_state_screen_topology_events_recompute_without_opening(path: Path) -> None:
    result = run_node(path, "topology_events")

    assert result["initial"]["state"] == "ready"
    assert result["afterScreensChange"]["state"] == "fallback"
    assert result["afterScreensChange"]["status"] == "A second display is unavailable; speaker view will open here."
    assert result["final"]["state"] == "ready"
    assert result["targetLeft"] == 1440
    assert result["opens"] == 0


@pytest.mark.parametrize("path", DECKS)
def test_state_current_screen_exclusion_uses_identity_or_equal_bounds(path: Path) -> None:
    result = run_node(path, "bounds_equal_exclusion")

    assert result == {"targetLeft": -1920, "state": "ready"}


@pytest.mark.parametrize("path", DECKS)
def test_popup_placement_warning_uses_finite_coordinates_and_tolerance(path: Path) -> None:
    result = run_node(path, "placement_warning")

    assert result["status"] == "The browser kept speaker view on this display. Move it to the other display manually."


@pytest.mark.parametrize("path", DECKS)
def test_popup_absent_popup_coordinates_do_not_false_warn(path: Path) -> None:
    result = run_node(path, "placement_no_false_warning")

    assert result["status"] != "The browser kept speaker view on this display. Move it to the other display manually."


@pytest.mark.parametrize("path", DECKS)
def test_popup_placement_uses_complete_coordinate_pairs(path: Path) -> None:
    result = run_node(path, "placement_pair_fallback")

    assert result["status"] == "The browser kept speaker view on this display. Move it to the other display manually."


@pytest.mark.parametrize("path", DECKS)
def test_popup_placement_uses_half_open_eight_pixel_tolerance(path: Path) -> None:
    result = run_node(path, "placement_tolerance_boundary")

    assert result["inside"]["status"] == ""
    assert result["outside"]["status"] == "The browser kept speaker view on this display. Move it to the other display manually."


@pytest.mark.parametrize("path", DECKS)
def test_popup_blocked_window_uses_existing_notes_drawer_fallback(path: Path) -> None:
    result = run_node(path, "blocked_popup")

    assert result == {"result": None, "drawerOpen": True, "alerts": 1}
