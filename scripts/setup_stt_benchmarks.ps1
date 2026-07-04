param(
    [switch]$SkipPythonPackages
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if (-not $SkipPythonPackages) {
    python -m pip install -r requirements.txt
}

Write-Host ""
Write-Host "Checking benchmark dataset..."
@'
from datasets import Audio, load_dataset
ds = load_dataset("hf-internal-testing/librispeech_asr_dummy", "clean", split="validation")
ds = ds.cast_column("audio", Audio(sampling_rate=16000))
row = ds[0]
print(f"Dataset OK: {len(ds)} rows, first audio samples={len(row['audio']['array'])}")
'@ | python -

Write-Host ""
Write-Host "Checking Moonshine models..."
$MoonshineSmall = "models\moonshine\download.moonshine.ai\model\small-streaming-en\quantized"
$MoonshineMedium = "models\moonshine\download.moonshine.ai\model\medium-streaming-en\quantized"
if (-not (Test-Path $MoonshineSmall)) {
    python -m moonshine_voice.download --stt --language en --model-arch 4 --root models\moonshine
}
if (-not (Test-Path $MoonshineMedium)) {
    python -m moonshine_voice.download --stt --language en --model-arch 5 --root models\moonshine
}

Write-Host ""
Write-Host "Checking faster-whisper CPU smoke..."
@'
from faster_whisper import WhisperModel
model = WhisperModel("small.en", device="cpu", compute_type="float32")
print("faster-whisper CPU OK")
del model
'@ | python -

Write-Host ""
Write-Host "Checking faster-whisper CUDA availability..."
@'
try:
    import ctranslate2
    import numpy as np
    import tempfile
    import wave
    from pathlib import Path
    count = ctranslate2.get_cuda_device_count()
    print(f"CUDA devices visible to CTranslate2: {count}")
    if count:
        from faster_whisper import WhisperModel
        model = WhisperModel("small.en", device="cuda", compute_type="float16")
        with tempfile.TemporaryDirectory() as tmp:
            wav_path = Path(tmp) / "silence.wav"
            audio = np.zeros(16000, dtype=np.int16)
            with wave.open(str(wav_path), "wb") as handle:
                handle.setnchannels(1)
                handle.setsampwidth(2)
                handle.setframerate(16000)
                handle.writeframes(audio.tobytes())
            segments, _ = model.transcribe(str(wav_path), language="en", beam_size=1)
            list(segments)
        print("faster-whisper CUDA inference OK")
except Exception as exc:
    print(f"CUDA not benchmark-ready: {exc}")
'@ | python -

Write-Host ""
Write-Host "Checking Parakeet ONNX through onnx-asr..."
@'
try:
    import inspect
    import onnx_asr
    print(f"onnx-asr OK: {getattr(onnx_asr, '__version__', 'unknown')}")
    print(f"load_model signature: {inspect.signature(onnx_asr.load_model)}")
    print("Parakeet benchmark model id: nemo-parakeet-tdt-0.6b-v3")
except Exception as exc:
    raise SystemExit(f"Parakeet ONNX setup failed: {exc}")
'@ | python -

Write-Host ""
Write-Host "Setup check complete."
