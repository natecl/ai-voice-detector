import numpy as np
import pytest
import soundfile as sf

from detector import InputError, prepare_audio
import torch
import torchaudio


def test_silence_is_not_classified_as_human(tmp_path):
    path = tmp_path / "silence.wav"
    sf.write(path, np.zeros(64000), 16000)
    with pytest.raises(InputError, match="silent"):
        prepare_audio(path)


def test_short_input_is_rejected(tmp_path):
    path = tmp_path / "short.wav"
    sf.write(path, np.ones(160), 16000)
    with pytest.raises(InputError, match="at least"):
        prepare_audio(path)


def test_preprocessing_matches_reference_and_reports_crop(tmp_path):
    path = tmp_path / "stereo.wav"
    signal = np.random.default_rng(42).normal(0, 0.1, (48000 * 6, 2))
    sf.write(path, signal, 48000)
    waveform, metadata = prepare_audio(path)
    audio, sr = sf.read(path, dtype="float32", always_2d=True)
    reference = torchaudio.functional.resample(torch.from_numpy(audio.T).mean(0), sr, 16000)
    reference = reference / (reference.abs().max() + 1e-8)
    start = (len(reference) - 80000) // 2
    np.testing.assert_allclose(waveform, reference[start:start + 80000].numpy(), atol=1e-6)
    assert waveform.shape == (80000,)
    assert metadata["analyzed_start_seconds"] == 0.5
    assert metadata["analyzed_end_seconds"] == 5.5


def test_silent_center_is_rejected_even_with_sound_at_edges(tmp_path):
    path = tmp_path / "edges.wav"
    audio = np.zeros(16000 * 12)
    audio[:1600] = 0.2
    audio[-1600:] = -0.2
    sf.write(path, audio, 16000)
    with pytest.raises(InputError, match="silent"):
        prepare_audio(path)


def test_invalid_checkpoint_is_rejected_before_inference():
    import torch
    from detector import validate_checkpoint
    with pytest.raises(ValueError, match="2 non-finite weights"):
        validate_checkpoint({"bad_layer": torch.tensor([0.0, float("nan"), float("inf")])})
    validate_checkpoint({"good_layer": torch.tensor([0.0, 1.0])})


def test_nonfinite_output_never_becomes_human_label():
    import torch
    from detector import predict
    with pytest.raises(RuntimeError, match="non-finite score"):
        predict(lambda _: torch.tensor(float("nan")), np.zeros(64000, dtype=np.float32), "cpu", 0.5)


def test_score_direction_matches_real_positive_training_label():
    from detector import predict
    waveform = np.zeros(80000, dtype=np.float32)
    assert predict(lambda _: torch.tensor(8.0), waveform, "cpu", 0.5)["prediction"] == "HUMAN"
    assert predict(lambda _: torch.tensor(-8.0), waveform, "cpu", 0.5)["prediction"] == "AI"


def test_short_speech_is_repeated_with_correct_metadata(tmp_path):
    path = tmp_path / "short_speech.wav"
    audio = np.sin(np.arange(16000) * 0.1).astype(np.float32) * 0.2
    sf.write(path, audio, 16000)
    waveform, metadata = prepare_audio(path)
    assert len(waveform) == 80000
    assert metadata["repeated"] is True
    assert metadata["analyzed_end_seconds"] == 1.0
    np.testing.assert_array_equal(waveform[:16000], waveform[16000:32000])
