const {
  app,
  BrowserWindow,
  clipboard,
  ipcMain,
  Menu,
  nativeImage,
  screen,
  shell,
  Tray,
} = require("electron");
const { spawn } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");
const readline = require("node:readline");

const {
  DEFAULT_USER_DATA,
  buildPersonalizationProfile,
  deriveStats,
  recordTranscript,
  sanitizeUserData,
} = require("./product-data");
const { DEFAULT_SETTINGS, sanitizeSettings } = require("./settings");
const {
  backendTimeoutMs,
  controlRejection,
  restartDelayMs,
} = require("./runtime-health");

let mainWindow;
let overlayWindow;
let tray;
let backendProcess;
let forceKillTimer;
let isQuitting = false;
let hideOverlayTimer;
let modelSetupProcess;
let draftSaveTimer;
let backendRestartTimer;
let backendWatchdogTimer;
let backendRecoveryInFlight = false;
let backendRestartAttempts = 0;
let backendStateEnteredAt = Date.now();
let lastRecordingDurationMs = 0;
const lastRendererRecoveryAt = { main: 0, overlay: 0 };

const MAX_AUTOMATIC_RESTARTS = 3;
const RENDERER_RECOVERY_COOLDOWN_MS = 30_000;

const state = {
  backend: "stopped",
  formatter: "warming",
  message: "Starting Parrot…",
  partial: "",
  transcript: "",
  handsFree: false,
  recordingStartedAt: null,
  log: [],
  settings: { ...DEFAULT_SETTINGS },
  userData: { ...DEFAULT_USER_DATA },
};

function isUiOnly() {
  return (
    process.env.PARROT_SKIP_BACKEND === "1" ||
    process.argv.includes("--ui-only")
  );
}

function settingsPath() {
  return path.join(app.getPath("userData"), "settings.json");
}

function userDataPath() {
  return path.join(app.getPath("userData"), "dictation-data.json");
}

function personalizationPath() {
  return path.join(app.getPath("userData"), "personalization.json");
}

function runtimeHealthPath() {
  return path.join(app.getPath("userData"), "runtime-health.log");
}

function recordRuntimeHealth(event, details = {}) {
  try {
    const target = runtimeHealthPath();
    if (fs.existsSync(target) && fs.statSync(target).size > 256_000) {
      fs.copyFileSync(target, `${target}.previous`);
      fs.truncateSync(target, 0);
    }
    fs.appendFileSync(
      target,
      `${JSON.stringify({ at: new Date().toISOString(), event, ...details })}\n`,
      "utf8",
    );
  } catch {
    // Diagnostics must never become another reason for Parrot to stop.
  }
}

function loadSettings() {
  try {
    const saved = JSON.parse(fs.readFileSync(settingsPath(), "utf8"));
    state.settings = sanitizeSettings({ ...DEFAULT_SETTINGS, ...saved });
  } catch {
    state.settings = { ...DEFAULT_SETTINGS };
  }
  applyLoginSetting();
}

function loadUserData() {
  try {
    const saved = JSON.parse(fs.readFileSync(userDataPath(), "utf8"));
    state.userData = sanitizeUserData(saved);
  } catch {
    state.userData = sanitizeUserData(DEFAULT_USER_DATA);
  }
  const latest = state.userData.history[0];
  state.transcript = latest?.text || state.userData.recoveryDraft || "";
  state.partial = state.userData.recoveryDraft || state.transcript;
  writePersonalizationProfile();
}

function writeJson(target, value) {
  fs.mkdirSync(path.dirname(target), { recursive: true });
  fs.writeFileSync(target, JSON.stringify(value, null, 2), "utf8");
}

function saveSettings(nextSettings) {
  state.settings = sanitizeSettings({ ...state.settings, ...nextSettings });
  writeJson(settingsPath(), state.settings);
  writePersonalizationProfile();
  applyLoginSetting();
  broadcastState();
  rebuildTrayMenu();
  return state.settings;
}

function saveUserData() {
  state.userData = sanitizeUserData(state.userData);
  writeJson(userDataPath(), state.userData);
  writePersonalizationProfile();
}

function saveRecoveryDraft(text) {
  state.userData.recoveryDraft = String(text || "").slice(0, 20000);
  clearTimeout(draftSaveTimer);
  draftSaveTimer = setTimeout(() => {
    draftSaveTimer = undefined;
    saveUserData();
  }, 750);
}

function writePersonalizationProfile() {
  writeJson(
    personalizationPath(),
    buildPersonalizationProfile(state.userData, state.settings),
  );
}

function applyLoginSetting() {
  if (!app.isPackaged || isUiOnly()) return;
  app.setLoginItemSettings({
    openAtLogin: state.settings.launchAtLogin,
    path: process.execPath,
    args: ["--background"],
  });
}

function createTrayIcon() {
  const image = nativeImage.createFromPath(
    path.join(__dirname, "assets", "brand", "parrot-tray-icon-16.png"),
  );
  image.addRepresentation({
    scaleFactor: 2,
    buffer: fs.readFileSync(
      path.join(__dirname, "assets", "brand", "parrot-tray-icon-32.png"),
    ),
  });
  return image;
}

function createMainWindow() {
  mainWindow = new BrowserWindow({
    width: 1080,
    height: 760,
    minWidth: 760,
    minHeight: 600,
    show: false,
    backgroundColor: "#edf3ee",
    autoHideMenuBar: true,
    title: "Parrot",
    titleBarStyle: "hidden",
    titleBarOverlay: {
      color: "#edf3ee",
      symbolColor: "#193b33",
      height: 48,
    },
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });

  mainWindow.loadFile(path.join(__dirname, "index.html"));
  installWindowRecovery(mainWindow, "main");
  mainWindow.on("close", (event) => {
    if (!isQuitting) {
      event.preventDefault();
      mainWindow.hide();
    }
  });
  mainWindow.on("closed", () => {
    mainWindow = undefined;
  });
  mainWindow.once("ready-to-show", () => {
    if (!process.argv.includes("--background")) mainWindow.show();
  });
}

function createOverlayWindow() {
  overlayWindow = new BrowserWindow({
    width: 420,
    height: 66,
    show: false,
    frame: false,
    transparent: true,
    alwaysOnTop: true,
    skipTaskbar: true,
    focusable: false,
    resizable: false,
    hasShadow: false,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });

  overlayWindow.setAlwaysOnTop(true, "floating");
  overlayWindow.setIgnoreMouseEvents(true);
  overlayWindow.loadFile(path.join(__dirname, "overlay.html"));
  installWindowRecovery(overlayWindow, "overlay");
  overlayWindow.on("closed", () => {
    overlayWindow = undefined;
  });
}

function installWindowRecovery(window, label) {
  const recover = (reason) => {
    const now = Date.now();
    if (
      window.isDestroyed() ||
      now - lastRendererRecoveryAt[label] < RENDERER_RECOVERY_COOLDOWN_MS
    ) {
      return;
    }
    lastRendererRecoveryAt[label] = now;
    recordRuntimeHealth("renderer-recovery", { label, reason });
    addLog(`${label === "main" ? "Parrot's window" : "The status bar"} recovered.`);
    try {
      if (!window.webContents.isDestroyed()) {
        window.webContents.reloadIgnoringCache();
      } else if (label === "main") {
        window.destroy();
        mainWindow = undefined;
        createMainWindow();
      } else {
        window.destroy();
        overlayWindow = undefined;
        createOverlayWindow();
      }
      if (label === "main") {
        showMainWindow();
      }
    } catch (error) {
      recordRuntimeHealth("renderer-recovery-failed", {
        label,
        reason: error.message,
      });
    }
  };
  window.on("unresponsive", () => recover("unresponsive"));
  window.webContents.on("render-process-gone", (_event, details) =>
    recover(`render-process-gone:${details.reason}`),
  );
  window.webContents.on("did-fail-load", (_event, code) => {
    if (code !== -3) recover(`did-fail-load:${code}`);
  });
}

function positionOverlay() {
  if (!overlayWindow) return;
  const display = screen.getDisplayNearestPoint(screen.getCursorScreenPoint());
  const { x, y, width, height } = display.workArea;
  const [overlayWidth, overlayHeight] = overlayWindow.getSize();
  overlayWindow.setPosition(
    Math.round(x + (width - overlayWidth) / 2),
    Math.round(y + height - overlayHeight - 28),
    false,
  );
}

function createTray() {
  tray = new Tray(createTrayIcon());
  tray.on("click", showMainWindow);
  rebuildTrayMenu();
}

function menuText(value, maxLength = 72) {
  const compact = String(value || "")
    .replace(/\s+/g, " ")
    .trim();
  if (!compact) return "";
  return compact.length > maxLength
    ? `${compact.slice(0, maxLength - 1)}…`
    : compact;
}

function menuAccelerator(shortcut) {
  return String(shortcut || "").startsWith("Mouse") ? undefined : shortcut;
}

function rebuildTrayMenu() {
  if (!tray) return;
  const active = !["stopped", "error"].includes(state.backend);
  const recording = state.backend === "recording";
  const transcript = menuText(state.transcript || state.partial, 64);
  tray.setToolTip(
    menuText(
      `Parrot — ${state.message || state.backend}${
        transcript ? `\nLatest: ${transcript}` : ""
      }`,
      120,
    ),
  );
  tray.setContextMenu(
    Menu.buildFromTemplate([
      {
        label: recording
          ? state.handsFree
            ? "Listening hands-free"
            : "Listening"
          : active
            ? "Parrot is ready"
            : "Parrot is stopped",
        enabled: false,
      },
      ...(transcript ? [{ label: `Latest: ${transcript}`, enabled: false }] : []),
      { type: "separator" },
      { label: "Open Parrot", click: showMainWindow },
      {
        label: state.handsFree ? "Finish hands-free dictation" : "Start hands-free",
        accelerator: menuAccelerator(state.settings.handsFreeShortcut),
        click: () => sendBackendControl({ type: "toggle-hands-free" }),
      },
      {
        label: "Cancel current dictation",
        accelerator: menuAccelerator(state.settings.cancelShortcut),
        enabled: recording,
        click: () => sendBackendControl({ type: "cancel" }),
      },
      {
        label: "Paste previous dictation",
        accelerator: menuAccelerator(state.settings.pasteLastShortcut),
        enabled: Boolean(state.transcript),
        click: () => sendBackendControl({ type: "paste-last" }),
      },
      { type: "separator" },
      {
        label: active ? "Restart dictation engine" : "Start dictation engine",
        click: restartBackend,
      },
      {
        label: "Launch at sign in",
        type: "checkbox",
        checked: state.settings.launchAtLogin,
        click: (item) => saveSettings({ launchAtLogin: item.checked }),
      },
      { type: "separator" },
      { label: "Quit Parrot", click: quitApplication },
    ]),
  );
}

function showMainWindow() {
  if (
    !mainWindow ||
    mainWindow.isDestroyed() ||
    mainWindow.webContents.isDestroyed()
  ) {
    if (mainWindow && !mainWindow.isDestroyed()) mainWindow.destroy();
    createMainWindow();
  }
  if (mainWindow.isMinimized()) mainWindow.restore();
  mainWindow.show();
  mainWindow.focus();
}

function backendRoot() {
  return app.isPackaged
    ? path.join(process.resourcesPath, "backend")
    : path.resolve(__dirname, "..");
}

function backendCommand() {
  const root = backendRoot();
  const executable = path.join(root, "project-parrot.exe");
  const releaseExecutable = path.join(
    root,
    "target",
    "release",
    "project-parrot.exe",
  );

  if (app.isPackaged) return { command: executable, prefixArgs: [] };
  if (fs.existsSync(releaseExecutable)) {
    return { command: releaseExecutable, prefixArgs: [] };
  }
  return {
    command: "cargo",
    prefixArgs: ["run", "--quiet", "--release", "--"],
  };
}

function effectiveThreads() {
  if (state.settings.sttThreads > 0) return state.settings.sttThreads;
  return Math.max(1, require("node:os").availableParallelism() - 2);
}

function startBackend() {
  if (backendProcess || isUiOnly()) {
    if (isUiOnly()) {
      updateState("ready", "Preview mode — dictation engine is not running.");
    }
    return;
  }

  writePersonalizationProfile();
  const { command, prefixArgs } = backendCommand();
  const sessionLimitSeconds = state.settings.longSessionMinutes * 60;
  const args = [
    ...prefixArgs,
    "--stt",
    state.settings.sttEngine,
    "--stt-threads",
    String(effectiveThreads()),
    "--ollama-model",
    state.settings.ollamaModel,
    "--ollama-keep-alive=-1m",
    "--update-interval",
    String(state.settings.updateInterval),
    "--live-window-seconds",
    String(state.settings.liveWindowSeconds),
    "--push-to-talk-shortcut",
    state.settings.pushToTalkShortcut,
    "--hands-free-shortcut",
    state.settings.handsFreeShortcut,
    "--cancel-shortcut",
    state.settings.cancelShortcut,
    "--paste-last-shortcut",
    state.settings.pasteLastShortcut,
    "--personalization-path",
    personalizationPath(),
    "--session-warning-seconds",
    String(Math.max(30, sessionLimitSeconds - 60)),
    "--session-limit-seconds",
    String(sessionLimitSeconds),
    "--control-stdin",
  ];

  state.formatter = "warming";
  addLog(`Starting ${state.settings.sttEngine} locally.`);
  updateState("starting", "Loading the local speech model…");

  try {
    backendProcess = spawn(command, args, {
      cwd: backendRoot(),
      windowsHide: true,
      stdio: ["pipe", "pipe", "pipe"],
    });
  } catch (error) {
    backendProcess = undefined;
    updateState("error", `Could not start the dictation engine: ${error.message}`);
    return;
  }

  const child = backendProcess;
  recordRuntimeHealth("backend-start", { pid: child.pid });
  const stdout = readline.createInterface({ input: child.stdout });
  const stderr = readline.createInterface({ input: child.stderr });

  stdout.on("line", handleBackendLine);
  stderr.on("line", (line) => {
    if (line.trim()) addLog(line.trim(), "error");
  });
  child.on("error", (error) => {
    if (backendProcess === child) {
      backendProcess = undefined;
      updateState("error", `Dictation engine failed: ${error.message}`);
      recordRuntimeHealth("backend-error", { code: error.code || "unknown" });
      scheduleBackendRestart();
    }
  });
  child.on("exit", (code, signal) => {
    stdout.close();
    stderr.close();
    if (backendProcess !== child) return;
    backendProcess = undefined;
    state.handsFree = false;
    state.recordingStartedAt = null;
    if (!isQuitting && state.backend !== "stopping") {
      updateState(
        "error",
        `Dictation engine stopped${
          code !== null ? ` (code ${code})` : signal ? ` (${signal})` : ""
        }.`,
      );
      recordRuntimeHealth("backend-exit", { code, signal, unexpected: true });
      scheduleBackendRestart();
    } else {
      updateState("stopped", "Dictation is stopped.");
      recordRuntimeHealth("backend-exit", { code, signal, unexpected: false });
    }
  });
}

function sendBackendControl(message) {
  if (isUiOnly()) {
    if (message.type === "toggle-hands-free") {
      state.handsFree = !state.handsFree;
      state.recordingStartedAt = state.handsFree ? Date.now() : null;
      if (state.handsFree) state.partial = "";
      updateState(
        state.handsFree ? "recording" : "ready",
        state.handsFree
          ? "Hands-free preview is active."
          : "Hands-free preview finished.",
      );
      if (state.handsFree) showOverlay();
      else scheduleOverlayHide();
    } else if (message.type === "cancel") {
      state.handsFree = false;
      state.recordingStartedAt = null;
      state.partial = "";
      updateState("ready", "Cancelled. Nothing was pasted.");
      scheduleOverlayHide();
    } else if (message.type === "paste" && message.text) {
      clipboard.writeText(String(message.text));
      state.transcript = String(message.text);
      broadcastState();
    }
    return { ok: true, preview: true };
  }
  const rejection = controlRejection(message.type, state.backend);
  if (rejection) {
    addLog(rejection, "error");
    return { ok: false, message: rejection };
  }
  if (!backendProcess?.stdin?.writable) {
    return { ok: false, message: "The dictation engine is not ready." };
  }
  backendProcess.stdin.write(`${JSON.stringify(message)}\n`);
  return { ok: true };
}

function sendAfterHiding(message) {
  if (isUiOnly()) return sendBackendControl(message);
  const rejection = controlRejection(message.type, state.backend);
  if (rejection || !backendProcess?.stdin?.writable) {
    const result = {
      ok: false,
      message: rejection || "The dictation engine is not ready.",
    };
    addLog(result.message, "error");
    showMainWindow();
    return result;
  }
  mainWindow?.hide();
  setTimeout(() => {
    const result = sendBackendControl(message);
    if (!result.ok) {
      showMainWindow();
      updateState("error", result.message);
    }
  }, 180);
  return { ok: true };
}

function stopBackend() {
  return new Promise((resolve) => {
    const child = backendProcess;
    if (!child) {
      resolve();
      return;
    }

    updateState("stopping", "Stopping the dictation engine…");
    child.once("exit", () => {
      clearTimeout(forceKillTimer);
      forceKillTimer = undefined;
      resolve();
    });

    try {
      child.stdin.write(`${JSON.stringify({ type: "quit" })}\n`);
      child.stdin.end();
    } catch {
      child.kill();
    }

    forceKillTimer = setTimeout(() => {
      if (backendProcess === child && child.pid) {
        const killer = spawn("taskkill", ["/PID", String(child.pid), "/T", "/F"], {
          windowsHide: true,
          stdio: "ignore",
        });
        killer.once("exit", () => {
          if (backendProcess === child) backendProcess = undefined;
          resolve();
        });
        killer.once("error", () => {
          if (backendProcess === child) backendProcess = undefined;
          resolve();
        });
      } else {
        resolve();
      }
    }, 4000);
  });
}

async function restartBackend() {
  clearTimeout(backendRestartTimer);
  backendRestartTimer = undefined;
  backendRestartAttempts = 0;
  await stopBackend();
  if (!isQuitting) startBackend();
}

function scheduleBackendRestart() {
  if (isQuitting || backendRestartTimer || backendRecoveryInFlight) return;
  if (backendRestartAttempts >= MAX_AUTOMATIC_RESTARTS) {
    updateState(
      "error",
      "The speech engine could not recover automatically. Open Parrot and choose Restart engine.",
    );
    showMainWindow();
    return;
  }
  backendRestartAttempts += 1;
  const delay = restartDelayMs(backendRestartAttempts);
  updateState(
    "recovering",
    `Speech engine stopped. Recovering automatically (${backendRestartAttempts}/${MAX_AUTOMATIC_RESTARTS})…`,
  );
  backendRestartTimer = setTimeout(() => {
    backendRestartTimer = undefined;
    if (!isQuitting && !backendProcess) startBackend();
  }, delay);
}

async function recoverUnresponsiveBackend(reason) {
  if (backendRecoveryInFlight || isQuitting) return;
  backendRecoveryInFlight = true;
  recordRuntimeHealth("backend-watchdog", {
    state: state.backend,
    elapsedMs: Date.now() - backendStateEnteredAt,
    reason,
  });
  addLog(`The speech engine stopped responding during ${state.backend}. Recovering…`, "error");
  if (state.partial) saveRecoveryDraft(state.partial);
  await stopBackend();
  if (!isQuitting) startBackend();
  showMainWindow();
  backendRecoveryInFlight = false;
}

function startBackendWatchdog() {
  clearInterval(backendWatchdogTimer);
  backendWatchdogTimer = setInterval(() => {
    if (!backendProcess || backendRecoveryInFlight || isQuitting) return;
    const timeout = backendTimeoutMs(state.backend, lastRecordingDurationMs);
    if (!timeout || Date.now() - backendStateEnteredAt <= timeout) return;
    recoverUnresponsiveBackend(`${state.backend}-timeout`).catch((error) => {
      backendRecoveryInFlight = false;
      updateState("error", `Automatic recovery failed: ${error.message}`);
      showMainWindow();
    });
  }, 5_000);
}

function handleBackendLine(line) {
  const trimmed = line.trim();
  if (!trimmed) return;

  if (trimmed.startsWith("PARROT_EVENT ")) {
    try {
      const event = JSON.parse(trimmed.slice("PARROT_EVENT ".length));
      handleBackendEvent(event);
      return;
    } catch {
      // Keep malformed structured events in diagnostics.
    }
  }
  addLog(trimmed);
}

function handleBackendEvent(event) {
  if (event.type === "formatter") {
    state.formatter = event.state || "warming";
    const message = String(event.message || "");
    if (message) {
      addLog(message, event.state === "unavailable" ? "error" : "info", false);
    }
    broadcastState();
    return;
  }
  if (event.type === "mode") {
    state.handsFree = Boolean(event.handsFree);
    broadcastState();
    rebuildTrayMenu();
    return;
  }
  if (event.type === "partial") {
    state.partial = String(event.text || "");
    saveRecoveryDraft(state.partial);
    showOverlay();
    broadcastState();
    rebuildTrayMenu();
    return;
  }
  if (event.type === "final") {
    state.transcript = String(event.text || "");
    state.partial = state.transcript;
    state.recordingStartedAt = null;
    state.handsFree = false;
    state.userData = recordTranscript(state.userData, {
      text: state.transcript,
      durationSeconds: Number(event.durationSeconds) || 0,
      source: event.developerContext ? "developer" : "dictation",
    });
    saveUserData();
    broadcastState();
    rebuildTrayMenu();
    return;
  }
  if (event.type === "repaste") {
    state.transcript = String(event.text || state.transcript);
    state.partial = state.transcript;
    broadcastState();
    return;
  }
  if (event.type !== "status") return;

  if (event.state === "recording") {
    state.partial = "";
    state.recordingStartedAt ||= Date.now();
  } else if (["ready", "error", "stopped"].includes(event.state)) {
    state.recordingStartedAt = null;
  }
  updateState(event.state || "starting", event.message || "");
  if (["recording", "processing", "formatting", "pasting"].includes(event.state)) {
    showOverlay();
  } else if (event.state === "ready") {
    scheduleOverlayHide();
  } else if (["error", "stopped"].includes(event.state)) {
    hideOverlay();
  }
}

function updateState(backend, message) {
  if (backend !== state.backend) {
    const now = Date.now();
    if (state.backend === "recording" && backend !== "recording") {
      lastRecordingDurationMs = state.recordingStartedAt
        ? Math.max(0, now - state.recordingStartedAt)
        : 0;
    }
    backendStateEnteredAt = now;
    recordRuntimeHealth("state", { from: state.backend, to: backend });
  }
  state.backend = backend;
  state.message = message;
  if (backend === "ready") backendRestartAttempts = 0;
  if (message) addLog(message, backend === "error" ? "error" : "info", false);
  broadcastState();
  rebuildTrayMenu();
}

function addLog(message, level = "info", broadcast = true) {
  const entry = {
    at: new Date().toISOString(),
    level,
    message: String(message),
  };
  state.log = [...state.log.slice(-79), entry];
  if (broadcast) broadcastState();
}

function broadcastState() {
  const snapshot = publicState();
  sendWindowState(mainWindow, snapshot);
  sendWindowState(overlayWindow, snapshot);
}

function sendWindowState(window, snapshot) {
  if (
    !window ||
    window.isDestroyed() ||
    window.webContents.isDestroyed()
  ) {
    return;
  }
  try {
    window.webContents.send("parrot:state", snapshot);
  } catch {
    // A renderer may disappear between the liveness check and IPC send. Its
    // recovery listener will rebuild it without affecting audio capture.
  }
}

function publicState() {
  return {
    backend: state.backend,
    formatter: state.formatter,
    message: state.message,
    partial: state.partial,
    transcript: state.transcript,
    handsFree: state.handsFree,
    recordingStartedAt: state.recordingStartedAt,
    log: state.log,
    settings: state.settings,
    history: state.userData.history,
    dictionary: state.userData.dictionary,
    snippets: state.userData.snippets,
    learnedWords: state.userData.learnedWords,
    recoveryDraft: state.userData.recoveryDraft,
    stats: deriveStats(state.userData),
    packaged: app.isPackaged,
    setupRunning: Boolean(modelSetupProcess),
    previewMode: isUiOnly(),
    sampleData: process.argv.includes("--e2e"),
  };
}

function showOverlay() {
  clearTimeout(hideOverlayTimer);
  if (!overlayWindow || overlayWindow.isDestroyed()) return;
  positionOverlay();
  overlayWindow.showInactive();
}

function scheduleOverlayHide() {
  clearTimeout(hideOverlayTimer);
  hideOverlayTimer = setTimeout(hideOverlay, 1100);
}

function hideOverlay() {
  clearTimeout(hideOverlayTimer);
  if (overlayWindow && !overlayWindow.isDestroyed()) overlayWindow.hide();
}

function runModelSetup() {
  if (modelSetupProcess) {
    return Promise.resolve({
      ok: false,
      message: "Model setup is already running.",
    });
  }

  return new Promise((resolve) => {
    const model = state.settings.ollamaModel;
    updateState("setup", `Downloading ${model} with Ollama…`);
    addLog(`Running: ollama pull ${model}`);
    modelSetupProcess = spawn("ollama", ["pull", model], {
      windowsHide: true,
      stdio: ["ignore", "pipe", "pipe"],
    });
    broadcastState();

    let failureText = "";
    modelSetupProcess.stdout.on("data", (chunk) => {
      const message = chunk.toString().trim();
      if (message) addLog(message);
    });
    modelSetupProcess.stderr.on("data", (chunk) => {
      failureText += chunk.toString();
      const message = chunk.toString().trim();
      if (message) addLog(message, "error");
    });
    modelSetupProcess.on("error", (error) => {
      modelSetupProcess = undefined;
      const message =
        error.code === "ENOENT"
          ? "Ollama is not installed or is not available on PATH."
          : error.message;
      updateState("error", message);
      resolve({ ok: false, message });
    });
    modelSetupProcess.on("exit", async (code) => {
      modelSetupProcess = undefined;
      if (code === 0) {
        addLog(`${model} is ready.`);
        await restartBackend();
        resolve({ ok: true, message: `${model} is ready.` });
      } else {
        const message =
          failureText.trim() || `Ollama exited with code ${code ?? "unknown"}.`;
        updateState("error", message);
        resolve({ ok: false, message });
      }
    });
  });
}

function updatePersonalization(next) {
  state.userData = sanitizeUserData({
    ...state.userData,
    dictionary: next?.dictionary,
    snippets: next?.snippets,
  });
  saveUserData();
  broadcastState();
  return publicState();
}

function deleteHistoryItem(id) {
  state.userData.history = state.userData.history.filter(
    (entry) => entry.id !== String(id),
  );
  saveUserData();
  broadcastState();
  return publicState();
}

function clearHistory() {
  state.userData.history = [];
  state.userData.recoveryDraft = "";
  state.transcript = "";
  state.partial = "";
  saveUserData();
  broadcastState();
  rebuildTrayMenu();
  return publicState();
}

function quitApplication() {
  if (isQuitting) return;
  isQuitting = true;
  clearTimeout(draftSaveTimer);
  clearTimeout(backendRestartTimer);
  clearInterval(backendWatchdogTimer);
  if (state.userData.recoveryDraft) saveUserData();
  stopBackend().finally(() => app.quit());
}

function registerIpc() {
  ipcMain.handle("parrot:get-state", () => publicState());
  ipcMain.handle("parrot:save-settings", async (_event, settings) => {
    saveSettings(settings);
    await restartBackend();
    return publicState();
  });
  ipcMain.handle("parrot:save-personalization", async (_event, data) => {
    updatePersonalization(data);
    await restartBackend();
    return publicState();
  });
  ipcMain.handle("parrot:restart", async () => {
    await restartBackend();
    return publicState();
  });
  ipcMain.handle("parrot:setup-model", () => runModelSetup());
  ipcMain.handle("parrot:toggle-hands-free", () =>
    sendAfterHiding({ type: "toggle-hands-free" }),
  );
  ipcMain.handle("parrot:cancel", () => sendBackendControl({ type: "cancel" }));
  ipcMain.handle("parrot:paste-last", () =>
    sendAfterHiding({ type: "paste-last" }),
  );
  ipcMain.handle("parrot:paste-text", (_event, text) =>
    sendAfterHiding({ type: "paste", text: String(text || "") }),
  );
  ipcMain.handle("parrot:delete-history", (_event, id) =>
    deleteHistoryItem(id),
  );
  ipcMain.handle("parrot:clear-history", () => clearHistory());
  ipcMain.handle("parrot:copy-transcript", (_event, text) => {
    clipboard.writeText(String(text || ""));
    return { ok: true };
  });
  ipcMain.handle("parrot:open-ollama", () =>
    shell.openExternal("https://ollama.com/download/windows"),
  );
  ipcMain.handle("parrot:hide", () => mainWindow?.hide());
  ipcMain.handle("parrot:quit", () => quitApplication());
  if (process.argv.includes("--e2e")) {
    ipcMain.handle("parrot:e2e-seed", (_event, data) => {
      state.userData = sanitizeUserData(data);
      state.transcript = state.userData.history[0]?.text || "";
      state.partial = state.transcript;
      saveUserData();
      broadcastState();
      rebuildTrayMenu();
      return publicState();
    });
  }
}

const hasLock = app.requestSingleInstanceLock();
if (!hasLock) {
  app.quit();
} else {
  app.on("second-instance", showMainWindow);
  app.whenReady().then(() => {
    loadSettings();
    loadUserData();
    registerIpc();
    createTray();
    createMainWindow();
    createOverlayWindow();
    recordRuntimeHealth("app-ready", { version: app.getVersion() });
    startBackend();
    startBackendWatchdog();
  });
}

app.on("activate", showMainWindow);
app.on("window-all-closed", () => {
  // The tray owns the application lifetime.
});
app.on("before-quit", () => {
  isQuitting = true;
  clearTimeout(backendRestartTimer);
  clearInterval(backendWatchdogTimer);
});
