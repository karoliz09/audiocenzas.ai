"""AudioCenzas.ai - web interface. Run: python app.py"""
import subprocess
import tempfile
import html
import json
import time
from pathlib import Path

import gradio as gr
import pandas as pd

from audiocenzas import PAD, all_words, censor, default_model, find_hits, load_patterns, transcribe

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
        "mode": "Default action",
        "actions": {"beep": "🔔 Beep", "mute": "🔇 Mute", "cut": "✂️ Cut out", "skip": "⏭️ Skip"},
        "set_all": "Set all to:",
        "hints": {"beep": "a beep plays over the word", "mute": "the word is silenced",
                  "cut": "the fragment is cut out of audio and video", "skip": "the word is left as is"},
        "hint_change": "Click to change the action.",
        "hint_add": "Click to mark this word for censoring.",
        "export": "2. Export",
        "result": "Result",
        "columns": ["Action", "Start", "End", "Word"],
        "table": "Detected words - click the action to change it, any other cell to listen",
        "clip": "Clip (+-1 s)",
        "transcript": "Full transcript - click a word to change its action (or to add a missed one)",
        "no_file": "Please upload a file.",
        "loading": "Loading model...",
        "transcribing": "Transcribing speech...",
        "found": ("Profanity found: **{n}**. Click a word's action to change it "
                  "(⏭️ Skip for false positives), add a row for missed words, then click **Export**."),
        "nothing_selected": "No words selected.",
        "rendering": "Creating censored file...",
        "done": "Censored spots: **{n}**. File is ready.",
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
        "mode": "Numatytasis veiksmas",
        "actions": {"beep": "🔔 Pyptelėti", "mute": "🔇 Nutildyti", "cut": "✂️ Iškirpti", "skip": "⏭️ Praleisti"},
        "set_all": "Visiems:",
        "hints": {"beep": "vietoje žodžio skambės pyptelėjimas", "mute": "žodis bus nutildytas",
                  "cut": "fragmentas bus iškirptas iš garso ir vaizdo", "skip": "žodis paliekamas nepakeistas"},
        "hint_change": "Paspauskite, kad pakeistumėte veiksmą.",
        "hint_add": "Paspauskite, kad pažymėtumėte šį žodį cenzūrai.",
        "export": "2. Eksportuoti",
        "result": "Rezultatas",
        "columns": ["Veiksmas", "Pradžia", "Pabaiga", "Žodis"],
        "table": "Rasti žodžiai - paspauskite veiksmą, kad jį pakeistumėte, kitą langelį - perklausysite",
        "clip": "Fragmentas (+-1 s)",
        "transcript": "Visas transkriptas - paspauskite žodį, kad pakeistumėte veiksmą (arba pridėtumėte praleistą)",
        "no_file": "Įkelkite failą.",
        "loading": "Kraunamas modelis...",
        "transcribing": "Atpažįstama kalba...",
        "found": ("Rasta keiksmažodžių: **{n}**. Paspauskite žodžio veiksmą, kad jį pakeistumėte "
                  "(klaidingiems - ⏭️ Praleisti), pridėkite eilutę praleistiems, tada spauskite **Eksportuoti**."),
        "nothing_selected": "Nepažymėtas nė vienas žodis.",
        "rendering": "Kuriamas cenzūruotas failas...",
        "done": "Cenzūruota vietų: **{n}**. Failas paruoštas.",
        "elapsed": "Analizė užtruko **{t}**.",
    },
}
DEFAULT_UI = "lt"
ACTIONS = ["beep", "mute", "cut", "skip"]
ICONS = {"beep": "🔔", "mute": "🔇", "cut": "✂️", "skip": "⏭️"}
ICON_COLORS = {"🔔": "#f59e0b", "🔇": "#ef4444", "✂️": "#8b5cf6", "⏭️": "#9ca3af"}


def parse_action(value, default="beep"):
    """Action label in any UI language (or its code) -> code; empty -> default."""
    v = str(value).strip().lower()
    if v in ("", "nan", "none"):
        return default
    for lang in TEXT.values():
        for code, label in lang["actions"].items():
            if v in (code, label.lower()):
                return code
    return default


def action_choices(T, with_skip=True):
    return [(T["actions"][a], a) for a in ACTIONS if with_skip or a != "skip"]


def table_frame(data, T):
    return pd.DataFrame(data, columns=T["columns"])


def rows(table):
    """Table rows as lists, independent of the (translated) column headers."""
    if table is None:
        return []
    return pd.DataFrame(table).values.tolist()


def analyze(file, lang, model, mode, ui, progress=gr.Progress()):
    T = TEXT[ui]
    if not file:
        raise gr.Error(T["no_file"])
    started = time.monotonic()
    progress(0, desc=T["loading"])
    segments = transcribe(Path(file), model, lang or None,
                          progress=lambda p: progress(p, desc=T["transcribing"]))
    hits = find_hits(all_words(segments), load_patterns(WORDS))
    table = table_frame([[T["actions"][mode], to_hms(s), to_hms(e), w] for s, e, w in hits], T)
    segs = [[seg_start, [list(w) for w in words]] for seg_start, _, words in segments]
    elapsed = T["elapsed"].format(t=format_duration(time.monotonic() - started))
    status = f'{elapsed} {T["found"].format(n=len(hits))}'
    return table, segs, status, gr.update(interactive=True)


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


def word_key(s, e, w):
    """Table row key (start, word) of a transcript word, matching find_hits' padding."""
    return to_hms(max(0.0, s - PAD)), w


def transcript_tokens(segs):
    """[(text, word|None)] - one line per segment; word is (start, end, text) for clickable words."""
    out = []
    for seg_start, words in segs:
        out.append((f"[{to_hms(seg_start, decimals=False)}]  ", None))
        for s, e, w in words:
            out += [(w, (s, e, w)), (" ", None)]
        out.append(("\n", None))
    return out


def build_transcript(segs, table, mode):
    """HighlightedText value: words in the table are tagged with their action icon."""
    actions = {(r[1], r[3]): parse_action(r[0], mode) for r in rows(table)}
    out = []
    for text, word in transcript_tokens(segs or []):
        action = actions.get(word_key(*word)) if word else None
        out.append((text, ICONS[action] if action else None))
    return out


def transcript_legend(T):
    """Visible legend under the transcript; also carries the hover hints for HINTS_JS."""
    icons = {ICONS[a]: f'{T["actions"][a]} - {T["hints"][a]}.' for a in ACTIONS}
    data = html.escape(json.dumps({"icons": icons, "change": T["hint_change"], "add": T["hint_add"]}))
    items = " &nbsp;·&nbsp; ".join(
        f'<span style="color:{ICON_COLORS[ICONS[a]]}" title="{html.escape(T["hints"][a])}">'
        f'{html.escape(T["actions"][a])}</span>' for a in ACTIONS)
    return f'<div id="ac-hints" data-hints="{data}" style="font-size:0.9em">{items}</div>'


# Adds hover hints (title) to transcript words; hint texts come from the legend's data-hints.
HINTS_JS = """
() => {
  const apply = () => {
    const box = document.getElementById('ac-hints');
    if (!box) return;
    const hints = JSON.parse(box.dataset.hints);
    document.querySelectorAll('#transcript .token-container').forEach(el => {
      const text = el.textContent.trim();
      if (!text || text.startsWith('[')) return;  // spaces, line breaks, timestamps
      const icon = Object.keys(hints.icons).find(i => text.includes(i));
      const title = icon ? hints.icons[icon] + ' ' + hints.change : hints.add;
      if (el.title !== title) el.title = title;
    });
  };
  new MutationObserver(apply).observe(document.body, {childList: true, subtree: true, characterData: true});
}
"""


def on_word_click(segs, table, mode, ui, evt: gr.SelectData):
    """Word in the table: switch to the next action. Other word: add it with the default action."""
    tokens = transcript_tokens(segs or [])
    if not 0 <= evt.index < len(tokens) or tokens[evt.index][1] is None:
        return gr.update()
    T = TEXT[ui]
    s, e, w = tokens[evt.index][1]
    start, _ = word_key(s, e, w)
    data = rows(table)
    for r in data:
        if (r[1], r[3]) == (start, w):
            current = ACTIONS.index(parse_action(r[0], mode))
            r[0] = T["actions"][ACTIONS[(current + 1) % len(ACTIONS)]]
            break
    else:
        data.append([T["actions"][mode], start, to_hms(e + PAD), w])
        data.sort(key=lambda r: sort_key(r[1]))
    return table_frame(data, T)


def sort_key(value):
    try:
        return from_hms(value)
    except (TypeError, ValueError):
        return float("inf")


def intervals_by_action(table, default):
    """{"beep"|"mute"|"cut": [(start, end), ...]}; skipped and malformed rows are ignored."""
    out = {a: [] for a in ACTIONS if a != "skip"}
    for r in rows(table):
        try:
            s, e = from_hms(r[1]), from_hms(r[2])
        except (TypeError, ValueError):
            continue  # empty or malformed row
        action = parse_action(r[0], default)
        if action in out and e > s:
            out[action].append((s, e))
    return out


def set_all(table, action, ui):
    T = TEXT[ui]
    return table_frame([[T["actions"][action], *r[1:]] for r in rows(table)], T)


def on_cell_click(file, table, mode, ui, evt: gr.SelectData):
    """Action cell: switch to the next action. Any other cell: play the word."""
    row, col = evt.index
    data = rows(table)
    if not 0 <= row < len(data):
        return gr.update(), gr.update()
    if col == 0:
        T = TEXT[ui]
        current = ACTIONS.index(parse_action(data[row][0], mode))
        data[row][0] = T["actions"][ACTIONS[(current + 1) % len(ACTIONS)]]
        return table_frame(data, T), gr.update()
    return gr.update(), preview(file, data[row])


def preview(file, row):
    """Cuts a clip (+-1 s) around one word for listening."""
    if not file:
        return None
    try:
        s, e = from_hms(row[1]), from_hms(row[2])
    except (TypeError, ValueError):
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
    actions = intervals_by_action(table, mode)
    count = sum(map(len, actions.values()))
    if not count:
        raise gr.Error(T["nothing_selected"])
    src = Path(file)
    OUT_DIR.mkdir(exist_ok=True)
    out = OUT_DIR / f"{src.stem}_cenzuruota{src.suffix}"
    progress(0.5, desc=T["rendering"])
    censor(src, out, actions)
    return str(out), T["done"].format(n=count)


def set_ui_lang(ui, table):
    """Re-labels every component; keeps the table contents under translated headers."""
    T = TEXT[ui]
    data = table_frame([[T["actions"].get(parse_action(r[0], None), r[0]), *r[1:]] for r in rows(table)], T)
    return (gr.update(value=T["intro"]), gr.update(label=T["ui_lang"]),
            gr.update(label=T["file"]), gr.update(label=T["lang"], choices=T["lang_choices"]),
            gr.update(label=T["model"]), gr.update(value=T["analyze"]),
            gr.update(label=T["mode"], choices=action_choices(T, with_skip=False)),
            gr.update(value=T["export"]),
            gr.update(label=T["result"]), gr.update(value=data, label=T["table"]),
            gr.update(label=T["clip"]), gr.update(label=T["transcript"]), gr.update(value=T["set_all"]),
            gr.update(value=transcript_legend(T)),
            *(gr.update(value=T["actions"][a]) for a in ACTIONS))


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
            mode = gr.Radio(action_choices(T, with_skip=False), value="beep", label=T["mode"])
            analyze_btn = gr.Button(T["analyze"], variant="primary")
            export_btn = gr.Button(T["export"], variant="primary", interactive=False)
            result = gr.File(label=T["result"])
        with gr.Column(scale=2):
            status = gr.Markdown()
            table = gr.Dataframe(headers=T["columns"], datatype="str", interactive=True,
                                 static_columns=[0], column_widths=["24%", "20%", "20%", "36%"],
                                 max_height=420, label=T["table"])
            with gr.Row(equal_height=True):
                set_all_label = gr.Markdown(T["set_all"])
                set_all_btns = {a: gr.Button(T["actions"][a], size="sm", min_width=90) for a in ACTIONS}
            clip = gr.Audio(label=T["clip"], type="filepath", interactive=False)
    segs = gr.State([])  # [[segment_start, [[start, end, word], ...]], ...]
    transcript = gr.HighlightedText(label=T["transcript"], color_map=ICON_COLORS, show_legend=False,
                                    combine_adjacent=False, elem_id="transcript")
    legend = gr.HTML(transcript_legend(T))

    ui.change(set_ui_lang, [ui, table],
              [intro, ui, file, lang, model, analyze_btn, mode, export_btn, result, table, clip, transcript,
               set_all_label, legend, *set_all_btns.values()])
    analyze_btn.click(analyze, [file, lang, model, mode, ui], [table, segs, status, export_btn])
    table.change(build_transcript, [segs, table, mode], transcript)
    transcript.select(on_word_click, [segs, table, mode, ui], table)
    table.select(on_cell_click, [file, table, mode, ui], [table, clip])
    for a, btn in set_all_btns.items():
        btn.click(set_all, [table, gr.State(a), ui], table)
    export_btn.click(export, [file, table, mode, ui], [result, status])

if __name__ == "__main__":
    demo.launch(inbrowser=True, js=HINTS_JS)
