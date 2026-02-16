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
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import requests
from PIL import Image, ExifTags
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

# ── Настройки ──────────────────────────────────────────────────────────────

SCOPES = [
    "https://www.googleapis.com/auth/photoslibrary",
    "https://www.googleapis.com/auth/photoslibrary.readonly",
    "https://www.googleapis.com/auth/photoslibrary.appendonly",
    "https://www.googleapis.com/auth/photoslibrary.sharing",
]

API_BASE = "https://photoslibrary.googleapis.com/v1"

# Поддерживаемые форматы (Google Photos принимает эти типы)
SUPPORTED_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic", ".heif",
    ".bmp", ".tiff", ".tif", ".avif", ".ico",
    # RAW форматы (включая Fujifilm RAF)
    ".raw", ".raf", ".cr2", ".cr3", ".nef", ".arw", ".dng",
    ".orf", ".rw2", ".pef", ".srw",
    # Видео
    ".mp4", ".mov", ".avi", ".mkv", ".m4v", ".3gp", ".wmv", ".mpg",
}

# Файл для отслеживания уже загруженных файлов
UPLOAD_LOG = ".gphotos_uploaded.json"

# Максимальный размер файла (Google Photos лимит)
MAX_FILE_SIZE = 200 * 1024 * 1024  # 200 MB для фото; видео — 10 GB

# ── Аутентификация ─────────────────────────────────────────────────────────

def authenticate(credentials_path: str = "credentials.json",
                 token_path: str = "token.json") -> Credentials:
    """
    OAuth2 аутентификация. При первом запуске откроет браузер.
    Токен сохраняется в token.json для последующих запусков.
    """
    creds = None

    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("🔄 Обновляю токен...")
            creds.refresh(Request())
        else:
            if not os.path.exists(credentials_path):
                print(f"❌ Файл {credentials_path} не найден!")
                print("   Скачай его из Google Cloud Console (см. README).")
                sys.exit(1)

            print("🌐 Открываю браузер для авторизации...")
            flow = InstalledAppFlow.from_client_secrets_file(
                credentials_path, SCOPES
            )
            creds = flow.run_local_server(port=0)

        with open(token_path, "w") as f:
            f.write(creds.to_json())
        print("✅ Авторизация успешна, токен сохранён.")

    return creds


# ── Работа с API ───────────────────────────────────────────────────────────

class GooglePhotosClient:
    """Клиент для работы с Google Photos Library API."""

    def __init__(self, creds: Credentials):
        self.creds = creds
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {creds.token}",
        })

    def _refresh_if_needed(self):
        """Обновляет токен, если он истёк."""
        if self.creds.expired:
            self.creds.refresh(Request())
            self.session.headers["Authorization"] = f"Bearer {self.creds.token}"

    def list_albums(self) -> dict:
        """Получает все существующие альбомы. Возвращает {title: id}."""
        self._refresh_if_needed()
        albums = {}
        page_token = None

        while True:
            params = {"pageSize": 50}
            if page_token:
                params["pageToken"] = page_token

            resp = self.session.get(f"{API_BASE}/albums", params=params)
            resp.raise_for_status()
            data = resp.json()

            for album in data.get("albums", []):
                albums[album["title"]] = album["id"]

            page_token = data.get("nextPageToken")
            if not page_token:
                break

        return albums

    def create_album(self, title: str) -> str:
        """Создаёт альбом и возвращает его ID."""
        self._refresh_if_needed()
        resp = self.session.post(
            f"{API_BASE}/albums",
            json={"album": {"title": title}},
        )
        resp.raise_for_status()
        album_id = resp.json()["id"]
        return album_id

    def get_or_create_album(self, title: str, existing_albums: dict) -> str:
        """Возвращает ID альбома, создавая его при необходимости."""
        if title in existing_albums:
            return existing_albums[title]

        album_id = self.create_album(title)
        existing_albums[title] = album_id
        return album_id

    def upload_file(self, filepath: Path, filename_override: str | None = None) -> str | None:
        """
        Загружает файл и возвращает upload token.
        Это первый шаг — файл ещё не привязан к библиотеке.
        """
        self._refresh_if_needed()
        filename = filename_override or filepath.name
        filesize = filepath.stat().st_size

        headers = {
            "Authorization": f"Bearer {self.creds.token}",
            "Content-Type": "application/octet-stream",
            "X-Goog-Upload-File-Name": filename.encode("utf-8"),
            "X-Goog-Upload-Protocol": "raw",
        }

        with open(filepath, "rb") as f:
            resp = requests.post(
                f"{API_BASE}/uploads",
                headers=headers,
                data=f,
            )

        if resp.status_code == 200:
            return resp.text  # upload token
        else:
            print(f"  ⚠️  Ошибка загрузки {filename}: {resp.status_code} {resp.text}")
            return None

    def add_to_album(self, upload_tokens: list[str], album_id: str,
                     descriptions: list[str] | None = None) -> set[int]:
        """
        Создаёт media items из upload tokens и добавляет в альбом.
        Google Photos API позволяет до 50 items за один запрос.
        Возвращает множество индексов успешно добавленных элементов.
        """
        self._refresh_if_needed()
        success_indices = set()

        # Разбиваем на батчи по 50
        for i in range(0, len(upload_tokens), 50):
            batch_tokens = upload_tokens[i:i + 50]
            batch_descs = (descriptions[i:i + 50]
                           if descriptions else [None] * len(batch_tokens))

            new_items = []
            for token, desc in zip(batch_tokens, batch_descs):
                item = {"simpleMediaItem": {"uploadToken": token}}
                if desc:
                    item["description"] = desc
                new_items.append(item)

            body = {
                "albumId": album_id,
                "newMediaItems": new_items,
            }

            resp = self.session.post(
                f"{API_BASE}/mediaItems:batchCreate",
                json=body,
            )

            if resp.status_code == 200:
                results = resp.json().get("newMediaItemResults", [])
                for j, r in enumerate(results):
                    status = r.get("status", {})
                    if status.get("message") in ("Success", "OK") or status.get("code", -1) == 0:
                        success_indices.add(i + j)
                    else:
                        print(f"  ⚠️  Элемент не добавлен: {status}")
            else:
                print(f"  ⚠️  Ошибка batchCreate: {resp.status_code} {resp.text}")

            # Небольшая пауза между батчами
            if i + 50 < len(upload_tokens):
                time.sleep(1)

        return success_indices

    def list_album_items(self, album_id: str) -> dict[str, dict]:
        """
        Получает все медиа-элементы в альбоме.
        Возвращает {filename: {id, creationTime, width, height}}.
        """
        self._refresh_if_needed()
        items = {}
        page_token = None

        while True:
            body = {"albumId": album_id, "pageSize": 100}
            if page_token:
                body["pageToken"] = page_token

            resp = self.session.post(
                f"{API_BASE}/mediaItems:search",
                json=body,
            )
            resp.raise_for_status()
            data = resp.json()

            for item in data.get("mediaItems", []):
                metadata = item.get("mediaMetadata", {})
                items[item["filename"]] = {
                    "id": item["id"],
                    "creationTime": metadata.get("creationTime", ""),
                    "width": metadata.get("width", ""),
                    "height": metadata.get("height", ""),
                }

            page_token = data.get("nextPageToken")
            if not page_token:
                break

        return items

    def remove_from_album(self, album_id: str, media_item_ids: list[str]):
        """
        Удаляет медиа-элементы из альбома (не из библиотеки).
        """
        self._refresh_if_needed()
        resp = self.session.post(
            f"{API_BASE}/albums/{album_id}:batchRemoveMediaItems",
            json={"mediaItemIds": media_item_ids},
        )
        resp.raise_for_status()


# ── Лог загруженных файлов ─────────────────────────────────────────────────

def load_upload_log(export_dir: Path) -> tuple[set, dict]:
    """Загружает список ранее загруженных файлов и кеш альбомов."""
    log_path = export_dir / UPLOAD_LOG
    if log_path.exists():
        with open(log_path) as f:
            data = json.load(f)
            return set(data.get("uploaded", [])), data.get("albums", {})
    return set(), {}


def save_upload_log(export_dir: Path, uploaded: set, albums: dict):
    """Сохраняет список загруженных файлов и кеш альбомов."""
    log_path = export_dir / UPLOAD_LOG
    with open(log_path, "w") as f:
        json.dump({"uploaded": sorted(uploaded), "albums": albums},
                  f, indent=2, ensure_ascii=False)


# ── Основная логика ────────────────────────────────────────────────────────

def find_media_files(folder: Path) -> list[Path]:
    """Находит все поддерживаемые медиафайлы в папке (без рекурсии)."""
    files = []
    for f in sorted(folder.iterdir()):
        if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS:
            files.append(f)
    return files


def format_size(size_bytes: int) -> str:
    """Форматирует размер в человекочитаемый вид."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


def get_local_file_info(filepath: Path) -> dict:
    """Возвращает информацию о локальном файле: размер, дату, размеры изображения."""
    stat = filepath.stat()
    info = {
        "filename": filepath.name,
        "size": stat.st_size,
        "date": None,
        "width": None,
        "height": None,
    }

    # Пробуем получить EXIF DateTimeOriginal
    try:
        with Image.open(filepath) as img:
            info["width"], info["height"] = img.size
            exif_data = img._getexif()
            if exif_data:
                for tag_id, value in exif_data.items():
                    tag_name = ExifTags.TAGS.get(tag_id, "")
                    if tag_name == "DateTimeOriginal":
                        info["date"] = datetime.strptime(value, "%Y:%m:%d %H:%M:%S")
                        break
    except Exception:
        pass

    if info["date"] is None:
        info["date"] = datetime.fromtimestamp(stat.st_mtime)

    return info


def format_remote_date(creation_time: str) -> str:
    """Форматирует дату из Google Photos API (ISO 8601)."""
    if not creation_time:
        return "?"
    try:
        dt = datetime.fromisoformat(creation_time.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return creation_time[:16]


def prompt_duplicate(filepath: Path, remote_info: dict) -> str:
    """
    Показывает сравнение локального и удалённого файла,
    запрашивает действие: Skip / Replace / Rename.
    Возвращает 's', 'r' или 'n'.
    """
    local = get_local_file_info(filepath)

    local_date = local["date"].strftime("%Y-%m-%d %H:%M") if local["date"] else "?"
    local_dims = (f"{local['width']}×{local['height']}"
                  if local["width"] and local["height"] else "?")

    remote_date = format_remote_date(remote_info.get("creationTime", ""))
    rw, rh = remote_info.get("width", ""), remote_info.get("height", "")
    remote_dims = f"{rw}×{rh}" if rw and rh else "?"

    print(f"\n  ⚠️  Дубликат найден: {filepath.name}")
    print(f"       Локальный:  {local_date}  |  {format_size(local['size']):>8}  |  {local_dims}")
    print(f"       Удалённый:  {remote_date}  |  {'—':>8}  |  {remote_dims}")

    while True:
        choice = input("       [S]kip / [R]eplace / Re[n]ame? ").strip().lower()
        if choice in ("s", "r", "n"):
            return choice
        print("       Введите s, r или n")


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
