import json
from pathlib import Path

from config import UPLOAD_LOG


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
