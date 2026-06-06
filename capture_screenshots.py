import argparse
import subprocess
from pathlib import Path

from app import DEFAULT_SOURCE, resolve_video_stream


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Capture evenly spaced screenshots from a video stream."
    )
    parser.add_argument("--source", default=DEFAULT_SOURCE)
    parser.add_argument("--output-dir", default="screenshots")
    parser.add_argument("--count", type=int, default=200)
    parser.add_argument("--interval-seconds", type=float, default=0.25)
    parser.add_argument("--cookies-from-browser", default="chrome")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    existing_count = len(list(output_dir.glob("screenshot_*.jpg")))
    remaining_count = args.count - existing_count
    if remaining_count <= 0:
        print(f"[OK] {existing_count} screenshots already exist in {output_dir.resolve()}")
        return

    stream_url = resolve_video_stream(args.source, args.cookies_from_browser)
    output_pattern = str(output_dir / "screenshot_%03d.jpg")
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        stream_url,
        "-vf",
        f"fps=1/{args.interval_seconds}",
        "-frames:v",
        str(remaining_count),
        "-start_number",
        str(existing_count + 1),
        "-q:v",
        "2",
        output_pattern,
    ]

    print(f"[INFO] Capturing {remaining_count} screenshots with FFmpeg.")
    subprocess.run(command, check=True)

    saved_count = len(list(output_dir.glob("screenshot_*.jpg")))
    print(f"[OK] Saved {saved_count} screenshots to {output_dir.resolve()}")


if __name__ == "__main__":
    main()
