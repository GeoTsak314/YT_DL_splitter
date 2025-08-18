
# YouTube Download Splitter v1.5 (by George Tsakalos)

Download a YouTube video (or just its audio) and automatically split it into multiple files based on the video’s YouTube timeline/chapters.

Powered by the [yt-dlp](https://github.com/yt-dlp/yt-dlp) Python API and FFmpeg.

---

## Features

- **Chapters-aware**: Detects YouTube chapters and splits into separate files.
- **Video or Audio**: Choose to download the full video or just the audio.
- **Format control**:
  - Video: `mp4`, `mkv`, `webm`
  - Audio: `mp3`, `m4a`, `flac`, `wav`, `opus`
- **Resolution cap** (video): *best*, 2160p, 1440p, 1080p, 720p, 480p, 360p.
- **Audio bitrate**: choose 128–320 kbps for MP3/AAC/Opus.  
  - **FLAC/WAV** are lossless → **no bitrate prompt**.
- **Duplicate-safe naming**: if chapter titles collide, names become `NN - <Chapter Title>`.
- **Skip re-download**: if `<Video Title>.<ext>` already exists, splitting starts immediately (saves time).
- **Unified ffmpeg splitting**: both audio & video use the same reliable download-once → split pipeline.  

> If a video has **no chapters**, the tool outputs a single file.

---

## Requirements

- **Python 3.8+**
- **FFmpeg** installed and on your PATH
- Python packages:
  ```bash
  pip install -r requirements.txt
  ```

---

## How to install / fix FFmpeg on Windows

1. **Download FFmpeg build**  
   - Go to: [https://www.gyan.dev/ffmpeg/builds/](https://www.gyan.dev/ffmpeg/builds/)  
   - Download the latest **“release full”** zip.

2. **Extract it**  
   - Extract somewhere like: `C:\ffmpeg\`  
   - Inside you should see a `bin` folder with `ffmpeg.exe`, `ffprobe.exe`, and `ffplay.exe`.

3. **Add FFmpeg to PATH**  
   - Press **Win + R**, type `sysdm.cpl`, go to *Advanced → Environment Variables*.  
   - Under *System variables*, select **Path**, click *Edit*, and add:  
     ```
     C:\ffmpeg\bin
     ```
   - Click OK on everything.

4. **Verify installation**  
   Open a new Command Prompt and type:
   ```cmd
   ffmpeg -version
   ffprobe -version
   ```
   Both should print version info.

---

## Usage

Run the script and follow the prompts:

```bash
python yt_dl_splitter.py
```

1. Paste a YouTube video URL.  
2. Select **Video** or **Audio**.  
3. Pick format (`mp4`, `mkv`, `webm` for video; `mp3`, `m4a`, `flac`, `wav`, `opus` for audio).  
   - If `flac` or `wav` is selected, bitrate is skipped.  
4. (Video) choose max resolution.  
   (Audio) choose bitrate if applicable.  
5. Pick destination folder.  
6. Wait — ffmpeg will split into:

```
<Destination>/<Video Title>/<Chapter Title>.ext
```

If duplicate names would occur:

```
<Destination>/<Video Title>/01 - Intro.ext
<Destination>/<Video Title>/02 - Intro.ext
```

If no chapters are present:

```
<Destination>/<Video Title>.ext
```

---

## Notes

- **Accuracy**: Cuts are made with `-ss/-to` after input for precise chapter edges.  
- **Compatibility**: For video, if your chosen container doesn’t support the downloaded codecs, the script falls back to MKV and stream-copies without re-encoding.  
- **Skip-download**: Works for both video and audio — saves time if the source file already exists.

---

## License

MIT
