from __future__ import annotations

import math

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly


def load_audio(path: str, sample_rate: int):
    """Load audio as mono float32 numpy without relying on torchaudio's codec stack.

    Newer torchaudio versions delegate decoding to torchcodec, which requires
    matching shared FFmpeg libraries in the container. SoundFile handles WAV/FLAC
    directly and is enough for Jimsky's bounded smoke tests and most payloads.
    """
    data, original_sample_rate = sf.read(path, dtype="float32", always_2d=True)
    if data.shape[1] > 1:
        data = data.mean(axis=1)
    else:
        data = data[:, 0]

    if original_sample_rate != sample_rate:
        divisor = math.gcd(int(original_sample_rate), int(sample_rate))
        up = int(sample_rate) // divisor
        down = int(original_sample_rate) // divisor
        data = resample_poly(data, up, down).astype(np.float32)

    return data.astype(np.float32, copy=False)
