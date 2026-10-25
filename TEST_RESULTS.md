# Forensics 0.3B prototype test results

Tested 2026-10-23 on Nathan, macOS Apple M4 Pro with 24 GB RAM.

## Outcome

The local file-input detector works: all three human recordings and three
synthetic recordings were correctly classified on CPU and Apple MPS at the
unchanged reference threshold of 0.5. Eight code tests pass.

**This is a six-sample smoke test, not a general accuracy estimate.** Human
samples come from one LibriSpeech speaker; synthetic samples use macOS TTS,
not a representative set of modern voice clones. Training overlap is unknown.
Phone codecs, background noise, other languages, and live calls remain untested.

## Measured predictions

Synthetic scores are raw model outputs, not calibrated confidence.
Only each recording's center five seconds were analyzed.

| Sample | Known source | CPU prediction | Synthetic score | CPU inference (s) |
|---|---|---|---|---|
| human_1.wav | 1272-128104-0002 | HUMAN | 0.064122 | 0.1859 |
| ai_1.wav | Samantha | AI | 0.864676 | 0.1779 |
| human_2.wav | 1272-128104-0003 | HUMAN | 0.072005 | 0.1778 |
| ai_2.wav | Daniel | AI | 0.865234 | 0.1879 |
| human_3.wav | 1272-128104-0004 | HUMAN | 0.075713 | 0.1863 |
| ai_3.wav | Karen | AI | 0.864976 | 0.1926 |

CPU model loading took 2.75 seconds, excluding Python startup and downloads.
CPU prediction took 0.178–0.193 seconds per five-second clip, excluding audio
preprocessing. MPS took 5.136 seconds for its first prediction and 0.198–0.210
seconds thereafter. CPU remains the default based on this small local run.
Both devices produced identical labels; the largest absolute score difference
was below 0.0001. No broad performance claim is implied by these measurements.

## Reproducibility

- Model: https://huggingface.co/eliya/forensics_0.3B_base_deepfake_classifier
- Revision: `cfd11365b02167214dc3b392378809fef6ca3cfa`
- Checkpoint: `checkpoint_epoch_5.safetensors`, 1,269,932,956 bytes.
- SHA-256: `803d2c57e705395d007b9deaf5b1a110965950f207df223e6dff5b6d298490fb`
- Local hash matches the published Hugging Face LFS hash.
- All checkpoint tensors passed finite-value validation.
- The four auxiliary projection tensors unused by the published inference
  architecture are explicitly excluded after shape checks. All inference
  parameters load strictly; none are randomly left uninitialized.
- Published code is retained under vendor/. No model training was performed.
- Environment is pinned in requirements.txt (Python 3.12, torch/torchaudio
  2.11.0, transformers 5.20.2).

```sh
.venv/bin/python -m pytest -q
.venv/bin/python scripts/prepare_smoke_samples.py
.venv/bin/python scripts/evaluate_smoke.py --weights work/forensics/checkpoint_epoch_5.safetensors --device both
.venv/bin/python detector.py work/samples/human_1.wav work/samples/ai_1.wav --weights work/forensics/checkpoint_epoch_5.safetensors --json
```

Machine-readable results are retained in tests/fixtures/forensics_smoke_results.json.
Audio and weights stay locally under work/ and are excluded from Git.

## Scope and limitations

Audio stays local. The pipeline averages channels, resamples to 16 kHz,
peak-normalizes, center-crops five seconds, and repeats shorter speech clips.
It returns HUMAN/AI plus an uncalibrated synthetic score. Non-speech is outside
its intended use. The code tests include invalid input, preprocessing,
short-clip repetition, score direction, and non-finite weights/output rejection.

The model's CC BY-NC 4.0 license restricts commercial use. This is a personal
prototype; review licensing before building a commercial product with it.
Pella's earlier failed experiment is preserved in PELLA_TEST_RESULTS.md.
