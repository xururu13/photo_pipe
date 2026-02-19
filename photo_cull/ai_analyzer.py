# ── AI-анализ через Ollama vision ─────────────────────────────────────────────

from __future__ import annotations

import base64
import json
import logging
import re
from pathlib import Path

import requests

from config import PhotoInfo

logger = logging.getLogger(__name__)

OLLAMA_DEFAULT_MODEL = "llava"
OLLAMA_DEFAULT_URL = "http://localhost:11434"


def _encode_image(path: Path) -> str:
    """Base64-кодирование файла изображения."""
    return base64.b64encode(path.read_bytes()).decode("utf-8")


def _build_prompt() -> str:
    """Структурированный промпт для оценки фото."""
    return (
        "Analyze this photograph for technical and aesthetic quality.\n"
        "Return ONLY valid JSON with these fields:\n"
        '- sharpness: 0.0-1.0 (focus quality, 0=very blurry, 1=tack sharp)\n'
        '- exposure: 0.0-1.0 (brightness correctness, 0=very dark/bright, 1=perfect)\n'
        '- face_quality: 0.0-1.0 (face/eyes quality if faces present, 0.7 if no faces)\n'
        '- face_count: integer (number of human faces)\n'
        '- eyes_closed: true/false (are ALL eyes in the photo closed)\n'
        '- composition: 0.0-1.0 (framing, balance, visual appeal)\n'
    )


def _parse_response(text: str) -> dict | None:
    """Извлекает JSON из ответа модели (может содержать markdown-обёртку и лишний текст)."""
    cleaned = text.strip()

    # Извлекаем содержимое между ``` ... ``` если есть
    fence_match = re.search(r"```(?:json)?\s*\n(.*?)\n\s*```", cleaned, re.DOTALL)
    if fence_match:
        cleaned = fence_match.group(1).strip()

    # Пробуем найти JSON-объект в тексте
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        # Ищем первый { ... } блок
        brace_match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if not brace_match:
            return None
        try:
            data = json.loads(brace_match.group(0))
        except json.JSONDecodeError:
            return None

    # Заполняем отсутствующие поля дефолтами
    defaults = {
        "sharpness": 0.5,
        "exposure": 0.5,
        "face_quality": 0.7,
        "face_count": 0,
        "eyes_closed": False,
        "composition": 0.5,
    }
    for key, default in defaults.items():
        if key not in data:
            data[key] = default

    return data


def analyze_photo_ai(
    photo: PhotoInfo,
    model: str = OLLAMA_DEFAULT_MODEL,
    ollama_url: str = OLLAMA_DEFAULT_URL,
) -> PhotoInfo:
    """
    Анализирует фото через Ollama vision model.
    Заполняет: sharpness_score, exposure_score, face_score, face_count,
    all_eyes_closed, ai_score, sharpness (mapped).
    """
    try:
        image_b64 = _encode_image(photo.path)
    except Exception as e:
        logger.warning("Failed to read image %s: %s", photo.path.name, e)
        return photo

    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": _build_prompt(),
                "images": [image_b64],
            }
        ],
        "stream": False,
    }

    try:
        resp = requests.post(
            f"{ollama_url}/api/chat",
            json=payload,
            timeout=300,
        )
        resp.raise_for_status()
    except requests.RequestException as e:
        logger.warning("Ollama request failed for %s: %s", photo.path.name, e)
        return photo

    try:
        body = resp.json()
        content = body["message"]["content"]
    except (KeyError, json.JSONDecodeError) as e:
        logger.warning("Ollama response parse error for %s: %s", photo.path.name, e)
        return photo

    data = _parse_response(content)
    if data is None:
        logger.warning("Invalid AI response for %s: %s", photo.path.name, content[:200])
        return photo

    # Заполняем PhotoInfo
    photo.sharpness_score = float(data["sharpness"])
    photo.exposure_score = float(data["exposure"])
    photo.face_score = float(data["face_quality"])
    photo.face_count = int(data["face_count"])
    photo.all_eyes_closed = bool(data["eyes_closed"])
    photo.ai_score = float(data["composition"])

    # Маппинг sharpness_score → raw sharpness (для hard rules и ранжирования в дубликатах/сериях)
    # 0.0 → 0, 0.5 → 400, 1.0 → 1000
    photo.sharpness = photo.sharpness_score * 1000.0

    return photo
