use std::{
    io::{BufRead, BufReader, Write},
    process::{Child, ChildStdin, Command, Stdio},
    sync::{
        mpsc::{self, Receiver},
        Arc, Mutex,
    },
    thread,
    time::Duration,
};

use anyhow::{anyhow, bail, Context, Result};
use base64::{engine::general_purpose::STANDARD, Engine};
use serde::Deserialize;
use serde_json::json;

use crate::{config::AppConfig, log, workspace_root};

pub struct SttWorker {
    child: Child,
    stdin: Arc<Mutex<ChildStdin>>,
    events: Receiver<WorkerEvent>,
    sample_rate: u32,
}

#[derive(Clone)]
pub struct SttAudioSink {
    stdin: Arc<Mutex<ChildStdin>>,
    sample_rate: u32,
}

#[derive(Debug, Deserialize)]
#[serde(tag = "type")]
enum WorkerMessage {
    #[serde(rename = "ready")]
    Ready {
        engine: String,
        model: String,
        runtime: String,
        load_seconds: f32,
    },
    #[serde(rename = "started")]
    Started,
    #[serde(rename = "partial")]
    Partial {
        text: String,
        latency_ms: Option<u32>,
    },
    #[serde(rename = "final")]
    Final {
        text: String,
        latency_ms: Option<u32>,
    },
    #[serde(rename = "error")]
    Error { message: String },
}

#[derive(Debug)]
enum WorkerEvent {
    Ready,
    Started,
    Final(String),
    Error(String),
}

impl SttWorker {
    pub fn start(config: &AppConfig) -> Result<Self> {
        let script = workspace_root().join("scripts").join("stt_worker.py");
        let packaged_worker = workspace_root()
            .join("bin")
            .join("stt_worker")
            .join("stt_worker.exe");

        let mut command = if packaged_worker.exists() {
            Command::new(packaged_worker)
        } else {
            if !script.exists() {
                bail!("missing STT worker script: {}", script.display());
            }
            let local_python = workspace_root().join(".venv").join("Scripts").join("python.exe");
            let mut command = if local_python.exists() {
                Command::new(local_python)
            } else {
                Command::new("python")
            };
            command.arg(script);
            command
        };

        let mut child = command
            .arg("--engine")
            .arg(&config.stt_engine)
            .arg("--threads")
            .arg(config.stt_threads.to_string())
            .arg("--update-interval")
            .arg(config.update_interval.to_string())
            .arg("--live-window-seconds")
            .arg(config.live_window_seconds.to_string())
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()
            .context("failed to start STT worker")?;

        let stdin = Arc::new(Mutex::new(
            child
                .stdin
                .take()
                .ok_or_else(|| anyhow!("failed to open STT worker stdin"))?,
        ));
        let stdout = child
            .stdout
            .take()
            .ok_or_else(|| anyhow!("failed to open STT worker stdout"))?;
        let stderr = child
            .stderr
            .take()
            .ok_or_else(|| anyhow!("failed to open STT worker stderr"))?;

        let (tx, events) = mpsc::channel();
        thread::spawn(move || {
            let reader = BufReader::new(stdout);
            for line in reader.lines().map_while(|line| line.ok()) {
                match serde_json::from_str::<WorkerMessage>(&line) {
                    Ok(WorkerMessage::Ready {
                        engine,
                        model,
                        runtime,
                        load_seconds,
                    }) => {
                        log(&format!(
                            "STT ready: {engine} / {model} on {runtime} in {load_seconds:.1}s"
                        ));
                        let _ = tx.send(WorkerEvent::Ready);
                    }
                    Ok(WorkerMessage::Started) => {
                        let _ = tx.send(WorkerEvent::Started);
                    }
                    Ok(WorkerMessage::Partial { text, latency_ms }) => {
                        if let Some(latency_ms) = latency_ms {
                            log(&format!("Live raw ({latency_ms}ms): {text}"));
                        } else {
                            log(&format!("Live raw: {text}"));
                        }
                    }
                    Ok(WorkerMessage::Final { text, latency_ms }) => {
                        if let Some(latency_ms) = latency_ms {
                            log(&format!("Final STT latency: {latency_ms}ms"));
                        }
                        let _ = tx.send(WorkerEvent::Final(text));
                    }
                    Ok(WorkerMessage::Error { message }) => {
                        let _ = tx.send(WorkerEvent::Error(message));
                    }
                    Err(error) => log(&format!("STT worker output parse error: {error}")),
                }
            }
        });

        thread::spawn(move || {
            let reader = BufReader::new(stderr);
            for line in reader.lines().map_while(|line| line.ok()) {
                if !line.trim().is_empty() {
                    log(&format!("STT: {}", line.trim()));
                }
            }
        });

        let worker = Self {
            child,
            stdin,
            events,
            sample_rate: config.sample_rate,
        };
        worker.wait_ready()?;
        Ok(worker)
    }

    pub fn begin_utterance(&self) -> Result<()> {
        self.send_json(json!({ "type": "start" }))?;
        loop {
            match self.events.recv_timeout(Duration::from_secs(5)) {
                Ok(WorkerEvent::Started) => return Ok(()),
                Ok(WorkerEvent::Error(message)) => bail!("STT worker error: {message}"),
                Ok(_) => {}
                Err(_) => bail!("STT worker did not start the stream"),
            }
        }
    }

    pub fn audio_sink(&self) -> SttAudioSink {
        SttAudioSink {
            stdin: Arc::clone(&self.stdin),
            sample_rate: self.sample_rate,
        }
    }

    pub fn end_utterance(&self) -> Result<String> {
        self.send_json(json!({ "type": "stop" }))?;
        loop {
            match self.events.recv_timeout(Duration::from_secs(60)) {
                Ok(WorkerEvent::Final(text)) => return Ok(text),
                Ok(WorkerEvent::Error(message)) => bail!("STT worker error: {message}"),
                Ok(_) => {}
                Err(_) => bail!("STT worker did not return a final transcript"),
            }
        }
    }

    fn wait_ready(&self) -> Result<()> {
        loop {
            match self.events.recv_timeout(Duration::from_secs(120)) {
                Ok(WorkerEvent::Ready) => return Ok(()),
                Ok(WorkerEvent::Error(message)) => bail!("STT worker error: {message}"),
                Ok(_) => {}
                Err(_) => bail!("STT worker did not become ready"),
            }
        }
    }

    fn send_json(&self, value: serde_json::Value) -> Result<()> {
        let mut stdin = self
            .stdin
            .lock()
            .map_err(|_| anyhow!("STT worker stdin mutex poisoned"))?;
        serde_json::to_writer(&mut *stdin, &value)?;
        stdin.write_all(b"\n")?;
        stdin.flush()?;
        Ok(())
    }
}

impl SttAudioSink {
    pub fn send_audio(&self, samples: &[f32]) -> Result<()> {
        if samples.is_empty() {
            return Ok(());
        }
        let mut bytes = Vec::with_capacity(samples.len() * 4);
        for sample in samples {
            bytes.extend_from_slice(&sample.to_le_bytes());
        }
        self.send_json(json!({
            "type": "audio",
            "sample_rate": self.sample_rate,
            "samples": STANDARD.encode(bytes),
        }))
    }

    fn send_json(&self, value: serde_json::Value) -> Result<()> {
        let mut stdin = self
            .stdin
            .lock()
            .map_err(|_| anyhow!("STT worker stdin mutex poisoned"))?;
        serde_json::to_writer(&mut *stdin, &value)?;
        stdin.write_all(b"\n")?;
        stdin.flush()?;
        Ok(())
    }
}

impl Drop for SttWorker {
    fn drop(&mut self) {
        let _ = self.send_json(json!({ "type": "shutdown" }));
        let _ = self.child.kill();
        let _ = self.child.wait();
    }
}
