# ── Анализ изображений: резкость, яркость, экспозиция ─────────────────────────

from __future__ import annotations

import cv2
import numpy as np

from config import (
    BRIGHTNESS_IDEAL_HIGH,
    BRIGHTNESS_IDEAL_LOW,
    SHARPNESS_HIGH,
    SHARPNESS_LOW,
    SHARPNESS_TERRIBLE,
)


def load_image(path) -> np.ndarray | None:
    """Загружает изображение через OpenCV. Для RAF — извлекает thumbnail через rawpy."""
    path_str = str(path)

    if path_str.lower().endswith(".raf"):
        return _load_raf(path_str)

    img = cv2.imread(path_str)
    return img


def _load_raf(path_str: str) -> np.ndarray | None:
    """Извлекает thumbnail из RAF, при неудаче — полный postprocess."""
    try:
        import rawpy
        with rawpy.imread(path_str) as raw:
            try:
                thumb = raw.extract_thumb()
                if thumb.format == rawpy.ThumbFormat.JPEG:
                    buf = np.frombuffer(thumb.data, dtype=np.uint8)
                    return cv2.imdecode(buf, cv2.IMREAD_COLOR)
            except Exception:
                pass
            # Fallback: полная обработка
            rgb = raw.postprocess()
            return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    except Exception:
        return None


def compute_sharpness(image: np.ndarray) -> float:
    """Вычисляет резкость через вариацию Лапласиана."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return cv2.Laplacian(gray, cv2.CV_64F).var()


def compute_brightness(image: np.ndarray) -> float:
    """Вычисляет среднюю яркость (0–255)."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return float(np.mean(gray))


def normalize_sharpness(sharpness: float) -> float:
    """Нормализует резкость в скор 0–1 (piecewise linear)."""
    if sharpness < SHARPNESS_TERRIBLE:
        return 0.0
    if sharpness < SHARPNESS_LOW:
        return (sharpness - SHARPNESS_TERRIBLE) / (SHARPNESS_LOW - SHARPNESS_TERRIBLE) * 0.5
    if sharpness < SHARPNESS_HIGH:
        return 0.5 + (sharpness - SHARPNESS_LOW) / (SHARPNESS_HIGH - SHARPNESS_LOW) * 0.5
    return 1.0


def score_exposure(brightness: float) -> float:
    """Скор экспозиции: 1.0 в идеальном диапазоне, падает к краям."""
    if BRIGHTNESS_IDEAL_LOW <= brightness <= BRIGHTNESS_IDEAL_HIGH:
        return 1.0
    if brightness < BRIGHTNESS_IDEAL_LOW:
        return max(0.0, brightness / BRIGHTNESS_IDEAL_LOW)
    # brightness > BRIGHTNESS_IDEAL_HIGH
    return max(0.0, (255 - brightness) / (255 - BRIGHTNESS_IDEAL_HIGH))


def analyze_image(image: np.ndarray) -> tuple[float, float, float, float]:
    """Полный анализ: возвращает (sharpness, sharpness_score, brightness, exposure_score)."""
    sharpness = compute_sharpness(image)
    brightness = compute_brightness(image)
    return sharpness, normalize_sharpness(sharpness), brightness, score_exposure(brightness)
