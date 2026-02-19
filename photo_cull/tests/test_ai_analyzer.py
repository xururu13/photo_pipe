import json
from pathlib import Path
from unittest.mock import patch, MagicMock

from config import PhotoInfo
from ai_analyzer import _encode_image, _build_prompt, _parse_response, analyze_photo_ai


class TestEncodeImage:
    def test_encodes_file(self, tmp_path):
        img = tmp_path / "test.jpg"
        img.write_bytes(b"\xff\xd8\xff\xe0dummy")
        result = _encode_image(img)
        assert isinstance(result, str)
        assert len(result) > 0
        # Должен быть валидный base64
        import base64
        decoded = base64.b64decode(result)
        assert decoded == b"\xff\xd8\xff\xe0dummy"


class TestBuildPrompt:
    def test_returns_nonempty(self):
        prompt = _build_prompt()
        assert isinstance(prompt, str)
        assert len(prompt) > 50
        assert "sharpness" in prompt
        assert "composition" in prompt


class TestParseResponse:
    def test_valid_json(self):
        data = {
            "sharpness": 0.8,
            "exposure": 0.9,
            "face_quality": 0.7,
            "face_count": 2,
            "eyes_closed": False,
            "composition": 0.85,
        }
        result = _parse_response(json.dumps(data))
        assert result == data

    def test_markdown_wrapped_json(self):
        data = {
            "sharpness": 0.5,
            "exposure": 0.6,
            "face_quality": 0.7,
            "face_count": 0,
            "eyes_closed": False,
            "composition": 0.4,
        }
        text = f"```json\n{json.dumps(data)}\n```"
        result = _parse_response(text)
        assert result == data

    def test_invalid_json(self):
        assert _parse_response("not json at all") is None

    def test_markdown_with_trailing_text(self):
        data = {
            "sharpness": 0.9,
            "exposure": 0.8,
            "face_quality": 0.7,
            "face_count": 0,
            "eyes_closed": False,
            "composition": 0.6,
        }
        text = f"```json\n{json.dumps(data)}\n```\nThis photograph appears to have high sharpness"
        result = _parse_response(text)
        assert result is not None
        assert result["sharpness"] == 0.9

    def test_json_embedded_in_text(self):
        data = {
            "sharpness": 0.7,
            "exposure": 0.6,
            "face_quality": 0.7,
            "face_count": 0,
            "eyes_closed": False,
            "composition": 0.5,
        }
        text = f"Here is my analysis:\n{json.dumps(data)}\nHope that helps!"
        result = _parse_response(text)
        assert result is not None
        assert result["sharpness"] == 0.7

    def test_missing_fields_filled_with_defaults(self):
        data = {"sharpness": 0.8, "exposure": 0.9, "face_count": 2, "eyes_closed": False}
        result = _parse_response(json.dumps(data))
        assert result is not None
        assert result["sharpness"] == 0.8
        assert result["face_quality"] == 0.7  # default
        assert result["composition"] == 0.5   # default

    def test_empty_json_gets_all_defaults(self):
        result = _parse_response("{}")
        assert result is not None
        assert result["sharpness"] == 0.5
        assert result["composition"] == 0.5
        assert result["face_count"] == 0


class TestAnalyzePhotoAi:
    def _make_ollama_response(self, scores: dict) -> dict:
        return {
            "message": {
                "content": json.dumps(scores),
            }
        }

    def _default_scores(self) -> dict:
        return {
            "sharpness": 0.8,
            "exposure": 0.9,
            "face_quality": 0.75,
            "face_count": 1,
            "eyes_closed": False,
            "composition": 0.85,
        }

    @patch("ai_analyzer.requests.post")
    def test_successful_analysis(self, mock_post, tmp_path):
        img = tmp_path / "test.jpg"
        img.write_bytes(b"\xff\xd8\xff\xe0dummy")

        scores = self._default_scores()
        mock_resp = MagicMock()
        mock_resp.json.return_value = self._make_ollama_response(scores)
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        photo = PhotoInfo(path=img)
        result = analyze_photo_ai(photo)

        assert result.sharpness_score == 0.8
        assert result.exposure_score == 0.9
        assert result.face_score == 0.75
        assert result.face_count == 1
        assert result.all_eyes_closed is False
        assert result.ai_score == 0.85
        assert result.sharpness == 800.0  # 0.8 * 1000

    @patch("ai_analyzer.requests.post")
    def test_connection_error(self, mock_post, tmp_path):
        img = tmp_path / "test.jpg"
        img.write_bytes(b"\xff\xd8\xff\xe0dummy")

        import requests
        mock_post.side_effect = requests.ConnectionError("Connection refused")

        photo = PhotoInfo(path=img)
        result = analyze_photo_ai(photo)

        # Должны остаться дефолтные значения
        assert result.sharpness_score == 0.0
        assert result.ai_score == 0.0

    @patch("ai_analyzer.requests.post")
    def test_invalid_json_response(self, mock_post, tmp_path):
        img = tmp_path / "test.jpg"
        img.write_bytes(b"\xff\xd8\xff\xe0dummy")

        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "message": {"content": "I cannot analyze this image properly."}
        }
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        photo = PhotoInfo(path=img)
        result = analyze_photo_ai(photo)

        # Дефолтные значения при невалидном ответе
        assert result.sharpness_score == 0.0
        assert result.ai_score == 0.0

    @patch("ai_analyzer.requests.post")
    def test_eyes_closed_detection(self, mock_post, tmp_path):
        img = tmp_path / "test.jpg"
        img.write_bytes(b"\xff\xd8\xff\xe0dummy")

        scores = self._default_scores()
        scores["eyes_closed"] = True
        mock_resp = MagicMock()
        mock_resp.json.return_value = self._make_ollama_response(scores)
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        photo = PhotoInfo(path=img)
        result = analyze_photo_ai(photo)

        assert result.all_eyes_closed is True

    @patch("ai_analyzer.requests.post")
    def test_custom_model_and_url(self, mock_post, tmp_path):
        img = tmp_path / "test.jpg"
        img.write_bytes(b"\xff\xd8\xff\xe0dummy")

        mock_resp = MagicMock()
        mock_resp.json.return_value = self._make_ollama_response(self._default_scores())
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        photo = PhotoInfo(path=img)
        analyze_photo_ai(photo, model="llava:13b", ollama_url="http://gpu:11434")

        call_args = mock_post.call_args
        assert "http://gpu:11434/api/chat" == call_args[0][0]
        assert call_args[1]["json"]["model"] == "llava:13b"
