# ── Настройки photo_cull ──────────────────────────────────────────────────────

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

# Поддерживаемые форматы
JPEG_EXTENSIONS = {".jpg", ".jpeg"}
RAW_EXTENSIONS = {".raf"}
SUPPORTED_EXTENSIONS = JPEG_EXTENSIONS | RAW_EXTENSIONS

# ── Пороги анализа ────────────────────────────────────────────────────────────

# Резкость (Laplacian variance)
SHARPNESS_TERRIBLE = 50       # ниже → rating 1 (hard rule)
SHARPNESS_LOW = 200           # нижняя граница нормы
SHARPNESS_HIGH = 800          # верхняя граница (всё выше → max)

# Яркость (средняя яркость, 0–255)
BRIGHTNESS_IDEAL_LOW = 100    # нижняя граница идеального диапазона
BRIGHTNESS_IDEAL_HIGH = 180   # верхняя граница идеального диапазона

# Лица — Eye Aspect Ratio
EAR_CLOSED_THRESHOLD = 0.20   # ниже → глаз закрыт

# Дубликаты — dHash
DHASH_SIZE = 8                # размер хеша (8×8 → 64 бита)
DHASH_THRESHOLD = 10          # расстояние Хэмминга ≤ → дубликат

# Серии — временной порог
SERIES_GAP_SECONDS = 3.0      # ≤3с между кадрами → одна серия

# ── Веса скоринга ─────────────────────────────────────────────────────────────

WEIGHT_SHARPNESS = 0.35
WEIGHT_EXPOSURE = 0.20
WEIGHT_FACES = 0.25
WEIGHT_UNIQUENESS = 0.10
WEIGHT_SERIES = 0.10

# AI-режим: веса скоринга (замена sharpness/exposure/faces на AI-оценки + composition)
AI_WEIGHT_SHARPNESS = 0.25
AI_WEIGHT_EXPOSURE = 0.15
AI_WEIGHT_FACES = 0.20
AI_WEIGHT_COMPOSITION = 0.20
AI_WEIGHT_UNIQUENESS = 0.10
AI_WEIGHT_SERIES = 0.10

# Пороги рейтинга (soft rules)
RATING_THRESHOLD_2 = 0.35     # score < 0.35 → rating 2
RATING_THRESHOLD_3 = 0.55     # score < 0.55 → rating 3
RATING_THRESHOLD_4 = 0.80     # score < 0.80 → rating 4
HARD_RULE_5_MIN_SCORE = 0.85  # min score для hard rule → rating 5

# Нейтральный скор лиц (когда лиц нет)
FACES_NEUTRAL_SCORE = 0.7


# ── Данные фотографии ─────────────────────────────────────────────────────────

@dataclass
class PhotoInfo:
    """Все данные о фото, накапливаемые по ходу пайплайна."""
    path: Path                           # путь к основному файлу (JPEG или RAF)
    jpeg_path: Path | None = None        # JPEG-файл (если есть пара)
    raf_path: Path | None = None         # RAF-файл (если есть пара)
    stem: str = ""                       # имя без расширения (DSCF1234)

    # Анализ
    sharpness: float = 0.0               # Laplacian variance
    brightness: float = 0.0              # средняя яркость (0–255)
    exposure_score: float = 0.0          # скор экспозиции (0–1)
    sharpness_score: float = 0.0         # нормализованный скор резкости (0–1)

    # Лица
    face_count: int = 0                  # количество обнаруженных лиц
    eyes_open_ratio: float = 0.0         # доля открытых глаз
    all_eyes_closed: bool = False        # все глаза закрыты
    face_score: float = FACES_NEUTRAL_SCORE

    # Дубликаты
    dhash: str = ""                      # perceptual hash
    duplicate_group: int = -1            # id группы дубликатов (-1 = уникальный)
    is_worst_duplicate: bool = False     # худший в группе дубликатов
    uniqueness_score: float = 1.0        # 1.0 уникальный/лучший, 0.3 худший

    # Серии
    timestamp: datetime | None = None    # EXIF DateTimeOriginal
    series_group: int = -1               # id серии (-1 = нет серии)
    is_best_in_series: bool = False      # лучший в серии
    series_score: float = 0.5            # 1.0 лучший, 0.5 нет серии, 0.3 остальные

    # AI-анализ
    ai_score: float = 0.0               # композиция/эстетика от AI (0–1)

    # Итоговый рейтинг
    composite_score: float = 0.0         # взвешенный скор (0–1)
    rating: int = 3                      # итоговый рейтинг (1–5)
    rating_reason: str = ""              # причина рейтинга (для отладки)
