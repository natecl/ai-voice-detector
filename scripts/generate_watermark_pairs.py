"""Controlled local QA: capture the same synthesis before/after watermark insertion."""
import os
os.environ.setdefault('HF_HUB_DISABLE_XET','1')
os.environ.setdefault('PYTORCH_ENABLE_MPS_FALLBACK','1')
import hashlib
import json
from pathlib import Path
import random
from datetime import datetime,timezone
import numpy as np
import soundfile as sf
import torch
from huggingface_hub import snapshot_download
from chatterbox.tts_turbo import ChatterboxTurboTTS

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'work/watermark-pairs'
MODEL='ResembleAI/chatterbox-turbo'
REVISION='749d1c1a46eb10492095d68fbcf55691ccf137cd'

class CaptureWatermarker:
    def __init__(self, delegate):
        self.delegate=delegate
        self.raw=None
    def apply_watermark(self, signal, sample_rate, **kwargs):
        self.raw=np.array(signal,copy=True)
        return self.delegate.apply_watermark(signal,sample_rate,**kwargs)


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    plan=json.loads((ROOT/'work/fresh-clones/plan.json').read_text())
    directory=snapshot_download(MODEL,revision=REVISION,allow_patterns=[
        've.safetensors','t3_turbo_v1.safetensors','s3gen_meanflow.safetensors','*.json','*.txt','*.model'])
    device='mps' if torch.backends.mps.is_available() else 'cpu'
    model=ChatterboxTurboTTS.from_local(directory,device)
    capture=CaptureWatermarker(model.watermarker)
    model.watermarker=capture
    manifest_path=OUT/'manifest.json'
    manifest=json.loads(manifest_path.read_text()) if manifest_path.exists() else [
        {**r,'variant':'human','group':'human'} for r in plan['human_controls']]
    complete={r.get('pair_id') for r in manifest if r.get('variant')=='watermarked'}
    for i,job in enumerate(plan['clone_jobs']):
        pair=f"{job['speaker_id']}_{job['text_index']}"
        if pair in complete:continue
        assert hashlib.sha256((ROOT/job['prompt']).read_bytes()).hexdigest()==job['prompt_sha256']
        random.seed(job['seed']);np.random.seed(job['seed']);torch.manual_seed(job['seed'])
        if device=='mps':torch.mps.manual_seed(job['seed'])
        capture.raw=None
        with torch.inference_mode():
            marked=model.generate(job['text'],audio_prompt_path=str(ROOT/job['prompt'])).squeeze().cpu().numpy()
        raw=capture.raw
        assert raw is not None and np.isfinite(raw).all() and np.isfinite(marked).all()
        n=min(len(raw),len(marked))
        delta_rms=float(np.sqrt(np.mean((raw[:n]-marked[:n])**2)))
        assert delta_rms>0, 'Watermark operation did not change waveform'
        pair_rows=[]
        for variant,wave in [('unwatermarked',raw),('watermarked',marked)]:
            path=OUT/f'clone_{pair}_{variant}.wav'
            sf.write(path,wave,model.sr,subtype='PCM_16')
            decoded,sr=sf.read(path,dtype='float32')
            with torch.inference_mode():
                wm=np.asarray(capture.delegate.get_watermark(decoded,sample_rate=sr,round=False))
            pair_rows.append({**job,'pair_id':pair,'file':str(path.relative_to(ROOT)),
                'expected':'AI','variant':variant,'group':variant,'generator':MODEL,'generator_revision':REVISION,
                'generated_at_utc':datetime.now(timezone.utc).isoformat(),'device':device,
                'duration_seconds':len(wave)/model.sr,'samples':len(wave),
                'watermark_decoder_mean':float(wm.mean()),'watermark_decoder_min':float(wm.min()),
                'watermark_decoder_max':float(wm.max()),'pair_waveform_delta_rms':delta_rms,
                'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
        manifest.extend(pair_rows)
        manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
        print(f"Captured pair {i+1}/15 {pair}: watermark decoder means raw={pair_rows[0]['watermark_decoder_mean']:.4f}, marked={pair_rows[1]['watermark_decoder_mean']:.4f}",flush=True)
    assert len(manifest)==40

if __name__=='__main__':main()
