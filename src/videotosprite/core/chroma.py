"""Chroma-key background removal driven by numpy (fast enough for live preview).

The "nível de corte" the user asked for maps to ``tolerance``: every pixel whose
colour distance to the key colour is below it becomes fully transparent. A second
``softness`` band feathers the edge so the cut-out isn't jagged.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

try:  # cv2 only used for the optional edge blur; degrade gracefully without it
    import cv2
except Exception:  # pragma: no cover
    cv2 = None


@dataclass
class ChromaSettings:
    color: tuple[int, int, int] = (0, 255, 0)  # key colour (RGB)
    tolerance: float = 0.18   # 0..1 — distance fully cut (the "cut level")
    softness: float = 0.10    # 0..1 — feather band above the tolerance
    spill: float = 0.0        # 0..1 — desaturate the key colour bleeding on edges
    feather_px: int = 0       # optional blur of the alpha edge in pixels
    # Magic-wand mode: only remove the background region that is connected to the
    # image borders, so areas of the same colour *inside* the subject (e.g. the
    # white patches of a cow on a white background) are preserved.
    connected: bool = False
    close_px: int = 0         # close small gaps in the outline so bg can't leak in
    # Extra seed points (normalised x,y in 0..1): the background blob under each
    # is also removed, even when it doesn't touch a border.
    seeds: list[tuple[float, float]] = field(default_factory=list)


def sample_color(rgb: np.ndarray, x: int, y: int, radius: int = 2) -> tuple[int, int, int]:
    """Sample a colour from ``rgb`` at (x, y) using the **median** of a small
    window around it. The median (vs a single pixel or a mean) rejects video
    noise/compression artefacts and the odd edge pixel, so the eyedropper lands on
    the representative background colour."""
    h, w = rgb.shape[:2]
    x = int(np.clip(x, 0, w - 1))
    y = int(np.clip(y, 0, h - 1))
    x0, x1 = max(x - radius, 0), min(x + radius + 1, w)
    y0, y1 = max(y - radius, 0), min(y + radius + 1, h)
    patch = rgb[y0:y1, x0:x1].reshape(-1, rgb.shape[2])[:, :3]
    return tuple(int(v) for v in np.median(patch, axis=0))


def compute_alpha(rgb: np.ndarray, s: ChromaSettings) -> np.ndarray:
    """Return an HxW uint8 alpha mask (0 = background, 255 = subject)."""
    img = rgb.astype(np.float32) / 255.0
    key = np.array(s.color, dtype=np.float32) / 255.0

    # Euclidean distance in RGB (normalised to 0..1) so *any* solid colour works,
    # including white/grey backgrounds where chroma-only keys would fail.
    dist = np.sqrt(np.sum((img - key) ** 2, axis=2)) / np.sqrt(3.0)

    lo = s.tolerance
    hi = s.tolerance + max(s.softness, 1e-4)
    alpha = np.clip((dist - lo) / (hi - lo), 0.0, 1.0)

    if s.connected and cv2 is not None:
        alpha = _restrict_to_border_region(alpha, s.close_px, s.seeds)

    if s.feather_px > 0 and cv2 is not None:
        k = s.feather_px * 2 + 1
        alpha = cv2.GaussianBlur(alpha, (k, k), 0)

    return (alpha * 255).astype(np.uint8)


def _restrict_to_border_region(alpha, close_px=0, seeds=()):
    """Keep transparency only on the background blob connected to the image borders
    (plus any explicit seed points); enclosed background-coloured pixels become
    opaque. ``close_px`` removes thin background bridges so a small gap in the
    subject outline doesn't let the background leak inside."""
    bg = (alpha < 1.0).astype(np.uint8)  # pixels that are at all background-ish
    if not bg.any():
        return alpha
    mask = bg
    if close_px > 0:
        k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE,
                                      (close_px * 2 + 1, close_px * 2 + 1))
        mask = cv2.morphologyEx(bg, cv2.MORPH_OPEN, k)  # break thin bg bridges
    num, labels = cv2.connectedComponents(mask, connectivity=8)
    border = np.concatenate([labels[0, :], labels[-1, :], labels[:, 0], labels[:, -1]])
    keep = set(np.unique(border).tolist()) - {0}
    h, w = alpha.shape
    for fx, fy in seeds:
        sx = int(min(max(fx, 0.0), 0.999) * w)
        sy = int(min(max(fy, 0.0), 0.999) * h)
        lbl = int(labels[sy, sx])
        if lbl != 0:
            keep.add(lbl)
    if not keep:
        return alpha
    connected_bg = np.isin(labels, list(keep))
    # bg-coloured pixels not connected to a border/seed are restored to opaque
    return np.where(bg.astype(bool) & ~connected_bg, 1.0, alpha)


def apply(rgb: np.ndarray, s: ChromaSettings) -> np.ndarray:
    """Return an HxWx4 RGBA image with the chroma key applied."""
    alpha = compute_alpha(rgb, s)
    out = np.dstack([rgb, alpha]).astype(np.uint8)

    if s.spill > 0:
        # Despill: where pixels lean toward the key colour, pull them toward grey.
        img = out[:, :, :3].astype(np.float32)
        key = np.array(s.color, dtype=np.float32)
        key_dir = key / (np.linalg.norm(key) + 1e-6)
        proj = np.tensordot(img, key_dir, axes=([2], [0]))[..., None] * key_dir
        gray = img.mean(axis=2, keepdims=True)
        edge = (alpha[..., None] > 0) & (alpha[..., None] < 255)
        fixed = np.where(edge, img - s.spill * (proj - gray), img)
        out[:, :, :3] = np.clip(fixed, 0, 255).astype(np.uint8)

    return out
