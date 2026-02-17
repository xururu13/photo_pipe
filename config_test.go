package main

import (
	"testing"
)

func TestScopesNotEmpty(t *testing.T) {
	if len(Scopes) != 4 {
		t.Errorf("expected 4 scopes, got %d", len(Scopes))
	}
}

func TestSupportedExtensions(t *testing.T) {
	expected := []string{
		".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic", ".heif",
		".bmp", ".tiff", ".tif", ".avif", ".ico",
		".raw", ".raf", ".cr2", ".cr3", ".nef", ".arw", ".dng",
		".orf", ".rw2", ".pef", ".srw",
		".mp4", ".mov", ".avi", ".mkv", ".m4v", ".3gp", ".wmv", ".mpg",
	}
	for _, ext := range expected {
		if !SupportedExtensions[ext] {
			t.Errorf("expected extension %s to be supported", ext)
		}
	}
	if SupportedExtensions[".txt"] {
		t.Error("expected .txt to not be supported")
	}
}

func TestAPIBase(t *testing.T) {
	if APIBase != "https://photoslibrary.googleapis.com/v1" {
		t.Errorf("unexpected API base: %s", APIBase)
	}
}

func TestMaxFileSize(t *testing.T) {
	if MaxFileSize != 200*1024*1024 {
		t.Errorf("unexpected max file size: %d", MaxFileSize)
	}
}
