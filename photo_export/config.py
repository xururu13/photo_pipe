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
