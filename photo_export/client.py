from __future__ import annotations

import time
from pathlib import Path

import requests
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

from config import API_BASE


class GooglePhotosClient:
    """Клиент для работы с Google Photos Library API."""

    def __init__(self, creds: Credentials):
        self.creds = creds
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {creds.token}",
        })

    def _refresh_if_needed(self):
        """Обновляет токен, если он истёк."""
        if self.creds.expired:
            self.creds.refresh(Request())
            self.session.headers["Authorization"] = f"Bearer {self.creds.token}"

    def list_albums(self) -> dict:
        """Получает все существующие альбомы. Возвращает {title: id}."""
        self._refresh_if_needed()
        albums = {}
        page_token = None

        while True:
            params = {"pageSize": 50}
            if page_token:
                params["pageToken"] = page_token

            resp = self.session.get(f"{API_BASE}/albums", params=params)
            resp.raise_for_status()
            data = resp.json()

            for album in data.get("albums", []):
                albums[album["title"]] = album["id"]

            page_token = data.get("nextPageToken")
            if not page_token:
                break

        return albums

    def create_album(self, title: str) -> str:
        """Создаёт альбом и возвращает его ID."""
        self._refresh_if_needed()
        resp = self.session.post(
            f"{API_BASE}/albums",
            json={"album": {"title": title}},
        )
        resp.raise_for_status()
        album_id = resp.json()["id"]
        return album_id

    def get_or_create_album(self, title: str, existing_albums: dict) -> str:
        """Возвращает ID альбома, создавая его при необходимости."""
        if title in existing_albums:
            return existing_albums[title]

        album_id = self.create_album(title)
        existing_albums[title] = album_id
        return album_id

    def upload_file(self, filepath: Path, filename_override: str | None = None) -> str | None:
        """
        Загружает файл и возвращает upload token.
        Это первый шаг — файл ещё не привязан к библиотеке.
        """
        self._refresh_if_needed()
        filename = filename_override or filepath.name
        filesize = filepath.stat().st_size

        headers = {
            "Authorization": f"Bearer {self.creds.token}",
            "Content-Type": "application/octet-stream",
            "X-Goog-Upload-File-Name": filename.encode("utf-8"),
            "X-Goog-Upload-Protocol": "raw",
        }

        with open(filepath, "rb") as f:
            resp = requests.post(
                f"{API_BASE}/uploads",
                headers=headers,
                data=f,
            )

        if resp.status_code == 200:
            return resp.text  # upload token
        else:
            print(f"  ⚠️  Ошибка загрузки {filename}: {resp.status_code} {resp.text}")
            return None

    def add_to_album(self, upload_tokens: list[str], album_id: str,
                     descriptions: list[str] | None = None) -> set[int]:
        """
        Создаёт media items из upload tokens и добавляет в альбом.
        Google Photos API позволяет до 50 items за один запрос.
        Возвращает множество индексов успешно добавленных элементов.
        """
        self._refresh_if_needed()
        success_indices = set()

        # Разбиваем на батчи по 50
        for i in range(0, len(upload_tokens), 50):
            batch_tokens = upload_tokens[i:i + 50]
            batch_descs = (descriptions[i:i + 50]
                           if descriptions else [None] * len(batch_tokens))

            new_items = []
            for token, desc in zip(batch_tokens, batch_descs):
                item = {"simpleMediaItem": {"uploadToken": token}}
                if desc:
                    item["description"] = desc
                new_items.append(item)

            body = {
                "albumId": album_id,
                "newMediaItems": new_items,
            }

            resp = self.session.post(
                f"{API_BASE}/mediaItems:batchCreate",
                json=body,
            )

            if resp.status_code == 200:
                results = resp.json().get("newMediaItemResults", [])
                for j, r in enumerate(results):
                    status = r.get("status", {})
                    if status.get("message") in ("Success", "OK") or status.get("code", -1) == 0:
                        success_indices.add(i + j)
                    else:
                        print(f"  ⚠️  Элемент не добавлен: {status}")
            else:
                print(f"  ⚠️  Ошибка batchCreate: {resp.status_code} {resp.text}")

            # Небольшая пауза между батчами
            if i + 50 < len(upload_tokens):
                time.sleep(1)

        return success_indices

    def list_album_items(self, album_id: str) -> dict[str, dict]:
        """
        Получает все медиа-элементы в альбоме.
        Возвращает {filename: {id, creationTime, width, height}}.
        """
        self._refresh_if_needed()
        items = {}
        page_token = None

        while True:
            body = {"albumId": album_id, "pageSize": 100}
            if page_token:
                body["pageToken"] = page_token

            resp = self.session.post(
                f"{API_BASE}/mediaItems:search",
                json=body,
            )
            resp.raise_for_status()
            data = resp.json()

            for item in data.get("mediaItems", []):
                metadata = item.get("mediaMetadata", {})
                items[item["filename"]] = {
                    "id": item["id"],
                    "creationTime": metadata.get("creationTime", ""),
                    "width": metadata.get("width", ""),
                    "height": metadata.get("height", ""),
                }

            page_token = data.get("nextPageToken")
            if not page_token:
                break

        return items

    def remove_from_album(self, album_id: str, media_item_ids: list[str]):
        """
        Удаляет медиа-элементы из альбома (не из библиотеки).
        """
        self._refresh_if_needed()
        resp = self.session.post(
            f"{API_BASE}/albums/{album_id}:batchRemoveMediaItems",
            json={"mediaItemIds": media_item_ids},
        )
        resp.raise_for_status()
