"""Generate fresh, watermarked Chatterbox-Turbo clones from a frozen plan."""
import os
os.environ.setdefault('HF_HUB_DISABLE_XET','1')
os.environ.setdefault('PYTORCH_ENABLE_MPS_FALLBACK','1')
import hashlib
import json
from pathlib import Path
import random
import time
from datetime import datetime,timezone
import numpy as np
import soundfile as sf
import torch
from huggingface_hub import snapshot_download
from chatterbox.tts_turbo import ChatterboxTurboTTS

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'work/fresh-clones'
MODEL='ResembleAI/chatterbox-turbo'
REVISION='749d1c1a46eb10492095d68fbcf55691ccf137cd'

def main():
    plan=json.loads((OUT/'plan.json').read_text())
    directory=snapshot_download(MODEL,revision=REVISION,allow_patterns=['ve.safetensors','t3_turbo_v1.safetensors','s3gen_meanflow.safetensors','*.json','*.txt','*.model'])
    device='mps' if torch.backends.mps.is_available() else 'cpu'
    model=ChatterboxTurboTTS.from_local(directory,device)
    manifest_path=OUT/'chatterbox-manifest.json'
    manifest=json.loads(manifest_path.read_text()) if manifest_path.exists() else list(plan['human_controls'])
    completed={r['file'] for r in manifest}
    for i,job in enumerate(plan['clone_jobs']):
        path=OUT/f"chatterbox_{job['speaker_id']}_{job['text_index']}.wav"
        relative=str(path.relative_to(ROOT))
        if relative in completed:continue
        prompt=ROOT/job['prompt']
        assert hashlib.sha256(prompt.read_bytes()).hexdigest()==job['prompt_sha256']
        random.seed(job['seed']);np.random.seed(job['seed']);torch.manual_seed(job['seed'])
        if device=='mps':torch.mps.manual_seed(job['seed'])
        started=time.perf_counter()
        with torch.inference_mode():
            audio=model.generate(job['text'],audio_prompt_path=str(prompt))
        waveform=audio.squeeze().cpu().numpy()
        assert np.isfinite(waveform).all() and len(waveform)>0
        sf.write(path,waveform,model.sr)
        row={**job,'file':relative,'expected':'AI','generator':MODEL,'generator_revision':REVISION,
             'generated_at_utc':datetime.now(timezone.utc).isoformat(),'watermark':'upstream Perth watermark retained',
             'device':device,'duration_seconds':len(waveform)/model.sr,
             'generation_seconds':time.perf_counter()-started,
             'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
        manifest.append(row)
        manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
        print(f"Generated {i+1}/{len(plan['clone_jobs'])}: {path.name}, {row['duration_seconds']:.2f}s audio, {row['generation_seconds']:.1f}s generation",flush=True)

if __name__=='__main__':main()
