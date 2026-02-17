package main

import (
	"os"
	"path/filepath"
	"testing"
)

func TestFindMediaFiles(t *testing.T) {
	dir := t.TempDir()

	// Create test files
	for _, name := range []string{"a.jpg", "b.png", "c.txt", "d.MP4", "e.gif"} {
		os.WriteFile(filepath.Join(dir, name), []byte("test"), 0644)
	}
	// Create a subdirectory (should be skipped)
	os.Mkdir(filepath.Join(dir, "subdir"), 0755)

	files, err := FindMediaFiles(dir)
	if err != nil {
		t.Fatal(err)
	}

	if len(files) != 4 {
		t.Errorf("expected 4 media files, got %d: %v", len(files), files)
	}

	// Check sorted order
	expected := []string{"a.jpg", "b.png", "d.MP4", "e.gif"}
	for i, f := range files {
		base := filepath.Base(f)
		if base != expected[i] {
			t.Errorf("file %d: expected %s, got %s", i, expected[i], base)
		}
	}
}

func TestFindMediaFilesEmpty(t *testing.T) {
	dir := t.TempDir()
	files, err := FindMediaFiles(dir)
	if err != nil {
		t.Fatal(err)
	}
	if len(files) != 0 {
		t.Errorf("expected 0 files, got %d", len(files))
	}
}

func TestFindMediaFilesAllExtensions(t *testing.T) {
	dir := t.TempDir()
	exts := []string{
		".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic", ".heif",
		".bmp", ".tiff", ".tif", ".avif", ".ico",
		".raw", ".raf", ".cr2", ".cr3", ".nef", ".arw", ".dng",
		".orf", ".rw2", ".pef", ".srw",
		".mp4", ".mov", ".avi", ".mkv", ".m4v", ".3gp", ".wmv", ".mpg",
	}
	for _, ext := range exts {
		os.WriteFile(filepath.Join(dir, "file"+ext), []byte("x"), 0644)
	}

	files, err := FindMediaFiles(dir)
	if err != nil {
		t.Fatal(err)
	}
	if len(files) != len(exts) {
		t.Errorf("expected %d files, got %d", len(exts), len(files))
	}
}

func TestFormatSize(t *testing.T) {
	tests := []struct {
		input    int64
		expected string
	}{
		{0, "0 B"},
		{512, "512 B"},
		{1023, "1023 B"},
		{1024, "1.0 KB"},
		{1536, "1.5 KB"},
		{1048576, "1.0 MB"},
		{1572864, "1.5 MB"},
		{1073741824, "1.00 GB"},
		{1610612736, "1.50 GB"},
	}
	for _, tt := range tests {
		result := FormatSize(tt.input)
		if result != tt.expected {
			t.Errorf("FormatSize(%d) = %q, want %q", tt.input, result, tt.expected)
		}
	}
}

func TestGetLocalFileInfo(t *testing.T) {
	dir := t.TempDir()
	fpath := filepath.Join(dir, "test.jpg")
	os.WriteFile(fpath, []byte("hello world"), 0644)

	info := GetLocalFileInfo(fpath)
	if info.Filename != "test.jpg" {
		t.Errorf("expected filename test.jpg, got %s", info.Filename)
	}
	if info.Size != 11 {
		t.Errorf("expected size 11, got %d", info.Size)
	}
	if info.Date.IsZero() {
		t.Error("expected non-zero date")
	}
}

func TestGetLocalFileInfoMissing(t *testing.T) {
	info := GetLocalFileInfo("/nonexistent/file.jpg")
	if info.Filename != "file.jpg" {
		t.Errorf("expected filename file.jpg, got %s", info.Filename)
	}
	if info.Size != 0 {
		t.Errorf("expected size 0, got %d", info.Size)
	}
}

func TestFormatRemoteDate(t *testing.T) {
	tests := []struct {
		input    string
		expected string
	}{
		{"", "?"},
		{"2025-02-16T20:32:22Z", "2025-02-16 20:32"},
		{"2025-02-16T20:32:22+03:00", "2025-02-16 20:32"},
		{"invalid-but-long-enough", "invalid-but-long"},
		{"short", "short"},
	}
	for _, tt := range tests {
		result := FormatRemoteDate(tt.input)
		if result != tt.expected {
			t.Errorf("FormatRemoteDate(%q) = %q, want %q", tt.input, result, tt.expected)
		}
	}
}
