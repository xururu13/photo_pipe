from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock

from files import find_media_files, format_size, format_remote_date, get_local_file_info, prompt_duplicate


# ── format_size ──────────────────────────────────────────────────────────────

class TestFormatSize:
    def test_bytes(self):
        assert format_size(0) == "0 B"
        assert format_size(512) == "512 B"
        assert format_size(1023) == "1023 B"

    def test_kilobytes(self):
        assert format_size(1024) == "1.0 KB"
        assert format_size(1536) == "1.5 KB"

    def test_megabytes(self):
        assert format_size(1024 * 1024) == "1.0 MB"
        assert format_size(int(2.5 * 1024 * 1024)) == "2.5 MB"

    def test_gigabytes(self):
        assert format_size(1024 ** 3) == "1.00 GB"
        assert format_size(int(1.5 * 1024 ** 3)) == "1.50 GB"


# ── format_remote_date ───────────────────────────────────────────────────────

class TestFormatRemoteDate:
    def test_empty_string(self):
        assert format_remote_date("") == "?"

    def test_valid_iso(self):
        result = format_remote_date("2025-06-15T10:30:00+00:00")
        assert result == "2025-06-15 10:30"

    def test_z_suffix(self):
        result = format_remote_date("2025-06-15T10:30:00Z")
        assert result == "2025-06-15 10:30"

    def test_malformed_falls_back(self):
        result = format_remote_date("not-a-date-at-all")
        assert result == "not-a-date-at-all"[:16]


# ── find_media_files ─────────────────────────────────────────────────────────

class TestFindMediaFiles:
    def test_finds_supported_files(self, tmp_path):
        (tmp_path / "photo.jpg").touch()
        (tmp_path / "video.mp4").touch()
        (tmp_path / "raw.raf").touch()
        result = find_media_files(tmp_path)
        names = {f.name for f in result}
        assert names == {"photo.jpg", "video.mp4", "raw.raf"}

    def test_ignores_unsupported(self, tmp_path):
        (tmp_path / "readme.txt").touch()
        (tmp_path / "data.csv").touch()
        (tmp_path / "photo.jpg").touch()
        result = find_media_files(tmp_path)
        assert len(result) == 1
        assert result[0].name == "photo.jpg"

    def test_case_insensitive_extension(self, tmp_path):
        (tmp_path / "PHOTO.JPG").touch()
        (tmp_path / "Video.MP4").touch()
        result = find_media_files(tmp_path)
        assert len(result) == 2

    def test_empty_folder(self, tmp_path):
        assert find_media_files(tmp_path) == []

    def test_skips_subdirectories(self, tmp_path):
        sub = tmp_path / "subdir"
        sub.mkdir()
        (sub / "nested.jpg").touch()
        (tmp_path / "top.jpg").touch()
        result = find_media_files(tmp_path)
        assert len(result) == 1
        assert result[0].name == "top.jpg"

    def test_returns_sorted(self, tmp_path):
        (tmp_path / "c.jpg").touch()
        (tmp_path / "a.jpg").touch()
        (tmp_path / "b.jpg").touch()
        result = find_media_files(tmp_path)
        names = [f.name for f in result]
        assert names == ["a.jpg", "b.jpg", "c.jpg"]


# ── get_local_file_info ──────────────────────────────────────────────────────

class TestGetLocalFileInfo:
    def test_with_exif_date(self, tmp_path):
        filepath = tmp_path / "test.jpg"
        filepath.write_bytes(b"\x00" * 100)

        mock_img = MagicMock()
        mock_img.size = (1920, 1080)
        mock_img._getexif.return_value = {
            36867: "2025:06:15 10:30:00",  # DateTimeOriginal tag id
        }
        mock_img.__enter__ = lambda s: s
        mock_img.__exit__ = MagicMock(return_value=False)

        with patch("files.ExifTags") as mock_tags:
            mock_tags.TAGS = {36867: "DateTimeOriginal"}
            with patch("files.Image.open", return_value=mock_img):
                info = get_local_file_info(filepath)

        assert info["filename"] == "test.jpg"
        assert info["size"] == 100
        assert info["width"] == 1920
        assert info["height"] == 1080
        assert info["date"] == datetime(2025, 6, 15, 10, 30, 0)

    def test_fallback_to_mtime(self, tmp_path):
        filepath = tmp_path / "test.jpg"
        filepath.write_bytes(b"\x00" * 50)

        mock_img = MagicMock()
        mock_img.size = (800, 600)
        mock_img._getexif.return_value = None
        mock_img.__enter__ = lambda s: s
        mock_img.__exit__ = MagicMock(return_value=False)

        with patch("files.Image.open", return_value=mock_img):
            info = get_local_file_info(filepath)

        assert info["width"] == 800
        assert info["height"] == 600
        assert info["date"] is not None  # falls back to mtime

    def test_non_image_file(self, tmp_path):
        filepath = tmp_path / "video.mp4"
        filepath.write_bytes(b"\x00" * 200)

        with patch("files.Image.open", side_effect=Exception("not an image")):
            info = get_local_file_info(filepath)

        assert info["filename"] == "video.mp4"
        assert info["size"] == 200
        assert info["width"] is None
        assert info["height"] is None
        assert info["date"] is not None  # mtime fallback


# ── prompt_duplicate ─────────────────────────────────────────────────────────

class TestPromptDuplicate:
    def test_returns_skip(self, tmp_path):
        filepath = tmp_path / "photo.jpg"
        filepath.write_bytes(b"\x00" * 100)
        remote_info = {"creationTime": "2025-06-15T10:00:00Z", "width": "1920", "height": "1080"}

        with patch("files.get_local_file_info", return_value={
            "filename": "photo.jpg", "size": 100, "date": datetime(2025, 6, 15),
            "width": 1920, "height": 1080,
        }):
            with patch("builtins.input", return_value="s"):
                result = prompt_duplicate(filepath, remote_info)
        assert result == "s"

    def test_returns_replace(self, tmp_path):
        filepath = tmp_path / "photo.jpg"
        filepath.write_bytes(b"\x00" * 100)
        remote_info = {"creationTime": "", "width": "", "height": ""}

        with patch("files.get_local_file_info", return_value={
            "filename": "photo.jpg", "size": 100, "date": datetime(2025, 1, 1),
            "width": None, "height": None,
        }):
            with patch("builtins.input", return_value="r"):
                result = prompt_duplicate(filepath, remote_info)
        assert result == "r"

    def test_returns_rename(self, tmp_path):
        filepath = tmp_path / "photo.jpg"
        filepath.write_bytes(b"\x00" * 100)
        remote_info = {}

        with patch("files.get_local_file_info", return_value={
            "filename": "photo.jpg", "size": 100, "date": None,
            "width": None, "height": None,
        }):
            with patch("builtins.input", return_value="n"):
                result = prompt_duplicate(filepath, remote_info)
        assert result == "n"

    def test_retries_on_invalid_input(self, tmp_path):
        filepath = tmp_path / "photo.jpg"
        filepath.write_bytes(b"\x00" * 100)
        remote_info = {"creationTime": "2025-01-01T00:00:00Z", "width": "100", "height": "100"}

        with patch("files.get_local_file_info", return_value={
            "filename": "photo.jpg", "size": 100, "date": datetime(2025, 1, 1),
            "width": 100, "height": 100,
        }):
            with patch("builtins.input", side_effect=["x", "invalid", "s"]):
                result = prompt_duplicate(filepath, remote_info)
        assert result == "s"
