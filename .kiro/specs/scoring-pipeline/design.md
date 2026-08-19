# Design Document: Scoring Pipeline (Phase 3)

## Overview

Phase 3 implements deterministic comparison and scoring. All modules are pure functions consuming Phase 2 data models unchanged. No DTW, no ML, no UI coupling.

## Architecture

### Data Flow

```
Player NormalizedPose + MotionFeatures (per frame)
        ↓
┌─────────────────────────────────────────┐
│ Temporal Alignment (nearest-frame)       │
│ ratio = player_ts / ref_duration         │
│ frame_idx = round(ratio * (N-1))         │
└───────────────┬─────────────────────────┘
                ↓ reference frame at frame_idx
┌─────────────────────────────────────────┐
│ Pose Comparison (2D x,y only)            │
│ score = max(0, 100 - mean_dist * 200)    │
├─────────────────────────────────────────┤
│ Angle Comparison (circular error)        │
│ score = max(0, 100 - mean_err * 1.0)     │
├─────────────────────────────────────────┤
│ Motion Comparison (speed + direction)    │
│ score = mean(speed_sim*0.5 + dir_sim*0.5)│
├─────────────────────────────────────────┤
│ Timing Comparison (phase alignment)      │
│ both same state → 100; mismatch → penalty│
└───────────────┬─────────────────────────┘
                ↓
┌─────────────────────────────────────────┐
│ Aggregation (ScoringWeights, renorm)     │
│ combined = Σ(w_i*s_i) / Σ(w_i)          │
└───────────────┬─────────────────────────┘
                ↓
┌─────────────────────────────────────────┐
│ Event Rating (ScoringThresholds)         │
│ ≥90 PERFECT, ≥75 GREAT, ...             │
└───────────────┬─────────────────────────┘
                ↓
┌─────────────────────────────────────────┐
│ Feedback (FeedbackItems, severity)       │
│ angle: error/90, pose: dist/0.5          │
└─────────────────────────────────────────┘
```

### File Structure

```
src/opendance/scoring/
├── __init__.py
├── models.py             # EventRating, FrameComparison, FeedbackItem, LANDMARK_REGIONS
├── alignment.py          # align_frame()
├── pose_compare.py       # compute_pose_score()
├── angle_compare.py      # compute_angle_score()
├── motion_compare.py     # compute_motion_score()
├── timing_compare.py     # compute_timing_score()
├── aggregation.py        # aggregate_scores()
├── rating.py             # compute_event_rating()
├── feedback.py           # generate_feedback()
└── engine.py             # ScoringEngine
```

## Components and Interfaces

### 1. Temporal Alignment (`alignment.py`)

```python
def align_frame(
    player_timestamp_ms: int,
    reference_duration_ms: int,
    reference_frame_count: int,
) -> int:
    """Map player timestamp to nearest reference frame index.

    Formula:
        ratio = clamp(player_timestamp_ms / reference_duration_ms, 0.0, 1.0)
        exact_index = ratio * (reference_frame_count - 1)
        frame_index = round(exact_index)
        return clamp(frame_index, 0, reference_frame_count - 1)

    No landmark interpolation. Nearest frame selection only.
    Deterministic: same inputs → same output.
    """
```

**Example:** Reference 100 frames, 3333ms. Player at 1500ms → ratio=0.45, exact=44.55, round=45 → frame 45.

### 2. Pose Comparison (`pose_compare.py`)

```python
def compute_pose_score(
    player_pose: NormalizedPose,
    reference_pose: NormalizedPose,
    pose_scale_factor: float = 200.0,
    min_valid_landmarks: int = 8,
) -> float | None:
    """2D (x,y) Euclidean distance comparison.

    Formula:
        For each landmark i where both player[i] and reference[i] are not None:
            dist_i = sqrt((px - rx)² + (py - ry)²)  # z excluded
        mean_distance = sum(dist_i) / count
        score = max(0.0, 100.0 - mean_distance * pose_scale_factor)

    Returns None if count < min_valid_landmarks.
    Default: 0.5 body-units mean distance → score 0.

    Example: 20 landmarks, mean dist 0.15 → score = 100 - 30 = 70.0
    """
```

### 3. Angle Comparison (`angle_compare.py`)

```python
def compute_angle_score(
    player_angles: dict[str, float | None],
    reference_angles: dict[str, float | None],
    angle_scale: float = 1.0,
) -> float | None:
    """Circular angular error with wraparound.

    Formula:
        For each joint where both angles are not None:
            abs_diff = abs(player_angle - reference_angle)
            error = min(abs_diff, 360.0 - abs_diff)  # ∈ [0, 180]
        mean_error = sum(errors) / count
        score = max(0.0, 100.0 - mean_error * angle_scale)

    Returns None if count == 0.
    Default: 100° mean error → score 0.

    Example: player=-170°, ref=175° → abs_diff=345° → error=min(345,15)=15°
    """
```

### 4. Motion Comparison (`motion_compare.py`)

```python
def compute_motion_score(
    player_motion: MotionFeatures | None,
    reference_motion: MotionFeatures | None,
    speed_weight: float = 0.5,
    direction_weight: float = 0.5,
    epsilon: float = 0.001,
) -> float | None:
    """Speed magnitude + clamped direction dot product.

    Per-landmark formula:
        # Speed similarity
        if p_speed < epsilon and r_speed < epsilon:
            speed_sim = 1.0  # both still
        else:
            speed_sim = 1.0 - abs(p_speed - r_speed) / max(p_speed, r_speed, epsilon)
            # speed_sim ∈ [0.0, 1.0]

        # Direction similarity
        if p_speed < epsilon or r_speed < epsilon:
            per_lm = speed_sim  # direction undefined, use speed only
        else:
            dir_sim = max(0.0, dot(p_dir, r_dir))  # clamped [0, 1]
            per_lm = speed_sim * speed_weight + dir_sim * direction_weight

    score = mean(per_lm) * 100.0  # [0, 100]
    Returns None if no valid landmarks.

    Example: p_speed=2.0, r_speed=2.5 → speed_sim=0.8
             dir dot=0.95 → per_lm = 0.8*0.5 + 0.95*0.5 = 0.875
             20 landmarks mean 0.85 → score = 85.0
    """
```

### 5. Timing Comparison (`timing_compare.py`)

```python
def compute_timing_score(
    player_motion: MotionFeatures | None,
    reference_motion: MotionFeatures | None,
    timing_scale: float = 0.5,
    velocity_threshold: float = 0.01,  # from MotionConfig.min_velocity_threshold
) -> float | None:
    """Movement-phase alignment: same state = credit, mismatch = penalty.

    Per-landmark formula:
        player_moving = player_speed > velocity_threshold
        ref_moving = ref_speed > velocity_threshold

        if player_moving == ref_moving:
            per_lm = 100.0  # same phase
        else:
            moving_speed = player_speed if player_moving else ref_speed
            per_lm = max(0.0, 100.0 - moving_speed * timing_scale * 1000.0)

    timing_score = mean(per_lm across valid landmarks)  # [0, 100]
    Returns None if no valid data.

    Conceptual distinction from motion:
    - Motion: how well speed/direction match when BOTH are moving.
    - Timing: whether movement OCCURS in the correct temporal phase.

    Example: ref moving at speed 0.8, player still →
        penalty = 0.8 * 0.5 * 1000 = 400 → per_lm = max(0, 100-400) = 0
    Example: both moving → per_lm = 100
    """
```

### 6. Score Aggregation (`aggregation.py`)

```python
def aggregate_scores(
    pose_score: float | None,
    angle_score: float | None,
    motion_score: float | None,
    timing_score: float | None,
    weights: ScoringWeights,
) -> float | None:
    """Weighted average with renormalization for None.

    Formula:
        pairs = [(0.40, pose), (0.25, angle), (0.20, motion), (0.15, timing)]
        available = [(w, s) for w, s in pairs if s is not None]
        if not available: return None
        combined = sum(w*s for w,s in available) / sum(w for w,_ in available)
        # combined ∈ [0.0, 100.0]

    Example: pose=80, angle=90, motion=None, timing=70
        available_weights = 0.40+0.25+0.15 = 0.80
        combined = (32+22.5+10.5) / 0.80 = 81.25
    """
```

### 7. Event Rating (`rating.py`)

```python
class EventRating(Enum):
    PERFECT = "PERFECT"
    GREAT = "GREAT"
    OK = "OK"
    MEH = "MEH"
    MISS = "MISS"

def compute_event_rating(combined: float | None, thresholds: ScoringThresholds) -> EventRating:
    """
    None → MISS
    >= 90 → PERFECT
    >= 75 → GREAT
    >= 50 → OK
    >= 30 → MEH
    < 30 → MISS
    """
```

### 8. Feedback (`feedback.py`)

```python
@dataclass(frozen=True)
class FeedbackItem:
    body_region: str    # from LANDMARK_REGIONS: "face","left_arm","right_arm","torso","left_leg","right_leg"
    issue_type: str     # "angle_mismatch","position_off","timing_phase_mismatch","low_confidence"
    severity: float     # [0.0, 1.0]
    description: str    # measurable, e.g. "left elbow angle differs by 25°"

def generate_feedback(comparison_data, significance_threshold: float = 0.1) -> list[FeedbackItem]:
    """
    Angle feedback:
        severity = min(1.0, angle_error / 90.0)
        emit if severity > significance_threshold

    Pose feedback:
        severity = min(1.0, landmark_distance / 0.5)
        emit if severity > significance_threshold

    Timing feedback:
        emit if timing mismatch detected for a body region
    """
```

### 9. Landmark Regions (`models.py`)

```python
LANDMARK_REGIONS: dict[int, str] = {
    0: "face", 1: "face", 2: "face", 3: "face", 4: "face",
    5: "face", 6: "face", 7: "face", 8: "face", 9: "face", 10: "face",
    11: "left_arm", 13: "left_arm", 15: "left_arm",
    17: "left_arm", 19: "left_arm", 21: "left_arm",
    12: "right_arm", 14: "right_arm", 16: "right_arm",
    18: "right_arm", 20: "right_arm", 22: "right_arm",
    23: "torso", 24: "torso",
    25: "left_leg", 27: "left_leg", 29: "left_leg", 31: "left_leg",
    26: "right_leg", 28: "right_leg", 30: "right_leg", 32: "right_leg",
}
```

### 10. ScoringEngine (`engine.py`)

```python
class ScoringEngine:
    def __init__(self, reference: ReferenceSequence, config: AppConfig) -> None: ...

    def score_frame(self, player_pose: NormalizedPose, player_motion: MotionFeatures | None) -> FrameComparison: ...

    def score_sequence(self, player_poses: list[NormalizedPose | None], player_motions: list[MotionFeatures | None]) -> list[FrameComparison | None]: ...
```

## Data Models

### FrameComparison

| Field | Type | Range |
|-------|------|-------|
| `timestamp_ms` | `int` | Player frame timestamp |
| `pose_score` | `float | None` | [0, 100] |
| `angle_score` | `float | None` | [0, 100] |
| `motion_score` | `float | None` | [0, 100] |
| `timing_score` | `float | None` | [0, 100] |
| `combined_score` | `float | None` | [0, 100] |
| `event_rating` | `EventRating` | PERFECT/GREAT/OK/MEH/MISS |
| `feedback` | `tuple[FeedbackItem, ...]` | Structured feedback |

### Configuration (`[scoring.comparison]`)

| Parameter | Default | Meaning |
|-----------|---------|---------|
| `pose_scale_factor` | 200.0 | 0.5 body-units → score 0 |
| `angle_scale` | 1.0 | 100° → score 0 |
| `timing_scale` | 0.5 | Controls timing penalty magnitude |
| `min_valid_landmarks` | 8 | Below this → PoseScore None |
| `feedback_significance_threshold` | 0.1 | Minimum severity to emit |
| `motion_speed_weight` | 0.5 | Speed contribution |
| `motion_direction_weight` | 0.5 | Direction contribution |
| `epsilon` | 0.001 | Near-zero speed threshold |

## Correctness Properties

### Property 1: Score range

All sub-scores and CombinedScore SHALL be in [0.0, 100.0] or None.

**Validates: Requirements 2.3, 3.3, 4.5, 5.6, 6.4**

### Property 2: Determinism

Identical inputs + config → byte-identical outputs.

**Validates: Requirements 12.1, 12.2**

### Property 3: Monotonicity

As player-reference 2D distance increases, PoseScore SHALL decrease (or remain 0).

**Validates: Requirements 2.3, 14.4**

### Property 4: Missing data propagation

All input landmarks None → all sub-scores None → CombinedScore None → MISS.

**Validates: Requirements 10.1, 10.2, 7.3**

### Property 5: Weight renormalization

If one sub-score is None, CombinedScore equals weighted average of remaining with renormalized weights.

**Validates: Requirements 6.2, 10.3**

## Error Handling

| Condition | Response |
|-----------|----------|
| All landmarks None | All scores None, MISS |
| < min_valid_landmarks | PoseScore None |
| No valid angles | AngleScore None |
| No valid motion | MotionScore None |
| No valid timing data | TimingScore None |
| All sub-scores None | CombinedScore None, MISS |
| Player ts outside reference | Clamp to boundary |

## Testing Strategy

- Pure functions → all testable with synthetic NormalizedPose/MotionFeatures.
- Known geometric inputs: identical poses → 100, max error → 0.
- Wraparound angle tests: -179° vs +179° → error 2°.
- Phase-alignment timing: both moving → 100, mismatch → penalty.
- Property tests: range [0,100], monotonicity, determinism.
- Missing data: various None combinations.
- No hardware/video/model dependencies.

## Performance

- All functions O(33) per frame (33 landmarks).
- Alignment O(1) per frame.
- Full sequence O(n).
- Suitable for real-time per-frame scoring.
