# Model Assets

This directory stores MediaPipe model files required for pose detection.

## Required Models

### pose_landmarker.task

- **Source:** [MediaPipe Pose Landmarker (Lite)](https://ai.google.dev/edge/mediapipe/solutions/vision/pose_landmarker)
- **License:** Apache 2.0
- **Download:** Run `python scripts/download_models.py` from the project root

The model file is NOT committed to version control due to its size.
Run the download script after cloning the repository.

## Download Instructions

```bash
python scripts/download_models.py
```

This downloads `pose_landmarker_lite.task` (~4 MB) and saves it as
`assets/models/pose_landmarker.task`.
