"""Local audio -> Pella -> HUMAN/AI prototype. No audio is uploaded."""
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
from transformers import Wav2Vec2BertConfig, Wav2Vec2BertModel

from vendor.pellav2_infer import CROP, SR, Detector, load_clip

MODEL_ID = "Sadanie/pellav2-audio-deepfake-detector"
MODEL_REVISION = "808e16a49526178f8e1e6276725dfd14f218ec82"
BACKBONE_ID = "facebook/w2v-bert-2.0"
BACKBONE_REVISION = "da985ba0987f70aaeb84a80f2851cfac8c697a7b"


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
        raise InputError("Provide at least 0.4 seconds of audio; 4+ seconds of speech is recommended.")
    if not np.isfinite(audio).all():
        raise InputError("Audio contains non-finite samples.")
    waveform = load_clip(str(path))
    if not np.isfinite(waveform).all() or np.sqrt(np.mean(waveform ** 2)) < 1e-5:
        raise InputError("The analyzed crop is silent or invalid. Provide audible speech.")
    duration = len(audio) / sr
    # Reference crops after resampling; account for the same rounding.
    resampled_length = math.ceil(len(audio) * SR / sr)
    start = max(0, (resampled_length - CROP) // 2) / SR
    return waveform, {
        "duration_seconds": round(duration, 6),
        "analyzed_start_seconds": round(start, 6),
        "analyzed_end_seconds": round(min(duration, start + 4), 6),
        "padded": duration < 4,
    }


class LocalPella(Detector):
    def __init__(self):
        # The detector checkpoint contains the entire backbone, so fetch only
        # its pinned configuration rather than downloading base weights too.
        torch.nn.Module.__init__(self)
        config = Wav2Vec2BertConfig.from_pretrained(
            BACKBONE_ID, revision=BACKBONE_REVISION
        )
        config._attn_implementation = "eager"
        self.backbone = Wav2Vec2BertModel(config)
        self.layer_weights = torch.nn.Parameter(
            torch.zeros(config.num_hidden_layers + 1)
        )
        self.head = torch.nn.Linear(config.hidden_size, 1)

    @staticmethod
    def features(wav):
        # Kaldi feature extraction remains on CPU for consistent Mac support.
        features, mask = Detector.features(wav.cpu())
        return features.to(wav.device), mask.to(wav.device)


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
                    "Obtain a corrected Pella checkpoint; no prediction can be trusted."
                )


def load_model(weights: Path | None, device: str):
    if weights is None:
        weights = Path(hf_hub_download(
            MODEL_ID, "pellav2_detector.pt", revision=MODEL_REVISION
        ))
    # weights_only avoids executing pickled Python objects from a checkpoint.
    state = torch.load(weights, map_location="cpu", weights_only=True, mmap=True)
    validate_checkpoint(state)
    model = LocalPella()
    model.load_state_dict(state, strict=True)
    del state
    return model.eval().to(device)


def predict(model, waveform, device: str, threshold: float):
    started = time.perf_counter()
    with torch.inference_mode():
        score = torch.sigmoid(model(torch.from_numpy(waveform)[None].to(device))).item()
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
    parser.add_argument("--device", choices=("auto", "cpu", "mps"), default="auto")
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
    print(f"Loading Pella on {device}; audio stays local.", file=sys.stderr)
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
