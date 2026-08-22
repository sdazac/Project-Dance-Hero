"""Download MediaPipe pose landmarker model to assets/models/.

Usage:
    python scripts/download_models.py

Downloads the pose_landmarker_lite.task model from the official MediaPipe
release and saves it to assets/models/pose_landmarker.task.
"""

import sys
import urllib.request
from pathlib import Path

MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/"
    "pose_landmarker/pose_landmarker_lite/float16/latest/pose_landmarker_lite.task"
)
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "assets" / "models"
OUTPUT_FILE = OUTPUT_DIR / "pose_landmarker.task"


def download_model() -> None:
    """Download the MediaPipe pose landmarker model."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if OUTPUT_FILE.exists():
        print(f"Model already exists at: {OUTPUT_FILE}")
        return

    print(f"Downloading pose landmarker model from:\n  {MODEL_URL}")
    print(f"Saving to: {OUTPUT_FILE}")

    try:
        urllib.request.urlretrieve(MODEL_URL, OUTPUT_FILE)
        size_mb = OUTPUT_FILE.stat().st_size / (1024 * 1024)
        print(f"Download complete ({size_mb:.1f} MB)")
    except Exception as exc:
        print(f"Download failed: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    download_model()
