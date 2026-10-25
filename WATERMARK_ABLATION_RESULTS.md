# Matched watermark ablation

15 fresh Chatterbox-Turbo syntheses, five reference speakers and three neutral
texts each. Each synthesis is captured immediately **before** Chatterbox calls
Perth watermark insertion and **after** that same call. These are two versions
of the same generated waveform, not separate random generations. Ten human
controls are included. Test date: 2026-10-23.

Both versions use the same PCM-16 WAV encoding, sample rate, detector,
preprocessing and threshold (0.5). We also test paired narrowband G.711 phone
simulations. This yields 80 predictions: 30 synthetic variants + 10 human clips,
each tested in two channel conditions. No detector tuning or sample filtering.

## Detection results

| Condition | Without added watermark: AI detected | With watermark: AI detected | Human correctly identified | Errors |
|---|---:|---:|---:|---:|
| original | 15/15 | 15/15 | 10/10 | 0 |
| phone_simulation | 15/15 | 15/15 | 10/10 | 0 |

## Watermark sanity check

Perth decoder output on saved unwatermarked WAVs: mean **0.000008**, range 0.000000–0.000040. These are watermark-detector outputs, not deepfake confidence.

Perth decoder output on saved watermarked WAVs: mean **0.999844**, range 0.997659–1.000000. These are watermark-detector outputs, not deepfake confidence.

All 15 pairs have different waveform hashes and nonzero waveform differences. Watermark insertion changed length by 0 to 0 samples; any such length effect is part of the insertion operation. The raw branch was copied before insertion; no watermark-removal processing was used.

## Paired synthetic scores

Scores are uncalibrated model outputs. Delta = watermarked minus unwatermarked.

| Channel | Speaker / text | Unwatermarked score | Watermarked score | Delta | Label changed? |
|---|---|---:|---:|---:|---|
| original | 1089_0 | 0.864325 | 0.864201 | -0.000124 | no |
| original | 1089_1 | 0.864814 | 0.865005 | +0.000191 | no |
| original | 1089_2 | 0.865161 | 0.865609 | +0.000447 | no |
| original | 4507_0 | 0.864692 | 0.864747 | +0.000055 | no |
| original | 4507_1 | 0.864915 | 0.864973 | +0.000058 | no |
| original | 4507_2 | 0.865209 | 0.865035 | -0.000174 | no |
| original | 5105_0 | 0.865500 | 0.865813 | +0.000313 | no |
| original | 5105_1 | 0.865093 | 0.865311 | +0.000218 | no |
| original | 5105_2 | 0.865686 | 0.865692 | +0.000006 | no |
| original | 6829_0 | 0.864804 | 0.864677 | -0.000128 | no |
| original | 6829_1 | 0.865077 | 0.865252 | +0.000175 | no |
| original | 6829_2 | 0.865304 | 0.865184 | -0.000120 | no |
| original | 8224_0 | 0.865865 | 0.865786 | -0.000080 | no |
| original | 8224_1 | 0.864852 | 0.865025 | +0.000174 | no |
| original | 8224_2 | 0.865540 | 0.865696 | +0.000156 | no |
| phone_simulation | 1089_0 | 0.862334 | 0.861530 | -0.000804 | no |
| phone_simulation | 1089_1 | 0.864149 | 0.864250 | +0.000101 | no |
| phone_simulation | 1089_2 | 0.836390 | 0.843256 | +0.006865 | no |
| phone_simulation | 4507_0 | 0.850728 | 0.857583 | +0.006855 | no |
| phone_simulation | 4507_1 | 0.862820 | 0.863902 | +0.001082 | no |
| phone_simulation | 4507_2 | 0.846936 | 0.842614 | -0.004322 | no |
| phone_simulation | 5105_0 | 0.866487 | 0.866833 | +0.000347 | no |
| phone_simulation | 5105_1 | 0.853375 | 0.849423 | -0.003952 | no |
| phone_simulation | 5105_2 | 0.864307 | 0.864616 | +0.000308 | no |
| phone_simulation | 6829_0 | 0.864124 | 0.863572 | -0.000551 | no |
| phone_simulation | 6829_1 | 0.865358 | 0.864639 | -0.000719 | no |
| phone_simulation | 6829_2 | 0.865123 | 0.863795 | -0.001328 | no |
| phone_simulation | 8224_0 | 0.865921 | 0.865879 | -0.000042 | no |
| phone_simulation | 8224_1 | 0.865395 | 0.865635 | +0.000240 | no |
| phone_simulation | 8224_2 | 0.865862 | 0.865552 | -0.000310 | no |

## Interpretation

The detector recognized all 15 pre-insertion waveforms in both channel conditions. This supports that detection in this sample does **not require Chatterbox's added Perth watermark**. It does not establish which acoustic cues the detector uses or prove it ignores watermark cues generally.

The sample covers one generator, five speakers and three repeated texts. It is
not an estimate of general accuracy or a test of other cloning engines. A voice
clone engine or source speaker may have appeared in detector training even
though these generated files are new. Speaker similarity and transcription
quality were not independently measured. Phone audio is simulated, not a real
call. Original and compressed variants are correlated observations.

## Reproduction

- Generator: `ResembleAI/chatterbox-turbo`, revision
  `749d1c1a46eb10492095d68fbcf55691ccf137cd`.
- Chatterbox code: `5de7a54aa4e5e2baadb0182dde554908b48b85c2`.
- Detector: Forensics 0.3B, revision `cfd11365b02167214dc3b392378809fef6ca3cfa`.
- Prompt texts, seeds, reference hashes and timestamps are recorded in the manifest.
- Wrapper copies the pre-insertion waveform, calls the original Perth operation
  unchanged, and saves both outputs with matching encoding. The upstream
  installation and normal generator behavior are unchanged.
- The phone transform is unchanged from prior QA: high-pass 300 Hz, low-pass
  3400 Hz, mono 8 kHz G.711 mu-law WAV, decoded by the detector.

```sh
work/chatterbox-venv/bin/python scripts/generate_watermark_pairs.py
.venv/bin/python scripts/evaluate_qa.py --manifest work/watermark-pairs/manifest.json --output-dir work/watermark-pairs --selection '15 matched pre/post watermark pairs plus 10 human controls'
.venv/bin/python -m scripts.report_watermark_pairs
```

Local audio is clearly named `clone_*_unwatermarked.wav` and
`clone_*_watermarked.wav` under `work/watermark-pairs/` and ignored by Git.
No audio was uploaded. Machine-readable evidence is retained in
`WATERMARK_ABLATION_RESULTS.json` and `watermark-pair-manifest.json`.
