# OpenDance AI — AI and Motion Analysis Rules

## Purpose

The movement-analysis system compares a user's body movement against a reference dance sequence.

The MVP must prioritize deterministic and explainable algorithms.

A complex machine-learning model is not required for the initial scoring engine.

## Pose estimation

Use MediaPipe Pose Landmarker for the initial pose-estimation system.

The system should preserve:

* landmark coordinates;
* world coordinates when available;
* visibility/confidence;
* timestamps.

Do not treat low-confidence landmarks as equally reliable as high-confidence landmarks.

## Pose normalization

Raw camera coordinates must not be directly compared to reference coordinates.

Normalize the body using body-relative measurements.

The normalization should account for:

* body position;
* body scale;
* camera distance;
* horizontal/vertical translation.

Where appropriate, account for body orientation.

## Relevant landmarks

The system should support analysis of major body regions including:

* head;
* shoulders;
* elbows;
* wrists;
* torso;
* hips;
* knees;
* ankles.

The implementation should not assume that every landmark is always visible.

## Joint angles

Calculate meaningful joint angles where reliable landmarks are available.

Examples:

* left elbow;
* right elbow;
* left shoulder;
* right shoulder;
* left knee;
* right knee;
* hip angles;
* torso orientation.

Joint-angle calculations should be independently testable.

## Motion features

The system may calculate:

* normalized landmark position;
* joint angle;
* velocity;
* acceleration;
* movement direction;
* relative distances.

Velocity and acceleration must account for frame timing.

## Confidence

Confidence must affect scoring.

If important landmarks are not visible:

* reduce confidence;
* avoid treating missing data as a wrong pose;
* communicate detection problems when appropriate.

The system should distinguish between:

1. wrong movement;
2. correct movement but low confidence;
3. body outside camera view.

## Similarity

Expose separate similarity metrics:

* pose similarity;
* angle similarity;
* motion similarity;
* timing similarity.

Do not immediately collapse all information into a single score.

## Default scoring weights

pose similarity: 40%

joint-angle similarity: 25%

motion similarity: 20%

timing similarity: 15%

Weights must be configurable.

## Temporal alignment

The reference and user may perform the same movement at slightly different times.

Never assume frame-to-frame equality.

Use a temporal alignment algorithm such as constrained Dynamic Time Warping.

The alignment must allow:

* small delays;
* small advances;
* different movement speeds.

Do not allow unrestricted warping that makes obviously incorrect movements appear correct.

## Error explanation

The system should produce measurable explanations when possible.

Examples:

* left elbow angle differs by approximately X degrees;
* right arm movement is delayed;
* left knee position differs significantly;
* insufficient body visibility;
* low confidence.

Avoid subjective statements such as:

"Your dancing is bad."

Use measurable statements.

## Machine learning

The MVP scoring system should be deterministic.

Future ML components may be introduced for:

* movement classification;
* automatic error classification;
* quality estimation;
* choreography segmentation;
* personalized feedback.

When ML is introduced:

* isolate inference from the rest of the application;
* define a stable model interface;
* keep preprocessing explicit;
* version models;
* document model inputs and outputs;
* prefer local inference;
* prefer ONNX when practical.

## ML reproducibility

Any ML model added to the project must document:

* model version;
* input format;
* output format;
* preprocessing;
* postprocessing;
* expected runtime;
* hardware requirements.

## Important limitation

Pose similarity is not the same thing as artistic quality.

The system should describe its result as movement similarity or dance-performance similarity based on measurable pose and timing features.

It should not claim to objectively judge artistic quality.
