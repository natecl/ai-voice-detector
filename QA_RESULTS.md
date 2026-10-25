# Human and voice-clone QA

## Scope

268 distinct public research fixtures, each tested in its original form and
through a simulated narrowband phone channel: **536 inference attempts**.
102 human clips and 166 synthetic clips per condition. No threshold tuning,
training, sample replacement, or score-based selection was performed.

- SONAR: 100 human clips and 20 from each of eight synthesis systems (260 total).
  Selection is the first records ordered by SHA-256 of `qa-v1:` plus source path,
  separately within each group. This intentionally balances synthesis systems;
  aggregate accuracy does not estimate real-world prevalence.
- SWAN/LibriTTS-DF public audio demos: all 8 clips—2 human originals and 6
  adapted/cloned/converted voices (AdaSpeech, TorToiSe, YourTTS).
- Ground truth comes from dataset labels and the researchers' demo table,
  not from this detector or a human listening guess.
- Frozen model: Forensics 0.3B, revision
  `cfd11365b02167214dc3b392378809fef6ca3cfa`, CPU, threshold **0.5**.
- Original production preprocessing is unchanged: mono, 16 kHz, peak-normalize,
  center five seconds, repeat shorter clips. Predictions describe that crop.
- Phone simulation: 300 Hz high-pass + 3400 Hz low-pass, mono, 8 kHz,
  G.711 mu-law encode/decode using ffmpeg. This is not an actual phone call.

## Overall results

| Condition | Correct / total | Accuracy | Human incorrectly flagged AI | AI missed as human | Errors |
|---|---:|---:|---:|---:|---:|
| original | 261/268 | 97.4% | 0/102 (0.0%) | 7/166 (4.2%) | 0 |
| phone_simulation | 259/268 | 96.6% | 0/102 (0.0%) | 9/166 (5.4%) | 0 |

## Results by source

| Dataset / source | Original correct | Phone simulation correct |
|---|---:|---:|
| SONAR / AudioGen | 18/20 | 18/20 |
| SONAR / FlashSpeech | 19/20 | 18/20 |
| SONAR / NaturalSpeech3 | 16/20 | 16/20 |
| SONAR / OpenAI | 20/20 | 20/20 |
| SONAR / PromptTTS2 | 20/20 | 20/20 |
| SONAR / VALLE | 20/20 | 20/20 |
| SONAR / VoiceBox | 20/20 | 19/20 |
| SONAR / human | 100/100 | 100/100 |
| SONAR / xTTS | 20/20 | 20/20 |
| SWAN-LibriTTS-DF-demos / AdaSpeech-adapted | 2/2 | 2/2 |
| SWAN-LibriTTS-DF-demos / TorToiSe-tuned | 2/2 | 2/2 |
| SWAN-LibriTTS-DF-demos / YourTTS-voice-conversion | 2/2 | 2/2 |
| SWAN-LibriTTS-DF-demos / human | 2/2 | 2/2 |

## Every incorrect prediction or rejection

| Condition | Source fixture | Expected | Predicted | Synthetic score / error |
|---|---|---|---|---|
| original | AudioGen/30.wav | AI | HUMAN | 0.333407 |
| original | AudioGen/9.wav | AI | HUMAN | 0.403802 |
| original | FlashSpeech/13.wav | AI | HUMAN | 0.487972 |
| original | NaturalSpeech3/30.wav | AI | HUMAN | 0.289732 |
| original | NaturalSpeech3/6.wav | AI | HUMAN | 0.229022 |
| original | NaturalSpeech3/7.wav | AI | HUMAN | 0.224375 |
| original | NaturalSpeech3/18.wav | AI | HUMAN | 0.234834 |
| phone_simulation | AudioGen/30.wav | AI | HUMAN | 0.193372 |
| phone_simulation | AudioGen/37.wav | AI | HUMAN | 0.153934 |
| phone_simulation | FlashSpeech/13.wav | AI | HUMAN | 0.345408 |
| phone_simulation | FlashSpeech/58.wav | AI | HUMAN | 0.199580 |
| phone_simulation | NaturalSpeech3/16.wav | AI | HUMAN | 0.218412 |
| phone_simulation | NaturalSpeech3/7.wav | AI | HUMAN | 0.219675 |
| phone_simulation | NaturalSpeech3/31.wav | AI | HUMAN | 0.149535 |
| phone_simulation | NaturalSpeech3/21.wav | AI | HUMAN | 0.276423 |
| phone_simulation | VoiceBox/4.wav | AI | HUMAN | 0.398409 |

The 100 SONAR human clips represent 31 distinct LibriTTS speaker IDs inferred from source filenames.

## Performance

original: median inference 0.185 s per analyzed crop; excludes decoding, model load and channel simulation.

phone_simulation: median inference 0.179 s per analyzed crop; excludes decoding, model load and channel simulation.

## Interpretation and limits

This is an external-fixture QA check, not proof of safe identity verification.
The model publisher already reports SONAR evaluation; training/development
contamination cannot be ruled out, and the training corpus is not fully disclosed.
The eight cloning demos are tiny and publicly available; those may also have
been seen during development. Do not describe this as an unseen-generator test.

The fixtures are mainly read/research speech, with only two human originals in
the explicitly paired cloning demos. They do not establish current ElevenLabs
or Chatterbox clone accuracy, conversational-call accuracy, language robustness,
or performance under noise/packet loss. Phone variants reuse the same source
clips, so they are paired stress tests, not additional independent samples.

A low synthetic score does not authenticate a speaker. Raw scores are not
calibrated confidence. Correct classifications here cannot resolve whether an
arbitrary call is safe. Rejections count against overall accuracy and are
reported separately from false positives/negatives.

## Sources and reproduction

- [SWAN-DF researchers' demo page](https://swan-df.github.io/): adapted AdaSpeech,
  tuned TorToiSe, and YourTTS voice conversion. See Korshunov et al.,
  *Vulnerability of Automatic Identity Recognition to Audio-Visual Deepfakes*, IJCB 2023.
- [SONAR packaging](https://huggingface.co/datasets/SpeechAntiSpoofingBenchmarks/SONAR),
  pinned dataset revision `ea98ab87279154094d2000198dd4b885c69aefaa`.
- [Original SONAR research/code](https://github.com/Jessegator/SONAR).
- [Forensics model card](https://huggingface.co/eliya/forensics_0.3B_base_deepfake_classifier).

SONAR packaging is CC BY-NC 4.0 with underlying sources retaining their terms.
Audio is retained locally, ignored by Git, and not redistributed in this report.
The manifest records fixture hashes and provenance; downloaded parquet shards
were checked against the published LFS SHA-256 values.

```sh
.venv/bin/python scripts/prepare_qa_fixtures.py
.venv/bin/python scripts/evaluate_qa.py
.venv/bin/python scripts/report_qa.py
.venv/bin/python -m pytest -q
```

Machine-readable results: `QA_RESULTS.json`; fixture manifest:
`qa-fixture-manifest.json`. Local audio: `work/qa/audio/`, phone simulations:
`work/qa/phone/`. No changes to detector behavior were made for this evaluation.
