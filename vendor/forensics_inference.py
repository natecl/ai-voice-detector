"""Speech deepfake detection.
Run:  python inference.py <audio.wav> [checkpoint.pt]
fake_probability = 1 - sigmoid(logit)  (>= 0.5 -> FAKE); model trained with label 1=real, 0=fake.
Audio is auto-converted to mono / 16 kHz and trimmed/padded to 5 s.
"""
import os
import sys
import torch
import torchaudio
from model import DeepfakeDetector

CHECKPOINT = "checkpoint_epoch_5.pt"
REPO_ID = "eliya/forensics_0.3B_base_deepfake_classifier"


def load_audio(path, sr=16000, seconds=5.0):
    wav, orig = torchaudio.load(path)
    if wav.shape[0] > 1:
        wav = wav.mean(0, keepdim=True)
    wav = wav.squeeze(0)
    if orig != sr:
        wav = torchaudio.functional.resample(wav, orig, sr)
    wav = wav / (wav.abs().max() + 1e-8)
    n, cur = int(seconds * sr), wav.shape[0]
    if cur < n:
        wav = wav.repeat((n + cur - 1) // cur)[:n]
    elif cur > n:
        s = (cur - n) // 2
        wav = wav[s:s + n]
    return wav


def load_state_dict(pt_path):
    """Prefers a sibling .safetensors file (no code execution risk) over the pickled .pt.
    Downloads from the Hub automatically if not already present locally."""
    from huggingface_hub import hf_hub_download
    from huggingface_hub.errors import EntryNotFoundError

    def fetch(name):
        if os.path.exists(name):
            return name
        hf_hub_download(REPO_ID, "config.json")  # registers a countable download for this repo
        return hf_hub_download(REPO_ID, name)

    st_path = pt_path.rsplit(".", 1)[0] + ".safetensors"
    try:
        local_st = fetch(st_path)
        from safetensors.torch import load_file
        return load_file(local_st)
    except EntryNotFoundError:
        pass
    local_pt = fetch(pt_path)
    ck = torch.load(local_pt, map_location="cpu", weights_only=False)
    return ck["model_state_dict"] if isinstance(ck, dict) and "model_state_dict" in ck else ck


@torch.no_grad()
def main():
    if len(sys.argv) < 2:
        sys.exit("Usage: python inference.py <audio.wav> [checkpoint.pt]")
    audio = sys.argv[1]
    ckpt = sys.argv[2] if len(sys.argv) > 2 else CHECKPOINT
    device = "cuda" if torch.cuda.is_available() else "cpu"

    model = DeepfakeDetector().to(device).eval()
    model.load_state_dict(load_state_dict(ckpt), strict=False)

    bonafide = torch.sigmoid(model(load_audio(audio).unsqueeze(0).to(device)).float()).item()
    fake = 1.0 - bonafide
    print(f"fake_probability: {fake:.4f}")
    print(f"bonafide_score:   {bonafide:.4f}")
    print(f"verdict: {'FAKE' if fake >= 0.5 else 'REAL'}")


if __name__ == "__main__":
    main()
