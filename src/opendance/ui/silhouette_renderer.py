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
    base_color: tuple[int, int, int] = (220, 220, 220),
    mirror: bool = True
) -> QPixmap:
    """Returns a QPixmap with a transparent background and humanoid silhouette."""
    
    # Lienzo RGBA 100% transparente
    canvas = np.zeros((h, w, 4), dtype=np.uint8)
    
    if pose_result.is_empty:
        qimg = QImage(canvas.data, w, h, w * 4, QImage.Format.Format_RGBA8888)
        return QPixmap.fromImage(qimg)

    lms = pose_result.landmarks

    def get_pt(idx: int) -> tuple[int, int] | None:
        if idx >= len(lms): return None
        lm = lms[idx]
        if lm.visibility < visibility_threshold: return None
        
        # CORRECCIÓN 3: Efecto Espejo invirtiendo el eje X
        x_val = 1.0 - lm.x if mirror else lm.x
        return (int(x_val * w), int(lm.y * h))

    pts = {
        'N': get_pt(0),
        'LS': get_pt(11), 'RS': get_pt(12),
        'LE': get_pt(13), 'RE': get_pt(14),
        'LW': get_pt(15), 'RW': get_pt(16),
        'LH': get_pt(23), 'RH': get_pt(24),
        'LK': get_pt(25), 'RK': get_pt(26),
        'LA': get_pt(27), 'RA': get_pt(28),
    }

    color_rgba = (base_color[0], base_color[1], base_color[2], 255)

    def draw_limb(p1_key: str, p2_key: str, thickness: int):
        p1, p2 = pts.get(p1_key), pts.get(p2_key)
        if p1 and p2:
            cv2.line(canvas, p1, p2, color_rgba, thickness, cv2.LINE_AA)
            cv2.circle(canvas, p1, thickness // 2, color_rgba, -1, cv2.LINE_AA)
            cv2.circle(canvas, p2, thickness // 2, color_rgba, -1, cv2.LINE_AA)

    # Extremidades (Más delgadas para parecer humanas)
    draw_limb('LS', 'LE', 16)
    draw_limb('LE', 'LW', 12)
    draw_limb('RS', 'RE', 16)
    draw_limb('RE', 'RW', 12)
    
    draw_limb('LH', 'LK', 20)
    draw_limb('LK', 'LA', 16)
    draw_limb('RH', 'RK', 20)
    draw_limb('RK', 'RA', 16)

    # Torso
    torso_pts = [pts[k] for k in ['LS', 'RS', 'RH', 'LH'] if pts[k] is not None]
    if len(torso_pts) == 4:
        arr = np.array(torso_pts, np.int32).reshape((-1, 1, 2))
        cv2.fillPoly(canvas, [arr], color_rgba, cv2.LINE_AA)

    # Cabeza y Cuello
    if pts['N'] and pts['LS'] and pts['RS']:
        neck = ((pts['LS'][0] + pts['RS'][0]) // 2, (pts['LS'][1] + pts['RS'][1]) // 2)
        cv2.line(canvas, neck, pts['N'], color_rgba, 12, cv2.LINE_AA)
        shoulder_w = abs(pts['LS'][0] - pts['RS'][0])
        head_r = max(20, int(shoulder_w * 0.35))
        cv2.circle(canvas, pts['N'], head_r, color_rgba, -1, cv2.LINE_AA)

    canvas = np.ascontiguousarray(canvas)
    qimg = QImage(canvas.data, w, h, w * 4, QImage.Format.Format_RGBA8888)
    return QPixmap.fromImage(qimg)