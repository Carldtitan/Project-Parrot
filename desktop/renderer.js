const elements = {
  body: document.body,
  statusDot: document.querySelector("#status-dot"),
  statusLabel: document.querySelector("#status-label"),
  statusMessage: document.querySelector("#status-message"),
  runningBadge: document.querySelector("#running-badge"),
  stageTitle: document.querySelector("#stage-title"),
  transcript: document.querySelector("#live-transcript"),
  transcriptHint: document.querySelector("#transcript-hint"),
  copyButton: document.querySelector("#copy-button"),
  sttEngine: document.querySelector("#stt-engine"),
  ollamaModel: document.querySelector("#ollama-model"),
  sttThreads: document.querySelector("#stt-threads"),
  launchAtLogin: document.querySelector("#launch-at-login"),
  saveButton: document.querySelector("#save-button"),
  restartButton: document.querySelector("#restart-button"),
  setupButton: document.querySelector("#setup-button"),
  ollamaButton: document.querySelector("#ollama-button"),
  hideButton: document.querySelector("#hide-button"),
  quitButton: document.querySelector("#quit-button"),
  formMessage: document.querySelector("#form-message"),
  log: document.querySelector("#log"),
};

const STATE_COPY = {
  starting: ["Starting", "Getting Parrot ready"],
  ready: ["Ready", "Ready when you are"],
  recording: ["Listening", "I’m listening"],
  processing: ["Transcribing", "Turning speech into text"],
  formatting: ["Finishing", "Adding punctuation"],
  pasting: ["Pasting", "Sending your words"],
  setup: ["Installing", "Preparing the formatter"],
  stopping: ["Stopping", "Stopping Parrot"],
  stopped: ["Stopped", "Parrot is stopped"],
  error: ["Needs attention", "Parrot needs attention"],
};

let currentState;
let hydrated = false;
let copyResetTimer;

function visibleTranscript(state) {
  if (state.backend === "recording") {
    return state.partial || "";
  }
  return state.transcript || state.partial || "";
}

function render(nextState) {
  currentState = nextState;
  const backend = nextState.backend || "starting";
  const [label, title] = STATE_COPY[backend] || ["Working", "Parrot is working"];
  const transcript = visibleTranscript(nextState);

  elements.body.dataset.state = backend;
  elements.statusDot.className = `status-dot ${backend}`;
  elements.statusLabel.textContent = label;
  elements.stageTitle.textContent = title;
  elements.statusMessage.textContent =
    nextState.message || "Everything stays on this computer.";
  elements.runningBadge.textContent =
    nextState.formatter === "ready" ? "LOCAL + POLISHED" : "ON DEVICE";
  elements.runningBadge.classList.toggle(
    "formatter-unavailable",
    nextState.formatter === "unavailable",
  );

  elements.transcript.textContent =
    transcript ||
    (backend === "recording"
      ? "Say something…"
      : "Your words will appear here as you speak.");
  elements.transcript.classList.toggle("empty", !transcript);
  elements.copyButton.disabled = !transcript;
  elements.transcriptHint.textContent =
    backend === "recording"
      ? "Keep holding Space. Release it when you’re finished."
      : "Release Space and Parrot pastes the finished text into your active app.";

  elements.setupButton.disabled = nextState.setupRunning;
  elements.setupButton.textContent = nextState.setupRunning
    ? "Installing…"
    : "Install formatter";

  if (!hydrated) {
    elements.sttEngine.value = nextState.settings.sttEngine;
    elements.ollamaModel.value = nextState.settings.ollamaModel;
    elements.sttThreads.value = String(nextState.settings.sttThreads);
    elements.launchAtLogin.checked = nextState.settings.launchAtLogin;
    hydrated = true;
  }

  const entries = [...nextState.log].slice(-30).reverse();
  elements.log.replaceChildren(
    ...entries.map((entry) => {
      const row = document.createElement("div");
      row.className = `log-row ${entry.level}`;
      const time = document.createElement("time");
      time.textContent = new Date(entry.at).toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      });
      const message = document.createElement("span");
      message.textContent = entry.message;
      row.append(time, message);
      return row;
    }),
  );
}

function formSettings() {
  return {
    sttEngine: elements.sttEngine.value,
    ollamaModel: elements.ollamaModel.value.trim(),
    sttThreads: Number(elements.sttThreads.value || 0),
    launchAtLogin: elements.launchAtLogin.checked,
  };
}

async function runAction(button, action, successMessage) {
  const originalText = button.textContent;
  button.disabled = true;
  elements.formMessage.textContent = "";
  try {
    const result = await action();
    elements.formMessage.textContent = result?.message || successMessage;
    return result;
  } catch (error) {
    elements.formMessage.textContent = error.message;
    return undefined;
  } finally {
    button.disabled = false;
    button.textContent = originalText;
  }
}

elements.saveButton.addEventListener("click", () =>
  runAction(
    elements.saveButton,
    () => window.parrot.saveSettings(formSettings()),
    "Saved. Parrot is restarting.",
  ),
);

elements.restartButton.addEventListener("click", () =>
  runAction(
    elements.restartButton,
    () => window.parrot.restart(),
    "Parrot is restarting.",
  ),
);

elements.setupButton.addEventListener("click", () =>
  runAction(
    elements.setupButton,
    () => window.parrot.setupModel(),
    "The optional formatter is ready.",
  ),
);

elements.copyButton.addEventListener("click", async () => {
  const transcript = visibleTranscript(currentState || {});
  if (!transcript) return;
  await window.parrot.copyTranscript(transcript);
  clearTimeout(copyResetTimer);
  elements.copyButton.textContent = "Copied";
  copyResetTimer = setTimeout(() => {
    elements.copyButton.textContent = "Copy";
  }, 1400);
});

elements.hideButton.addEventListener("click", () => window.parrot.hide());
elements.quitButton.addEventListener("click", () => window.parrot.quit());
elements.ollamaButton.addEventListener("click", () => window.parrot.openOllama());
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") window.parrot.hide();
});

window.parrot.onState(render);
window.parrot.getState().then(render);
