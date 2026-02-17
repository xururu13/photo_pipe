from pathlib import Path
from unittest.mock import patch, MagicMock

from google_photos_upload import process_folder


def make_mock_client():
    client = MagicMock()
    client.get_or_create_album.return_value = "album_id"
    client.list_album_items.return_value = {}
    client.upload_file.return_value = "upload_token"
    client.add_to_album.return_value = set()
    return client


# ── skip_existing filtering ──────────────────────────────────────────────────

class TestSkipExisting:
    def test_filters_uploaded_files(self, tmp_path):
        folder = tmp_path / "Album"
        folder.mkdir()
        (folder / "old.jpg").write_bytes(b"\x00" * 10)
        (folder / "new.jpg").write_bytes(b"\x00" * 10)

        client = make_mock_client()
        client.add_to_album.return_value = {0}
        uploaded_log = {str(folder / "old.jpg")}

        uploaded, skipped = process_folder(
            client, folder, {}, uploaded_log,
            skip_existing=True, dry_run=False, can_read_library=False,
        )

        assert skipped == 1
        # Only new.jpg should be uploaded
        client.upload_file.assert_called_once()
        call_path = client.upload_file.call_args.args[0]
        assert call_path.name == "new.jpg"

    def test_no_skip_uploads_all(self, tmp_path):
        folder = tmp_path / "Album"
        folder.mkdir()
        (folder / "a.jpg").write_bytes(b"\x00" * 10)
        (folder / "b.jpg").write_bytes(b"\x00" * 10)

        client = make_mock_client()
        client.add_to_album.return_value = {0, 1}
        uploaded_log = {str(folder / "a.jpg")}

        uploaded, skipped = process_folder(
            client, folder, {}, uploaded_log,
            skip_existing=False, dry_run=False, can_read_library=False,
        )

        assert skipped == 0
        assert client.upload_file.call_count == 2

    def test_all_files_already_uploaded(self, tmp_path):
        folder = tmp_path / "Album"
        folder.mkdir()
        (folder / "a.jpg").write_bytes(b"\x00" * 10)

        client = make_mock_client()
        uploaded_log = {str(folder / "a.jpg")}

        uploaded, skipped = process_folder(
            client, folder, {}, uploaded_log,
            skip_existing=True, dry_run=False, can_read_library=False,
        )

        assert uploaded == 0
        assert skipped == 1
        client.upload_file.assert_not_called()


# ── dry_run mode ─────────────────────────────────────────────────────────────

class TestDryRun:
    def test_no_api_calls(self, tmp_path):
        folder = tmp_path / "Album"
        folder.mkdir()
        (folder / "photo.jpg").write_bytes(b"\x00" * 10)

        client = make_mock_client()

        uploaded, skipped = process_folder(
            client, folder, {}, set(),
            skip_existing=False, dry_run=True,
        )

        assert uploaded == 0
        client.upload_file.assert_not_called()
        client.add_to_album.assert_not_called()
        client.get_or_create_album.assert_not_called()

    def test_dry_run_with_skip_existing(self, tmp_path):
        folder = tmp_path / "Album"
        folder.mkdir()
        (folder / "a.jpg").write_bytes(b"\x00" * 10)
        (folder / "b.jpg").write_bytes(b"\x00" * 10)

        uploaded_log = {str(folder / "a.jpg")}

        uploaded, skipped = process_folder(
            MagicMock(), folder, {}, uploaded_log,
            skip_existing=True, dry_run=True,
        )

        assert uploaded == 0
        assert skipped == 1


# ── duplicate handling ───────────────────────────────────────────────────────

class TestDuplicateHandling:
    def test_skip_duplicate(self, tmp_path):
        folder = tmp_path / "Album"
        folder.mkdir()
        (folder / "dup.jpg").write_bytes(b"\x00" * 10)

        client = make_mock_client()
        client.list_album_items.return_value = {
            "dup.jpg": {"id": "remote_id", "creationTime": "", "width": "", "height": ""},
        }

        with patch("google_photos_upload.prompt_duplicate", return_value="s"):
            uploaded, skipped = process_folder(
                client, folder, {}, set(),
                skip_existing=False, dry_run=False, can_read_library=True,
            )

        assert skipped == 1
        client.upload_file.assert_not_called()

    def test_replace_duplicate(self, tmp_path):
        folder = tmp_path / "Album"
        folder.mkdir()
        (folder / "dup.jpg").write_bytes(b"\x00" * 10)

        client = make_mock_client()
        client.list_album_items.return_value = {
            "dup.jpg": {"id": "old_remote_id", "creationTime": "", "width": "", "height": ""},
        }
        client.add_to_album.return_value = {0}

        with patch("google_photos_upload.prompt_duplicate", return_value="r"):
            uploaded, skipped = process_folder(
                client, folder, {}, set(),
                skip_existing=False, dry_run=False, can_read_library=True,
            )

        client.remove_from_album.assert_called_once_with("album_id", ["old_remote_id"])
        client.upload_file.assert_called_once()
        assert uploaded == 1

    def test_rename_duplicate(self, tmp_path):
        folder = tmp_path / "Album"
        folder.mkdir()
        (folder / "dup.jpg").write_bytes(b"\x00" * 10)

        client = make_mock_client()
        client.list_album_items.return_value = {
            "dup.jpg": {"id": "remote_id", "creationTime": "", "width": "", "height": ""},
        }
        client.add_to_album.return_value = {0}

        with patch("google_photos_upload.prompt_duplicate", return_value="n"):
            with patch("builtins.input", return_value="dup_v2.jpg"):
                uploaded, skipped = process_folder(
                    client, folder, {}, set(),
                    skip_existing=False, dry_run=False, can_read_library=True,
                )

        # Should upload with the overridden name
        call_kwargs = client.upload_file.call_args
        assert call_kwargs.kwargs.get("filename_override") == "dup_v2.jpg" or \
               (len(call_kwargs.args) > 1 and call_kwargs.args[1] == "dup_v2.jpg")

    def test_rename_empty_name_skips(self, tmp_path):
        folder = tmp_path / "Album"
        folder.mkdir()
        (folder / "dup.jpg").write_bytes(b"\x00" * 10)

        client = make_mock_client()
        client.list_album_items.return_value = {
            "dup.jpg": {"id": "remote_id", "creationTime": "", "width": "", "height": ""},
        }

        with patch("google_photos_upload.prompt_duplicate", return_value="n"):
            with patch("builtins.input", return_value=""):
                uploaded, skipped = process_folder(
                    client, folder, {}, set(),
                    skip_existing=False, dry_run=False, can_read_library=True,
                )

        assert skipped == 1
        client.upload_file.assert_not_called()

    def test_empty_folder_returns_zeros(self, tmp_path):
        folder = tmp_path / "Empty"
        folder.mkdir()

        uploaded, skipped = process_folder(
            MagicMock(), folder, {}, set(),
            skip_existing=False, dry_run=False,
        )

        assert uploaded == 0
        assert skipped == 0
