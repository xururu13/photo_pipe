from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open

from client import GooglePhotosClient


def make_client():
    creds = MagicMock()
    creds.token = "test_token"
    creds.expired = False
    return GooglePhotosClient(creds)


# ── get_or_create_album ──────────────────────────────────────────────────────

class TestGetOrCreateAlbum:
    def test_cache_hit(self):
        client = make_client()
        existing = {"My Album": "album_123"}
        result = client.get_or_create_album("My Album", existing)
        assert result == "album_123"

    def test_cache_miss_creates_album(self):
        client = make_client()
        existing = {}

        with patch.object(client, "create_album", return_value="new_id") as mock_create:
            result = client.get_or_create_album("New Album", existing)

        assert result == "new_id"
        assert existing["New Album"] == "new_id"
        mock_create.assert_called_once_with("New Album")


# ── list_albums ──────────────────────────────────────────────────────────────

class TestListAlbums:
    def test_single_page(self):
        client = make_client()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "albums": [
                {"title": "Album1", "id": "id1"},
                {"title": "Album2", "id": "id2"},
            ]
        }
        client.session.get = MagicMock(return_value=mock_resp)

        result = client.list_albums()
        assert result == {"Album1": "id1", "Album2": "id2"}

    def test_paginated(self):
        client = make_client()
        page1 = MagicMock()
        page1.json.return_value = {
            "albums": [{"title": "A", "id": "1"}],
            "nextPageToken": "tok2",
        }
        page2 = MagicMock()
        page2.json.return_value = {
            "albums": [{"title": "B", "id": "2"}],
        }
        client.session.get = MagicMock(side_effect=[page1, page2])

        result = client.list_albums()
        assert result == {"A": "1", "B": "2"}
        assert client.session.get.call_count == 2

    def test_empty_response(self):
        client = make_client()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {}
        client.session.get = MagicMock(return_value=mock_resp)

        result = client.list_albums()
        assert result == {}


# ── upload_file ──────────────────────────────────────────────────────────────

class TestUploadFile:
    def test_success(self, tmp_path):
        client = make_client()
        filepath = tmp_path / "photo.jpg"
        filepath.write_bytes(b"\xff\xd8\xff" + b"\x00" * 100)

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "upload_token_abc"

        with patch("client.requests.post", return_value=mock_resp):
            token = client.upload_file(filepath)

        assert token == "upload_token_abc"

    def test_failure(self, tmp_path):
        client = make_client()
        filepath = tmp_path / "photo.jpg"
        filepath.write_bytes(b"\x00" * 10)

        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "Internal Server Error"

        with patch("client.requests.post", return_value=mock_resp):
            token = client.upload_file(filepath)

        assert token is None

    def test_filename_override(self, tmp_path):
        client = make_client()
        filepath = tmp_path / "original.jpg"
        filepath.write_bytes(b"\x00" * 10)

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "tok"

        with patch("client.requests.post", return_value=mock_resp) as mock_post:
            client.upload_file(filepath, filename_override="renamed.jpg")

        headers = mock_post.call_args.kwargs["headers"]
        assert headers["X-Goog-Upload-File-Name"] == b"renamed.jpg"


# ── add_to_album ─────────────────────────────────────────────────────────────

class TestAddToAlbum:
    def test_single_batch_success(self):
        client = make_client()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "newMediaItemResults": [
                {"status": {"message": "Success"}},
                {"status": {"code": 0}},
            ]
        }
        client.session.post = MagicMock(return_value=mock_resp)

        result = client.add_to_album(["tok1", "tok2"], "album_id")
        assert result == {0, 1}

    def test_partial_failure(self):
        client = make_client()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "newMediaItemResults": [
                {"status": {"message": "Success"}},
                {"status": {"message": "INVALID_ARGUMENT", "code": 3}},
            ]
        }
        client.session.post = MagicMock(return_value=mock_resp)

        result = client.add_to_album(["tok1", "tok2"], "album_id")
        assert result == {0}

    @patch("client.time.sleep")
    def test_batch_splitting(self, mock_sleep):
        client = make_client()
        tokens = [f"tok{i}" for i in range(75)]

        resp1 = MagicMock()
        resp1.status_code = 200
        resp1.json.return_value = {
            "newMediaItemResults": [{"status": {"message": "OK"}} for _ in range(50)]
        }
        resp2 = MagicMock()
        resp2.status_code = 200
        resp2.json.return_value = {
            "newMediaItemResults": [{"status": {"message": "OK"}} for _ in range(25)]
        }
        client.session.post = MagicMock(side_effect=[resp1, resp2])

        result = client.add_to_album(tokens, "album_id")
        assert len(result) == 75
        assert client.session.post.call_count == 2
        mock_sleep.assert_called_once_with(1)

    def test_index_tracking_across_batches(self):
        client = make_client()
        tokens = [f"tok{i}" for i in range(55)]

        resp1 = MagicMock()
        resp1.status_code = 200
        resp1.json.return_value = {
            "newMediaItemResults": [{"status": {"message": "Success"}} for _ in range(50)]
        }
        resp2 = MagicMock()
        resp2.status_code = 200
        resp2.json.return_value = {
            "newMediaItemResults": [
                {"status": {"message": "FAIL", "code": 3}},
                {"status": {"message": "Success"}},
                {"status": {"message": "FAIL", "code": 3}},
                {"status": {"message": "Success"}},
                {"status": {"message": "Success"}},
            ]
        }
        client.session.post = MagicMock(side_effect=[resp1, resp2])

        with patch("client.time.sleep"):
            result = client.add_to_album(tokens, "album_id")

        # First batch: 0-49 all succeed; second batch: indices 50,52 fail; 51,53,54 succeed
        assert 50 not in result
        assert 51 in result
        assert 52 not in result
        assert 53 in result
        assert 54 in result
        assert len(result) == 53

    def test_http_error(self):
        client = make_client()
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "error"
        client.session.post = MagicMock(return_value=mock_resp)

        result = client.add_to_album(["tok1"], "album_id")
        assert result == set()

    def test_with_descriptions(self):
        client = make_client()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "newMediaItemResults": [{"status": {"message": "Success"}}]
        }
        client.session.post = MagicMock(return_value=mock_resp)

        client.add_to_album(["tok1"], "album_id", descriptions=["My photo"])
        body = client.session.post.call_args.kwargs["json"]
        assert body["newMediaItems"][0]["description"] == "My photo"


# ── list_album_items ─────────────────────────────────────────────────────────

class TestListAlbumItems:
    def test_single_page(self):
        client = make_client()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "mediaItems": [{
                "filename": "photo.jpg",
                "id": "item_1",
                "mediaMetadata": {
                    "creationTime": "2025-01-01T00:00:00Z",
                    "width": "1920",
                    "height": "1080",
                },
            }]
        }
        client.session.post = MagicMock(return_value=mock_resp)

        result = client.list_album_items("album_id")
        assert "photo.jpg" in result
        assert result["photo.jpg"]["id"] == "item_1"
        assert result["photo.jpg"]["width"] == "1920"

    def test_paginated(self):
        client = make_client()
        page1 = MagicMock()
        page1.json.return_value = {
            "mediaItems": [{"filename": "a.jpg", "id": "1", "mediaMetadata": {}}],
            "nextPageToken": "next",
        }
        page2 = MagicMock()
        page2.json.return_value = {
            "mediaItems": [{"filename": "b.jpg", "id": "2", "mediaMetadata": {}}],
        }
        client.session.post = MagicMock(side_effect=[page1, page2])

        result = client.list_album_items("album_id")
        assert len(result) == 2
        assert "a.jpg" in result
        assert "b.jpg" in result

    def test_empty_album(self):
        client = make_client()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {}
        client.session.post = MagicMock(return_value=mock_resp)

        result = client.list_album_items("album_id")
        assert result == {}


# ── remove_from_album ────────────────────────────────────────────────────────

class TestRemoveFromAlbum:
    def test_calls_api(self):
        client = make_client()
        mock_resp = MagicMock()
        client.session.post = MagicMock(return_value=mock_resp)

        client.remove_from_album("album_123", ["item_1", "item_2"])

        call_args = client.session.post.call_args
        assert "album_123" in call_args.args[0]
        assert call_args.kwargs["json"] == {"mediaItemIds": ["item_1", "item_2"]}
