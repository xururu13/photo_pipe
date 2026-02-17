package main

import (
	"bufio"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"testing"
)

func setupUploadTestServer() *httptest.Server {
	mux := http.NewServeMux()

	mux.HandleFunc("/albums", func(w http.ResponseWriter, r *http.Request) {
		if r.Method == "POST" {
			json.NewEncoder(w).Encode(map[string]string{"id": "test-album-id"})
		} else {
			json.NewEncoder(w).Encode(map[string]interface{}{
				"albums": []map[string]string{},
			})
		}
	})

	mux.HandleFunc("/uploads", func(w http.ResponseWriter, r *http.Request) {
		io.ReadAll(r.Body)
		w.Write([]byte("upload-token"))
	})

	mux.HandleFunc("/mediaItems:batchCreate", func(w http.ResponseWriter, r *http.Request) {
		var body struct {
			NewMediaItems []interface{} `json:"newMediaItems"`
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

	mux.HandleFunc("/mediaItems:search", func(w http.ResponseWriter, r *http.Request) {
		json.NewEncoder(w).Encode(map[string]interface{}{
			"mediaItems": []interface{}{},
		})
	})

	return httptest.NewServer(mux)
}

func TestProcessFolderDryRun(t *testing.T) {
	dir := t.TempDir()
	folder := filepath.Join(dir, "TestAlbum")
	os.Mkdir(folder, 0755)
	os.WriteFile(filepath.Join(folder, "a.jpg"), []byte("photo"), 0644)
	os.WriteFile(filepath.Join(folder, "b.png"), []byte("image"), 0644)

	result, err := ProcessFolder(nil, folder, nil, nil, false, true, false, nil)
	if err != nil {
		t.Fatal(err)
	}
	if result.Added != 0 {
		t.Errorf("expected 0 added in dry run, got %d", result.Added)
	}
}

func TestProcessFolderEmpty(t *testing.T) {
	dir := t.TempDir()
	folder := filepath.Join(dir, "Empty")
	os.Mkdir(folder, 0755)

	result, err := ProcessFolder(nil, folder, nil, nil, false, true, false, nil)
	if err != nil {
		t.Fatal(err)
	}
	if result.Added != 0 || result.Skipped != 0 {
		t.Errorf("expected 0/0, got %d/%d", result.Added, result.Skipped)
	}
}

func TestProcessFolderUpload(t *testing.T) {
	server := setupUploadTestServer()
	defer server.Close()

	client := &GooglePhotosClient{
		httpClient: server.Client(),
		baseURL:    server.URL,
	}

	dir := t.TempDir()
	folder := filepath.Join(dir, "Album1")
	os.Mkdir(folder, 0755)
	os.WriteFile(filepath.Join(folder, "a.jpg"), []byte("photo data"), 0644)

	existingAlbums := make(map[string]string)
	uploadedLog := make(map[string]bool)
	reader := bufio.NewReader(os.Stdin)

	result, err := ProcessFolder(client, folder, existingAlbums, uploadedLog, false, false, false, reader)
	if err != nil {
		t.Fatal(err)
	}
	if result.Added != 1 {
		t.Errorf("expected 1 added, got %d", result.Added)
	}

	// Check uploaded log was updated
	absPath, _ := filepath.Abs(filepath.Join(folder, "a.jpg"))
	if !uploadedLog[absPath] {
		t.Error("expected file to be in upload log")
	}
}

func TestProcessFolderSkipExisting(t *testing.T) {
	dir := t.TempDir()
	folder := filepath.Join(dir, "Album2")
	os.Mkdir(folder, 0755)
	fpath := filepath.Join(folder, "a.jpg")
	os.WriteFile(fpath, []byte("photo"), 0644)

	absPath, _ := filepath.Abs(fpath)
	uploadedLog := map[string]bool{absPath: true}

	result, err := ProcessFolder(nil, folder, nil, uploadedLog, true, true, false, nil)
	if err != nil {
		t.Fatal(err)
	}
	if result.Skipped != 1 {
		t.Errorf("expected 1 skipped, got %d", result.Skipped)
	}
}

func TestProcessFolderMultipleFiles(t *testing.T) {
	server := setupUploadTestServer()
	defer server.Close()

	client := &GooglePhotosClient{
		httpClient: server.Client(),
		baseURL:    server.URL,
	}

	dir := t.TempDir()
	folder := filepath.Join(dir, "Multi")
	os.Mkdir(folder, 0755)
	for _, name := range []string{"a.jpg", "b.png", "c.mp4"} {
		os.WriteFile(filepath.Join(folder, name), []byte("data"), 0644)
	}

	existingAlbums := make(map[string]string)
	uploadedLog := make(map[string]bool)
	reader := bufio.NewReader(os.Stdin)

	result, err := ProcessFolder(client, folder, existingAlbums, uploadedLog, false, false, false, reader)
	if err != nil {
		t.Fatal(err)
	}
	if result.Added != 3 {
		t.Errorf("expected 3 added, got %d", result.Added)
	}
	if len(uploadedLog) != 3 {
		t.Errorf("expected 3 in upload log, got %d", len(uploadedLog))
	}
}
