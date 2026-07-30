const SHORTCUT_OPTIONS = [
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
];

const elements = {
  body: document.body,
  statusDot: document.querySelector("#status-dot"),
  statusLabel: document.querySelector("#status-label"),
  statusMessage: document.querySelector("#status-message"),
  dictationTitlePrefix: document.querySelector("#dictation-title-prefix"),
  dictationTitleSuffix: document.querySelector("#dictation-title-suffix"),
  dictationMessage: document.querySelector("#dictation-message"),
  primaryShortcut: document.querySelector("#primary-shortcut"),
  handsFreeLabel: document.querySelector("#hands-free-label"),
  sampleDataNote: document.querySelector("#sample-data-note"),
  recordingTimer: document.querySelector("#recording-timer"),
  transcript: document.querySelector("#live-transcript"),
  transcriptState: document.querySelector("#transcript-state"),
  copyButton: document.querySelector("#copy-button"),
  handsFreeButton: document.querySelector("#hands-free-button"),
  cancelButton: document.querySelector("#cancel-button"),
  pasteLastButton: document.querySelector("#paste-last-button"),
  recentList: document.querySelector("#recent-list"),
  historyList: document.querySelector("#history-list"),
  historySearch: document.querySelector("#history-search"),
  clearHistoryButton: document.querySelector("#clear-history-button"),
  todayWords: document.querySelector("#today-words"),
  averageWpm: document.querySelector("#average-wpm"),
  sessionCount: document.querySelector("#session-count"),
  activeDays: document.querySelector("#active-days"),
  dictionaryForm: document.querySelector("#dictionary-form"),
  dictionarySpoken: document.querySelector("#dictionary-spoken"),
  dictionaryWritten: document.querySelector("#dictionary-written"),
  dictionaryList: document.querySelector("#dictionary-list"),
  snippetForm: document.querySelector("#snippet-form"),
  snippetTrigger: document.querySelector("#snippet-trigger"),
  snippetContent: document.querySelector("#snippet-content"),
  snippetList: document.querySelector("#snippet-list"),
  learnedList: document.querySelector("#learned-list"),
  personalizationMessage: document.querySelector("#personalization-message"),
  settingsForm: document.querySelector("#settings-form"),
  pushToTalkShortcut: document.querySelector("#push-to-talk-shortcut"),
  handsFreeShortcut: document.querySelector("#hands-free-shortcut"),
  cancelShortcut: document.querySelector("#cancel-shortcut"),
  pasteLastShortcut: document.querySelector("#paste-last-shortcut"),
  cleanupFillers: document.querySelector("#cleanup-fillers"),
  formatLists: document.querySelector("#format-lists"),
  developerMode: document.querySelector("#developer-mode"),
  longSessionMinutes: document.querySelector("#long-session-minutes"),
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
  starting: "Starting",
  ready: "Ready",
  recording: "Listening",
  processing: "Transcribing",
  formatting: "Cleaning up",
  pasting: "Pasting",
  setup: "Installing",
  stopping: "Stopping",
  stopped: "Stopped",
  error: "Needs attention",
};

let currentState;
let hydrated = false;
let copyResetTimer;
let clearHistoryResetTimer;
let clearHistoryArmed = false;
let activeView = "home";

function humanShortcut(shortcut) {
  return String(shortcut || "").replaceAll("+", " + ");
}

function populateShortcutSelects() {
  for (const select of document.querySelectorAll("[data-shortcut-select]")) {
    select.replaceChildren(
      ...SHORTCUT_OPTIONS.map((shortcut) => {
        const option = document.createElement("option");
        option.value = shortcut;
        option.textContent = humanShortcut(shortcut);
        return option;
      }),
    );
  }
}

function visibleTranscript(state) {
  if (state.backend === "recording") return state.partial || "";
  return state.transcript || state.partial || state.recoveryDraft || "";
}

function formatTime(value) {
  const date = new Date(value);
  const today = new Date();
  const sameDay = date.toDateString() === today.toDateString();
  return date.toLocaleString([], sameDay
    ? { hour: "numeric", minute: "2-digit" }
    : { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
}

function formatDuration(seconds) {
  const rounded = Math.max(0, Math.round(Number(seconds) || 0));
  if (rounded < 60) return `${rounded}s`;
  return `${Math.floor(rounded / 60)}m ${rounded % 60}s`;
}

function emptyState(title, message) {
  const empty = document.createElement("div");
  empty.className = "empty-state";
  const strong = document.createElement("strong");
  strong.textContent = title;
  const span = document.createElement("span");
  span.textContent = message;
  empty.append(strong, span);
  return empty;
}

function recentRow(entry) {
  const row = document.createElement("div");
  row.className = "activity-row";
  const text = document.createElement("p");
  text.textContent = entry.text;
  text.title = entry.text;
  const time = document.createElement("time");
  time.dateTime = entry.createdAt;
  time.textContent = formatTime(entry.createdAt);
  row.append(text, time);
  return row;
}

function actionButton(label, action, id, className = "") {
  const button = document.createElement("button");
  button.type = "button";
  button.className = `row-action ${className}`.trim();
  button.dataset.action = action;
  button.dataset.id = id;
  button.textContent = label;
  return button;
}

function historyRow(entry) {
  const row = document.createElement("article");
  row.className = "history-row";
  const content = document.createElement("div");
  const text = document.createElement("p");
  text.textContent = entry.text;
  const meta = document.createElement("div");
  meta.className = "history-meta";
  const time = document.createElement("time");
  time.dateTime = entry.createdAt;
  time.textContent = formatTime(entry.createdAt);
  const words = document.createElement("span");
  words.textContent = `${entry.wordCount} words`;
  const duration = document.createElement("span");
  duration.textContent = formatDuration(entry.durationSeconds);
  meta.append(time, words, duration);
  content.append(text, meta);

  const actions = document.createElement("div");
  actions.className = "row-actions";
  actions.append(
    actionButton("Copy", "copy-history", entry.id),
    actionButton("Paste", "paste-history", entry.id),
    actionButton("Delete", "delete-history", entry.id, "delete"),
  );
  row.append(content, actions);
  return row;
}

function dataRow(primary, secondary, action, id) {
  const row = document.createElement("div");
  row.className = "data-row";
  const content = document.createElement("div");
  const strong = document.createElement("strong");
  strong.textContent = primary;
  const small = document.createElement("small");
  small.textContent = secondary;
  content.append(strong, small);
  const actions = document.createElement("div");
  actions.className = "row-actions";
  actions.append(actionButton("Remove", action, id, "delete"));
  row.append(content, actions);
  return row;
}

function renderRecent(state) {
  const recent = (state.history || []).slice(0, 3);
  elements.recentList.replaceChildren(
    ...(recent.length
      ? recent.map(recentRow)
      : [
          emptyState(
            "Your recent dictations will appear here",
            "Anything Parrot finishes is saved locally so you can recover it.",
          ),
        ]),
  );
}

function renderHistory(state) {
  const query = elements.historySearch.value.trim().toLocaleLowerCase();
  const history = (state.history || []).filter((entry) =>
    entry.text.toLocaleLowerCase().includes(query),
  );
  elements.historyList.replaceChildren(
    ...(history.length
      ? history.map(historyRow)
      : [
          emptyState(
            query ? "No matching dictations" : "No dictation history yet",
            query
              ? "Try a different word or phrase."
              : "Hold your push-to-talk shortcut and finish one dictation.",
          ),
        ]),
  );
  elements.clearHistoryButton.disabled = !(state.history || []).length;
}

function renderPersonalization(state) {
  const dictionary = state.dictionary || [];
  const snippets = state.snippets || [];
  elements.dictionaryList.replaceChildren(
    ...(dictionary.length
      ? dictionary.map((entry, index) =>
          dataRow(entry.written, `When you say “${entry.spoken}”`, "delete-word", String(index)),
        )
      : [
          emptyState(
            "No custom words yet",
            "Add names, product terms, and uncommon spellings.",
          ),
        ]),
  );
  elements.snippetList.replaceChildren(
    ...(snippets.length
      ? snippets.map((entry, index) =>
          dataRow(entry.trigger, entry.content, "delete-snippet", String(index)),
        )
      : [
          emptyState(
            "No snippets yet",
            "Create a cue for text you paste often.",
          ),
        ]),
  );

  const learned = (state.learnedWords || [])
    .filter((entry) => entry.count >= 2)
    .slice(0, 40);
  elements.learnedList.replaceChildren(
    ...(learned.length
      ? learned.map((entry) => {
          const word = document.createElement("span");
          word.className = "learned-word";
          const label = document.createElement("span");
          label.textContent = entry.written;
          const count = document.createElement("small");
          count.textContent = `×${entry.count}`;
          word.append(label, count);
          return word;
        })
      : [
          emptyState(
            "Parrot learns through repetition",
            "Terms used in more than one successful dictation will appear here.",
          ),
        ]),
  );
}

function hydrateSettings(state) {
  if (hydrated) return;
  const settings = state.settings;
  elements.pushToTalkShortcut.value = settings.pushToTalkShortcut;
  elements.handsFreeShortcut.value = settings.handsFreeShortcut;
  elements.cancelShortcut.value = settings.cancelShortcut;
  elements.pasteLastShortcut.value = settings.pasteLastShortcut;
  elements.cleanupFillers.checked = settings.cleanupFillers;
  elements.formatLists.checked = settings.formatLists;
  elements.developerMode.checked = settings.developerMode;
  elements.longSessionMinutes.value = String(settings.longSessionMinutes);
  elements.sttEngine.value = settings.sttEngine;
  elements.ollamaModel.value = settings.ollamaModel;
  elements.sttThreads.value = String(settings.sttThreads);
  elements.launchAtLogin.checked = settings.launchAtLogin;
  hydrated = true;
}

function renderLog(state) {
  const entries = [...(state.log || [])].slice(-40).reverse();
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

function updateTimer() {
  const startedAt = Number(currentState?.recordingStartedAt);
  if (!startedAt || currentState?.backend !== "recording") {
    elements.recordingTimer.textContent = "00:00";
    return;
  }
  const seconds = Math.max(0, Math.floor((Date.now() - startedAt) / 1000));
  const minutes = Math.floor(seconds / 60);
  elements.recordingTimer.textContent = `${String(minutes).padStart(2, "0")}:${String(
    seconds % 60,
  ).padStart(2, "0")}`;
}

function render(nextState) {
  currentState = nextState;
  const backend = nextState.backend || "starting";
  const transcript = visibleTranscript(nextState);
  const shortcut = humanShortcut(nextState.settings.pushToTalkShortcut);

  elements.body.dataset.state = backend;
  elements.statusDot.className = `status-dot ${backend}`;
  elements.statusLabel.textContent = STATE_COPY[backend] || "Working";
  elements.statusMessage.textContent =
    nextState.message || "Speech processing stays on this computer.";

  elements.primaryShortcut.textContent = shortcut;
  if (backend === "recording") {
    elements.dictationTitlePrefix.textContent = nextState.handsFree
      ? "Listening"
      : "Keep holding";
    elements.dictationTitleSuffix.textContent = nextState.handsFree
      ? "hands-free"
      : "while you speak";
    elements.dictationMessage.textContent = nextState.handsFree
      ? `Use ${humanShortcut(nextState.settings.handsFreeShortcut)} again to finish.`
      : "Release the shortcut to finish and paste.";
  } else {
    elements.dictationTitlePrefix.textContent = "Hold";
    elements.dictationTitleSuffix.textContent = "to dictate";
    elements.dictationMessage.textContent =
      "Release the shortcut when you finish. Parrot pastes into the app you were using.";
  }

  elements.transcript.textContent =
    transcript ||
    (backend === "recording"
      ? "Listening for your first words…"
      : "Your words appear here while you speak.");
  elements.transcript.classList.toggle("empty", !transcript);
  elements.transcriptState.textContent =
    backend === "recording"
      ? nextState.handsFree
        ? "Hands-free session"
        : "Live from the microphone"
      : transcript
        ? "Last completed dictation"
        : "Waiting for speech";
  elements.copyButton.disabled = !transcript;
  elements.pasteLastButton.disabled = !nextState.transcript;
  elements.cancelButton.disabled = backend !== "recording";
  elements.handsFreeButton.setAttribute(
    "aria-label",
    nextState.handsFree ? "Finish hands-free dictation" : "Start hands-free dictation",
  );
  elements.handsFreeLabel.textContent = nextState.handsFree
    ? "Finish"
    : "Hands-free";
  elements.sampleDataNote.hidden = !nextState.sampleData;

  elements.todayWords.textContent = String(nextState.stats?.todayWords || 0);
  elements.averageWpm.textContent = String(nextState.stats?.averageWpm || 0);
  elements.sessionCount.textContent = String(nextState.stats?.sessions || 0);
  elements.activeDays.textContent = String(nextState.stats?.activeDays || 0);

  elements.setupButton.disabled = nextState.setupRunning;
  elements.setupButton.textContent = nextState.setupRunning
    ? "Installing…"
    : "Install formatter";

  hydrateSettings(nextState);
  renderRecent(nextState);
  renderHistory(nextState);
  renderPersonalization(nextState);
  renderLog(nextState);
  updateTimer();
}

function formSettings() {
  return {
    sttEngine: elements.sttEngine.value,
    ollamaModel: elements.ollamaModel.value.trim(),
    sttThreads: Number(elements.sttThreads.value || 0),
    launchAtLogin: elements.launchAtLogin.checked,
    pushToTalkShortcut: elements.pushToTalkShortcut.value,
    handsFreeShortcut: elements.handsFreeShortcut.value,
    cancelShortcut: elements.cancelShortcut.value,
    pasteLastShortcut: elements.pasteLastShortcut.value,
    cleanupFillers: elements.cleanupFillers.checked,
    formatLists: elements.formatLists.checked,
    developerMode: elements.developerMode.checked,
    longSessionMinutes: Number(elements.longSessionMinutes.value || 20),
  };
}

async function runAction(button, action, successMessage, messageElement = elements.formMessage) {
  const originalText = button?.textContent;
  if (button) button.disabled = true;
  messageElement.textContent = "";
  try {
    const result = await action();
    messageElement.textContent = result?.message || successMessage;
    return result;
  } catch (error) {
    messageElement.textContent = error.message;
    return undefined;
  } finally {
    if (button) {
      button.disabled = false;
      button.textContent = originalText;
    }
  }
}

function showView(viewName) {
  activeView = viewName;
  for (const view of document.querySelectorAll("[data-view]")) {
    const active = view.dataset.view === viewName;
    view.hidden = !active;
    view.classList.toggle("active", active);
  }
  for (const button of document.querySelectorAll("[data-view-target]")) {
    const active = button.dataset.viewTarget === viewName;
    button.classList.toggle("active", active);
    if (active) button.setAttribute("aria-current", "page");
    else button.removeAttribute("aria-current");
  }
  document.querySelector(".view-stack").scrollTop = 0;
  if (viewName === "history") elements.historySearch.focus();
}

async function savePersonalization(dictionary, snippets, message) {
  const result = await window.parrot.savePersonalization({
    dictionary,
    snippets,
  });
  if (result) render(result);
  elements.personalizationMessage.textContent = message;
}

elements.settingsForm.addEventListener("submit", (event) => {
  event.preventDefault();
  runAction(
    elements.saveButton,
    () => window.parrot.saveSettings(formSettings()),
    "Saved. Parrot restarted with the new settings.",
  ).then((result) => {
    if (result) {
      hydrated = false;
      render(result);
    }
  });
});

elements.restartButton.addEventListener("click", () =>
  runAction(
    elements.restartButton,
    () => window.parrot.restart(),
    "The local engine restarted.",
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
    elements.copyButton.textContent = "Copy text";
  }, 1400);
});

elements.handsFreeButton.addEventListener("click", () =>
  window.parrot.toggleHandsFree(),
);
elements.cancelButton.addEventListener("click", () => window.parrot.cancel());
elements.pasteLastButton.addEventListener("click", () => window.parrot.pasteLast());

elements.dictionaryForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const spoken = elements.dictionarySpoken.value.trim();
  const written = elements.dictionaryWritten.value.trim();
  if (!spoken || !written) return;
  const dictionary = [...(currentState.dictionary || []), { spoken, written }];
  await savePersonalization(
    dictionary,
    currentState.snippets || [],
    `Added “${written}” to your local dictionary.`,
  );
  elements.dictionaryForm.reset();
  elements.dictionarySpoken.focus();
});

elements.snippetForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const trigger = elements.snippetTrigger.value.trim();
  const content = elements.snippetContent.value.trim();
  if (!trigger || !content) return;
  const snippets = [...(currentState.snippets || []), { trigger, content }];
  await savePersonalization(
    currentState.dictionary || [],
    snippets,
    `Added the “${trigger}” voice snippet.`,
  );
  elements.snippetForm.reset();
  elements.snippetTrigger.focus();
});

elements.dictionaryList.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-action='delete-word']");
  if (!button) return;
  const dictionary = [...(currentState.dictionary || [])];
  dictionary.splice(Number(button.dataset.id), 1);
  await savePersonalization(
    dictionary,
    currentState.snippets || [],
    "Removed the dictionary entry.",
  );
});

elements.snippetList.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-action='delete-snippet']");
  if (!button) return;
  const snippets = [...(currentState.snippets || [])];
  snippets.splice(Number(button.dataset.id), 1);
  await savePersonalization(
    currentState.dictionary || [],
    snippets,
    "Removed the voice snippet.",
  );
});

elements.historyList.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-action]");
  if (!button) return;
  const entry = (currentState.history || []).find(
    (item) => item.id === button.dataset.id,
  );
  if (!entry) return;
  if (button.dataset.action === "copy-history") {
    await window.parrot.copyTranscript(entry.text);
    button.textContent = "Copied";
  } else if (button.dataset.action === "paste-history") {
    await window.parrot.pasteText(entry.text);
  } else if (button.dataset.action === "delete-history") {
    const result = await window.parrot.deleteHistory(entry.id);
    if (result) render(result);
  }
});

elements.historySearch.addEventListener("input", () => renderHistory(currentState));

elements.clearHistoryButton.addEventListener("click", async () => {
  clearTimeout(clearHistoryResetTimer);
  if (!clearHistoryArmed) {
    clearHistoryArmed = true;
    elements.clearHistoryButton.textContent = "Confirm clear";
    clearHistoryResetTimer = setTimeout(() => {
      clearHistoryArmed = false;
      elements.clearHistoryButton.textContent = "Clear history";
    }, 3500);
    return;
  }
  clearHistoryArmed = false;
  elements.clearHistoryButton.textContent = "Clear history";
  const result = await window.parrot.clearHistory();
  if (result) render(result);
});

for (const button of document.querySelectorAll("[data-view-target]")) {
  button.addEventListener("click", () => showView(button.dataset.viewTarget));
}
for (const button of document.querySelectorAll("[data-view-link]")) {
  button.addEventListener("click", () => showView(button.dataset.viewLink));
}

elements.hideButton.addEventListener("click", () => window.parrot.hide());
elements.quitButton.addEventListener("click", () => window.parrot.quit());
elements.ollamaButton.addEventListener("click", () => window.parrot.openOllama());
document.addEventListener("keydown", (event) => {
  if (
    event.key === "Escape" &&
    event.target instanceof HTMLElement &&
    event.target.matches("input, select, textarea")
  ) {
    event.target.blur();
    return;
  }
  if (event.key === "Escape" && activeView !== "home") showView("home");
  else if (event.key === "Escape") window.parrot.hide();
});

populateShortcutSelects();
setInterval(updateTimer, 250);
window.parrot.onState(render);
window.parrot.getState().then(render);
