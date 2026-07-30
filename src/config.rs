use std::path::PathBuf;

use anyhow::Result;
use clap::Parser;

#[derive(Parser, Debug)]
#[command(author, version, about = "Project Parrot local dictation MVP")]
pub struct Args {
    #[arg(
        long,
        value_parser = ["parakeet", "small-en"],
        default_value = "parakeet",
        help = "Local CPU STT engine. Parakeet is the recommended default; small-en is the faster-whisper fallback."
    )]
    pub stt: String,

    #[arg(long, default_value_t = default_threads())]
    pub stt_threads: usize,

    #[arg(long, default_value = "qwen2.5:3b-instruct")]
    pub ollama_model: String,

    #[arg(
        long,
        default_value = "-1m",
        allow_hyphen_values = true,
        help = "Ollama keep_alive value for the formatter. Negative duration keeps the model loaded."
    )]
    pub ollama_keep_alive: String,

    #[arg(
        long,
        default_value_t = 0.5,
        help = "Seconds between live preview STT passes while recording."
    )]
    pub update_interval: f32,

    #[arg(
        long,
        default_value_t = 8.0,
        help = "Seconds of recent audio used for live preview. Final paste uses full utterance."
    )]
    pub live_window_seconds: f32,

    #[arg(
        long,
        default_value_t = false,
        help = "Accept a `quit` command on stdin for desktop-shell process management."
    )]
    pub control_stdin: bool,

    #[arg(long, default_value = "Ctrl+Space")]
    pub push_to_talk_shortcut: String,

    #[arg(long, default_value = "Ctrl+Alt+Space")]
    pub hands_free_shortcut: String,

    #[arg(long, default_value = "Ctrl+Alt+Escape")]
    pub cancel_shortcut: String,

    #[arg(long, default_value = "Ctrl+Alt+V")]
    pub paste_last_shortcut: String,

    #[arg(long)]
    pub personalization_path: Option<PathBuf>,

    #[arg(long, default_value_t = 1140)]
    pub session_warning_seconds: u64,

    #[arg(long, default_value_t = 1200)]
    pub session_limit_seconds: u64,
}

pub struct AppConfig {
    pub sample_rate: u32,
    pub stt_engine: String,
    pub stt_threads: usize,
    pub ollama_model: String,
    pub ollama_keep_alive: String,
    pub restore_clipboard: bool,
    pub update_interval: f32,
    pub live_window_seconds: f32,
    pub control_stdin: bool,
    pub push_to_talk_shortcut: String,
    pub hands_free_shortcut: String,
    pub cancel_shortcut: String,
    pub paste_last_shortcut: String,
    pub personalization_path: Option<PathBuf>,
    pub session_warning_seconds: u64,
    pub session_limit_seconds: u64,
}

impl AppConfig {
    pub fn from_args(args: Args) -> Result<Self> {
        Ok(Self {
            sample_rate: 16_000,
            stt_engine: args.stt,
            stt_threads: args.stt_threads.max(1),
            ollama_model: args.ollama_model,
            ollama_keep_alive: args.ollama_keep_alive,
            restore_clipboard: true,
            update_interval: args.update_interval.clamp(0.25, 3.0),
            live_window_seconds: args.live_window_seconds.clamp(2.0, 30.0),
            control_stdin: args.control_stdin,
            push_to_talk_shortcut: args.push_to_talk_shortcut,
            hands_free_shortcut: args.hands_free_shortcut,
            cancel_shortcut: args.cancel_shortcut,
            paste_last_shortcut: args.paste_last_shortcut,
            personalization_path: args.personalization_path,
            session_warning_seconds: args.session_warning_seconds.max(1),
            session_limit_seconds: args
                .session_limit_seconds
                .max(args.session_warning_seconds.max(1) + 1),
        })
    }
}

fn default_threads() -> usize {
    std::thread::available_parallelism()
        .map(|threads| threads.get().saturating_sub(2).max(1))
        .unwrap_or(4)
}

#[cfg(test)]
mod tests {
    use super::Args;
    use clap::Parser;

    #[test]
    fn defaults_to_the_recommended_models() {
        let args = Args::try_parse_from(["project-parrot"]).expect("default args should parse");
        assert_eq!(args.stt, "parakeet");
        assert_eq!(args.ollama_model, "qwen2.5:3b-instruct");
        assert_eq!(args.live_window_seconds, 8.0);
    }

    #[test]
    fn accepts_negative_ollama_keep_alive_values() {
        let args = Args::try_parse_from(["project-parrot", "--ollama-keep-alive", "-1m"])
            .expect("negative durations should be accepted as values");
        assert_eq!(args.ollama_keep_alive, "-1m");
    }

    #[test]
    fn long_session_limit_always_follows_warning() {
        let args = Args::try_parse_from([
            "project-parrot",
            "--session-warning-seconds",
            "20",
            "--session-limit-seconds",
            "10",
        ])
        .expect("session limits should parse");
        let config = super::AppConfig::from_args(args).expect("config should build");
        assert_eq!(config.session_warning_seconds, 20);
        assert_eq!(config.session_limit_seconds, 21);
    }
}
