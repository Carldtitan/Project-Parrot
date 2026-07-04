from __future__ import annotations

import re
import warnings

with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    import requests


class CleanupError(RuntimeError):
    pass


class OllamaCleaner:
    def __init__(self, model: str, endpoint: str = "http://127.0.0.1:11434/api/generate") -> None:
        self.model = model
        self.endpoint = endpoint

    def clean(self, transcript: str) -> str:
        transcript = transcript.strip()
        if not transcript:
            return ""

        prompt = f"""You are a conservative dictation formatter.
Your job is to preserve the speaker's words and format them.

Rules:
- Preserve all phrases, clauses, names, and sentence order.
- Do not summarize, shorten, paraphrase, or rewrite the sentence structure.
- Do not remove opening phrases or introductory clauses.
- Do not replace uncertain or garbled words with guessed concepts.
- If a word or phrase looks wrong but you are not certain, keep it exactly.
- Fix punctuation, capitalization, spacing, and obvious plural/singular agreement only.
- Remove filler words only when they are clearly filler, such as "um" or "uh".
- Keep proper nouns as close to the transcript as possible unless the correction is obvious from spelling.
- Return only the formatted text.

Examples of forbidden edits:
- Do not change "pessinum, more and more" to "poetry".
- Do not change "personal mem war" to "poetry".
- Do not delete "To dive into world-class essays," from the beginning.

Dictated text:
{transcript}
"""
        try:
            response = requests.post(
                self.endpoint,
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0,
                        "num_predict": 512,
                    },
                },
                timeout=60,
            )
        except requests.RequestException as exc:
            raise CleanupError(f"Could not reach Ollama at {self.endpoint}: {exc}") from exc

        if response.status_code >= 400:
            raise CleanupError(f"Ollama returned HTTP {response.status_code}: {response.text}")

        cleaned = _strip_wrapping_quotes(response.json().get("response", "").strip())
        if not cleaned:
            return transcript
        if not _preserves_content(transcript, cleaned):
            return transcript
        return cleaned


def _strip_wrapping_quotes(text: str) -> str:
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {'"', "'"}:
        return text[1:-1].strip()
    return text


def _preserves_content(original: str, cleaned: str) -> bool:
    original_words = _important_words(original)
    if not original_words:
        return True

    cleaned_words = _all_words(cleaned)
    if len(cleaned_words) < len(_all_words(original)) * 0.75:
        return False

    missing = [
        word for word in original_words
        if not any(_close_word_match(word, candidate) for candidate in cleaned_words)
    ]
    return not missing


def _important_words(text: str) -> list[str]:
    stopwords = {
        "about", "after", "again", "also", "and", "are", "because", "but", "can",
        "for", "from", "have", "into", "not", "that", "the", "these", "this",
        "through", "with", "you", "your",
    }
    return [
        word for word in _all_words(text)
        if len(word) >= 5 and word not in stopwords
    ]


def _all_words(text: str) -> list[str]:
    return [word.lower() for word in re.findall(r"[A-Za-z']+", text)]


def _close_word_match(left: str, right: str) -> bool:
    if left == right:
        return True
    max_distance = 1 if len(left) < 7 else 2
    return _levenshtein_distance(left, right, max_distance) <= max_distance


def _levenshtein_distance(left: str, right: str, limit: int) -> int:
    if abs(len(left) - len(right)) > limit:
        return limit + 1

    previous = list(range(len(right) + 1))
    for i, left_char in enumerate(left, start=1):
        current = [i]
        row_min = current[0]
        for j, right_char in enumerate(right, start=1):
            insert = current[j - 1] + 1
            delete = previous[j] + 1
            replace = previous[j - 1] + (left_char != right_char)
            value = min(insert, delete, replace)
            current.append(value)
            row_min = min(row_min, value)
        if row_min > limit:
            return limit + 1
        previous = current

    return previous[-1]
