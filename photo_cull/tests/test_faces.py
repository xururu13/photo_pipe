import numpy as np
from unittest.mock import patch, MagicMock

from faces import compute_ear, compute_face_score, detect_faces


class _FakeLandmark:
    def __init__(self, x, y):
        self.x = x
        self.y = y


class TestComputeEar:
    def test_open_eye(self):
        """Глаз открыт: вертикальные расстояния значительны."""
        # p0(left), p1(top-left), p2(top-right), p3(right), p4(bottom-right), p5(bottom-left)
        lm = {
            0: _FakeLandmark(0.1, 0.5),   # left corner
            1: _FakeLandmark(0.2, 0.4),   # top-left
            2: _FakeLandmark(0.3, 0.4),   # top-right
            3: _FakeLandmark(0.4, 0.5),   # right corner
            4: _FakeLandmark(0.3, 0.6),   # bottom-right
            5: _FakeLandmark(0.2, 0.6),   # bottom-left
        }
        ear = compute_ear(lm, [0, 1, 2, 3, 4, 5], 100, 100)
        assert ear > 0.3

    def test_closed_eye(self):
        """Глаз закрыт: вертикальные расстояния почти нулевые."""
        lm = {
            0: _FakeLandmark(0.1, 0.5),
            1: _FakeLandmark(0.2, 0.50),
            2: _FakeLandmark(0.3, 0.50),
            3: _FakeLandmark(0.4, 0.5),
            4: _FakeLandmark(0.3, 0.51),
            5: _FakeLandmark(0.2, 0.51),
        }
        ear = compute_ear(lm, [0, 1, 2, 3, 4, 5], 100, 100)
        assert ear < 0.1

    def test_zero_horizontal(self):
        """Если горизонтальное расстояние нулевое — EAR = 0."""
        lm = {i: _FakeLandmark(0.5, 0.5) for i in range(6)}
        ear = compute_ear(lm, [0, 1, 2, 3, 4, 5], 100, 100)
        assert ear == 0.0


class TestComputeFaceScore:
    def test_no_faces(self):
        assert compute_face_score(0, 0.0) == 0.7

    def test_all_open(self):
        assert compute_face_score(2, 1.0) == 1.0

    def test_half_open(self):
        assert compute_face_score(1, 0.5) == 0.5


class TestDetectFaces:
    @patch("faces._get_face_mesh")
    def test_no_mediapipe(self, mock_mesh):
        """Если MediaPipe недоступен — возвращает нули."""
        mock_mesh.return_value = None
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        count, ratio, closed = detect_faces(img)
        assert count == 0
        assert ratio == 0.0
        assert closed is False

    @patch("faces._get_face_mesh")
    def test_no_faces_detected(self, mock_mesh):
        """Если лиц не найдено."""
        mock_result = MagicMock()
        mock_result.multi_face_landmarks = None
        mock_mesh.return_value.process.return_value = mock_result
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        count, ratio, closed = detect_faces(img)
        assert count == 0
