import xml.etree.ElementTree as ET
from pathlib import Path

from xmp import generate_xmp, write_xmp


class TestGenerateXmp:
    def test_contains_rating(self):
        xml_str = generate_xmp(4)
        assert 'xmp:Rating="4"' in xml_str

    def test_valid_xml(self):
        xml_str = generate_xmp(3)
        root = ET.fromstring(xml_str)
        assert root.tag == "{adobe:ns:meta/}xmpmeta"

    def test_rating_clamped_low(self):
        xml_str = generate_xmp(0)
        assert 'xmp:Rating="1"' in xml_str

    def test_rating_clamped_high(self):
        xml_str = generate_xmp(10)
        assert 'xmp:Rating="5"' in xml_str

    def test_has_xml_declaration(self):
        xml_str = generate_xmp(3)
        assert xml_str.startswith("<?xml")

    def test_has_rdf_description(self):
        xml_str = generate_xmp(3)
        assert "rdf:Description" in xml_str

    def test_all_ratings(self):
        for r in range(1, 6):
            xml_str = generate_xmp(r)
            assert f'xmp:Rating="{r}"' in xml_str


class TestWriteXmp:
    def test_dry_run_no_file(self, tmp_path):
        photo = tmp_path / "DSCF1234.jpg"
        photo.touch()
        result = write_xmp(photo, 4, dry_run=True)
        assert result == tmp_path / "DSCF1234.xmp"
        assert not result.exists()

    def test_writes_file(self, tmp_path):
        photo = tmp_path / "DSCF1234.jpg"
        photo.touch()
        result = write_xmp(photo, 4, dry_run=False)
        assert result.exists()
        content = result.read_text()
        assert 'xmp:Rating="4"' in content

    def test_xmp_filename_matches_stem(self, tmp_path):
        photo = tmp_path / "IMG_0001.jpg"
        photo.touch()
        result = write_xmp(photo, 2)
        assert result.name == "IMG_0001.xmp"
