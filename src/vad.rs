pub fn trim_silence(audio: &[f32], sample_rate: u32, threshold: f32) -> Vec<f32> {
    let frame_size = (sample_rate as f32 * 0.03) as usize;
    let padding = (sample_rate as f32 * 0.18) as usize;
    if audio.len() < frame_size || frame_size == 0 {
        return audio.to_vec();
    }

    let mut first = None;
    let mut last = None;

    for (index, frame) in audio.chunks(frame_size).enumerate() {
        let rms =
            (frame.iter().map(|sample| sample * sample).sum::<f32>() / frame.len() as f32).sqrt();
        if rms >= threshold {
            let start = index * frame_size;
            first.get_or_insert(start);
            last = Some((start + frame.len()).min(audio.len()));
        }
    }

    match (first, last) {
        (Some(start), Some(end)) => {
            let start = start.saturating_sub(padding);
            let end = (end + padding).min(audio.len());
            audio[start..end].to_vec()
        }
        _ => Vec::new(),
    }
}
