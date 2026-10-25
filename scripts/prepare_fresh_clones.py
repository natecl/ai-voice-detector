"""Select human controls and freeze new cloning prompts before generation."""
import hashlib
import io
import json
from pathlib import Path
import pyarrow.parquet as pq
import soundfile as sf

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'work/fresh-clones'
TEXTS=[
 'The train arrived early this morning, so we had time to buy coffee and walk through the station before our meeting.',
 'Could you check whether the blue notebook is on the kitchen table? I think I left it beside the window yesterday.',
 'We planted tomatoes and basil in the garden last weekend. If the weather stays warm, we should see new leaves soon.',
]

def main():
    OUT.mkdir(exist_ok=True)
    previous={r.get('source_path') for r in json.loads((ROOT/'work/qa/manifest.json').read_text())}
    groups={}
    for shard in sorted((ROOT/'work/qa').glob('test-*.parquet')):
        for r in pq.read_table(shard).to_pylist():
            if r['label']!=0 or r['path'] in previous: continue
            speaker=Path(r['path']).stem.split('_')[0]
            groups.setdefault(speaker,[]).append(r)
    selected=[]
    for speaker in sorted(groups,key=lambda s:hashlib.sha256(('fresh-v1:'+s).encode()).hexdigest()):
        eligible=[]
        for r in sorted(groups[speaker],key=lambda r:hashlib.sha256(r['path'].encode()).hexdigest()):
            a,sr=sf.read(io.BytesIO(r['audio']['bytes']))
            if 6 <= len(a)/sr <= 20: eligible.append((r,a,sr))
            if len(eligible)==2: break
        if len(eligible)!=2: continue
        for i,(r,a,sr) in enumerate(eligible):
            path=OUT/f'human_{speaker}_{i}.flac';path.write_bytes(r['audio']['bytes'])
            selected.append({'file':str(path.relative_to(ROOT)),'expected':'HUMAN','speaker_id':speaker,
                'source_path':r['path'],'source':'SONAR LibriTTS human subset',
                'dataset_revision':'ea98ab87279154094d2000198dd4b885c69aefaa',
                'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
            if i==0:
                prompt=OUT/f'prompt_{speaker}.wav';sf.write(prompt,a[:10*sr],sr)
        if len(selected)==10: break
    assert len(selected)==10
    plan={'selection':'5 hash-ordered speakers; 2 clips each, 6–20 seconds, excluding earlier QA clips',
          'texts':TEXTS,'human_controls':selected,
          'clone_jobs':[{'speaker_id':s,'text':text,'text_index':i,'seed':20261023+i,
              'prompt':str((OUT/f'prompt_{s}.wav').relative_to(ROOT)),
              'prompt_sha256':hashlib.sha256((OUT/f'prompt_{s}.wav').read_bytes()).hexdigest()}
              for s in sorted({r['speaker_id'] for r in selected}) for i,text in enumerate(TEXTS)]}
    (OUT/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    print('Frozen plan: 10 human controls, 15 Chatterbox clones, 5 speakers.')

if __name__=='__main__':main()
