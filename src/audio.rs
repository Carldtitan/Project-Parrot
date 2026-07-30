use std::sync::{mpsc::Sender, Arc, Mutex};

use anyhow::{anyhow, Context, Result};
use cpal::{
    traits::{DeviceTrait, HostTrait, StreamTrait},
    SampleFormat, Stream,
};

pub struct Recorder {
    sample_rate: u32,
    frames: Arc<Mutex<Vec<f32>>>,
    stream: Option<Stream>,
}

impl Recorder {
    pub fn new(sample_rate: u32) -> Result<Self> {
        Ok(Self {
            sample_rate,
            frames: Arc::new(Mutex::new(Vec::new())),
            stream: None,
        })
    }

    pub fn is_recording(&self) -> bool {
        self.stream.is_some()
    }

    pub fn start_with_sender(&mut self, sample_tx: Sender<Vec<f32>>) -> Result<()> {
        self.start_with_stream(Some(sample_tx))
    }

    fn start_with_stream(&mut self, sample_tx: Option<Sender<Vec<f32>>>) -> Result<()> {
        if self.stream.is_some() {
            return Ok(());
        }

        self.frames
            .lock()
            .expect("audio frames mutex poisoned")
            .clear();

        let host = cpal::default_host();
        let device = host
            .default_input_device()
            .ok_or_else(|| anyhow!("no default input device found"))?;
        let supported = device.default_input_config()?;
        let input_sample_rate = supported.sample_rate();
        let channels = supported.channels() as usize;
        let stream_config = supported.config();
        let target_rate = self.sample_rate;
        let err_fn = |err| eprintln!("audio stream error: {err}");

        let stream = match supported.sample_format() {
            SampleFormat::F32 => {
                let frames = Arc::clone(&self.frames);
                let sample_tx = sample_tx.clone();
                device.build_input_stream(
                    stream_config.clone(),
                    move |data: &[f32], _| {
                        push_samples(
                            data,
                            channels,
                            input_sample_rate,
                            target_rate,
                            &frames,
                            sample_tx.as_ref(),
                        )
                    },
                    err_fn,
                    None,
                )?
            }
            SampleFormat::I16 => {
                let frames = Arc::clone(&self.frames);
                let sample_tx = sample_tx.clone();
                device.build_input_stream(
                    stream_config.clone(),
                    move |data: &[i16], _| {
                        let converted: Vec<f32> =
                            data.iter().map(|sample| *sample as f32 / 32768.0).collect();
                        push_samples(
                            &converted,
                            channels,
                            input_sample_rate,
                            target_rate,
                            &frames,
                            sample_tx.as_ref(),
                        );
                    },
                    err_fn,
                    None,
                )?
            }
            SampleFormat::U16 => {
                let frames = Arc::clone(&self.frames);
                let sample_tx = sample_tx.clone();
                device.build_input_stream(
                    stream_config.clone(),
                    move |data: &[u16], _| {
                        let converted: Vec<f32> = data
                            .iter()
                            .map(|sample| (*sample as f32 - 32768.0) / 32768.0)
                            .collect();
                        push_samples(
                            &converted,
                            channels,
                            input_sample_rate,
                            target_rate,
                            &frames,
                            sample_tx.as_ref(),
                        );
                    },
                    err_fn,
                    None,
                )?
            }
            _ => return Err(anyhow!("unsupported sample format")),
        };

        stream.play().context("failed to start microphone stream")?;
        self.stream = Some(stream);
        Ok(())
    }

    pub fn stop(&mut self) -> Result<Vec<f32>> {
        self.stream.take();
        let audio = self
            .frames
            .lock()
            .expect("audio frames mutex poisoned")
            .clone();
        Ok(audio)
    }
}

fn push_samples(
    input: &[f32],
    channels: usize,
    input_sample_rate: u32,
    target_sample_rate: u32,
    frames: &Arc<Mutex<Vec<f32>>>,
    sample_tx: Option<&Sender<Vec<f32>>>,
) {
    let mono = to_mono(input, channels);
    let resampled = if input_sample_rate == target_sample_rate {
        mono
    } else {
        resample_linear(&mono, input_sample_rate, target_sample_rate)
    };
    frames
        .lock()
        .expect("audio frames mutex poisoned")
        .extend_from_slice(&resampled);
    if let Some(sample_tx) = sample_tx {
        let _ = sample_tx.send(resampled);
    }
}

fn to_mono(input: &[f32], channels: usize) -> Vec<f32> {
    if channels <= 1 {
        return input.to_vec();
    }

    input
        .chunks(channels)
        .map(|frame| frame.iter().copied().sum::<f32>() / frame.len() as f32)
        .collect()
}

fn resample_linear(input: &[f32], input_rate: u32, output_rate: u32) -> Vec<f32> {
    if input.is_empty() {
        return Vec::new();
    }

    let output_len = (input.len() as u64 * output_rate as u64 / input_rate as u64) as usize;
    let ratio = input_rate as f64 / output_rate as f64;
    let mut output = Vec::with_capacity(output_len);

    for i in 0..output_len {
        let pos = i as f64 * ratio;
        let left = pos.floor() as usize;
        let right = (left + 1).min(input.len() - 1);
        let frac = (pos - left as f64) as f32;
        output.push(input[left] * (1.0 - frac) + input[right] * frac);
    }

    output
}
