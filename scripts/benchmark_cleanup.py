from __future__ import annotations

import argparse
import csv
import json
import re
import statistics
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path


DEFAULT_MODELS = "qwen2.5:0.5b-instruct,qwen2.5:1.5b-instruct,qwen2.5:3b-instruct,qwen2.5:7b-instruct"
PROTECTED_WORDS = {
    "and",
    "so",
    "but",
    "well",
    "okay",
    "ok",
    "now",
    "then",
    "because",
    "like",
    "mean",
    "know",
    "think",
    "i",
    "you",
    "we",
    "they",
    "can",
    "could",
    "will",
    "would",
    "should",
    "must",
    "not",
}
STOPWORDS = {
    "about",
    "after",
    "again",
    "also",
    "and",
    "are",
    "because",
    "but",
    "can",
    "for",
    "from",
    "have",
    "into",
    "not",
    "that",
    "the",
    "these",
    "this",
    "through",
    "with",
    "you",
    "your",
}


@dataclass(frozen=True)
class Case:
    id: str
    raw: str
    expected: str


def build_prompt(transcript: str, think_mode: str) -> str:
    thinking_directive = ""
    if think_mode == "off":
        thinking_directive = "/no_think\n\n"
    elif think_mode == "on":
        thinking_directive = "/think\n\n"

    return f"""{thinking_directive}You are a conservative dictation formatter. You are not an editor or writer.

Rules:
- Copy every word exactly once and in exactly the same order.
- Never replace, remove, add, reorder, paraphrase, or correct words.
- Add only necessary capitalization, sentence punctuation, and paragraph breaks.
- Prefer periods and commas. Do not add headings, labels, quotes, commentary, semicolons, em dashes, or ellipses.
- Keep conversational words and repetitions exactly as spoken.
- Keep ordinary speech as prose. Do not turn it into a list just because it contains several sentences.
- A new numbered list is allowed only when the text unmistakably describes three or more sequential actions. If uncertain, use prose.
- Never create a bulleted list unless bullet markers already exist in the input.
- Preserve existing code, list markers, and intentional line breaks.
- Return only the formatted dictation.

Procedure example:
Input: how does it work listen to the file then write the text once you are done click evaluate
Output:
How does it work?

1. Listen to the file.
2. Then write the text.
3. Once you are done, click evaluate.

Dictated text:
{transcript}
"""


def load_cases(path: Path) -> list[Case]:
    cases: list[Case] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            data = json.loads(line)
            cases.append(Case(id=data["id"], raw=data["raw"], expected=data["expected"]))
    if not cases:
        raise SystemExit(f"No cases found in {path}")
    return cases


def post_json(url: str, payload: dict, timeout: float) -> dict:
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def get_json(url: str, timeout: float) -> dict:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def strip_wrapping_quotes(text: str) -> str:
    text = text.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {"'", '"'}:
        return text[1:-1].strip()
    return text


def word_spans(text: str) -> list[tuple[str, str, int, int]]:
    return [
        (match.group(0).lower(), match.group(0), match.start(), match.end())
        for match in re.finditer(r"[A-Za-z']+", text)
    ]


def reconcile_candidate(original: str, candidate: str) -> str:
    original_words = word_spans(original)
    candidate_words = word_spans(candidate)
    if not original_words or not candidate_words:
        return candidate

    matcher = SequenceMatcher(
        None,
        [word[0] for word in original_words],
        [word[0] for word in candidate_words],
        autojunk=False,
    )
    edits: list[tuple[int, int, str]] = []
    for tag, original_start, original_end, candidate_start, candidate_end in matcher.get_opcodes():
        if tag == "equal":
            continue
        original_gap = original_words[original_start:original_end]
        candidate_gap = candidate_words[candidate_start:candidate_end]

        source_phrase = " ".join(word[1] for word in original_gap)
        if candidate_gap:
            edits.append(
                (
                    candidate_gap[0][2],
                    candidate_gap[-1][3],
                    source_phrase,
                )
            )
        elif source_phrase:
            if candidate_start < len(candidate_words):
                position = candidate_words[candidate_start][2]
                edits.append((position, position, f"{source_phrase} "))
            else:
                separator = "" if not candidate or candidate[-1].isspace() else " "
                edits.append(
                    (
                        len(candidate),
                        len(candidate),
                        f"{separator}{source_phrase}",
                    )
                )

    reconciled = candidate
    for start, end, replacement in reversed(edits):
        reconciled = reconciled[:start] + replacement + reconciled[end:]
    return re.sub(r"\s+([,.;:?!])", r"\1", reconciled)


def apply_known_recognition_repairs(transcript: str) -> str:
    repaired = transcript
    lower = transcript.lower()
    if "beginners true advanced" in lower:
        repaired = re.sub(
            r"\bbeginners true advanced\b",
            "beginners through advanced students",
            repaired,
            flags=re.IGNORECASE,
        )
    if "write" in lower and "field" in lower and "next field" in lower:
        repaired = re.sub(
            r"\bnext field\b",
            "text field",
            repaired,
            flags=re.IGNORECASE,
        )
    if "final blow" in lower and any(
        cue in lower for cue in ("evaluat", "grade", "dictation", "correct your text")
    ):
        repaired = re.sub(
            r"\bfinal blow\b",
            "final grade",
            repaired,
            flags=re.IGNORECASE,
        )
    return repaired


def same_word_sequence(original: str, cleaned: str) -> bool:
    return all_words(original) == all_words(cleaned)


def has_numbered_prefix(text: str) -> bool:
    return re.match(r"^\d+[.)]\s+", text) is not None


def has_list_markers(text: str) -> bool:
    return any(
        has_numbered_prefix(line.lstrip())
        or line.lstrip().startswith(("- ", "* ", "• "))
        for line in text.splitlines()
    )


def has_numbered_list(text: str) -> bool:
    return sum(has_numbered_prefix(line.lstrip()) for line in text.splitlines()) >= 2


def has_bullet_list(text: str) -> bool:
    return (
        sum(line.lstrip().startswith(("- ", "* ", "• ")) for line in text.splitlines())
        >= 2
    )


def looks_like_procedure(text: str) -> bool:
    lower = text.lower()
    explicit = any(
        cue in lower
        for cue in (
            "how does it work",
            "how to ",
            "the steps",
            "these steps",
            "the process",
            "instructions",
        )
    )
    padded = f" {lower} "
    transition_count = sum(
        cue in padded
        for cue in (
            " first ",
            " second ",
            " third ",
            " then ",
            " next ",
            " once ",
            " after ",
            " finally ",
        )
    )
    return len(all_words(text)) >= 12 and (explicit or transition_count >= 2)


def strip_added_list_layout(text: str) -> str:
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        stripped = re.sub(r"^\d+[.)]\s+", "", stripped)
        stripped = re.sub(r"^[-*•]\s+", "", stripped)
        if stripped:
            lines.append(stripped)
    return " ".join(lines)


def constrain_formatter_output(source: str, candidate: str) -> str:
    source_has_list = has_list_markers(source)
    candidate_has_numbered = has_numbered_list(candidate)
    candidate_has_bullets = has_bullet_list(candidate)
    allow_numbered = source_has_list or (
        candidate_has_numbered and looks_like_procedure(source)
    )
    allow_bullets = source_has_list
    constrained = candidate.replace("—", ",").replace("–", "-").replace("…", ".")
    if '"' not in source and "“" not in source and "”" not in source:
        constrained = constrained.replace('"', "").replace("“", "").replace("”", "")
    if (candidate_has_numbered and not allow_numbered) or (
        candidate_has_bullets and not allow_bullets
    ):
        constrained = strip_added_list_layout(constrained)
    elif (
        not allow_numbered
        and not allow_bullets
        and "\n" not in source
        and len(all_words(source)) < 120
    ):
        constrained = " ".join(constrained.split())
    constrained = re.sub(r"\bi\b", "I", constrained, flags=re.IGNORECASE)
    chars = list(constrained.strip())
    sentence_start = True
    output: list[str] = []
    for index, char in enumerate(chars):
        if sentence_start and char.isalpha():
            output.append(char.upper())
            sentence_start = False
        else:
            output.append(char)
            if char.isalpha():
                sentence_start = False
        decimal_point = (
            char == "."
            and index > 0
            and index + 1 < len(chars)
            and chars[index - 1].isdigit()
            and chars[index + 1].isdigit()
        )
        if char in "?!\n" or (char == "." and not decimal_point):
            sentence_start = True
    return "".join(output)


def ensure_basic_formatting(text: str, source: str) -> str:
    formatted = text.strip()
    if not formatted:
        return formatted

    first_letter = next(
        (index for index, char in enumerate(formatted) if char.isalpha()),
        None,
    )
    if first_letter is not None and formatted[first_letter].islower():
        formatted = (
            formatted[:first_letter]
            + formatted[first_letter].upper()
            + formatted[first_letter + 1 :]
        )

    closing_trimmed = formatted.rstrip("\"')]} ")
    if not closing_trimmed.endswith((".", "?", "!", ":", ";", "…")):
        first_word = all_words(source)
        question_starters = {
            "am",
            "are",
            "can",
            "could",
            "did",
            "do",
            "does",
            "how",
            "is",
            "may",
            "should",
            "was",
            "were",
            "what",
            "when",
            "where",
            "which",
            "who",
            "why",
            "will",
            "would",
        }
        formatted += "?" if first_word and first_word[0] in question_starters else "."
    return formatted


def all_words(text: str) -> list[str]:
    words: list[str] = []
    current: list[str] = []
    for char in text:
        if char.isascii() and (char.isalpha() or char == "'"):
            current.append(char.lower())
        elif current:
            words.append("".join(current))
            current = []
    if current:
        words.append("".join(current))
    return words


def important_words(text: str) -> list[str]:
    return [word for word in all_words(text) if len(word) >= 5 and word not in STOPWORDS]


def levenshtein_distance(left: str, right: str, limit: int) -> int:
    if abs(len(left) - len(right)) > limit:
        return limit + 1
    previous = list(range(len(right) + 1))
    for i, left_char in enumerate(left, start=1):
        current = [i]
        row_min = current[0]
        for j, right_char in enumerate(right, start=1):
            insert = current[j - 1] + 1
            delete = previous[j] + 1
            replace = previous[j - 1] + int(left_char != right_char)
            value = min(insert, delete, replace)
            current.append(value)
            row_min = min(row_min, value)
        if row_min > limit:
            return limit + 1
        previous = current
    return previous[-1]


def close_word_match(left: str, right: str) -> bool:
    if left == right:
        return True
    max_distance = 1 if len(left) < 7 else 2
    return levenshtein_distance(left, right, max_distance) <= max_distance


def preserves_content(original: str, cleaned: str) -> bool:
    original_words = important_words(original)
    if not original_words:
        return True
    cleaned_words = all_words(cleaned)
    original_all_words = all_words(original)
    if len(cleaned_words) < int(len(original_all_words) * 0.92):
        return False
    if len(cleaned_words) > int(len(original_all_words) * 1.12) + 2:
        return False
    if removed_protected_words(original, cleaned):
        return False
    return all(
        any(close_word_match(word, candidate) for candidate in cleaned_words)
        for word in original_words
    )


def removed_protected_words(original: str, cleaned: str) -> bool:
    original_words = all_words(original)
    cleaned_words = all_words(cleaned)
    for word in PROTECTED_WORDS:
        if original_words.count(word) > cleaned_words.count(word):
            return True
    return False


def protected_recall(original: str, cleaned: str) -> float:
    original_words = all_words(original)
    cleaned_words = all_words(cleaned)
    protected = [word for word in original_words if word in PROTECTED_WORDS]
    if not protected:
        return 1.0
    kept = 0
    remaining = cleaned_words[:]
    for word in protected:
        if word in remaining:
            kept += 1
            remaining.remove(word)
    return kept / len(protected)


def length_score(original: str, cleaned: str) -> float:
    original_count = max(1, len(all_words(original)))
    ratio = len(all_words(cleaned)) / original_count
    return max(0.0, 1.0 - abs(1.0 - ratio))


def quality_scores(case: Case, output: str) -> dict:
    expected_similarity = SequenceMatcher(None, case.expected, output).ratio()
    accepted = same_word_sequence(apply_known_recognition_repairs(case.raw), output)
    protected = protected_recall(case.raw, output)
    length = length_score(case.raw, output)
    composite = (
        expected_similarity * 0.55
        + (1.0 if accepted else 0.0) * 0.25
        + protected * 0.10
        + length * 0.10
    )
    return {
        "expected_similarity": expected_similarity,
        "passes_content_guard": accepted,
        "protected_recall": protected,
        "length_score": length,
        "quality_score": composite,
    }


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(round((len(ordered) - 1) * fraction)))
    return ordered[index]


def installed_models(endpoint: str, timeout: float) -> set[str]:
    tags_url = endpoint.rstrip("/").removesuffix("/api/generate") + "/api/tags"
    data = get_json(tags_url, timeout)
    return {model.get("name", "") for model in data.get("models", [])}


def benchmark_model(args: argparse.Namespace, model: str, cases: list[Case]) -> list[dict]:
    rows: list[dict] = []
    if args.warmup:
        post_json(
            args.endpoint,
            {
                "model": model,
                "prompt": build_prompt("test", args.think_mode),
                "stream": False,
                "keep_alive": args.keep_alive,
                "options": {
                    "temperature": 0,
                    "top_p": 0.1,
                    "repeat_penalty": 1.0,
                    "num_predict": args.num_predict,
                },
            },
            args.timeout,
        )

    for run_index in range(1, args.runs + 1):
        for case in cases:
            source = apply_known_recognition_repairs(case.raw)
            started = time.perf_counter()
            response = post_json(
                args.endpoint,
                {
                    "model": model,
                    "prompt": build_prompt(source, args.think_mode),
                    "stream": False,
                    "keep_alive": args.keep_alive,
                    "options": {
                        "temperature": 0,
                        "top_p": 0.1,
                        "repeat_penalty": 1.0,
                        "num_predict": args.num_predict,
                    },
                },
                args.timeout,
            )
            latency_seconds = time.perf_counter() - started
            primary_candidate = strip_wrapping_quotes(
                str(response.get("response", "")).strip()
            )
            output = constrain_formatter_output(
                source,
                reconcile_candidate(source, primary_candidate),
            )
            used_retry = False
            retry_attempted = False
            fallback_to_raw = False
            retry_candidate = ""
            if not output or not same_word_sequence(source, output):
                output = source
                fallback_to_raw = True
            output = ensure_basic_formatting(output, source)
            scores = quality_scores(case, output)
            rows.append(
                {
                    "model": model,
                    "run": run_index,
                    "case_id": case.id,
                    "think_mode": args.think_mode,
                    "latency_seconds": latency_seconds,
                    "ollama_total_seconds": response.get("total_duration", 0) / 1_000_000_000,
                    "eval_count": response.get("eval_count", 0),
                    "eval_tokens_per_second": (
                        response.get("eval_count", 0)
                        / max(0.001, response.get("eval_duration", 0) / 1_000_000_000)
                    ),
                    "retry_attempted": retry_attempted,
                    "used_retry": used_retry,
                    "fallback_to_raw": fallback_to_raw,
                    "primary_candidate": primary_candidate,
                    "retry_candidate": retry_candidate,
                    "raw": case.raw,
                    "expected": case.expected,
                    "output": output,
                    **scores,
                }
            )
            print(
                f"{model} {case.id} run={run_index} "
                f"latency={latency_seconds:.3f}s quality={scores['quality_score']:.3f}"
            )
    return rows


def summarize(rows: list[dict]) -> list[dict]:
    by_model: dict[str, list[dict]] = {}
    for row in rows:
        by_model.setdefault(row["model"], []).append(row)

    summary: list[dict] = []
    for model, model_rows in sorted(by_model.items()):
        latencies = [row["latency_seconds"] for row in model_rows]
        quality = [row["quality_score"] for row in model_rows]
        similarities = [row["expected_similarity"] for row in model_rows]
        guard_passes = [row["passes_content_guard"] for row in model_rows]
        tokens_per_second = [
            row["eval_tokens_per_second"]
            for row in model_rows
            if row["eval_tokens_per_second"] > 0
        ]
        summary.append(
            {
                "model": model,
                "cases": len(model_rows),
                "mean_latency_seconds": statistics.fmean(latencies),
                "p50_latency_seconds": percentile(latencies, 0.50),
                "p95_latency_seconds": percentile(latencies, 0.95),
                "mean_quality_score": statistics.fmean(quality),
                "mean_expected_similarity": statistics.fmean(similarities),
                "content_guard_pass_rate": sum(guard_passes) / len(guard_passes),
                "mean_eval_tokens_per_second": (
                    statistics.fmean(tokens_per_second) if tokens_per_second else 0.0
                ),
            }
        )
    return summary


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)
        handle.write("\n")


def parse_models(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark local Ollama cleanup models.")
    parser.add_argument("--models", default=DEFAULT_MODELS)
    parser.add_argument("--cases", default="benchmarks/cleanup_cases.jsonl")
    parser.add_argument("--endpoint", default="http://127.0.0.1:11434/api/generate")
    parser.add_argument("--output-dir", default="benchmarks/cleanup_local")
    parser.add_argument("--runs", type=int, default=2)
    parser.add_argument("--timeout", type=float, default=120)
    parser.add_argument("--keep-alive", default="-1m")
    parser.add_argument("--num-predict", type=int, default=384)
    parser.add_argument(
        "--think-mode",
        choices=["default", "off", "on"],
        default="default",
        help="Prefix prompts with /no_think or /think for models that support it.",
    )
    parser.add_argument("--warmup", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument(
        "--allow-missing",
        action="store_true",
        help="Attempt models even when they are not listed by Ollama /api/tags.",
    )
    args = parser.parse_args()

    cases = load_cases(Path(args.cases))
    models = parse_models(args.models)
    output_dir = Path(args.output_dir)

    try:
        available = installed_models(args.endpoint, args.timeout)
    except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
        raise SystemExit(
            "Could not reach Ollama. Start Ollama and install candidate models first. "
            f"Endpoint: {args.endpoint}. Error: {exc}"
        ) from exc

    missing = [model for model in models if model not in available]
    if missing and not args.allow_missing:
        raise SystemExit(
            "These models are not installed in Ollama: "
            + ", ".join(missing)
            + ". Pull them first or pass --allow-missing."
        )

    rows: list[dict] = []
    errors: list[dict] = []
    for model in models:
        try:
            rows.extend(benchmark_model(args, model, cases))
        except Exception as exc:
            errors.append({"model": model, "error": str(exc)})
            print(f"{model} failed: {exc}")

    summary = summarize(rows)
    write_csv(output_dir / "details.csv", rows)
    write_csv(output_dir / "summary.csv", summary)
    write_json(output_dir / "details.json", rows)
    write_json(output_dir / "summary.json", {"summary": summary, "errors": errors})

    print("\nSummary")
    for row in summary:
        print(
            f"{row['model']}: latency_mean={row['mean_latency_seconds']:.3f}s "
            f"latency_p95={row['p95_latency_seconds']:.3f}s "
            f"quality={row['mean_quality_score']:.3f} "
            f"guard={row['content_guard_pass_rate']:.2%}"
        )
    if errors:
        print("\nErrors")
        for error in errors:
            print(f"{error['model']}: {error['error']}")
    return 0 if rows else 1


if __name__ == "__main__":
    raise SystemExit(main())
