#!/usr/bin/env python3
"""
Google Photos Auto-Uploader
============================
Скрипт для автоматической загрузки фотографий из подпапок в Google Photos
с созданием альбомов по имени каждой подпапки.

Структура папок:
    export/
    ├── 2025-02-15_Wedding/
    │   ├── IMG_001.jpg
    │   └── IMG_002.jpg
    ├── 2025-03-01_Birthday/
    │   ├── IMG_010.jpg
    │   └── IMG_011.jpg
    └── ...

Результат в Google Photos:
    Альбом "2025-02-15_Wedding"  → IMG_001.jpg, IMG_002.jpg
    Альбом "2025-03-01_Birthday" → IMG_010.jpg, IMG_011.jpg

Использование:
    python google_photos_upload.py /path/to/export
    python google_photos_upload.py /path/to/export --dry-run
    python google_photos_upload.py /path/to/export --skip-existing
"""

import argparse
import sys
import time
from pathlib import Path

import requests

from auth import authenticate
from client import GooglePhotosClient
from files import find_media_files, format_size, prompt_duplicate
from log import load_upload_log, save_upload_log


def process_folder(client: GooglePhotosClient, folder: Path,
                   existing_albums: dict, uploaded_log: set,
                   skip_existing: bool, dry_run: bool,
                   can_read_library: bool = True) -> tuple[int, int]:
    """
    Обрабатывает одну подпапку: создаёт альбом, загружает фото.
    Возвращает (uploaded_count, skipped_count).
    """
    album_name = folder.name
    files = find_media_files(folder)

    if not files:
        return 0, 0

    # Фильтруем уже загруженные
    if skip_existing:
        new_files = [f for f in files if str(f) not in uploaded_log]
        skipped = len(files) - len(new_files)
        files = new_files
    else:
        skipped = 0

    if not files:
        print(f"  📁 {album_name}: все файлы уже загружены ({skipped} пропущено)")
        return 0, skipped

    total_size = sum(f.stat().st_size for f in files)
    print(f"\n  📁 {album_name}")
    print(f"     {len(files)} файлов ({format_size(total_size)})"
          + (f", {skipped} пропущено" if skipped else ""))

    if dry_run:
        for f in files:
            print(f"     → {f.name} ({format_size(f.stat().st_size)})")
        return 0, skipped

    # Создаём / находим альбом
    album_existed = album_name in existing_albums
    album_id = client.get_or_create_album(album_name, existing_albums)
    print(f"     Альбом: {'найден' if album_existed else 'создан'}")

    # Получаем содержимое альбома для проверки дубликатов
    if can_read_library:
        remote_items = client.list_album_items(album_id)
        if remote_items:
            print(f"     В альбоме уже {len(remote_items)} файлов")
    else:
        remote_items = {}

    # Загружаем файлы
    upload_tokens = []
    uploaded_files = []
    file_index = 0

    for i, filepath in enumerate(files, 1):
        filename = filepath.name

        # Проверка дубликатов по имени файла
        if filename in remote_items:
            choice = prompt_duplicate(filepath, remote_items[filename])
            if choice == "s":
                skipped += 1
                continue
            elif choice == "r":
                # Удаляем старый элемент из альбома
                old_id = remote_items[filename]["id"]
                try:
                    client.remove_from_album(album_id, [old_id])
                    print(f"       ✓ Старый файл удалён из альбома")
                except Exception as e:
                    print(f"       ⚠️  Не удалось удалить старый файл: {e}")
            elif choice == "n":
                new_name = input("       Новое имя файла: ").strip()
                if not new_name:
                    print("       Пропускаю (пустое имя)")
                    skipped += 1
                    continue
                # Для переименования: создаём симлинк/копию с новым именем
                # Google Photos берёт имя из X-Goog-Upload-File-Name заголовка
                # поэтому просто запомним новое имя для загрузки
                filepath = (filepath, new_name)  # tuple сигнализирует о переименовании

        file_index += 1
        # Определяем реальный путь и имя для загрузки
        if isinstance(filepath, tuple):
            real_path, upload_name = filepath
            display_name = f"{real_path.name} → {upload_name}"
        else:
            real_path = filepath
            upload_name = None
            display_name = filepath.name

        print(f"     ⬆️  [{file_index}/{len(files)}] {display_name}", end="", flush=True)

        token = client.upload_file(real_path, filename_override=upload_name)
        if token:
            upload_tokens.append(token)
            uploaded_files.append(real_path)
            print(" ✓")
        else:
            print(" ✗")

        # Rate limiting: пауза каждые 20 файлов
        if file_index % 20 == 0:
            time.sleep(2)

    if not upload_tokens:
        print("     ⚠️  Ни один файл не загружен")
        return 0, skipped

    # Добавляем в альбом
    print(f"     📎 Добавляю {len(upload_tokens)} файлов в альбом...", end="", flush=True)
    success_indices = client.add_to_album(upload_tokens, album_id)
    added = len(success_indices)
    print(f" ✓ ({added} добавлено)")

    # Обновляем лог — только успешно добавленные
    for idx in success_indices:
        uploaded_log.add(str(uploaded_files[idx]))

    return added, skipped


def main():
    parser = argparse.ArgumentParser(
        description="Загрузка фотографий из подпапок в Google Photos с созданием альбомов.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры:
  %(prog)s ~/Photos/export                  Загрузить все подпапки
  %(prog)s ~/Photos/export --dry-run        Показать план без загрузки
  %(prog)s ~/Photos/export --skip-existing  Пропустить уже загруженные
  %(prog)s ~/Photos/export --credentials ~/keys/creds.json
        """,
    )

    parser.add_argument(
        "export_dir",
        type=Path,
        help="Папка с подпапками-альбомами для загрузки",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Показать что будет загружено, без реальной загрузки",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        default=True,
        help="Пропускать ранее загруженные файлы (по умолчанию: да)",
    )
    parser.add_argument(
        "--no-skip-existing",
        action="store_false",
        dest="skip_existing",
        help="Загружать все файлы, даже если они уже были загружены ранее",
    )
    parser.add_argument(
        "--credentials",
        type=Path,
        default=Path("credentials.json"),
        help="Путь к credentials.json (по умолчанию: ./credentials.json)",
    )
    parser.add_argument(
        "--token",
        type=Path,
        default=Path("token.json"),
        help="Путь к token.json (по умолчанию: ./token.json)",
    )

    args = parser.parse_args()

    # Проверяем папку
    if not args.export_dir.is_dir():
        print(f"❌ Папка не найдена: {args.export_dir}")
        sys.exit(1)

    # Находим подпапки
    subfolders = sorted([
        d for d in args.export_dir.iterdir()
        if d.is_dir() and not d.name.startswith(".")
    ])

    if not subfolders:
        print(f"❌ В {args.export_dir} нет подпапок для загрузки")
        sys.exit(1)

    # Предварительный подсчёт
    total_files = 0
    total_size = 0
    for folder in subfolders:
        files = find_media_files(folder)
        total_files += len(files)
        total_size += sum(f.stat().st_size for f in files)

    print("=" * 60)
    print("📸 Google Photos Auto-Uploader")
    print("=" * 60)
    print(f"📂 Источник:  {args.export_dir}")
    print(f"📁 Альбомов:  {len(subfolders)}")
    print(f"🖼️  Файлов:    {total_files}")
    print(f"💾 Размер:    {format_size(total_size)}")

    if args.dry_run:
        print(f"🔍 Режим:     DRY RUN (без загрузки)")

    print("=" * 60)

    # Аутентификация (пропускаем в dry-run только если нет credentials)
    if not args.dry_run:
        creds = authenticate(
            str(args.credentials),
            str(args.token),
        )
        client = GooglePhotosClient(creds)

        # Получаем список существующих альбомов
        print("\n📋 Загружаю список существующих альбомов...")
        try:
            existing_albums = client.list_albums()
            print(f"   Найдено {len(existing_albums)} альбомов")
            can_read_library = True
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 403:
                print("   ⚠️  Нет доступа на чтение (403). Приложение не верифицировано?")
                print("   Продолжаю без проверки дубликатов — только загрузка.")
                existing_albums = {}
                can_read_library = False
            else:
                raise
    else:
        client = None
        existing_albums = {}
        can_read_library = False

    # Загружаем лог
    uploaded_log, cached_albums = load_upload_log(args.export_dir)
    if cached_albums and not can_read_library:
        existing_albums.update(cached_albums)
        print(f"📝 Из кеша загружено {len(cached_albums)} альбомов")
    if uploaded_log:
        print(f"📝 В логе {len(uploaded_log)} ранее загруженных файлов")

    # Обрабатываем каждую подпапку
    grand_uploaded = 0
    grand_skipped = 0

    for folder in subfolders:
        uploaded, skipped = process_folder(
            client, folder, existing_albums, uploaded_log,
            args.skip_existing, args.dry_run, can_read_library,
        )
        grand_uploaded += uploaded
        grand_skipped += skipped

    # Сохраняем лог
    if not args.dry_run:
        save_upload_log(args.export_dir, uploaded_log, existing_albums)

    # Итоги
    print("\n" + "=" * 60)
    print("📊 Итоги:")
    print(f"   ✅ Загружено:  {grand_uploaded} файлов")
    print(f"   ⏭️  Пропущено: {grand_skipped} файлов")
    print("=" * 60)


if __name__ == "__main__":
    main()
