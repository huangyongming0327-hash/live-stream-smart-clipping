"use strict";

const fs = require("fs");
const path = require("path");
const vm = require("vm");

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return {promise, resolve, reject};
}

class FakeElement {
  constructor(id = "") {
    this.id = id;
    this.listeners = {};
    this.children = [];
    this.dataset = {};
    this.classList = {toggle() {}};
    this.textContent = "";
    this.hidden = true;
    this.disabled = false;
    this.checked = false;
    this.value = "";
    this.currentTime = 0;
    this.currentSrc = "";
    this.src = "";
    this.readyState = 4;
    this.videoWidth = 1280;
    this.videoHeight = 720;
    this.seeking = false;
    this.paused = true;
    this.pauseCount = 0;
    this.playQueue = [];
  }
  addEventListener(name, callback) { this.listeners[name] = callback; }
  async emit(name) {
    if (this.listeners[name]) return await this.listeners[name]({target: this});
  }
  append(...children) { this.children.push(...children); }
  replaceChildren() { this.children = []; }
  pause() { this.paused = true; this.pauseCount += 1; }
  play() {
    const next = this.playQueue.shift();
    const promise = next ? next.promise : Promise.resolve();
    promise.then(() => { this.paused = false; }, () => {});
    return promise;
  }
  load() {
    this.currentSrc = this.src;
    Promise.resolve().then(() => this.emit("loadedmetadata"));
  }
}

const session = {
  video: {file_name: "source.mp4", duration_ms: 600000},
  export_completed: false,
  completed_export: null,
  candidates: [
    {id: "A", rank: 1, total_score: 90, title: "A", duration_ms: 24890,
     reason: "r", risk: "", review_status: "pending",
     original_start_ms: 575110, original_end_ms: 600000},
    {id: "B", rank: 2, total_score: 80, title: "B", duration_ms: 35414,
     reason: "r", risk: "", review_status: "pending",
     original_start_ms: 329702, original_end_ms: 365116},
  ],
};

async function flush() {
  await new Promise((resolve) => setImmediate(resolve));
}

async function createRuntime(sourcePath) {
  const ids = [
    "sourceName", "candidateCount", "candidateList", "emptyCandidates",
    "previewHeading", "reviewStatus", "video", "videoError", "currentTime",
    "clipDuration", "startNumber", "endNumber", "startSlider", "endSlider",
    "rangeError", "resetRange", "previewRange", "confirmExport", "exportButton",
    "exportMessage",
  ];
  const byId = Object.fromEntries(ids.map((id) => [id, new FakeElement(id)]));
  const created = [];
  const timers = [];
  let timerId = 0;
  const context = {
    URL, URLSearchParams, Promise, Math, JSON,
    proxyPosts: 0,
    window: {
      location: {search: "?token=0123456789abcdef", origin: "http://127.0.0.1:12345"},
      setTimeout(callback) {
        const item = {id: ++timerId, callback, cancelled: false};
        timers.push(item);
        return item.id;
      },
      clearTimeout(id) {
        const item = timers.find((candidate) => candidate.id === id);
        if (item) item.cancelled = true;
      },
      setInterval() { return 1; },
      clearInterval() {},
      addEventListener() {},
    },
    document: {
      querySelector(selector) { return byId[selector.slice(1)]; },
      querySelectorAll(selector) {
        if (selector === ".candidate-card") {
          return created.filter((element) => element.className === "candidate-card");
        }
        return [];
      },
      createElement() {
        const element = new FakeElement();
        created.push(element);
        return element;
      },
    },
    fetch: async (url) => {
      const path = new URL(url).pathname;
      if (path === "/api/session") return {ok: true, json: async () => session};
      if (path === "/api/preview-proxy") {
        context.proxyPosts += 1;
        return {ok: true, json: async () => ({status: "ready", cached: false})};
      }
      return {ok: true, json: async () => ({ok: true})};
    },
  };
  vm.createContext(context);
  vm.runInContext(fs.readFileSync(sourcePath, "utf8"), context);
  await flush();
  await vm.runInContext("requestPreviewProxy(false)", context);
  await flush();
  return {
    context,
    video: byId.video,
    fireTimeout() {
      const item = timers.find((candidate) => !candidate.cancelled);
      if (!item) throw new Error("no active timeout");
      item.callback();
    },
    eval(code) { return vm.runInContext(code, context); },
  };
}

async function begin(runtime, candidateId, play) {
  if (candidateId) runtime.eval(`selectCandidate(${JSON.stringify(candidateId)})`);
  runtime.video.playQueue.push(play);
  const pending = runtime.eval("elements.previewRange.emit('click')");
  await flush();
  return {pending};
}

async function timeoutThenLate(sourcePath, rejectLate) {
  const runtime = await createRuntime(sourcePath);
  const old = deferred();
  const {pending} = await begin(runtime, "B", old);
  runtime.fireTimeout();
  await pending;
  if (rejectLate) old.reject(new Error("late rejection"));
  else old.resolve();
  await flush();
  return runtime.eval(`JSON.stringify({
    paused: elements.video.paused,
    active: state.rangePreviewActive,
    pendingStartMs: state.pendingStartMs,
    proxyPosts,
    message: elements.videoError.textContent
  })`);
}

async function oldLateAfterNew(sourcePath, switchCandidate) {
  const runtime = await createRuntime(sourcePath);
  const old = deferred();
  const {pending: oldPending} = await begin(runtime, "A", old);
  runtime.fireTimeout();
  await oldPending;
  const current = deferred();
  const {pending: currentPending} = await begin(
    runtime, switchCandidate ? "B" : null, current
  );
  current.resolve();
  await currentPending;
  old.resolve();
  await flush();
  const start = switchCandidate ? 329.802 : 575.210;
  runtime.eval(`elements.video.currentTime = ${start}`);
  await runtime.eval("elements.video.emit('timeupdate')");
  const end = switchCandidate ? 365.116 : 600.0;
  runtime.eval(`elements.video.currentTime = ${end}`);
  await runtime.eval("elements.video.emit('timeupdate')");
  return runtime.eval(`JSON.stringify({
    selected: state.selected.id,
    paused: elements.video.paused,
    active: state.rangePreviewActive,
    proxyPosts,
    message: elements.videoError.textContent
  })`);
}

async function consecutive(sourcePath) {
  const runtime = await createRuntime(sourcePath);
  runtime.eval("selectCandidate('B')");
  const old = deferred();
  const current = deferred();
  runtime.video.playQueue.push(old, current);
  const first = runtime.eval("elements.previewRange.emit('click')");
  await flush();
  const second = runtime.eval("elements.previewRange.emit('click')");
  await flush();
  current.resolve();
  await second;
  old.resolve();
  await first;
  await flush();
  runtime.eval("selectCandidate('A')");
  runtime.eval("selectCandidate('B')");
  return runtime.eval(`JSON.stringify({
    selected: state.selected.id,
    paused: elements.video.paused,
    active: state.rangePreviewActive,
    proxyPosts,
    message: elements.videoError.textContent
  })`);
}

(async () => {
  const sourcePath = process.argv[2] || path.join(
    __dirname,
    "..",
    "src",
    "liveclip",
    "review",
    "static",
    "review.js",
  );
  const results = {
    lateSuccess: JSON.parse(await timeoutThenLate(sourcePath, false)),
    lateFailure: JSON.parse(await timeoutThenLate(sourcePath, true)),
    oldLateAfterNew: JSON.parse(await oldLateAfterNew(sourcePath, false)),
    switchDuringTimeout: JSON.parse(await oldLateAfterNew(sourcePath, true)),
    consecutive: JSON.parse(await consecutive(sourcePath)),
  };
  process.stdout.write(JSON.stringify(results));
})().catch((error) => { console.error(error); process.exit(1); });
