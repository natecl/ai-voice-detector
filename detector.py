"""Local audio -> Forensics -> HUMAN/AI prototype. No audio is uploaded."""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
from huggingface_hub import hf_hub_download
from transformers import WavLMConfig, WavLMModel
import torchaudio
from safetensors.torch import load_file

from vendor.forensics_model import DeepfakeDetector, AASISTPool, Classifier

SR = 16000
CROP = 5 * SR

MODEL_ID = "eliya/forensics_0.3B_base_deepfake_classifier"
MODEL_REVISION = "cfd11365b02167214dc3b392378809fef6ca3cfa"
BACKBONE_ID = "microsoft/wavlm-large"
BACKBONE_REVISION = "c1423ed94bb01d80a3f5ce5bc39f6026a0f4828c"


class InputError(ValueError):
    pass


def prepare_audio(path: Path):
    """Validate first, then preserve the published preprocessing exactly."""
    try:
        info = sf.info(path)
        if info.duration > 120:
            raise InputError("Audio exceeds the prototype's 120-second limit.")
        audio, sr = sf.read(path, dtype="float32", always_2d=True)
    except (RuntimeError, OSError) as exc:
        raise InputError(f"Cannot decode audio: {exc}") from exc
    if len(audio) < 0.4 * sr:
        raise InputError("Provide at least 0.4 seconds of audio; 5+ seconds of speech is recommended.")
    if not np.isfinite(audio).all():
        raise InputError("Audio contains non-finite samples.")
    # Match upstream: mean channels, resample, peak-normalize, center crop/repeat.
    waveform = torch.from_numpy(audio.mean(axis=1))
    if sr != SR:
        waveform = torchaudio.functional.resample(waveform, sr, SR)
    resampled_length = len(waveform)
    waveform = waveform / (waveform.abs().max() + 1e-8)
    if len(waveform) < CROP:
        waveform = waveform.repeat(math.ceil(CROP / len(waveform)))[:CROP]
    else:
        offset = (len(waveform) - CROP) // 2
        waveform = waveform[offset:offset + CROP]
    waveform = waveform.numpy()
    if not np.isfinite(waveform).all() or np.sqrt(np.mean(waveform ** 2)) < 1e-5:
        raise InputError("The analyzed crop is silent or invalid. Provide audible speech.")
    duration = len(audio) / sr
    # Reference crops after resampling; account for the same rounding.
    start = max(0, (resampled_length - CROP) // 2) / SR
    return waveform, {
        "duration_seconds": round(duration, 6),
        "analyzed_start_seconds": round(start, 6),
        "analyzed_end_seconds": round(min(duration, start + 5), 6),
        "repeated": duration < 5,
    }


class LocalForensics(DeepfakeDetector):
    def __init__(self):
        # Full fine-tuned weights are in the detector; download only base config.
        torch.nn.Module.__init__(self)
        config = WavLMConfig.from_pretrained(BACKBONE_ID, revision=BACKBONE_REVISION)
        config._attn_implementation = "eager"
        self.wavlm = WavLMModel(config)
        self.pool = AASISTPool(config.hidden_size, config.num_hidden_layers)
        self.classifier = Classifier(self.pool.output_dim, 320, 3)


def choose_device(requested: str) -> str:
    if requested == "auto":
        return "mps" if torch.backends.mps.is_available() else "cpu"
    if requested == "mps" and not torch.backends.mps.is_available():
        raise ValueError("MPS is unavailable; use --device cpu.")
    return requested


def validate_checkpoint(state):
    """Reject invalid published or custom weights before any prediction."""
    for name, tensor in state.items():
        if isinstance(tensor, torch.Tensor) and (tensor.is_floating_point() or tensor.is_complex()):
            invalid = int((~torch.isfinite(tensor)).sum().item())
            if invalid:
                raise ValueError(
                    f"Invalid checkpoint: {name} contains {invalid} non-finite weights. "
                    "Obtain a corrected Forensics checkpoint; no prediction can be trusted."
                )


def load_model(weights: Path | None, device: str):
    if weights is None:
        weights = Path(hf_hub_download(
            MODEL_ID, "checkpoint_epoch_5.safetensors", revision=MODEL_REVISION
        ))
    # Safetensors only: never execute checkpoint pickle payloads.
    state = load_file(str(weights), device="cpu")
    validate_checkpoint(state)
    # The published inference architecture never uses this auxiliary projection.
    # Upstream ignores extras via strict=False. Exclude only these four known
    # tensors, then strictly validate every parameter that participates in inference.
    auxiliary_shapes = {
        "projection.0.weight": (320, 320), "projection.0.bias": (320,),
        "projection.2.weight": (320, 320), "projection.2.bias": (320,),
    }
    for key, shape in auxiliary_shapes.items():
        if key in state:
            if tuple(state[key].shape) != shape:
                raise ValueError(f"Unexpected auxiliary tensor shape: {key}")
            del state[key]
    model = LocalForensics()
    model.load_state_dict(state, strict=True)
    del state
    return model.eval().to(device)


def predict(model, waveform, device: str, threshold: float):
    started = time.perf_counter()
    with torch.inference_mode():
        score = (1.0 - torch.sigmoid(model(torch.from_numpy(waveform)[None].to(device)))).item()
    if not math.isfinite(score):
        raise RuntimeError("Model returned a non-finite score.")
    return {
        "prediction": "AI" if score >= threshold else "HUMAN",
        "synthetic_score": score,
        "threshold": threshold,
        "inference_seconds": round(time.perf_counter() - started, 4),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", type=Path, nargs="+")
    parser.add_argument("--device", choices=("auto", "cpu", "mps"), default="cpu")
    parser.add_argument("--weights", type=Path, help="Optional local checkpoint")
    parser.add_argument("--threshold", type=float, default=0.5)
    parser.add_argument("--json", action="store_true", help="Emit one JSON object per file")
    args = parser.parse_args(argv)
    if not 0 < args.threshold < 1:
        parser.error("--threshold must be between 0 and 1")
    prepared, failed = [], False
    for path in args.files:
        try:
            wav, metadata = prepare_audio(path)
            prepared.append((path, wav, metadata))
        except (InputError, ValueError) as exc:
            failed = True
            error = {"file": str(path), "error": str(exc)}
            print(json.dumps(error) if args.json else f"{path}: ERROR: {exc}", flush=True)
    if not prepared:
        return 1
    device = choose_device(args.device)
    print(f"Loading Forensics on {device}; audio stays local.", file=sys.stderr)
    started = time.perf_counter()
    model = load_model(args.weights, device)
    load_seconds = round(time.perf_counter() - started, 4)
    for path, wav, metadata in prepared:
        result = {"file": str(path), **metadata, **predict(model, wav, device, args.threshold),
                  "device": device, "model": MODEL_ID, "model_revision": MODEL_REVISION,
                  "weights_source": str(args.weights) if args.weights else "pinned_hub",
                  "model_load_seconds": load_seconds,
                  "note": "Prediction only. Score is not calibrated confidence. Only the reported crop was analyzed."}
        if args.json:
            print(json.dumps(result), flush=True)
        else:
            print(f"{path}: {result['prediction']} | synthetic score {result['synthetic_score']:.4f}"
                  f" | crop {metadata['analyzed_start_seconds']:.2f}-{metadata['analyzed_end_seconds']:.2f}s"
                  f" | {result['inference_seconds']:.2f}s ({device})", flush=True)
    return int(failed)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"Detector failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
