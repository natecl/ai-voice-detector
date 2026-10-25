"""Local-only browser UI for the audio detector. Run: python app.py"""
from contextlib import asynccontextmanager
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import numpy as np
import soundfile as sf
import webrtcvad

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from starlette.concurrency import run_in_threadpool

from detector import InputError, load_model, predict, prepare_audio

ROOT = Path(__file__).resolve().parent
MAX_BYTES = 25 * 1024 * 1024


class DetectorService:
    def __init__(self):
        self.model = None
        self.lock = threading.Lock()

    def warmup(self):
        with self.lock:
            if self.model is None:
                weights = ROOT / 'work/forensics/checkpoint_epoch_5.safetensors'
                self.model = load_model(weights if weights.exists() else None, 'cpu')

    def analyze(self, content, live=False):
        if not content:
            raise InputError('Choose an audio file or record your voice first.')
        if not shutil.which('ffmpeg'):
            raise RuntimeError('ffmpeg is required to read recordings and audio uploads.')
        with tempfile.TemporaryDirectory(prefix='voice-detector-') as directory:
            source, decoded = Path(directory)/'input', Path(directory)/'audio.wav'
            source.write_bytes(content)
            try:
                subprocess.run([
                    'ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error',
                    '-protocol_whitelist', 'file,pipe', '-i', str(source),
                    '-map', '0:a:0', '-vn', '-t', '121', '-ac', '1', '-ar', '16000',
                    '-c:a', 'pcm_f32le', str(decoded),
                ], check=True, capture_output=True, timeout=30)
            except subprocess.TimeoutExpired as exc:
                raise InputError('Audio took too long to decode. Try a shorter WAV file.') from exc
            except subprocess.CalledProcessError as exc:
                raise InputError('Could not read this audio. Try WAV, MP3, M4A, FLAC, OGG, or WebM.') from exc
            speech_fraction = None
            if live:
                audio, rate = sf.read(decoded, dtype='float32')
                # Test raw level before the model's peak normalization amplifies quiet noise.
                level = float(np.sqrt(np.mean(audio ** 2))) if len(audio) else 0.0
                pcm = (np.clip(audio,-1,1) * 32767).astype('<i2').tobytes()
                frames = [pcm[i:i+960] for i in range(0,len(pcm)-959,960)]
                vad = webrtcvad.Vad(2)
                speech_fraction = sum(vad.is_speech(frame,16000) for frame in frames)/len(frames) if frames else 0.0
                if level < 0.002 or speech_fraction < 0.30:
                    return {'status':'insufficient_speech','speech_fraction':speech_fraction,
                            'message':'Waiting for clearer speech…'}
            waveform, metadata = prepare_audio(decoded)
            self.warmup()
            with self.lock:
                result = predict(self.model, waveform, 'cpu', 0.5)
            return {**result, **metadata, 'status':'ok', 'speech_fraction':speech_fraction, 'model': 'Forensics 0.3B', 'device': 'cpu'}


service = DetectorService()

@asynccontextmanager
async def lifespan(app):
    await run_in_threadpool(service.warmup)
    yield

app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None)

@app.middleware('http')
async def local_only(request, call_next):
    allowed = {'127.0.0.1:8765', 'localhost:8765', 'testserver'}
    if request.headers.get('host') not in allowed:
        return JSONResponse({'error': 'Use the local detector address.'}, status_code=403)
    origin = request.headers.get('origin')
    if origin and origin not in {'http://127.0.0.1:8765', 'http://localhost:8765'}:
        return JSONResponse({'error': 'Requests must come from this local page.'}, status_code=403)
    response = await call_next(request)
    response.headers['Cache-Control'] = 'no-store'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'no-referrer'
    return response

@app.get('/')
def index():
    return FileResponse(ROOT/'ui/index.html')

@app.get('/health')
def health():
    return {'ready': service.model is not None, 'local': True}

@app.post('/analyze/live')
@app.post('/analyze')
async def analyze(request: Request):
    content = bytearray()
    async for chunk in request.stream():
        content.extend(chunk)
        if len(content) > MAX_BYTES:
            return JSONResponse({'error': 'File is too large. Maximum size is 25 MB.'}, status_code=413)
    try:
        return await run_in_threadpool(service.analyze, bytes(content), request.url.path == '/analyze/live')
    except InputError as exc:
        return JSONResponse({'error': str(exc)}, status_code=400)
    except (RuntimeError, OSError, ValueError) as exc:
        return JSONResponse({'error': f'Detector could not finish: {exc}'}, status_code=503)

if __name__ == '__main__':
    import uvicorn
    print('Opening local detector at http://127.0.0.1:8765 — loading model first.', flush=True)
    uvicorn.run(app, host='127.0.0.1', port=8765)
