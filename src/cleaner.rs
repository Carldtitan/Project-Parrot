use anyhow::{Context, Result};
use reqwest::blocking::Client;
use serde::{Deserialize, Serialize};
use serde_json::json;

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
            client: Client::new(),
        }
    }

    pub fn clean(&self, transcript: &str) -> Result<String> {
        let prompt = format!(
            r#"You are a strict local dictation formatter.
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
"#
        );

        let response = self
            .client
            .post("http://127.0.0.1:11434/api/generate")
            .json(&OllamaRequest {
                model: &self.model,
                prompt: &prompt,
                stream: false,
                keep_alive: &self.keep_alive,
                options: json!({
                    "temperature": 0,
                    "top_p": 0.1,
                    "repeat_penalty": 1.0,
                    "num_predict": 384
                }),
            })
            .send()
            .context("could not reach Ollama")?
            .error_for_status()
            .context("Ollama returned an error")?
            .json::<OllamaResponse>()
            .context("invalid Ollama response")?;

        let cleaned = strip_wrapping_quotes(response.response.trim());
        if cleaned.is_empty() || !preserves_content(transcript, &cleaned) {
            Ok(transcript.to_string())
        } else {
            Ok(cleaned)
        }
    }

    pub fn warmup(&self) -> Result<()> {
        let _ = self.clean("test")?;
        Ok(())
    }
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
    let protected = [
        "and", "so", "but", "well", "okay", "ok", "now", "then", "because", "like", "mean",
        "know",
    ];
    let original_words = all_words(original);
    let cleaned_words = all_words(cleaned);
    protected.iter().any(|word| {
        original_words.iter().filter(|candidate| *candidate == word).count()
            > cleaned_words.iter().filter(|candidate| *candidate == word).count()
    })
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
