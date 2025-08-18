# YouTube Download Splitter (by George Tsakalos)

Download a YouTube video (or just its audio) and automatically split it into multiple files based on the video's YouTube timeline/chapters.

Powered by the [yt-dlp](https://github.com/yt-dlp/yt-dlp) Python API and FFmpeg.

---

## Features

- **Chapters-aware**: Detects YouTube chapters (timeline markers) and splits into separate files.
- **Video or Audio**: Choose to download the full video (muxed) or audio-only.
- **Format control**:
  - Video containers: `mp4`, `mkv`, `webm`
  - Audio formats: `mp3`, `m4a`, `flac`, `wav`, `opus`
- **Resolution cap** (video): pick *best*, 2160p, 1440p, 1080p, 720p, 480p, or 360p.
- **Audio bitrate** (audio-only): pick 128–320 kbps.
- **Clean filenames** with chapter numbers and titles.

> If a video has **no chapters**, the tool downloads a single file.

---

## Requirements

- **Python 3.8+**
- **FFmpeg** installed and available on your system PATH  
  - Windows: download from the official site (e.g., Gyan.dev), unzip, and add the `bin` folder to PATH  
  - macOS (Homebrew): `brew install ffmpeg`  
  - Ubuntu/Debian: `sudo apt install ffmpeg`
- Python packages:
  ```bash
  pip install -r requirements.txt
