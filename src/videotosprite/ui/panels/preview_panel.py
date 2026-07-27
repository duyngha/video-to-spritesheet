"""Central preview: the rendered frame, crop rectangle, eyedropper, animated
playback, and the thumbnail strip with per-frame include/exclude selection."""
from __future__ import annotations

import asyncio
import io

import flet as ft
import numpy as np
from PIL import Image

from ...core.render import BgMode, render
from ..i18n import t
from ..imageutils import preview_png, to_png_bytes
from ..widgets import (
    ACCENT,
    CROP_COLOR,
    PREVIEW_MAX_H,
    PREVIEW_MAX_W,
    PREVIEW_RENDER_MAX,
    to_float,
)


class PreviewPanel:
    def __init__(self, app):
        self.app = app
        self.crop_mode = False
        self.playing = False
        self._view_w = 0
        self._view_h = 0
        self._img_w = 0
        self._img_h = 0
        self._crop_start = None
        self._pick_src = None
        self.thumbs: list[dict] = []
        self._build()

    # ---------------------------------------------------------------- build
    def _build(self):
        # Image fills the GestureDetector (CONTAIN, so it letterboxes). We measure
        # the GestureDetector itself and map gestures against the letterboxed image
        # rect, so crop/eyedropper stay exact regardless of layout/DPI.
        self.preview_img = ft.Image(src=b"", fit=ft.BoxFit.CONTAIN,
                                    gapless_playback=True, expand=True)
        img_fill = ft.Container(content=self.preview_img, left=0, top=0,
                                right=0, bottom=0, alignment=ft.Alignment.CENTER)
        self.crop_rect = ft.Container(
            visible=False, border=ft.Border.all(2, CROP_COLOR),
            bgcolor=ft.Colors.with_opacity(0.12, CROP_COLOR), border_radius=2)
        self.preview_stack = ft.Stack([img_fill, self.crop_rect], expand=True)
        self.preview_gd = ft.GestureDetector(
            content=self.preview_stack, expand=True,
            on_tap_down=self.on_preview_tap, on_pan_start=self.on_crop_start,
            on_pan_update=self.on_crop_update, on_pan_end=self.on_crop_end,
            on_size_change=self.on_view_size)
        self.holder = ft.Container(content=self.preview_gd, bgcolor="#161619",
                                   border_radius=8, expand=True, padding=6)

        self.play_btn = ft.Button("Reproduzir", icon=ft.Icons.PLAY_ARROW,
                                  on_click=self.toggle_play, disabled=True)
        self.play_fps_field = ft.TextField(value="12", width=86, label="veloc (fps)",
                                            tooltip="Velocidade da reprodução")
        toolbar = ft.Row([self.play_btn, self.play_fps_field],
                         alignment=ft.MainAxisAlignment.CENTER,
                         vertical_alignment=ft.CrossAxisAlignment.CENTER)

        self.caption = ft.Text("Abra um vídeo para começar", size=12, color="#999",
                               text_align=ft.TextAlign.CENTER)
        self.sel_count = ft.Text("", size=11, color="#8fc")
        sel_row = ft.Row([
            ft.Text("Frames", size=11, color="#999"),
            ft.TextButton("todos", on_click=lambda e: self.select_all(True)),
            ft.TextButton("nenhum", on_click=lambda e: self.select_all(False)),
            ft.TextButton("inverter", on_click=self.invert_selection),
            self.sel_count,
        ], spacing=4)
        self.frames_row = ft.Row([], scroll=ft.ScrollMode.AUTO, height=104, spacing=4)

        self.view = ft.Column([
            toolbar, self.holder, self.caption, sel_row, self.frames_row,
        ], expand=True, spacing=6,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER)

        self.show_placeholder()

    # -------------------------------------------------------------- display
    def show_placeholder(self):
        self.preview_img.src = to_png_bytes(
            np.full((PREVIEW_MAX_H, PREVIEW_MAX_W, 3), 22, np.uint8))

    def set_caption(self, text: str):
        self.caption.value = text

    def refresh(self):
        fr = self.app.store.get(self.app.current)
        if fr is None:
            return
        rgba = render(fr, self.app.bg, allow_ai_compute=False,
                      max_dim=PREVIEW_RENDER_MAX, apply_crop=not self.crop_mode)
        self.show(rgba)
        self._highlight_current()
        note = ""
        if self.app.bg.mode == BgMode.AI and fr.ai_matte is None:
            note = "  · " + t("clique em 'Pré-computar IA'")
        if self.crop_mode:
            note = "  · " + t("arraste para recortar")
        self.caption.value = f"{t('Frame')} {fr.index + 1} / {len(self.app.store)}{note}"

    def show(self, rgba: np.ndarray):
        h, w = rgba.shape[:2]
        self._img_w, self._img_h = w, h
        self._pick_src = rgba[:, :, :3]
        self.preview_img.src = preview_png(rgba)
        self._sync_crop_rect()

    def show_source(self, rgb: np.ndarray):
        self.show(np.dstack([rgb, np.full(rgb.shape[:2], 255, np.uint8)]))

    # ------------------------------------------------------------ geometry
    def on_view_size(self, e):
        self._view_w, self._view_h = e.width, e.height

    def _img_rect(self):
        bw = self._view_w or PREVIEW_MAX_W
        bh = self._view_h or PREVIEW_MAX_H
        iw = self._img_w or 1
        ih = self._img_h or 1
        scale = min(bw / iw, bh / ih)
        rw, rh = iw * scale, ih * scale
        return (bw - rw) / 2, (bh - rh) / 2, rw, rh

    @staticmethod
    def _clamp(x, lo, hi):
        return max(lo, min(float(x), hi))

    # ---------------------------------------------------------------- crop
    def _sync_crop_rect(self):
        if self.crop_mode and self.app.bg.crop is not None:
            rx, ry, rw, rh = self._img_rect()
            fx, fy, fw, fh = self.app.bg.crop
            self.crop_rect.left = rx + fx * rw
            self.crop_rect.top = ry + fy * rh
            self.crop_rect.width = max(fw * rw, 1)
            self.crop_rect.height = max(fh * rh, 1)
            self.crop_rect.visible = True
        elif not self.crop_mode:
            self.crop_rect.visible = False

    def on_crop_start(self, e):
        if not self.crop_mode:
            return
        rx, ry, rw, rh = self._img_rect()
        x = self._clamp(e.local_position.x, rx, rx + rw)
        y = self._clamp(e.local_position.y, ry, ry + rh)
        self._crop_start = (x, y)
        self.crop_rect.left, self.crop_rect.top = x, y
        self.crop_rect.width, self.crop_rect.height = 1, 1
        self.crop_rect.visible = True
        self.crop_rect.update()

    def on_crop_update(self, e):
        if not self.crop_mode or self._crop_start is None:
            return
        rx, ry, rw, rh = self._img_rect()
        x0, y0 = self._crop_start
        x = self._clamp(e.local_position.x, rx, rx + rw)
        y = self._clamp(e.local_position.y, ry, ry + rh)
        self.crop_rect.left, self.crop_rect.top = min(x0, x), min(y0, y)
        self.crop_rect.width = max(abs(x - x0), 1)
        self.crop_rect.height = max(abs(y - y0), 1)
        self.crop_rect.update()
        self.app.crop_panel.show_norm(self._rect_norm())  # live coords readout

    def on_crop_end(self, e):
        if not self.crop_mode or self._crop_start is None:
            return
        self._crop_start = None
        if self.crop_rect.width < 4 or self.crop_rect.height < 4:
            return
        self.app.bg.crop = self._rect_norm()
        self.app.crop_panel.show_norm(self.app.bg.crop)
        self.caption.value = t("Recorte definido · Enter p/ aplicar, Esc p/ cancelar")
        self.app.page.update()

    def _rect_norm(self):
        """Current crop_rect as normalised (fx, fy, fw, fh)."""
        rx, ry, rw, rh = self._img_rect()
        return ((self.crop_rect.left - rx) / rw, (self.crop_rect.top - ry) / rh,
                self.crop_rect.width / rw, self.crop_rect.height / rh)

    def sync_crop_overlay(self):
        """Redraw the overlay from app.bg.crop (used when the crop panel edits it)."""
        self._sync_crop_rect()
        self.crop_rect.update()

    def toggle_crop(self, e=None):
        self._stop_play()
        self.crop_mode = not self.crop_mode
        if self.crop_mode:
            self.app.set_eyedropper(False)
            self.app.set_seed_mode(False)
        self.app.crop_panel.set_active(self.crop_mode)
        self.app.crop_panel.show_norm(self.app.bg.crop)
        self.refresh()
        self.app.page.update()

    def clear_crop(self, e=None):
        self.app.bg.crop = None
        self.crop_rect.visible = False
        self.app.crop_panel.show_norm(None)
        self.refresh()
        self.app.page.update()

    def on_key(self, e):
        """Crop mode: Enter applies, Esc cancels. Otherwise: Space toggles play,
        arrows step through frames."""
        if self.crop_mode:
            if e.key == "Enter":
                self.toggle_crop()
            elif e.key == "Escape":
                self.app.bg.crop = None
                self.toggle_crop()
            return
        if not len(self.app.store) or self.app.busy:
            return
        if e.key in (" ", "Space"):
            self.toggle_play()
        elif e.key in ("Arrow Right", "Arrow Down", "Right", "Down"):
            self._step(1)
        elif e.key in ("Arrow Left", "Arrow Up", "Left", "Up"):
            self._step(-1)

    def _step(self, d):
        n = len(self.app.store)
        if not n:
            return
        self.app.current = (self.app.current + d) % n
        self.refresh()
        self.app.page.update()

    # ------------------------------------------------------------ playback
    def toggle_play(self, e=None):
        if self.playing:
            self._stop_play()
            self.app.page.update()
        elif len(self.app.store):
            if self.crop_mode:
                self.toggle_crop()
            self.playing = True
            self.play_btn.content = "Pausar"
            self.play_btn.icon = ft.Icons.PAUSE
            self.app.page.update()
            # run_task drives the animation on the event loop (stays responsive and
            # surfaces errors; run_thread would swallow them).
            self.app.page.run_task(self._play_loop)

    def _stop_play(self):
        self.playing = False
        self.play_btn.content = "Reproduzir"
        self.play_btn.icon = ft.Icons.PLAY_ARROW

    async def _play_loop(self):
        i = 0
        while self.playing:
            frames = self.app.store.included()
            if not frames:
                break
            self.app.current = frames[i % len(frames)].index
            self.refresh()
            self.app.page.update()
            i += 1
            await asyncio.sleep(1.0 / max(to_float(self.play_fps_field.value, 12), 0.5))
        self._stop_play()
        self.app.page.update()

    # ----------------------------------------------------------- eyedropper
    def on_preview_tap(self, e):
        if self._pick_src is None:
            return
        rx, ry, rw, rh = self._img_rect()
        if rw <= 0 or rh <= 0:
            return
        fx = self._clamp((e.local_position.x - rx) / rw, 0, 0.999)
        fy = self._clamp((e.local_position.y - ry) / rh, 0, 0.999)
        if self.app.eyedropper:
            from ...core.chroma import sample_color
            h, w = self._pick_src.shape[:2]
            color = sample_color(self._pick_src, int(fx * w), int(fy * h))
            self.app.pick_color(color)
        elif self.app.seed_mode:
            self.app.add_seed(fx, fy)

    # -------------------------------------------------------- thumbnails
    def populate(self, store):
        ctrls, self.thumbs = [], []
        for fr in store.frames:
            img = ft.Image(src=self._thumb_bytes(fr.rgb), width=96, height=64,
                           fit=ft.BoxFit.CONTAIN, border_radius=4, opacity=1.0)
            border = ft.Container(width=96, height=64, border_radius=4,
                                  border=ft.Border.all(2, "#00000000"))
            chk = ft.Checkbox(value=True, scale=0.8,
                              on_change=lambda e, i=fr.index: self.toggle_include(i))
            cell = ft.Column([
                ft.GestureDetector(content=ft.Stack([img, border], width=96, height=64),
                                   on_tap=lambda e, i=fr.index: self.select_frame(i)),
                ft.Row([chk, ft.Text(str(fr.index + 1), size=10, color="#999")],
                       spacing=0, tight=True),
            ], spacing=0, tight=True,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER)
            self.thumbs.append({"img": img, "border": border, "chk": chk})
            ctrls.append(cell)
        self.frames_row.controls = ctrls
        self._update_sel_count()

    @staticmethod
    def _thumb_bytes(rgb):
        im = Image.fromarray(rgb).convert("RGB")
        im.thumbnail((96, 96))
        buf = io.BytesIO()
        im.save(buf, "PNG")
        return buf.getvalue()

    def included_count(self):
        return sum(1 for f in self.app.store.frames if f.included)

    def toggle_include(self, index):
        fr = self.app.store.get(index)
        if fr is None:
            return
        fr.included = self.thumbs[index]["chk"].value
        self.thumbs[index]["img"].opacity = 1.0 if fr.included else 0.3
        self._update_sel_count()
        self.app.on_selection_changed()
        self.app.page.update()

    def select_all(self, value):
        for i, fr in enumerate(self.app.store.frames):
            fr.included = value
            self.thumbs[i]["chk"].value = value
            self.thumbs[i]["img"].opacity = 1.0 if value else 0.3
        self._update_sel_count()
        self.app.on_selection_changed()
        self.app.page.update()

    def invert_selection(self, e=None):
        for i, fr in enumerate(self.app.store.frames):
            fr.included = not fr.included
            self.thumbs[i]["chk"].value = fr.included
            self.thumbs[i]["img"].opacity = 1.0 if fr.included else 0.3
        self._update_sel_count()
        self.app.on_selection_changed()
        self.app.page.update()

    def _update_sel_count(self):
        self.sel_count.value = (f"{self.included_count()}/{len(self.app.store)} "
                                f"{t('incluídos')}")

    def select_frame(self, index):
        self.app.current = index
        self.refresh()
        self.app.page.update()

    def _highlight_current(self):
        for i, t in enumerate(self.thumbs):
            t["border"].border = ft.Border.all(
                2, ACCENT if i == self.app.current else "#00000000")

    # -------------------------------------------------------------- state
    def set_enabled(self, on: bool):
        self.play_btn.disabled = not on
        self.app.crop_panel.set_enabled(on)

    def set_busy(self, busy: bool):
        if busy:
            self._stop_play()
        self.play_btn.disabled = busy or len(self.app.store) == 0
        self.app.crop_panel.set_busy(busy)

    def reset(self):
        self.thumbs = []
        self.frames_row.controls = []
        self.app.bg.crop = None
        self.crop_rect.visible = False
        self.crop_mode = False
        self.set_enabled(False)
        self.app.crop_panel.show_norm(None)
