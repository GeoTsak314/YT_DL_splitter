# Youtube DL Splitter v1.5 by George Tsakalos

#!/usr/bin/env python3
# -*- coding: utf-8 -*-



import os
import sys
import re
import json
import shutil
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any, Iterable, List, Tuple

try:
    from yt_dlp import YoutubeDL
except ImportError:
    print("Error: yt-dlp is not installed. Run: pip install -r requirements.txt")
    sys.exit(1)


# ------------------------- Helpers -------------------------

def prompt_nonempty(prompt_text: str) -> str:
    while True:
        s = input(prompt_text).strip()
        if s:
            return s
        print("Please enter a non-empty value.\n")


def prompt_choice(prompt_text: str, choices) -> str:
    normalized = []
    for c in choices:
        if isinstance(c, tuple):
            normalized.append((str(c[0]), str(c[1])))
        else:
            normalized.append((str(c), str(c)))
    print(prompt_text)
    for i, (label, _) in enumerate(normalized, start=1):
        print(f"  {i}) {label}")
    while True:
        sel = input("Select number: ").strip()
        if sel.isdigit():
            idx = int(sel) - 1
            if 0 <= idx < len(normalized):
                return normalized[idx][1]
        print("Invalid selection. Try again.\n")


def ensure_output_dir(path_str: str) -> Path:
    p = Path(path_str).expanduser().resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


def has_chapters(info: Dict[str, Any]) -> bool:
    return bool(info.get("chapters"))


def sanitize_container(ext: str, for_video: bool) -> str:
    ext = ext.lower().strip(".")
    if for_video and ext in {"mp4", "mkv", "webm"}:
        return ext
    if not for_video and ext in {"mp3", "m4a", "flac", "wav", "opus"}:
        return ext
    raise ValueError("Unsupported format/container selected.")


def build_video_format_selector(max_height: Optional[int]) -> str:
    if max_height is None:
        return "bv*+ba/best"
    return f"bv*[height<={max_height}]+ba/best[height<={max_height}]/best"


def parse_height(s: str) -> Optional[int]:
    if s.lower() == "best":
        return None
    if s.isdigit():
        return int(s)
    return None


# --- Duplicate filename prediction ---

_FORBIDDEN_RE = re.compile(r'[<>:"/\\|?*\x00-\x1F]')  # also strip control chars

def _sanitize_basename(name: str) -> str:
    s = (name or "").strip()
    s = _FORBIDDEN_RE.sub("_", s)
    s = re.sub(r"\s+", " ", s)
    s = s.strip(" .")
    if not s:
        s = "untitled"
    return s

def _has_duplicate_after_sanitize(titles: Iterable[str]) -> bool:
    seen = set()
    for t in titles:
        key = _sanitize_basename(t).casefold()
        if key in seen:
            return True
        seen.add(key)
    return False

def detect_duplicate_chapter_names(info: Dict[str, Any]) -> bool:
    chapters = info.get("chapters") or []
    titles = [c.get("title") or "" for c in chapters]
    return _has_duplicate_after_sanitize(titles)


# --- ffmpeg helpers ---

def _ensure_ffmpeg() -> None:
    for exe in ("ffmpeg", "ffprobe"):
        if shutil.which(exe) is None:
            raise RuntimeError(
                f"{exe} not found. Please install FFmpeg and ensure it's on PATH."
            )

def _ts(seconds: float) -> str:
    if seconds is None:
        return ""
    ms = int(round((seconds - int(seconds)) * 1000))
    s = int(seconds) % 60
    m = (int(seconds) // 60) % 60
    h = int(seconds) // 3600
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"

def _ffprobe_stream_codecs(src: Path) -> Tuple[Optional[str], Optional[str]]:
    """Return (vcodec, acodec) using ffprobe JSON; may return (None, codec) for audio-only files."""
    _ensure_ffmpeg()
    cmd = ["ffprobe", "-v", "error", "-show_streams", "-select_streams", "v:0,a:0", "-of", "json", str(src)]
    out = subprocess.check_output(cmd)
    data = json.loads(out.decode("utf-8", errors="ignore"))
    vcodec = acodec = None
    for st in data.get("streams", []):
        if st.get("codec_type") == "video" and vcodec is None:
            vcodec = st.get("codec_name")
        elif st.get("codec_type") == "audio" and acodec is None:
            acodec = st.get("codec_name")
    return vcodec, acodec

def _choose_container_for_copy(preferred: str, vcodec: Optional[str], acodec: Optional[str]) -> str:
    preferred = preferred.lower()
    if preferred == "mkv":
        return "mkv"
    if preferred == "mp4":
        if (vcodec in {"h264", "hevc", "av1", None}) and (acodec in {"aac", "mp3", "alac", None}):
            return "mp4"
        return "mkv"  # fallback
    if preferred == "webm":
        if (vcodec in {"vp8", "vp9", "av1", None}) and (acodec in {"opus", "vorbis", None}):
            return "webm"
        return "mkv"  # fallback
    return "mkv"

def split_audio_with_ffmpeg(
    src: Path,
    out_folder: Path,
    chapters: List[Dict[str, Any]],
    template_with_num: bool,
    out_ext: str,
    audio_codec: str,
    bitrate_kbps: Optional[str],
):
    _ensure_ffmpeg()
    out_folder.mkdir(parents=True, exist_ok=True)

    for idx, ch in enumerate(chapters, start=1):
        ch_title = ch.get("title") or f"Chapter {idx:02d}"
        safe_title = _sanitize_basename(ch_title)
        base_name = f"{idx:02d} - {safe_title}" if template_with_num else safe_title
        out_path = out_folder / f"{base_name}.{out_ext}"

        ss = ch.get("start_time")
        ee = ch.get("end_time")
        if ss is None:
            ss = 0.0

        cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(src)]
        cmd += ["-ss", _ts(ss)]
        if ee is not None:
            cmd += ["-to", _ts(ee)]
        cmd += ["-vn", "-map", "a", "-c:a", audio_codec]
        if bitrate_kbps and audio_codec not in {"flac", "pcm_s16le"}:
            cmd += ["-b:a", f"{bitrate_kbps}k"]
        cmd += [str(out_path)]

        try:
            subprocess.run(cmd, check=True)
            print(f"  ✔ {out_path.name}")
        except subprocess.CalledProcessError as e:
            print(f"  ✖ Failed: {out_path.name} ({e})")

def split_video_with_ffmpeg_copy(
    src: Path,
    out_folder: Path,
    chapters: List[Dict[str, Any]],
    template_with_num: bool,
    preferred_container: str,
):
    _ensure_ffmpeg()
    out_folder.mkdir(parents=True, exist_ok=True)
    vcodec, acodec = _ffprobe_stream_codecs(src)
    container = _choose_container_for_copy(preferred_container, vcodec, acodec)
    if container != preferred_container:
        print(f"ℹ Selected container '{preferred_container}' not compatible with streams ({vcodec}/{acodec}). Falling back to MKV copy.")

    for idx, ch in enumerate(chapters, start=1):
        ch_title = ch.get("title") or f"Chapter {idx:02d}"
        safe_title = _sanitize_basename(ch_title)
        base_name = f"{idx:02d} - {safe_title}" if template_with_num else safe_title
        out_path = out_folder / f"{base_name}.{container}"

        ss = ch.get("start_time")
        ee = ch.get("end_time")
        if ss is None:
            ss = 0.0

        cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(src)]
        cmd += ["-ss", _ts(ss)]
        if ee is not None:
            cmd += ["-to", _ts(ee)]
        # stream copy (no re-encode)
        cmd += ["-c", "copy"]
        cmd += [str(out_path)]

        try:
            subprocess.run(cmd, check=True)
            print(f"  ✔ {out_path.name}")
        except subprocess.CalledProcessError as e:
            print(f"  ✖ Failed: {out_path.name} ({e})")


# --- yt-dlp helpers ---

KNOWN_SOURCE_EXTS = [".webm", ".m4a", ".mp4", ".ogg", ".opus", ".mkv"]

def _find_existing_source_loose(title: str, out_dir: Path) -> Optional[Path]:
    """Loose scan for <sanitized title>.* in out_dir with known source extensions."""
    safe = _sanitize_basename(title)
    for ext in KNOWN_SOURCE_EXTS:
        p = out_dir / f"{safe}{ext}"
        if p.exists():
            return p
    # fallback: any file starting with safe title
    matches = list(out_dir.glob(f"{safe}*"))
    matches = [m for m in matches if m.is_file()]
    if matches:
        return max(matches, key=lambda p: p.stat().st_mtime)
    return None

def _resolve_downloaded_file_path(res: Dict[str, Any], ydl: YoutubeDL, out_dir: Path, title: str) -> Optional[Path]:
    # 1) requested_downloads entries contain 'filepath'
    for d in res.get("requested_downloads") or []:
        fp = d.get("filepath") or d.get("filename")
        if fp:
            p = Path(fp)
            if p.exists():
                return p
    # 2) direct keys
    for key in ("filepath", "_filename", "filename"):
        fp = res.get(key)
        if fp:
            p = Path(fp)
            if p.exists():
                return p
    # 3) prepare_filename
    try:
        fn = ydl.prepare_filename(res)
        p = Path(fn)
        if p.exists():
            return p
    except Exception:
        pass
    # 4) loose scan
    return _find_existing_source_loose(title, out_dir)


# ------------------------- Main flow -------------------------

def main():
    print("\n=== Youtube DL Splitter v1.5 ===\n")

    url = prompt_nonempty("Paste a YouTube video URL: ")

    mode = prompt_choice(
        "\nWhat would you like to download?",
        [("Video (split into chapter files)", "video"),
         ("Audio only (split into chapter files)", "audio")]
    )

    out_dir = ensure_output_dir(prompt_nonempty("\nDestination folder for the files: "))

    # Probe
    probe_opts = {"paths": {"home": str(out_dir)}, "quiet": True, "noplaylist": True}
    with YoutubeDL(probe_opts) as probe:
        try:
            info = probe.extract_info(url, download=False)
        except Exception as e:
            print(f"\nFailed to fetch video info: {e}")
            sys.exit(1)

    title = info.get("title") or "YouTube"
    chapters_available = has_chapters(info)
    dupes = detect_duplicate_chapter_names(info) if chapters_available else False

    if mode == "video":
        # --- VIDEO PATH: download once then ffmpeg split ---
        video_container = sanitize_container(
            prompt_choice(
                "\nSelect output video container/format:",
                [("MP4 (widely compatible)", "mp4"),
                 ("MKV (versatile container)", "mkv"),
                 ("WEBM (VP9/Opus friendly)", "webm")]
            ),
            for_video=True
        )
        res_choice = prompt_choice(
            "\nSelect maximum video resolution:",
            [("Best available", "best"),
             ("2160p (4K)", "2160"),
             ("1440p (2K)", "1440"),
             ("1080p", "1080"),
             ("720p", "720"),
             ("480p", "480"),
             ("360p", "360")]
        )
        max_height = parse_height(res_choice)
        fmt_selector = build_video_format_selector(max_height)

        _ = prompt_choice(
            "\nSelect preferred audio bitrate (applies to audio-only downloads; ignored for video):",
            [("128 kbps", "128"), ("160 kbps", "160"), ("192 kbps", "192"),
             ("256 kbps", "256"), ("320 kbps", "320")]
        )

        # Download or reuse source
        chapter_note = "→ Will split into chapter files." if chapters_available else "→ No chapters detected; will keep single file."
        print(chapter_note)

        ydl_opts_src = {
            "paths": {"home": str(out_dir)},
            "outtmpl": {"default": "%(title)s.%(ext)s"},
            "windowsfilenames": True,
            "trim_file_name": 180,
            "format": fmt_selector,
            "noplaylist": True,
            "ignoreerrors": False,
            "quiet": False,
            "no_warnings": False,
            "split_chapters": False,  # we split ourselves
            "merge_output_format": None,
        }

        with YoutubeDL(ydl_opts_src) as ydl:
            res = ydl.extract_info(url, download=True)
            src = _resolve_downloaded_file_path(res, ydl, out_dir, title)
            if not src or not Path(src).exists():
                print("✖ Could not find downloaded source video file.")
                sys.exit(1)

        out_folder = out_dir / _sanitize_basename(title)
        if chapters_available:
            split_video_with_ffmpeg_copy(
                src=src,
                out_folder=out_folder,
                chapters=info["chapters"],
                template_with_num=dupes,
                preferred_container=video_container,
            )
        else:
            # just move/remux single file to chosen container if needed
            _ensure_ffmpeg()
            vcodec, acodec = _ffprobe_stream_codecs(src)
            container = _choose_container_for_copy(video_container, vcodec, acodec)
            out_path = out_folder / f"{_sanitize_basename(title)}.{container}"
            out_folder.mkdir(parents=True, exist_ok=True)
            cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(src), "-c", "copy", str(out_path)]
            subprocess.run(cmd, check=True)
            print(f"  ✔ {out_path.name}")

        print("\n✅ Done!")
        return

    # --- AUDIO MODE: download once then ffmpeg split ---
    audio_container = sanitize_container(
        prompt_choice(
            "\nSelect output audio format:",
            [("MP3", "mp3"), ("M4A (AAC)", "m4a"), ("FLAC (lossless)", "flac"),
             ("WAV (PCM)", "wav"), ("OPUS", "opus")]
        ),
        for_video=False
    )

    bitrate = None
    if audio_container not in {"flac", "wav"}:
        bitrate = prompt_choice(
            "\nSelect target audio bitrate (kbps):",
            [("128 kbps", "128"), ("160 kbps", "160"), ("192 kbps", "192"),
             ("256 kbps", "256"), ("320 kbps", "320")]
        )
    else:
        print("ℹ FLAC/WAV are lossless; bitrate setting is not applicable.")

    if not chapters_available:
        print("\n⚠ No chapters found in this video. Will download and convert the full audio only.\n")

    ydl_opts_src = {
        "paths": {"home": str(out_dir)},
        "outtmpl": {"default": "%(title)s.%(ext)s"},
        "windowsfilenames": True,
        "trim_file_name": 180,
        "format": "bestaudio/best",
        "noplaylist": True,
        "ignoreerrors": False,
        "quiet": False,
        "no_warnings": False,
        "split_chapters": False,  # we split ourselves
    }
    with YoutubeDL(ydl_opts_src) as ydl:
        print("↓ Downloading source audio (or reusing existing)...")
        res = ydl.extract_info(url, download=True)
        src = _resolve_downloaded_file_path(res, ydl, out_dir, title)
        if not src or not Path(src).exists():
            print("✖ Could not find downloaded source file.")
            sys.exit(1)

    out_folder = out_dir / _sanitize_basename(title)
    if chapters_available:
        print("→ Splitting into chapter files with ffmpeg...")
        codec_map = {
            "flac": "flac",
            "wav": "pcm_s16le",
            "mp3": "libmp3lame",
            "m4a": "aac",
            "opus": "libopus",
        }
        ff_codec = codec_map[audio_container]
        split_audio_with_ffmpeg(
            src=src,
            out_folder=out_folder,
            chapters=info["chapters"],
            template_with_num=dupes,
            out_ext=audio_container,
            audio_codec=ff_codec,
            bitrate_kbps=bitrate,
        )
    else:
        # convert whole file to chosen audio format
        _ensure_ffmpeg()
        out_path = out_folder / f"{_sanitize_basename(title)}.{audio_container}"
        out_folder.mkdir(parents=True, exist_ok=True)
        codec_map = {
            "flac": "flac",
            "wav": "pcm_s16le",
            "mp3": "libmp3lame",
            "m4a": "aac",
            "opus": "libopus",
        }
        ff_codec = codec_map[audio_container]
        cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(src), "-vn", "-map", "a", "-c:a", ff_codec]
        if bitrate and ff_codec not in {"flac", "pcm_s16le"}:
            cmd += ["-b:a", f"{bitrate}k"]
        cmd += [str(out_path)]
        subprocess.run(cmd, check=True)
        print(f"  ✔ {out_path.name}")

    print("\n✅ Done!")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nAborted by user.")
