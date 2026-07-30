use std::{fs, path::Path};

use regex::{Captures, Regex};
use serde::Deserialize;

#[derive(Clone, Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct DictionaryEntry {
    spoken: String,
    written: String,
}

#[derive(Clone, Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct SnippetEntry {
    trigger: String,
    content: String,
}

#[derive(Clone, Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct LearnedWord {
    key: String,
    written: String,
    count: u32,
}

#[derive(Clone, Debug, Deserialize)]
#[serde(default, rename_all = "camelCase")]
pub struct TextIntelligence {
    dictionary: Vec<DictionaryEntry>,
    snippets: Vec<SnippetEntry>,
    learned_words: Vec<LearnedWord>,
    cleanup_fillers: bool,
    format_lists: bool,
    developer_mode: bool,
}

impl Default for TextIntelligence {
    fn default() -> Self {
        Self {
            dictionary: Vec::new(),
            snippets: Vec::new(),
            learned_words: Vec::new(),
            cleanup_fillers: true,
            format_lists: true,
            developer_mode: true,
        }
    }
}

impl TextIntelligence {
    pub fn from_path(path: Option<&Path>) -> Self {
        path.and_then(|path| fs::read_to_string(path).ok())
            .and_then(|contents| serde_json::from_str(&contents).ok())
            .unwrap_or_default()
    }

    pub fn prepare(&self, raw: &str, active_window: &str) -> PreparedText {
        if let Some(snippet) = self.expand_snippet(raw) {
            return PreparedText {
                text: snippet,
                is_snippet: true,
                developer_context: false,
            };
        }

        let developer_context = self.developer_mode && is_developer_window(active_window);
        let mut text = raw.trim().to_string();
        if self.cleanup_fillers {
            text = remove_fillers(&text);
        }
        text = apply_spoken_structure(&text);
        if developer_context || contains_developer_command(&text) {
            text = apply_developer_syntax(&text);
        }
        text = self.apply_vocabulary(&text);
        if self.format_lists {
            text = format_spoken_lists(&text);
        }
        text = normalize_spacing(&text);

        PreparedText {
            text,
            is_snippet: false,
            developer_context,
        }
    }

    pub fn finalize(&self, text: &str) -> String {
        normalize_spacing(&self.apply_vocabulary(text))
    }

    fn expand_snippet(&self, raw: &str) -> Option<String> {
        let normalized = raw
            .trim()
            .trim_matches(|ch: char| ch.is_ascii_punctuation())
            .to_ascii_lowercase();
        self.snippets.iter().find_map(|entry| {
            let trigger = entry.trigger.trim().to_ascii_lowercase();
            if normalized == trigger || normalized == format!("insert {trigger}") {
                Some(entry.content.trim().to_string())
            } else {
                None
            }
        })
    }

    fn apply_vocabulary(&self, text: &str) -> String {
        let mut result = text.to_string();
        for (spoken, written) in self
            .dictionary
            .iter()
            .map(|entry| (&entry.spoken, &entry.written))
            .chain(
                self.learned_words
                    .iter()
                    .filter(|entry| entry.count >= 2)
                    .map(|entry| (&entry.key, &entry.written)),
            )
        {
            let spoken = spoken.trim();
            let written = written.trim();
            if spoken.is_empty() || written.is_empty() {
                continue;
            }
            let pattern = format!(r"(?i)\b{}\b", regex::escape(spoken));
            if let Ok(regex) = Regex::new(&pattern) {
                result = regex.replace_all(&result, written).to_string();
            }
        }
        result
    }
}

pub struct PreparedText {
    pub text: String,
    pub is_snippet: bool,
    pub developer_context: bool,
}

fn is_developer_window(title: &str) -> bool {
    let title = title.to_ascii_lowercase();
    [
        "visual studio code",
        "cursor",
        "windsurf",
        "terminal",
        "powershell",
        "command prompt",
        "github",
        "jetbrains",
        "intellij",
        "pycharm",
        "webstorm",
        "rustrover",
        "sublime text",
        "notepad++",
    ]
    .iter()
    .any(|name| title.contains(name))
}

fn contains_developer_command(text: &str) -> bool {
    let text = text.to_ascii_lowercase();
    [
        "camel case",
        "pascal case",
        "snake case",
        "kebab case",
        "open brace",
        "close brace",
        "open bracket",
        "close bracket",
        "dot py",
        "dot js",
        "dot ts",
    ]
    .iter()
    .any(|phrase| text.contains(phrase))
}

fn remove_fillers(text: &str) -> String {
    let fillers =
        Regex::new(r"(?i)\b(?:um+|uh+|erm+|hmm+)\b[\s,]*").expect("filler regex is valid");
    fillers.replace_all(text, "").to_string()
}

fn apply_spoken_structure(text: &str) -> String {
    let mut result = text.to_string();
    let replacements = [
        (r"(?i)\bnew paragraph\b", "\n\n"),
        (r"(?i)\bnew line\b", "\n"),
        (r"(?i)\bquestion mark\b", "?"),
        (r"(?i)\bexclamation (?:mark|point)\b", "!"),
        (r"(?i)\bcomma\b", ","),
        (r"(?i)\bsemicolon\b", ";"),
        (r"(?i)\bcolon\b", ":"),
    ];
    for (pattern, replacement) in replacements {
        let regex = Regex::new(pattern).expect("spoken structure regex is valid");
        result = regex.replace_all(&result, replacement).to_string();
    }
    result
}

fn apply_developer_syntax(text: &str) -> String {
    let mut result = text.to_string();
    let replacements = [
        (r"(?i)\bc sharp\b", "C#"),
        (r"(?i)\bc plus plus\b", "C++"),
        (r"(?i)\bnode j s\b", "Node.js"),
        (r"(?i)\bjava script\b", "JavaScript"),
        (r"(?i)\btype script\b", "TypeScript"),
        (r"(?i)\bgit hub\b", "GitHub"),
        (r"(?i)\bcloud flare\b", "Cloudflare"),
        (r"(?i)\bsuper base\b", "Supabase"),
        (r"(?i)\bverse sell\b", "Vercel"),
        (r"(?i)\bdot p y\b|\bdot py\b", ".py"),
        (r"(?i)\bdot j s\b|\bdot js\b", ".js"),
        (r"(?i)\bdot t s x\b|\bdot tsx\b", ".tsx"),
        (r"(?i)\bdot t s\b|\bdot ts\b", ".ts"),
        (r"(?i)\bdot j s o n\b|\bdot json\b", ".json"),
        (r"(?i)\bopen parenthes(?:is|es)\b|\bopen paren\b", "("),
        (r"(?i)\bclose parenthes(?:is|es)\b|\bclose paren\b", ")"),
        (r"(?i)\bopen brace\b", "{"),
        (r"(?i)\bclose brace\b", "}"),
        (r"(?i)\bopen bracket\b", "["),
        (r"(?i)\bclose bracket\b", "]"),
        (r"(?i)\bequals equals\b", "=="),
        (r"(?i)\bequals\b", "="),
        (r"(?i)\bgreater than\b", ">"),
        (r"(?i)\bless than\b", "<"),
        (r"(?i)\barrow\b", "->"),
        (r"(?i)\bback tick\b", "`"),
    ];
    for (pattern, replacement) in replacements {
        let regex = Regex::new(pattern).expect("developer syntax regex is valid");
        result = regex.replace_all(&result, replacement).to_string();
    }

    for (command, style) in [
        ("camel case", CaseStyle::Camel),
        ("pascal case", CaseStyle::Pascal),
        ("snake case", CaseStyle::Snake),
        ("kebab case", CaseStyle::Kebab),
    ] {
        let pattern = Regex::new(&format!(
            r"(?i)\b{}\s+([A-Za-z0-9]+(?:\s+[A-Za-z0-9]+){{0,5}})",
            regex::escape(command)
        ))
        .expect("case command regex is valid");
        result = pattern
            .replace_all(&result, |captures: &Captures| {
                apply_case_style(&captures[1], style)
            })
            .to_string();
    }

    let operators = Regex::new(r"\s*(==|=|->|<|>)\s*").expect("developer operator regex is valid");
    result = operators.replace_all(&result, "$1").to_string();
    let empty_pairs = Regex::new(r"(\{|\[|\()\s+(\}|\]|\))").expect("empty pair regex is valid");
    result = empty_pairs.replace_all(&result, "$1$2").to_string();

    result
}

#[derive(Clone, Copy)]
enum CaseStyle {
    Camel,
    Pascal,
    Snake,
    Kebab,
}

fn apply_case_style(value: &str, style: CaseStyle) -> String {
    let words: Vec<String> = value
        .split_whitespace()
        .map(|word| word.to_ascii_lowercase())
        .collect();
    match style {
        CaseStyle::Snake => words.join("_"),
        CaseStyle::Kebab => words.join("-"),
        CaseStyle::Camel | CaseStyle::Pascal => words
            .iter()
            .enumerate()
            .map(|(index, word)| {
                if index == 0 && matches!(style, CaseStyle::Camel) {
                    word.clone()
                } else {
                    let mut chars = word.chars();
                    chars
                        .next()
                        .map(|first| first.to_ascii_uppercase().to_string() + chars.as_str())
                        .unwrap_or_default()
                }
            })
            .collect(),
    }
}

fn format_spoken_lists(text: &str) -> String {
    let numbered = Regex::new(
        r"(?i)\b(?:number\s+(?:one|two|three|four|five|six|seven|eight|nine|ten)\b[\s.):,-]*|(?:[1-9]|10)[.)]\s+)",
    )
    .expect("numbered list regex is valid");
    let markers: Vec<_> = numbered.find_iter(text).collect();
    if markers.len() >= 2 {
        let mut items = Vec::new();
        for (index, marker) in markers.iter().enumerate() {
            let end = markers
                .get(index + 1)
                .map(|next| next.start())
                .unwrap_or(text.len());
            let item = text[marker.end()..end]
                .trim()
                .trim_matches(|ch: char| ch == ',' || ch == '.' || ch == ';')
                .trim();
            if !item.is_empty() {
                items.push(format!("{}. {}", index + 1, capitalize_first(item)));
            }
        }
        if items.len() >= 2 {
            let prefix = text[..markers[0].start()].trim();
            return if prefix.is_empty() {
                items.join("\n")
            } else {
                format!("{prefix}\n\n{}", items.join("\n"))
            };
        }
    }

    let bullets = Regex::new(r"(?i)\bbullet[\s:,-]+").expect("bullet list regex is valid");
    let markers: Vec<_> = bullets.find_iter(text).collect();
    if markers.len() >= 2 {
        let mut items = Vec::new();
        for (index, marker) in markers.iter().enumerate() {
            let end = markers
                .get(index + 1)
                .map(|next| next.start())
                .unwrap_or(text.len());
            let item = text[marker.end()..end].trim().trim_matches('.').trim();
            if !item.is_empty() {
                items.push(format!("- {}", capitalize_first(item)));
            }
        }
        if items.len() >= 2 {
            let prefix = text[..markers[0].start()].trim();
            return if prefix.is_empty() {
                items.join("\n")
            } else {
                format!("{prefix}\n\n{}", items.join("\n"))
            };
        }
    }
    text.to_string()
}

fn capitalize_first(text: &str) -> String {
    let mut chars = text.chars();
    chars
        .next()
        .map(|first| first.to_ascii_uppercase().to_string() + chars.as_str())
        .unwrap_or_default()
}

fn normalize_spacing(text: &str) -> String {
    let spaces = Regex::new(r"[ \t]+").expect("spacing regex is valid");
    let punctuation = Regex::new(r"\s+([,.;:!?])").expect("punctuation regex is valid");
    let newline_space = Regex::new(r" *\n *").expect("newline regex is valid");
    let blank_lines = Regex::new(r"\n{3,}").expect("blank line regex is valid");
    let result = spaces.replace_all(text.trim(), " ").to_string();
    let result = punctuation.replace_all(&result, "$1").to_string();
    let result = newline_space.replace_all(&result, "\n").to_string();
    blank_lines.replace_all(&result, "\n\n").trim().to_string()
}

#[cfg(test)]
mod tests {
    use super::TextIntelligence;

    fn profile() -> TextIntelligence {
        serde_json::from_str(
            r#"{
                "dictionary": [{"spoken": "project pair it", "written": "Project Parrot"}],
                "snippets": [{"trigger": "my portfolio", "content": "https://carl.example"}],
                "learnedWords": [{"key": "cloudflare", "written": "Cloudflare", "count": 3}],
                "cleanupFillers": true,
                "formatLists": true,
                "developerMode": true
            }"#,
        )
        .expect("profile should parse")
    }

    #[test]
    fn removes_only_unambiguous_fillers() {
        let text = profile().prepare("um meet meet at two actually three", "");
        assert_eq!(text.text, "meet meet at two actually three");
    }

    #[test]
    fn preserves_valid_words_around_actually_and_no() {
        let text = profile().prepare(
            "i actually think there are no good options for this release",
            "",
        );
        assert_eq!(
            text.text,
            "i actually think there are no good options for this release"
        );
    }

    #[test]
    fn preserves_intentional_repetition() {
        let text = profile().prepare("this is very very important", "");
        assert_eq!(text.text, "this is very very important");
    }

    #[test]
    fn formats_numbered_lists() {
        let text = profile().prepare(
            "number one apples number two bananas number three oranges",
            "",
        );
        assert_eq!(text.text, "1. Apples\n2. Bananas\n3. Oranges");
    }

    #[test]
    fn keeps_context_before_spoken_list_markers() {
        let text = profile().prepare(
            "shopping list number one apples number two bananas number three oranges",
            "",
        );
        assert_eq!(
            text.text,
            "shopping list\n\n1. Apples\n2. Bananas\n3. Oranges"
        );
    }

    #[test]
    fn expands_snippets_exactly() {
        let text = profile().prepare("insert my portfolio", "");
        assert!(text.is_snippet);
        assert_eq!(text.text, "https://carl.example");
    }

    #[test]
    fn applies_dictionary_and_learned_vocabulary() {
        let text = profile().prepare("project pair it uses cloudflare", "");
        assert_eq!(text.text, "Project Parrot uses Cloudflare");
    }

    #[test]
    fn formats_developer_commands_in_known_editors() {
        let text = profile().prepare(
            "camel case user account id equals open brace close brace",
            "main.rs - Visual Studio Code",
        );
        assert!(text.developer_context);
        assert_eq!(text.text, "userAccountId={}");
    }
}
