"""UI-logic tests driven headlessly through a mock Page (see conftest.py).

The UI is split into panels; the controller (``app``) holds shared state (store,
bg, info, current) and exposes the panels as ``app.video``, ``app.preview``,
``app.bg_panel`` and ``app.export``.
"""
from __future__ import annotations

import types

import numpy as np


def _ev(x, y):
    return types.SimpleNamespace(local_position=types.SimpleNamespace(x=x, y=y))


# ----------------------------------------------------------------- crop mapping
def test_crop_maps_exactly_with_letterbox(loaded_app):
    app = loaded_app
    pv = app.preview
    pv.crop_mode = True
    pv.refresh()
    # gesture box wider AND taller than 16:9 -> image is letterboxed inside it
    pv.on_view_size(types.SimpleNamespace(width=600.0, height=500.0))
    rx, ry, rw, rh = pv._img_rect()
    pv.on_crop_start(_ev(rx + 0.2 * rw, ry + 0.2 * rh))
    pv.on_crop_update(_ev(rx + 0.6 * rw, ry + 0.7 * rh))
    pv.on_crop_end(_ev(rx + 0.6 * rw, ry + 0.7 * rh))
    fx, fy, fw, fh = app.bg.crop
    assert abs(fx - 0.2) < 0.01
    assert abs(fy - 0.2) < 0.01
    assert abs(fw - 0.4) < 0.01
    assert abs(fh - 0.5) < 0.01


def test_crop_enter_applies_escape_cancels(loaded_app):
    app = loaded_app
    pv = app.preview
    pv.crop_mode = True
    pv.refresh()
    pv.on_view_size(types.SimpleNamespace(width=320.0, height=180.0))
    pv.on_crop_start(_ev(40, 30))
    pv.on_crop_update(_ev(200, 150))
    pv.on_crop_end(_ev(200, 150))
    assert app.bg.crop is not None
    pv.on_key(types.SimpleNamespace(key="Enter"))
    assert pv.crop_mode is False              # applied (left crop mode)
    assert app.bg.crop is not None

    pv.crop_mode = True
    pv.on_key(types.SimpleNamespace(key="Escape"))
    assert pv.crop_mode is False and app.bg.crop is None  # cancelled


# ------------------------------------------------------------------- crop panel
def test_crop_panel_shows_coords_on_drag(loaded_app):
    app = loaded_app  # frames are 160x90
    pv = app.preview
    pv.toggle_crop()
    pv.on_view_size(types.SimpleNamespace(width=160.0, height=90.0))
    pv.on_crop_start(_ev(32, 18))
    pv.on_crop_update(_ev(96, 63))
    pv.on_crop_end(_ev(96, 63))
    cp = app.crop_panel
    assert cp.x.value == "32" and cp.y.value == "18"
    assert cp.w.value == "64" and cp.h.value == "45"
    assert "64 × 45" in cp.size_lbl.value


def test_crop_panel_edit_fields_updates_crop(loaded_app):
    app = loaded_app
    cp = app.crop_panel
    cp.x.value, cp.y.value, cp.w.value, cp.h.value = "40", "20", "80", "40"
    cp.on_field(types.SimpleNamespace())
    fx, fy, fw, fh = app.bg.crop
    assert abs(fx - 40 / 160) < 1e-6 and abs(fy - 20 / 90) < 1e-6
    assert abs(fw - 80 / 160) < 1e-6 and abs(fh - 40 / 90) < 1e-6


# ------------------------------------------------------------------- selection
def test_frame_selection_include_exclude(loaded_app):
    app = loaded_app
    assert app.included_count() == 4
    app.preview.thumbs[1]["chk"].value = False
    app.preview.toggle_include(1)
    assert app.included_count() == 3
    assert app.preview.thumbs[1]["img"].opacity < 1.0
    app.preview.select_all(False)
    assert app.included_count() == 0
    app.preview.invert_selection(types.SimpleNamespace())
    assert app.included_count() == 4


# ------------------------------------------------------------------- eyedropper
def test_eyedropper_picks_color_under_cursor(loaded_app):
    app = loaded_app
    app.store.frames[0].rgb = np.full((90, 160, 3), (200, 10, 10), np.uint8)
    app.preview.refresh()
    app.preview.on_view_size(types.SimpleNamespace(width=160.0, height=90.0))
    app.set_eyedropper(True)
    app.preview.on_preview_tap(_ev(80, 45))
    assert app.bg.chroma.color == (200, 10, 10)
    assert app.eyedropper is False  # turns itself off after picking


def test_magic_wand_toggle(loaded_app):
    app = loaded_app
    app.bg_panel.wand_cb.value = True
    app.bg_panel.on_wand(types.SimpleNamespace())
    assert app.bg.chroma.connected is True


# --------------------------------------------------------------- export guard
def test_export_asks_before_overwriting_existing_dir(loaded_app, tmp_path):
    app = loaded_app
    app.export.outdir_field.value = str(tmp_path)  # exists
    app.export.start_export(types.SimpleNamespace())
    assert app.page.dialog is not None       # confirmation shown
    assert app.page.threads == []            # export not started yet


def test_export_runs_directly_when_dir_absent(loaded_app, tmp_path):
    app = loaded_app
    app.export.outdir_field.value = str(tmp_path / "does_not_exist")
    app.export.start_export(types.SimpleNamespace())
    assert app.page.dialog is None
    assert len(app.page.threads) == 1        # export kicked off


# --------------------------------------------------------------- startup check
def _hide_ffmpeg(monkeypatch, tmp_path):
    """Make the app believe no ffmpeg/ffprobe is installed anywhere."""
    import shutil

    import videotosprite.core.ffmpeg as ff

    real_which = shutil.which
    monkeypatch.setattr(
        ff.shutil, "which",
        lambda n: None if n in ("ffmpeg", "ffprobe") else real_which(n))
    monkeypatch.setattr(ff, "_EXTRA_DIRS", (str(tmp_path / "nowhere"),))
    monkeypatch.setattr(ff, "MANAGED_BIN_DIR", tmp_path / "managed")


def test_missing_ffmpeg_shows_banner(page, monkeypatch, tmp_path):
    from videotosprite.ui.app import VideoToSpriteApp

    _hide_ffmpeg(monkeypatch, tmp_path)
    app = VideoToSpriteApp(page)
    assert app.warning_bar.visible is True
    assert "ffmpeg" in app.ffmpeg_text.value
    assert app.ffmpeg_btn.disabled is False


def test_install_ffmpeg_button_runs_download(page, monkeypatch, tmp_path):
    """The banner's button downloads the binaries and then hides the banner."""
    import videotosprite.core.ffmpeg as ff
    from videotosprite.core import ffmpeg_setup
    from videotosprite.ui.app import VideoToSpriteApp

    _hide_ffmpeg(monkeypatch, tmp_path)
    app = VideoToSpriteApp(page)

    calls = {}

    def fake_install(progress=None, should_cancel=None):
        calls["progress"] = progress
        progress("ffmpeg", 0.5)
        # once installed, the binaries are visible to core.ffmpeg
        monkeypatch.setattr(ff, "find", lambda n: "/fake/" + n)
        return []

    monkeypatch.setattr(ffmpeg_setup, "install", fake_install)
    app.install_ffmpeg()
    assert app.ffmpeg_btn.disabled is True and app.ffmpeg_pb.visible is True
    fn, args = page.threads[-1]              # run the worker inline
    fn(*args)

    assert calls["progress"] is not None
    assert app.warning_bar.visible is False
    assert app.ffmpeg_pb.visible is False and app.ffmpeg_btn.disabled is False


def test_install_ffmpeg_failure_keeps_banner(page, monkeypatch, tmp_path):
    from videotosprite.core import ffmpeg_setup
    from videotosprite.ui.app import VideoToSpriteApp

    _hide_ffmpeg(monkeypatch, tmp_path)
    app = VideoToSpriteApp(page)

    def boom(progress=None, should_cancel=None):
        raise ffmpeg_setup.InstallError("sem internet")

    monkeypatch.setattr(ffmpeg_setup, "install", boom)
    app.install_ffmpeg()
    fn, args = page.threads[-1]
    fn(*args)

    assert app.warning_bar.visible is True
    assert "sem internet" in app.ffmpeg_text.value
    assert app.ffmpeg_btn.disabled is False   # retryable


# --------------------------------------------------------------- wand seed
def test_wand_seed_via_preview_click(loaded_app):
    app = loaded_app
    app.bg_panel.wand_cb.value = True
    app.bg_panel.on_wand(types.SimpleNamespace())
    app.bg_panel.toggle_seed(types.SimpleNamespace())
    assert app.seed_mode is True and app.eyedropper is False
    app.preview.on_view_size(types.SimpleNamespace(width=160.0, height=90.0))
    app.preview.refresh()
    app.preview.on_preview_tap(_ev(80, 45))
    assert len(app.bg.chroma.seeds) == 1
    app.bg_panel.clear_seeds(types.SimpleNamespace())
    assert app.bg.chroma.seeds == []


# --------------------------------------------------------------- shortcuts
def test_shortcuts_navigate_and_play(loaded_app):
    app = loaded_app
    app.current = 0
    app.preview.on_key(types.SimpleNamespace(key="Arrow Right"))
    assert app.current == 1
    app.preview.on_key(types.SimpleNamespace(key="Arrow Left"))
    assert app.current == 0
    app.preview.on_key(types.SimpleNamespace(key=" "))
    assert app.preview.playing is True
    app.preview.on_key(types.SimpleNamespace(key=" "))
    assert app.preview.playing is False


# --------------------------------------------------------------- persistence
def test_settings_persist_across_sessions(page, monkeypatch, tmp_path):
    from videotosprite.core import config
    monkeypatch.setattr(config, "CONFIG_PATH", tmp_path / "c.json")
    from videotosprite.ui.app import VideoToSpriteApp

    a = VideoToSpriteApp(page)
    a.export.cb_webp.value = False
    a.video.fps_field.value = "7"
    a.bg_panel.tol.set(0.42)
    a.save_settings()

    b = VideoToSpriteApp(type(page)())   # fresh "session"
    assert b.export.cb_webp.value is False
    assert b.video.fps_field.value == "7"
    assert abs(b.bg_panel.tol.value - 0.42) < 0.01


# --------------------------------------------------------------- i18n
def test_language_translation_and_data_preserved(page):
    from videotosprite.ui import i18n
    from videotosprite.ui.app import VideoToSpriteApp

    i18n.set_lang("en")
    app = VideoToSpriteApp(page)
    assert app.video.extract_btn.content == "Extract frames"
    assert app.crop_panel.crop_btn.content == "✂ Enable crop"
    # radio value is data, must survive translation
    assert app.bg_panel.mode_group.value in ("none", "chroma", "ai")

    app.lang_dd.value = "pt"
    app.on_language(types.SimpleNamespace())
    assert app.video.extract_btn.content == "Extrair frames"
    assert app.bg_panel.tol.text.value.startswith("Nível de corte")


# --------------------------------------------------------------- scrub readout
def test_scrub_label_shows_time(app):
    app.info = types.SimpleNamespace(duration=10.0, width=160, height=90, fps=24, path="x")
    app.video.on_scrub_change(types.SimpleNamespace(
        control=types.SimpleNamespace(value=3.45)))
    assert app.video.scrub_lbl.value == "Posição no vídeo: 00:03.45 / 00:10.00"
