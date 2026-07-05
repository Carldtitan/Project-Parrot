be honest, is there a market for me to build a startup in voice models? are voice to voice models open source other than Mushi? what are their model architectures, i just want to know if I am trying to build a spaceship in my backyard or if this is a project I can embark on with as little compute as possible




Friday 6:06 PM






Worked for 50s



Honest answer: yes, there is a market, but probably not for “I trained a better generic voice foundation model.” That is the backyard-spaceship version. The viable startup path is more likely: use/open-adapt existing voice models and win on a specific workflow, latency, reliability, integrations, privacy, vertical data, or cost.
Market
Voice agents are a real market. Reports estimate voice AI agents around $2.4B in 2024 growing fast, and a16z noted voice companies became a large share of recent YC activity. But it is also crowded: OpenAI, Google, ElevenLabs, Cartesia, Deepgram, Vapi, Retell, PolyAI, SoundHound, Synthflow, etc. So the market exists, but “general voice assistant API” is brutal.
A good startup wedge would be something like:
voice agents for one regulated vertical: clinics, insurance, dispatch, legal intake, field service
local/offline/private voice agents for enterprise
ultra-low-latency phone agents with tool use and audit logs
voice model eval/monitoring/safety/compliance
cheaper self-hostable voice stack for SMBs
fine-tuned voices/languages/accents underserved by big providers
Open voice-to-voice models besides Moshi
Yes. Also, it is Moshi, not Mushi.
Examples:
Model	Open?	Rough architecture
Moshi / Kyutai	Yes	Speech-text foundation model using Mimi neural audio codec, Helium text LM backbone, streaming hierarchical generation of semantic/acoustic audio tokens plus text tokens. Source: Moshi paper, repo
Mini-Omni	Yes	Built around Qwen2-0.5B plus Whisper-small encoder, trained for end-to-end speech input and streaming speech output. Source: paper, repo
LLaMA-Omni	Yes/research	Speech encoder + speech adaptor + Llama-3.1-8B-Instruct + streaming speech decoder. Paper claims training in under 3 days on 4 GPUs. Source: paper, repo
Qwen2.5-Omni	Yes	End-to-end multimodal model with Thinker-Talker architecture: perception/reasoning separated from streaming speech generation. Source: Qwen blog, repo
Qwen3-Omni	Yes	Native omni-modal model for text/image/audio/video input and real-time text/speech output. Source: repo
GLM-4-Voice	Yes	End-to-end voice model for Chinese/English speech understanding and generation with controllable emotion/intonation/speed/dialect. Source: repo
Baichuan-Omni-1.5	Yes	7B-ish omni-modal model supporting text/image/video/audio input and text/audio output. Source: repo, HF
Sesame CSM-1B	Yes, but more speech generation than full assistant	Llama backbone plus smaller audio decoder that emits Mimi audio codes from text/audio inputs. Source: repo, HF

There are also many cascaded open stacks: VAD -> STT -> LLM -> TTS, like Hugging Face’s speech-to-speech. These are not “native voice-to-voice foundation models,” but they are often the most practical way to ship.
Backyard spaceship or feasible?
Depends what you mean by “build.”
Training a frontier native voice-to-voice model from scratch: spaceship. You need huge speech datasets, codec training, alignment data, preference/eval loops, latency engineering, safety, and expensive multi-GPU training.
Fine-tuning/adapting an existing open model: feasible. Especially if you constrain the product: one language, one domain, one voice style, one workflow.
Building a startup product with low compute: very feasible. Use a cascaded architecture first:
WebRTC/VAD -> streaming ASR -> small/hosted LLM -> streaming TTS -> telephony/browser
Then replace pieces with native models only where it creates a measurable advantage.
My pragmatic recommendation: do not start by training a new base voice model. Start with a product benchmark: latency, interruption handling, accuracy in your domain, cost per minute, call success rate. If you can beat incumbents in one narrow use case using open models plus engineering, then you have a real company path.

Friday 6:07 PM






First of all, do not suggest a cascaded arrchitectire to me at all, I am not interested in doing that. Also, do not suggest for me to fine tune an already existing model unless I tell you so, I am asking you where the loophole in voice models is right now, broswe the web




Friday 6:11 PM






Worked for 47s



You’re right to reject my previous framing. I looked it up fresh. The loophole is not “another generic voice model.” The loophole is that native voice models are still weak at control.
The current gaps:
Full-duplex models are still immature
Models like Moshi made simultaneous listen/speak real, but current research still says full-duplex systems struggle with interruptions, overlap, pause timing, backchannels, and dynamic turn negotiation. HumDial-FDBench exists because this is still not solved well. Source: HumDial-FDBench paper.

Voice + role control is newly open
NVIDIA PersonaPlex explicitly says existing duplex models were locked to fixed voice/role, and it adds role conditioning plus voice conditioning on top of a Moshi-style architecture. That means the market gap was obvious enough that NVIDIA just attacked it. Source: PersonaPlex paper, HF model.

Audio tokenization is still a bottleneck
Most SpeechLMs are basically: speech tokenizer → LM → vocoder. The tokenizer has to preserve semantics, speaker identity, prosody, emotion, and acoustic detail while staying cheap. That is a hard compression problem, and it is not “done.” Source: SpeechLM survey, Discrete Audio Tokens survey.

Text/audio alignment is leaky
Hume’s TADA release is important because they argue LLM-based speech systems suffer from a mismatch: audio has far more frames than text tokens, causing memory, latency, skipped content, and hallucinated speech. Their trick is one acoustic vector per text token. Source: Hume TADA.

Native voice models lag at agentic reliability
Benchmarks are now testing long multi-turn voice behavior, tool use, instruction following, grounding, and latency because normal LLM benchmarks don’t measure voice-agent failure modes. Daily’s benchmark says speech-to-speech models are closing the gap, but still behind text-mode LLMs in long multi-turn reliability. Source: Daily voice benchmark.

So the honest “loophole” is:
Build a smaller native voice model that is not trying to beat GPT-4o/Realtme/Gemini on general intelligence, but is unusually good at one missing axis: controllable full-duplex behavior, low-token-rate speech generation, emotional/prosodic control, stable persona/voice control, or native speech-to-action reliability.
The least-compute path is probably not a giant foundation model. It is a new architecture or training objective around one of these bottlenecks:
Better speech tokenizer/codec: fewer tokens, preserves speaker/prosody, streamable.
Better duplex behavior model: learns when to interrupt, pause, backchannel, resume.
Better controllability layer: voice, role, emotion, speed, style, domain behavior.
Better spoken reasoning/eval data: pure speech-in/speech-out benchmarks expose weaknesses.
Tiny native model for one domain: not general assistant, but native voice model for a narrow interaction class.
If you try to build “Moshi but smarter” from scratch, yes, that’s a spaceship. If you try to build the missing controllability/duplex/tokenization piece with a compact model and prove it on benchmarks, that is an actual backyard project that could become valuable.

Friday 6:11 PM






can i build my own voice chat model just like wispr flow hosted locally on my rtx30606gb RAM?




Friday 6:15 PM






Worked for 16s



Short answer: not “just like Wispr Flow” as a native voice chat model on a 6GB RTX 3060. But you can build a local Wispr Flow-like dictation product on that GPU.
Important distinction:
Wispr Flow is primarily voice-to-text dictation, not a native voice-to-voice chat foundation model. Its own site calls it “voice-to-text AI,” and their technical post says users expect transcription plus LLM formatting within ~700ms after stopping speech. Sources: Wispr Flow, technical challenges.
A native voice chat model means audio in, audio out, learned end-to-end. That is much harder and 6GB VRAM is a severe limit.
On your RTX 3060 6GB, realistic:
Local dictation app: yes.
Local polished dictation like Wispr Flow: yes, with small models and tight UX.
Local native voice-to-voice model comparable to Moshi/PersonaPlex/Qwen-Omni: no, not comfortably.
Training your own native voice chat model from scratch: no.
Tiny research prototype that speaks/listens natively: maybe, but it will sound/behave far below commercial quality.
If you want a Wispr Flow-like local app, the minimum viable version is:
Push-to-talk/global hotkey.
Local speech model.
Cleanup/rewrite model.
Paste result into active app.
Optional command mode.
But since you asked about your own voice chat model, the honest 6GB path is more like:
use a very small audio encoder/tokenizer
use a tiny decoder-only transformer
train it on narrow voice interactions
output speech tokens through a lightweight vocoder/codec
accept that it will be narrow, fragile, and not generally smart
The actual loophole for your GPU is not scale. It is building a small, specialized, local voice model that does one thing extremely well: fast dictation cleanup, command-style speech interaction, or narrow conversational behavior. If you aim for “Wispr Flow but local,” that is feasible. If you aim for “GPT-4o realtime but open and locally trained on 6GB,” that is the spaceship.

Friday 6:16 PM






oh no, not a voice chat model, just simple STT and maybe an LLM for cleanup




Friday 6:17 PM






Yes. That is very doable on an RTX 3060 6GB. For a Wispr Flow-like local app, you do not need a voice chat model.
A practical local stack:
STT: faster-whispertiny/base: very fast, lower accuracy
small: good default for 6GB
medium maybe works with quantization, but may feel slower

Cleanup LLM: small local model through llama.cpp / OllamaQwen2.5-1.5B/3B, Gemma 2B, Llama 3.2 3B, etc.
Task: remove filler words, add punctuation, preserve meaning, format for target app

UX shell: global hotkey → record mic → transcribe → cleanup → paste into active text field
For your GPU, the MVP target should be:
Push hotkey -> record until release -> faster-whisper small int8/float16 -> cleanup with 1.5B/3B LLM -> paste
You can build this locally without crazy compute. The product challenge is mostly latency and UX polish, not model training.
Good first implementation choice on Windows:
Python
faster-whisper
sounddevice or pyaudio
keyboard for global hotkey
pyperclip + paste hotkey for insertion
Ollama or llama.cpp server for cleanup
The only thing I’d avoid early is training. Start with inference-only. Once the app feels useful, then you can consider a small cleanup model fine-tune or prompt cache optimization.

Friday 6:18 PM






okay, recommend it to me, what will be the TTS and what will be the LLM, I want this to be able to run on even base PCs so I can share to my friends




Friday 6:48 PM






Worked for 28s



For “base PCs, share with friends,” I’d build around this default:
Recommended Local Stack
STT: whisper.cpp with base.en or small.en
Cleanup LLM: Qwen2.5-1.5B-Instruct-GGUF, quantized Q4_K_M
TTS: Piper
Runtime: native app + bundled binaries, not a heavy Python environment if you want easy sharing
Why:
STT: whisper.cpp
Use this over faster-whisper if distribution matters. whisper.cpp is C/C++, CPU-friendly, supports quantized models, and can run without Python dependencies. That makes it better for friends with random laptops. Source: whisper.cpp.
Model choice:
tiny.en: fastest, less accurate
base.en: best default for weak PCs
small.en: better quality, still reasonable
avoid medium/large for the friend-share version
LLM: Qwen2.5-1.5B-Instruct-GGUF
For cleanup, you do not need a 7B model. You need punctuation, filler removal, light rewriting, and “preserve meaning.” A 1.5B instruct model is enough and will run on CPU through llama.cpp. Source: Qwen2.5-1.5B-Instruct-GGUF, llama.cpp.
Use:
Q4_K_M for normal users
Q8_0 only if their machine is decent
context can be small, maybe 2048 tokens
Backup LLM:
SmolLM2-1.7B-Instruct-GGUF if you want a very lightweight alternative. Source: SmolLM2 GGUF.
TTS: Piper
If your goal is “runs everywhere,” choose Piper. It is fast, local, and light. The voices are not always as premium as newer neural TTS systems, but it is the practical default for base PCs. Source: Piper.
If you want better voice quality later, test Kokoro ONNX. It sounds better in many cases, but I would not make it the default for the first shareable build. Source: kokoro-onnx, Kokoro 82M ONNX.
My recommendation:
MVP default:
whisper.cpp base.en
+ Qwen2.5-1.5B-Instruct Q4_K_M via llama.cpp
+ Piper TTS
Higher-quality preset:
whisper.cpp small.en
+ Qwen2.5-1.5B-Instruct Q8_0 or Qwen 3B Q4
+ Kokoro ONNX
For your first version, I’d make TTS optional. The core product is hotkey dictation + cleanup + paste. TTS is useful for readback, command confirmations, or accessibility, but it should not sit in the critical path.

Friday 6:49 PM