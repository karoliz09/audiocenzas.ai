# AudioCenzas.ai

Automatically finds and censors profanity in audio and video files. Speech is transcribed locally with [faster-whisper](https://github.com/SYSTRAN/faster-whisper), matched against a word list, and the hits are muted or beeped out with ffmpeg. Video is copied without re-encoding.

Built primarily for Lithuanian (plus common Russian-derived and English profanity), but any Whisper language works with your own word list.

## Features

- Web UI (Gradio): review detected words before exporting, untick false positives, add missed ones by hand
- Click a row to preview the clip (±1 s)
- Full transcript with highlighted hits
- `beep`, `mute` or `cut` mode (`cut` removes the fragment from audio and video; video is re-encoded, so it is slower)
- Runs fully offline; uses an NVIDIA GPU automatically if available, otherwise CPU
- Command-line mode for batch use

## Requirements

- Python 3.12+
- [ffmpeg](https://ffmpeg.org/) on `PATH`
- Optional: NVIDIA GPU (CUDA libraries are installed via pip)

## Installation

**Windows:** run `start.bat`. It installs ffmpeg (via winget) if missing, creates a virtual environment, installs dependencies and opens the app.

**Manual:**

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate    Linux/macOS: source .venv/bin/activate
pip install -r src/requirements.txt
python src/app.py
```

The Whisper model is downloaded on first use.

## Usage

### Web UI

```bash
python src/app.py
```

1. Upload a file, choose language and model.
2. Click **1. Analizuoti** and review the table.
3. Click **2. Eksportuoti**. The result is saved to `output/`.

### Command line

```bash
python src/audiocenzas.py input.mp4 [-o output.mp4] [--mode mute|beep|cut] [--lang lt] [--model small] [--words profanity.txt]
```

## Word list

`profanity.txt` contains one word stem per line:

- `*` matches any letters, e.g. `blyat*`
- diacritics are ignored (`sudas` matches `šūdas`)
- lines starting with `#` are comments

Be careful with short stems, which can produce false positives.

## Models

| Model | Speed | Accuracy |
|-------|-------|----------|
| `tiny`, `base` | fastest | low |
| `small` | default on CPU | medium |
| `medium` | slower | good |
| `large-v3` | default on GPU | best |

## Limitations

- Whisper sometimes softens or misspells profanity, or writes it in Cyrillic, so some words may be missed. Always review the table before exporting.
- Word timestamps are approximate; each hit is padded by 0.15 s on both sides.
- Only the first audio track is kept in the output.

## License

[MIT](LICENSE) - free to use, modify and distribute.
