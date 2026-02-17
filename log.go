package main

import (
	"encoding/json"
	"os"
	"path/filepath"
	"sort"
)

type uploadLogData struct {
	Uploaded []string          `json:"uploaded"`
	Albums   map[string]string `json:"albums"`
}

func LoadUploadLog(exportDir string) (map[string]bool, map[string]string, error) {
	logPath := filepath.Join(exportDir, UploadLog)
	data, err := os.ReadFile(logPath)
	if err != nil {
		if os.IsNotExist(err) {
			return make(map[string]bool), make(map[string]string), nil
		}
		return nil, nil, err
	}

	var logData uploadLogData
	if err := json.Unmarshal(data, &logData); err != nil {
		return nil, nil, err
	}

	uploaded := make(map[string]bool, len(logData.Uploaded))
	for _, path := range logData.Uploaded {
		uploaded[path] = true
	}

	albums := logData.Albums
	if albums == nil {
		albums = make(map[string]string)
	}
	return uploaded, albums, nil
}

func SaveUploadLog(exportDir string, uploaded map[string]bool, albums map[string]string) error {
	logPath := filepath.Join(exportDir, UploadLog)

	paths := make([]string, 0, len(uploaded))
	for p := range uploaded {
		paths = append(paths, p)
	}
	sort.Strings(paths)

	logData := uploadLogData{
		Uploaded: paths,
		Albums:   albums,
	}

	data, err := json.MarshalIndent(logData, "", "  ")
	if err != nil {
		return err
	}
	data = append(data, '\n')
	return os.WriteFile(logPath, data, 0644)
}
