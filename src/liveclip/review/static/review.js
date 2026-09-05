"use strict";

const token = new URLSearchParams(window.location.search).get("token") || "";
const PLAY_START_TIMEOUT_MS = 3000;
const elements = {
  sourceName: document.querySelector("#sourceName"),
  candidateCount: document.querySelector("#candidateCount"),
  candidateList: document.querySelector("#candidateList"),
  emptyCandidates: document.querySelector("#emptyCandidates"),
  previewHeading: document.querySelector("#previewHeading"),
  reviewStatus: document.querySelector("#reviewStatus"),
  video: document.querySelector("#video"),
  videoError: document.querySelector("#videoError"),
  currentTime: document.querySelector("#currentTime"),
  clipDuration: document.querySelector("#clipDuration"),
  startNumber: document.querySelector("#startNumber"),
  endNumber: document.querySelector("#endNumber"),
  startSlider: document.querySelector("#startSlider"),
  endSlider: document.querySelector("#endSlider"),
  rangeError: document.querySelector("#rangeError"),
  resetRange: document.querySelector("#resetRange"),
  previewRange: document.querySelector("#previewRange"),
  confirmExport: document.querySelector("#confirmExport"),
  exportButton: document.querySelector("#exportButton"),
  exportMessage: document.querySelector("#exportMessage"),
};

const state = {
  session: null,
  selected: null,
  startMs: 0,
  endMs: 0,
  exporting: false,
  proxyRequested: false,
  proxyReady: false,
  usingProxy: false,
  proxyFailed: false,
  proxyPlaybackFailed: false,
  proxyPromise: null,
  proxyPlayRequested: false,
  rangePreviewActive: false,
  pendingStartMs: null,
};

function localUrl(path) {
  const url = new URL(path, window.location.origin);
  url.searchParams.set("token", token);
  return url.toString();
}

function formatClock(milliseconds) {
  const safe = Math.max(0, Math.round(milliseconds));
  const minutes = Math.floor(safe / 60000);
  const seconds = Math.floor((safe % 60000) / 1000);
  const millis = safe % 1000;
  return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}.${String(millis).padStart(3, "0")}`;
}

function seconds(milliseconds) {
  return (milliseconds / 1000).toFixed(3);
}

function showPreviewMessage(message, kind) {
  elements.videoError.textContent = message;
  elements.videoError.dataset.kind = kind;
  elements.videoError.hidden = false;
}

async function playSelectedRange() {
  state.rangePreviewActive = false;
  state.pendingStartMs = state.startMs;
  elements.video.pause();
  elements.video.currentTime = state.startMs / 1000;
  let timeoutId;
  const timeout = new Promise((_resolve, reject) => {
    timeoutId = window.setTimeout(
      () => reject(new Error("本地视频播放启动超时。")),
      PLAY_START_TIMEOUT_MS,
    );
  });
  try {
    await Promise.race([elements.video.play(), timeout]);
    state.rangePreviewActive = true;
  } finally {
    window.clearTimeout(timeoutId);
  }
}

function showProxyReady() {
  showPreviewMessage(
    "兼容预览已准备好。正式导出仍使用原视频，不影响成片画质。",
    "ready",
  );
}

function showProxyPlaybackFailure() {
  state.rangePreviewActive = false;
  state.proxyPlaybackFailed = true;
  state.proxyPlayRequested = false;
  showPreviewMessage(
    "兼容预览播放失败，请暂停后重试。请不要勾选确认导出。",
    "failed",
  );
}

async function playReadyProxyRange() {
  try {
    await playSelectedRange();
    state.proxyPlaybackFailed = false;
    showProxyReady();
  } catch (_error) {
    state.pendingStartMs = null;
    showProxyPlaybackFailure();
  }
}

function isPreviewMediaSource() {
  try {
    return new URL(elements.video.currentSrc || elements.video.src).pathname === "/media/preview";
  } catch (_error) {
    return false;
  }
}

async function requestPreviewProxy(playWhenReady) {
  if (state.usingProxy || state.proxyReady) return;
  if (state.proxyFailed) return;
  if (playWhenReady) state.proxyPlayRequested = true;
  if (state.proxyPromise) return state.proxyPromise;

  state.proxyRequested = true;
  showPreviewMessage(
    "当前视频编码浏览器不支持，正在生成兼容预览…首次需要一点时间，后续会直接复用。",
    "working",
  );
  state.proxyPromise = (async () => {
    const response = await fetch(localUrl("/api/preview-proxy"), {
      method: "POST",
      credentials: "omit",
      cache: "no-store",
    });
    const payload = await response.json();
    if (!response.ok || payload.status !== "ready") {
      throw new Error(payload.error || "兼容预览生成失败。");
    }
    state.proxyReady = true;
    state.proxyFailed = false;
    state.proxyPlaybackFailed = false;
    showProxyReady();
    elements.video.src = localUrl("/media/preview");
    state.usingProxy = true;
    elements.video.load();
  })().catch((_error) => {
    state.proxyFailed = true;
    state.proxyPlayRequested = false;
    showPreviewMessage(
      "兼容预览生成失败，暂时无法人工预览。请不要勾选确认导出。",
      "failed",
    );
  }).finally(() => {
    state.proxyPromise = null;
  });
  return state.proxyPromise;
}

function controlsEnabled(enabled) {
  const controls = [
    elements.startNumber,
    elements.endNumber,
    elements.startSlider,
    elements.endSlider,
    elements.resetRange,
    elements.previewRange,
    elements.confirmExport,
    ...document.querySelectorAll(".nudge-row button"),
  ];
  controls.forEach((control) => { control.disabled = !enabled; });
}

function validRange() {
  if (!state.session || !state.selected) return false;
  const duration = state.endMs - state.startMs;
  return state.startMs >= 0 &&
    state.endMs <= state.session.video.duration_ms &&
    state.endMs > state.startMs &&
    duration >= 1000 && duration <= 180000;
}

function updateExportGate() {
  const completed = Boolean(state.session && state.session.export_completed);
  elements.exportButton.disabled = completed || state.exporting || !validRange() || !elements.confirmExport.checked;
}

function updateControls() {
  if (!state.session || !state.selected) return;
  elements.startNumber.value = seconds(state.startMs);
  elements.endNumber.value = seconds(state.endMs);
  elements.startSlider.value = seconds(state.startMs);
  elements.endSlider.value = seconds(state.endMs);
  elements.clipDuration.textContent = `${seconds(state.endMs - state.startMs)} 秒`;
  elements.rangeError.textContent = validRange() ? "" : "时间范围必须在视频内，且片段时长为 1—180 秒。";
  updateExportGate();
}

function setRange(startMs, endMs) {
  elements.confirmExport.checked = false;
  state.startMs = Math.round(startMs);
  state.endMs = Math.round(endMs);
  updateControls();
}

function exportDetailsMessage(exported, prefix) {
  if (!exported) return "";
  const videoSubtitle = exported.subtitles_burned_in
    ? "视频字幕：已烧录"
    : "本片段没有可烧录字幕";
  return `${prefix} MP4：${exported.video_file_name}；SRT：${exported.subtitle_file_name}；` +
    `最终范围：${formatClock(exported.final_start_ms)} – ${formatClock(exported.final_end_ms)}；` +
    `实际时长：${seconds(exported.duration_ms)} 秒；${videoSubtitle}；` +
    `独立字幕：已生成；输出文件夹：${exported.output_folder_name}。`;
}

function makeText(className, text) {
  const node = document.createElement("p");
  node.className = className;
  node.textContent = text;
  return node;
}

function renderCandidates() {
  elements.candidateList.replaceChildren();
  const candidates = state.session.candidates;
  elements.candidateCount.textContent = String(candidates.length);
  elements.emptyCandidates.hidden = candidates.length !== 0;
  candidates.forEach((candidate) => {
    const item = document.createElement("li");
    const button = document.createElement("button");
    button.type = "button";
    button.className = "candidate-card";
    button.dataset.candidateId = candidate.id;
    const top = document.createElement("div");
    top.className = "candidate-top";
    const rank = document.createElement("span");
    rank.textContent = `#${candidate.rank}`;
    const score = document.createElement("span");
    score.textContent = `${candidate.total_score} 分`;
    top.append(rank, score);
    button.append(
      top,
      makeText("candidate-title", candidate.title),
      makeText("candidate-meta", `时长 ${seconds(candidate.duration_ms)} 秒`),
      makeText("candidate-reason", `推荐理由：${candidate.reason}`),
      makeText("candidate-risk", `风险提示：${candidate.risk}`),
      makeText("candidate-status", `审核状态：${candidate.review_status}`),
    );
    button.addEventListener("click", () => selectCandidate(candidate.id));
    item.append(button);
    elements.candidateList.append(item);
  });
}

function selectCandidate(candidateId) {
  state.selected = state.session.candidates.find((candidate) => candidate.id === candidateId) || null;
  document.querySelectorAll(".candidate-card").forEach((card) => {
    card.classList.toggle("selected", card.dataset.candidateId === candidateId);
  });
  if (!state.selected) return;
  elements.previewHeading.textContent = state.selected.title;
  elements.reviewStatus.textContent = state.selected.review_status;
  elements.confirmExport.checked = false;
  controlsEnabled(!state.session.export_completed);
  state.rangePreviewActive = false;
  elements.video.pause();
  setRange(state.selected.original_start_ms, state.selected.original_end_ms);
  state.pendingStartMs = state.startMs;
  elements.video.currentTime = state.startMs / 1000;
  elements.currentTime.textContent = formatClock(state.startMs);
  elements.exportMessage.textContent = state.session.completed_export
    ? exportDetailsMessage(state.session.completed_export, "此前已导出。")
    : "";
}

async function loadSession() {
  const firstLoad = state.session === null;
  const response = await fetch(localUrl("/api/session"), {cache: "no-store", credentials: "omit"});
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || "无法读取审核数据。");
  state.session = payload;
  elements.sourceName.textContent = payload.video.file_name;
  const maximum = seconds(payload.video.duration_ms);
  [elements.startSlider, elements.endSlider, elements.startNumber, elements.endNumber].forEach((input) => {
    input.max = maximum;
  });
  if (firstLoad) {
    elements.video.src = localUrl("/media");
  }
  renderCandidates();
  if (payload.candidates.length) selectCandidate(payload.candidates[0].id);
  else controlsEnabled(false);
}

function readNumber(target) {
  const value = Number(target.value);
  return Number.isFinite(value) ? Math.round(value * 1000) : null;
}

elements.startSlider.addEventListener("input", () => {
  const value = readNumber(elements.startSlider);
  if (value !== null) setRange(value, state.endMs);
});
elements.endSlider.addEventListener("input", () => {
  const value = readNumber(elements.endSlider);
  if (value !== null) setRange(state.startMs, value);
});
elements.startNumber.addEventListener("input", () => {
  const value = readNumber(elements.startNumber);
  if (value !== null) setRange(value, state.endMs);
});
elements.endNumber.addEventListener("input", () => {
  const value = readNumber(elements.endNumber);
  if (value !== null) setRange(state.startMs, value);
});

document.querySelectorAll(".nudge-row button").forEach((button) => {
  button.addEventListener("click", () => {
    const target = button.parentElement.dataset.target;
    const delta = Math.round(Number(button.dataset.delta) * 1000);
    if (target === "start") setRange(state.startMs + delta, state.endMs);
    else setRange(state.startMs, state.endMs + delta);
  });
});

elements.resetRange.addEventListener("click", () => {
  if (!state.selected) return;
  setRange(state.selected.original_start_ms, state.selected.original_end_ms);
});

elements.previewRange.addEventListener("click", async () => {
  if (!validRange()) return;
  if (state.usingProxy) {
    await playReadyProxyRange();
    return;
  }
  try {
    await playSelectedRange();
  } catch (_error) {
    await requestPreviewProxy(true);
  }
});

elements.video.addEventListener("timeupdate", () => {
  const currentMs = elements.video.currentTime * 1000;
  if (state.pendingStartMs !== null) {
    if (Math.abs(currentMs - state.pendingStartMs) > 250) {
      elements.video.currentTime = state.pendingStartMs / 1000;
      elements.currentTime.textContent = formatClock(state.pendingStartMs);
      return;
    }
    state.pendingStartMs = null;
  }
  elements.currentTime.textContent = formatClock(currentMs);
  if (
    state.rangePreviewActive &&
    state.selected &&
    !elements.video.seeking &&
    currentMs >= state.endMs
  ) {
    state.rangePreviewActive = false;
    elements.video.pause();
  }
});
elements.video.addEventListener("loadedmetadata", async () => {
  if (!state.usingProxy) {
    if (elements.video.videoWidth === 0 || elements.video.videoHeight === 0) {
      await requestPreviewProxy(false);
    }
    return;
  }
  if (!isPreviewMediaSource()) return;
  elements.video.currentTime = state.startMs / 1000;
  if (!state.proxyPlayRequested) return;
  state.proxyPlayRequested = false;
  await playReadyProxyRange();
});
elements.video.addEventListener("play", () => {
  if (state.usingProxy) return;
  window.setTimeout(() => {
    if (
      !state.usingProxy &&
      (
        elements.video.readyState === 0 ||
        elements.video.videoWidth === 0 ||
        elements.video.videoHeight === 0
      )
    ) {
      requestPreviewProxy(false);
    }
  }, PLAY_START_TIMEOUT_MS);
});
elements.video.addEventListener("error", () => {
  if (state.usingProxy || isPreviewMediaSource()) {
    showProxyPlaybackFailure();
    return;
  }
  requestPreviewProxy(false);
});
elements.confirmExport.addEventListener("change", updateExportGate);

elements.exportButton.addEventListener("click", async () => {
  if (state.exporting || !state.selected || !validRange() || !elements.confirmExport.checked) return;
  state.exporting = true;
  elements.exportMessage.textContent = "正在使用 FFmpeg 导出，请勿重复点击…";
  updateExportGate();
  try {
    const response = await fetch(localUrl("/api/export"), {
      method: "POST",
      credentials: "omit",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({
        candidate_id: state.selected.id,
        start_ms: state.startMs,
        end_ms: state.endMs,
        confirmed: true,
      }),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || "导出失败。");
    await loadSession();
    elements.exportMessage.textContent = exportDetailsMessage(payload, payload.message);
  } catch (error) {
    elements.exportMessage.textContent = error.message || "导出失败。";
  } finally {
    state.exporting = false;
    updateExportGate();
  }
});

let shutdownRequested = false;
async function sendHeartbeat() {
  try {
    await fetch(localUrl("/api/heartbeat"), {
      method: "POST",
      credentials: "omit",
      cache: "no-store",
    });
  } catch (_error) {
    // The local service may already be stopping; no remote fallback is allowed.
  }
}
const heartbeatTimer = window.setInterval(sendHeartbeat, 2000);
sendHeartbeat();

function requestShutdown() {
  if (shutdownRequested) return;
  shutdownRequested = true;
  window.clearInterval(heartbeatTimer);
  fetch(localUrl("/api/shutdown"), {
    method: "POST",
    credentials: "omit",
    keepalive: true,
  }).catch(() => {});
}
window.addEventListener("pagehide", requestShutdown);
window.addEventListener("beforeunload", requestShutdown);

loadSession().catch((error) => {
  elements.exportMessage.textContent = error.message || "审核页面初始化失败。";
  controlsEnabled(false);
});
