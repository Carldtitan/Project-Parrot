use std::time::Duration;

use anyhow::{Context, Result};
use reqwest::blocking::Client;
use serde::{Deserialize, Serialize};
use serde_json::json;

const PROTECTED_WORDS: [&str; 24] = [
    "and", "so", "but", "well", "okay", "ok", "now", "then", "because", "like", "mean", "know",
    "think", "i", "you", "we", "they", "can", "could", "will", "would", "should", "must", "not",
];

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
        let prompt = build_prompt(transcript, &context);

        let cleaned = restore_dropped_protected_phrases(transcript, &self.generate(&prompt)?);
        if !cleaned.is_empty() && preserves_content(transcript, &cleaned) {
            return Ok(cleaned);
        }

        if !cleaned.is_empty() {
            let retry_prompt = build_preservation_retry_prompt(transcript, &cleaned, &context);
            let retried =
                restore_dropped_protected_phrases(transcript, &self.generate(&retry_prompt)?);
            if !retried.is_empty() && preserves_content(transcript, &retried) {
                return Ok(retried);
            }
        }

        Ok(transcript.to_string())
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
                    "num_predict": 512
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
            });
        }
    }
    if let Some(word_start) = start {
        let surface = &text[word_start..];
        spans.push(WordSpan {
            normalized: surface.to_ascii_lowercase(),
            surface: surface.to_string(),
            start: word_start,
        });
    }
    spans
}

fn restore_dropped_protected_phrases(original: &str, candidate: &str) -> String {
    let original_words = word_spans(original);
    let candidate_words = word_spans(candidate);
    if original_words.is_empty() || candidate_words.is_empty() {
        return candidate.to_string();
    }

    let mut original_index = 0;
    let mut candidate_index = 0;
    let mut insertions: Vec<(usize, String)> = Vec::new();
    const LOOKAHEAD: usize = 8;

    while original_index < original_words.len() && candidate_index < candidate_words.len() {
        if original_words[original_index].normalized == candidate_words[candidate_index].normalized
        {
            original_index += 1;
            candidate_index += 1;
            continue;
        }

        let original_match = original_words
            .iter()
            .enumerate()
            .skip(original_index + 1)
            .take(LOOKAHEAD)
            .find(|(_, word)| word.normalized == candidate_words[candidate_index].normalized)
            .map(|(index, _)| index);
        if let Some(match_index) = original_match {
            let omitted = &original_words[original_index..match_index];
            if !omitted.is_empty()
                && omitted
                    .iter()
                    .all(|word| PROTECTED_WORDS.contains(&word.normalized.as_str()))
            {
                insertions.push((
                    candidate_words[candidate_index].start,
                    format!(
                        "{} ",
                        omitted
                            .iter()
                            .map(|word| word.surface.as_str())
                            .collect::<Vec<_>>()
                            .join(" ")
                    ),
                ));
                original_index = match_index;
                continue;
            }
        }

        let candidate_match = candidate_words
            .iter()
            .enumerate()
            .skip(candidate_index + 1)
            .take(LOOKAHEAD)
            .find(|(_, word)| word.normalized == original_words[original_index].normalized)
            .map(|(index, _)| index);
        if let Some(match_index) = candidate_match {
            candidate_index = match_index;
            continue;
        }

        original_index += 1;
        candidate_index += 1;
    }

    let mut restored = candidate.to_string();
    for (position, phrase) in insertions.into_iter().rev() {
        restored.insert_str(position, &phrase);
    }
    restored
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
        build_preservation_retry_prompt, build_prompt, levenshtein_distance, preserves_content,
        restore_dropped_protected_phrases, strip_wrapping_quotes,
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
    fn restores_only_dropped_protected_phrases_inside_formatted_text() {
        assert_eq!(
            restore_dropped_protected_phrases(
                "Once you are done you can click the button.",
                "3. Once you are done, click the button."
            ),
            "3. Once you are done, you can click the button."
        );
        assert_eq!(
            restore_dropped_protected_phrases(
                "Okay so I think we should ship.",
                "Okay, so we should ship."
            ),
            "Okay, so I think we should ship."
        );
        assert_eq!(
            restore_dropped_protected_phrases("Receive a final blow.", "Receive a final grade."),
            "Receive a final grade."
        );
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
    fn bounded_levenshtein_handles_close_and_distant_words() {
        assert_eq!(levenshtein_distance("project", "projects", 2), 1);
        assert!(levenshtein_distance("project", "parrot", 2) > 2);
    }
}
