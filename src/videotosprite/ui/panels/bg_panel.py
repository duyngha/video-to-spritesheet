"""Background removal panel: none / chroma key (+ magic wand) / AI (rembg)."""
from __future__ import annotations

import flet as ft

from ...core import bg_ai
from ...core.render import BgMode
from ..i18n import t
from ..widgets import ACCENT, LabeledSlider, card


class BgPanel:
    def __init__(self, app):
        self.app = app
        self._build()

    def _build(self):
        self.mode_group = ft.RadioGroup(
            value="none", on_change=self.on_mode_change,
            content=ft.Column([
                ft.Radio(value="none", label="Nenhum"),
                ft.Radio(value="chroma", label="Chroma key (cor)"),
                ft.Radio(value="ai", label="IA (rembg)"),
            ], spacing=0))

        # chroma
        self.swatch = ft.Container(width=26, height=26, bgcolor="#00ff00",
                                   border_radius=4, border=ft.Border.all(1, "#111"))
        self.eyedrop_btn = ft.Button("💧 Pingar cor do fundo",
                                     on_click=self.toggle_eyedropper)
        self.wand_cb = ft.Checkbox(
            label="🪄 Varinha mágica (só fundo conectado)", value=False,
            on_change=self.on_wand,
            tooltip="Remove só o fundo ligado às bordas; preserva áreas internas "
                    "da mesma cor (ex.: branco dentro da vaca).")
        self.wand_close = ft.Slider(min=0, max=8, divisions=8, value=0,
                                    label="{value} px", active_color=ACCENT,
                                    on_change=self.on_wand_close)
        self.seed_btn = ft.Button("🌱 semear fundo", on_click=self.toggle_seed)
        self.clear_seeds_btn = ft.TextButton("limpar sementes",
                                             on_click=self.clear_seeds)
        self.wand_extra = ft.Column([
            ft.Text("Fechar frestas no contorno:", size=11, color="#999"),
            self.wand_close,
            ft.Row([self.seed_btn, self.clear_seeds_btn]),
            ft.Text("Semear: clique numa região de fundo que sobrou.",
                    size=11, color="#999"),
        ], visible=False, spacing=2)
        self.tol = LabeledSlider("Nível de corte (tolerância)", 0.18, self.on_chroma)
        self.soft = LabeledSlider("Suavização (feather)", 0.10, self.on_chroma)
        self.spill = LabeledSlider("Despill", 0.0, self.on_chroma)
        self.chroma_box = ft.Column([
            self.eyedrop_btn, ft.Row([ft.Text("Cor:", size=12), self.swatch]),
            self.wand_cb, self.wand_extra,
            *self.tol.controls, *self.soft.controls, *self.spill.controls,
        ], visible=False, spacing=2)

        # AI
        self.ai_model_dd = ft.Dropdown(
            value="u2net", label="modelo", width=200, on_select=self.on_ai_model,
            options=[ft.DropdownOption(key=m, text=m) for m in bg_ai.MODELS])
        self.ai_alpha_cb = ft.Checkbox(label="alpha matting (bordas finas, +lento)",
                                       value=False, on_change=self.on_ai_alpha)
        self.ai_cut = LabeledSlider("Nível de corte (matte)", 0.0, self.on_ai)
        self.ai_btn = ft.Button("⚙ Pré-computar IA (todos os frames)",
                                on_click=self.start_ai)
        self.ai_pb = ft.ProgressBar(value=0, visible=False, expand=True)
        self.ai_cancel = ft.TextButton("cancelar", visible=False,
                                       on_click=self.app.cancel_op)
        self.ai_box = ft.Column([
            self.ai_model_dd, self.ai_alpha_cb, *self.ai_cut.controls, self.ai_btn,
            ft.Row([self.ai_pb, self.ai_cancel]),
            ft.Text("A 1ª execução de cada modelo baixa os pesos (~170MB).",
                    size=11, color="#999"),
        ], visible=False, spacing=2)

        self.card = card("3 · Remover fundo",
                         [self.mode_group, self.chroma_box, self.ai_box])

    # ------------------------------------------------------------- chroma
    def on_mode_change(self, e):
        v = self.mode_group.value
        self.app.bg.mode = BgMode(v)
        self.chroma_box.visible = v == "chroma"
        self.ai_box.visible = v == "ai"
        if v != "chroma":
            self.app.set_eyedropper(False)
        self.app.refresh_preview()
        self.app.page.update()

    def on_chroma(self):
        self.app.bg.chroma.tolerance = self.tol.value
        self.app.bg.chroma.softness = self.soft.value
        self.app.bg.chroma.spill = self.spill.value
        self.app.refresh_preview()
        self.app.page.update()

    def on_wand(self, e):
        self.app.bg.chroma.connected = self.wand_cb.value
        self.wand_extra.visible = self.wand_cb.value
        if not self.wand_cb.value:
            self.app.set_seed_mode(False)
        self.app.refresh_preview()
        self.app.page.update()

    def on_wand_close(self, e):
        self.app.bg.chroma.close_px = int(self.wand_close.value)
        self.app.refresh_preview()
        self.app.page.update()

    def toggle_seed(self, e):
        self.app.set_seed_mode(not self.app.seed_mode)
        self.app.page.update()

    def set_seed_active(self, on: bool):
        self.seed_btn.bgcolor = ACCENT if on else None
        self.seed_btn.color = "white" if on else None

    def clear_seeds(self, e):
        self.app.bg.chroma.seeds.clear()
        self.app.refresh_preview()
        self.app.page.update()

    def toggle_eyedropper(self, e):
        self.app.set_eyedropper(not self.app.eyedropper)
        self.app.page.update()

    def set_eyedropper_active(self, on: bool):
        self.eyedrop_btn.bgcolor = ACCENT if on else None
        self.eyedrop_btn.color = "white" if on else None

    def set_chroma_color(self, color):
        r, g, b = color
        self.app.bg.chroma.color = (r, g, b)
        self.swatch.bgcolor = f"#{r:02x}{g:02x}{b:02x}"

    # ----------------------------------------------------------------- AI
    def on_ai(self):
        self.app.bg.ai_cut = self.ai_cut.value
        self.app.refresh_preview()
        self.app.page.update()

    def on_ai_model(self, e):
        self.app.bg.ai_model = self.ai_model_dd.value
        self.app.store.clear_mattes()
        self.app.refresh_preview()
        self.app.toast(t("Modelo trocado — recompute a IA."))
        self.app.page.update()

    def on_ai_alpha(self, e):
        self.app.bg.ai_alpha_matting = self.ai_alpha_cb.value
        self.app.store.clear_mattes()
        self.app.refresh_preview()
        self.app.page.update()

    def start_ai(self, e):
        if self.app.busy or not len(self.app.store):
            return
        if not any(f.ai_matte is None for f in self.app.store.frames):
            self.app.refresh_preview()
            self.app.page.update()
            return
        self.app.cancel = False
        self.app.set_busy(True)
        self.ai_pb.visible = True
        self.ai_pb.value = 0
        self.ai_cancel.visible = True
        self.app.page.update()
        self.app.page.run_thread(self._do_ai)

    def _do_ai(self):
        pending = [f for f in self.app.store.frames if f.ai_matte is None]
        total = len(pending)
        try:
            for i, fr in enumerate(pending, 1):
                if self.app.cancel:
                    break
                fr.ai_matte = bg_ai.compute_matte(fr.rgb, self.app.bg.ai_model,
                                                  self.app.bg.ai_alpha_matting)
                self.ai_pb.value = i / total
                self.ai_pb.update()
                if fr.index == self.app.current:
                    self.app.refresh_preview()
                    self.app.page.update()
        except Exception as ex:
            self._end_ai()
            self.app.toast(f"{t('Erro na IA:')} {ex}")
            return
        self._end_ai()

    def _end_ai(self):
        self.ai_pb.visible = False
        self.ai_cancel.visible = False
        self.app.set_busy(False)
        self.app.refresh_preview()
        self.app.page.update()

    # --------------------------------------------------------------- state
    def set_busy(self, busy):
        self.ai_btn.disabled = busy or len(self.app.store) == 0

    # --------------------------------------------------------- persistence
    def settings(self):
        return {"mode": self.mode_group.value, "tol": self.tol.value,
                "soft": self.soft.value, "spill": self.spill.value,
                "wand": self.wand_cb.value, "close": self.wand_close.value,
                "ai_model": self.ai_model_dd.value, "ai_alpha": self.ai_alpha_cb.value}

    def apply(self, d):
        bg = self.app.bg
        mode = d.get("mode", self.mode_group.value)
        self.mode_group.value = mode
        bg.mode = BgMode(mode)
        self.chroma_box.visible = mode == "chroma"
        self.ai_box.visible = mode == "ai"
        self.tol.set(d.get("tol", self.tol.value))
        self.soft.set(d.get("soft", self.soft.value))
        self.spill.set(d.get("spill", self.spill.value))
        bg.chroma.tolerance = self.tol.value
        bg.chroma.softness = self.soft.value
        bg.chroma.spill = self.spill.value
        self.wand_cb.value = d.get("wand", self.wand_cb.value)
        self.wand_extra.visible = self.wand_cb.value
        bg.chroma.connected = self.wand_cb.value
        self.wand_close.value = d.get("close", self.wand_close.value)
        bg.chroma.close_px = int(self.wand_close.value)
        self.ai_model_dd.value = d.get("ai_model", self.ai_model_dd.value)
        bg.ai_model = self.ai_model_dd.value
        self.ai_alpha_cb.value = d.get("ai_alpha", self.ai_alpha_cb.value)
        bg.ai_alpha_matting = self.ai_alpha_cb.value
