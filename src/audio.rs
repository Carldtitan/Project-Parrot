use std::{
    sync::{mpsc::Sender, Arc, Mutex},
    thread,
    time::{Duration, Instant},
};

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

#[derive(Debug, Clone, Copy)]
pub struct ReleaseTail {
    pub waited: Duration,
    pub appended_seconds: f32,
    pub ended_on_silence: bool,
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

    /// Keep the microphone open briefly after push-to-talk key-up.
    ///
    /// Audio drivers deliver input in buffered callbacks, so stopping on the
    /// key event can cut the last phoneme even when the user released the key
    /// after speaking. A minimum cushion catches that buffered audio. If the
    /// user is still finishing a word, continue until a short quiet boundary,
    /// with a hard upper bound so ambient noise cannot stall dictation.
    pub fn wait_for_release_tail(
        &self,
        minimum: Duration,
        silence_window: Duration,
        maximum: Duration,
        poll_interval: Duration,
    ) -> ReleaseTail {
        let started = Instant::now();
        let start_frame = self
            .frames
            .lock()
            .expect("audio frames mutex poisoned")
            .len();
        let silence_samples =
            (self.sample_rate as f32 * silence_window.as_secs_f32()).round() as usize;
        let mut ended_on_silence = false;

        loop {
            thread::sleep(poll_interval);
            let elapsed = started.elapsed();
            if elapsed >= maximum {
                break;
            }
            if elapsed < minimum {
                continue;
            }

            let frames = self.frames.lock().expect("audio frames mutex poisoned");
            let appended = frames.len().saturating_sub(start_frame);
            if appended < silence_samples {
                continue;
            }
            let recent_start = frames.len().saturating_sub(silence_samples);
            if !has_voice(&frames[recent_start..]) {
                ended_on_silence = true;
                break;
            }
        }

        let appended = self
            .frames
            .lock()
            .expect("audio frames mutex poisoned")
            .len()
            .saturating_sub(start_frame);
        ReleaseTail {
            waited: started.elapsed(),
            appended_seconds: appended as f32 / self.sample_rate as f32,
            ended_on_silence,
        }
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

    // Microphone arrays and virtual devices sometimes expose an active
    // channel beside a silent or phase-inverted channel. Averaging them can
    // make a normal voice extremely quiet or cancel it altogether. Follow the
    // loudest channel in this callback instead.
    let mut energy = vec![0.0f64; channels];
    let mut counts = vec![0usize; channels];
    for frame in input.chunks(channels) {
        for (channel, sample) in frame.iter().enumerate() {
            energy[channel] += f64::from(*sample) * f64::from(*sample);
            counts[channel] += 1;
        }
    }
    let selected = energy
        .iter()
        .zip(counts.iter())
        .enumerate()
        .max_by(
            |(_, (left_energy, left_count)), (_, (right_energy, right_count))| {
                let left = **left_energy / (**left_count).max(1) as f64;
                let right = **right_energy / (**right_count).max(1) as f64;
                left.total_cmp(&right)
            },
        )
        .map(|(channel, _)| channel)
        .unwrap_or(0);

    input
        .chunks(channels)
        .filter_map(|frame| frame.get(selected).copied())
        .collect()
}

fn has_voice(samples: &[f32]) -> bool {
    if samples.is_empty() {
        return false;
    }
    let peak = samples
        .iter()
        .map(|sample| sample.abs())
        .fold(0.0, f32::max);
    let rms =
        (samples.iter().map(|sample| sample * sample).sum::<f32>() / samples.len() as f32).sqrt();
    peak >= 0.006 || rms >= 0.002
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

#[cfg(test)]
mod tests {
    use super::{has_voice, to_mono};

    #[test]
    fn stereo_capture_uses_active_channel_instead_of_diluting_it() {
        let stereo = [0.0, 0.25, 0.0, -0.25, 0.0, 0.5];
        assert_eq!(to_mono(&stereo, 2), vec![0.25, -0.25, 0.5]);
    }

    #[test]
    fn stereo_capture_does_not_cancel_phase_inverted_microphones() {
        let stereo = [0.2, -0.2, -0.4, 0.4, 0.3, -0.3];
        let mono = to_mono(&stereo, 2);
        assert_eq!(
            mono.iter().map(|sample| sample.abs()).collect::<Vec<_>>(),
            vec![0.2, 0.4, 0.3]
        );
    }

    #[test]
    fn release_tail_keeps_quiet_voice_but_ignores_room_silence() {
        assert!(has_voice(&[0.0, 0.006, -0.006, 0.001]));
        assert!(!has_voice(&[0.0, 0.0008, -0.0008, 0.0004]));
    }
}
