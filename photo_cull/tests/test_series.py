from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from config import PhotoInfo
from series import group_into_series, read_exif_timestamp


class TestGroupIntoSeries:
    def test_no_timestamps(self):
        photos = [
            PhotoInfo(path=Path("/a.jpg")),
            PhotoInfo(path=Path("/b.jpg")),
        ]
        result = group_into_series(photos)
        assert all(p.series_group == -1 for p in result)

    def test_burst_grouped(self):
        photos = [
            PhotoInfo(path=Path("/a.jpg"), timestamp=datetime(2025, 1, 1, 12, 0, 0), sharpness=100),
            PhotoInfo(path=Path("/b.jpg"), timestamp=datetime(2025, 1, 1, 12, 0, 1), sharpness=200),
            PhotoInfo(path=Path("/c.jpg"), timestamp=datetime(2025, 1, 1, 12, 0, 2), sharpness=300),
        ]
        result = group_into_series(photos)
        assert result[0].series_group == result[1].series_group == result[2].series_group
        assert result[0].series_group >= 0

    def test_best_in_series(self):
        photos = [
            PhotoInfo(path=Path("/a.jpg"), timestamp=datetime(2025, 1, 1, 12, 0, 0), sharpness=100),
            PhotoInfo(path=Path("/b.jpg"), timestamp=datetime(2025, 1, 1, 12, 0, 1), sharpness=500),
            PhotoInfo(path=Path("/c.jpg"), timestamp=datetime(2025, 1, 1, 12, 0, 2), sharpness=300),
        ]
        result = group_into_series(photos)
        assert result[1].is_best_in_series  # sharpness=500
        assert result[1].series_score == 1.0
        assert result[0].series_score == 0.3

    def test_separate_series(self):
        photos = [
            PhotoInfo(path=Path("/a.jpg"), timestamp=datetime(2025, 1, 1, 12, 0, 0), sharpness=100),
            PhotoInfo(path=Path("/b.jpg"), timestamp=datetime(2025, 1, 1, 12, 0, 1), sharpness=200),
            # 10-секундный разрыв
            PhotoInfo(path=Path("/c.jpg"), timestamp=datetime(2025, 1, 1, 12, 0, 11), sharpness=300),
            PhotoInfo(path=Path("/d.jpg"), timestamp=datetime(2025, 1, 1, 12, 0, 12), sharpness=400),
        ]
        result = group_into_series(photos)
        assert result[0].series_group != result[2].series_group
        assert result[0].series_group == result[1].series_group
        assert result[2].series_group == result[3].series_group

    def test_single_photo_no_series(self):
        photos = [
            PhotoInfo(path=Path("/a.jpg"), timestamp=datetime(2025, 1, 1, 12, 0, 0)),
        ]
        result = group_into_series(photos)
        assert result[0].series_group == -1

    def test_gap_exactly_3s(self):
        """3 секунды ровно — всё ещё одна серия (≤3с)."""
        photos = [
            PhotoInfo(path=Path("/a.jpg"), timestamp=datetime(2025, 1, 1, 12, 0, 0), sharpness=100),
            PhotoInfo(path=Path("/b.jpg"), timestamp=datetime(2025, 1, 1, 12, 0, 3), sharpness=200),
        ]
        result = group_into_series(photos)
        assert result[0].series_group == result[1].series_group


class TestReadExifTimestamp:
    @patch("series.Image")
    def test_reads_timestamp(self, mock_image_mod):
        mock_img = mock_image_mod.open.return_value.__enter__.return_value
        mock_img._getexif.return_value = {36867: "2025:01:15 14:30:00"}
        with patch("series.ExifTags") as mock_tags:
            mock_tags.TAGS = {36867: "DateTimeOriginal"}
            result = read_exif_timestamp(Path("/test.jpg"))
        assert result == datetime(2025, 1, 15, 14, 30, 0)

    @patch("series.Image")
    def test_no_exif(self, mock_image_mod):
        mock_img = mock_image_mod.open.return_value.__enter__.return_value
        mock_img._getexif.return_value = None
        result = read_exif_timestamp(Path("/test.jpg"))
        assert result is None

    @patch("series.Image")
    def test_exception_returns_none(self, mock_image_mod):
        mock_image_mod.open.side_effect = Exception("file error")
        result = read_exif_timestamp(Path("/test.jpg"))
        assert result is None
