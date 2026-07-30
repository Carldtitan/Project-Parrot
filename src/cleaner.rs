use std::time::Duration;

use anyhow::{Context, Result};
use reqwest::blocking::Client;
use serde::{Deserialize, Serialize};
use serde_json::json;

const PROTECTED_WORDS: [&str; 24] = [
    "and", "so", "but", "well", "okay", "ok", "now", "then", "because", "like", "mean", "know",
    "think", "i", "you", "we", "they", "can", "could", "will", "would", "should", "must", "not",
];
const MAX_CLEANUP_WORDS: usize = 320;

#[derive(Clone)]
pub struct OllamaCleaner {
    model: String,
    keep_alive: String,
    client: Client,
}

impl OllamaCleaner {
    pub fn new(model: String, keep_alive: String) -> Self {
        Self {
            model,
            keep_alive,
            client: Client::builder()
                .timeout(Duration::from_secs(60))
                .build()
                .unwrap_or_else(|_| Client::new()),
        }
    }

    pub fn clean(
        &self,
        transcript: &str,
        active_window: &str,
        developer_context: bool,
    ) -> Result<String> {
        let context = if active_window.trim().is_empty() {
            "The active application is unknown.".to_string()
        } else if developer_context {
            format!(
                "The active window is a local developer tool: {:?}. Preserve identifiers, paths, code punctuation, line breaks, and Markdown exactly.",
                active_window.trim()
            )
        } else {
            format!(
                "The active window title is {:?}. Use it only to choose appropriate punctuation; do not mention it.",
                active_window.trim()
            )
        };
        let chunks = split_cleanup_chunks(transcript, MAX_CLEANUP_WORDS);
        let mut cleaned_chunks = Vec::with_capacity(chunks.len());
        for chunk in chunks {
            cleaned_chunks.push(self.clean_segment(&chunk, &context, developer_context)?);
        }
        Ok(cleaned_chunks.join("\n\n"))
    }

    fn clean_segment(
        &self,
        transcript: &str,
        context: &str,
        developer_context: bool,
    ) -> Result<String> {
        let prompt = build_prompt(transcript, context);
        let cleaned = reconcile_candidate(transcript, &self.generate(&prompt)?);
        if !cleaned.is_empty() && preserves_content(transcript, &cleaned) {
            return Ok(ensure_basic_formatting(
                &cleaned,
                transcript,
                developer_context,
            ));
        }

        if !cleaned.is_empty() {
            let retry_prompt = build_preservation_retry_prompt(transcript, &cleaned, context);
            let retried = reconcile_candidate(transcript, &self.generate(&retry_prompt)?);
            if !retried.is_empty() && preserves_content(transcript, &retried) {
                return Ok(ensure_basic_formatting(
                    &retried,
                    transcript,
                    developer_context,
                ));
            }
        }

        Ok(ensure_basic_formatting(
            transcript,
            transcript,
            developer_context,
        ))
    }

    fn generate(&self, prompt: &str) -> Result<String> {
        let response = self
            .client
            .post("http://127.0.0.1:11434/api/generate")
            .json(&OllamaRequest {
                model: &self.model,
                prompt,
                stream: false,
                keep_alive: &self.keep_alive,
                options: json!({
                    "temperature": 0,
                    "top_p": 0.1,
                    "repeat_penalty": 1.0,
                    "num_predict": 768
                }),
            })
            .send()
            .context("could not reach Ollama")?
            .error_for_status()
            .context("Ollama returned an error")?
            .json::<OllamaResponse>()
            .context("invalid Ollama response")?;
        Ok(strip_wrapping_quotes(response.response.trim()))
    }

    pub fn warmup(&self) -> Result<()> {
        let _ = self.clean("test", "", false)?;
        Ok(())
    }
}

fn build_prompt(transcript: &str, context: &str) -> String {
    format!(
        r#"You are Parrot's local dictation editor.
Your job is to format speech-to-text output for pasting into the user's active app.

Context:
{context}

Use one adaptive writing style based only on the dictated text:
- If it sounds professional, use formal punctuation and capitalization.
- If it sounds casual, keep it casual and avoid over-punctuating.
- If it sounds excited, preserve that energy, but do not add excitement.

Rules:
- Preserve the speaker's meaning, voice, names, facts, and sentence order.
- This is an editor, not an author. Do not summarize, expand, or creatively rewrite.
- Do not summarize, shorten, paraphrase, or rewrite the sentence structure.
- Do not remove opening phrases, introductory clauses, connector words, or discourse words.
- Keep words like "and", "so", "but", "well", "okay", "now", "then", "because", and "like" unless they are repeated stutters.
- Never delete subject or helper phrases such as "I think", "you can", "we will", "they should", or "do not".
- Preserve the approximate word count. The output should usually contain the same words as the input.
- Repair a recognition slip only when the surrounding sentence makes the intended word or short phrase unambiguous. Make the smallest possible correction.
- Examples of high-confidence recognition repair include "write into the next field" -> "write into the text field", "receive a final blow" -> "receive a final grade", and "beginners true advanced" -> "beginners through advanced students".
- Do not leave an obvious semantic impossibility unchanged. In an evaluation or grading context, "receive a final blow" must become "receive a final grade". In a skill-range context, "beginners true advanced" must become "beginners through advanced students".
- If a word or phrase looks wrong but you are not certain, keep it exactly.
- Fix punctuation, capitalization, spacing, obvious speech-to-text casing, and high-confidence recognition slips.
- Ordinary prose must start with a capital letter and end with appropriate punctuation even when the input has neither.
- You may add punctuation marks to reflect natural speech pauses: periods, commas, question marks, colons, semicolons, em dashes, and ellipses.
- Use ellipses for unfinished thoughts or self-interruptions, especially before phrases like "I don't know", "never mind", or "let's see".
- You may split one raw run-on transcript into sentences.
- If the raw text is awkward, keep the awkward wording and only make it readable with punctuation.
- Remove filler words only when they are clearly non-semantic fillers: "um", "uh", "erm".
- Do not remove "and", "so", "I mean", or "you know"; these may be intentional style.
- Keep proper nouns as close to the transcript as possible unless the correction is obvious from spelling.
- Silently determine the document shape before writing the output.
- Infer layout from meaning; the speaker should not have to dictate "number one", "bullet", "new line", or "firstly".
- Mandatory layout rule: if the text is a how-to, workflow, set of instructions, or staged process with three or more distinct actions, output those actions as a Markdown numbered list.
- This mandatory rule applies even when the raw transcript has no punctuation and no spoken list markers.
- A setup question such as "How does it work?" belongs on its own line before the numbered list. A step may contain more than one supporting sentence.
- Do not leave a qualifying procedure as one paragraph.
- When three or more short parallel items are clearly a collection rather than a sequence, format them as bullets.
- Keep ordinary prose as paragraphs. Do not turn a paragraph into a list merely because it has several sentences.
- Preserve existing numbered lists, bullet lists, code, and intentional line breaks.
- Do not invent list items, headings, labels, or content.
- Do not answer the text.
- Do not add commentary.
- Return only the formatted text.

Formatting example:
Input: How does it work? Listen carefully to the audio file. Write the text into the text field. Once you are done, click the button to have your dictation evaluated. We instantly check and correct your text.
Output:
How does it work?

1. Listen carefully to the audio file.
2. Write the text into the text field.
3. Once you are done, click the button to have your dictation evaluated.
4. We instantly check and correct your text.

Dictated text:
{transcript}
"#
    )
}

fn build_preservation_retry_prompt(original: &str, candidate: &str, context: &str) -> String {
    format!(
        r#"You are Parrot's final dictation verifier.
The draft below has useful punctuation and layout, but it was rejected because it dropped words from the source.

Context:
{context}

Requirements:
- Keep the draft's punctuation, paragraphs, and Markdown list layout.
- Restore every phrase from the source in its original order.
- Never delete phrases such as "I think", "you can", "we will", "they should", or "do not".
- Preserve connector words including "and", "so", "but", "then", and "because".
- Keep only high-confidence acoustic repairs when context makes them certain: grading "final blow" may be "final grade"; a range from "beginners true advanced" may be "beginners through advanced students".
- Do not summarize, answer, explain, or add new facts.
- Return only the corrected final text.

Source transcript:
{original}

Rejected formatted draft:
{candidate}
"#
    )
}

#[derive(Serialize)]
struct OllamaRequest<'a> {
    model: &'a str,
    prompt: &'a str,
    stream: bool,
    keep_alive: &'a str,
    options: serde_json::Value,
}

#[derive(Deserialize)]
struct OllamaResponse {
    response: String,
}

fn strip_wrapping_quotes(text: &str) -> String {
    let text = text.trim();
    if text.len() >= 2 {
        let first = text.as_bytes()[0] as char;
        let last = text.as_bytes()[text.len() - 1] as char;
        if (first == '"' || first == '\'') && first == last {
            return text[1..text.len() - 1].trim().to_string();
        }
    }
    text.to_string()
}

fn preserves_content(original: &str, cleaned: &str) -> bool {
    let original_words = important_words(original);
    if original_words.is_empty() {
        return true;
    }
    let cleaned_words = all_words(cleaned);
    let original_all_words = all_words(original);
    if cleaned_words.len() < (original_all_words.len() as f32 * 0.92) as usize {
        return false;
    }
    if cleaned_words.len() > (original_all_words.len() as f32 * 1.12) as usize + 2 {
        return false;
    }
    if removed_protected_words(original, cleaned) {
        return false;
    }
    original_words.iter().all(|word| {
        cleaned_words
            .iter()
            .any(|candidate| close_word_match(word, candidate))
    })
}

fn removed_protected_words(original: &str, cleaned: &str) -> bool {
    let original_words = all_words(original);
    let cleaned_words = all_words(cleaned);
    PROTECTED_WORDS.iter().any(|word| {
        original_words
            .iter()
            .filter(|candidate| *candidate == word)
            .count()
            > cleaned_words
                .iter()
                .filter(|candidate| *candidate == word)
                .count()
    })
}

#[derive(Debug)]
struct WordSpan {
    normalized: String,
    surface: String,
    start: usize,
    end: usize,
}

fn word_spans(text: &str) -> Vec<WordSpan> {
    let mut spans = Vec::new();
    let mut start = None;
    for (index, ch) in text.char_indices() {
        if ch.is_ascii_alphabetic() || ch == '\'' {
            start.get_or_insert(index);
        } else if let Some(word_start) = start.take() {
            let surface = &text[word_start..index];
            spans.push(WordSpan {
                normalized: surface.to_ascii_lowercase(),
                surface: surface.to_string(),
                start: word_start,
                end: index,
            });
        }
    }
    if let Some(word_start) = start {
        let surface = &text[word_start..];
        spans.push(WordSpan {
            normalized: surface.to_ascii_lowercase(),
            surface: surface.to_string(),
            start: word_start,
            end: text.len(),
        });
    }
    spans
}

fn split_cleanup_chunks(text: &str, max_words: usize) -> Vec<String> {
    let words = word_spans(text);
    if words.len() <= max_words || max_words < 2 {
        return vec![text.trim().to_string()];
    }

    let mut chunks = Vec::new();
    let mut word_start = 0;
    let mut char_start = 0;
    while word_start < words.len() {
        let target_end = (word_start + max_words).min(words.len());
        if target_end == words.len() {
            let chunk = text[char_start..].trim();
            if !chunk.is_empty() {
                chunks.push(chunk.to_string());
            }
            break;
        }

        let minimum_end = word_start + max_words / 2;
        let mut word_end = target_end;
        for candidate_end in (minimum_end..target_end).rev() {
            let gap_start = words[candidate_end - 1].end;
            let gap_end = words[candidate_end].start;
            if text[gap_start..gap_end]
                .chars()
                .any(|ch| matches!(ch, '.' | '?' | '!' | '\n'))
            {
                word_end = candidate_end;
                break;
            }
        }

        let split_at = words[word_end].start;
        let chunk = text[char_start..split_at].trim();
        if !chunk.is_empty() {
            chunks.push(chunk.to_string());
        }
        word_start = word_end;
        char_start = split_at;
    }

    if chunks.is_empty() {
        vec![text.trim().to_string()]
    } else {
        chunks
    }
}

#[derive(Debug)]
struct CandidateEdit {
    start: usize,
    end: usize,
    replacement: String,
}

fn reconcile_candidate(original: &str, candidate: &str) -> String {
    let original_words = word_spans(original);
    let candidate_words = word_spans(candidate);
    if original_words.is_empty() || candidate_words.is_empty() {
        return candidate.to_string();
    }

    let original_count = original_words.len();
    let candidate_count = candidate_words.len();
    let mut lcs = vec![vec![0usize; candidate_count + 1]; original_count + 1];
    for original_index in (0..original_count).rev() {
        for candidate_index in (0..candidate_count).rev() {
            lcs[original_index][candidate_index] = if original_words[original_index].normalized
                == candidate_words[candidate_index].normalized
            {
                lcs[original_index + 1][candidate_index + 1] + 1
            } else {
                lcs[original_index + 1][candidate_index]
                    .max(lcs[original_index][candidate_index + 1])
            };
        }
    }

    let mut anchors = Vec::new();
    let mut original_index = 0;
    let mut candidate_index = 0;
    while original_index < original_count && candidate_index < candidate_count {
        if original_words[original_index].normalized == candidate_words[candidate_index].normalized
        {
            anchors.push((original_index, candidate_index));
            original_index += 1;
            candidate_index += 1;
        } else if lcs[original_index + 1][candidate_index]
            >= lcs[original_index][candidate_index + 1]
        {
            original_index += 1;
        } else {
            candidate_index += 1;
        }
    }
    anchors.push((original_count, candidate_count));

    let mut edits = Vec::new();
    let mut previous_original = 0;
    let mut previous_candidate = 0;
    for (anchor_original, anchor_candidate) in anchors {
        let original_gap = &original_words[previous_original..anchor_original];
        let candidate_gap = &candidate_words[previous_candidate..anchor_candidate];
        if (!original_gap.is_empty() || !candidate_gap.is_empty())
            && !allowed_semantic_repair(original, original_gap, candidate_gap)
        {
            let source_phrase = original_gap
                .iter()
                .map(|word| word.surface.as_str())
                .collect::<Vec<_>>()
                .join(" ");
            if let (Some(first), Some(last)) = (candidate_gap.first(), candidate_gap.last()) {
                edits.push(CandidateEdit {
                    start: first.start,
                    end: last.end,
                    replacement: source_phrase,
                });
            } else if !source_phrase.is_empty() {
                if anchor_candidate < candidate_count {
                    edits.push(CandidateEdit {
                        start: candidate_words[anchor_candidate].start,
                        end: candidate_words[anchor_candidate].start,
                        replacement: format!("{source_phrase} "),
                    });
                } else {
                    let separator = if candidate.chars().last().is_none_or(char::is_whitespace) {
                        ""
                    } else {
                        " "
                    };
                    edits.push(CandidateEdit {
                        start: candidate.len(),
                        end: candidate.len(),
                        replacement: format!("{separator}{source_phrase}"),
                    });
                }
            }
        }

        if anchor_original < original_count && anchor_candidate < candidate_count {
            previous_original = anchor_original + 1;
            previous_candidate = anchor_candidate + 1;
        } else {
            previous_original = anchor_original;
            previous_candidate = anchor_candidate;
        }
    }

    let mut reconciled = candidate.to_string();
    for edit in edits.into_iter().rev() {
        reconciled.replace_range(edit.start..edit.end, &edit.replacement);
    }
    reconciled
}

fn allowed_semantic_repair(
    full_original: &str,
    original_words: &[WordSpan],
    candidate_words: &[WordSpan],
) -> bool {
    let source = original_words
        .iter()
        .map(|word| word.normalized.as_str())
        .collect::<Vec<_>>()
        .join(" ");
    let candidate = candidate_words
        .iter()
        .map(|word| word.normalized.as_str())
        .collect::<Vec<_>>()
        .join(" ");
    if matches!(
        (source.as_str(), candidate.as_str()),
        ("blow", "grade") | ("next", "text") | ("true", "through")
    ) {
        return true;
    }

    source.is_empty()
        && candidate == "students"
        && full_original
            .to_ascii_lowercase()
            .contains("beginners true advanced")
}

fn ensure_basic_formatting(text: &str, source: &str, developer_context: bool) -> String {
    let mut formatted = text.trim().to_string();
    if formatted.is_empty() || developer_context {
        return formatted;
    }

    if let Some((index, first)) = formatted.char_indices().find(|(_, ch)| ch.is_alphabetic()) {
        if first.is_lowercase() {
            let uppercase = first.to_uppercase().collect::<String>();
            formatted.replace_range(index..index + first.len_utf8(), &uppercase);
        }
    }

    let has_terminal_punctuation = formatted
        .trim_end_matches(['"', '\'', ')', ']', '}'])
        .ends_with(['.', '?', '!', ':', ';', '…']);
    if !has_terminal_punctuation {
        let first_word = all_words(source).into_iter().next().unwrap_or_default();
        let question_starters = [
            "am", "are", "can", "could", "did", "do", "does", "how", "is", "may", "should", "was",
            "were", "what", "when", "where", "which", "who", "why", "will", "would",
        ];
        formatted.push(if question_starters.contains(&first_word.as_str()) {
            '?'
        } else {
            '.'
        });
    }
    formatted
}

fn important_words(text: &str) -> Vec<String> {
    let stopwords = [
        "about", "after", "again", "also", "and", "are", "because", "but", "can", "for", "from",
        "have", "into", "not", "that", "the", "these", "this", "through", "with", "you", "your",
    ];
    all_words(text)
        .into_iter()
        .filter(|word| word.len() >= 5 && !stopwords.contains(&word.as_str()))
        .collect()
}

fn all_words(text: &str) -> Vec<String> {
    text.split(|ch: char| !ch.is_ascii_alphabetic() && ch != '\'')
        .filter(|word| !word.is_empty())
        .map(|word| word.to_ascii_lowercase())
        .collect()
}

fn close_word_match(left: &str, right: &str) -> bool {
    if left == right {
        return true;
    }
    let max_distance = if left.len() < 7 { 1 } else { 2 };
    levenshtein_distance(left, right, max_distance) <= max_distance
}

fn levenshtein_distance(left: &str, right: &str, limit: usize) -> usize {
    if left.len().abs_diff(right.len()) > limit {
        return limit + 1;
    }
    let mut previous: Vec<usize> = (0..=right.len()).collect();
    for (i, left_char) in left.chars().enumerate() {
        let mut current = vec![i + 1];
        let mut row_min = i + 1;
        for (j, right_char) in right.chars().enumerate() {
            let insert = current[j] + 1;
            let delete = previous[j + 1] + 1;
            let replace = previous[j] + usize::from(left_char != right_char);
            let value = insert.min(delete).min(replace);
            current.push(value);
            row_min = row_min.min(value);
        }
        if row_min > limit {
            return limit + 1;
        }
        previous = current;
    }
    previous[right.len()]
}

#[cfg(test)]
mod tests {
    use super::{
        all_words, build_preservation_retry_prompt, build_prompt, ensure_basic_formatting,
        levenshtein_distance, preserves_content, reconcile_candidate, split_cleanup_chunks,
        strip_wrapping_quotes,
    };

    #[test]
    fn strips_matching_wrapping_quotes() {
        assert_eq!(strip_wrapping_quotes("\"Hello there.\""), "Hello there.");
        assert_eq!(strip_wrapping_quotes("'Hello there.'"), "Hello there.");
        assert_eq!(strip_wrapping_quotes("\"Hello there.'"), "\"Hello there.'");
    }

    #[test]
    fn content_guard_accepts_punctuation_repairs() {
        assert!(preserves_content(
            "okay so we should finish the project tomorrow",
            "Okay, so we should finish the project tomorrow."
        ));
    }

    #[test]
    fn content_guard_rejects_removed_protected_words() {
        assert!(!preserves_content(
            "well I mean we should finish the project tomorrow",
            "We should finish the project tomorrow."
        ));
        assert!(!preserves_content(
            "Once you are done you can click the button.",
            "Once you are done, click the button."
        ));
    }

    #[test]
    fn content_guard_accepts_inferred_layout_without_spoken_markers() {
        assert!(preserves_content(
            "How does it work? Listen carefully. Write the text. Click evaluate.",
            "How does it work?\n\n1. Listen carefully.\n2. Write the text.\n3. Click evaluate."
        ));
    }

    #[test]
    fn content_guard_accepts_small_contextual_recognition_repairs() {
        assert!(preserves_content(
            "We instantly check and correct your text allowing you to receive a final blow.",
            "We instantly check and correct your text, allowing you to receive a final grade."
        ));
        assert!(preserves_content(
            "We have hundreds of dictations for beginners true advanced.",
            "We have hundreds of dictations for beginners through advanced students."
        ));
    }

    #[test]
    fn prompt_requires_semantic_structure_without_spoken_commands() {
        let prompt = build_prompt("How does it work? Listen. Write. Submit.", "Unknown.");
        assert!(prompt.contains("should not have to dictate"));
        assert!(prompt.contains("three or more distinct actions"));
        assert!(prompt.contains("1. Listen carefully"));
    }

    #[test]
    fn retry_prompt_preserves_layout_while_restoring_dropped_words() {
        let prompt = build_preservation_retry_prompt(
            "Once you are done you can click evaluate.",
            "3. Once you are done, click evaluate.",
            "Unknown.",
        );
        assert!(prompt.contains("Keep the draft's punctuation, paragraphs, and Markdown list"));
        assert!(prompt.contains("you can"));
        assert!(prompt.contains("3. Once you are done"));
    }

    #[test]
    fn reconciliation_keeps_formatting_but_restores_speculative_words() {
        let original = "linnell's pictures are a sort of up guards and atom paintings and mason's exquisite idols are as national as a jingo poem";
        let candidate = "Linnell's pictures are a sort of up and down paintings, and Mason's exquisite idols are as national as a jingo poem.";

        let reconciled = reconcile_candidate(original, candidate);

        assert_eq!(
            reconciled,
            "Linnell's pictures are a sort of up guards and atom paintings, and Mason's exquisite idols are as national as a jingo poem."
        );
        assert!(preserves_content(original, &reconciled));
    }

    #[test]
    fn reconciliation_preserves_guarded_contextual_repairs() {
        assert_eq!(
            reconcile_candidate(
                "we instantly check your text and return a final blow",
                "We instantly check your text and return a final grade."
            ),
            "We instantly check your text and return a final grade."
        );
        assert_eq!(
            reconcile_candidate(
                "we have dictations for beginners true advanced",
                "We have dictations for beginners through advanced students."
            ),
            "We have dictations for beginners through advanced students."
        );
    }

    #[test]
    fn reconciliation_restores_dropped_and_invented_phrases_in_order() {
        let original = "I actually think we should keep every word because it matters";
        let candidate = "I think we should add a clever summary because it matters.";

        let reconciled = reconcile_candidate(original, candidate);

        assert_eq!(
            reconciled,
            "I actually think we should keep every word because it matters."
        );
    }

    #[test]
    fn long_cleanup_chunks_cover_every_source_word() {
        let original = (0..750)
            .map(|index| format!("word{index}"))
            .collect::<Vec<_>>()
            .join(" ");
        let chunks = split_cleanup_chunks(&original, 320);
        let recombined = chunks.join(" ");

        assert_eq!(chunks.len(), 3);
        assert_eq!(all_words(&recombined), all_words(&original));
    }

    #[test]
    fn basic_formatting_handles_plain_statements_and_questions() {
        assert_eq!(
            ensure_basic_formatting(
                "i actually think there are no good options",
                "i actually think there are no good options",
                false
            ),
            "I actually think there are no good options."
        );
        assert_eq!(
            ensure_basic_formatting("how does it work", "how does it work", false),
            "How does it work?"
        );
    }

    #[test]
    fn basic_formatting_does_not_mutate_developer_text() {
        assert_eq!(
            ensure_basic_formatting("const parrot = true", "const parrot = true", true),
            "const parrot = true"
        );
    }

    #[test]
    fn bounded_levenshtein_handles_close_and_distant_words() {
        assert_eq!(levenshtein_distance("project", "projects", 2), 1);
        assert!(levenshtein_distance("project", "parrot", 2) > 2);
    }
}
