package main

import (
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func newTestClient(handler http.Handler) (*GooglePhotosClient, *httptest.Server) {
	server := httptest.NewServer(handler)
	client := &GooglePhotosClient{
		httpClient: server.Client(),
		baseURL:    server.URL,
	}
	return client, server
}

func TestListAlbums(t *testing.T) {
	mux := http.NewServeMux()
	mux.HandleFunc("/albums", func(w http.ResponseWriter, r *http.Request) {
		json.NewEncoder(w).Encode(map[string]interface{}{
			"albums": []map[string]string{
				{"id": "id1", "title": "Album 1"},
				{"id": "id2", "title": "Album 2"},
			},
		})
	})

	client, server := newTestClient(mux)
	defer server.Close()

	albums, err := client.ListAlbums()
	if err != nil {
		t.Fatal(err)
	}
	if len(albums) != 2 {
		t.Errorf("expected 2 albums, got %d", len(albums))
	}
	if albums["Album 1"] != "id1" || albums["Album 2"] != "id2" {
		t.Errorf("unexpected albums: %v", albums)
	}
}

func TestListAlbumsPaginated(t *testing.T) {
	callCount := 0
	mux := http.NewServeMux()
	mux.HandleFunc("/albums", func(w http.ResponseWriter, r *http.Request) {
		callCount++
		if r.URL.Query().Get("pageToken") == "" {
			json.NewEncoder(w).Encode(map[string]interface{}{
				"albums":        []map[string]string{{"id": "id1", "title": "A1"}},
				"nextPageToken": "page2",
			})
		} else {
			json.NewEncoder(w).Encode(map[string]interface{}{
				"albums": []map[string]string{{"id": "id2", "title": "A2"}},
			})
		}
	})

	client, server := newTestClient(mux)
	defer server.Close()

	albums, err := client.ListAlbums()
	if err != nil {
		t.Fatal(err)
	}
	if len(albums) != 2 {
		t.Errorf("expected 2 albums, got %d", len(albums))
	}
	if callCount != 2 {
		t.Errorf("expected 2 API calls, got %d", callCount)
	}
}

func TestCreateAlbum(t *testing.T) {
	mux := http.NewServeMux()
	mux.HandleFunc("/albums", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != "POST" {
			t.Errorf("expected POST, got %s", r.Method)
		}
		var body map[string]map[string]string
		json.NewDecoder(r.Body).Decode(&body)
		if body["album"]["title"] != "Test Album" {
			t.Errorf("unexpected title: %v", body)
		}
		json.NewEncoder(w).Encode(map[string]string{"id": "new-id"})
	})

	client, server := newTestClient(mux)
	defer server.Close()

	id, err := client.CreateAlbum("Test Album")
	if err != nil {
		t.Fatal(err)
	}
	if id != "new-id" {
		t.Errorf("expected new-id, got %s", id)
	}
}

func TestGetOrCreateAlbumExisting(t *testing.T) {
	client := &GooglePhotosClient{httpClient: http.DefaultClient, baseURL: "http://unused"}
	existing := map[string]string{"Existing": "eid"}

	id, err := client.GetOrCreateAlbum("Existing", existing)
	if err != nil {
		t.Fatal(err)
	}
	if id != "eid" {
		t.Errorf("expected eid, got %s", id)
	}
}

func TestUploadFile(t *testing.T) {
	mux := http.NewServeMux()
	mux.HandleFunc("/uploads", func(w http.ResponseWriter, r *http.Request) {
		if r.Header.Get("Content-Type") != "application/octet-stream" {
			t.Errorf("unexpected content type: %s", r.Header.Get("Content-Type"))
		}
		if r.Header.Get("X-Goog-Upload-Protocol") != "raw" {
			t.Errorf("unexpected upload protocol: %s", r.Header.Get("X-Goog-Upload-Protocol"))
		}
		name := r.Header.Get("X-Goog-Upload-File-Name")
		body, _ := io.ReadAll(r.Body)
		w.Write([]byte("upload-token-for-" + name + "-" + string(body)))
	})

	client, server := newTestClient(mux)
	defer server.Close()

	dir := t.TempDir()
	fpath := filepath.Join(dir, "photo.jpg")
	os.WriteFile(fpath, []byte("content"), 0644)

	token, err := client.UploadFile(fpath, "")
	if err != nil {
		t.Fatal(err)
	}
	if token != "upload-token-for-photo.jpg-content" {
		t.Errorf("unexpected token: %s", token)
	}
}

func TestUploadFileWithOverride(t *testing.T) {
	mux := http.NewServeMux()
	mux.HandleFunc("/uploads", func(w http.ResponseWriter, r *http.Request) {
		name := r.Header.Get("X-Goog-Upload-File-Name")
		if name != "renamed.jpg" {
			t.Errorf("expected renamed.jpg, got %s", name)
		}
		w.Write([]byte("token"))
	})

	client, server := newTestClient(mux)
	defer server.Close()

	dir := t.TempDir()
	fpath := filepath.Join(dir, "original.jpg")
	os.WriteFile(fpath, []byte("x"), 0644)

	_, err := client.UploadFile(fpath, "renamed.jpg")
	if err != nil {
		t.Fatal(err)
	}
}

func TestAddToAlbum(t *testing.T) {
	mux := http.NewServeMux()
	mux.HandleFunc("/mediaItems:batchCreate", func(w http.ResponseWriter, r *http.Request) {
		var body struct {
			AlbumID       string `json:"albumId"`
			NewMediaItems []struct {
				SimpleMediaItem struct {
					UploadToken string `json:"uploadToken"`
				} `json:"simpleMediaItem"`
			} `json:"newMediaItems"`
		}
		json.NewDecoder(r.Body).Decode(&body)

		results := make([]map[string]interface{}, len(body.NewMediaItems))
		for i := range body.NewMediaItems {
			results[i] = map[string]interface{}{
				"status": map[string]interface{}{"message": "Success"},
			}
		}
		json.NewEncoder(w).Encode(map[string]interface{}{
			"newMediaItemResults": results,
		})
	})

	client, server := newTestClient(mux)
	defer server.Close()

	indices, err := client.AddToAlbum([]string{"t1", "t2", "t3"}, "album-id")
	if err != nil {
		t.Fatal(err)
	}
	if len(indices) != 3 {
		t.Errorf("expected 3 successes, got %d", len(indices))
	}
}

func TestAddToAlbumPartialFailure(t *testing.T) {
	mux := http.NewServeMux()
	mux.HandleFunc("/mediaItems:batchCreate", func(w http.ResponseWriter, r *http.Request) {
		json.NewEncoder(w).Encode(map[string]interface{}{
			"newMediaItemResults": []map[string]interface{}{
				{"status": map[string]interface{}{"message": "Success"}},
				{"status": map[string]interface{}{"message": "FAILED", "code": 3}},
			},
		})
	})

	client, server := newTestClient(mux)
	defer server.Close()

	indices, err := client.AddToAlbum([]string{"t1", "t2"}, "album-id")
	if err != nil {
		t.Fatal(err)
	}
	if len(indices) != 1 {
		t.Errorf("expected 1 success, got %d", len(indices))
	}
	if !indices[0] {
		t.Error("expected index 0 to succeed")
	}
}

func TestListAlbumItems(t *testing.T) {
	mux := http.NewServeMux()
	mux.HandleFunc("/mediaItems:search", func(w http.ResponseWriter, r *http.Request) {
		json.NewEncoder(w).Encode(map[string]interface{}{
			"mediaItems": []map[string]interface{}{
				{
					"id":       "mid1",
					"filename": "photo.jpg",
					"mediaMetadata": map[string]string{
						"creationTime": "2025-01-01T12:00:00Z",
						"width":        "4000",
						"height":       "3000",
					},
				},
			},
		})
	})

	client, server := newTestClient(mux)
	defer server.Close()

	items, err := client.ListAlbumItems("album-id")
	if err != nil {
		t.Fatal(err)
	}
	if len(items) != 1 {
		t.Errorf("expected 1 item, got %d", len(items))
	}
	item := items["photo.jpg"]
	if item.ID != "mid1" {
		t.Errorf("expected mid1, got %s", item.ID)
	}
	if item.Width != "4000" || item.Height != "3000" {
		t.Errorf("unexpected dimensions: %s×%s", item.Width, item.Height)
	}
}

func TestRemoveFromAlbum(t *testing.T) {
	mux := http.NewServeMux()
	mux.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		if !strings.HasSuffix(r.URL.Path, ":batchRemoveMediaItems") {
			t.Errorf("unexpected path: %s", r.URL.Path)
		}
		var body map[string][]string
		json.NewDecoder(r.Body).Decode(&body)
		if len(body["mediaItemIds"]) != 1 || body["mediaItemIds"][0] != "item1" {
			t.Errorf("unexpected body: %v", body)
		}
		w.WriteHeader(http.StatusOK)
	})

	client, server := newTestClient(mux)
	defer server.Close()

	err := client.RemoveFromAlbum("album-id", []string{"item1"})
	if err != nil {
		t.Fatal(err)
	}
}

func TestUploadFileError(t *testing.T) {
	mux := http.NewServeMux()
	mux.HandleFunc("/uploads", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusInternalServerError)
		w.Write([]byte("server error"))
	})

	client, server := newTestClient(mux)
	defer server.Close()

	dir := t.TempDir()
	fpath := filepath.Join(dir, "photo.jpg")
	os.WriteFile(fpath, []byte("x"), 0644)

	_, err := client.UploadFile(fpath, "")
	if err == nil {
		t.Error("expected error")
	}
}
