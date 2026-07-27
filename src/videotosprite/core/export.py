"""Write the final artefacts: PNG frames, sprite sheet (+ atlas) and GIF."""
from __future__ import annotations

import json
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import numpy as np
from PIL import Image

from .frames import FrameStore
from .render import BgSettings, render
from .spritesheet import SheetSettings, pack


@dataclass
class ExportOptions:
    out_dir: Path
    fps: float = 12.0
    export_pngs: bool = True
    zip_pngs: bool = False
    export_sheet: bool = True
    export_gif: bool = True
    export_webp: bool = False   # animated WebP — 8-bit alpha (smooth edges)
    export_apng: bool = False   # animated PNG — lossless 8-bit alpha
    sheet: SheetSettings = None  # type: ignore[assignment]

    def __post_init__(self):
        self.out_dir = Path(self.out_dir)
        if self.sheet is None:
            self.sheet = SheetSettings()


def _render_all(
    store: FrameStore,
    bg: BgSettings,
    progress: Optional[Callable[[int, int], None]],
    should_cancel: Optional[Callable[[], bool]],
) -> list[np.ndarray]:
    out = []
    frames = store.included()
    total = len(frames)
    for i, fr in enumerate(frames):
        if should_cancel and should_cancel():
            break
        out.append(render(fr, bg, allow_ai_compute=True))
        if progress:
            progress(i + 1, total)
    return out


def export(
    store: FrameStore,
    bg: BgSettings,
    opts: ExportOptions,
    progress: Optional[Callable[[int, int], None]] = None,
    status: Optional[Callable[[str], None]] = None,
    should_cancel: Optional[Callable[[], bool]] = None,
) -> dict:
    """Run the whole export. Returns a dict of written paths."""
    opts.out_dir.mkdir(parents=True, exist_ok=True)
    written: dict[str, str] = {}

    if status:
        status("Aplicando remoção de fundo...")
    rgba = _render_all(store, bg, progress, should_cancel)
    if should_cancel and should_cancel():
        return written

    images = [Image.fromarray(a, "RGBA") for a in rgba]

    if opts.export_pngs:
        if status:
            status("Salvando PNGs...")
        frames_dir = opts.out_dir / "frames"
        frames_dir.mkdir(exist_ok=True)
        paths = []
        for i, img in enumerate(images, 1):
            p = frames_dir / f"frame_{i:05d}.png"
            img.save(p)
            paths.append(p)
        written["frames_dir"] = str(frames_dir)

        if opts.zip_pngs:
            zip_path = opts.out_dir / "frames.zip"
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for p in paths:
                    zf.write(p, p.name)
            written["frames_zip"] = str(zip_path)

    if opts.export_sheet:
        if status:
            status("Montando sprite sheet...")
        sheet_img, atlas = pack(rgba, opts.sheet)
        sheet_path = opts.out_dir / "sheet.png"
        atlas_path = opts.out_dir / "sheet.json"
        sheet_img.save(sheet_path)
        atlas["fps"] = opts.fps
        atlas_path.write_text(json.dumps(atlas, indent=2))
        written["sheet"] = str(sheet_path)
        written["atlas"] = str(atlas_path)

    if images and (opts.export_gif or opts.export_webp or opts.export_apng):
        duration_ms = int(1000 / max(opts.fps, 1))
        frames = [im.convert("RGBA") for im in images]

        if opts.export_gif:
            if status:
                status("Gerando GIF...")
            # GIF only supports 1-bit alpha (hard edge); webp/apng keep soft edges.
            p = opts.out_dir / "preview.gif"
            frames[0].save(p, save_all=True, append_images=frames[1:],
                           duration=duration_ms, loop=0, disposal=2, transparency=0)
            written["gif"] = str(p)

        if opts.export_webp:
            if status:
                status("Gerando WebP...")
            p = opts.out_dir / "preview.webp"
            frames[0].save(p, format="WEBP", save_all=True, append_images=frames[1:],
                           duration=duration_ms, loop=0, lossless=True)
            written["webp"] = str(p)

        if opts.export_apng:
            if status:
                status("Gerando APNG...")
            p = opts.out_dir / "preview.apng"
            frames[0].save(p, format="PNG", save_all=True, append_images=frames[1:],
                           duration=duration_ms, loop=0, disposal=1)
            written["apng"] = str(p)

    if status:
        status("Concluído.")
    return written
