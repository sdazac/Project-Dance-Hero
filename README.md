# 🕺 Project ModDance Hero

**Open-source dance analysis and rhythm-game scoring powered by real-time pose detection.**

ModDance Hero captures your movement through a webcam or analyzes reference dance videos, detects body landmarks using AI, and provides frame-by-frame scoring based on pose similarity, joint angles, motion dynamics, and timing precision.

Whether you're learning choreography from a tutorial, practicing a routine from your favorite rhythm game, or just having fun matching moves from any dance video — ModDance Hero gives you measurable, explainable feedback on how well you're doing.

---

## Features

- **Real-time webcam pose detection** — see your skeleton overlaid on your camera feed
- **Reference video analysis** — import any dance video and extract the full movement sequence
- **33-landmark body tracking** — head, shoulders, elbows, wrists, hips, knees, ankles, feet
- **Multi-person detection** — tracks up to 5 people, locks onto your selected dancer
- **Persistent subject tracking** — follows the same person through crossings and occlusions
- **Scoring pipeline** — pose similarity, angle comparison, motion dynamics, timing alignment
- **Event ratings** — PERFECT, GREAT, OK, MEH, MISS based on configurable thresholds
- **Structured feedback** — tells you *which* body part is off and by how much
- **Local processing** — all analysis happens on your machine, no cloud required
- **Configurable** — thresholds, weights, analysis FPS, all adjustable via TOML

## Current Status

| Component | Status |
|-----------|--------|
| Camera & Pose Detection | ✅ Complete |
| Pose Normalization & Motion | ✅ Complete |
| Scoring Pipeline | ✅ Complete |
| Multi-Person Subject Tracking | ✅ Complete |
| Practice Mode UI | 🔲 Phase 4 |
| Arcade Mode | 🔲 Future |

---

## Quick Start

### Prerequisites

- **Python 3.10+** (tested on 3.10, 3.11, 3.12)
- **Windows 10/11** (primary target; Linux/macOS supported where practical)
- A webcam (for live detection)

### Installation

```bash
# Clone the repository
git clone https://github.com/sdazac/Project-Dance-Hero.git
cd Project-Dance-Hero

# Create virtual environment
python -m venv .venv

# Activate it
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

# Install with development tools
pip install -e ".[dev]"

# Download the MediaPipe pose model (~5.5 MB)
python scripts/download_models.py
```

### Verify Installation

```bash
python -c "import opendance; print('ModDance Hero ready!')"
pytest tests/ -q
```

---

## Usage

### 🎥 Live Camera with Landmarks

Open your webcam and see real-time pose detection with skeleton overlay:

```bash
python scripts/camera_diagnostic.py
```

Shows: live feed, detected skeleton, FPS, landmark count, body scale, detection status.

Press `q` or `ESC` to exit.

---

### 📹 Analyze a Dance Video

Process any local dance video through the full analysis pipeline:

```bash
python scripts/video_analysis_diagnostic.py path/to/your/video.mp4
```

Reports: resolution, FPS, detection rate, normalized poses, joint angles, motion features, and validates the analysis cache.

Add `--preview` to replay the video with skeleton overlay:

```bash
python scripts/video_analysis_diagnostic.py path/to/video.mp4 --preview
```

---

### 🦴 Landmark Replay

Replay an analyzed video with full landmark visualization, joint angles, and motion vectors:

```bash
# Basic replay
python scripts/landmark_replay.py path/to/video.mp4

# With joint angles displayed
python scripts/landmark_replay.py path/to/video.mp4 --angles

# With motion vectors
python scripts/landmark_replay.py path/to/video.mp4 --motion

# With normalized body-relative view
python scripts/landmark_replay.py path/to/video.mp4 --normalized

# Save as video file
python scripts/landmark_replay.py path/to/video.mp4 --angles --save output.mp4
```

**Controls:** `SPACE`=pause, `q`/`ESC`=exit, `←`/`→`=step frame, `1`=1x, `2`=2x, `5`=0.5x

---

### 👥 Multi-Person Subject Tracking

Analyze videos with multiple dancers. The system locks onto a selected person and maintains identity through crossings and occlusions:

```bash
# Basic multi-person analysis
python scripts/multi_person_diagnostic.py path/to/video.mp4

# Visual preview with all candidates highlighted
python scripts/multi_person_diagnostic.py path/to/video.mp4 --preview

# Configure max detected people
python scripts/multi_person_diagnostic.py path/to/video.mp4 --max-poses 5
```

---

### 🎯 Subject Tracking Validation

Visual validation tool showing persistent identity tracking with bounding boxes, trails, and confidence scores:

```bash
python scripts/subject_tracking_replay.py path/to/video.mp4

# Save the tracking replay
python scripts/subject_tracking_replay.py path/to/video.mp4 --save tracking.mp4
```

**Controls:** `SPACE`=pause, `←`/`→`=step, `TAB`=toggle candidates, `T`=trail, `I`=info, `q`=exit

**Colors:** GREEN=tracked subject, YELLOW=occluded, RED=lost, OTHER COLORS=other candidates

---

### ⚡ Performance Benchmark

Measure analysis speed at different sampling rates:

```bash
python scripts/performance_diagnostic.py path/to/video.mp4
python scripts/performance_diagnostic.py path/to/video.mp4 --fps 10 15 20 30
```

---

## How It Works

```
Reference Video                          Camera (Live)
     │                                        │
     ▼                                        ▼
 Frame Extraction                        Frame Capture
     │                                        │
     ▼                                        ▼
 Pose Detection (MediaPipe 33 landmarks)
     │                                        │
     ▼                                        ▼
 Pose Normalization (body-relative coords)
     │                                        │
     ▼                                        ▼
 Motion Features (velocity, angles, direction)
     │                                        │
     ▼                                        ▼
 ┌───────────────────────────────────────────────┐
 │           Temporal Alignment                  │
 │     Reference Motion + User Motion            │
 │              ▼                                │
 │     Pose Score (2D Euclidean)                 │
 │     Angle Score (circular difference)         │
 │     Motion Score (speed + direction)          │
 │     Timing Score (phase alignment)            │
 │              ▼                                │
 │     Weighted Aggregation                      │
 │              ▼                                │
 │     Event Rating (PERFECT/GREAT/OK/MEH/MISS) │
 │              ▼                                │
 │     Structured Feedback                       │
 └───────────────────────────────────────────────┘
```

---

## Scoring System

### Event Ratings

| Rating | Accuracy Range | Description |
|--------|---------------|-------------|
| PERFECT | 90%–100% | Body closely matches the reference |
| GREAT | 75%–89.99% | Strong movement with moderate differences |
| OK | 50%–74.99% | Intended movement recognized, significant differences |
| MEH | 30%–49.99% | Approximately correct timing, pose differs substantially |
| MISS | Below 30% | Movement substantially different or not detected |

### Scoring Weights (configurable)

| Dimension | Default Weight |
|-----------|---------------|
| Pose similarity | 40% |
| Joint-angle similarity | 25% |
| Motion similarity | 20% |
| Timing similarity | 15% |

---

## Configuration

ModDance Hero uses TOML configuration with sensible defaults. Override any setting in your user config:

- **Windows:** `%APPDATA%\opendance\config.toml`
- **Linux/macOS:** `~/.config/opendance/config.toml`

Key settings:

```toml
[reference]
sample_fps = 15.0    # Analysis sampling rate (10/15/20/30)

[pose]
max_poses = 1        # Max people to detect (1-5)

[scoring.thresholds]
perfect_min = 90.0
great_min = 75.0
ok_min = 50.0
meh_min = 30.0

[scoring.weights]
pose_similarity = 0.40
angle_similarity = 0.25
motion_similarity = 0.20
timing_similarity = 0.15
```

---

## Development

### Running Tests

```bash
# All tests
pytest tests/

# Quick summary
pytest tests/ -q

# With coverage
pytest --cov=opendance --cov-report=term-missing
```

### Code Quality

```bash
# Linting
ruff check src/ tests/ scripts/

# Type checking
mypy src/

# Both
ruff check src/ tests/ scripts/ && mypy src/
```

### Project Structure

```
src/opendance/
├── app/          Entry point
├── camera/       Webcam capture, FPS monitoring
├── pose/         MediaPipe detection, multi-person tracking
├── motion/       Normalization, angles, velocity, features
├── video/        Reference analysis, cache
├── scoring/      Comparison, aggregation, rating, feedback
├── ui/           PySide6 widgets, skeleton renderer
└── config/       TOML loader, dataclass models

scripts/          Diagnostic and utility tools
tests/            Unit and integration tests
```

---

## Known Limitations

- **Finger tracking:** The 33-landmark Pose model does NOT track individual finger joints. Detailed hand choreography would require MediaPipe Hands (21 landmarks per hand) as a future enhancement.
- **Animated characters:** MediaPipe is trained on real humans. Detection of animated/3D characters (MMD, etc.) may be reduced compared to real footage.
- **CPU performance:** Pose inference runs at ~60ms/frame on CPU. The default 15 FPS analysis rate balances quality and speed. GPU acceleration is planned for future versions.
- **Body rotation:** When a person faces completely away from the camera, landmark detection degrades. The system handles this gracefully (OCCLUDED/LOST state).

---

## Contributing

ModDance Hero is open-source and welcomes contributions. Whether it's bug fixes, new features, documentation improvements, or just ideas — all help is appreciated.

1. Fork the repository
2. Create a feature branch: `git checkout -b feat/my-feature`
3. Make your changes and add tests
4. Verify: `ruff check . && mypy src/ && pytest`
5. Submit a Pull Request

Please read the development guidelines in `AGENTS.md` and `.kiro/steering/` before contributing.

---

## Support the Project

ModDance Hero is free and open-source. If you find it useful and want to support continued development:

☕ **[Buy me a coffee](https://buymeacoffee.com/)** — every contribution helps keep the project alive

⭐ **Star this repository** — helps others discover the project

🐛 **Report issues** — helps improve quality for everyone

📢 **Share it** — tell your dance community about ModDance Hero

---

## Roadmap

- [x] Phase 0 — Project foundation, configuration, CI/CD
- [x] Phase 1 — Camera capture, pose detection, skeleton overlay
- [x] Phase 2 — Pose normalization, joint angles, motion features
- [x] Phase 3 — Scoring pipeline (comparison, aggregation, rating, feedback)
- [x] Phase 3.5 — Multi-person tracking, performance optimization
- [ ] Phase 4 — Practice Mode UI, combo tracking, final grading
- [ ] Phase 5 — Arcade Mode, session history, analytics dashboard
- [ ] Future — Beat detection, GPU acceleration, mobile support

---

## License

Released under the [MIT License](LICENSE). Free to use, modify, and distribute.

---

## Privacy

- All processing happens locally on your device
- Camera frames are never uploaded or stored
- Reference videos remain on your filesystem
- No internet connection required for core functionality
- No telemetry or tracking

---

*ModDance Hero — dance your way, scored your way.* 🎶
