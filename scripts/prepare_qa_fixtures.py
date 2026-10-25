"""Fetch public research fixtures and select them before running predictions."""
import concurrent.futures
import hashlib
import json
import re
import urllib.request
from pathlib import Path
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'work/qa'
REVISION = 'ea98ab87279154094d2000198dd4b885c69aefaa'
BASE = f'https://huggingface.co/datasets/SpeechAntiSpoofingBenchmarks/SONAR/resolve/{REVISION}'
SHARDS = {
 'test-00000-of-00002.parquet': 'e398e67c65b0fe18ef6ac45a9d0f4f8c4685d62c2cab6b53f7d2ce381e22ef2d',
 'test-00001-of-00002.parquet': '54c9b77e96202ca9ea73c309e26d8f7693a305619fcf0143ec86581e4aa73a72',
}

def fetch(job):
    url, path = job
    if not path.exists():
        temporary = path.with_suffix(path.suffix + '.partial')
        urllib.request.urlretrieve(url, temporary)
        temporary.replace(path)
    return path


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT/'audio').mkdir(exist_ok=True)
    html = urllib.request.urlopen('https://swan-df.github.io/').read().decode()
    (OUT/'swan.html').write_text(html)
    demo_paths = sorted(set(re.findall(r'src="(audios/[^\"]+\.wav)"', html)))
    assert len(demo_paths) == 8, 'Source layout changed; verify labels before continuing.'
    jobs = [(BASE+'/data/'+name, OUT/name) for name in SHARDS]
    jobs += [('https://swan-df.github.io/'+p, OUT/'audio'/Path(p).name) for p in demo_paths]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for p in pool.map(fetch,jobs): print('Downloaded',p.name,flush=True)
    groups = {}
    for name, expected_hash in SHARDS.items():
        path = OUT/name
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected_hash
        for row in pq.read_table(path).to_pylist():
            notes = json.loads(row['notes'])
            group = 'human' if row['label'] == 0 else notes['system']
            groups.setdefault(group,[]).append(row)
    manifest = []
    # Stable hash ordering, no score-based selection. 100 human + 20 per generator.
    for group, rows in sorted(groups.items()):
        rows.sort(key=lambda r: hashlib.sha256(('qa-v1:'+r['path']).encode()).hexdigest())
        for row in rows[:100 if group == 'human' else 20]:
            content = row['audio']['bytes']
            sha = hashlib.sha256(content).hexdigest()
            path = OUT/'audio'/(sha+'.flac')
            path.write_bytes(content)
            manifest.append({'file':str(path.relative_to(ROOT)), 'expected':'HUMAN' if row['label']==0 else 'AI',
                'dataset':'SONAR', 'group':group, 'source_path':row['path'], 'dataset_revision':REVISION,
                'sha256':sha, 'notes':json.loads(row['notes'])})
    for source in demo_paths:
        path = OUT/'audio'/Path(source).name
        name = path.name
        group = ('human' if 'original' in name else 'YourTTS-voice-conversion' if 'voice-conversion' in name
                 else 'AdaSpeech-adapted' if 'Adaspeech' in name else 'TorToiSe-tuned')
        manifest.append({'file':str(path.relative_to(ROOT)), 'expected':'HUMAN' if group=='human' else 'AI',
             'dataset':'SWAN-LibriTTS-DF-demos', 'group':group,'source_url':'https://swan-df.github.io/'+source,
             'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print('Selected',len(manifest),'fixtures; full group sizes:',{k:len(v) for k,v in groups.items()})

if __name__ == '__main__': main()
