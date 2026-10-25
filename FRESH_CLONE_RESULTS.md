# Fresh Chatterbox clone QA

## What was tested

15 Chatterbox-Turbo clips generated locally on 2026-10-23: five reference
speakers reading three new neutral sentences each. Ten human controls (two
recordings per speaker) were selected from LibriTTS via SONAR, excluding all
clips in our previous QA run. Five of the controls supplied the reference voice
prompts. Selection and text were frozen before generation and inference.

The generated audio files did not exist when the detector checkpoint was
published. **Unseen audio does not mean an unseen synthesis engine or speaker**:
Chatterbox or these public human voices could occur in detector training.
We did not measure speaker-similarity or independently transcribe the generated
audio, so this tests reference-conditioned synthesis, not a verified level of
impersonation quality. All outputs are retained; there was no score-based curation.

Both original audio and paired simulated G.711 narrowband versions were tested.
The fixed detector threshold remains 0.5. No detector weights or preprocessing
were changed. ElevenLabs was excluded at the user's request.

## Results

| Condition | Correct / total | Humans falsely flagged | Clones missed | Errors |
|---|---:|---:|---:|---:|
| original | 25/25 (100.0%) | 0/10 | 0/15 | 0 |
| phone_simulation | 25/25 (100.0%) | 0/10 | 0/15 | 0 |

## Per speaker

| Condition | LibriTTS speaker | Class | Correct / total |
|---|---|---|---:|
| original | 1089 | AI | 3/3 |
| original | 1089 | HUMAN | 2/2 |
| original | 4507 | AI | 3/3 |
| original | 4507 | HUMAN | 2/2 |
| original | 5105 | AI | 3/3 |
| original | 5105 | HUMAN | 2/2 |
| original | 6829 | AI | 3/3 |
| original | 6829 | HUMAN | 2/2 |
| original | 8224 | AI | 3/3 |
| original | 8224 | HUMAN | 2/2 |
| phone_simulation | 1089 | AI | 3/3 |
| phone_simulation | 1089 | HUMAN | 2/2 |
| phone_simulation | 4507 | AI | 3/3 |
| phone_simulation | 4507 | HUMAN | 2/2 |
| phone_simulation | 5105 | AI | 3/3 |
| phone_simulation | 5105 | HUMAN | 2/2 |
| phone_simulation | 6829 | AI | 3/3 |
| phone_simulation | 6829 | HUMAN | 2/2 |
| phone_simulation | 8224 | AI | 3/3 |
| phone_simulation | 8224 | HUMAN | 2/2 |

## All clip scores

Scores are raw model outputs, not calibrated confidence.

| Condition | Clip | Expected | Prediction | Synthetic score |
|---|---|---|---|---:|
| original | human_6829_0.flac | HUMAN | HUMAN | 0.064011 |
| original | human_6829_1.flac | HUMAN | HUMAN | 0.066846 |
| original | human_8224_0.flac | HUMAN | HUMAN | 0.065784 |
| original | human_8224_1.flac | HUMAN | HUMAN | 0.064436 |
| original | human_4507_0.flac | HUMAN | HUMAN | 0.091171 |
| original | human_4507_1.flac | HUMAN | HUMAN | 0.082713 |
| original | human_1089_0.flac | HUMAN | HUMAN | 0.074597 |
| original | human_1089_1.flac | HUMAN | HUMAN | 0.074575 |
| original | human_5105_0.flac | HUMAN | HUMAN | 0.071776 |
| original | human_5105_1.flac | HUMAN | HUMAN | 0.071789 |
| original | chatterbox_1089_0.wav | AI | AI | 0.864201 |
| original | chatterbox_1089_1.wav | AI | AI | 0.865005 |
| original | chatterbox_1089_2.wav | AI | AI | 0.865609 |
| original | chatterbox_4507_0.wav | AI | AI | 0.864747 |
| original | chatterbox_4507_1.wav | AI | AI | 0.864973 |
| original | chatterbox_4507_2.wav | AI | AI | 0.865035 |
| original | chatterbox_5105_0.wav | AI | AI | 0.865813 |
| original | chatterbox_5105_1.wav | AI | AI | 0.865311 |
| original | chatterbox_5105_2.wav | AI | AI | 0.865692 |
| original | chatterbox_6829_0.wav | AI | AI | 0.864677 |
| original | chatterbox_6829_1.wav | AI | AI | 0.865252 |
| original | chatterbox_6829_2.wav | AI | AI | 0.865184 |
| original | chatterbox_8224_0.wav | AI | AI | 0.865786 |
| original | chatterbox_8224_1.wav | AI | AI | 0.865025 |
| original | chatterbox_8224_2.wav | AI | AI | 0.865696 |
| phone_simulation | human_6829_0.flac | HUMAN | HUMAN | 0.062425 |
| phone_simulation | human_6829_1.flac | HUMAN | HUMAN | 0.069450 |
| phone_simulation | human_8224_0.flac | HUMAN | HUMAN | 0.070276 |
| phone_simulation | human_8224_1.flac | HUMAN | HUMAN | 0.077650 |
| phone_simulation | human_4507_0.flac | HUMAN | HUMAN | 0.074117 |
| phone_simulation | human_4507_1.flac | HUMAN | HUMAN | 0.103880 |
| phone_simulation | human_1089_0.flac | HUMAN | HUMAN | 0.077181 |
| phone_simulation | human_1089_1.flac | HUMAN | HUMAN | 0.075770 |
| phone_simulation | human_5105_0.flac | HUMAN | HUMAN | 0.067124 |
| phone_simulation | human_5105_1.flac | HUMAN | HUMAN | 0.071653 |
| phone_simulation | chatterbox_1089_0.wav | AI | AI | 0.861530 |
| phone_simulation | chatterbox_1089_1.wav | AI | AI | 0.864250 |
| phone_simulation | chatterbox_1089_2.wav | AI | AI | 0.843256 |
| phone_simulation | chatterbox_4507_0.wav | AI | AI | 0.857583 |
| phone_simulation | chatterbox_4507_1.wav | AI | AI | 0.863902 |
| phone_simulation | chatterbox_4507_2.wav | AI | AI | 0.842614 |
| phone_simulation | chatterbox_5105_0.wav | AI | AI | 0.866833 |
| phone_simulation | chatterbox_5105_1.wav | AI | AI | 0.849423 |
| phone_simulation | chatterbox_5105_2.wav | AI | AI | 0.864616 |
| phone_simulation | chatterbox_6829_0.wav | AI | AI | 0.863572 |
| phone_simulation | chatterbox_6829_1.wav | AI | AI | 0.864639 |
| phone_simulation | chatterbox_6829_2.wav | AI | AI | 0.863795 |
| phone_simulation | chatterbox_8224_0.wav | AI | AI | 0.865879 |
| phone_simulation | chatterbox_8224_1.wav | AI | AI | 0.865635 |
| phone_simulation | chatterbox_8224_2.wav | AI | AI | 0.865552 |

## Reproducibility and limits

- Generator: [ResembleAI/chatterbox-turbo](https://huggingface.co/ResembleAI/chatterbox-turbo),
  revision `749d1c1a46eb10492095d68fbcf55691ccf137cd`.
- Generator code: [resemble-ai/chatterbox](https://github.com/resemble-ai/chatterbox),
  commit `5de7a54aa4e5e2baadb0182dde554908b48b85c2`.
- Default temperature 0.8, top-p 0.95, top-k 1000, repetition penalty 1.2;
  per-text random seeds recorded. Hardware/library changes may alter generation.
- Upstream **Perth watermark was retained**. Detection results should not be
  generalized to unwatermarked synthesis; the detector was not given watermark labels.
- Detector: Forensics 0.3B, revision `cfd11365b02167214dc3b392378809fef6ca3cfa`.
- Human data: SONAR revision `ea98ab87279154094d2000198dd4b885c69aefaa`, LibriTTS
  source IDs and hashes retained in the manifest. Human controls are new to our
  tests, but not demonstrably absent from detector training.
- Channel simulation: band-pass approximated by 300 Hz high-pass and 3400 Hz
  low-pass, resampled to mono 8 kHz and G.711 mu-law encoded/decoded using ffmpeg.
- Each prediction analyzes the center five seconds (repeating shorter inputs).
- Only five reference speakers and one engine were tested. Repeated texts and
  channel variants are correlated; they are not independent evidence of a general
  accuracy rate. Natural conversation, noise, and real calls remain untested.
- Local generation/detection incur no API fee. The detector is noncommercial.

The generator runs in a separate environment so its dependencies do not change
the detector. Reproduce after installing the pinned Chatterbox source there:

```sh
.venv/bin/python scripts/prepare_fresh_clones.py
work/chatterbox-venv/bin/python scripts/generate_chatterbox_fixtures.py
.venv/bin/python scripts/evaluate_qa.py --manifest work/fresh-clones/chatterbox-manifest.json --output-dir work/fresh-clones --selection 'Frozen fresh-v1 plan: 5 speakers, 10 human controls, 15 generated clones'
.venv/bin/python -m scripts.report_fresh_clones
```

Local audio, frozen plan, generation log, model metadata and generator dependency
versions are under `work/fresh-clones/` (ignored by Git). Machine-readable
results are saved as `FRESH_CLONE_RESULTS.json` and provenance as
`fresh-clone-manifest.json`. Files are clearly labeled by source; no audio was
uploaded to a voice-cloning service.
