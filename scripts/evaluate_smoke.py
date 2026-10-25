"""Evaluate the labeled smoke samples, measuring CPU/MPS agreement."""
import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import torch
from detector import MODEL_ID, MODEL_REVISION, load_model, predict, prepare_audio


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--weights", type=Path)
    parser.add_argument("--device", choices=("cpu", "mps", "both"), default="cpu")
    args = parser.parse_args()
    samples = json.loads((ROOT / "work/samples/manifest.json").read_text())
    started = time.perf_counter()
    try:
        model = load_model(args.weights, "cpu")
    except (ValueError, RuntimeError, OSError) as exc:
        output = {"model": MODEL_ID, "revision": MODEL_REVISION,
                  "status": "blocked", "error": str(exc),
                  "results": [{**sample, "status": "not_run", "prediction": None} for sample in samples]}
        (ROOT / "work/smoke-results.json").write_text(json.dumps(output, indent=2) + "\n")
        print(f"Evaluation blocked: {exc}", file=sys.stderr)
        return 1
    print(f"Model load: {time.perf_counter() - started:.2f}s", flush=True)
    rows = []
    devices = (["cpu"] + (["mps"] if torch.backends.mps.is_available() else [])) if args.device == "both" else [args.device]
    for device in devices:
        model.to(device)
        for sample in samples:
            wav, metadata = prepare_audio(ROOT / sample["file"])
            result = {**sample, **metadata, **predict(model, wav, device, 0.5), "device": device}
            result["correct"] = result["prediction"] == sample["expected"]
            rows.append(result)
            print(f"{device} {sample['file']}: expected={sample['expected']}"
                  f" predicted={result['prediction']} score={result['synthetic_score']:.6f}"
                  f" time={result['inference_seconds']}s", flush=True)
        # Save after each device so CPU findings survive an MPS failure.
        output = {"model": MODEL_ID, "revision": MODEL_REVISION, "results": rows,
                  "limitations": "Three excerpts from one human speaker; three macOS TTS voices. Training overlap unknown. Smoke test, not general accuracy."}
        (ROOT / "work/smoke-results.json").write_text(json.dumps(output, indent=2) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
