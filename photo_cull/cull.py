#!/usr/bin/env python3
"""
Photo Cull — автоматический отбор фотографий Fujifilm X-S20.
Анализирует резкость, экспозицию, лица, дубликаты и серии.
Записывает XMP-сайдкары с рейтингом 1–5 для Capture One.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from config import JPEG_EXTENSIONS, RAW_EXTENSIONS, SUPPORTED_EXTENSIONS, PhotoInfo
from analyzer import load_image, analyze_image
from faces import detect_faces, compute_face_score
from duplicates import compute_dhash, find_duplicate_groups
from series import read_exif_timestamp, group_into_series
from rating import rate_photos
from xmp import write_xmp


def find_photos(folder: Path) -> list[Path]:
    """Находит все поддерживаемые фото в папке (без рекурсии, сортировка)."""
    return sorted(
        f for f in folder.iterdir()
        if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS
    )


def pair_raf_jpeg(files: list[Path]) -> list[PhotoInfo]:
    """
    Группирует файлы по имени (stem): RAF + JPEG → один PhotoInfo.
    Если есть оба — анализируем JPEG, рейтинг применяется к обоим через один XMP.
    """
    by_stem: dict[str, dict[str, Path]] = {}
    for f in files:
        stem = f.stem
        ext = f.suffix.lower()
        by_stem.setdefault(stem, {})[ext] = f

    photos = []
    for stem, exts in sorted(by_stem.items()):
        jpeg_path = None
        raf_path = None

        for ext in JPEG_EXTENSIONS:
            if ext in exts:
                jpeg_path = exts[ext]
                break
        for ext in RAW_EXTENSIONS:
            if ext in exts:
                raf_path = exts[ext]
                break

        # Основной файл для анализа — JPEG (быстрее), иначе RAF
        path = jpeg_path or raf_path
        if path is None:
            continue

        photos.append(PhotoInfo(
            path=path,
            jpeg_path=jpeg_path,
            raf_path=raf_path,
            stem=stem,
        ))

    return photos


def analyze_photo(photo: PhotoInfo) -> PhotoInfo:
    """Полный анализ одного фото: загрузка, резкость, яркость, лица, хеш, EXIF."""
    image = load_image(photo.path)
    if image is None:
        print(f"  ⚠️  Не удалось загрузить: {photo.path.name}")
        return photo

    # Резкость и экспозиция
    photo.sharpness, photo.sharpness_score, photo.brightness, photo.exposure_score = (
        analyze_image(image)
    )

    # Лица
    try:
        photo.face_count, photo.eyes_open_ratio, photo.all_eyes_closed = (
            detect_faces(image)
        )
        photo.face_score = compute_face_score(photo.face_count, photo.eyes_open_ratio)
    except Exception:
        pass  # face_score остаётся нейтральным

    # dHash
    try:
        photo.dhash = compute_dhash(image)
    except Exception:
        pass

    # EXIF timestamp
    exif_path = photo.jpeg_path or photo.path
    photo.timestamp = read_exif_timestamp(exif_path)

    return photo


def write_all_xmp(photos: list[PhotoInfo], dry_run: bool = False) -> int:
    """Записывает XMP-сайдкары для всех фото. Возвращает количество записанных."""
    written = 0
    for photo in photos:
        try:
            xmp_path = write_xmp(photo.path, photo.rating, dry_run=dry_run)
            if xmp_path:
                written += 1
        except Exception as e:
            print(f"  ⚠️  Ошибка записи XMP для {photo.stem}: {e}")
    return written


def print_summary(photos: list[PhotoInfo], written: int, dry_run: bool):
    """Печатает итоговую статистику."""
    rating_counts = {r: 0 for r in range(1, 6)}
    for p in photos:
        rating_counts[p.rating] += 1

    stars = {1: "★☆☆☆☆", 2: "★★☆☆☆", 3: "★★★☆☆", 4: "★★★★☆", 5: "★★★★★"}

    print(f"\n{'─' * 50}")
    print(f"  📊 Итого: {len(photos)} фото")
    for r in range(1, 6):
        count = rating_counts[r]
        if count > 0:
            print(f"     {stars[r]}  ({r}): {count}")

    dup_count = sum(1 for p in photos if p.duplicate_group >= 0)
    series_count = sum(1 for p in photos if p.series_group >= 0)
    if dup_count:
        print(f"  🔄 Дубликатов: {dup_count}")
    if series_count:
        print(f"  📸 В сериях: {series_count}")

    if dry_run:
        print(f"  🏷️  XMP-файлов (dry-run): {written}")
    else:
        print(f"  🏷️  XMP-файлов записано: {written}")
    print(f"{'─' * 50}")


def process_folder(
    folder: Path,
    dry_run: bool = False,
    verbose: bool = False,
    ai_cull: bool = False,
    ollama_model: str = "llava",
    ollama_url: str = "http://localhost:11434",
):
    """Основной пайплайн обработки папки."""
    print(f"\n📂 Сканирование: {folder}")

    # 1. Поиск файлов
    files = find_photos(folder)
    if not files:
        print("  ❌ Фото не найдены")
        return

    # 2. Группировка RAF+JPEG
    photos = pair_raf_jpeg(files)
    print(f"  📷 Найдено: {len(photos)} фото ({len(files)} файлов)")

    # 3. Анализ каждого фото
    if ai_cull:
        from ai_analyzer import analyze_photo_ai

        print(f"  🤖 AI-анализ ({ollama_model})...")
        for i, photo in enumerate(photos):
            analyze_photo_ai(photo, model=ollama_model, ollama_url=ollama_url)
            # dHash и EXIF timestamp нужны для дубликатов и серий
            try:
                from analyzer import load_image
                image = load_image(photo.path)
                if image is not None:
                    photo.dhash = compute_dhash(image)
            except Exception:
                pass
            exif_path = photo.jpeg_path or photo.path
            photo.timestamp = read_exif_timestamp(exif_path)
            if verbose:
                print(f"     [{i+1}/{len(photos)}] {photo.stem}: "
                      f"sharp={photo.sharpness_score:.2f} expo={photo.exposure_score:.2f} "
                      f"faces={photo.face_count} comp={photo.ai_score:.2f}")
    else:
        print("  🔍 Анализ...")
        for i, photo in enumerate(photos):
            analyze_photo(photo)
            if verbose:
                print(f"     [{i+1}/{len(photos)}] {photo.stem}: "
                      f"sharp={photo.sharpness:.0f} bright={photo.brightness:.0f} "
                      f"faces={photo.face_count}")

    # 4. Поиск дубликатов
    photos = find_duplicate_groups(photos)

    # 5. Группировка серий
    photos = group_into_series(photos)

    # 6. Рейтинг
    photos = rate_photos(photos, ai_mode=ai_cull)

    if verbose:
        for p in photos:
            print(f"     {p.stem}: ★{p.rating} (score={p.composite_score:.2f}, "
                  f"{p.rating_reason})")

    # 7. Запись XMP
    mode = "dry-run" if dry_run else "запись"
    print(f"  🏷️  XMP ({mode})...")
    written = write_all_xmp(photos, dry_run=dry_run)

    # 8. Итоги
    print_summary(photos, written, dry_run)


def main():
    parser = argparse.ArgumentParser(
        description="Photo Cull — автоматический отбор фотографий"
    )
    parser.add_argument("folder", type=Path, help="Папка с фотографиями")
    parser.add_argument("--dry-run", action="store_true",
                        help="Не записывать XMP-файлы")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Подробный вывод")
    parser.add_argument("--ai-cull", action="store_true",
                        help="Использовать Ollama vision вместо алгоритмического анализа")
    parser.add_argument("--ollama-model", default="llava",
                        help="Ollama model (default: llava)")
    parser.add_argument("--ollama-url", default="http://localhost:11434",
                        help="Ollama API URL (default: http://localhost:11434)")

    args = parser.parse_args()

    if not args.folder.is_dir():
        print(f"❌ Папка не найдена: {args.folder}")
        sys.exit(1)

    process_folder(
        args.folder,
        dry_run=args.dry_run,
        verbose=args.verbose,
        ai_cull=args.ai_cull,
        ollama_model=args.ollama_model,
        ollama_url=args.ollama_url,
    )


if __name__ == "__main__":
    main()
