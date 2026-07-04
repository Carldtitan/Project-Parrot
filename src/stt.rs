use anyhow::{Context, Result};
use std::path::PathBuf;
use whisper_rs::{FullParams, SamplingStrategy, WhisperContext, WhisperContextParameters};

pub struct WhisperTranscriber {
    ctx: WhisperContext,
    threads: i32,
    audio_ctx: i32,
}

impl WhisperTranscriber {
    pub fn new(model_path: PathBuf, threads: i32, audio_ctx: i32) -> Result<Self> {
        let ctx = WhisperContext::new_with_params(
            model_path
                .to_str()
                .context("model path contains invalid UTF-8")?,
            WhisperContextParameters::default(),
        )
        .context("Whisper model load failed")?;
        Ok(Self {
            ctx,
            threads,
            audio_ctx,
        })
    }

    pub fn transcribe(&mut self, audio: &[f32]) -> Result<String> {
        let mut state = self
            .ctx
            .create_state()
            .context("failed to create Whisper state")?;
        let mut params = FullParams::new(SamplingStrategy::Greedy { best_of: 1 });
        params.set_language(Some("en"));
        params.set_no_context(true);
        params.set_single_segment(false);
        params.set_no_timestamps(true);
        params.set_print_special(false);
        params.set_print_progress(false);
        params.set_print_realtime(false);
        params.set_print_timestamps(false);
        params.set_suppress_nst(true);
        params.set_temperature_inc(0.0);
        params.set_audio_ctx(self.audio_ctx);
        params.set_n_threads(self.threads);

        state
            .full(params, audio)
            .context("Whisper inference failed")?;

        let text = state
            .as_iter()
            .map(|segment| segment.to_string())
            .collect::<Vec<_>>()
            .join(" ")
            .trim()
            .to_string();
        Ok(text)
    }
}
