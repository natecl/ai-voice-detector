# Current detector: Forensics 0.3B

Author: Eliya Segev (2026), Forensics 0.3B Speech Deepfake Detection Classifier.
Source: https://huggingface.co/eliya/forensics_0.3B_base_deepfake_classifier
Revision: `cfd11365b02167214dc3b392378809fef6ca3cfa`.
License: CC BY-NC 4.0, https://creativecommons.org/licenses/by-nc/4.0/

`vendor/forensics_model.py` and `vendor/forensics_inference.py` are unmodified
copies of the supplied architecture and reference inference script. The latter
is retained for reference only; our app does not invoke its pickle loader or
non-strict loading. We use safetensors, validate finite weights, and require
strict state-dictionary loading for inference parameters. The checkpoint also
contains four `projection.{0,2}.{weight,bias}` tensors absent from the published
inference architecture; we validate their expected shapes and explicitly omit
only those unused tensors. All checkpoint tensors are checked for finite values.

Our adapter initializes the WavLM architecture from its pinned configuration,
loads the full detector state, decodes using soundfile instead of torchaudio's
codec backend, and follows the reference preprocessing and score direction.
It adds input validation, crop metadata, CLI/JSON output, and timing.
No training or weight modification was performed.

Backbone: https://huggingface.co/microsoft/wavlm-large
Configuration revision: `c1423ed94bb01d80a3f5ce5bc39f6026a0f4828c`.
The complete fine-tuned weights are supplied by the detector checkpoint.

## Earlier Pella experiment

# Third-party model attribution

`vendor/pellav2_infer.py` is the unchanged reference implementation from
https://huggingface.co/Sadanie/pellav2-audio-deepfake-detector,
revision `808e16a49526178f8e1e6276725dfd14f218ec82`.
The model repository declares the MIT license in its metadata. Retain upstream
attribution; check upstream licensing before redistributing model weights.

The detector uses the `facebook/w2v-bert-2.0` architecture/configuration,
revision `da985ba0987f70aaeb84a80f2851cfac8c697a7b`.
The full fine-tuned backbone is loaded from the Pella checkpoint with strict
state-dictionary matching, rather than downloading a second set of base weights.

Prototype changes: input validation and crop metadata, CPU feature extraction
for MPS compatibility, pinned configuration, weights-only loading, JSON output,
timing, and a reusable prediction function. We did not train this detector.

## Windows audio capture

The Windows companion references `NAudio.Wasapi` 2.2.1 (and its NuGet
dependencies), distributed under the MIT license. Source and license:
https://github.com/naudio/NAudio/tree/v2.2.1 and
https://github.com/naudio/NAudio/blob/v2.2.1/license.txt.
Packages are restored by NuGet; no NAudio source is vendored here.
