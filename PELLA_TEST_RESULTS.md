# Local Pella prototype test results

Tested 2026-10-23 on branch Nathan, macOS Apple M4 Pro (24 GB RAM).

## Outcome

The file-input prototype is implemented, but working classification is blocked
by invalid weights in the published Pella checkpoint. No valid accuracy or
latency claim can be made. No weights were repaired, replaced, or trained.

## Reproduction and evidence

- Model: https://huggingface.co/Sadanie/pellav2-audio-deepfake-detector
- Pinned revision: `808e16a49526178f8e1e6276725dfd14f218ec82`
- File: `pellav2_detector.pt`, 2,322,248,702 bytes.
- SHA-256: `2279c24f6e4b672c85eb2593f93cbbad83a7c1e9486fe3bcdc246c13fcca80e6`
- The local SHA-256 matches the published Hugging Face LFS object hash.
- Direct inspection with `torch.load(weights_only=True, mmap=True)` found
  12,154 non-finite values in
  `backbone.encoder.layers.14.ffn1.intermediate_dense.weight` (4096 x 1024).
- Input features on the first human clip were finite. The unmodified checkpoint
  produced non-finite output on all six CPU inference attempts.
- The loader now detects this invalid tensor and fails before inference.
- No corrected release was found in the official model repository during this check.

## Speech smoke tests (before adding the checkpoint guard)

| Sample | Known source | Result |
|---|---|---|
| human_1.wav | LibriSpeech 1272-128104-0002 | Non-finite score; no prediction |
| human_2.wav | LibriSpeech 1272-128104-0003 | Non-finite score; no prediction |
| human_3.wav | LibriSpeech 1272-128104-0004 | Non-finite score; no prediction |
| ai_1.wav | macOS Samantha TTS | Non-finite score; no prediction |
| ai_2.wav | macOS Daniel TTS | Non-finite score; no prediction |
| ai_3.wav | macOS Karen TTS | Non-finite score; no prediction |

Human excerpts are from `hf-internal-testing/librispeech_asr_dummy`, one speaker.
TTS voices read matching transcripts. These synthetic samples are a basic smoke
test, not a representative set of modern AI voice clones. Training overlap is
unknown. MPS inference was not evaluated after discovering invalid weights.

The sample manifest and raw inference results are retained locally under
`work/`. Audio, weights, and the environment are excluded from Git.

## Code validation

`python -m pytest -q`: **6 passed**. Checks cover silence, short inputs,
reference preprocessing parity, silent center crops, invalid checkpoints, and
non-finite predictions. Speech preprocessing succeeded on all six clips.

Re-run with the virtual environment:

```sh
.venv/bin/python -m pytest -q
.venv/bin/python scripts/prepare_smoke_samples.py
.venv/bin/python scripts/evaluate_smoke.py --weights work/pellav2_detector.pt
```

The evaluator now exits unsuccessfully and writes a structured blocked report
when checkpoint validation fails. A corrected compatible checkpoint can be
supplied with `--weights`; it must be validated before reporting accuracy.

## Implemented scope

Local decoding, upstream four-second preprocessing, pinned model/config
loading, strict state loading, checkpoint validation, CPU/MPS selection,
HUMAN/AI thresholding for finite output, JSON output, sample generation, and
evaluation harness. No overlay or call capture. All audio processing is local.

Dependencies: Python 3.12, torch/torchaudio 2.11.0, transformers 5.20.2;
full environment pinned in requirements.txt.
