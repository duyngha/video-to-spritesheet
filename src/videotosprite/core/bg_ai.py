"""AI background removal via rembg. Sessions are cached per model and the
per-frame matte is cached by the caller (FrameStore) so the cut-level slider only
re-thresholds an existing alpha instead of re-running the network.
"""
from __future__ import annotations

import numpy as np

# Models offered in the UI (name -> human label handled by the UI layer).
MODELS = ["u2net", "u2netp", "isnet-general-use"]

_sessions: dict[str, object] = {}


def _get_session(model: str):
    if model not in _sessions:
        # Imported lazily: rembg pulls onnxruntime and downloads the model on
        # first use, which we don't want to pay for at app startup.
        from rembg import new_session
        _sessions[model] = new_session(model)
    return _sessions[model]


def compute_matte(rgb: np.ndarray, model: str = "u2net",
                  alpha_matting: bool = False) -> np.ndarray:
    """Run rembg and return the raw HxW uint8 alpha matte (0..255)."""
    from rembg import remove
    rgba = remove(rgb, session=_get_session(model), alpha_matting=alpha_matting)
    rgba = np.asarray(rgba)
    if rgba.ndim == 3 and rgba.shape[2] == 4:
        return rgba[:, :, 3].copy()
    # Fallback: model returned RGB — treat as fully opaque.
    return np.full(rgb.shape[:2], 255, dtype=np.uint8)


def apply_matte(rgb: np.ndarray, matte: np.ndarray, cut: float) -> np.ndarray:
    """Combine an RGB frame with a cached matte, applying the cut level.

    ``cut`` (0..1) shifts where the matte is considered background. Values below
    the threshold are pushed to 0; the remaining range is rescaled to 0..255 so
    the slider gives a clean, controllable edge.
    """
    m = matte.astype(np.float32) / 255.0
    lo = float(np.clip(cut, 0.0, 0.99))
    alpha = np.clip((m - lo) / (1.0 - lo), 0.0, 1.0)
    alpha8 = (alpha * 255).astype(np.uint8)
    return np.dstack([rgb, alpha8]).astype(np.uint8)
