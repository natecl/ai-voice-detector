"""Frozen-threshold QA on public human/synthetic and explicit cloning fixtures."""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import statistics
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from detector import MODEL_ID, MODEL_REVISION, load_model, prepare_audio, predict


def metrics(rows):
    human = [r for r in rows if r['expected']=='HUMAN']
    ai = [r for r in rows if r['expected']=='AI']
    accepted = [r for r in rows if r.get('prediction') in ('HUMAN','AI')]
    correct = sum(r.get('prediction') == r['expected'] for r in rows)
    fp = sum(r.get('prediction') == 'AI' for r in human)
    fn = sum(r.get('prediction') == 'HUMAN' for r in ai)
    return {'total':len(rows),'accepted':len(accepted),'errors':len(rows)-len(accepted),
        'human':len(human),'ai':len(ai),'correct':correct,
        'accuracy_all':correct/len(rows) if rows else None,
        'false_positives':fp,'false_negatives':fn,
        'false_positive_rate':fp/len(human) if human else None,
        'false_negative_rate':fn/len(ai) if ai else None,
        'error_rate':(len(rows)-len(accepted))/len(rows) if rows else None}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--weights',type=Path,default=ROOT/'work/forensics/checkpoint_epoch_5.safetensors')
    parser.add_argument('--manifest',type=Path,default=ROOT/'work/qa/manifest.json')
    parser.add_argument('--output-dir',type=Path,default=ROOT/'work/qa')
    parser.add_argument('--selection',default='SHA256(qa-v1:source_path), 100 human and 20 per SONAR generator; all 8 audio-only SWAN demos')
    args=parser.parse_args()
    folder=args.output_dir
    folder.mkdir(parents=True,exist_ok=True)
    samples=json.loads(args.manifest.read_text())
    for sample in samples:
        sample.setdefault('dataset','fresh-clone-test')
        sample.setdefault('group',sample.get('generator','human'))
    (folder/'phone').mkdir(exist_ok=True)
    start=time.perf_counter()
    model=load_model(args.weights,'cpu')
    output={'model':MODEL_ID,'revision':MODEL_REVISION,'threshold':0.5,'device':'cpu',
            'model_load_seconds':time.perf_counter()-start,
            'weights_sha256':hashlib.sha256(args.weights.read_bytes()).hexdigest(),
            'selection':args.selection,
            'phone_transform':'ffmpeg highpass=300,lowpass=3400; mono 8000 Hz G.711 mu-law WAV; simulated narrowband, not an actual call',
            'results':[]}
    for condition in ['original','phone_simulation']:
        for i,sample in enumerate(samples):
            row={**sample,'condition':condition}
            try:
                path=ROOT/sample['file']
                assert hashlib.sha256(path.read_bytes()).hexdigest()==sample['sha256'],'Fixture hash mismatch'
                if condition=='phone_simulation':
                    target=folder/'phone'/(sample['sha256']+'.wav')
                    subprocess.run(['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-y','-i',str(path),
                       '-af','highpass=f=300,lowpass=f=3400','-ac','1','-ar','8000','-c:a','pcm_mulaw',str(target)],check=True,capture_output=True)
                    path=target
                wav,meta=prepare_audio(path)
                row.update(meta)
                row.update(predict(model,wav,'cpu',0.5))
                row['correct']=row['prediction']==row['expected']
                row['status']='ok'
            except Exception as exc:
                row.update(status='error',prediction=None,correct=False,error=str(exc))
            output['results'].append(row)
            if (i+1)%20==0 or i==len(samples)-1:
                print(condition,i+1,'/',len(samples),flush=True)
                (folder/'results.json').write_text(json.dumps(output,indent=2)+'\n')
    grouped=defaultdict(list)
    for r in output['results']: grouped[(r['condition'],r['dataset'],r['group'])].append(r)
    output['groups']=[dict(condition=k[0],dataset=k[1],group=k[2],**metrics(v)) for k,v in grouped.items()]
    output['conditions']={c:metrics([r for r in output['results'] if r['condition']==c]) for c in ['original','phone_simulation']}
    (folder/'results.json').write_text(json.dumps(output,indent=2)+'\n')
    print(json.dumps(output['conditions'],indent=2),flush=True)
    return int(any(r['status']=='error' for r in output['results']))

if __name__ == '__main__': raise SystemExit(main())
