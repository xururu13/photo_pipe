from pathlib import Path
from unittest.mock import patch, MagicMock
import numpy as np

from config import PhotoInfo
from cull import find_photos, pair_raf_jpeg, analyze_photo, write_all_xmp, process_folder


class TestFindPhotos:
    def test_finds_jpeg(self, tmp_path):
        (tmp_path / "DSCF0001.jpg").touch()
        (tmp_path / "DSCF0002.jpeg").touch()
        (tmp_path / "readme.txt").touch()
        result = find_photos(tmp_path)
        assert len(result) == 2

    def test_finds_raf(self, tmp_path):
        (tmp_path / "DSCF0001.raf").touch()
        (tmp_path / "DSCF0001.RAF").touch()  # дубль с другим регистром → 2 файла
        result = find_photos(tmp_path)
        assert len(result) >= 1

    def test_sorted(self, tmp_path):
        (tmp_path / "DSCF0003.jpg").touch()
        (tmp_path / "DSCF0001.jpg").touch()
        (tmp_path / "DSCF0002.jpg").touch()
        result = find_photos(tmp_path)
        names = [f.name for f in result]
        assert names == sorted(names)

    def test_empty_folder(self, tmp_path):
        assert find_photos(tmp_path) == []

    def test_ignores_subdirs(self, tmp_path):
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "DSCF0001.jpg").touch()
        assert find_photos(tmp_path) == []


class TestPairRafJpeg:
    def test_jpeg_only(self, tmp_path):
        files = [tmp_path / "DSCF0001.jpg"]
        result = pair_raf_jpeg(files)
        assert len(result) == 1
        assert result[0].jpeg_path == files[0]
        assert result[0].raf_path is None

    def test_raf_only(self, tmp_path):
        files = [tmp_path / "DSCF0001.raf"]
        result = pair_raf_jpeg(files)
        assert len(result) == 1
        assert result[0].raf_path == files[0]
        assert result[0].jpeg_path is None
        assert result[0].path == files[0]

    def test_pair(self, tmp_path):
        jpg = tmp_path / "DSCF0001.jpg"
        raf = tmp_path / "DSCF0001.raf"
        result = pair_raf_jpeg([jpg, raf])
        assert len(result) == 1
        assert result[0].jpeg_path == jpg
        assert result[0].raf_path == raf
        assert result[0].path == jpg  # JPEG предпочтительнее

    def test_stem_set(self, tmp_path):
        files = [tmp_path / "DSCF0001.jpg"]
        result = pair_raf_jpeg(files)
        assert result[0].stem == "DSCF0001"


class TestAnalyzePhoto:
    @patch("cull.read_exif_timestamp", return_value=None)
    @patch("cull.compute_dhash", return_value="abc123")
    @patch("cull.detect_faces", return_value=(0, 0.0, False))
    @patch("cull.analyze_image", return_value=(500.0, 0.7, 140.0, 1.0))
    @patch("cull.load_image")
    def test_full_analysis(self, mock_load, mock_analyze, mock_faces, mock_hash, mock_exif):
        mock_load.return_value = np.zeros((100, 100, 3), dtype=np.uint8)
        photo = PhotoInfo(path=Path("/test.jpg"))
        result = analyze_photo(photo)
        assert result.sharpness == 500.0
        assert result.dhash == "abc123"

    @patch("cull.load_image", return_value=None)
    def test_load_failure(self, mock_load):
        photo = PhotoInfo(path=Path("/missing.jpg"))
        result = analyze_photo(photo)
        assert result.sharpness == 0.0  # не анализировалось


class TestWriteAllXmp:
    def test_writes_all(self, tmp_path):
        photos = []
        for i in range(3):
            p = tmp_path / f"DSCF{i:04d}.jpg"
            p.touch()
            photos.append(PhotoInfo(path=p, rating=4))
        written = write_all_xmp(photos, dry_run=False)
        assert written == 3
        assert (tmp_path / "DSCF0000.xmp").exists()

    def test_dry_run(self, tmp_path):
        p = tmp_path / "DSCF0001.jpg"
        p.touch()
        photos = [PhotoInfo(path=p, rating=3)]
        written = write_all_xmp(photos, dry_run=True)
        assert written == 1
        assert not (tmp_path / "DSCF0001.xmp").exists()


class TestProcessFolder:
    @patch("cull.write_all_xmp", return_value=3)
    @patch("cull.rate_photos", side_effect=lambda x, ai_mode=False: x)
    @patch("cull.group_into_series", side_effect=lambda x: x)
    @patch("cull.find_duplicate_groups", side_effect=lambda x: x)
    @patch("cull.analyze_photo", side_effect=lambda x: x)
    def test_pipeline(self, mock_analyze, mock_dup, mock_series, mock_rate, mock_xmp, tmp_path):
        (tmp_path / "DSCF0001.jpg").touch()
        (tmp_path / "DSCF0002.jpg").touch()
        process_folder(tmp_path, dry_run=True)
        assert mock_analyze.call_count == 2
        mock_dup.assert_called_once()
        mock_series.assert_called_once()
        mock_rate.assert_called_once()

    def test_empty_folder(self, tmp_path, capsys):
        process_folder(tmp_path)
        captured = capsys.readouterr()
        assert "не найдены" in captured.out.lower() or "❌" in captured.out

    @patch("cull.write_all_xmp", return_value=2)
    @patch("cull.rate_photos", side_effect=lambda x, ai_mode=False: x)
    @patch("cull.group_into_series", side_effect=lambda x: x)
    @patch("cull.find_duplicate_groups", side_effect=lambda x: x)
    @patch("cull.read_exif_timestamp", return_value=None)
    @patch("cull.compute_dhash", return_value="abc123")
    def test_ai_cull_pipeline(
        self, mock_dhash, mock_exif, mock_dup, mock_series, mock_rate, mock_xmp, tmp_path
    ):
        (tmp_path / "DSCF0001.jpg").write_bytes(b"\xff\xd8\xff\xe0dummy")
        (tmp_path / "DSCF0002.jpg").write_bytes(b"\xff\xd8\xff\xe0dummy")

        with patch("ai_analyzer.requests.post") as mock_post, \
             patch("cull.load_image", return_value=MagicMock()):
            import json
            mock_resp = MagicMock()
            mock_resp.json.return_value = {
                "message": {
                    "content": json.dumps({
                        "sharpness": 0.8, "exposure": 0.9,
                        "face_quality": 0.7, "face_count": 0,
                        "eyes_closed": False, "composition": 0.85,
                    })
                }
            }
            mock_resp.raise_for_status = MagicMock()
            mock_post.return_value = mock_resp

            process_folder(tmp_path, dry_run=True, ai_cull=True)

        assert mock_post.call_count == 2
        mock_rate.assert_called_once()
        # Проверяем что rate_photos вызван с ai_mode=True
        _, kwargs = mock_rate.call_args
        assert kwargs.get("ai_mode") is True
