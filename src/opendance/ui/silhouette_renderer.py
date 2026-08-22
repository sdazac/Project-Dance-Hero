"""Silhouette renderer for Practice Mode."""

from typing import Optional

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

    # CORRECCIÓN DE MYPY: Se usa landmarks en lugar de poses[0]
    lms = pose_result.landmarks

    def get_pt(idx: int) -> Optional[tuple[int, int]]:
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

    def draw_limb(p1_key: str, p2_key: str, thickness: int) -> None:
        p1 = pts.get(p1_key)
        p2 = pts.get(p2_key)
        if p1 and p2:
            cv2.line(canvas, p1, p2, (150, 150, 150, 255), thickness)
            cv2.circle(canvas, p1, thickness // 2, (150, 150, 150, 255), -1)
            cv2.circle(canvas, p2, thickness // 2, (150, 150, 150, 255), -1)

    draw_limb('LS', 'LE', 16)
    draw_limb('LE', 'LW', 12)
    draw_limb('RS', 'RE', 16)
    draw_limb('RE', 'RW', 12)

    draw_limb('LH', 'LK', 20)
    draw_limb('LK', 'LA', 16)
    draw_limb('RH', 'RK', 20)
    draw_limb('RK', 'RA', 16)

    # Cabeza
    p_no = pts.get('NO')
    p_ls = pts.get('LS')
    p_rs = pts.get('RS')
    if p_no and p_ls and p_rs:
        neck_mid = ((p_ls[0] + p_rs[0]) // 2, (p_ls[1] + p_rs[1]) // 2)
        head_radius = int(np.linalg.norm(np.array(p_no) - np.array(neck_mid))) * 1
        head_radius = max(20, min(50, head_radius))
        cv2.circle(canvas, p_no, head_radius, (220, 220, 220, 255), -1)

    canvas = np.ascontiguousarray(canvas)
    qimg = QImage(canvas.data, w, h, w * 4, QImage.Format.Format_RGBA8888)
    return QPixmap.fromImage(qimg)
