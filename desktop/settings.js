const DEFAULT_SETTINGS = Object.freeze({
  sttEngine: "parakeet",
  ollamaModel: "qwen2.5:3b-instruct",
  sttThreads: 0,
  launchAtLogin: true,
  updateInterval: 0.5,
  liveWindowSeconds: 8,
  pushToTalkShortcut: "Ctrl+Space",
  handsFreeShortcut: "Ctrl+Alt+Space",
  cancelShortcut: "Ctrl+Alt+Escape",
  pasteLastShortcut: "Ctrl+Alt+V",
  cleanupFillers: true,
  formatLists: true,
  developerMode: true,
  longSessionMinutes: 20,
});

const SHORTCUT_OPTIONS = Object.freeze([
  "Ctrl+Space",
  "Ctrl+Alt+Space",
  "Ctrl+Shift+Space",
  "Alt+Space",
  "Ctrl+Alt+Escape",
  "Ctrl+Alt+V",
  "Ctrl+Shift+V",
  "F8",
  "F9",
  "F10",
  "Mouse4",
  "Mouse5",
]);

function validShortcut(value, fallback) {
  const shortcut = String(value || "").trim();
  return SHORTCUT_OPTIONS.includes(shortcut) ? shortcut : fallback;
}

function sanitizeSettings(input) {
  const sttEngine = input.sttEngine === "small-en" ? "small-en" : "parakeet";
  const sttThreads = Number.isFinite(Number(input.sttThreads))
    ? Math.max(0, Math.min(64, Math.trunc(Number(input.sttThreads))))
    : 0;
  const updateInterval = Math.max(
    0.25,
    Math.min(3, Number(input.updateInterval) || DEFAULT_SETTINGS.updateInterval),
  );
  const liveWindowSeconds = Math.max(
    2,
    Math.min(
      30,
      Number(input.liveWindowSeconds) || DEFAULT_SETTINGS.liveWindowSeconds,
    ),
  );
  const ollamaModel =
    String(input.ollamaModel || "").trim() || DEFAULT_SETTINGS.ollamaModel;
  const shortcuts = {
    pushToTalkShortcut: validShortcut(
      input.pushToTalkShortcut,
      DEFAULT_SETTINGS.pushToTalkShortcut,
    ),
    handsFreeShortcut: validShortcut(
      input.handsFreeShortcut,
      DEFAULT_SETTINGS.handsFreeShortcut,
    ),
    cancelShortcut: validShortcut(
      input.cancelShortcut,
      DEFAULT_SETTINGS.cancelShortcut,
    ),
    pasteLastShortcut: validShortcut(
      input.pasteLastShortcut,
      DEFAULT_SETTINGS.pasteLastShortcut,
    ),
  };
  const seen = new Set();
  for (const key of Object.keys(shortcuts)) {
    if (seen.has(shortcuts[key])) {
      shortcuts[key] = seen.has(DEFAULT_SETTINGS[key])
        ? SHORTCUT_OPTIONS.find((shortcut) => !seen.has(shortcut))
        : DEFAULT_SETTINGS[key];
    }
    seen.add(shortcuts[key]);
  }
  const longSessionMinutes = Math.max(
    5,
    Math.min(
      20,
      Math.trunc(
        Number(input.longSessionMinutes) ||
          DEFAULT_SETTINGS.longSessionMinutes,
      ),
    ),
  );

  return {
    sttEngine,
    ollamaModel,
    sttThreads,
    launchAtLogin: Boolean(input.launchAtLogin),
    updateInterval,
    liveWindowSeconds,
    ...shortcuts,
    cleanupFillers: input.cleanupFillers !== false,
    formatLists: input.formatLists !== false,
    developerMode: input.developerMode !== false,
    longSessionMinutes,
  };
}

module.exports = {
  DEFAULT_SETTINGS,
  SHORTCUT_OPTIONS,
  sanitizeSettings,
};
