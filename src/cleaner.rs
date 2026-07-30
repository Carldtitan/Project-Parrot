use std::time::Duration;

use anyhow::{Context, Result};
use regex::Regex;
use reqwest::blocking::Client;
use serde::{Deserialize, Serialize};
use serde_json::json;

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
        // Recognition repair is deliberately deterministic and tiny. Qwen is
        // never allowed to decide which words the user meant.
        let repaired = apply_known_recognition_repairs(transcript);
        let chunks = split_cleanup_chunks(&repaired, MAX_CLEANUP_WORDS);
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
        let generated = self.generate(&prompt)?;
        let cleaned = constrain_formatter_output(
            transcript,
            &reconcile_candidate(transcript, &generated),
            developer_context,
        );
        if !cleaned.is_empty() && same_word_sequence(transcript, &cleaned) {
            return Ok(ensure_basic_formatting(
                &cleaned,
                transcript,
                developer_context,
            ));
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
        r#"You are a conservative dictation formatter. You are not an editor or writer.

Context:
{context}

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

fn apply_known_recognition_repairs(transcript: &str) -> String {
    let mut repaired = transcript.to_string();
    let lower = transcript.to_ascii_lowercase();

    if lower.contains("beginners true advanced") {
        repaired = replace_case_insensitive(
            &repaired,
            r"\bbeginners true advanced\b",
            "beginners through advanced students",
        );
    }
    if lower.contains("write") && lower.contains("field") && lower.contains("next field") {
        repaired = replace_case_insensitive(&repaired, r"\bnext field\b", "text field");
    }
    if lower.contains("final blow")
        && ["evaluat", "grade", "dictation", "correct your text"]
            .iter()
            .any(|cue| lower.contains(cue))
    {
        repaired = replace_case_insensitive(&repaired, r"\bfinal blow\b", "final grade");
    }

    repaired
}

fn replace_case_insensitive(text: &str, pattern: &str, replacement: &str) -> String {
    Regex::new(&format!("(?i){pattern}"))
        .map(|regex| regex.replace_all(text, replacement).into_owned())
        .unwrap_or_else(|_| text.to_string())
}

fn same_word_sequence(original: &str, cleaned: &str) -> bool {
    all_words(original) == all_words(cleaned)
}

fn constrain_formatter_output(source: &str, candidate: &str, developer_context: bool) -> String {
    if developer_context {
        return candidate.trim().to_string();
    }

    let source_has_list = has_list_markers(source);
    let candidate_has_numbered_list = has_numbered_list(candidate);
    let candidate_has_bullets = has_bullet_list(candidate);
    let allow_numbered_list =
        source_has_list || (candidate_has_numbered_list && looks_like_procedure(source));
    let allow_bullets = source_has_list;

    let mut constrained = candidate
        .replace('—', ",")
        .replace('–', "-")
        .replace('…', ".");
    if !source.contains('"') && !source.contains('“') && !source.contains('”') {
        constrained.retain(|ch| ch != '"' && ch != '“' && ch != '”');
    }

    if (candidate_has_numbered_list && !allow_numbered_list)
        || (candidate_has_bullets && !allow_bullets)
    {
        constrained = strip_added_list_layout(&constrained);
    } else if !allow_numbered_list
        && !allow_bullets
        && !source.contains('\n')
        && all_words(source).len() < 120
    {
        constrained = constrained.split_whitespace().collect::<Vec<_>>().join(" ");
    }

    capitalize_sentence_starts(&replace_standalone_i(constrained.trim()))
}

fn replace_standalone_i(text: &str) -> String {
    Regex::new(r"(?i)\bi\b")
        .map(|regex| regex.replace_all(text, "I").into_owned())
        .unwrap_or_else(|_| text.to_string())
}

fn capitalize_sentence_starts(text: &str) -> String {
    let chars = text.chars().collect::<Vec<_>>();
    let mut result = String::with_capacity(text.len());
    let mut sentence_start = true;

    for (index, ch) in chars.iter().copied().enumerate() {
        if sentence_start && ch.is_alphabetic() {
            result.extend(ch.to_uppercase());
            sentence_start = false;
        } else {
            result.push(ch);
            if ch.is_alphabetic() {
                sentence_start = false;
            }
        }

        if matches!(ch, '?' | '!' | '\n')
            || (ch == '.'
                && !(index > 0
                    && index + 1 < chars.len()
                    && chars[index - 1].is_ascii_digit()
                    && chars[index + 1].is_ascii_digit()))
        {
            sentence_start = true;
        }
    }

    result
}

fn has_list_markers(text: &str) -> bool {
    text.lines().any(|line| {
        let trimmed = line.trim_start();
        has_numbered_prefix(trimmed)
            || trimmed.starts_with("- ")
            || trimmed.starts_with("* ")
            || trimmed.starts_with("• ")
    })
}

fn has_numbered_list(text: &str) -> bool {
    text.lines()
        .filter(|line| has_numbered_prefix(line.trim_start()))
        .count()
        >= 2
}

fn has_bullet_list(text: &str) -> bool {
    text.lines()
        .filter(|line| {
            let trimmed = line.trim_start();
            trimmed.starts_with("- ") || trimmed.starts_with("* ") || trimmed.starts_with("• ")
        })
        .count()
        >= 2
}

fn has_numbered_prefix(text: &str) -> bool {
    let digits = text.chars().take_while(|ch| ch.is_ascii_digit()).count();
    digits > 0
        && text
            .chars()
            .nth(digits)
            .is_some_and(|ch| ch == '.' || ch == ')')
        && text
            .chars()
            .nth(digits + 1)
            .is_some_and(char::is_whitespace)
}

fn looks_like_procedure(text: &str) -> bool {
    let lower = text.to_ascii_lowercase();
    let explicit = [
        "how does it work",
        "how to ",
        "the steps",
        "these steps",
        "the process",
        "instructions",
    ]
    .iter()
    .any(|cue| lower.contains(cue));
    let transition_count = [
        " first ",
        " second ",
        " third ",
        " then ",
        " next ",
        " once ",
        " after ",
        " finally ",
    ]
    .iter()
    .filter(|cue| format!(" {lower} ").contains(**cue))
    .count();
    all_words(text).len() >= 12 && (explicit || transition_count >= 2)
}

fn strip_added_list_layout(text: &str) -> String {
    text.lines()
        .map(|line| {
            let trimmed = line.trim();
            if has_numbered_prefix(trimmed) {
                let digits = trimmed.chars().take_while(|ch| ch.is_ascii_digit()).count();
                trimmed[digits + 1..].trim_start()
            } else {
                trimmed
                    .strip_prefix("- ")
                    .or_else(|| trimmed.strip_prefix("* "))
                    .or_else(|| trimmed.strip_prefix("• "))
                    .unwrap_or(trimmed)
            }
        })
        .filter(|line| !line.is_empty())
        .collect::<Vec<_>>()
        .join(" ")
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
        if !original_gap.is_empty() || !candidate_gap.is_empty() {
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
    Regex::new(r"\s+([,.;:?!])")
        .map(|regex| regex.replace_all(&reconciled, "$1").into_owned())
        .unwrap_or(reconciled)
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

fn all_words(text: &str) -> Vec<String> {
    text.split(|ch: char| !ch.is_ascii_alphabetic() && ch != '\'')
        .filter(|word| !word.is_empty())
        .map(|word| word.to_ascii_lowercase())
        .collect()
}

#[cfg(test)]
mod tests {
    use super::{
        all_words, apply_known_recognition_repairs, build_prompt, constrain_formatter_output,
        ensure_basic_formatting, reconcile_candidate, same_word_sequence, split_cleanup_chunks,
        strip_wrapping_quotes,
    };

    #[test]
    fn strips_matching_wrapping_quotes() {
        assert_eq!(strip_wrapping_quotes("\"Hello there.\""), "Hello there.");
        assert_eq!(strip_wrapping_quotes("'Hello there.'"), "Hello there.");
        assert_eq!(strip_wrapping_quotes("\"Hello there.'"), "\"Hello there.'");
    }

    #[test]
    fn exact_guard_accepts_only_the_same_spoken_words() {
        assert!(same_word_sequence(
            "okay so we should finish the project tomorrow",
            "Okay, so we should finish the project tomorrow."
        ));
        assert!(!same_word_sequence(
            "well I mean we should finish the project tomorrow",
            "We should finish the project tomorrow."
        ));
        assert!(!same_word_sequence(
            "Once you are done you can click the button.",
            "Once you are done, click the button."
        ));
    }

    #[test]
    fn prompt_limits_qwen_to_conservative_formatting() {
        let prompt = build_prompt("How does it work? Listen. Write. Submit.", "Unknown.");
        assert!(prompt.contains("Copy every word exactly once"));
        assert!(prompt.contains("Never replace, remove, add, reorder"));
        assert!(prompt.contains("If uncertain, use prose"));
        assert!(!prompt.contains("recognition slip"));
        assert!(!prompt.contains("adaptive writing style"));
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
        assert!(same_word_sequence(original, &reconciled));
    }

    #[test]
    fn qwen_cannot_make_semantic_repairs_or_rewrites() {
        assert_eq!(
            reconcile_candidate(
                "we instantly check your text and return a final blow",
                "We instantly check your text and return a final grade."
            ),
            "We instantly check your text and return a final blow."
        );
        assert_eq!(
            reconcile_candidate(
                "we have dictations for beginners true advanced",
                "We have dictations for beginners through advanced students."
            ),
            "We have dictations for beginners true advanced."
        );
    }

    #[test]
    fn known_recognition_repairs_are_narrow_and_deterministic() {
        assert_eq!(
            apply_known_recognition_repairs(
                "We instantly correct your dictation and return a final blow."
            ),
            "We instantly correct your dictation and return a final grade."
        );
        assert_eq!(
            apply_known_recognition_repairs("We have dictations for beginners true advanced."),
            "We have dictations for beginners through advanced students."
        );
        assert_eq!(
            apply_known_recognition_repairs("The boxer delivered the final blow."),
            "The boxer delivered the final blow."
        );
    }

    #[test]
    fn ordinary_speech_cannot_be_turned_into_an_ai_style_list() {
        let source = "it is buggy and qwen does too much and the final words hardly get captured";
        let candidate =
            "It is buggy.\n\n1. And Qwen does too much.\n2. And the final words hardly get captured.";
        assert_eq!(
            constrain_formatter_output(source, candidate, false),
            "It is buggy. And Qwen does too much. And the final words hardly get captured."
        );
    }

    #[test]
    fn unmistakable_process_can_still_be_formatted_as_steps() {
        let source = "how does it work listen to the file then write the text once you are done click evaluate and finally review the grade";
        let candidate = "How does it work?\n\n1. Listen to the file.\n2. Then write the text.\n3. Once you are done, click evaluate.\n4. And finally review the grade.";
        assert_eq!(
            constrain_formatter_output(source, candidate, false),
            candidate
        );
    }

    #[test]
    fn short_prose_does_not_get_fragmented_into_ai_paragraphs() {
        let source = "I think this is useful but I do not want every sentence to look dramatic";
        let candidate =
            "I think this is useful.\n\nBut I do not want every sentence to look dramatic.";
        assert_eq!(
            constrain_formatter_output(source, candidate, false),
            "I think this is useful. But I do not want every sentence to look dramatic."
        );
    }

    #[test]
    fn formatter_cannot_add_stylized_quotes_and_leaves_decimal_casing_alone() {
        let source = "he says like a shampooer next man and i waited 1.5 seconds";
        let candidate = "He says, \"Like a shampooer. Next man.\" And i waited 1.5 seconds.";
        assert_eq!(
            constrain_formatter_output(source, candidate, false),
            "He says, Like a shampooer. Next man. And I waited 1.5 seconds."
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
}
