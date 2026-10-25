# Voice Check — AI Voice Detector

A local macOS voice companion: **system audio → Forensics 0.3B → Human / AI
prediction**. The desktop pill has an audio-reactive waveform and a separate
verdict badge. A browser app also supports audio uploads and microphone samples.

**For agents taking over the project:** read [the operator and knowledge guide](docs/AGENT_GUIDE.md).
It covers controls, architecture, setup, local API, verification, and known issues.

## Desktop pill

Open the existing `Voice Check.app` in the checkout's sibling `outputs/` folder.
Click the pill to start system listening, and click again to stop. Escape stops
capture when the widget has keyboard focus. Drag the pill to move it; its position
is saved between launches, and the right-hand badge follows it.

The waveform responds to actual system audio. Five-second windows produce Human
or AI predictions. Quiet windows or windows with too little speech show Waiting.
It captures combined system output, excluding Voice Check; pause unrelated audio.
Headphones work without microphone loopback. The score is not calibrated
confidence, and the result does not verify a caller's identity.

Use the waveform menu-bar icon to show the widget or quit. The pill's X/check
marks are parts of the same stop target. Upload and microphone controls are in
the browser app, rather than an expandable widget panel.

Requires macOS 13+. To build after setup:

```sh
.venv/bin/python scripts/build_widget.py
```

The bundle depends on this checkout, its `.venv`, model assets, and ffmpeg; it is
not a portable installer. Native rebuilds can invalidate the macOS capture
permission for ad-hoc development builds. See the guide before resetting the
app-specific permission. UI-only edits do not require a native rebuild.

## Local browser UI

```sh
.venv/bin/python app.py
```

Open http://127.0.0.1:8765 in Chrome or Safari. Upload audio or click **Record my
voice**, allow microphone access, stop recording, then click **Analyze voice**.
The server loads the detector once on CPU. It binds only to your Mac's loopback
address. No audio is sent to an external service. Temporary decoded audio is
removed after each request. ffmpeg is required (already installed on this Mac).

Uploads are capped at 25 MB and 120 seconds. Recording stops automatically just
before 120 seconds. The server accepts browser WebM/Opus and M4A/AAC recordings
as well as WAV, MP3 and other ffmpeg-readable audio. It decodes to mono 16 kHz
float WAV before the detector's existing normalization and five-second crop.

## Setup

Python 3.12 and uv:

```sh
uv venv --python 3.12
uv pip sync --python .venv/bin/python requirements.txt
```

## Run

```sh
.venv/bin/python detector.py /path/to/clip.wav
.venv/bin/python detector.py /path/to/clip.wav --json
# Use the already-downloaded local weights:
.venv/bin/python detector.py work/samples/human_1.wav --weights work/forensics/checkpoint_epoch_5.safetensors
```

First use downloads pinned model weights and backbone configuration from
Hugging Face. CPU is the default; `--device mps` enables Apple GPU inference.
Multiple input paths share one model load. Only safetensors checkpoints are
accepted. Custom checkpoints must match the architecture strictly.

The raw `synthetic_score` is **not calibrated confidence**. Scores >= 0.5 produce
AI; lower scores produce HUMAN, following the published inference script. The
model was trained with positive labels for real speech, so we invert its sigmoid
output. The default threshold has not been tuned against our evaluation fixtures.

## Audio processing

Matches the reference pipeline: average channels, resample to 16 kHz,
peak-normalize, select the **center five seconds**, and repeat shorter clips to
fill five seconds. JSON identifies the crop and whether audio was repeated.
Only that crop is classified. Use speech: non-speech can yield meaningless
predictions. Silence, non-finite samples, clips below 0.4 seconds, and files over
120 seconds are rejected. File support depends on the installed libsndfile.

## Tests

```sh
.venv/bin/python -m pytest -q
# macOS, ffmpeg, and Samantha/Daniel/Karen voices required:
.venv/bin/python scripts/prepare_smoke_samples.py
.venv/bin/python scripts/evaluate_smoke.py --weights work/forensics/checkpoint_epoch_5.safetensors --device both
```

The evaluation writes `work/smoke-results.json`. Samples, checkpoints, and the
virtual environment are ignored by Git. Three human excerpts come from one
LibriSpeech speaker; three macOS TTS voices read matching text. This is a smoke
test, not evidence of general accuracy on voice clones or real phone calls.

## Models and licensing

The default is `eliya/forensics_0.3B_base_deepfake_classifier`, WavLM + AASIST.
Its weights and supplied implementation are published under **CC BY-NC 4.0**;
commercial use needs separate licensing review/permission. See `THIRD_PARTY.md`.

The earlier Pella experiment is preserved in `detector_pella.py` and
`PELLA_TEST_RESULTS.md`. Its pinned public checkpoint has invalid weights and
cannot produce valid predictions. It is not the default detector.

See `TEST_RESULTS.md` for measured results from the current model.

## Public human / cloned-voice QA

```sh
.venv/bin/python scripts/prepare_qa_fixtures.py
.venv/bin/python scripts/evaluate_qa.py
.venv/bin/python scripts/report_qa.py
```

Fetches about 530 MB of SONAR research data plus eight explicitly labeled
SWAN/LibriTTS-DF audio demos. Selects 268 fixtures before inference and evaluates
both originals and paired G.711 narrowband simulations. Requires ffmpeg.
See `QA_RESULTS.md` for subgroup results, every mistake, provenance, and limits.
SONAR appears in the model publisher's evaluation, so these results do not prove
unseen-data generalization. Audio remains local and is not added to Git.

## Fresh Chatterbox clone QA

Fresh cloning uses a separate environment and does not alter detector dependencies.
The frozen plan selects five human speakers, ten controls not used in earlier QA,
and three new texts per speaker. No detector threshold changes are made.

```sh
git clone https://github.com/resemble-ai/chatterbox.git work/chatterbox-src
git -C work/chatterbox-src checkout 5de7a54aa4e5e2baadb0182dde554908b48b85c2
uv venv --python 3.12 work/chatterbox-venv
uv pip install --python work/chatterbox-venv/bin/python ./work/chatterbox-src
.venv/bin/python scripts/prepare_fresh_clones.py
work/chatterbox-venv/bin/python scripts/generate_chatterbox_fixtures.py
.venv/bin/python scripts/evaluate_qa.py --manifest work/fresh-clones/chatterbox-manifest.json --output-dir work/fresh-clones --selection 'Frozen fresh-v1 plan: 5 speakers, 10 human controls, 15 generated clones'
.venv/bin/python -m scripts.report_fresh_clones
```

Run the public-fixture preparation first to provide the human source parquet files.
Generated outputs retain the upstream Perth watermark. See `FRESH_CLONE_RESULTS.md`.
Freshly generated audio is not proof that the detector has never seen the engine
or source speakers during training. ElevenLabs is not included in this run.

## Matched watermark ablation

To test whether detection depends on Chatterbox's added watermark, capture
pre/post insertion audio from the same synthesis (15 pairs, plus 10 humans):

```sh
work/chatterbox-venv/bin/python scripts/generate_watermark_pairs.py
.venv/bin/python scripts/evaluate_qa.py --manifest work/watermark-pairs/manifest.json --output-dir work/watermark-pairs --selection '15 matched pre/post watermark pairs plus 10 human controls'
.venv/bin/python -m scripts.report_watermark_pairs
```

The QA wrapper preserves the original watermark operation and captures its
input. It also runs Perth's decoder on saved files to verify the experimental
conditions. No upstream installation changes or detector tuning are needed.
See `WATERMARK_ABLATION_RESULTS.md` for paired scores and limitations.


## Widget state checks

```sh
node tests/widget_state_test.cjs
```

See [the agent guide](docs/AGENT_GUIDE.md) for the current native acceptance steps
and the distinction between automated checks and actual live-capture QA.
