use std::path::PathBuf;

use anyhow::{bail, Result};
use clap::Parser;

use crate::workspace_root;

#[derive(Parser, Debug)]
#[command(author, version, about = "Project Parrot local dictation MVP")]
pub struct Args {
    #[arg(
        long,
        value_parser = ["small", "medium"],
        default_value = "small",
        help = "Moonshine streaming model mode. Use medium for higher accuracy."
    )]
    pub mode: String,

    #[arg(
        long,
        help = "Explicit Moonshine model directory. Defaults to models/moonshine/<mode>-streaming-en."
    )]
    pub moonshine_model_dir: Option<PathBuf>,

    #[arg(long, default_value = "qwen2.5:1.5b")]
    pub ollama_model: String,

    #[arg(
        long,
        default_value = "-1m",
        help = "Ollama keep_alive value for the formatter. Negative duration keeps the model loaded."
    )]
    pub ollama_keep_alive: String,

    #[arg(long, default_value_t = 0.18)]
    pub update_interval: f32,
}

pub struct AppConfig {
    pub hotkey_label: &'static str,
    pub sample_rate: u32,
    pub moonshine_model_dir: PathBuf,
    pub moonshine_arch: String,
    pub mode: String,
    pub ollama_model: String,
    pub ollama_keep_alive: String,
    pub restore_clipboard: bool,
    pub update_interval: f32,
}

impl AppConfig {
    pub fn from_args(args: Args) -> Result<Self> {
        let moonshine_arch = match args.mode.as_str() {
            "small" => "small-streaming",
            "medium" => "medium-streaming",
            _ => unreachable!("clap validates mode"),
        }
        .to_string();

        let moonshine_model_dir = args.moonshine_model_dir.unwrap_or_else(|| {
            workspace_root()
                .join("models")
                .join("moonshine")
                .join("download.moonshine.ai")
                .join("model")
                .join(format!("{}-streaming-en", args.mode))
                .join("quantized")
        });

        if !moonshine_model_dir.exists() {
            bail!(
                "missing Moonshine model directory: {}\nProvide --moonshine-model-dir pointing to a Moonshine {} model directory.",
                moonshine_model_dir.display(),
                moonshine_arch
            );
        }

        Ok(Self {
            hotkey_label: "Ctrl+Space",
            sample_rate: 16_000,
            moonshine_model_dir,
            moonshine_arch,
            mode: args.mode,
            ollama_model: args.ollama_model,
            ollama_keep_alive: args.ollama_keep_alive,
            restore_clipboard: true,
            update_interval: args.update_interval.clamp(0.08, 1.0),
        })
    }
}
