const statusElement = document.querySelector("#overlay-status");
const textElement = document.querySelector("#overlay-text");
const orbElement = document.querySelector("#overlay-orb");

const STATUS_COPY = {
  recording: ["Listening…", "Speak naturally, then release Space."],
  processing: ["Transcribing…", "Keeping your words local."],
  formatting: ["Polishing…", "Restoring punctuation and casing."],
  pasting: ["Pasting…", "Sending text to the focused app."],
  ready: ["Done", "Your text is ready."],
};

function render(state) {
  const [title, fallback] =
    STATUS_COPY[state.backend] || ["Project Parrot", state.message || ""];
  statusElement.textContent = title;
  textElement.textContent =
    state.backend === "recording" && state.partial
      ? state.partial
      : fallback;
  orbElement.classList.toggle("working", state.backend !== "ready");
  orbElement.classList.toggle("recording", state.backend === "recording");
}

window.parrot.onState(render);
window.parrot.getState().then(render);
