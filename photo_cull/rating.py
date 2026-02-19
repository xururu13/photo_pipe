# ── Рейтинг: композитный скор и правила ───────────────────────────────────────

from __future__ import annotations

from config import (
    AI_WEIGHT_COMPOSITION,
    AI_WEIGHT_EXPOSURE,
    AI_WEIGHT_FACES,
    AI_WEIGHT_SERIES,
    AI_WEIGHT_SHARPNESS,
    AI_WEIGHT_UNIQUENESS,
    HARD_RULE_5_MIN_SCORE,
    RATING_THRESHOLD_2,
    RATING_THRESHOLD_3,
    RATING_THRESHOLD_4,
    SHARPNESS_TERRIBLE,
    WEIGHT_EXPOSURE,
    WEIGHT_FACES,
    WEIGHT_SERIES,
    WEIGHT_SHARPNESS,
    WEIGHT_UNIQUENESS,
    PhotoInfo,
)


def compute_composite_score(photo: PhotoInfo) -> float:
    """Вычисляет взвешенный композитный скор (0–1)."""
    return (
        WEIGHT_SHARPNESS * photo.sharpness_score
        + WEIGHT_EXPOSURE * photo.exposure_score
        + WEIGHT_FACES * photo.face_score
        + WEIGHT_UNIQUENESS * photo.uniqueness_score
        + WEIGHT_SERIES * photo.series_score
    )


def compute_composite_score_ai(photo: PhotoInfo) -> float:
    """Вычисляет взвешенный композитный скор (0–1) для AI-режима (включая composition)."""
    return (
        AI_WEIGHT_SHARPNESS * photo.sharpness_score
        + AI_WEIGHT_EXPOSURE * photo.exposure_score
        + AI_WEIGHT_FACES * photo.face_score
        + AI_WEIGHT_COMPOSITION * photo.ai_score
        + AI_WEIGHT_UNIQUENESS * photo.uniqueness_score
        + AI_WEIGHT_SERIES * photo.series_score
    )


def apply_rating(photo: PhotoInfo, ai_mode: bool = False) -> PhotoInfo:
    """Вычисляет композитный скор и назначает рейтинг 1–5."""
    if ai_mode:
        photo.composite_score = compute_composite_score_ai(photo)
    else:
        photo.composite_score = compute_composite_score(photo)

    # Hard rule → Rating 1
    if photo.sharpness < SHARPNESS_TERRIBLE:
        photo.rating = 1
        photo.rating_reason = "hard: low sharpness"
        return photo

    if photo.all_eyes_closed and not ai_mode:
        photo.rating = 1
        photo.rating_reason = "hard: all eyes closed"
        return photo

    if photo.is_worst_duplicate:
        photo.rating = 1
        photo.rating_reason = "hard: worst duplicate"
        return photo

    # Hard rule → Rating 5
    if (
        photo.is_best_in_series
        and photo.face_count > 0
        and not photo.all_eyes_closed
        and photo.composite_score >= HARD_RULE_5_MIN_SCORE
    ):
        photo.rating = 5
        photo.rating_reason = "hard: best in series + faces + eyes open + high score"
        return photo

    # Soft rules по скору
    score = photo.composite_score
    if score < RATING_THRESHOLD_2:
        photo.rating = 2
        photo.rating_reason = f"soft: score {score:.2f} < {RATING_THRESHOLD_2}"
    elif score < RATING_THRESHOLD_3:
        photo.rating = 3
        photo.rating_reason = f"soft: score {score:.2f} < {RATING_THRESHOLD_3}"
    elif score < RATING_THRESHOLD_4:
        photo.rating = 4
        photo.rating_reason = f"soft: score {score:.2f} < {RATING_THRESHOLD_4}"
    else:
        photo.rating = 5
        photo.rating_reason = f"soft: score {score:.2f} >= {RATING_THRESHOLD_4}"

    return photo


def rate_photos(photos: list[PhotoInfo], ai_mode: bool = False) -> list[PhotoInfo]:
    """Назначает рейтинг всем фото."""
    for photo in photos:
        apply_rating(photo, ai_mode=ai_mode)
    return photos
