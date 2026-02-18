from datetime import datetime
from pathlib import Path

from PIL import Image, ExifTags

from config import SUPPORTED_EXTENSIONS


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
