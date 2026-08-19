# Phase 3.5 — Performance, Temporal Fidelity & Multi-Person Analysis

## 1. Performance Benchmark

### Known measurements (single-person 576x1024 30fps video)
- 30 FPS analysis: 881 frames in ~53s → ~60ms/frame effective
- Processing ratio: 53s / 29.4s = 1.8x (slower than real-time)

### Projected performance at different analysis FPS
| Analysis FPS | Frames (30s video) | Est. Wall Time | Processing Ratio | Effective FPS |
|---|---|---|---|---|
| 10 | ~300 | ~18s | 0.6x | 16.7 |
| 15 | ~450 | ~27s | 0.9x | 16.7 |
| 20 | ~600 | ~36s | 1.2x | 16.7 |
| 30 | ~900 | ~54s | 1.8x | 16.7 |

### Bottleneck
MediaPipe Pose Landmarker inference: ~60ms per frame on CPU (TFLite XNNPACK).
This is the dominant cost regardless of video resolution or number of visible people (since num_poses=1).

## 2. Frame Sampling Strategy

### Current behavior
- ReferenceAnalyzer samples at configured `sample_fps`
- Timestamp authority: `timestamp_ms = sample_index * (1000 / sample_fps)`
- Frame selection: `frame_number = int((timestamp_ms / 1000.0) * video_fps)`

### Correct behavior
Timestamps MUST reflect the original video time, not the sampling rate.
The sampling rate only determines WHICH frames are selected, not the time axis.

### Recommendation
Keep current design. The authoritative timestamp correctly maps to real video time.
A 60fps source sampled at 15fps picks every 4th frame — timestamps remain 0, 66.67, 133.33ms etc.

## 3. Temporal Fidelity

### Root cause of desync
The landmark_replay.py diagnostic used a hardcoded `sample_interval_ms = 1000.0 / 30.0` regardless of actual source FPS. If source is 60fps, the replay plays at half speed. The fix is to use `sequence.metadata.fps` for playback timing.

### Architectural principle
- Analysis is OFFLINE — wall-clock processing time has NO effect on timestamps
- Timestamps come from the sampling formula, which maps to real video time
- Replay uses source FPS for frame pacing, independent of analysis FPS
- Scoring comparison uses timestamp_ms for alignment, which is correct

## 4. Multi-Person Analysis

### Current behavior
- PoseDetector is configured with `num_poses=1`
- MediaPipe returns only the FIRST detected pose
- There is no selection logic for which person is returned
- MediaPipe internally selects "the most prominent" pose (undefined priority)

### Impact
For multi-person videos, the detected person may:
- Switch between dancers unpredictably
- Jump to a different person between frames
- Cause discontinuities in normalization and motion features

### Current pipeline: SINGLE-PERSON ONLY

## 5. Primary Person Selection Strategy

### Recommended approach for Phase 4: Largest Body Area

| Strategy | Pros | Cons |
|---|---|---|
| A. Largest area | Simple, stable, predictable | May select wrong person if closest |
| B. Highest confidence | MediaPipe-native priority | Not configurable |
| C. Closest to center | Good for solo-centered videos | Fails for off-center dancers |
| D. Combined | Most robust | Complex |
| E. Manual selection | User control | Requires UI |
| F. Multi-person | Full tracking | Phase 5+ scope |

**Recommendation:** Start with A (largest body area) as default, with option C (closest to center) as alternative. Both are deterministic and simple.

### Implementation notes
- Increase `num_poses` to 3-5 in PoseDetector
- After detection, score each pose by bounding box area
- Select the one with largest area
- Track consistency: if the largest person changes, apply a small hysteresis to avoid frame-to-frame jumping

## 6. Product Scenario

"A user imports a choreography video with 5 dancers."

### Expected behavior:
1. System analyzes the video
2. System selects the PRIMARY dancer (largest/most visible)
3. System informs the user which person was selected
4. User can override (future UI)
5. If the selected person exits frame, system handles gracefully (None pose)
6. If people enter/exit, the selection remains stable (hysteresis)

### Current limitation:
The system cannot reliably handle this scenario yet. Phase 4 should add:
- num_poses > 1
- Selection logic
- Visual indicator of selected person

## 7. Analysis FPS Recommendation

### Recommended default: 15 FPS

| Criterion | 10 FPS | 15 FPS | 20 FPS | 30 FPS |
|---|---|---|---|---|
| Temporal resolution | 100ms | 66ms | 50ms | 33ms |
| Fast movement capture | Poor | Acceptable | Good | Good |
| Processing time (30s) | ~18s | ~27s | ~36s | ~54s |
| Processing ratio | 0.6x | 0.9x | 1.2x | 1.8x |
| Memory (2min) | ~5.4MB | ~8.1MB | ~10.8MB | ~16.2MB |
| Scoring accuracy | Reduced | Good | Good | Best |

**Rationale:**
- 15 FPS provides 66ms temporal resolution — sufficient for most dance movements
- Processing at ~0.9x approaches real-time on CPU
- Memory remains manageable
- Captures movements faster than ~150ms (sufficient for choreography)
- Can be increased to 20-30 for competition/precision mode

### Future: GPU acceleration
With GPU (TFLite GPU delegate), per-frame time could drop to ~15-20ms, making 30 FPS feasible in near-real-time.

## 8. Cache Impact

### Current design
AnalysisCache key includes config_hash, which incorporates all ReferenceConfig values including sample_fps.

- 15 FPS analysis ≠ 30 FPS analysis (different cache entries)
- Changing sample_fps invalidates cache (correct behavior)
- No risk of cross-contamination

### Recommendation
No changes needed. The existing cache design correctly separates different configurations.

## 9. Memory Impact

### Estimates per frame: ~3 KB
- NormalizedPose: ~1.1 KB (33 landmarks × 3 coords × 8 bytes + metadata)
- MotionFeatures: ~1.2 KB (33 LandmarkMotion × ~36 bytes)
- JointAngles: ~0.1 KB (8 angles × 8 bytes + dict overhead)
- Overhead: ~0.6 KB (Python object headers)

### By duration and FPS:

| Duration | 10 FPS | 15 FPS | 20 FPS | 30 FPS |
|---|---|---|---|---|
| 30s | 0.9 MB | 1.4 MB | 1.8 MB | 2.7 MB |
| 2 min | 3.6 MB | 5.4 MB | 7.2 MB | 10.8 MB |
| 5 min | 9.0 MB | 13.5 MB | 18.0 MB | 27.0 MB |

**Conclusion:** Memory is NOT a concern for videos up to 5 minutes at any reasonable FPS.
For longer videos (10+ min at 30 FPS), consider lazy loading or chunked processing.

## 10. Recommendations for Phase 4

### Required before Phase 4:
1. **None.** The current pipeline works correctly for single-person videos.

### Recommended for Phase 4:
1. Add configurable `analysis_fps` to UI (default 15, option for 20/30)
2. Add `num_poses > 1` support with person selection
3. Add visual indicator of selected person in analysis preview
4. Handle detection gaps gracefully in combo/scoring (already None)
5. Use `sequence.metadata.fps` for replay timing (fix diagnostic scripts)

### Phase 4 scope boundaries:
- Multi-person selection: simple heuristic (largest area)
- NOT full multi-person tracking
- NOT pose ID assignment across frames
- NOT hand/finger tracking

## 11. Discrepancies Found

- `landmark_replay.py` uses hardcoded `sample_interval_ms = 1000.0 / 30.0` for timestamps — should use `sequence.metadata.fps`
- This only affects the DIAGNOSTIC script, not production code
- Production ReferenceAnalyzer timestamps are correct

## 12. Conclusion

The pipeline is suitable for Phase 4 with no production code changes required. The observed slowness is inherent to CPU-based MediaPipe inference (~60ms/frame). Reducing analysis FPS to 15 provides a good balance. Multi-person support requires a small Phase 4 change (num_poses + selection logic).
