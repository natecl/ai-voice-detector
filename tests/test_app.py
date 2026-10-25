import io
from pathlib import Path
import numpy as np
import soundfile as sf
from fastapi.testclient import TestClient
import app as web


def test_local_endpoint_rejects_cross_origin_and_empty_audio():
    client = TestClient(web.app)
    assert client.post('/analyze', content=b'x', headers={'Origin':'https://elsewhere.example'}).status_code == 403
    assert client.get('/',headers={'Host':'elsewhere.example'}).status_code == 403
    assert client.post('/analyze', content=b'').status_code == 400


def test_size_limit(monkeypatch):
    monkeypatch.setattr(web,'MAX_BYTES',4)
    assert TestClient(web.app).post('/analyze',content=b'12345').status_code == 413


def test_decode_failure_is_useful_and_removes_temporary_files(monkeypatch, tmp_path):
    import tempfile
    monkeypatch.setattr(tempfile,'tempdir',str(tmp_path))
    response=TestClient(web.app).post('/analyze',content=b'not audio')
    assert response.status_code == 400
    assert 'Could not read' in response.json()['error']
    assert list(tmp_path.iterdir()) == []


def test_silence_rejected_before_prediction():
    buffer=io.BytesIO()
    sf.write(buffer,np.zeros(80000),16000,format='WAV')
    response=TestClient(web.app).post('/analyze',content=buffer.getvalue())
    assert response.status_code==400
    assert 'silent' in response.json()['error']


def test_live_silence_waits_without_loading_model(monkeypatch):
    monkeypatch.setattr(web.service, 'warmup', lambda: (_ for _ in ()).throw(AssertionError('must skip inference')))
    buffer = io.BytesIO()
    sf.write(buffer, np.zeros(80000), 16000, format='WAV')
    response = TestClient(web.app).post('/analyze/live', content=buffer.getvalue())
    assert response.status_code == 200
    assert response.json()['status'] == 'insufficient_speech'
    assert 'prediction' not in response.json()


def test_live_origin_restriction():
    response = TestClient(web.app).post('/analyze/live', content=b'x', headers={'Origin':'https://elsewhere.example'})
    assert response.status_code == 403
