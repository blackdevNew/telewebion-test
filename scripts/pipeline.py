import os
import re
import json
import requests
import subprocess
from pathlib import Path

from moviepy import VideoFileClip
from pydub import AudioSegment


# ---------------- Configuration ----------------
PROGRAM_ID = os.getenv("PROGRAM_ID", "0x13a521a4")
TARGET_DATE = os.getenv("TARGET_DATE", "2026-08-05")  # YYYY-MM-DD

# این ثابت را طبق کدی که دادی گذاشتم. اگر می‌خواهی تغییر کند، از env بگیر.
DL_BASE_PREFIX = os.getenv(
    "DL_BASE_PREFIX",
    "https://dl.telewebion.ir/4eb161fd-c23e-4641-95d5-95dee456df55"
)

FIRST = int(os.getenv("FIRST", "24"))
OFFSET = int(os.getenv("OFFSET", "0"))

def download_file(url: str, filename: Path):
    print(f"Downloading {filename} ...")
    resp = requests.get(url, stream=True, timeout=60)
    resp.raise_for_status()
    filename.parent.mkdir(parents=True, exist_ok=True)

    with open(filename, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)

    print(f"Finished downloading {filename}")


def get_episodes_by_date():
    api_url = (
        "https://gateway.telewebion.ir/kandoo/program/getEpisodesByProgramDate/"
        f"?ProgramID={PROGRAM_ID}&First={FIRST}&Offset={OFFSET}"
        f"&FromDate={TARGET_DATE}T00:00:00&ToDate={TARGET_DATE}T23:59:59"
    )
    print("API URL:", api_url)
    resp = requests.get(api_url, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    print("url called")

    episodes = data.get("body", {}).get("queryProgram", [{}])[0].get("episodes", [])
    return episodes


def extract_audio_from_video(video_path: Path, output_audio_path: Path):
    print(f"Extracting audio from: {video_path}")
    video = VideoFileClip(str(video_path))
    # moviepy ممکن است خروجی mp3 را با codecهای مختلف بسازد؛ معمولاً با ffmpeg خوب است.
    video.audio.write_audiofile(str(output_audio_path))
    video.close()
    print(f"Saved audio: {output_audio_path}")


def split_mp3_to_chunks(input_mp3_path: Path, output_dir: Path, chunk_seconds: int = 30):
    output_dir.mkdir(parents=True, exist_ok=True)
    audio = AudioSegment.from_mp3(str(input_mp3_path))

    chunk_length_ms = chunk_seconds * 1000
    total_length_ms = len(audio)
    num_chunks = (total_length_ms + chunk_length_ms - 1) // chunk_length_ms

    print(f"Total length (ms): {total_length_ms}, chunks: {num_chunks}")

    for i in range(num_chunks):
        start_ms = i * chunk_length_ms
        end_ms = min((i + 1) * chunk_length_ms, total_length_ms)
        chunk = audio[start_ms:end_ms]

        out_file = output_dir / f"chunk_{i+1:03d}.mp3"
        chunk.export(str(out_file), format="mp3")
        print("Exported:", out_file)


def main():

    workdir = Path(os.getenv("WORKDIR", "work"))
    downloads_dir = workdir / "videos"
    output_dir = workdir / "chunks"
    workdir.mkdir(parents=True, exist_ok=True)
    print("directories ended")

    episodes = get_episodes_by_date()
    if not episodes:
        print("No episodes found.")
        return

    print(f"Found {len(episodes)} episodes. Starting download...")

    downloaded = []
    for ep in episodes:
        ep_id = ep["EpisodeID"]

        # با توجه به الگوی کدت در سوال:
        # https://dl.telewebion.ir/{image_uuid}/{ep_id}/480p/?coid={ep_id}&ql=480p
        dl_url = f"{DL_BASE_PREFIX}/{ep_id}/480p/?coid={ep_id}&ql=480p"
        filename = downloads_dir / f"{ep_id}_480p.mp4"

        try:
            print("download file:")
            download_file(dl_url, filename)
            downloaded.append(filename)
        except Exception as e:
            print(f"Failed to download {ep_id}: {e}")

    if not downloaded:
        print("No video files downloaded successfully.")
        return

    # برای اینکه دقیقاً مشابه کدت باشد: از اولین فایل دانلود شده استخراج کن
    input_video = downloaded[0]
    output_audio = workdir / "extracted_audio.mp3"
    print("extract audio")

    extract_audio_from_video(input_video, output_audio)

    # تکه‌کردن
    split_mp3_to_chunks(output_audio, output_dir, chunk_seconds=30)

    # لیست خروجی برای لاگ
    print("Chunk files:")
    for p in sorted(output_dir.glob("chunk_*.mp3")):
        print(" -", p)


if __name__ == "__main__":
    print("alllo...")
    main()
