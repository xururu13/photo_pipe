package main

import (
	"bufio"
	"fmt"
	"os"
	"path/filepath"
	"time"
)

type UploadResult struct {
	Added   int
	Skipped int
}

func ProcessFolder(
	client *GooglePhotosClient,
	folder string,
	existingAlbums map[string]string,
	uploadedLog map[string]bool,
	skipExisting bool,
	dryRun bool,
	canReadLibrary bool,
	stdinReader *bufio.Reader,
) (UploadResult, error) {
	albumName := filepath.Base(folder)
	files, err := FindMediaFiles(folder)
	if err != nil {
		return UploadResult{}, err
	}

	if len(files) == 0 {
		return UploadResult{}, nil
	}

	// Calculate total size
	var totalSize int64
	for _, f := range files {
		if info, err := os.Stat(f); err == nil {
			totalSize += info.Size()
		}
	}

	// Filter already uploaded
	skipped := 0
	if skipExisting {
		var filtered []string
		for _, f := range files {
			absPath, _ := filepath.Abs(f)
			if uploadedLog[absPath] {
				skipped++
			} else {
				filtered = append(filtered, f)
			}
		}
		files = filtered
	}

	// Print folder header
	fmt.Printf("\n  📁 %s\n", albumName)
	skippedStr := ""
	if skipped > 0 {
		skippedStr = fmt.Sprintf(" (пропущено %d ранее загруженных)", skipped)
	}
	fmt.Printf("     %d файлов (%s)%s\n", len(files), FormatSize(totalSize), skippedStr)

	if len(files) == 0 {
		return UploadResult{Skipped: skipped}, nil
	}

	// Dry run mode
	if dryRun {
		for _, f := range files {
			info, _ := os.Stat(f)
			size := int64(0)
			if info != nil {
				size = info.Size()
			}
			fmt.Printf("     → %s (%s)\n", filepath.Base(f), FormatSize(size))
		}
		return UploadResult{Skipped: skipped}, nil
	}

	// Get or create album
	albumID, err := client.GetOrCreateAlbum(albumName, existingAlbums)
	if err != nil {
		return UploadResult{Skipped: skipped}, fmt.Errorf("album error: %w", err)
	}

	// Check remote items for duplicates
	var remoteItems map[string]RemoteItemInfo
	if canReadLibrary {
		remoteItems, err = client.ListAlbumItems(albumID)
		if err != nil {
			return UploadResult{Skipped: skipped}, fmt.Errorf("list items error: %w", err)
		}
		if len(remoteItems) > 0 {
			fmt.Printf("     📋 В альбоме уже %d файлов\n", len(remoteItems))
		}
	}

	type uploadEntry struct {
		token   string
		absPath string
	}

	var uploads []uploadEntry
	total := len(files)

	for idx, fpath := range files {
		displayName := filepath.Base(fpath)
		realPath := fpath
		uploadName := ""

		// Check for remote duplicates
		if remoteItems != nil {
			if remote, exists := remoteItems[displayName]; exists {
				choice := PromptDuplicate(fpath, remote, stdinReader)
				switch choice {
				case "s":
					skipped++
					continue
				case "r":
					if err := client.RemoveFromAlbum(albumID, []string{remote.ID}); err != nil {
						fmt.Printf("       ⚠️  Не удалось удалить: %v\n", err)
					} else {
						fmt.Println("       ✓ Старый файл удалён из альбома")
					}
				case "n":
					fmt.Print("       Новое имя: ")
					line, _ := stdinReader.ReadString('\n')
					newName := trimNewline(line)
					if newName == "" {
						skipped++
						continue
					}
					uploadName = newName
					displayName = newName
				}
			}
		}

		fmt.Printf("     ⬆️  [%d/%d] %s", idx+1, total, displayName)

		token, err := client.UploadFile(realPath, uploadName)
		if err != nil {
			fmt.Println(" ✗")
			fmt.Printf("  %v\n", err)
			continue
		}
		fmt.Println(" ✓")

		absPath, _ := filepath.Abs(realPath)
		uploads = append(uploads, uploadEntry{token: token, absPath: absPath})

		// Rate limiting: 2s sleep every 20 files
		if (idx+1)%20 == 0 && idx+1 < total {
			time.Sleep(2 * time.Second)
		}
	}

	if len(uploads) == 0 {
		fmt.Println("     ⚠️  Ни один файл не загружен")
		return UploadResult{Skipped: skipped}, nil
	}

	// Add to album
	tokens := make([]string, len(uploads))
	for i, u := range uploads {
		tokens[i] = u.token
	}

	fmt.Printf("     📎 Добавляю %d файлов в альбом...", len(tokens))

	successIndices, err := client.AddToAlbum(tokens, albumID)

	// If album ID is stale (404), create a new album and retry
	if err != nil && len(successIndices) == 0 {
		fmt.Println()
		fmt.Printf("     🔄 Альбом не найден, создаю заново...")
		delete(existingAlbums, albumName)
		newID, createErr := client.CreateAlbum(albumName)
		if createErr != nil {
			fmt.Println(" ✗")
			return UploadResult{Skipped: skipped}, fmt.Errorf("recreate album error: %w", createErr)
		}
		existingAlbums[albumName] = newID
		albumID = newID
		fmt.Println(" ✓")
		fmt.Printf("     📎 Добавляю %d файлов в альбом...", len(tokens))
		successIndices, err = client.AddToAlbum(tokens, albumID)
	}

	if err != nil {
		fmt.Println(" ✗")
		return UploadResult{Skipped: skipped}, fmt.Errorf("add to album error: %w", err)
	}

	fmt.Printf(" ✓ (%d добавлено)\n", len(successIndices))

	// Update uploaded log with successfully added files
	for idx := range successIndices {
		uploadedLog[uploads[idx].absPath] = true
	}

	return UploadResult{Added: len(successIndices), Skipped: skipped}, nil
}

func trimNewline(s string) string {
	for len(s) > 0 && (s[len(s)-1] == '\n' || s[len(s)-1] == '\r') {
		s = s[:len(s)-1]
	}
	return s
}
