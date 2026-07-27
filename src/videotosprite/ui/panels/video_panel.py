"""Source panel: open a video, scrub/trim, choose frame rate, extract frames."""
from __future__ import annotations

from pathlib import Path

import flet as ft

from ...core import ffmpeg
from ..i18n import t
from ..widgets import ACCENT, card, fmt_time, to_float, to_int


class VideoPanel:
    def __init__(self, app):
        self.app = app
        self._build()

    def _build(self):
        self.open_btn = ft.Button("Abrir vídeo…", on_click=self.open_video)
        self.info_text = ft.Text("Nenhum vídeo carregado", size=12, color="#aaa")
        self.scrub_lbl = ft.Text("Posição no vídeo", size=11, color="#999")
        self.scrub = ft.Slider(min=0, max=1, value=0, on_change=self.on_scrub_change,
                               on_change_end=self.on_scrub_end, disabled=True)
        self.trim = ft.RangeSlider(start_value=0, end_value=1, min=0, max=1,
                                   on_change=self.on_trim_change, disabled=True)
        self.trim_lbl = ft.Text("—", size=12, color="#8fc")
        self.fps_field = ft.TextField(value="12", width=90, label="fps",
                                      on_change=self.on_estimate)
        self.maxframes_field = ft.TextField(value="0", width=110, label="máx frames",
                                            on_change=self.on_estimate)
        self.maxwidth_field = ft.TextField(value="0", width=110, label="larg. máx")
        self.estimate_text = ft.Text("—", size=12, color="#8fc")
        self.extract_btn = ft.Button("Extrair frames", on_click=self.start_extract,
                                     disabled=True, bgcolor=ACCENT, color="white")
        self.extract_pb = ft.ProgressBar(value=0, visible=False, expand=True)
        self.extract_cancel = ft.TextButton("cancelar", visible=False,
                                            on_click=self.app.cancel_op)

        self.card = card("1 · Vídeo", [
            self.open_btn, self.info_text,
            self.scrub_lbl, self.scrub,
            ft.Text("Intervalo (trim)", size=11, color="#999"), self.trim, self.trim_lbl,
            ft.Row([self.fps_field, self.maxframes_field, self.maxwidth_field], wrap=True),
            self.estimate_text, self.extract_btn,
            ft.Row([self.extract_pb, self.extract_cancel]),
        ])

    # ----------------------------------------------------------- load
    async def open_video(self, e):
        from ...core import config
        files = await self.app.fp.pick_files(
            dialog_title="Escolha um vídeo", allow_multiple=False,
            initial_directory=config.get("open_dir"),
            allowed_extensions=["mp4", "mov", "mkv", "avi", "webm", "m4v"])
        if files:
            config.set("open_dir", str(Path(files[0].path).parent))
            self.load_video(files[0].path)

    def load_video(self, path):
        try:
            info = ffmpeg.probe(path)
        except Exception as ex:
            self.app.toast(f"{t('Não consegui ler o vídeo:')} {ex}")
            return
        self.app.info = info
        self.info_text.value = (f"{Path(path).name}\n{info.width}×{info.height} · "
                                f"{info.fps:.2f} fps · {fmt_time(info.duration)}")
        dur = max(info.duration, 0.01)
        self.scrub.min, self.scrub.max, self.scrub.value = 0, dur, 0
        self.scrub.disabled = False
        self.trim.min, self.trim.max = 0, dur
        self.trim.start_value, self.trim.end_value = 0, dur
        self.trim.disabled = False
        self.extract_btn.disabled = False
        self._update_scrub_label(0.0)
        self.app.store.clear()
        self.app.preview.reset()
        self.app.export.set_ready(False)
        self._update_estimate()
        self.app.page.update()
        self._preview_source(0.0)

    # ------------------------------------------------------- scrub / trim
    def on_scrub_change(self, e):
        self._update_scrub_label(float(e.control.value))
        self.scrub_lbl.update()

    def _update_scrub_label(self, secs):
        total = self.app.info.duration if self.app.info else 0.0
        self.scrub_lbl.value = (f"{t('Posição no vídeo')}: "
                                f"{fmt_time(secs)} / {fmt_time(total)}")

    def on_scrub_end(self, e):
        if self.app.info and len(self.app.store) == 0:
            self._preview_source(float(e.control.value))

    def _preview_source(self, secs):
        if not self.app.info:
            return
        try:
            rgb = ffmpeg.grab_frame(self.app.info.path, secs, max_width=720,
                                    src_size=(self.app.info.width, self.app.info.height))
        except Exception:
            return
        self.app.preview.show_source(rgb)
        self.app.preview.set_caption(f"{t('Preview da fonte @')} {secs:.2f}s")
        self.app.page.update()

    def on_trim_change(self, e):
        self._update_estimate()
        self.app.page.update()

    def on_estimate(self, e):
        self._update_estimate()
        self.app.page.update()

    def effective_fps(self):
        fps = max(to_float(self.fps_field.value, 12), 0.1)
        dur = max(self.trim.end_value - self.trim.start_value, 1e-3)
        cap = to_int(self.maxframes_field.value, 0)
        if cap > 0 and fps * dur > cap:
            return max(cap / dur, 0.1)
        return fps

    def _update_estimate(self):
        if not self.app.info:
            return
        a, b = self.trim.start_value, self.trim.end_value
        dur = max(b - a, 0.0)
        eff = self.effective_fps()
        n = int(dur * eff)
        note = "" if abs(eff - to_float(self.fps_field.value, 12)) < 1e-3 else f" (fps→{eff:.2f})"
        self.trim_lbl.value = f"{fmt_time(a)} → {fmt_time(b)}"
        self.estimate_text.value = f"~{n} frames · {fmt_time(dur)}{note}"

    # --------------------------------------------------------- extract
    def start_extract(self, e):
        if self.app.busy or not self.app.info:
            return
        self.app.cancel = False
        self.app.set_busy(True)
        self.extract_pb.visible = True
        self.extract_pb.value = None
        self.extract_cancel.visible = True
        self.app.preview.set_caption(t("Extraindo frames…"))
        self.app.page.update()
        self.app.page.run_thread(self._do_extract, self.trim.start_value,
                                 self.trim.end_value, self.effective_fps(),
                                 to_int(self.maxwidth_field.value, 0))

    def _do_extract(self, start, end, fps, max_width):
        out_dir = self.app.tmp / "frames"
        est = max(int((end - start) * fps), 1)

        def prog(n):
            self.extract_pb.value = min(n / est, 1.0)
            self.extract_pb.update()

        try:
            paths = ffmpeg.extract_frames(self.app.info.path, out_dir, start, end, fps,
                                          max_width or None, progress=prog,
                                          should_cancel=lambda: self.app.cancel)
        except Exception as ex:
            self._finish(fps, error=str(ex))
            return
        if not self.app.cancel:
            self.app.store.load_from_paths(paths)
        self._finish(fps)

    def _finish(self, fps, error=None):
        self.extract_pb.visible = False
        self.extract_cancel.visible = False
        self.app.set_busy(False)
        if error:
            self.app.preview.set_caption(t("Falha na extração."))
            self.app.toast(f"{t('Erro na extração:')} {error}")
            self.app.page.update()
            return
        if not len(self.app.store):
            self.app.preview.set_caption(
                t("Cancelado.") if self.app.cancel else t("Nenhum frame gerado."))
            self.app.page.update()
            return
        self.app.on_frames_extracted(fps)

    # --------------------------------------------------------- progress
    def set_busy(self, busy):
        self.extract_btn.disabled = busy or self.app.info is None

    # --------------------------------------------------------- persistence
    def settings(self):
        return {"fps": self.fps_field.value,
                "maxframes": self.maxframes_field.value,
                "maxwidth": self.maxwidth_field.value}

    def apply(self, d):
        self.fps_field.value = d.get("fps", self.fps_field.value)
        self.maxframes_field.value = d.get("maxframes", self.maxframes_field.value)
        self.maxwidth_field.value = d.get("maxwidth", self.maxwidth_field.value)
