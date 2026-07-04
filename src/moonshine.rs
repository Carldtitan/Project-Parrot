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

pub struct MoonshineWorker {
    child: Child,
    stdin: Arc<Mutex<ChildStdin>>,
    events: Receiver<WorkerEvent>,
    sample_rate: u32,
}

#[derive(Clone)]
pub struct MoonshineAudioSink {
    stdin: Arc<Mutex<ChildStdin>>,
    sample_rate: u32,
}

#[derive(Debug, Deserialize)]
#[serde(tag = "type")]
enum WorkerMessage {
    #[serde(rename = "ready")]
    Ready {
        model_dir: String,
        model_arch: String,
    },
    #[serde(rename = "started")]
    Started,
    #[serde(rename = "partial")]
    Partial {
        text: String,
        latency_ms: Option<u32>,
    },
    #[serde(rename = "line_completed")]
    LineCompleted {
        text: String,
        latency_ms: Option<u32>,
    },
    #[serde(rename = "final")]
    Final { text: String },
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

impl MoonshineWorker {
    pub fn start(config: &AppConfig) -> Result<Self> {
        let script = workspace_root().join("scripts").join("moonshine_worker.py");
        if !script.exists() {
            bail!("missing Moonshine worker script: {}", script.display());
        }

        let mut child = Command::new("python")
            .arg(script)
            .arg("--model-dir")
            .arg(&config.moonshine_model_dir)
            .arg("--model-arch")
            .arg(&config.moonshine_arch)
            .arg("--update-interval")
            .arg(config.update_interval.to_string())
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()
            .context("failed to start Moonshine worker")?;

        let stdin = Arc::new(Mutex::new(
            child
                .stdin
                .take()
                .ok_or_else(|| anyhow!("failed to open Moonshine worker stdin"))?,
        ));
        let stdout = child
            .stdout
            .take()
            .ok_or_else(|| anyhow!("failed to open Moonshine worker stdout"))?;
        let stderr = child
            .stderr
            .take()
            .ok_or_else(|| anyhow!("failed to open Moonshine worker stderr"))?;

        let (tx, events) = mpsc::channel();
        thread::spawn(move || {
            let reader = BufReader::new(stdout);
            for line in reader.lines().map_while(|line| line.ok()) {
                match serde_json::from_str::<WorkerMessage>(&line) {
                    Ok(WorkerMessage::Ready {
                        model_dir,
                        model_arch,
                    }) => {
                        log(&format!(
                            "Moonshine ready: {model_arch} at {model_dir}"
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
                    Ok(WorkerMessage::LineCompleted { text, latency_ms }) => {
                        if let Some(latency_ms) = latency_ms {
                            log(&format!("Line raw ({latency_ms}ms): {text}"));
                        } else {
                            log(&format!("Line raw: {text}"));
                        }
                    }
                    Ok(WorkerMessage::Final { text }) => {
                        let _ = tx.send(WorkerEvent::Final(text));
                    }
                    Ok(WorkerMessage::Error { message }) => {
                        let _ = tx.send(WorkerEvent::Error(message));
                    }
                    Err(error) => log(&format!("Moonshine worker output parse error: {error}")),
                }
            }
        });

        thread::spawn(move || {
            let reader = BufReader::new(stderr);
            for line in reader.lines().map_while(|line| line.ok()) {
                if !line.trim().is_empty() {
                    log(&format!("Moonshine: {}", line.trim()));
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
                Ok(WorkerEvent::Error(message)) => bail!("Moonshine worker error: {message}"),
                Ok(_) => {}
                Err(_) => bail!("Moonshine worker did not start the stream"),
            }
        }
    }

    pub fn audio_sink(&self) -> MoonshineAudioSink {
        MoonshineAudioSink {
            stdin: Arc::clone(&self.stdin),
            sample_rate: self.sample_rate,
        }
    }

    pub fn end_utterance(&self) -> Result<String> {
        self.send_json(json!({ "type": "stop" }))?;
        loop {
            match self.events.recv_timeout(Duration::from_secs(15)) {
                Ok(WorkerEvent::Final(text)) => return Ok(text),
                Ok(WorkerEvent::Error(message)) => bail!("Moonshine worker error: {message}"),
                Ok(_) => {}
                Err(_) => bail!("Moonshine worker did not return a final transcript"),
            }
        }
    }

    fn wait_ready(&self) -> Result<()> {
        loop {
            match self.events.recv_timeout(Duration::from_secs(60)) {
                Ok(WorkerEvent::Ready) => return Ok(()),
                Ok(WorkerEvent::Error(message)) => bail!("Moonshine worker error: {message}"),
                Ok(_) => {}
                Err(_) => bail!("Moonshine worker did not become ready"),
            }
        }
    }

    fn send_json(&self, value: serde_json::Value) -> Result<()> {
        let mut stdin = self
            .stdin
            .lock()
            .map_err(|_| anyhow!("Moonshine worker stdin mutex poisoned"))?;
        serde_json::to_writer(&mut *stdin, &value)?;
        stdin.write_all(b"\n")?;
        stdin.flush()?;
        Ok(())
    }
}

impl MoonshineAudioSink {
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
            .map_err(|_| anyhow!("Moonshine worker stdin mutex poisoned"))?;
        serde_json::to_writer(&mut *stdin, &value)?;
        stdin.write_all(b"\n")?;
        stdin.flush()?;
        Ok(())
    }
}

impl Drop for MoonshineWorker {
    fn drop(&mut self) {
        let _ = self.send_json(json!({ "type": "shutdown" }));
        let _ = self.child.kill();
        let _ = self.child.wait();
    }
}
