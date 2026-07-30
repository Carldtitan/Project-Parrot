const crypto = require("node:crypto");

const MAX_HISTORY = 500;
const MAX_DICTIONARY = 300;
const MAX_SNIPPETS = 100;

const DEFAULT_USER_DATA = Object.freeze({
  history: [],
  dictionary: [],
  snippets: [],
  learnedWords: [],
  recoveryDraft: "",
});

const COMMON_WORDS = new Set(
  "about after again also and are because been before being between both but can could did does doing down each few for from further had has have having here how into its itself just more most not now off once only other our out over same should some such than that the their them then there these they this those through under until very was were what when where which while who why will with would you your".split(
    " ",
  ),
);

function cleanText(value, maxLength) {
  return String(value || "").trim().slice(0, maxLength);
}

function sanitizeDictionary(entries) {
  if (!Array.isArray(entries)) return [];
  const seen = new Set();
  return entries
    .map((entry) => ({
      spoken: cleanText(entry?.spoken, 80),
      written: cleanText(entry?.written, 120),
    }))
    .filter((entry) => {
      const key = entry.spoken.toLocaleLowerCase();
      if (!entry.spoken || !entry.written || seen.has(key)) return false;
      seen.add(key);
      return true;
    })
    .slice(0, MAX_DICTIONARY);
}

function sanitizeSnippets(entries) {
  if (!Array.isArray(entries)) return [];
  const seen = new Set();
  return entries
    .map((entry) => ({
      trigger: cleanText(entry?.trigger, 80),
      content: cleanText(entry?.content, 4000),
    }))
    .filter((entry) => {
      const key = entry.trigger.toLocaleLowerCase();
      if (!entry.trigger || !entry.content || seen.has(key)) return false;
      seen.add(key);
      return true;
    })
    .slice(0, MAX_SNIPPETS);
}

function sanitizeLearnedWords(entries) {
  if (!Array.isArray(entries)) return [];
  const seen = new Set();
  return entries
    .map((entry) => ({
      key: cleanText(entry?.key, 80).toLocaleLowerCase(),
      written: cleanText(entry?.written, 120),
      count: Math.max(1, Math.min(10000, Math.trunc(Number(entry?.count) || 1))),
    }))
    .filter((entry) => {
      if (!entry.key || !entry.written || seen.has(entry.key)) return false;
      seen.add(entry.key);
      return true;
    })
    .slice(0, MAX_DICTIONARY);
}

function sanitizeHistory(entries) {
  if (!Array.isArray(entries)) return [];
  return entries
    .map((entry) => ({
      id: cleanText(entry?.id, 80) || crypto.randomUUID(),
      text: cleanText(entry?.text, 20000),
      createdAt:
        Number.isFinite(Date.parse(entry?.createdAt))
          ? new Date(entry.createdAt).toISOString()
          : new Date().toISOString(),
      durationSeconds: Math.max(0, Number(entry?.durationSeconds) || 0),
      wordCount: Math.max(
        0,
        Math.trunc(Number(entry?.wordCount) || countWords(entry?.text)),
      ),
      source: cleanText(entry?.source, 30) || "dictation",
    }))
    .filter((entry) => entry.text)
    .slice(0, MAX_HISTORY);
}

function sanitizeUserData(input = {}) {
  return {
    history: sanitizeHistory(input.history),
    dictionary: sanitizeDictionary(input.dictionary),
    snippets: sanitizeSnippets(input.snippets),
    learnedWords: sanitizeLearnedWords(input.learnedWords),
    recoveryDraft: cleanText(input.recoveryDraft, 20000),
  };
}

function countWords(text) {
  return String(text || "")
    .trim()
    .split(/\s+/)
    .filter(Boolean).length;
}

function learnFromTranscript(entries, text) {
  const byKey = new Map(
    sanitizeLearnedWords(entries).map((entry) => [entry.key, { ...entry }]),
  );
  const words = String(text || "").match(/[A-Za-z][A-Za-z0-9_-]{3,}/g) || [];
  const seenThisTranscript = new Set();
  for (const written of words) {
    const key = written.toLocaleLowerCase();
    if (COMMON_WORDS.has(key) || seenThisTranscript.has(key)) continue;
    seenThisTranscript.add(key);
    const existing = byKey.get(key);
    if (existing) {
      existing.count += 1;
      if (/[A-Z]/.test(written.slice(1))) existing.written = written;
    } else {
      byKey.set(key, { key, written, count: 1 });
    }
  }
  return [...byKey.values()]
    .sort((left, right) => right.count - left.count || left.key.localeCompare(right.key))
    .slice(0, MAX_DICTIONARY);
}

function recordTranscript(data, entry, now = new Date()) {
  const current = sanitizeUserData(data);
  const text = cleanText(entry?.text, 20000);
  if (!text) return current;
  const createdAt = now.toISOString();
  const nextEntry = {
    id: entry?.id || crypto.randomUUID(),
    text,
    createdAt,
    durationSeconds: Math.max(0, Number(entry?.durationSeconds) || 0),
    wordCount: countWords(text),
    source: cleanText(entry?.source, 30) || "dictation",
  };
  return {
    ...current,
    history: [nextEntry, ...current.history].slice(0, MAX_HISTORY),
    learnedWords: learnFromTranscript(current.learnedWords, text),
    recoveryDraft: "",
  };
}

function deriveStats(data, now = new Date()) {
  const { history } = sanitizeUserData(data);
  const totalWords = history.reduce((sum, entry) => sum + entry.wordCount, 0);
  const totalSeconds = history.reduce(
    (sum, entry) => sum + entry.durationSeconds,
    0,
  );
  const localDay = (value) => {
    const date = new Date(value);
    return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(
      2,
      "0",
    )}-${String(date.getDate()).padStart(2, "0")}`;
  };
  const todayKey = localDay(now);
  const todayWords = history
    .filter((entry) => localDay(entry.createdAt) === todayKey)
    .reduce((sum, entry) => sum + entry.wordCount, 0);
  const activeDays = new Set(history.map((entry) => localDay(entry.createdAt)))
    .size;
  return {
    totalWords,
    todayWords,
    sessions: history.length,
    activeDays,
    dictationMinutes: Math.round((totalSeconds / 60) * 10) / 10,
    averageWpm:
      totalSeconds > 0 ? Math.round(totalWords / (totalSeconds / 60)) : 0,
  };
}

function buildPersonalizationProfile(data, settings) {
  const current = sanitizeUserData(data);
  return {
    dictionary: current.dictionary,
    snippets: current.snippets,
    learnedWords: current.learnedWords.filter((entry) => entry.count >= 2),
    cleanupFillers: settings.cleanupFillers !== false,
    formatLists: settings.formatLists !== false,
    developerMode: settings.developerMode !== false,
  };
}

module.exports = {
  DEFAULT_USER_DATA,
  buildPersonalizationProfile,
  countWords,
  deriveStats,
  learnFromTranscript,
  recordTranscript,
  sanitizeUserData,
};
