import json

from log import load_upload_log, save_upload_log


class TestUploadLog:
    def test_round_trip(self, tmp_path):
        uploaded = {"file1.jpg", "file2.png"}
        albums = {"Album1": "id_1", "Album2": "id_2"}

        save_upload_log(tmp_path, uploaded, albums)
        loaded_uploaded, loaded_albums = load_upload_log(tmp_path)

        assert loaded_uploaded == uploaded
        assert loaded_albums == albums

    def test_missing_file_returns_empty(self, tmp_path):
        uploaded, albums = load_upload_log(tmp_path)
        assert uploaded == set()
        assert albums == {}

    def test_saved_file_is_valid_json(self, tmp_path):
        save_upload_log(tmp_path, {"a.jpg"}, {"X": "123"})
        log_path = tmp_path / ".gphotos_uploaded.json"
        data = json.loads(log_path.read_text())
        assert "uploaded" in data
        assert "albums" in data

    def test_uploaded_sorted_in_file(self, tmp_path):
        save_upload_log(tmp_path, {"c.jpg", "a.jpg", "b.jpg"}, {})
        log_path = tmp_path / ".gphotos_uploaded.json"
        data = json.loads(log_path.read_text())
        assert data["uploaded"] == ["a.jpg", "b.jpg", "c.jpg"]

    def test_overwrite_existing_log(self, tmp_path):
        save_upload_log(tmp_path, {"old.jpg"}, {"Old": "1"})
        save_upload_log(tmp_path, {"new.jpg"}, {"New": "2"})

        uploaded, albums = load_upload_log(tmp_path)
        assert uploaded == {"new.jpg"}
        assert albums == {"New": "2"}
