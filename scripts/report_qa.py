"""Write a readable report from completed QA results; no model rerun."""
from pathlib import Path
import json
import statistics
from collections import defaultdict

ROOT=Path(__file__).resolve().parents[1]

def main():
    data=json.loads((ROOT/'work/qa/results.json').read_text())
    assert 'conditions' in data, 'Evaluation has not completed.'
    rows=data['results']
    report='''# Human and voice-clone QA

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
'''
    for condition,m in data['conditions'].items():
        report+=f"| {condition} | {m['correct']}/{m['total']} | {100*m['accuracy_all']:.1f}% | {m['false_positives']}/{m['human']} ({100*m['false_positive_rate']:.1f}%) | {m['false_negatives']}/{m['ai']} ({100*m['false_negative_rate']:.1f}%) | {m['errors']} |\n"
    report+='\n## Results by source\n\n| Dataset / source | Original correct | Phone simulation correct |\n|---|---:|---:|\n'
    groups=defaultdict(dict)
    for g in data['groups']: groups[(g['dataset'],g['group'])][g['condition']]=g
    for (dataset,group),conditions in sorted(groups.items()):
        a=conditions['original']; b=conditions['phone_simulation']
        report+=f"| {dataset} / {group} | {a['correct']}/{a['total']} | {b['correct']}/{b['total']} |\n"
    report+='\n## Every incorrect prediction or rejection\n\n'
    failures=[r for r in rows if not r['correct']]
    if failures:
        report+='| Condition | Source fixture | Expected | Predicted | Synthetic score / error |\n|---|---|---|---|---|\n'
        for r in failures:
            name=r.get('source_path',r.get('source_url','').rsplit('/',1)[-1])
            score=f"{r['synthetic_score']:.6f}" if 'synthetic_score' in r else r['error']
            report+=f"| {r['condition']} | {name} | {r['expected']} | {r['prediction']} | {score} |\n"
    else: report+='No incorrect predictions or rejections in this selected sample.\n'
    manifest=json.loads((ROOT/'work/qa/manifest.json').read_text())
    speaker_ids={Path(r['source_path']).stem.split('_')[0] for r in manifest if r['dataset']=='SONAR' and r['expected']=='HUMAN'}
    report+=f'\nThe 100 SONAR human clips represent {len(speaker_ids)} distinct LibriTTS speaker IDs inferred from source filenames.\n'
    report+='\n## Performance\n\n'
    for c in data['conditions']:
        times=[r['inference_seconds'] for r in rows if r['condition']==c and 'inference_seconds' in r]
        report+=f"{c}: median inference {statistics.median(times):.3f} s per analyzed crop; excludes decoding, model load and channel simulation.\n\n"
    report+='''## Interpretation and limits

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
'''
    (ROOT/'QA_RESULTS.md').write_text(report)
    (ROOT/'QA_RESULTS.json').write_text(json.dumps(data,indent=2)+'\n')
    (ROOT/'qa-fixture-manifest.json').write_text((ROOT/'work/qa/manifest.json').read_text())
    out=ROOT.parent/'outputs';out.mkdir(exist_ok=True)
    (out/'human-and-cloned-voice-qa.md').write_text(report)
    print(json.dumps(data['conditions'],indent=2))

if __name__=='__main__': main()
