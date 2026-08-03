const assert = require("node:assert/strict");
const test = require("node:test");

const {
  backendTimeoutMs,
  controlRejection,
  restartDelayMs,
} = require("./runtime-health");

test("dictation controls cannot hide the app while the engine is busy", () => {
  assert.equal(controlRejection("toggle-hands-free", "ready"), "");
  assert.equal(controlRejection("toggle-hands-free", "recording"), "");
  assert.match(controlRejection("toggle-hands-free", "starting"), /still busy/i);
  assert.match(controlRejection("paste-last", "processing"), /still busy/i);
  assert.match(controlRejection("cancel", "ready"), /no active dictation/i);
});

test("processing watchdog scales with the completed recording", () => {
  assert.equal(backendTimeoutMs("processing", 60_000), 120_000);
  assert.equal(backendTimeoutMs("processing", 1_200_000), 630_000);
  assert.equal(backendTimeoutMs("formatting"), 90_000);
  assert.equal(backendTimeoutMs("formatting", 1_200_000), 375_000);
  assert.equal(backendTimeoutMs("starting"), 600_000);
  assert.equal(backendTimeoutMs("ready"), 0);
});

test("automatic restarts back off and remain bounded", () => {
  assert.equal(restartDelayMs(1), 1_000);
  assert.equal(restartDelayMs(2), 2_500);
  assert.equal(restartDelayMs(3), 5_000);
});
