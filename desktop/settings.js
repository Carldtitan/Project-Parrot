const DEFAULT_SETTINGS = Object.freeze({
  sttEngine: "parakeet",
  ollamaModel: "qwen2.5:3b-instruct",
  sttThreads: 0,
  launchAtLogin: true,
  updateInterval: 0.5,
  liveWindowSeconds: 8,
});

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

  return {
    sttEngine,
    ollamaModel,
    sttThreads,
    launchAtLogin: Boolean(input.launchAtLogin),
    updateInterval,
    liveWindowSeconds,
  };
}

module.exports = { DEFAULT_SETTINGS, sanitizeSettings };
