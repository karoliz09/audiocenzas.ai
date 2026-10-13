"""AudioCenzas.ai - web interface. Run: python app.py"""
import subprocess
import tempfile
import time
from pathlib import Path

import gradio as gr
import pandas as pd

from audiocenzas import PAD, all_words, censor, default_model, find_hits, load_patterns, merge, transcribe

ROOT = Path(__file__).resolve().parent.parent
WORDS = ROOT / "profanity.txt"
OUT_DIR = ROOT / "output"
CLIP_DIR = Path(tempfile.gettempdir()) / "audiocenzas_clips"
TEXT = {
    "en": {
        "intro": "# AudioCenzas.ai\nUpload an audio or video file - profanity will be muted.",
        "ui_lang": "Interface language",
        "file": "File",
        "lang": "Speech language",
        "lang_choices": [("Automatic", ""), ("Lithuanian", "lt"), ("English", "en")],
        "model": "Model (larger = more accurate, slower)",
        "analyze": "1. Analyze",
        "mode": "Mode",
        "mode_choices": [("Beep", "beep"), ("Mute", "mute"), ("Cut out", "cut")],
        "export": "2. Export",
        "result": "Result",
        "columns": ["Censor", "Start", "End", "Word"],
        "table": "Detected words (click a row to listen)",
        "clip": "Clip (+-1 s)",
        "transcript": "Full transcript (red = detected profanity)",
        "no_file": "Please upload a file.",
        "loading": "Loading model...",
        "transcribing": "Transcribing speech...",
        "found": ("Profanity found: **{n}**. Review the table: untick false positives, "
                  "add a row for missed words, then click **Export**."),
        "nothing_selected": "No words selected.",
        "rendering": "Creating censored file...",
        "done": "Muted spots: **{n}**. File is ready.",
        "elapsed": "Analysis took **{t}**.",
    },
    "lt": {
        "intro": "# AudioCenzas.ai\nĮkelkite audio ar video failą - keiksmažodžiai bus nutildyti.",
        "ui_lang": "Sąsajos kalba",
        "file": "Failas",
        "lang": "Kalbos kalba",
        "lang_choices": [("Automatiškai", ""), ("Lietuvių", "lt"), ("Anglų", "en")],
        "model": "Modelis (didesnis = tikslesnis, lėtesnis)",
        "analyze": "1. Analizuoti",
        "mode": "Režimas",
        "mode_choices": [("Pyptelėjimas", "beep"), ("Nutildymas", "mute"), ("Iškirpimas", "cut")],
        "export": "2. Eksportuoti",
        "result": "Rezultatas",
        "columns": ["Cenzūruoti", "Pradžia", "Pabaiga", "Žodis"],
        "table": "Rasti žodžiai (paspauskite eilutę - perklausysite)",
        "clip": "Fragmentas (+-1 s)",
        "transcript": "Visas transkriptas (raudonai - rasti keiksmažodžiai)",
        "no_file": "Įkelkite failą.",
        "loading": "Kraunamas modelis...",
        "transcribing": "Atpažįstama kalba...",
        "found": ("Rasta keiksmažodžių: **{n}**. Peržiūrėkite lentelę: nuimkite varnelę "
                  "nuo klaidingų, pridėkite eilutę praleistiems, tada spauskite **Eksportuoti**."),
        "nothing_selected": "Nepažymėtas nė vienas žodis.",
        "rendering": "Kuriamas cenzūruotas failas...",
        "done": "Nutildyta vietų: **{n}**. Failas paruoštas.",
        "elapsed": "Analizė užtruko **{t}**.",
    },
}
DEFAULT_UI = "lt"


def rows(table):
    """Table rows as lists, independent of the (translated) column headers."""
    if table is None:
        return []
    return pd.DataFrame(table).values.tolist()


def analyze(file, lang, model, ui, progress=gr.Progress()):
    T = TEXT[ui]
    if not file:
        raise gr.Error(T["no_file"])
    started = time.monotonic()
    progress(0, desc=T["loading"])
    segments = transcribe(Path(file), model, lang or None,
                          progress=lambda p: progress(p, desc=T["transcribing"]))
    hits = find_hits(all_words(segments), load_patterns(WORDS))
    table = pd.DataFrame([[True, to_hms(s), to_hms(e), w] for s, e, w in hits], columns=T["columns"])
    transcript = build_transcript(segments, {(round(s, 2), w) for s, _, w in hits})
    elapsed = T["elapsed"].format(t=format_duration(time.monotonic() - started))
    status = f'{elapsed} {T["found"].format(n=len(hits))}'
    return table, transcript, status, gr.update(interactive=True)


def format_duration(seconds):
    m, s = divmod(round(seconds), 60)
    return f"{m} min {s} s" if m else f"{s} s"


def to_hms(seconds, decimals=True):
    """1234.5 -> '0:20:34.50' (or '0:20:34' without decimals)."""
    seconds = round(seconds, 2) if decimals else int(seconds)
    h, rest = divmod(seconds, 3600)
    m, s = divmod(rest, 60)
    sec = f"{s:05.2f}" if decimals else f"{int(s):02d}"
    return f"{int(h)}:{int(m):02d}:{sec}"


def from_hms(value):
    """Parses 'h:mm:ss.ss', 'mm:ss' or plain seconds back to seconds."""
    total = 0.0
    for part in str(value).strip().split(":"):
        total = total * 60 + float(part)
    return total


def build_transcript(segments, hit_keys):
    """HighlightedText format: [(text, label|None)], one line per segment."""
    out = []
    for seg_start, _, words in segments:
        out.append((f"[{to_hms(seg_start, decimals=False)}]  ", None))
        for s, _, w in words:
            hit = (round(max(0.0, s - PAD), 2), w) in hit_keys
            out.append((w, "keiksmazodis" if hit else None))
            out.append((" ", None))
        out.append(("\n", None))
    return out


def selected_intervals(table):
    out = []
    for r in rows(table):
        try:
            if str(r[0]).lower() in ("true", "1"):
                out.append((from_hms(r[1]), from_hms(r[2])))
        except (TypeError, ValueError):
            continue  # empty or malformed row
    return [(s, e) for s, e in out if e > s]


def preview(file, table, evt: gr.SelectData):
    """On row click, cuts a clip (+-1 s) for preview."""
    try:
        row = rows(table)[evt.index[0]]
        s, e = from_hms(row[1]), from_hms(row[2])
    except (TypeError, ValueError, IndexError):
        return None
    CLIP_DIR.mkdir(exist_ok=True)
    clip = CLIP_DIR / f"clip_{s:.2f}.wav"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{max(0, s - 1):.2f}",
                    "-to", f"{e + 1:.2f}", "-i", file, "-vn", str(clip)], check=True)
    return str(clip)


def export(file, table, mode, ui, progress=gr.Progress()):
    T = TEXT[ui]
    if not file:
        raise gr.Error(T["no_file"])
    intervals = selected_intervals(table)
    if not intervals:
        raise gr.Error(T["nothing_selected"])
    src = Path(file)
    OUT_DIR.mkdir(exist_ok=True)
    out = OUT_DIR / f"{src.stem}_cenzuruota{src.suffix}"
    progress(0.5, desc=T["rendering"])
    censor(src, out, merge(intervals), mode)
    return str(out), T["done"].format(n=len(intervals))


def set_ui_lang(ui, table):
    """Re-labels every component; keeps the table contents under translated headers."""
    T = TEXT[ui]
    data = pd.DataFrame(rows(table), columns=T["columns"])
    return (gr.update(value=T["intro"]), gr.update(label=T["ui_lang"]),
            gr.update(label=T["file"]), gr.update(label=T["lang"], choices=T["lang_choices"]),
            gr.update(label=T["model"]), gr.update(value=T["analyze"]),
            gr.update(label=T["mode"], choices=T["mode_choices"]), gr.update(value=T["export"]),
            gr.update(label=T["result"]), gr.update(value=data, label=T["table"]),
            gr.update(label=T["clip"]), gr.update(label=T["transcript"]))


T = TEXT[DEFAULT_UI]
with gr.Blocks(title="AudioCenzas.ai") as demo:
    with gr.Row():
        intro = gr.Markdown(T["intro"])
        ui = gr.Radio([("English", "en"), ("Lietuvių", "lt")], value=DEFAULT_UI,
                      label=T["ui_lang"], scale=0, min_width=200)
    with gr.Row():
        with gr.Column(scale=1):
            file = gr.File(label=T["file"], file_types=["audio", "video"], type="filepath")
            lang = gr.Dropdown(T["lang_choices"], value="lt", label=T["lang"])
            model = gr.Dropdown(["tiny", "base", "small", "medium", "large-v3"],
                                value=default_model(), label=T["model"])
            analyze_btn = gr.Button(T["analyze"], variant="primary")
            mode = gr.Radio(T["mode_choices"], value="beep", label=T["mode"])
            export_btn = gr.Button(T["export"], variant="primary", interactive=False)
            result = gr.File(label=T["result"])
        with gr.Column(scale=2):
            status = gr.Markdown()
            table = gr.Dataframe(headers=T["columns"], datatype=["bool", "str", "str", "str"],
                                 interactive=True, label=T["table"])
            clip = gr.Audio(label=T["clip"], type="filepath", interactive=False)
    transcript = gr.HighlightedText(label=T["transcript"],
                                    color_map={"keiksmazodis": "red"}, show_legend=False,
                                    combine_adjacent=False)

    ui.change(set_ui_lang, [ui, table],
              [intro, ui, file, lang, model, analyze_btn, mode, export_btn, result, table, clip, transcript])
    analyze_btn.click(analyze, [file, lang, model, ui], [table, transcript, status, export_btn])
    table.select(preview, [file, table], clip)
    export_btn.click(export, [file, table, mode, ui], [result, status])

if __name__ == "__main__":
    demo.launch(inbrowser=True)
