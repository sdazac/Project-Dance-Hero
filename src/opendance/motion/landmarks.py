"""MediaPipe Pose Landmarker index constants and joint definitions.

Provides named constants for the 33-landmark scheme, joint angle triplet
definitions, and body center/scale landmark references.
"""

# Landmark indices (MediaPipe Pose Landmarker 33-landmark scheme)
NOSE = 0
LEFT_EYE_INNER = 1
LEFT_EYE = 2
LEFT_EYE_OUTER = 3
RIGHT_EYE_INNER = 4
RIGHT_EYE = 5
RIGHT_EYE_OUTER = 6
LEFT_EAR = 7
RIGHT_EAR = 8
MOUTH_LEFT = 9
MOUTH_RIGHT = 10
LEFT_SHOULDER = 11
RIGHT_SHOULDER = 12
LEFT_ELBOW = 13
RIGHT_ELBOW = 14
LEFT_WRIST = 15
RIGHT_WRIST = 16
LEFT_PINKY = 17
RIGHT_PINKY = 18
LEFT_INDEX = 19
RIGHT_INDEX = 20
LEFT_THUMB = 21
RIGHT_THUMB = 22
LEFT_HIP = 23
RIGHT_HIP = 24
LEFT_KNEE = 25
RIGHT_KNEE = 26
LEFT_ANKLE = 27
RIGHT_ANKLE = 28
LEFT_HEEL = 29
RIGHT_HEEL = 30
LEFT_FOOT_INDEX = 31
RIGHT_FOOT_INDEX = 32

NUM_LANDMARKS = 33

# Joint angle definitions: (proximal, joint_center, distal) landmark indices.
# Angle is computed at joint_center using vectors to proximal and distal.
JOINT_ANGLES: dict[str, tuple[int, int, int]] = {
    "left_elbow": (LEFT_SHOULDER, LEFT_ELBOW, LEFT_WRIST),
    "right_elbow": (RIGHT_SHOULDER, RIGHT_ELBOW, RIGHT_WRIST),
    "left_shoulder": (LEFT_ELBOW, LEFT_SHOULDER, LEFT_HIP),
    "right_shoulder": (RIGHT_ELBOW, RIGHT_SHOULDER, RIGHT_HIP),
    "left_knee": (LEFT_HIP, LEFT_KNEE, LEFT_ANKLE),
    "right_knee": (RIGHT_HIP, RIGHT_KNEE, RIGHT_ANKLE),
    "left_hip": (LEFT_KNEE, LEFT_HIP, LEFT_SHOULDER),
    "right_hip": (RIGHT_KNEE, RIGHT_HIP, RIGHT_SHOULDER),
}

# Landmarks used for body center computation (midpoint)
BODY_CENTER_LANDMARKS: tuple[int, int] = (LEFT_HIP, RIGHT_HIP)

# Landmarks used for body scale computation (Euclidean distance)
BODY_SCALE_LANDMARKS: tuple[int, int] = (LEFT_SHOULDER, RIGHT_HIP)
