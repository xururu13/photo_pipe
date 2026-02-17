package main

var Scopes = []string{
	"https://www.googleapis.com/auth/photoslibrary",
	"https://www.googleapis.com/auth/photoslibrary.readonly",
	"https://www.googleapis.com/auth/photoslibrary.appendonly",
	"https://www.googleapis.com/auth/photoslibrary.sharing",
}

const APIBase = "https://photoslibrary.googleapis.com/v1"

var SupportedExtensions = map[string]bool{
	// Images
	".jpg": true, ".jpeg": true, ".png": true, ".gif": true, ".webp": true,
	".heic": true, ".heif": true, ".bmp": true, ".tiff": true, ".tif": true,
	".avif": true, ".ico": true,
	// RAW
	".raw": true, ".raf": true, ".cr2": true, ".cr3": true, ".nef": true,
	".arw": true, ".dng": true, ".orf": true, ".rw2": true, ".pef": true,
	".srw": true,
	// Video
	".mp4": true, ".mov": true, ".avi": true, ".mkv": true, ".m4v": true,
	".3gp": true, ".wmv": true, ".mpg": true,
}

const UploadLog = ".gphotos_uploaded.json"
const MaxFileSize = 200 * 1024 * 1024 // 200 MB
