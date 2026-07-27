"""Helpers to turn numpy frames into PNG bytes that Flet's Image(src=bytes) shows.

Transparency is made visible by compositing the RGBA frame onto a checkerboard of
the same size before encoding, so we don't depend on any Flet layering trick.
"""
from __future__ import annotations

import io

import numpy as np
from PIL import Image

_CHECK_A = np.array([84, 84, 90], dtype=np.uint8)
_CHECK_B = np.array([60, 60, 66], dtype=np.uint8)


def _checker(h: int, w: int, size: int = 12) -> np.ndarray:
    ys = (np.arange(h) // size)[:, None]
    xs = (np.arange(w) // size)[None, :]
    mask = ((ys + xs) % 2).astype(bool)
    out = np.empty((h, w, 3), dtype=np.uint8)
    out[mask] = _CHECK_A
    out[~mask] = _CHECK_B
    return out


def composite_on_checker(rgba: np.ndarray) -> np.ndarray:
    """Alpha-composite an HxWx4 frame onto a checkerboard -> HxWx3 uint8."""
    if rgba.shape[2] == 3:
        return rgba
    h, w = rgba.shape[:2]
    bg = _checker(h, w).astype(np.float32)
    rgb = rgba[:, :, :3].astype(np.float32)
    a = (rgba[:, :, 3:4].astype(np.float32)) / 255.0
    out = rgb * a + bg * (1.0 - a)
    return out.astype(np.uint8)


def to_png_bytes(arr: np.ndarray) -> bytes:
    """Encode an RGB or RGBA uint8 array to PNG bytes."""
    mode = "RGBA" if arr.ndim == 3 and arr.shape[2] == 4 else "RGB"
    buf = io.BytesIO()
    Image.fromarray(np.ascontiguousarray(arr), mode).save(buf, format="PNG")
    return buf.getvalue()


def preview_png(rgba: np.ndarray) -> bytes:
    """RGBA frame -> PNG bytes composited on the checkerboard, ready for ft.Image."""
    return to_png_bytes(composite_on_checker(rgba))
