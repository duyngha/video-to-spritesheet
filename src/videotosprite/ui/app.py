"""VideoToSprite — Flet app.

This is a thin controller: it owns the shared state (frame store, background
settings, current frame, busy/cancel flags) and wires the four panels together.
Each panel (``ui/panels/*``) builds and owns its own controls and handlers and
calls back into this controller for cross-panel effects (refresh the preview,
toggle busy state, pick a colour, …). Heavy work runs through ``page.run_thread``.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import flet as ft

from ..core import ffmpeg, ffmpeg_setup
from ..core.frames import FrameStore
from ..core.render import BgSettings
from . import i18n
from .i18n import t
from .panels.bg_panel import BgPanel
from .panels.crop_panel import CropPanel
from .panels.export_panel import ExportPanel
from .panels.preview_panel import PreviewPanel
from .panels.video_panel import VideoPanel


class VideoToSpriteApp:
    def __init__(self, page: ft.Page):
        self.page = page
        # ---- shared state ----
        self.store = FrameStore()
        self.bg = BgSettings()
        self.info: ffmpeg.VideoInfo | None = None
        self.tmp = Path(tempfile.mkdtemp(prefix="videotosprite_"))
        self.current = 0
        self.busy = False
        self.cancel = False
        self.eyedropper = False
        self.seed_mode = False

        self.fp = ft.FilePicker()
        page.services.append(self.fp)

        # ---- panels ----
        self.preview = PreviewPanel(self)
        self.crop_panel = CropPanel(self)
        self.video = VideoPanel(self)
        self.bg_panel = BgPanel(self)
        self.export = ExportPanel(self)

        self._build()
        self.load_settings()
        page.on_keyboard_event = self.preview.on_key

    # ===================================================================== UI
    def _build(self):
        p = self.page
        p.title = "VideoToSprite"
        p.theme_mode = ft.ThemeMode.DARK
        p.padding = 10
        p.bgcolor = "#1e1e22"
        try:
            p.window.width = 1360
            p.window.height = 900
        except Exception:
            pass

        # Startup check: the binaries aren't bundled, so offer to fetch them.
        missing = ffmpeg.missing_tools()
        self.ffmpeg_text = ft.Text(
            f"⚠ {', '.join(missing)} " + t(
                "não encontrado(s) — a extração não vai funcionar. Baixe agora "
                "(~40MB) ou instale com: brew install ffmpeg"),
            color="#ffd2d2", size=13, weight=ft.FontWeight.BOLD, expand=True)
        self.ffmpeg_btn = ft.Button("Instalar ffmpeg", on_click=self.install_ffmpeg)
        self.ffmpeg_pb = ft.ProgressBar(value=0, visible=False, width=220)
        self.warning_bar = ft.Container(
            visible=bool(missing),
            bgcolor="#5a1d1d", border_radius=6, padding=10,
            margin=ft.Margin.only(bottom=8),
            content=ft.Row([self.ffmpeg_text, self.ffmpeg_pb, self.ffmpeg_btn],
                           vertical_alignment=ft.CrossAxisAlignment.CENTER))

        self.lang_dd = ft.Dropdown(
            value=i18n.get_lang(), width=170, label=t("Idioma"),
            on_select=self.on_language,
            options=[ft.DropdownOption(key=c, text=name) for c, name in i18n.LANGUAGES])
        top_bar = ft.Row([ft.Container(expand=True), self.lang_dd])

        left = ft.Column([self.video.card, self.crop_panel.card], width=330,
                         scroll=ft.ScrollMode.AUTO)
        right = ft.Column([self.bg_panel.card, self.export.card], width=330,
                          scroll=ft.ScrollMode.AUTO)
        p.add(ft.Column([
            top_bar, self.warning_bar,
            ft.Row([left, self.preview.view, right], expand=True, spacing=10,
                   vertical_alignment=ft.CrossAxisAlignment.START),
        ], expand=True, spacing=0))
        # Translate the freshly-built (Portuguese) tree to the chosen language.
        i18n.translate_tree(self.page.controls)

    # ============================================================ mediation
    def refresh_preview(self):
        self.preview.refresh()

    def included_count(self) -> int:
        return sum(1 for f in self.store.frames if f.included)

    def toast(self, msg: str):
        self.page.show_dialog(ft.SnackBar(ft.Text(msg)))

    def set_busy(self, busy: bool):
        self.busy = busy
        self.video.set_busy(busy)
        self.bg_panel.set_busy(busy)
        self.export.set_busy(busy)
        self.preview.set_busy(busy)

    def cancel_op(self, e=None):
        self.cancel = True
        self.export.export_status.value = t("Cancelando…")
        self.page.update()

    # ------------------------------------------------------- ffmpeg install
    def install_ffmpeg(self, e=None):
        """Download ffmpeg/ffprobe into ~/.videotosprite/bin (they aren't bundled)."""
        self.ffmpeg_btn.disabled = True
        self.ffmpeg_pb.value = 0
        self.ffmpeg_pb.visible = True
        self.ffmpeg_text.value = t("Baixando ffmpeg…")
        self.page.update()
        self.page.run_thread(self._do_install_ffmpeg)

    def _do_install_ffmpeg(self):
        def progress(tool: str, frac: float):
            self.ffmpeg_pb.value = frac
            self.ffmpeg_text.value = f"{t('Baixando')} {tool}… {frac * 100:.0f}%"
            self.page.update()

        try:
            ffmpeg_setup.install(progress)
        except Exception as ex:
            self.ffmpeg_pb.visible = False
            self.ffmpeg_btn.disabled = False
            self.ffmpeg_text.value = f"⚠ {ex}"
            self.page.update()
            return
        self.warning_bar.visible = bool(ffmpeg.missing_tools())
        self.ffmpeg_pb.visible = False
        self.ffmpeg_btn.disabled = False
        self.page.update()
        self.toast(t("ffmpeg instalado ✓"))

    def on_language(self, e):
        new = self.lang_dd.value
        if new == i18n.get_lang():
            return
        i18n.translate_tree(self.page.controls, lang=new)   # flip static labels
        i18n.set_lang(new)
        from ..core import config
        config.set("lang", new)
        # re-render the strings composed at runtime via t()
        for ls in (self.bg_panel.tol, self.bg_panel.soft, self.bg_panel.spill,
                   self.bg_panel.ai_cut):
            ls.set(ls.value)
        self.crop_panel.show_norm(self.bg.crop)
        if self.store.frames:
            self.preview.refresh()
            self.preview._update_sel_count()
        if self.info:
            self.video._update_estimate()
            self.video._update_scrub_label(self.video.scrub.value)
        self.page.update()

    def set_eyedropper(self, on: bool):
        self.eyedropper = on
        if on and self.seed_mode:
            self.seed_mode = False
            self.bg_panel.set_seed_active(False)
        self.bg_panel.set_eyedropper_active(on)

    def set_seed_mode(self, on: bool):
        self.seed_mode = on
        if on and self.eyedropper:
            self.eyedropper = False
            self.bg_panel.set_eyedropper_active(False)
        self.bg_panel.set_seed_active(on)

    def set_crop_norm(self, crop):
        """Crop edited numerically in the crop panel — sync overlay + preview."""
        self.bg.crop = crop
        self.preview.sync_crop_overlay()
        self.refresh_preview()
        self.page.update()

    def add_seed(self, fx: float, fy: float):
        self.bg.chroma.seeds.append((fx, fy))
        self.refresh_preview()
        self.page.update()

    def pick_color(self, color):
        self.bg_panel.set_chroma_color(color)
        self.set_eyedropper(False)
        self.refresh_preview()
        self.page.update()

    def on_selection_changed(self):
        self.export.update_ready()

    # ----------------------------------------------------------- settings
    def save_settings(self):
        from ..core import config
        config.set("settings", {
            "video": self.video.settings(),
            "bg": self.bg_panel.settings(),
            "export": self.export.settings(),
        })

    def load_settings(self):
        from ..core import config
        d = config.get("settings") or {}
        if "video" in d:
            self.video.apply(d["video"])
        if "bg" in d:
            self.bg_panel.apply(d["bg"])
        if "export" in d:
            self.export.apply(d["export"])

    def on_frames_extracted(self, fps: float):
        self.preview.populate(self.store)
        self.preview.play_fps_field.value = str(int(round(fps)))
        self.preview.set_enabled(True)
        self.export.set_default_fps(fps)
        self.export.set_ready(True)
        self.current = 0
        self.refresh_preview()
        self.save_settings()
        self.page.update()


def main(page: ft.Page):
    i18n.init_from_config()
    VideoToSpriteApp(page)
