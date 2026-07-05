use anyhow::Result;
use clap::Parser;

#[derive(Parser, Debug)]
#[command(author, version, about = "Project Parrot local dictation MVP")]
pub struct Args {
    #[arg(
        long,
        value_parser = ["unified", "parakeet", "small-en"],
        default_value = "small-en",
        help = "Local CPU STT engine. unified is NVIDIA Parakeet Unified; parakeet is ONNX fallback; small-en is faster-whisper fallback."
    )]
    pub stt: String,

    #[arg(long, default_value_t = default_threads())]
    pub stt_threads: usize,

    #[arg(long, default_value = "qwen2.5:3b-instruct")]
    pub ollama_model: String,

    #[arg(
        long,
        default_value = "-1m",
        help = "Ollama keep_alive value for the formatter. Negative duration keeps the model loaded."
    )]
    pub ollama_keep_alive: String,

    #[arg(
        long,
        default_value_t = 0.7,
        help = "Seconds between live preview STT passes while recording."
    )]
    pub update_interval: f32,

    #[arg(
        long,
        default_value_t = 8.0,
        help = "Seconds of recent audio used for live preview. Final paste uses full utterance."
    )]
    pub live_window_seconds: f32,
}

pub struct AppConfig {
    pub hotkey_label: &'static str,
    pub sample_rate: u32,
    pub stt_engine: String,
    pub stt_threads: usize,
    pub ollama_model: String,
    pub ollama_keep_alive: String,
    pub restore_clipboard: bool,
    pub update_interval: f32,
    pub live_window_seconds: f32,
}

impl AppConfig {
    pub fn from_args(args: Args) -> Result<Self> {
        Ok(Self {
            hotkey_label: "Ctrl+Space",
            sample_rate: 16_000,
            stt_engine: args.stt,
            stt_threads: args.stt_threads.max(1),
            ollama_model: args.ollama_model,
            ollama_keep_alive: args.ollama_keep_alive,
            restore_clipboard: true,
            update_interval: args.update_interval.clamp(0.25, 3.0),
            live_window_seconds: args.live_window_seconds.clamp(2.0, 30.0),
        })
    }
}

fn default_threads() -> usize {
    std::thread::available_parallelism()
        .map(|threads| threads.get().saturating_sub(2).max(1))
        .unwrap_or(4)
}
