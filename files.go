package main

import (
	"bufio"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"time"

	"github.com/rwcarlsen/goexif/exif"
)

type LocalFileInfo struct {
	Filename string
	Size     int64
	Date     time.Time
	Width    int
	Height   int
}

type RemoteItemInfo struct {
	ID           string
	CreationTime string
	Width        string
	Height       string
}

func FindMediaFiles(folder string) ([]string, error) {
	entries, err := os.ReadDir(folder)
	if err != nil {
		return nil, err
	}

	var files []string
	for _, e := range entries {
		if e.IsDir() {
			continue
		}
		ext := strings.ToLower(filepath.Ext(e.Name()))
		if SupportedExtensions[ext] {
			files = append(files, filepath.Join(folder, e.Name()))
		}
	}
	sort.Strings(files)
	return files, nil
}

func FormatSize(sizeBytes int64) string {
	switch {
	case sizeBytes < 1024:
		return fmt.Sprintf("%d B", sizeBytes)
	case sizeBytes < 1024*1024:
		return fmt.Sprintf("%.1f KB", float64(sizeBytes)/1024)
	case sizeBytes < 1024*1024*1024:
		return fmt.Sprintf("%.1f MB", float64(sizeBytes)/(1024*1024))
	default:
		return fmt.Sprintf("%.2f GB", float64(sizeBytes)/(1024*1024*1024))
	}
}

func GetLocalFileInfo(fpath string) LocalFileInfo {
	info := LocalFileInfo{
		Filename: filepath.Base(fpath),
	}

	stat, err := os.Stat(fpath)
	if err != nil {
		return info
	}
	info.Size = stat.Size()
	info.Date = stat.ModTime()

	f, err := os.Open(fpath)
	if err != nil {
		return info
	}
	defer f.Close()

	x, err := exif.Decode(f)
	if err == nil {
		if dt, err := x.DateTime(); err == nil {
			info.Date = dt
		}
		if w, err := x.Get(exif.PixelXDimension); err == nil {
			if v, err := w.Int(0); err == nil {
				info.Width = v
			}
		}
		if h, err := x.Get(exif.PixelYDimension); err == nil {
			if v, err := h.Int(0); err == nil {
				info.Height = v
			}
		}
	}

	return info
}

func FormatRemoteDate(creationTime string) string {
	if creationTime == "" {
		return "?"
	}
	s := strings.Replace(creationTime, "Z", "+00:00", 1)
	t, err := time.Parse(time.RFC3339, s)
	if err != nil {
		if len(creationTime) >= 16 {
			return creationTime[:16]
		}
		return creationTime
	}
	return t.Format("2006-01-02 15:04")
}

func PromptDuplicate(fpath string, remote RemoteItemInfo, reader *bufio.Reader) string {
	local := GetLocalFileInfo(fpath)
	filename := filepath.Base(fpath)

	localDate := local.Date.Format("2006-01-02 15:04")
	localSize := fmt.Sprintf("%8s", FormatSize(local.Size))
	localDim := ""
	if local.Width > 0 && local.Height > 0 {
		localDim = fmt.Sprintf("%d×%d", local.Width, local.Height)
	}

	remoteDate := FormatRemoteDate(remote.CreationTime)
	remoteDim := ""
	if remote.Width != "" && remote.Height != "" {
		remoteDim = fmt.Sprintf("%s×%s", remote.Width, remote.Height)
	}

	fmt.Printf("\n  ⚠️  Дубликат найден: %s\n", filename)
	fmt.Printf("       Локальный:  %s  |  %s  |  %s\n", localDate, localSize, localDim)
	fmt.Printf("       Удалённый:  %s  |  %8s  |  %s\n", remoteDate, "—", remoteDim)

	for {
		fmt.Print("       [S]kip / [R]eplace / Re[n]ame? ")
		line, _ := reader.ReadString('\n')
		choice := strings.TrimSpace(strings.ToLower(line))
		switch choice {
		case "s", "r", "n":
			return choice
		default:
			fmt.Println("       Введите s, r или n")
		}
	}
}
