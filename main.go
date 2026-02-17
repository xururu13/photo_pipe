package main

import (
	"bufio"
	"flag"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"
)

func main() {
	dryRun := flag.Bool("dry-run", false, "Показать план без загрузки")
	skipExisting := flag.Bool("skip-existing", true, "Пропускать ранее загруженные файлы")
	credPath := flag.String("credentials", "credentials.json", "Путь к OAuth credentials")
	tokenPath := flag.String("token", "token.json", "Путь к файлу токена")
	flag.Usage = func() {
		fmt.Fprintf(os.Stderr, "Использование: %s [опции] <папка-экспорта>\n\n", os.Args[0])
		fmt.Fprintf(os.Stderr, "Загружает фото и видео из подпапок в Google Photos.\n")
		fmt.Fprintf(os.Stderr, "Каждая подпапка становится отдельным альбомом.\n\n")
		fmt.Fprintf(os.Stderr, "Опции:\n")
		flag.PrintDefaults()
	}
	flag.Parse()

	if flag.NArg() < 1 {
		flag.Usage()
		os.Exit(1)
	}

	exportDir := flag.Arg(0)

	info, err := os.Stat(exportDir)
	if err != nil || !info.IsDir() {
		fmt.Printf("❌ Папка не найдена: %s\n", exportDir)
		os.Exit(1)
	}

	// Find subfolders (non-hidden, sorted)
	entries, err := os.ReadDir(exportDir)
	if err != nil {
		fmt.Printf("❌ Не удалось прочитать папку: %v\n", err)
		os.Exit(1)
	}

	var subfolders []string
	for _, e := range entries {
		if e.IsDir() && !strings.HasPrefix(e.Name(), ".") {
			subfolders = append(subfolders, filepath.Join(exportDir, e.Name()))
		}
	}
	sort.Strings(subfolders)

	if len(subfolders) == 0 {
		fmt.Println("❌ Подпапки не найдены")
		os.Exit(1)
	}

	// Pre-count files and sizes
	totalFiles := 0
	var totalSize int64
	for _, folder := range subfolders {
		files, _ := FindMediaFiles(folder)
		for _, f := range files {
			totalFiles++
			if s, err := os.Stat(f); err == nil {
				totalSize += s.Size()
			}
		}
	}

	// Print banner
	fmt.Println()
	fmt.Println("📸 Google Photos Auto-Uploader")
	fmt.Println()
	fmt.Printf("📂 Источник:  %s\n", exportDir)
	fmt.Printf("📁 Альбомов:  %d\n", len(subfolders))
	fmt.Printf("🖼️  Файлов:    %d\n", totalFiles)
	fmt.Printf("💾 Размер:    %s\n", FormatSize(totalSize))
	if *dryRun {
		fmt.Println("🔍 Режим:     DRY RUN (без загрузки)")
	}
	fmt.Println()

	var existingAlbums map[string]string
	canReadLibrary := true
	stdinReader := bufio.NewReader(os.Stdin)

	if !*dryRun {
		// Authenticate
		httpClient, err := Authenticate(*credPath, *tokenPath)
		if err != nil {
			fmt.Printf("❌ Ошибка авторизации: %v\n", err)
			os.Exit(1)
		}

		client := NewGooglePhotosClient(httpClient)

		// List existing albums
		fmt.Println("📋 Загружаю список существующих альбомов...")
		existingAlbums, err = client.ListAlbums()
		if err != nil {
			if strings.Contains(err.Error(), "403") {
				fmt.Println("  ⚠️  Нет доступа к списку альбомов, продолжаю без проверки")
				canReadLibrary = false
				existingAlbums = make(map[string]string)
			} else {
				fmt.Printf("❌ Ошибка получения альбомов: %v\n", err)
				os.Exit(1)
			}
		}

		// Load upload log
		uploadedLog, cachedAlbums, err := LoadUploadLog(exportDir)
		if err != nil {
			fmt.Printf("⚠️  Ошибка чтения лога: %v\n", err)
			uploadedLog = make(map[string]bool)
			cachedAlbums = make(map[string]string)
		}

		// Merge cached albums if we can't read library
		if !canReadLibrary && len(cachedAlbums) > 0 {
			fmt.Printf("📝 Из кеша загружено %d альбомов\n", len(cachedAlbums))
			for k, v := range cachedAlbums {
				if _, exists := existingAlbums[k]; !exists {
					existingAlbums[k] = v
				}
			}
		}

		if len(uploadedLog) > 0 {
			fmt.Printf("📝 В логе %d ранее загруженных файлов\n", len(uploadedLog))
		}

		// Process folders
		totalAdded := 0
		totalSkipped := 0

		for _, folder := range subfolders {
			result, err := ProcessFolder(
				client, folder, existingAlbums, uploadedLog,
				*skipExisting, false, canReadLibrary, stdinReader,
			)
			if err != nil {
				fmt.Printf("  ⚠️  Ошибка: %v\n", err)
			}
			totalAdded += result.Added
			totalSkipped += result.Skipped
		}

		// Save upload log
		if err := SaveUploadLog(exportDir, uploadedLog, existingAlbums); err != nil {
			fmt.Printf("⚠️  Не удалось сохранить лог: %v\n", err)
		}

		// Print summary
		fmt.Println()
		fmt.Println("📊 Итоги:")
		fmt.Printf("   ✅ Загружено:  %d файлов\n", totalAdded)
		fmt.Printf("   ⏭️  Пропущено: %d файлов\n", totalSkipped)
	} else {
		// Dry run mode
		uploadedLog, _, err := LoadUploadLog(exportDir)
		if err != nil {
			uploadedLog = make(map[string]bool)
		}

		totalSkipped := 0
		for _, folder := range subfolders {
			result, _ := ProcessFolder(
				nil, folder, nil, uploadedLog,
				*skipExisting, true, false, nil,
			)
			totalSkipped += result.Skipped
		}

		fmt.Println()
		fmt.Println("📊 Итоги (DRY RUN):")
		fmt.Printf("   ⏭️  Пропущено: %d файлов\n", totalSkipped)
	}
}
