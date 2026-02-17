package main

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"
)

func TestLoadUploadLogMissing(t *testing.T) {
	dir := t.TempDir()
	uploaded, albums, err := LoadUploadLog(dir)
	if err != nil {
		t.Fatal(err)
	}
	if len(uploaded) != 0 {
		t.Errorf("expected empty uploaded, got %d", len(uploaded))
	}
	if len(albums) != 0 {
		t.Errorf("expected empty albums, got %d", len(albums))
	}
}

func TestLoadUploadLogExisting(t *testing.T) {
	dir := t.TempDir()
	logData := `{
  "uploaded": ["/a/b.jpg", "/c/d.png"],
  "albums": {"album1": "id1"}
}`
	os.WriteFile(filepath.Join(dir, UploadLog), []byte(logData), 0644)

	uploaded, albums, err := LoadUploadLog(dir)
	if err != nil {
		t.Fatal(err)
	}
	if len(uploaded) != 2 {
		t.Errorf("expected 2 uploaded, got %d", len(uploaded))
	}
	if !uploaded["/a/b.jpg"] || !uploaded["/c/d.png"] {
		t.Error("missing expected paths")
	}
	if albums["album1"] != "id1" {
		t.Error("missing expected album")
	}
}

func TestSaveUploadLog(t *testing.T) {
	dir := t.TempDir()
	uploaded := map[string]bool{"/z/b.jpg": true, "/a/c.png": true}
	albums := map[string]string{"Album": "id123"}

	if err := SaveUploadLog(dir, uploaded, albums); err != nil {
		t.Fatal(err)
	}

	data, err := os.ReadFile(filepath.Join(dir, UploadLog))
	if err != nil {
		t.Fatal(err)
	}

	var logData uploadLogData
	if err := json.Unmarshal(data, &logData); err != nil {
		t.Fatal(err)
	}

	if len(logData.Uploaded) != 2 {
		t.Errorf("expected 2 uploaded, got %d", len(logData.Uploaded))
	}
	// Should be sorted
	if logData.Uploaded[0] != "/a/c.png" || logData.Uploaded[1] != "/z/b.jpg" {
		t.Errorf("uploaded not sorted: %v", logData.Uploaded)
	}
	if logData.Albums["Album"] != "id123" {
		t.Error("album not saved")
	}
}

func TestSaveLoadRoundtrip(t *testing.T) {
	dir := t.TempDir()
	uploaded := map[string]bool{"/path/to/file.jpg": true}
	albums := map[string]string{"MyAlbum": "abc"}

	if err := SaveUploadLog(dir, uploaded, albums); err != nil {
		t.Fatal(err)
	}

	loaded, loadedAlbums, err := LoadUploadLog(dir)
	if err != nil {
		t.Fatal(err)
	}
	if !loaded["/path/to/file.jpg"] {
		t.Error("roundtrip failed for uploaded")
	}
	if loadedAlbums["MyAlbum"] != "abc" {
		t.Error("roundtrip failed for albums")
	}
}
