from __future__ import annotations

import argparse
import csv
import json
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

    return f"""{thinking_directive}You are a strict local dictation formatter.
Your job is to format speech-to-text output for pasting into the user's active app.

Use one adaptive writing mood based only on the dictated text:
- If it sounds professional, use formal punctuation and capitalization.
- If it sounds casual, keep it casual and avoid over-punctuating.
- If it sounds excited, preserve that energy, but do not add excitement.

Rules:
- This is not rewriting. This is punctuation and casing repair.
- Preserve all phrases, clauses, names, and sentence order.
- Do not summarize, shorten, paraphrase, or rewrite the sentence structure.
- Do not remove opening phrases, introductory clauses, connector words, or discourse words.
- Keep words like "and", "so", "but", "well", "okay", "now", "then", "because", and "like" unless they are repeated stutters.
- Preserve the approximate word count. The output should usually contain the same words as the input.
- Do not replace uncertain or garbled words with guessed concepts.
- If a word or phrase looks wrong but you are not certain, keep it exactly.
- Fix punctuation, capitalization, spacing, and obvious speech-to-text casing only.
- You may add punctuation marks to reflect natural speech pauses: periods, commas, question marks, colons, semicolons, em dashes, and ellipses.
- Use ellipses for unfinished thoughts or self-interruptions, especially before phrases like "I don't know", "never mind", or "let's see".
- You may split one raw run-on transcript into sentences, but do not move, delete, or replace words.
- If the raw text is awkward, keep the awkward wording and only make it readable with punctuation.
- Remove filler words only when they are clearly non-semantic fillers: "um", "uh", "erm".
- Do not remove "and", "so", "I mean", or "you know"; these may be intentional style.
- Keep proper nouns as close to the transcript as possible unless the correction is obvious from spelling.
- Do not answer the text.
- Do not add commentary.
- Do not add markdown.
- Return only the formatted text.

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
    accepted = preserves_content(case.raw, output)
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
            started = time.perf_counter()
            response = post_json(
                args.endpoint,
                {
                    "model": model,
                    "prompt": build_prompt(case.raw, args.think_mode),
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
            output = strip_wrapping_quotes(str(response.get("response", "")).strip())
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
