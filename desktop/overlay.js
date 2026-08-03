const statusElement = document.querySelector("#overlay-status");
const textElement = document.querySelector("#overlay-text");
const signalElement = document.querySelector("#overlay-signal");
const modeElement = document.querySelector("#overlay-mode");

const STATUS_COPY = {
  recording: ["Listening", "Speak naturally. Parrot is transcribing locally."],
  processing: ["Transcribing", "Finishing the full recording on this PC."],
  formatting: ["Cleaning up", "Applying corrections, vocabulary, and structure."],
  pasting: ["Pasting", "Sending your text back to the focused app."],
  recovering: ["Recovering", "Restarting the local speech engine."],
  ready: ["Done", "Your dictation is saved in local history."],
};

function render(state) {
  const [title, fallback] =
    STATUS_COPY[state.backend] || ["Parrot", state.message || ""];
  statusElement.textContent = title;
  textElement.textContent =
    state.backend === "recording" && state.partial
      ? state.partial
      : state.message || fallback;
  modeElement.textContent = state.handsFree ? "HANDS-FREE" : "PUSH TO TALK";
  signalElement.classList.toggle("working", state.backend !== "ready");
  signalElement.classList.toggle("recording", state.backend === "recording");
}

window.parrot.onState(render);
window.parrot.getState().then(render);
