"""Tests for the UI-agnostic core (no ffmpeg/rembg needed — synthetic frames)."""
from __future__ import annotations

import json

import numpy as np
import pytest

from videotosprite.core.chroma import ChromaSettings, compute_alpha, sample_color
from videotosprite.core.export import ExportOptions, export
from videotosprite.core.frames import Frame, FrameStore
from videotosprite.core.render import BgMode, BgSettings, render
from videotosprite.core.spritesheet import SheetSettings, pack


def _solid(color, w=40, h=30):
    img = np.zeros((h, w, 3), np.uint8)
    img[:, :] = color
    return img


def _store(n=4, color=(10, 200, 10)):
    s = FrameStore()
    s.frames = [Frame(index=i, path=None, rgb=_solid(color)) for i in range(n)]
    return s


# ------------------------------------------------------------------ chroma
def test_sample_color_median_rejects_outlier():
    img = np.full((10, 10, 3), 250, np.uint8)
    img[5, 5] = (0, 0, 0)  # a stray dark pixel exactly under the click
    assert sample_color(img, 5, 5, radius=2) == (250, 250, 250)
    # still works clamped at a corner
    assert sample_color(img, 0, 0, radius=2) == (250, 250, 250)


def test_chroma_alpha_keys_background_color():
    rgb = _solid((0, 255, 0))
    a = compute_alpha(rgb, ChromaSettings(color=(0, 255, 0), tolerance=0.2, softness=0.1))
    assert a.max() == 0  # exact key colour is fully transparent


def test_chroma_alpha_keeps_distant_color():
    rgb = _solid((255, 0, 0))
    a = compute_alpha(rgb, ChromaSettings(color=(0, 255, 0), tolerance=0.2, softness=0.1))
    assert a.min() == 255  # far colour stays fully opaque


def test_chroma_magic_wand_preserves_interior():
    # White bg with a black ring enclosing a white interior (cow-on-white case).
    img = np.full((100, 100, 3), 255, np.uint8)
    img[30:70, 30:35] = 0
    img[30:70, 65:70] = 0
    img[30:35, 30:70] = 0
    img[65:70, 30:70] = 0
    s = ChromaSettings(color=(255, 255, 255), tolerance=0.1, softness=0.05)
    plain = compute_alpha(img, s)
    s.connected = True
    wand = compute_alpha(img, s)
    assert plain[50, 50] == 0      # plain chroma wrongly removes the interior white
    assert wand[50, 50] == 255     # magic wand keeps it
    assert wand[10, 10] == 0       # exterior background still removed
    assert wand[32, 50] == 255     # black outline kept


def test_chroma_wand_close_seals_gap():
    img = np.full((100, 100, 3), 255, np.uint8)
    img[30:70, 30:35] = 0
    img[30:70, 65:70] = 0
    img[65:70, 30:70] = 0
    img[30:35, 30:70] = 0
    img[30:35, 48:52] = 255  # 4px gap in the outline
    s = ChromaSettings(color=(255, 255, 255), tolerance=0.1, softness=0.05,
                       connected=True)
    assert compute_alpha(img, s)[50, 50] == 0       # leaks through the gap
    s.close_px = 3
    assert compute_alpha(img, s)[50, 50] == 255      # gap sealed -> interior kept


def test_chroma_wand_seed_removes_enclosed_region():
    img = np.full((100, 100, 3), 255, np.uint8)
    img[30:70, 30:35] = 0
    img[30:70, 65:70] = 0
    img[65:70, 30:70] = 0
    img[30:35, 30:70] = 0
    s = ChromaSettings(color=(255, 255, 255), tolerance=0.1, softness=0.05,
                       connected=True)
    assert compute_alpha(img, s)[50, 50] == 255      # enclosed bg kept by default
    s.seeds = [(0.5, 0.5)]
    assert compute_alpha(img, s)[50, 50] == 0        # seeded -> removed


def test_chroma_partial_subject():
    rgb = _solid((0, 255, 0))
    rgb[:, 20:] = (255, 0, 0)  # right half is the subject
    a = compute_alpha(rgb, ChromaSettings(color=(0, 255, 0), tolerance=0.2, softness=0.1))
    assert a[:, :20].max() == 0 and a[:, 20:].min() == 255


# ------------------------------------------------------------------ render
def test_apply_matte_cut_level():
    from videotosprite.core.bg_ai import apply_matte
    rgb = _solid((10, 20, 30))
    matte = np.zeros((30, 40), np.uint8)
    matte[:, 20:] = 255          # right half foreground, left half background
    out = apply_matte(rgb, matte, cut=0.0)
    assert out.shape[2] == 4
    assert out[:, :20, 3].max() == 0 and out[:, 20:, 3].min() == 255
    # raising the cut keeps only the strongest matte values
    mid = np.full((30, 40), 120, np.uint8)
    low = apply_matte(rgb, mid, cut=0.0)[:, :, 3].max()
    high = apply_matte(rgb, mid, cut=0.6)[:, :, 3].max()
    assert high < low


def test_render_none_is_opaque():
    fr = Frame(0, None, _solid((1, 2, 3)))
    out = render(fr, BgSettings(mode=BgMode.NONE))
    assert out.shape[2] == 4 and out[:, :, 3].min() == 255


def test_render_crop_dimensions():
    fr = Frame(0, None, _solid((1, 2, 3), w=100, h=100))
    out = render(fr, BgSettings(crop=(0.25, 0.25, 0.5, 0.5)))
    assert out.shape[0] == 50 and out.shape[1] == 50


def test_render_max_dim_downscales():
    fr = Frame(0, None, _solid((1, 2, 3), w=800, h=400))
    out = render(fr, BgSettings(), max_dim=200)
    assert max(out.shape[:2]) == 200


# --------------------------------------------------------------- spritesheet
def test_pack_atlas_count_and_rects():
    frames = [np.dstack([_solid((i, i, i)), np.full((30, 40), 255, np.uint8)])
              for i in range(6)]
    sheet, atlas = pack(frames, SheetSettings(columns=3, padding=2))
    assert atlas["count"] == 6 and atlas["columns"] == 3 and atlas["rows"] == 2
    assert len(atlas["frames"]) == 6
    assert all(f["w"] == 40 and f["h"] == 30 for f in atlas["frames"])
    assert sheet.size == (atlas["size"]["w"], atlas["size"]["h"])


def test_pack_trim_records_offset_and_source():
    f = np.zeros((30, 40, 4), np.uint8)
    f[10:18, 15:25] = (120, 30, 30, 255)  # opaque 10x8 block inside a 40x30 frame
    sheet, atlas = pack([f, f.copy()], SheetSettings(columns=2, trim=True))
    assert atlas["cell"] == {"w": 10, "h": 8}
    fr = atlas["frames"][0]
    assert fr["w"] == 10 and fr["h"] == 8 and fr["trimmed"] is True
    assert fr["offset"] == {"x": 15, "y": 10}
    assert fr["source_size"] == {"w": 40, "h": 30}


def test_pack_power_of_two():
    frames = [np.dstack([_solid((0, 0, 0)), np.full((30, 40), 255, np.uint8)])]
    sheet, atlas = pack(frames, SheetSettings(power_of_two=True))
    w, h = sheet.size
    assert (w & (w - 1)) == 0 and (h & (h - 1)) == 0


# --------------------------------------------------------------- frame store
def test_included_falls_back_to_all_when_none_selected():
    s = _store(3)
    for f in s.frames:
        f.included = False
    assert len(s.included()) == 3  # safety fallback


def test_included_subset():
    s = _store(4)
    s.frames[1].included = False
    s.frames[3].included = False
    assert len(s.included()) == 2


# ------------------------------------------------------------------ export
def test_export_only_included(tmp_path):
    s = _store(4)
    s.frames[0].included = False
    written = export(s, BgSettings(), ExportOptions(
        out_dir=tmp_path, fps=10, export_pngs=True, export_sheet=True, export_gif=True,
        sheet=SheetSettings(columns=2)))
    assert "sheet" in written and "gif" in written
    pngs = list((tmp_path / "frames").glob("*.png"))
    assert len(pngs) == 3  # the excluded frame is gone
    atlas = json.loads((tmp_path / "sheet.json").read_text())
    assert atlas["count"] == 3 and atlas["fps"] == 10


def test_export_webp_apng_keep_alpha(tmp_path):
    from PIL import Image

    # white bg with a red half -> chroma-key white -> real transparency
    img = _solid((255, 255, 255))
    img[:, 20:] = (255, 0, 0)
    s = FrameStore()
    s.frames = [Frame(i, None, img.copy()) for i in range(3)]
    bg = BgSettings(mode=BgMode.CHROMA, chroma=ChromaSettings(
        color=(255, 255, 255), tolerance=0.2, softness=0.1))
    written = export(s, bg, ExportOptions(
        out_dir=tmp_path, fps=8, export_pngs=False, export_sheet=False,
        export_gif=False, export_webp=True, export_apng=True))
    assert "webp" in written and "apng" in written
    webp = Image.open(written["webp"])
    apng = Image.open(written["apng"])
    assert webp.format == "WEBP" and webp.mode == "RGBA"   # 8-bit alpha (soft edges)
    assert apng.format == "PNG" and getattr(apng, "n_frames", 1) == 3
    # the keyed (white) half is transparent
    assert np.asarray(apng.convert("RGBA"))[:, :10, 3].max() == 0


def test_export_cancel_writes_nothing(tmp_path):
    s = _store(4)
    written = export(s, BgSettings(), ExportOptions(out_dir=tmp_path),
                     should_cancel=lambda: True)
    assert written == {}


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
