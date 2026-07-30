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

const { DEFAULT_SETTINGS, sanitizeSettings } = require("./settings");

let mainWindow;
let overlayWindow;
let tray;
let backendProcess;
let forceKillTimer;
let isQuitting = false;
let hideOverlayTimer;
let modelSetupProcess;

const state = {
  backend: "stopped",
  formatter: "warming",
  message: "Starting Project Parrot…",
  partial: "",
  transcript: "",
  log: [],
  settings: { ...DEFAULT_SETTINGS },
};

function settingsPath() {
  return path.join(app.getPath("userData"), "settings.json");
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

function saveSettings(nextSettings) {
  state.settings = sanitizeSettings({ ...state.settings, ...nextSettings });
  fs.mkdirSync(path.dirname(settingsPath()), { recursive: true });
  fs.writeFileSync(settingsPath(), JSON.stringify(state.settings, null, 2));
  applyLoginSetting();
  broadcastState();
  rebuildTrayMenu();
  return state.settings;
}

function applyLoginSetting() {
  if (!app.isPackaged || process.argv.includes("--ui-only")) return;
  app.setLoginItemSettings({
    openAtLogin: state.settings.launchAtLogin,
    path: process.execPath,
    args: ["--background"],
  });
}

function createTrayIcon() {
  const svg = `
    <svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 32 32">
      <rect width="32" height="32" rx="9" fill="#17181a"/>
      <path d="M9 9h8.2c4.2 0 6.8 2.2 6.8 5.8 0 3.8-2.8 6.1-7.1 6.1h-3V26H9V9Zm4.9 3.9v4.2h2.8c1.6 0 2.5-.7 2.5-2.2 0-1.3-.9-2-2.5-2h-2.8Z" fill="#f6f0df"/>
      <circle cx="23.5" cy="8.5" r="3.5" fill="#f3a65a"/>
    </svg>`;
  const image = nativeImage.createFromDataURL(
    `data:image/svg+xml;base64,${Buffer.from(svg).toString("base64")}`,
  );
  return image.resize({ width: 16, height: 16 });
}

function createMainWindow() {
  mainWindow = new BrowserWindow({
    width: 620,
    height: 760,
    minWidth: 440,
    minHeight: 600,
    show: false,
    backgroundColor: "#f5f6f2",
    autoHideMenuBar: true,
    title: "Project Parrot",
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
    width: 460,
    height: 104,
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
  const compact = String(value || "").replace(/\s+/g, " ").trim();
  if (!compact) return "";
  return compact.length > maxLength
    ? `${compact.slice(0, maxLength - 1)}…`
    : compact;
}

function rebuildTrayMenu() {
  if (!tray) return;
  const active = !["stopped", "error"].includes(state.backend);
  const status = menuText(state.message, 64);
  const transcript = menuText(state.transcript || state.partial, 64);
  tray.setToolTip(
    menuText(
      `Project Parrot — ${state.message || state.backend}${
        transcript ? `\nLatest: ${transcript}` : ""
      }`,
      120,
    ),
  );
  tray.setContextMenu(
    Menu.buildFromTemplate([
      {
        label: active ? "Parrot is running" : "Parrot is stopped",
        enabled: false,
      },
      ...(status ? [{ label: status, enabled: false }] : []),
      ...(transcript
        ? [{ label: `Latest: ${transcript}`, enabled: false }]
        : []),
      { type: "separator" },
      { label: "Open Parrot", click: showMainWindow },
      {
        label: active ? "Restart dictation" : "Start dictation",
        click: restartBackend,
      },
      { type: "separator" },
      {
        label: "Launch at sign in",
        type: "checkbox",
        checked: state.settings.launchAtLogin,
        click: (item) => saveSettings({ launchAtLogin: item.checked }),
      },
      { type: "separator" },
      { label: "Quit Project Parrot", click: quitApplication },
    ]),
  );
}

function showMainWindow() {
  if (!mainWindow) createMainWindow();
  if (mainWindow.isMinimized()) mainWindow.restore();
  mainWindow.show();
  mainWindow.focus();
}

function hideMainToActivity() {
  mainWindow?.hide();
}

function backendRoot() {
  return app.isPackaged
    ? path.join(process.resourcesPath, "backend")
    : path.resolve(__dirname, "..");
}

function backendCommand() {
  const root = backendRoot();
  const executable = path.join(root, "project-parrot.exe");
  const releaseExecutable = path.join(root, "target", "release", "project-parrot.exe");

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
  const uiOnly =
    process.env.PARROT_SKIP_BACKEND === "1" || process.argv.includes("--ui-only");
  if (backendProcess || uiOnly) {
    if (uiOnly) {
      updateState("ready", "UI preview mode — backend is disabled.");
    }
    return;
  }

  const { command, prefixArgs } = backendCommand();
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
    "--control-stdin",
  ];

  state.formatter = "warming";
  addLog(`Starting ${state.settings.sttEngine} with ${state.settings.ollamaModel}.`);
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
    if (!isQuitting && state.backend !== "stopping") {
      updateState(
        "error",
        `Dictation engine stopped${code !== null ? ` (code ${code})` : signal ? ` (${signal})` : ""}.`,
      );
    } else {
      updateState("stopped", "Dictation is stopped.");
    }
  });
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
      child.stdin.write("quit\n");
      child.stdin.end();
    } catch {
      child.kill();
    }

    forceKillTimer = setTimeout(() => {
      if (backendProcess === child && child.pid) {
        const killer = spawn(
          "taskkill",
          ["/PID", String(child.pid), "/T", "/F"],
          { windowsHide: true, stdio: "ignore" },
        );
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
      // Preserve malformed structured events in the diagnostic log.
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
    if (state.backend === "ready" && message) state.message = message;
    broadcastState();
    return;
  }
  if (event.type === "partial") {
    state.partial = String(event.text || "");
    showOverlay();
    broadcastState();
    rebuildTrayMenu();
    return;
  }
  if (event.type === "final") {
    state.transcript = String(event.text || "");
    state.partial = state.transcript;
    broadcastState();
    rebuildTrayMenu();
    return;
  }
  if (event.type !== "status") return;

  state.partial = event.state === "recording" ? "" : state.partial;
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
    log: state.log,
    settings: state.settings,
    packaged: app.isPackaged,
    setupRunning: Boolean(modelSetupProcess),
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
    return Promise.resolve({ ok: false, message: "Model setup is already running." });
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

function quitApplication() {
  if (isQuitting) return;
  isQuitting = true;
  stopBackend().finally(() => app.quit());
}

function registerIpc() {
  ipcMain.handle("parrot:get-state", () => publicState());
  ipcMain.handle("parrot:save-settings", async (_event, settings) => {
    saveSettings(settings);
    await restartBackend();
    return publicState();
  });
  ipcMain.handle("parrot:restart", async () => {
    await restartBackend();
    return publicState();
  });
  ipcMain.handle("parrot:setup-model", () => runModelSetup());
  ipcMain.handle("parrot:copy-transcript", (_event, text) => {
    clipboard.writeText(String(text || ""));
    return { ok: true };
  });
  ipcMain.handle("parrot:open-ollama", () =>
    shell.openExternal("https://ollama.com/download/windows"),
  );
  ipcMain.handle("parrot:hide", () => hideMainToActivity());
  ipcMain.handle("parrot:quit", () => quitApplication());
}

const hasLock = app.requestSingleInstanceLock();
if (!hasLock) {
  app.quit();
} else {
  app.on("second-instance", showMainWindow);
  app.whenReady().then(() => {
    loadSettings();
    registerIpc();
    createTray();
    createMainWindow();
    createOverlayWindow();
    startBackend();
  });
}

app.on("activate", showMainWindow);
app.on("window-all-closed", () => {
  // Tray lifetime owns the app. Closing the window intentionally keeps it alive.
});
app.on("before-quit", () => {
  isQuitting = true;
});
