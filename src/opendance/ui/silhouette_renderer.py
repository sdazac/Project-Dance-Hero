"""Silhouette renderer for Practice Mode."""

import cv2
import numpy as np
from PySide6.QtGui import QImage, QPixmap

from opendance.pose.result import PoseResult


def get_transparent_silhouette(
    h: int,
    w: int,
    pose_result: PoseResult,
    visibility_threshold: float = 0.5,
    mirror: bool = False
) -> QPixmap:
    """Returns a QPixmap with a transparent background and humanoid silhouette."""

    # Lienzo RGBA 100% transparente
    canvas = np.zeros((h, w, 4), dtype=np.uint8)

    if pose_result.is_empty:
        qimg = QImage(canvas.data, w, h, w * 4, QImage.Format.Format_RGBA8888)
        return QPixmap.fromImage(qimg)

    lms = pose_result.poses[0]

    def get_pt(idx: int) -> tuple[int, int] | None:
        if idx >= len(lms):
            return None
        lm = lms[idx]
        if lm.visibility < visibility_threshold:
            return None

        # CORRECCIÓN 3: Efecto Espejo invirtiendo el eje X
        x_val = 1.0 - lm.x if mirror else lm.x
        return (int(x_val * w), int(lm.y * h))

    pts = {
        'NO': get_pt(0),
        'LS': get_pt(11), 'RS': get_pt(12),
        'LE': get_pt(13), 'RE': get_pt(14),
        'LW': get_pt(15), 'RW': get_pt(16),
        'LH': get_pt(23), 'RH': get_pt(24),
        'LK': get_pt(25), 'RK': get_pt(26),
        'LA': get_pt(27), 'RA': get_pt(28),
    }

    # Dibujar torso
    if pts['LS'] and pts['RS'] and pts['LH'] and pts['RH']:
        poly = np.array([pts['LS'], pts['RS'], pts['RH'], pts['LH']], np.int32)
        cv2.fillPoly(canvas, [poly], (200, 200, 200, 255))

    def draw_limb(p1_key, p2_key, thickness):
        if pts[p1_key] and pts[p2_key]:
            cv2.line(canvas, pts[p1_key], pts[p2_key], (150, 150, 150, 255), thickness)
            cv2.circle(canvas, pts[p1_key], thickness // 2, (150, 150, 150, 255), -1)
            cv2.circle(canvas, pts[p2_key], thickness // 2, (150, 150, 150, 255), -1)

    draw_limb('LS', 'LE', 16)
    draw_limb('LE', 'LW', 12)
    draw_limb('RS', 'RE', 16)
    draw_limb('RE', 'RW', 12)

    draw_limb('LH', 'LK', 20)
    draw_limb('LK', 'LA', 16)
    draw_limb('RH', 'RK', 20)
    draw_limb('RK', 'RA', 16)

    # Cabeza
    if pts['NO'] and pts['LS'] and pts['RS']:
        neck_mid = ((pts['LS'][0] + pts['RS'][0]) // 2, (pts['LS'][1] + pts['RS'][1]) // 2)
        head_radius = int(np.linalg.norm(np.array(pts['NO']) - np.array(neck_mid))) * 1
        head_radius = max(20, min(50, head_radius))
        cv2.circle(canvas, pts['NO'], head_radius, (220, 220, 220, 255), -1)

    canvas = np.ascontiguousarray(canvas)
    qimg = QImage(canvas.data, w, h, w * 4, QImage.Format.Format_RGBA8888)
    return QPixmap.fromImage(qimg)
