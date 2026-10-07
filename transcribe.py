"""Transcribe student reflection videos (.mov, .mp4, ...) to text, locally.

Usage:
    .venv/bin/python transcribe.py [VIDEO_DIR] [--out transcripts] [--model large-v3-turbo]

Audio never leaves this machine: ffmpeg extracts the audio track and Whisper
transcribes it, using mlx-whisper on Apple Silicon Macs and faster-whisper
everywhere else (Windows, Intel Macs, Linux). Videos that already have a
transcript are skipped, so re-running only processes new uploads.
"""
import argparse
import platform
import subprocess
import sys
import tempfile
from pathlib import Path

VIDEO_EXTS = {".mov", ".mp4", ".m4v", ".mkv", ".webm", ".avi", ".m4a", ".mp3", ".wav"}
BACKEND = "mlx" if sys.platform == "darwin" and platform.machine() == "arm64" else "faster-whisper"
MODELS = {  # name -> model id per backend
    "large-v3-turbo": {"mlx": "mlx-community/whisper-large-v3-turbo", "faster-whisper": "large-v3-turbo"},  # default
    "small": {"mlx": "mlx-community/whisper-small-mlx", "faster-whisper": "small"},  # faster, less accurate
}
_faster_models = {}


def speech_to_text(wav: Path, model: str, backend: str = BACKEND) -> str:
    if backend == "mlx":
        import mlx_whisper
        return mlx_whisper.transcribe(str(wav), path_or_hf_repo=MODELS[model]["mlx"], language="en")["text"]
    from faster_whisper import WhisperModel
    if model not in _faster_models:
        # CPU + int8 works on any laptop; vad_filter skips silence, where Whisper tends to invent text.
        _faster_models[model] = WhisperModel(MODELS[model]["faster-whisper"], device="cpu", compute_type="int8")
    # Pass raw samples (ffmpeg already made 16 kHz mono) so faster-whisper doesn't need its own audio decoder.
    import wave
    import numpy as np
    with wave.open(str(wav)) as w:
        audio = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
    segments, _ = _faster_models[model].transcribe(audio, language="en", vad_filter=True)
    return " ".join(seg.text.strip() for seg in segments)


def extract_audio(video: Path, wav: Path) -> None:
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(video),
         "-vn", "-ac", "1", "-ar", "16000", str(wav)],
        check=True,
    )


def duration_seconds(video: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(video)],
        capture_output=True, text=True, check=True,
    )
    return float(out.stdout.strip())


def transcribe(video: Path, out_dir: Path, model: str, backend: str = BACKEND) -> Path:
    out = out_dir / f"{video.stem}.txt"
    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / "audio.wav"
        extract_audio(video, wav)
        text = speech_to_text(wav, model, backend).strip()
    minutes = duration_seconds(video) / 60
    out.write_text(
        f"# Source: {video.name}\n# Duration: {minutes:.1f} min\n# Words: {len(text.split())}\n\n{text}\n",
        encoding="utf-8",
    )
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video_dir", nargs="?", default=".", help="folder containing the videos")
    ap.add_argument("--out", default="transcripts", help="folder to write .txt transcripts")
    ap.add_argument("--model", default="large-v3-turbo", choices=MODELS)
    ap.add_argument("--backend", default=BACKEND, choices=["mlx", "faster-whisper"],
                    help=f"speech-to-text engine (default on this computer: {BACKEND})")
    ap.add_argument("--force", action="store_true", help="re-transcribe even if a transcript exists")
    args = ap.parse_args()

    video_dir, out_dir = Path(args.video_dir), Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    videos = sorted(p for p in video_dir.iterdir() if p.suffix.lower() in VIDEO_EXTS)
    if not videos:
        sys.exit(f"No videos found in {video_dir.resolve()}")

    for i, video in enumerate(videos, 1):
        if (out_dir / f"{video.stem}.txt").exists() and not args.force:
            print(f"[{i}/{len(videos)}] skip (already transcribed): {video.name}")
            continue
        print(f"[{i}/{len(videos)}] transcribing: {video.name}", flush=True)
        try:
            print(f"    -> {transcribe(video, out_dir, args.model, args.backend)}")
        except subprocess.CalledProcessError as e:
            print(f"    !! ffmpeg failed on {video.name}: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
