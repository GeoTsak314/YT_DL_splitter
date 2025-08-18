# Youtube DL Splitter v1.0 by George Tsakalos

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Youtube DL Splitter v1.0 by George Tsakalos: 
Download a YouTube video (or just its audio) and automatically split it
into chapter files based on the video's YouTube timeline/chapters.

Requirements:
  - Python 3.8+
  - pip install -r requirements.txt
  - FFmpeg installed and available on PATH
"""

import os
import sys
import re
from pathlib import Path
from typing import Optional, Tuple

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
    """
    Present a numbered list of choices; return the value for the selected choice.
    `choices` can be a list of strings or list of (label, value) tuples.
    """
    normalized = []
    for c in choices:
        if isinstance(c, tuple):
            normalized.append(c)
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


def has_chapters(info: dict) -> bool:
    # yt-dlp sets 'chapters' to a list when chapters are available
    return bool(info.get("chapters"))


def sanitize_container(ext: str, for_video: bool) -> str:
    """
    Limit to common, robust containers.
    Video: mp4, mkv, webm
    Audio: mp3, m4a, flac, wav, opus
    """
    ext = ext.lower().strip(".")
    if for_video and ext in {"mp4", "mkv", "webm"}:
        return ext
    if not for_video and ext in {"mp3", "m4a", "flac", "wav", "opus"}:
        return ext
    raise ValueError("Unsupported format/container selected.")


def build_video_format_selector(max_height: Optional[int]) -> str:
    """
    Compose a yt-dlp format selector that prefers the best quality up to the chosen height,
    with audio, and falls back gracefully.
    """
    if max_height is None:  # 'best'
        return "bv*+ba/best"
    # Prefer video up to max_height with best audio. Fall back to anything <= height.
    return f"bv*[height<={max_height}]+ba/best[height<={max_height}]/best"


def parse_height(s: str) -> Optional[int]:
    if s.lower() == "best":
        return None
    if s.isdigit():
        return int(s)
    return None


# ------------------------- Main flow -------------------------

def main():
    print("\n=== YouTube Chapter Slicer ===\n")

    url = prompt_nonempty("Paste a YouTube video URL: ")

    # What to download?
    mode = prompt_choice(
        "\nWhat would you like to download?",
        [("Video (split into chapter files)", "video"),
         ("Audio only (split into chapter files)", "audio")]
    )

    if mode == "video":
        # Video container/format
        video_container = sanitize_container(
            prompt_choice(
                "\nSelect output video container/format:",
                [("MP4 (widely compatible)", "mp4"),
                 ("MKV (versatile container)", "mkv"),
                 ("WEBM (VP9/Opus friendly)", "webm")]
            ),
            for_video=True
        )
        # Resolution
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

        # Audio bitrate prompt is requested in the spec, but for video we generally
        # do NOT re-encode audio to a target bitrate (to preserve quality & speed).
        # We’ll still ask and simply ignore it for video, with a friendly note:
        _ = prompt_choice(
            "\nSelect preferred audio bitrate (applies to audio-only downloads; ignored for video):",
            [("128 kbps", "128"), ("160 kbps", "160"), ("192 kbps", "192"),
             ("256 kbps", "256"), ("320 kbps", "320")]
        )

        out_dir = ensure_output_dir(prompt_nonempty("\nDestination folder for the files: "))

        ydl_opts = {
            "paths": {"home": str(out_dir)},  # base directory
            # Each split file will use the 'section_*' fields:
            "outtmpl": {
                "default": "%(title)s/%(section_number)02d - %(section_title)s.%(ext)s"
            },
            "format": fmt_selector,
            "merge_output_format": video_container,  # control container after muxing
            "noplaylist": True,
            "ignoreerrors": False,
            "quiet": False,
            "no_warnings": False,
            "concurrent_fragment_downloads": 4,
            # Split per chapter if available
            "split_chapters": True,
            # Add metadata (keeps chapter data too)
            "postprocessors": [
                {"key": "FFmpegMetadata"}
            ],
        }

        # Run extraction
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if not has_chapters(info):
                print("\n⚠ No chapters found in this video. "
                      "The full file will be downloaded as a single file.\n")
                # Adjust template without section fields
                ydl.params["outtmpl"]["default"] = "%(title)s.%(ext)s"
                ydl.params["split_chapters"] = False
            ydl.download([url])

        print("\n✅ Done!")

    else:
        # Audio-only
        audio_container = sanitize_container(
            prompt_choice(
                "\nSelect output audio format:",
                [("MP3", "mp3"), ("M4A (AAC)", "m4a"), ("FLAC (lossless)", "flac"),
                 ("WAV (PCM)", "wav"), ("OPUS", "opus")]
            ),
            for_video=False
        )
        bitrate = prompt_choice(
            "\nSelect target audio bitrate (kbps):",
            [("128 kbps", "128"), ("160 kbps", "160"), ("192 kbps", "192"),
             ("256 kbps", "256"), ("320 kbps", "320")]
        )

        out_dir = ensure_output_dir(prompt_nonempty("\nDestination folder for the files: "))

        # For audio-only, pick bestaudio; let yt-dlp/ffmpeg extract and split chapters
        ydl_opts = {
            "paths": {"home": str(out_dir)},
            "outtmpl": {
                "default": "%(title)s/%(section_number)02d - %(section_title)s.%(ext)s"
            },
            "format": "bestaudio/best",
            "noplaylist": True,
            "ignoreerrors": False,
            "quiet": False,
            "no_warnings": False,
            "concurrent_fragment_downloads": 4,
            "split_chapters": True,
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": audio_container,
                    "preferredquality": bitrate,
                },
                {"key": "FFmpegMetadata"},
            ],
        }

        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if not has_chapters(info):
                print("\n⚠ No chapters found in this video. "
                      "The full audio will be downloaded as a single file.\n")
                # For single-file audio, remove section fields
                ydl.params["outtmpl"]["default"] = "%(title)s.%(ext)s"
                ydl.params["split_chapters"] = False
            ydl.download([url])

        print("\n✅ Done!")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nAborted by user.")
