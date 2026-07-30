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

let mainWindow;
let overlayWindow;
let tray;
let backendProcess;
let forceKillTimer;
let isQuitting = false;
let hideOverlayTimer;
let modelSetupProcess;
let draftSaveTimer;

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
  const svg = `
    <svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 32 32">
      <rect width="32" height="32" rx="8" fill="#15181d"/>
      <path d="M9 8.5h8.6c4.3 0 6.9 2.2 6.9 5.9 0 3.9-2.8 6.2-7.2 6.2h-3.1v4.9H9v-17Zm5.2 4.1v4.1h2.7c1.6 0 2.5-.7 2.5-2.1 0-1.3-.9-2-2.5-2h-2.7Z" fill="#f7f8fb"/>
      <path d="M23.5 5.5 27 9l-3.5 3.5L20 9l3.5-3.5Z" fill="#5b6cff"/>
    </svg>`;
  const image = nativeImage.createFromDataURL(
    `data:image/svg+xml;base64,${Buffer.from(svg).toString("base64")}`,
  );
  return image.resize({ width: 16, height: 16 });
}

function createMainWindow() {
  mainWindow = new BrowserWindow({
    width: 1080,
    height: 760,
    minWidth: 760,
    minHeight: 600,
    show: false,
    backgroundColor: "#f6f7f9",
    autoHideMenuBar: true,
    title: "Parrot",
    titleBarStyle: "hidden",
    titleBarOverlay: {
      color: "#f6f7f9",
      symbolColor: "#20242a",
      height: 44,
    },
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });

  mainWindow.loadFile(path.join(__dirname, "index.html"));
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
  overlayWindow.on("closed", () => {
    overlayWindow = undefined;
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
  if (!mainWindow) createMainWindow();
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
    } else {
      updateState("stopped", "Dictation is stopped.");
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
  if (!backendProcess?.stdin?.writable) {
    return { ok: false, message: "The dictation engine is not ready." };
  }
  backendProcess.stdin.write(`${JSON.stringify(message)}\n`);
  return { ok: true };
}

function sendAfterHiding(message) {
  if (isUiOnly()) return sendBackendControl(message);
  mainWindow?.hide();
  setTimeout(() => sendBackendControl(message), 180);
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
        killer.once("exit", resolve);
      } else {
        resolve();
      }
    }, 4000);
  });
}

async function restartBackend() {
  await stopBackend();
  if (!isQuitting) startBackend();
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
  state.backend = backend;
  state.message = message;
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
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.webContents.send("parrot:state", snapshot);
  }
  if (overlayWindow && !overlayWindow.isDestroyed()) {
    overlayWindow.webContents.send("parrot:state", snapshot);
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
    startBackend();
  });
}

app.on("activate", showMainWindow);
app.on("window-all-closed", () => {
  // The tray owns the application lifetime.
});
app.on("before-quit", () => {
  isQuitting = true;
});
