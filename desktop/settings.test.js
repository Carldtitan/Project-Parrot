const assert = require("node:assert/strict");
const test = require("node:test");

const {
  DEFAULT_SETTINGS,
  SHORTCUT_OPTIONS,
  sanitizeSettings,
} = require("./settings");

test("recommended local models are the defaults", () => {
  assert.equal(DEFAULT_SETTINGS.sttEngine, "parakeet");
  assert.equal(DEFAULT_SETTINGS.ollamaModel, "qwen2.5:3b-instruct");
});

test("settings are clamped before reaching the backend", () => {
  assert.deepEqual(
    sanitizeSettings({
      sttEngine: "unknown",
      ollamaModel: "  ",
      sttThreads: 1000,
      launchAtLogin: 1,
      updateInterval: 0,
      liveWindowSeconds: 100,
      pushToTalkShortcut: "not-a-shortcut",
      handsFreeShortcut: "Mouse4",
      cancelShortcut: "Mouse4",
      pasteLastShortcut: "F10",
      cleanupFillers: false,
      formatLists: false,
      developerMode: false,
      longSessionMinutes: 100,
    }),
    {
      sttEngine: "parakeet",
      ollamaModel: "qwen2.5:3b-instruct",
      sttThreads: 64,
      launchAtLogin: true,
      updateInterval: 0.5,
      liveWindowSeconds: 30,
      pushToTalkShortcut: "Ctrl+Space",
      handsFreeShortcut: "Mouse4",
      cancelShortcut: "Ctrl+Alt+Escape",
      pasteLastShortcut: "F10",
      cleanupFillers: false,
      formatLists: false,
      developerMode: false,
      longSessionMinutes: 20,
    },
  );
});

test("faster-whisper remains an explicit fallback", () => {
  const settings = sanitizeSettings({
    ...DEFAULT_SETTINGS,
    sttEngine: "small-en",
    sttThreads: 6.9,
  });
  assert.equal(settings.sttEngine, "small-en");
  assert.equal(settings.sttThreads, 6);
});

test("shortcut choices include keyboard and mouse triggers", () => {
  assert.ok(SHORTCUT_OPTIONS.includes("Ctrl+Space"));
  assert.ok(SHORTCUT_OPTIONS.includes("Mouse4"));
  assert.ok(SHORTCUT_OPTIONS.includes("Mouse5"));
});

test("shortcut actions cannot silently collide", () => {
  const settings = sanitizeSettings({
    ...DEFAULT_SETTINGS,
    handsFreeShortcut: "F8",
    cancelShortcut: "F8",
  });
  assert.equal(settings.handsFreeShortcut, "F8");
  assert.equal(settings.cancelShortcut, DEFAULT_SETTINGS.cancelShortcut);
});
