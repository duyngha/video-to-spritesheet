"""Pack a list of frames into a single grid sprite sheet plus a JSON atlas.

With ``trim`` on, each frame's transparent border is cropped away (saving space)
and the atlas records the original size and the offset of the trimmed sprite —
TexturePacker-style — so an engine can place it back correctly."""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from PIL import Image


@dataclass
class SheetSettings:
    columns: int = 0          # 0 = auto (near-square)
    padding: int = 0          # transparent gap between cells
    power_of_two: bool = False  # round the sheet size up to a power of two
    trim: bool = False        # crop each frame's transparent border (tight packing)


def _next_pow2(n: int) -> int:
    return 1 if n <= 1 else 2 ** math.ceil(math.log2(n))


def _rgba(fr: np.ndarray) -> np.ndarray:
    if fr.shape[2] == 4:
        return fr
    return np.dstack([fr, np.full(fr.shape[:2], 255, np.uint8)])


def _trim(fr: np.ndarray):
    """Return (cropped_rgba, source_w, source_h, offset_x, offset_y, trimmed)."""
    oh, ow = fr.shape[:2]
    ys, xs = np.where(fr[:, :, 3] > 0)
    if len(xs) == 0:  # fully transparent — keep a 1x1 to stay valid
        return fr[:1, :1], ow, oh, 0, 0, True
    x0, x1 = int(xs.min()), int(xs.max()) + 1
    y0, y1 = int(ys.min()), int(ys.max()) + 1
    if x0 == 0 and y0 == 0 and x1 == ow and y1 == oh:
        return fr, ow, oh, 0, 0, False
    return fr[y0:y1, x0:x1], ow, oh, x0, y0, True


def pack(frames: list[np.ndarray], s: SheetSettings) -> tuple[Image.Image, dict]:
    """Return (sheet_image RGBA, atlas_dict)."""
    if not frames:
        raise ValueError("Sem frames para empacotar.")

    # cells: (rgba, source_w, source_h, offset_x, offset_y, trimmed)
    cells = []
    for fr in frames:
        rgba = _rgba(fr)
        if s.trim:
            cells.append(_trim(rgba))
        else:
            h, w = rgba.shape[:2]
            cells.append((rgba, w, h, 0, 0, False))

    cell_w = max(c[0].shape[1] for c in cells)
    cell_h = max(c[0].shape[0] for c in cells)
    n = len(cells)
    cols = s.columns if s.columns > 0 else max(1, round(math.sqrt(n)))
    cols = min(cols, n)
    rows = math.ceil(n / cols)

    pad = s.padding
    sheet_w = cols * cell_w + (cols + 1) * pad
    sheet_h = rows * cell_h + (rows + 1) * pad
    if s.power_of_two:
        sheet_w = _next_pow2(sheet_w)
        sheet_h = _next_pow2(sheet_h)

    sheet = Image.new("RGBA", (sheet_w, sheet_h), (0, 0, 0, 0))
    atlas_frames = []
    for i, (rgba, ow, oh, ox, oy, trimmed) in enumerate(cells):
        r, c = divmod(i, cols)
        th, tw = rgba.shape[:2]
        x = pad + c * (cell_w + pad)
        y = pad + r * (cell_h + pad)
        sheet.paste(Image.fromarray(rgba, "RGBA"), (x, y))
        atlas_frames.append({
            "index": i, "x": x, "y": y, "w": int(tw), "h": int(th),
            "source_size": {"w": int(ow), "h": int(oh)},
            "offset": {"x": int(ox), "y": int(oy)},
            "trimmed": trimmed,
        })

    atlas = {
        "image": "sheet.png",
        "size": {"w": sheet_w, "h": sheet_h},
        "cell": {"w": cell_w, "h": cell_h},
        "columns": cols,
        "rows": rows,
        "padding": pad,
        "trimmed": s.trim,
        "count": n,
        "frames": atlas_frames,
    }
    return sheet, atlas
