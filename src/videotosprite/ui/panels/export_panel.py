"""Export panel: choose outputs (PNG / sprite sheet / GIF) and run the export,
asking before overwriting an existing output folder."""
from __future__ import annotations

from pathlib import Path

import flet as ft

from ...core import config
from ...core.export import ExportOptions, export
from ...core.spritesheet import SheetSettings
from ..i18n import t
from ..widgets import card, to_float, to_int


class ExportPanel:
    def __init__(self, app):
        self.app = app
        self._build()

    def _build(self):
        self.cb_png = ft.Checkbox(label="Frames PNG", value=True)
        self.cb_zip = ft.Checkbox(label="Compactar PNGs (.zip)", value=False)
        self.cb_sheet = ft.Checkbox(label="Sprite sheet (+JSON)", value=True)
        self.cb_gif = ft.Checkbox(label="GIF de preview (borda dura)", value=True)
        self.cb_webp = ft.Checkbox(label="WebP animado (borda suave)", value=True,
                                   tooltip="Alpha de 8 bits — bordas suaves no preview")
        self.cb_apng = ft.Checkbox(label="APNG animado (sem perdas)", value=False)
        self.cols_field = ft.TextField(value="0", width=90, label="colunas (0=auto)")
        self.pad_field = ft.TextField(value="0", width=90, label="padding")
        self.pow2 = ft.Checkbox(label="Tamanho potência de 2", value=False)
        self.cb_trim = ft.Checkbox(
            label="Recortar transparência (sheet apertada)", value=False,
            tooltip="Corta a borda transparente de cada frame e grava offset/"
                    "source_size no JSON (estilo TexturePacker).")
        self.outfps_field = ft.TextField(value="12", width=110, label="fps GIF/atlas")
        self.outdir_field = ft.TextField(
            value=config.get("out_dir") or str(Path.cwd() / "output"),
            label="pasta de saída", expand=True)
        outdir_btn = ft.IconButton(icon=ft.Icons.FOLDER_OPEN, on_click=self.choose_outdir)
        self.export_btn = ft.Button("Exportar", on_click=self.start_export,
                                    disabled=True, bgcolor="#3fae6a", color="white")
        self.export_pb = ft.ProgressBar(value=0, visible=False, expand=True)
        self.export_cancel = ft.TextButton("cancelar", visible=False,
                                           on_click=self.app.cancel_op)
        self.export_status = ft.Text("", size=12, color="#8fc")

        self.card = card("4 · Exportar", [
            self.export_btn, ft.Row([self.export_pb, self.export_cancel]),
            self.export_status,
            ft.Divider(height=1),
            self.cb_png, self.cb_zip, self.cb_sheet,
            self.cb_gif, self.cb_webp, self.cb_apng, self.pow2, self.cb_trim,
            ft.Row([self.cols_field, self.pad_field, self.outfps_field], wrap=True),
            ft.Row([self.outdir_field, outdir_btn]),
        ])

    # -------------------------------------------------------------- state
    def set_ready(self, ready: bool):
        self.export_btn.disabled = not ready or self.app.busy

    def update_ready(self):
        self.export_btn.disabled = self.app.busy or self.app.included_count() == 0

    def set_default_fps(self, fps):
        self.outfps_field.value = str(int(round(fps)))

    def set_busy(self, busy):
        self.export_btn.disabled = busy or self.app.included_count() == 0

    # --------------------------------------------------------- persistence
    def settings(self):
        return {"png": self.cb_png.value, "zip": self.cb_zip.value,
                "sheet": self.cb_sheet.value, "gif": self.cb_gif.value,
                "webp": self.cb_webp.value, "apng": self.cb_apng.value,
                "pow2": self.pow2.value, "trim": self.cb_trim.value,
                "cols": self.cols_field.value, "pad": self.pad_field.value,
                "outfps": self.outfps_field.value}

    def apply(self, d):
        self.cb_png.value = d.get("png", self.cb_png.value)
        self.cb_zip.value = d.get("zip", self.cb_zip.value)
        self.cb_sheet.value = d.get("sheet", self.cb_sheet.value)
        self.cb_gif.value = d.get("gif", self.cb_gif.value)
        self.cb_webp.value = d.get("webp", self.cb_webp.value)
        self.cb_apng.value = d.get("apng", self.cb_apng.value)
        self.pow2.value = d.get("pow2", self.pow2.value)
        self.cb_trim.value = d.get("trim", self.cb_trim.value)
        self.cols_field.value = d.get("cols", self.cols_field.value)
        self.pad_field.value = d.get("pad", self.pad_field.value)
        self.outfps_field.value = d.get("outfps", self.outfps_field.value)

    # -------------------------------------------------------------- run
    async def choose_outdir(self, e):
        d = await self.app.fp.get_directory_path(
            dialog_title="Pasta de saída",
            initial_directory=self.outdir_field.value or config.get("out_dir"))
        if d:
            self.outdir_field.value = d
            config.set("out_dir", d)
            self.app.page.update()

    def start_export(self, e):
        if self.app.busy or self.app.included_count() == 0:
            return
        out_dir = Path(self.outdir_field.value)
        if out_dir.exists():
            self._confirm_overwrite(out_dir)
        else:
            self._run_export()

    def _confirm_overwrite(self, out_dir: Path):
        def cancel(e):
            self.app.page.pop_dialog()
            self.export_status.value = t("Exportação cancelada (pasta já existe).")
            self.app.page.update()

        def confirm(e):
            self.app.page.pop_dialog()
            self._run_export()

        self.app.page.show_dialog(ft.AlertDialog(
            modal=True,
            title=ft.Text(t("Pasta já existe")),
            content=ft.Text(
                f"{t('A pasta de saída já existe:')}\n{out_dir}\n\n"
                + t("Os arquivos com o mesmo nome serão sobrescritos. Continuar?")),
            actions=[
                ft.TextButton(t("Cancelar"), on_click=cancel),
                ft.FilledButton(t("Sobrescrever"), on_click=confirm),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        ))

    def _run_export(self):
        config.set("out_dir", self.outdir_field.value)
        self.app.save_settings()
        self.app.cancel = False
        self.app.set_busy(True)
        self.export_pb.visible = True
        self.export_pb.value = 0
        self.export_cancel.visible = True
        self.export_status.value = t("Iniciando…")
        self.app.page.update()
        self.app.page.run_thread(self._do_export)

    def _do_export(self):
        opts = ExportOptions(
            out_dir=Path(self.outdir_field.value),
            fps=to_float(self.outfps_field.value, 12),
            export_pngs=self.cb_png.value, zip_pngs=self.cb_zip.value,
            export_sheet=self.cb_sheet.value, export_gif=self.cb_gif.value,
            export_webp=self.cb_webp.value, export_apng=self.cb_apng.value,
            sheet=SheetSettings(columns=to_int(self.cols_field.value, 0),
                                padding=to_int(self.pad_field.value, 0),
                                power_of_two=self.pow2.value,
                                trim=self.cb_trim.value))

        def prog(d, t):
            self.export_pb.value = d / max(t, 1)
            self.export_pb.update()

        def status(s):
            self.export_status.value = s
            self.export_status.update()

        try:
            written = export(self.app.store, self.app.bg, opts, progress=prog,
                             status=status, should_cancel=lambda: self.app.cancel)
        except Exception as ex:
            self.export_pb.visible = False
            self.export_cancel.visible = False
            self.app.set_busy(False)
            self.export_status.value = t("Falha.")
            self.app.toast(f"{t('Erro na exportação:')} {ex}")
            self.app.page.update()
            return
        self.export_pb.visible = False
        self.export_cancel.visible = False
        self.app.set_busy(False)
        if self.app.cancel or not written:
            self.export_status.value = t("Cancelado.")
        else:
            self.export_status.value = t("Concluído ✓") + "  " + ", ".join(written.keys())
            self.app.toast(f"{t('Exportado para')} {opts.out_dir}")
        self.app.page.update()
