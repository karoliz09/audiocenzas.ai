"""AudioCenzas.ai - mutes profanity in audio/video files.

Usage:
    python src/audiocenzas.py input.mp4 [-o output.mp4] [--mode mute|beep] [--lang lt]
"""
import argparse
import functools
import json
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

import os


def _add_cuda_dll_dirs():
    """Windows: lets CUDA DLLs be found from the nvidia-cublas-cu12 / nvidia-cudnn-cu12 pip packages."""
    if sys.platform != "win32":
        return
    nvidia = Path(sys.prefix) / "Lib" / "site-packages" / "nvidia"
    for bin_dir in nvidia.glob("*/bin"):
        os.add_dll_directory(str(bin_dir))
        os.environ["PATH"] = str(bin_dir) + os.pathsep + os.environ["PATH"]


_add_cuda_dll_dirs()

import numpy as np
from faster_whisper import WhisperModel

PAD = 0.15  # seconds of padding before and after a word (Whisper timestamps are off by ~0.1-0.3 s)


def normalize(word: str) -> str:
    word = unicodedata.normalize("NFKD", word.lower())
    word = "".join(c for c in word if not unicodedata.combining(c))
    return re.sub(r"[^\w*]", "", word)


def load_patterns(path: Path) -> list[re.Pattern]:
    """Each line is a word stem; '*' means any ending."""
    patterns = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        rx = re.escape(normalize(line)).replace(r"\*", r"\w*")
        patterns.append(re.compile(rf"^{rx}$"))
    return patterns


def cuda_available() -> bool:
    """GPU is used only if both a card and the CUDA libraries (cuBLAS, cuDNN) are present."""
    try:
        import ctranslate2
        if ctranslate2.get_cuda_device_count() == 0:
            return False
        if sys.platform == "win32":
            import ctypes
            ctypes.WinDLL("cublas64_12.dll")
            ctypes.WinDLL("cudnn_ops64_9.dll")
        return True
    except Exception:
        return False


def load_audio(media: Path, sr: int = 16000) -> np.ndarray:
    """Decodes audio via ffmpeg (without PyAV) to 16 kHz mono float32."""
    r = subprocess.run(
        ["ffmpeg", "-nostdin", "-v", "error", "-i", str(media),
         "-f", "s16le", "-ac", "1", "-ar", str(sr), "-"],
        capture_output=True, check=True)
    return np.frombuffer(r.stdout, np.int16).astype(np.float32) / 32768.0


@functools.cache
def device() -> str:
    return "cuda" if cuda_available() else "cpu"


def default_model() -> str:
    return "large-v3" if device() == "cuda" else "small"


@functools.lru_cache(maxsize=1)
def get_model(model_size: str) -> WhisperModel:
    """The model is loaded once and kept in memory."""
    print(f"Kraunamas modelis {model_size} ({device()})...")
    return WhisperModel(model_size, device=device(),
                        compute_type="float16" if device() == "cuda" else "int8")


def transcribe(media: Path, model_size: str, lang: str | None, progress=None):
    """Returns segments [(start, end, [(start, end, word), ...])].
    progress(fraction 0..1) is called after each recognized segment."""
    segments, info = get_model(model_size).transcribe(
        load_audio(media), language=lang, word_timestamps=True)
    print(f"Kalba: {info.language} ({info.language_probability:.0%})")
    out = []
    for seg in segments:
        if progress and info.duration:
            progress(min(seg.end / info.duration, 1.0))
        out.append((seg.start, seg.end, [(w.start, w.end, w.word.strip()) for w in seg.words or []]))
    return out


def all_words(segments):
    return [w for *_, words in segments for w in words]


def find_hits(words, patterns):
    return [(max(0.0, s - PAD), e + PAD, w) for s, e, w in words
            if any(p.match(normalize(w)) for p in patterns)]


def merge(intervals):
    out = []
    for s, e, *_ in sorted(intervals):
        if out and s <= out[-1][1]:
            out[-1][1] = max(out[-1][1], e)
        else:
            out.append([s, e])
    return out


def has_video(media: Path) -> bool:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v", "-show_entries",
         "stream=codec_type", "-of", "json", str(media)],
        capture_output=True, text=True, check=True)
    return bool(json.loads(r.stdout).get("streams"))


def censor(media: Path, out: Path, intervals, mode: str):
    enable = "+".join(f"between(t,{s:.3f},{e:.3f})" for s, e in intervals)
    if mode == "mute":
        graph = f"[0:a]volume=0:enable='{enable}'[aout]"
    else:
        graph = (f"[0:a]volume=0:enable='{enable}'[m];"
                 f"sine=f=1000:sample_rate=44100,volume=4:enable='{enable}',"
                 f"volume=0:enable='not({enable})'[b];"
                 f"[m][b]amix=inputs=2:duration=first:normalize=0[aout]")
    cmd = ["ffmpeg", "-y", "-i", str(media), "-filter_complex", graph, "-map", "[aout]"]
    if has_video(media):
        cmd += ["-map", "0:v", "-c:v", "copy"]
    cmd.append(str(out))
    subprocess.run(cmd, check=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", type=Path)
    ap.add_argument("-o", "--output", type=Path)
    ap.add_argument("--mode", choices=["mute", "beep"], default="mute")
    ap.add_argument("--lang", default=None, help="pvz. lt, en (tuscia = automatiskai)")
    ap.add_argument("--model", default=None, help="tiny/base/small/medium/large-v3 (tuscia = pagal GPU/CPU)")
    ap.add_argument("--words", type=Path, default=Path(__file__).resolve().parent.parent / "profanity.txt")
    args = ap.parse_args()

    out = args.output or args.input.with_stem(args.input.stem + "_cenzuruota")
    segments = transcribe(args.input, args.model or default_model(), args.lang)
    hits = find_hits(all_words(segments), load_patterns(args.words))
    if not hits:
        print("Keiksmazodziu nerasta.")
        return
    for s, e, w in hits:
        print(f"  {s:8.2f}-{e:8.2f}  {w}")
    censor(args.input, out, merge(hits), args.mode)
    print(f"Rasta {len(hits)}. Issaugota: {out}")


if __name__ == "__main__":
    sys.exit(main())
