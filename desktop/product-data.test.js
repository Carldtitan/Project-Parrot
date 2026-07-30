const assert = require("node:assert/strict");
const test = require("node:test");

const {
  buildPersonalizationProfile,
  deriveStats,
  recordTranscript,
  sanitizeUserData,
} = require("./product-data");

test("history, learning, and stats are recorded locally", () => {
  const now = new Date("2026-07-29T18:00:00.000Z");
  let data = recordTranscript(
    {},
    { text: "Parrot handles Cloudflare workflows", durationSeconds: 12 },
    now,
  );
  data = recordTranscript(
    data,
    { text: "Cloudflare works with Parrot", durationSeconds: 8 },
    now,
  );
  const stats = deriveStats(data, now);
  assert.equal(stats.sessions, 2);
  assert.equal(stats.totalWords, 8);
  assert.equal(stats.todayWords, 8);
  assert.equal(stats.averageWpm, 24);
  assert.equal(
    data.learnedWords.find((entry) => entry.key === "cloudflare").count,
    2,
  );
});

test("personalization is deduplicated and learned words require repetition", () => {
  const data = sanitizeUserData({
    dictionary: [
      { spoken: "cloud flare", written: "Cloudflare" },
      { spoken: "cloud flare", written: "duplicate" },
    ],
    snippets: [{ trigger: "my calendar", content: "https://example.com" }],
    learnedWords: [
      { key: "parrot", written: "Parrot", count: 2 },
      { key: "novel", written: "novel", count: 1 },
    ],
  });
  const profile = buildPersonalizationProfile(data, {
    cleanupFillers: true,
    formatLists: true,
    developerMode: true,
  });
  assert.equal(profile.dictionary.length, 1);
  assert.deepEqual(
    profile.learnedWords.map((entry) => entry.written),
    ["Parrot"],
  );
  assert.equal(profile.snippets[0].content, "https://example.com");
});
