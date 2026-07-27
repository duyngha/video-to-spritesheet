"""In-memory store of the extracted frames plus a cache for AI mattes."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image


@dataclass
class Frame:
    index: int
    path: Path | None          # source PNG on disk (None if synthetic)
    rgb: np.ndarray            # HxWx3 uint8
    ai_matte: np.ndarray | None = None  # HxW uint8 alpha from rembg (cached)
    included: bool = True       # whether this frame is part of the export/playback


@dataclass
class FrameStore:
    frames: list[Frame] = field(default_factory=list)

    def clear(self) -> None:
        self.frames.clear()

    def __len__(self) -> int:
        return len(self.frames)

    @property
    def size(self) -> tuple[int, int]:
        """(width, height) of the frames, or (0, 0) when empty."""
        if not self.frames:
            return (0, 0)
        h, w = self.frames[0].rgb.shape[:2]
        return (w, h)

    def load_from_paths(self, paths: list[Path]) -> None:
        self.clear()
        for i, p in enumerate(paths):
            img = Image.open(p).convert("RGB")
            self.frames.append(Frame(index=i, path=Path(p), rgb=np.asarray(img)))

    def get(self, index: int) -> Frame | None:
        if 0 <= index < len(self.frames):
            return self.frames[index]
        return None

    def included(self) -> list[Frame]:
        """Frames flagged for export/playback (falls back to all if none)."""
        sel = [f for f in self.frames if f.included]
        return sel or self.frames

    def clear_mattes(self) -> None:
        for f in self.frames:
            f.ai_matte = None
