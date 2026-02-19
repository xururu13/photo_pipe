# ── Детекция лиц и анализ глаз (MediaPipe) ────────────────────────────────────

from __future__ import annotations

import numpy as np

from config import EAR_CLOSED_THRESHOLD, FACES_NEUTRAL_SCORE

# Индексы ландмарков для левого и правого глаза (MediaPipe FaceMesh 468 точек)
LEFT_EYE = [362, 385, 387, 263, 373, 380]
RIGHT_EYE = [33, 160, 158, 133, 153, 144]

_face_mesh = None
_init_failed = False


def _get_face_mesh():
    """Ленивая инициализация MediaPipe FaceMesh."""
    global _face_mesh, _init_failed
    if _init_failed:
        return None
    if _face_mesh is not None:
        return _face_mesh
    try:
        import mediapipe as mp
        _face_mesh = mp.solutions.face_mesh.FaceMesh(
            static_image_mode=True,
            max_num_faces=10,
            refine_landmarks=True,
            min_detection_confidence=0.5,
        )
        return _face_mesh
    except Exception:
        _init_failed = True
        return None


def compute_ear(landmarks, eye_indices: list[int], h: int, w: int) -> float:
    """Eye Aspect Ratio: вертикальное расстояние / горизонтальное расстояние."""
    pts = []
    for idx in eye_indices:
        lm = landmarks[idx]
        pts.append((lm.x * w, lm.y * h))

    # Горизонтальное расстояние (p0–p3)
    horizontal = np.linalg.norm(
        np.array(pts[0]) - np.array(pts[3])
    )
    if horizontal < 1e-6:
        return 0.0

    # Вертикальные расстояния (p1–p5, p2–p4)
    v1 = np.linalg.norm(np.array(pts[1]) - np.array(pts[5]))
    v2 = np.linalg.norm(np.array(pts[2]) - np.array(pts[4]))

    return (v1 + v2) / (2.0 * horizontal)


def detect_faces(image: np.ndarray) -> tuple[int, float, bool]:
    """
    Анализирует лица на изображении.
    Возвращает (face_count, eyes_open_ratio, all_eyes_closed).
    """
    import cv2

    mesh = _get_face_mesh()
    if mesh is None:
        return 0, 0.0, False

    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    results = mesh.process(rgb)

    if not results.multi_face_landmarks:
        return 0, 0.0, False

    h, w = image.shape[:2]
    face_count = len(results.multi_face_landmarks)
    eyes_open = 0
    total_eyes = 0

    for face_lm in results.multi_face_landmarks:
        lm = face_lm.landmark
        for eye_indices in [LEFT_EYE, RIGHT_EYE]:
            ear = compute_ear(lm, eye_indices, h, w)
            total_eyes += 1
            if ear >= EAR_CLOSED_THRESHOLD:
                eyes_open += 1

    eyes_open_ratio = eyes_open / total_eyes if total_eyes > 0 else 0.0
    all_closed = total_eyes > 0 and eyes_open == 0

    return face_count, eyes_open_ratio, all_closed


def compute_face_score(face_count: int, eyes_open_ratio: float) -> float:
    """Скор лиц: зависит от открытости глаз, нейтральный если лиц нет."""
    if face_count == 0:
        return FACES_NEUTRAL_SCORE
    return eyes_open_ratio
