"""Report the paired watermark ablation without tuning detector thresholds."""
import json
from pathlib import Path
import statistics
from collections import defaultdict

ROOT=Path(__file__).resolve().parents[1]

def main():
    folder=ROOT/'work/watermark-pairs'
    data=json.loads((folder/'results.json').read_text())
    manifest=json.loads((folder/'manifest.json').read_text())
    assert 'conditions' in data and len(manifest)==40
    assert len(data['results'])==80
    report='''# Matched watermark ablation

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
'''
    summaries={}
    for condition in ['original','phone_simulation']:
        rows=[r for r in data['results'] if r['condition']==condition]
        groups={v:[r for r in rows if r['variant']==v] for v in ['unwatermarked','watermarked','human']}
        for v,rs in groups.items():assert len(rs)==(10 if v=='human' else 15)
        correct={v:sum(r['correct'] for r in rs) for v,rs in groups.items()}
        errors=sum(r['status']!='ok' for r in rows)
        report+=f"| {condition} | {correct['unwatermarked']}/15 | {correct['watermarked']}/15 | {correct['human']}/10 | {errors} |\n"
        summaries[condition]={'correct':correct,'errors':errors}
    report+='\n## Watermark sanity check\n\n'
    for v in ['unwatermarked','watermarked']:
        vals=[r['watermark_decoder_mean'] for r in manifest if r['variant']==v]
        report+=f"Perth decoder output on saved {v} WAVs: mean **{statistics.mean(vals):.6f}**, range {min(vals):.6f}–{max(vals):.6f}. These are watermark-detector outputs, not deepfake confidence.\n\n"
    lengths=[]
    bypair=defaultdict(dict)
    for r in manifest:
        if 'pair_id' in r:bypair[r['pair_id']][r['variant']]=r
    for pair,vs in bypair.items():
        assert set(vs)=={'unwatermarked','watermarked'}
        assert vs['unwatermarked']['sha256']!=vs['watermarked']['sha256']
        lengths.append(vs['watermarked']['samples']-vs['unwatermarked']['samples'])
    report+=f"All 15 pairs have different waveform hashes and nonzero waveform differences. Watermark insertion changed length by {min(lengths)} to {max(lengths)} samples; any such length effect is part of the insertion operation. The raw branch was copied before insertion; no watermark-removal processing was used.\n"
    report+='\n## Paired synthetic scores\n\nScores are uncalibrated model outputs. Delta = watermarked minus unwatermarked.\n\n| Channel | Speaker / text | Unwatermarked score | Watermarked score | Delta | Label changed? |\n|---|---|---:|---:|---:|---|\n'
    for condition in ['original','phone_simulation']:
        pairs=defaultdict(dict)
        for r in data['results']:
            if r['condition']==condition and r['expected']=='AI':pairs[r['pair_id']][r['variant']]=r
        deltas=[];flips=0
        for pair,vs in sorted(pairs.items()):
            a,b=vs['unwatermarked'],vs['watermarked']
            if a['status']!='ok' or b['status']!='ok':
                report+=f"| {condition} | {pair} | ERROR | ERROR | — | — |\n";continue
            delta=b['synthetic_score']-a['synthetic_score'];deltas.append(delta)
            changed=a['prediction']!=b['prediction'];flips+=int(changed)
            report+=f"| {condition} | {pair} | {a['synthetic_score']:.6f} | {b['synthetic_score']:.6f} | {delta:+.6f} | {'yes' if changed else 'no'} |\n"
        summaries[condition].update(mean_score_delta=statistics.mean(deltas) if deltas else None,
             max_absolute_score_delta=max(map(abs,deltas)) if deltas else None,label_flips=flips)
    report+='\n## Interpretation\n\n'
    passed=all(x['correct']['unwatermarked']==15 and x['errors']==0 for x in summaries.values())
    report+=('The detector recognized all 15 pre-insertion waveforms in both channel conditions. This supports that detection in this sample does **not require Chatterbox\'s added Perth watermark**. It does not establish which acoustic cues the detector uses or prove it ignores watermark cues generally.\n\n' if passed else 'Detection changed or failed on some fixtures; inspect the paired scores and errors above before concluding whether the added watermark influences results.\n\n')
    report+='''The sample covers one generator, five speakers and three repeated texts. It is
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
'''
    data['paired_summary']=summaries
    (ROOT/'WATERMARK_ABLATION_RESULTS.md').write_text(report)
    (ROOT/'WATERMARK_ABLATION_RESULTS.json').write_text(json.dumps(data,indent=2)+'\n')
    (ROOT/'watermark-pair-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    (ROOT.parent/'outputs/matched-watermark-qa.md').write_text(report)
    print(json.dumps(summaries,indent=2))

if __name__=='__main__':main()
