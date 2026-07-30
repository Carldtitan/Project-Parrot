const assert = require("node:assert/strict");
const test = require("node:test");

const { DEFAULT_SETTINGS, sanitizeSettings } = require("./settings");

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
    }),
    {
      sttEngine: "parakeet",
      ollamaModel: "qwen2.5:3b-instruct",
      sttThreads: 64,
      launchAtLogin: true,
      updateInterval: 0.5,
      liveWindowSeconds: 30,
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
