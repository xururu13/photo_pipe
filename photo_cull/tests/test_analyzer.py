import numpy as np
from unittest.mock import patch, MagicMock

from analyzer import (
    compute_sharpness,
    compute_brightness,
    normalize_sharpness,
    score_exposure,
    analyze_image,
    load_image,
)


def _make_image(brightness=128, noise=False):
    """Создаёт тестовое BGR-изображение."""
    img = np.full((100, 100, 3), brightness, dtype=np.uint8)
    if noise:
        rng = np.random.RandomState(42)
        img = (img.astype(np.int16) + rng.randint(-50, 50, img.shape)).clip(0, 255).astype(np.uint8)
    return img


class TestComputeSharpness:
    def test_flat_image_low_sharpness(self):
        img = _make_image(128, noise=False)
        assert compute_sharpness(img) < 1.0

    def test_noisy_image_higher_sharpness(self):
        img = _make_image(128, noise=True)
        assert compute_sharpness(img) > 10.0


class TestComputeBrightness:
    def test_dark_image(self):
        img = _make_image(30)
        assert 25 < compute_brightness(img) < 35

    def test_bright_image(self):
        img = _make_image(220)
        assert 215 < compute_brightness(img) < 225

    def test_mid_image(self):
        img = _make_image(128)
        assert 125 < compute_brightness(img) < 131


class TestNormalizeSharpness:
    def test_zero_below_terrible(self):
        assert normalize_sharpness(10) == 0.0

    def test_max_above_high(self):
        assert normalize_sharpness(1000) == 1.0

    def test_mid_range(self):
        score = normalize_sharpness(500)
        assert 0.5 < score < 1.0

    def test_at_low_boundary(self):
        score = normalize_sharpness(200)
        assert abs(score - 0.5) < 0.01


class TestScoreExposure:
    def test_ideal_range(self):
        assert score_exposure(140) == 1.0
        assert score_exposure(100) == 1.0
        assert score_exposure(180) == 1.0

    def test_dark(self):
        score = score_exposure(50)
        assert 0.0 < score < 1.0

    def test_very_dark(self):
        assert score_exposure(0) == 0.0

    def test_overexposed(self):
        score = score_exposure(230)
        assert 0.0 < score < 1.0

    def test_max_overexposed(self):
        assert score_exposure(255) == 0.0


class TestAnalyzeImage:
    def test_returns_four_values(self):
        img = _make_image(140, noise=True)
        result = analyze_image(img)
        assert len(result) == 4
        sharpness, sharpness_score, brightness, exposure_score = result
        assert sharpness > 0
        assert 0.0 <= sharpness_score <= 1.0
        assert 130 < brightness < 150
        assert exposure_score == 1.0


class TestLoadImage:
    def test_load_jpeg(self, tmp_path):
        import cv2
        img = _make_image(128)
        path = tmp_path / "test.jpg"
        cv2.imwrite(str(path), img)
        loaded = load_image(path)
        assert loaded is not None
        assert loaded.shape[2] == 3

    def test_load_nonexistent(self, tmp_path):
        result = load_image(tmp_path / "missing.jpg")
        assert result is None

    @patch("analyzer._load_raf")
    def test_load_raf_delegates(self, mock_load_raf, tmp_path):
        mock_load_raf.return_value = _make_image(128)
        path = tmp_path / "test.raf"
        path.touch()
        result = load_image(path)
        mock_load_raf.assert_called_once()
        assert result is not None
