"""Build a small provenance-labeled smoke set. Requires macOS say + ffmpeg.

Human source: LibriSpeech dummy validation subset (public audiobook speech).
AI source: macOS text-to-speech, same transcripts. Not a modern-clone benchmark.
"""
import io
import json
import subprocess
from pathlib import Path
from urllib.request import urlretrieve

import pyarrow.parquet as pq
import soundfile as sf

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "work" / "samples"
URL = "https://huggingface.co/datasets/hf-internal-testing/librispeech_asr_dummy/resolve/main/clean/validation-00000-of-00001.parquet"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    parquet = ROOT / "work" / "human-samples.parquet"
    if not parquet.exists():
        urlretrieve(URL, parquet)
    rows = pq.read_table(parquet).to_pylist()
    manifest = []
    candidates = []
    for row in rows:
        audio, rate = sf.read(io.BytesIO(row["audio"]["bytes"]), dtype="float32")
        if len(audio) / rate >= 6:
            candidates.append((row, audio, rate))
        if len(candidates) == 3:
            break
    for i, ((row, audio, rate), voice) in enumerate(zip(candidates, ["Samantha", "Daniel", "Karen"]), 1):
        human = OUT / f"human_{i}.wav"
        sf.write(human, audio, rate)
        manifest.append({"file": str(human.relative_to(ROOT)), "expected": "HUMAN",
                         "source": URL, "source_id": row.get("id"),
                         "speaker_id": row.get("speaker_id"), "text": row["text"]})
        intermediate = OUT / f"ai_{i}.aiff"
        synthetic = OUT / f"ai_{i}.wav"
        subprocess.run(["say", "-v", voice, "-o", str(intermediate), row["text"]], check=True)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(intermediate), str(synthetic)], check=True)
        manifest.append({"file": str(synthetic.relative_to(ROOT)), "expected": "AI",
                         "source": "macOS say", "voice": voice, "text": row["text"]})
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Prepared {len(manifest)} samples in {OUT}")


if __name__ == "__main__":
    main()
