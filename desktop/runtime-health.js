const BACKEND_TIMEOUTS = Object.freeze({
  // A first launch may download and initialize the speech model. Do not turn
  // a slow connection into a restart loop.
  starting: 600_000,
  pasting: 20_000,
});

function controlRejection(type, backend) {
  if (type === "cancel") {
    return backend === "recording" ? "" : "There is no active dictation to cancel.";
  }
  if (type === "toggle-hands-free") {
    return ["ready", "recording"].includes(backend)
      ? ""
      : "Parrot is still busy. Wait until the speech engine is ready.";
  }
  if (["paste-last", "paste"].includes(type)) {
    return backend === "ready"
      ? ""
      : "Parrot is still busy. Wait until the current dictation is finished.";
  }
  return "";
}

function backendTimeoutMs(backend, recordingDurationMs = 0) {
  if (backend === "processing") {
    // The worker's own final-pass deadline grows with recording length. Give
    // it a wider external envelope before Electron replaces a wedged worker.
    return Math.max(
      120_000,
      Math.min(630_000, 75_000 + Math.max(0, recordingDurationMs) * 0.5),
    );
  }
  if (backend === "formatting") {
    return Math.max(
      90_000,
      Math.min(600_000, 75_000 + Math.max(0, recordingDurationMs) * 0.25),
    );
  }
  return BACKEND_TIMEOUTS[backend] || 0;
}

function restartDelayMs(attempt) {
  return [1_000, 2_500, 5_000][Math.max(0, attempt - 1)] || 5_000;
}

module.exports = {
  backendTimeoutMs,
  controlRejection,
  restartDelayMs,
};
