"""Lightweight internationalisation.

The UI is built in Portuguese (the original literals). At startup we translate the
already-built control tree to the chosen language via :func:`translate_tree` — so
the ~70 static labels need no code changes. The handful of strings composed at
runtime (captions, status, toasts, value labels) go through :func:`t`.

Default language is English (``en``); Brazilian Portuguese (``pt``) is optional.
"""
from __future__ import annotations

_lang = "en"

LANGUAGES = [("en", "English"), ("pt", "Português (BR)")]

# Portuguese source -> English. Anything not listed is left as-is (data, numbers,
# model names, identical words…), so it is always safe to run over any string.
_PT_EN: dict[str, str] = {
    # cards / sections
    "1 · Vídeo": "1 · Video",
    "2 · Recortar": "2 · Crop",
    "3 · Remover fundo": "3 · Remove background",
    "4 · Exportar": "4 · Export",
    # video panel
    "Abrir vídeo…": "Open video…",
    "Nenhum vídeo carregado": "No video loaded",
    "Posição no vídeo": "Position in video",
    "Intervalo (trim)": "Range (trim)",
    "máx frames": "max frames",
    "larg. máx": "max width",
    "Extrair frames": "Extract frames",
    "Extraindo frames…": "Extracting frames…",
    "Falha na extração.": "Extraction failed.",
    "Nenhum frame gerado.": "No frames produced.",
    "Cancelado.": "Cancelled.",
    "Não consegui ler o vídeo:": "Could not read the video:",
    "Erro na extração:": "Extraction error:",
    # crop panel
    "✂ Ativar recorte": "✂ Enable crop",
    "✂ Recorte ativo (arraste)": "✂ Crop active (drag)",
    "Largura": "Width",
    "Altura": "Height",
    "sem recorte": "no crop",
    "limpar recorte": "clear crop",
    "Arraste no preview ou edite os valores (px do frame).":
        "Drag on the preview or edit the values (frame px).",
    "Recorte definido · Enter p/ aplicar, Esc p/ cancelar":
        "Crop set · Enter to apply, Esc to cancel",
    # preview / playback / frames
    "Reproduzir": "Play",
    "Pausar": "Pause",
    "veloc (fps)": "speed (fps)",
    "Velocidade da reprodução": "Playback speed",
    "Abra um vídeo para começar": "Open a video to begin",
    "Frames": "Frames",
    "todos": "all",
    "nenhum": "none",
    "inverter": "invert",
    "incluídos": "included",
    "Frame": "Frame",
    "clique em 'Pré-computar IA'": "click 'Pre-compute AI'",
    "arraste para recortar": "drag to crop",
    "Preview da fonte @": "Source preview @",
    # background panel
    "Nenhum": "None",
    "Chroma key (cor)": "Chroma key (colour)",
    "IA (rembg)": "AI (rembg)",
    "Cor:": "Colour:",
    "💧 Pingar cor do fundo": "💧 Pick background colour",
    "🪄 Varinha mágica (só fundo conectado)": "🪄 Magic wand (border-connected only)",
    "Remove só o fundo ligado às bordas; preserva áreas internas da mesma cor "
    "(ex.: branco dentro da vaca).":
        "Removes only the border-connected background; keeps same-coloured areas "
        "inside the subject (e.g. white inside the cow).",
    "Fechar frestas no contorno:": "Close gaps in the outline:",
    "🌱 semear fundo": "🌱 seed background",
    "limpar sementes": "clear seeds",
    "Semear: clique numa região de fundo que sobrou.":
        "Seed: click a leftover background region.",
    "Nível de corte (tolerância)": "Cut level (tolerance)",
    "Suavização (feather)": "Softness (feather)",
    "Despill": "Despill",
    "Nível de corte (matte)": "Cut level (matte)",
    "modelo": "model",
    "alpha matting (bordas finas, +lento)": "alpha matting (fine edges, slower)",
    "⚙ Pré-computar IA (todos os frames)": "⚙ Pre-compute AI (all frames)",
    "A 1ª execução de cada modelo baixa os pesos (~170MB).":
        "The first run of each model downloads its weights (~170MB).",
    "Modelo trocado — recompute a IA.": "Model changed — recompute the AI.",
    "Erro na IA:": "AI error:",
    # export panel
    "Exportar": "Export",
    "Frames PNG": "PNG frames",
    "Compactar PNGs (.zip)": "Zip the PNGs (.zip)",
    "Sprite sheet (+JSON)": "Sprite sheet (+JSON)",
    "GIF de preview (borda dura)": "Preview GIF (hard edge)",
    "WebP animado (borda suave)": "Animated WebP (soft edge)",
    "Alpha de 8 bits — bordas suaves no preview":
        "8-bit alpha — soft edges in the preview",
    "APNG animado (sem perdas)": "Animated APNG (lossless)",
    "Tamanho potência de 2": "Power-of-two size",
    "Recortar transparência (sheet apertada)":
        "Trim transparency (tight sheet)",
    "Corta a borda transparente de cada frame e grava offset/source_size no JSON "
    "(estilo TexturePacker).":
        "Trims each frame's transparent border and records offset/source_size in "
        "the JSON (TexturePacker-style).",
    "colunas (0=auto)": "columns (0=auto)",
    "padding": "padding",
    "fps GIF/atlas": "GIF/atlas fps",
    "pasta de saída": "output folder",
    "cancelar": "cancel",
    "Cancelando…": "Cancelling…",
    "Iniciando…": "Starting…",
    "Falha.": "Failed.",
    "Exportação cancelada (pasta já existe).":
        "Export cancelled (folder already exists).",
    "Concluído ✓": "Done ✓",
    "Pasta já existe": "Folder already exists",
    "A pasta de saída já existe:": "The output folder already exists:",
    "Os arquivos com o mesmo nome serão sobrescritos. Continuar?":
        "Files with the same name will be overwritten. Continue?",
    "Cancelar": "Cancel",
    "Sobrescrever": "Overwrite",
    "Erro na exportação:": "Export error:",
    "Exportado para": "Exported to",
    # startup warning / ffmpeg install
    "não encontrado(s) — a extração não vai funcionar. Baixe agora (~40MB) ou "
    "instale com: brew install ffmpeg":
        "not found — extraction won't work. Download now (~40MB) or install with: "
        "brew install ffmpeg",
    "Instalar ffmpeg": "Install ffmpeg",
    "Baixando ffmpeg…": "Downloading ffmpeg…",
    "Baixando": "Downloading",
    "ffmpeg instalado ✓": "ffmpeg installed ✓",
    # language selector
    "Idioma": "Language",
}

_EN_PT = {v: k for k, v in _PT_EN.items()}


def set_lang(code: str):
    global _lang
    if code in ("en", "pt"):
        _lang = code


def get_lang() -> str:
    return _lang


def init_from_config():
    from ..core import config
    set_lang(config.get("lang", "en"))


def t(s: str) -> str:
    """Translate a single string for the current language."""
    return _PT_EN.get(s, s) if _lang == "en" else s


# control attributes that may hold display text / child controls
_TEXT_ATTRS = ("value", "content", "label", "tooltip")
_CHILD_ATTRS = ("content", "controls", "actions", "title", "leading", "trailing")


def _translate_to(s: str, lang: str) -> str:
    return _PT_EN.get(s, s) if lang == "en" else _EN_PT.get(s, s)


def translate_tree(roots, lang: str | None = None):
    """Walk the built control tree and translate every known display string to
    ``lang`` (defaults to the current language). Strings not in the table are left
    untouched, so data/numbers/paths are safe."""
    import flet as ft

    lang = lang or _lang
    seen: set[int] = set()

    def walk(c):
        if id(c) in seen:
            return
        seen.add(id(c))
        for attr in _TEXT_ATTRS:
            # `value` holds *data* on Radio/Dropdown/TextField/Slider — only translate
            # it for Text (display). content/label/tooltip are display text.
            if attr == "value" and not isinstance(c, ft.Text):
                continue
            v = getattr(c, attr, None)
            if isinstance(v, str) and v.strip():
                nv = _translate_to(v, lang)
                if nv != v:
                    try:
                        setattr(c, attr, nv)
                    except Exception:
                        pass
        for attr in _CHILD_ATTRS:
            v = getattr(c, attr, None)
            if isinstance(v, ft.Control):
                walk(v)
            elif isinstance(v, (list, tuple)):
                for it in v:
                    if isinstance(it, ft.Control):
                        walk(it)

    for r in roots:
        walk(r)
