from config import PhotoInfo, SUPPORTED_EXTENSIONS, JPEG_EXTENSIONS, RAW_EXTENSIONS
from pathlib import Path


class TestPhotoInfo:
    def test_defaults(self):
        p = PhotoInfo(path=Path("/tmp/test.jpg"))
        assert p.rating == 3
        assert p.composite_score == 0.0
        assert p.duplicate_group == -1
        assert p.series_group == -1
        assert p.face_score == 0.7
        assert p.uniqueness_score == 1.0
        assert p.series_score == 0.5

    def test_stem(self):
        p = PhotoInfo(path=Path("/photos/DSCF1234.jpg"), stem="DSCF1234")
        assert p.stem == "DSCF1234"

    def test_raf_jpeg_pair(self):
        p = PhotoInfo(
            path=Path("/photos/DSCF1234.jpg"),
            jpeg_path=Path("/photos/DSCF1234.jpg"),
            raf_path=Path("/photos/DSCF1234.RAF"),
            stem="DSCF1234",
        )
        assert p.jpeg_path is not None
        assert p.raf_path is not None


class TestConstants:
    def test_extensions_include_jpeg(self):
        assert ".jpg" in JPEG_EXTENSIONS
        assert ".jpeg" in JPEG_EXTENSIONS

    def test_extensions_include_raf(self):
        assert ".raf" in RAW_EXTENSIONS

    def test_supported_is_union(self):
        assert SUPPORTED_EXTENSIONS == JPEG_EXTENSIONS | RAW_EXTENSIONS
