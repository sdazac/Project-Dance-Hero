# UI Instructions — OpenDance AI

applyTo: "src/opendance/ui/**/*.py"

## Framework

PySide6 (Qt for Python). All UI components are QWidget subclasses.

## Architecture Rules

Read `.kiro/steering/architecture.md` — UI layer section.

- **UI widgets handle display and interaction only.**
- **No business logic in widgets**: pose analysis, scoring, motion features, and camera I/O belong in their respective layers.
- **No blocking operations**: Camera reads and MediaPipe inference happen on `FrameWorker` (QThread). The UI thread only receives finished results via Qt signals.
- **Signal/slot pattern**: Use `Signal`/`Slot` for cross-thread communication. Never access widgets from non-UI threads.

## Current UI Components

| Component | File | Purpose |
|-----------|------|---------|
| `CameraWidget` | `camera_widget.py` | Live feed display, Start/Stop controls |
| `StatusIndicator` | `status_indicator.py` | Human-readable camera state label |
| `render_skeleton` | `skeleton_renderer.py` | Pure function: draw landmarks + bones on frame |

## Frame Display Pipeline

The frame arrives from `FrameWorker` as a BGR numpy array + `PoseResult`:

1. `render_skeleton(frame, pose_result, threshold)` — fast, in-place on UI thread
2. `cv2.cvtColor(frame, COLOR_BGR2RGB)` — color conversion
3. `QImage(data, w, h, bytes_per_line, Format_RGB888)` — wrap as Qt image
4. `QPixmap.fromImage(qimage)` — create displayable pixmap
5. `pixmap.scaled(size, KeepAspectRatio, SmoothTransformation)` — fit to widget
6. `label.setPixmap(scaled)` — update display

## Control State Rules

| Camera State | Start Button | Stop Button |
|-------------|-------------|------------|
| INACTIVE | Enabled | Disabled |
| ACTIVE | Disabled | Enabled |
| PAUSED | Disabled | Enabled |
| ERROR | Enabled | Disabled |

## Testing UI

- Set `QT_QPA_PLATFORM=offscreen` for headless testing.
- Create `QApplication` in a module-scoped fixture.
- Test actual widget state (button enabled, label text, pixmap presence).
- Mock `CameraManager` where needed — do not require real camera.

## Adding New Widgets

When adding new UI components:
1. Create in `src/opendance/ui/<widget_name>.py`
2. Export from `src/opendance/ui/__init__.py`
3. Add unit tests in `tests/unit/test_<widget_name>.py`
4. Connect to the pipeline via signals in the appropriate manager
5. Integrate into the main window in `src/opendance/app/main.py`
