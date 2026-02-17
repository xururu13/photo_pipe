package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"time"
)

type GooglePhotosClient struct {
	httpClient *http.Client
	baseURL    string
}

func NewGooglePhotosClient(httpClient *http.Client) *GooglePhotosClient {
	return &GooglePhotosClient{
		httpClient: httpClient,
		baseURL:    APIBase,
	}
}

// ListAlbums returns a map of album title -> album ID
func (c *GooglePhotosClient) ListAlbums() (map[string]string, error) {
	albums := make(map[string]string)
	pageToken := ""

	for {
		url := c.baseURL + "/albums?pageSize=50"
		if pageToken != "" {
			url += "&pageToken=" + pageToken
		}

		resp, err := c.httpClient.Get(url)
		if err != nil {
			return nil, fmt.Errorf("list albums request failed: %w", err)
		}
		defer resp.Body.Close()

		if resp.StatusCode != http.StatusOK {
			body, _ := io.ReadAll(resp.Body)
			return nil, fmt.Errorf("list albums failed: %d %s", resp.StatusCode, string(body))
		}

		var result struct {
			Albums []struct {
				ID    string `json:"id"`
				Title string `json:"title"`
			} `json:"albums"`
			NextPageToken string `json:"nextPageToken"`
		}

		if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
			return nil, fmt.Errorf("failed to decode albums: %w", err)
		}

		for _, a := range result.Albums {
			albums[a.Title] = a.ID
		}

		if result.NextPageToken == "" {
			break
		}
		pageToken = result.NextPageToken
	}

	return albums, nil
}

// CreateAlbum creates a new album and returns its ID
func (c *GooglePhotosClient) CreateAlbum(title string) (string, error) {
	body := map[string]interface{}{
		"album": map[string]string{"title": title},
	}
	data, _ := json.Marshal(body)

	resp, err := c.httpClient.Post(c.baseURL+"/albums", "application/json", bytes.NewReader(data))
	if err != nil {
		return "", fmt.Errorf("create album request failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		respBody, _ := io.ReadAll(resp.Body)
		return "", fmt.Errorf("create album failed: %d %s", resp.StatusCode, string(respBody))
	}

	var result struct {
		ID string `json:"id"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return "", fmt.Errorf("failed to decode album response: %w", err)
	}

	return result.ID, nil
}

// GetOrCreateAlbum returns album ID, creating if needed. Updates existingAlbums in-place.
func (c *GooglePhotosClient) GetOrCreateAlbum(title string, existingAlbums map[string]string) (string, error) {
	if id, ok := existingAlbums[title]; ok {
		return id, nil
	}
	id, err := c.CreateAlbum(title)
	if err != nil {
		return "", err
	}
	existingAlbums[title] = id
	return id, nil
}

// UploadFile uploads a file and returns the upload token
func (c *GooglePhotosClient) UploadFile(fpath string, filenameOverride string) (string, error) {
	f, err := os.Open(fpath)
	if err != nil {
		return "", fmt.Errorf("failed to open file: %w", err)
	}
	defer f.Close()

	filename := filenameOverride
	if filename == "" {
		filename = filepath.Base(fpath)
	}

	req, err := http.NewRequest("POST", c.baseURL+"/uploads", f)
	if err != nil {
		return "", fmt.Errorf("failed to create upload request: %w", err)
	}

	req.Header.Set("Content-Type", "application/octet-stream")
	req.Header.Set("X-Goog-Upload-File-Name", filename)
	req.Header.Set("X-Goog-Upload-Protocol", "raw")

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return "", fmt.Errorf("upload request failed: %w", err)
	}
	defer resp.Body.Close()

	body, _ := io.ReadAll(resp.Body)

	if resp.StatusCode != http.StatusOK {
		return "", fmt.Errorf("  ⚠️  Ошибка загрузки %s: %d %s", filename, resp.StatusCode, string(body))
	}

	return string(body), nil
}

// AddToAlbum adds uploaded items to an album in batches of 50.
// Returns the set of successfully added indices (0-based).
func (c *GooglePhotosClient) AddToAlbum(uploadTokens []string, albumID string) (map[int]bool, error) {
	successIndices := make(map[int]bool)
	batchSize := 50

	for batchStart := 0; batchStart < len(uploadTokens); batchStart += batchSize {
		batchEnd := batchStart + batchSize
		if batchEnd > len(uploadTokens) {
			batchEnd = len(uploadTokens)
		}
		batch := uploadTokens[batchStart:batchEnd]

		items := make([]map[string]interface{}, len(batch))
		for i, token := range batch {
			items[i] = map[string]interface{}{
				"simpleMediaItem": map[string]string{"uploadToken": token},
			}
		}

		body := map[string]interface{}{
			"albumId":       albumID,
			"newMediaItems": items,
		}
		data, _ := json.Marshal(body)

		resp, err := c.httpClient.Post(
			c.baseURL+"/mediaItems:batchCreate",
			"application/json",
			bytes.NewReader(data),
		)
		if err != nil {
			fmt.Printf("  ⚠️  Ошибка batchCreate: %v\n", err)
			continue
		}

		var result struct {
			NewMediaItemResults []struct {
				Status struct {
					Code    int    `json:"code"`
					Message string `json:"message"`
				} `json:"status"`
			} `json:"newMediaItemResults"`
		}

		respBody, _ := io.ReadAll(resp.Body)
		resp.Body.Close()

		if resp.StatusCode != http.StatusOK {
			return successIndices, fmt.Errorf("batchCreate failed: %d %s", resp.StatusCode, string(respBody))
		}

		if err := json.Unmarshal(respBody, &result); err != nil {
			fmt.Printf("  ⚠️  Ошибка декодирования batchCreate: %v\n", err)
			continue
		}

		for i, item := range result.NewMediaItemResults {
			if item.Status.Message == "Success" || item.Status.Message == "OK" || item.Status.Code == 0 {
				successIndices[batchStart+i] = true
			} else {
				fmt.Printf("  ⚠️  Элемент не добавлен: %v\n", item.Status)
			}
		}

		// Sleep between batches (not after the last one)
		if batchEnd < len(uploadTokens) {
			time.Sleep(1 * time.Second)
		}
	}

	return successIndices, nil
}

// ListAlbumItems returns remote items in an album keyed by filename
func (c *GooglePhotosClient) ListAlbumItems(albumID string) (map[string]RemoteItemInfo, error) {
	items := make(map[string]RemoteItemInfo)
	pageToken := ""

	for {
		body := map[string]interface{}{
			"albumId":  albumID,
			"pageSize": 100,
		}
		if pageToken != "" {
			body["pageToken"] = pageToken
		}
		data, _ := json.Marshal(body)

		resp, err := c.httpClient.Post(
			c.baseURL+"/mediaItems:search",
			"application/json",
			bytes.NewReader(data),
		)
		if err != nil {
			return nil, fmt.Errorf("search request failed: %w", err)
		}

		var result struct {
			MediaItems []struct {
				ID            string `json:"id"`
				Filename      string `json:"filename"`
				MediaMetadata struct {
					CreationTime string `json:"creationTime"`
					Width        string `json:"width"`
					Height       string `json:"height"`
				} `json:"mediaMetadata"`
			} `json:"mediaItems"`
			NextPageToken string `json:"nextPageToken"`
		}

		respBody, _ := io.ReadAll(resp.Body)
		resp.Body.Close()

		if resp.StatusCode != http.StatusOK {
			return nil, fmt.Errorf("search failed: %d %s", resp.StatusCode, string(respBody))
		}

		if err := json.Unmarshal(respBody, &result); err != nil {
			return nil, fmt.Errorf("failed to decode search response: %w", err)
		}

		for _, item := range result.MediaItems {
			items[item.Filename] = RemoteItemInfo{
				ID:           item.ID,
				CreationTime: item.MediaMetadata.CreationTime,
				Width:        item.MediaMetadata.Width,
				Height:       item.MediaMetadata.Height,
			}
		}

		if result.NextPageToken == "" {
			break
		}
		pageToken = result.NextPageToken
	}

	return items, nil
}

// RemoveFromAlbum removes media items from an album
func (c *GooglePhotosClient) RemoveFromAlbum(albumID string, mediaItemIDs []string) error {
	body := map[string]interface{}{
		"mediaItemIds": mediaItemIDs,
	}
	data, _ := json.Marshal(body)

	resp, err := c.httpClient.Post(
		c.baseURL+"/albums/"+albumID+":batchRemoveMediaItems",
		"application/json",
		bytes.NewReader(data),
	)
	if err != nil {
		return fmt.Errorf("remove from album request failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		respBody, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("remove from album failed: %d %s", resp.StatusCode, string(respBody))
	}

	return nil
}
