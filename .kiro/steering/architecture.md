# OpenDance AI — Architecture

## Application type

OpenDance AI is a local desktop application.

The MVP should not require:

* a web server;
* cloud services;
* remote AI APIs;
* a database server;
* an internet connection for core functionality.

## Primary technology stack

Language:

Python 3.x

GUI:

PySide6

Computer vision:

OpenCV

Pose estimation:

MediaPipe Pose Landmarker

Numerical processing:

NumPy

Scientific processing:

SciPy when useful

Future model inference:

ONNX Runtime

Packaging:

PySide6 deployment tooling and/or Nuitka-based packaging

CI/CD:

GitHub Actions

## Architectural layers

The application should maintain clear separation between:

### UI layer

Responsible for:

* windows;
* widgets;
* navigation;
* visual feedback;
* user interaction;
* displaying metrics.

The UI must not contain core pose-analysis algorithms.

### Camera layer

Responsible for:

* camera discovery;
* camera initialization;
* frame acquisition;
* camera state;
* FPS;
* camera errors.

### Video layer

Responsible for:

* loading reference videos;
* playback;
* seeking;
* frame extraction;
* metadata;
* playback speed.

### Pose layer

Responsible for:

* MediaPipe initialization;
* pose detection;
* landmarks;
* visibility/confidence;
* pose results.

### Motion layer

Responsible for:

* pose normalization;
* body-relative coordinates;
* joint angles;
* distances;
* velocity;
* acceleration;
* motion vectors.

### Alignment layer

Responsible for:

* temporal synchronization;
* temporal offsets;
* constrained Dynamic Time Warping or equivalent algorithms.

### Scoring layer

Responsible for:

* pose similarity;
* angle similarity;
* motion similarity;
* timing similarity;
* combined accuracy;
* event rating;
* combo;
* final grade.

### Analytics layer

Responsible for:

* timeline metrics;
* weak sections;
* error identification;
* session summaries.

### Storage layer

Responsible for:

* reference analysis cache;
* metadata;
* settings;
* session results.

### Configuration layer

Responsible for:

* scoring thresholds;
* scoring weights;
* camera configuration;
* playback configuration;
* application settings.

## Recommended project structure

Use a structure similar to:

src/
opendance/
app/
ui/
camera/
video/
pose/
motion/
alignment/
scoring/
analytics/
storage/
config/

tests/
unit/
integration/
fixtures/

assets/
models/
demo/

scripts/

.github/
workflows/

## Reference analysis pipeline

Reference videos should be analyzed once and cached.

Pipeline:

Reference Video
→ metadata
→ frame extraction
→ pose detection
→ confidence filtering
→ pose normalization
→ motion feature extraction
→ temporal sequence
→ cached analysis artifact.

The cache must be invalidated if:

* the source video changes;
* the analysis configuration changes;
* the pose model changes;
* the feature representation changes.

## Camera pipeline

Camera:

Frame
→ pose detection
→ confidence filtering
→ normalization
→ motion features
→ comparison
→ scoring
→ UI feedback.

The camera pipeline must operate without blocking the UI.

## Real-time processing

Real-time camera processing is a primary requirement.

Avoid unnecessary frame processing.

Do not repeatedly run expensive operations on identical frames.

Long-running operations must not block the UI thread.

Use worker threads/processes where appropriate.

## Pose data

The internal pose representation must be independent of the UI.

The application should use body-relative information instead of relying only on absolute screen coordinates.

Use:

* normalized landmarks;
* world landmarks when appropriate;
* body center;
* body scale;
* joint angles;
* velocities;
* confidence.

## Similarity architecture

The comparison system should expose independent metrics:

pose_similarity
angle_similarity
motion_similarity
timing_similarity

The final accuracy should be calculated using configurable weights.

Default:

pose = 0.40
angles = 0.25
motion = 0.20
timing = 0.15

## Machine learning architecture

The MVP should not require a complex deep-learning scoring model.

The initial scoring engine should be deterministic and explainable.

The architecture must allow future ML models to be added without rewriting:

* UI;
* camera;
* reference analysis;
* storage.

Future ML models should preferably support ONNX export.

## Data flow

Reference:

Video
→ ReferenceAnalyzer
→ PoseSequence
→ MotionSequence
→ Cache

User:

Camera
→ PoseDetector
→ UserPose
→ MotionFeatures

Comparison:

ReferenceMotion
+
UserMotion
→ TemporalAligner
→ SimilarityEngine
→ ScoringEngine
→ Analytics
→ UI

## Architectural restrictions

Do not:

* put scoring algorithms inside UI classes;
* put MediaPipe logic inside widgets;
* make UI classes responsible for video analysis;
* create global mutable state without justification;
* add a database for the MVP;
* add a web API for the MVP;
* add cloud processing for the MVP;
* introduce unnecessary frameworks.

Prefer simple modules with explicit inputs and outputs.
