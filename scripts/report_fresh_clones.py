"""Summarize freshly generated clone QA separately from public benchmarks."""
import json
from pathlib import Path
from collections import defaultdict
from scripts.evaluate_qa import metrics

ROOT=Path(__file__).resolve().parents[1]

def main():
    folder=ROOT/'work/fresh-clones'
    data=json.loads((folder/'results.json').read_text())
    assert 'conditions' in data
    manifest=json.loads((folder/'chatterbox-manifest.json').read_text())
    report='''# Fresh Chatterbox clone QA

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
'''
    for c,m in data['conditions'].items():
        report+=f"| {c} | {m['correct']}/{m['total']} ({100*m['accuracy_all']:.1f}%) | {m['false_positives']}/{m['human']} | {m['false_negatives']}/{m['ai']} | {m['errors']} |\n"
    groups=defaultdict(list)
    for row in data['results']:groups[(row['condition'],row['speaker_id'],row['expected'])].append(row)
    report+='\n## Per speaker\n\n| Condition | LibriTTS speaker | Class | Correct / total |\n|---|---|---|---:|\n'
    for (c,s,expected),rows in sorted(groups.items()):
        m=metrics(rows);report+=f"| {c} | {s} | {expected} | {m['correct']}/{m['total']} |\n"
    report+='\n## All clip scores\n\nScores are raw model outputs, not calibrated confidence.\n\n| Condition | Clip | Expected | Prediction | Synthetic score |\n|---|---|---|---|---:|\n'
    for r in data['results']:
        score=f"{r['synthetic_score']:.6f}" if 'synthetic_score' in r else r['error']
        report+=f"| {r['condition']} | {Path(r['file']).name} | {r['expected']} | {r['prediction']} | {score} |\n"
    report+='''
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
'''
    (ROOT/'FRESH_CLONE_RESULTS.md').write_text(report)
    (ROOT/'FRESH_CLONE_RESULTS.json').write_text(json.dumps(data,indent=2)+'\n')
    (ROOT/'fresh-clone-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    (ROOT.parent/'outputs/fresh-chatterbox-clone-qa.md').write_text(report)
    print(json.dumps(data['conditions'],indent=2))

if __name__=='__main__':main()
