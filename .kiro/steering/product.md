# OpenDance AI — Product Definition

## Product overview

OpenDance AI is an open-source desktop application for dance practice, movement analysis and rhythm-game-style scoring.

The application allows users to import a reference dance video and compare the movements in that video against the user's movements captured through a computer camera.

The reference video may contain:

* a real dancer;
* a holographic performer;
* an animated character;
* a choreography;
* a dance tutorial;
* any other compatible video containing a visible human-like body.

The system must not depend on a specific character, artist, game or franchise.

The reference video is simply called the "Reference Video".

## Core concept

The application performs the following pipeline:

Reference Video
→ Pose Detection
→ Pose Normalization
→ Motion Feature Extraction
→ Reference Motion Sequence

Camera
→ Pose Detection
→ Pose Normalization
→ Motion Feature Extraction
→ User Motion Sequence

Reference Motion + User Motion
→ Temporal Alignment
→ Motion Comparison
→ Accuracy
→ Rating
→ Score

## MVP goal

The MVP must demonstrate the complete technical pipeline.

A user must be able to:

1. Launch the application.
2. Grant camera access.
3. See the webcam feed.
4. See their detected body skeleton.
5. Import a compatible reference video.
6. Analyze the reference video.
7. Extract its body-motion data.
8. Start Practice mode.
9. Play the reference video.
10. See their live body pose.
11. Compare their movement against the reference.
12. Receive live accuracy.
13. Receive PERFECT/GREAT/OK/MEH/MISS feedback.
14. Change playback speed.
15. Complete a practice session.
16. View overall accuracy.
17. View accuracy over time.
18. Identify weak sections of the choreography.
19. Start Arcade mode.
20. Complete the entire song.
21. Receive combo and score.
22. Receive a final grade.

## Practice mode

Practice mode is intended for learning and improving a choreography.

It must support:

* reference video playback;
* webcam preview;
* body skeleton visualization;
* play;
* pause;
* restart;
* seek;
* playback speed control;
* live accuracy;
* current rating;
* timeline accuracy;
* weak-section detection;
* section replay;
* final session statistics.

Practice mode may allow the user to pause, seek or repeat sections.

## Arcade mode

Arcade mode is intended to behave like a dance game.

The selected choreography must play from beginning to end.

The user cannot fail or be removed from the song during playback.

The system continuously evaluates the user's movement.

The final result is shown after the complete song.

Arcade mode must include:

* live accuracy;
* score;
* combo;
* current rating;
* final accuracy;
* final grade.

## Event ratings

The system uses the following default event ratings:

### PERFECT

90%–100%

The user's body angles, movement and timing closely match the reference.

### GREAT

75%–89.99%

The overall movement is strong but there are moderate differences in timing, pose or movement quality.

### OK

50%–74.99%

The system recognizes the intended movement, but significant differences exist.

### MEH

30%–49.99%

The user is moving in approximately the correct time but the pose differs substantially.

### MISS

Below 30%

The movement is substantially different, missing, poorly detected or outside the camera view.

These thresholds must remain configurable.

## Combo

PERFECT increases combo.

GREAT increases combo.

OK resets combo.

MEH resets combo.

MISS resets combo.

## Final grading

ALL PERFECT:

Every scored event is PERFECT.

SS:

The user achieved FULL COMBO but did not achieve ALL PERFECT.

S:

90.00%–100.00% overall accuracy.

A:

80.00%–89.99%.

B:

70.00%–79.99%.

C:

60.00%–69.99%.

D:

50.00%–59.99%.

FAILED:

Below 50%.

The application must store continuous numerical accuracy rather than only categorical grades.

## Analytics

Practice mode must provide useful information about performance.

At minimum the application should be able to show:

* overall accuracy;
* accuracy over time;
* pose similarity over time;
* joint-angle similarity over time;
* motion similarity over time;
* timing similarity over time;
* detection confidence;
* weak sections;
* important errors.

When possible, the system should explain low scores using measurable information.

Examples:

* left arm angle mismatch;
* right leg position mismatch;
* movement started late;
* movement started early;
* body partially outside camera;
* low landmark confidence.

## Future product direction

The project may eventually include:

* advanced machine-learning scoring;
* personalized training;
* automatic choreography segmentation;
* beat detection;
* music synchronization;
* multiple difficulty levels;
* mobile camera support;
* remote phone camera;
* richer game visuals;
* leaderboards;
* replay analysis;
* historical performance tracking.

These are future capabilities and must not be implemented unless explicitly requested.

## Open-source principles

The source code should be designed for public GitHub development.

The application should process user camera data locally by default.

The project must not bundle copyrighted commercial dance videos or music unless redistribution rights are available.

Users may import their own media locally.

## Product philosophy

Prioritize:

1. Correctness.
2. Reliable movement analysis.
3. Explainable scoring.
4. Good user experience.
5. Maintainable architecture.
6. Local processing.
7. Performance.
8. Extensibility.

Do not sacrifice the correctness of the movement-analysis engine merely to add visual game features.
