# ── Группировка серий (burst detection) ───────────────────────────────────────

from __future__ import annotations

from datetime import datetime

from PIL import Image, ExifTags

from config import SERIES_GAP_SECONDS, PhotoInfo


def read_exif_timestamp(path) -> datetime | None:
    """Читает EXIF DateTimeOriginal из JPEG-файла."""
    try:
        with Image.open(str(path)) as img:
            exif_data = img._getexif()
            if not exif_data:
                return None
            for tag_id, value in exif_data.items():
                if ExifTags.TAGS.get(tag_id) == "DateTimeOriginal":
                    return datetime.strptime(value, "%Y:%m:%d %H:%M:%S")
    except Exception:
        pass
    return None


def group_into_series(photos: list[PhotoInfo]) -> list[PhotoInfo]:
    """
    Группирует фото в серии по временному порогу (≤3с между кадрами).
    Заполняет series_group и is_best_in_series / series_score.
    """
    # Фильтруем фото с таймстемпами и сортируем
    timed = [(i, p) for i, p in enumerate(photos) if p.timestamp is not None]
    if len(timed) < 2:
        return photos

    timed.sort(key=lambda x: x[1].timestamp)

    # Группируем по временному интервалу
    series: list[list[int]] = []
    current_series = [timed[0][0]]

    for k in range(1, len(timed)):
        prev_idx, prev_photo = timed[k - 1]
        curr_idx, curr_photo = timed[k]
        gap = (curr_photo.timestamp - prev_photo.timestamp).total_seconds()

        if gap <= SERIES_GAP_SECONDS:
            current_series.append(curr_idx)
        else:
            if len(current_series) >= 2:
                series.append(current_series)
            current_series = [curr_idx]

    if len(current_series) >= 2:
        series.append(current_series)

    # Назначаем серии и лучших
    for group_id, members in enumerate(series):
        for idx in members:
            photos[idx].series_group = group_id
            photos[idx].series_score = 0.3

        # Лучший — с наибольшей резкостью
        best_idx = max(members, key=lambda i: photos[i].sharpness)
        photos[best_idx].is_best_in_series = True
        photos[best_idx].series_score = 1.0

    return photos
