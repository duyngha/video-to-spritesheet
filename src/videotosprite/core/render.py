"""Single place that turns a Frame + background settings into a final RGBA image.

Both the live preview (UI) and the exporter call this so what you see is exactly
what gets written. Settings cover background removal (none / chroma / AI) plus an
optional spatial crop expressed in normalised coordinates so it is resolution
independent.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

import numpy as np
from PIL import Image

from . import bg_ai, chroma
from .frames import Frame


class BgMode(str, Enum):
    NONE = "none"
    CHROMA = "chroma"
    AI = "ai"


@dataclass
class BgSettings:
    mode: BgMode = BgMode.NONE
    chroma: chroma.ChromaSettings = field(default_factory=chroma.ChromaSettings)
    ai_cut: float = 0.0            # cut level applied to the cached rembg matte
    ai_model: str = "u2net"       # rembg model name
    ai_alpha_matting: bool = False  # finer edges (slower)
    # Normalised crop rect (fx, fy, fw, fh) in 0..1, or None for the full frame.
    crop: tuple[float, float, float, float] | None = None


def _resize_rgb(rgb: np.ndarray, max_dim: int) -> np.ndarray:
    h, w = rgb.shape[:2]
    scale = max_dim / max(h, w)
    if scale >= 1.0:
        return rgb
    nw, nh = max(int(w * scale), 1), max(int(h * scale), 1)
    return np.asarray(Image.fromarray(rgb).resize((nw, nh), Image.BILINEAR))


def _resize_matte(matte: np.ndarray, size: tuple[int, int]) -> np.ndarray:
    w, h = size
    if matte.shape[:2] == (h, w):
        return matte
    return np.asarray(Image.fromarray(matte).resize((w, h), Image.BILINEAR))


def _apply_crop(rgba: np.ndarray, crop: tuple[float, float, float, float]) -> np.ndarray:
    h, w = rgba.shape[:2]
    fx, fy, fw, fh = crop
    x0 = int(round(np.clip(fx, 0, 1) * w))
    y0 = int(round(np.clip(fy, 0, 1) * h))
    x1 = int(round(np.clip(fx + fw, 0, 1) * w))
    y1 = int(round(np.clip(fy + fh, 0, 1) * h))
    x0, x1 = sorted((x0, x1))
    y0, y1 = sorted((y0, y1))
    if x1 - x0 < 1 or y1 - y0 < 1:
        return rgba
    return rgba[y0:y1, x0:x1].copy()


def render(frame: Frame, s: BgSettings, *, allow_ai_compute: bool = False,
           max_dim: int | None = None, apply_crop: bool = True) -> np.ndarray:
    """Return an HxWx4 RGBA array for ``frame`` under settings ``s``.

    ``max_dim`` downscales the working image first (used by the live preview to
    keep slider drags snappy); export passes None for full resolution. When
    ``mode`` is AI and no matte is cached, the matte is only computed if
    ``allow_ai_compute`` is True.
    """
    rgb = frame.rgb
    if max_dim:
        rgb = _resize_rgb(rgb, max_dim)

    if s.mode == BgMode.CHROMA:
        rgba = chroma.apply(rgb, s.chroma)
    elif s.mode == BgMode.AI:
        matte = frame.ai_matte
        if matte is None:
            if not allow_ai_compute:
                rgba = _opaque(rgb)
                return _crop(rgba, s, apply_crop)
            matte = bg_ai.compute_matte(frame.rgb, s.ai_model, s.ai_alpha_matting)
            frame.ai_matte = matte
        matte = _resize_matte(matte, (rgb.shape[1], rgb.shape[0]))
        rgba = bg_ai.apply_matte(rgb, matte, s.ai_cut)
    else:
        rgba = _opaque(rgb)

    return _crop(rgba, s, apply_crop)


def _crop(rgba: np.ndarray, s: BgSettings, apply_crop: bool) -> np.ndarray:
    if apply_crop and s.crop is not None:
        return _apply_crop(rgba, s.crop)
    return rgba


def _opaque(rgb: np.ndarray) -> np.ndarray:
    alpha = np.full(rgb.shape[:2], 255, dtype=np.uint8)
    return np.dstack([rgb, alpha]).astype(np.uint8)
