package main

import (
	"context"
	"encoding/json"
	"fmt"
	"net"
	"net/http"
	"os"
	"os/exec"
	"runtime"
	"sync"
	"time"

	"golang.org/x/oauth2"
	"golang.org/x/oauth2/google"
)

// pythonToken matches the JSON format written by Python's google-auth library
type pythonToken struct {
	Token        string   `json:"token"`
	RefreshToken string   `json:"refresh_token"`
	TokenURI     string   `json:"token_uri"`
	ClientID     string   `json:"client_id"`
	ClientSecret string   `json:"client_secret"`
	Scopes       []string `json:"scopes"`
	Expiry       string   `json:"expiry"`
}

// credentialsFile matches Google's credentials.json format
type credentialsFile struct {
	Installed struct {
		ClientID     string   `json:"client_id"`
		ClientSecret string   `json:"client_secret"`
		AuthURI      string   `json:"auth_uri"`
		TokenURI     string   `json:"token_uri"`
		RedirectURIs []string `json:"redirect_uris"`
	} `json:"installed"`
}

func loadCredentials(credPath string) (*oauth2.Config, error) {
	data, err := os.ReadFile(credPath)
	if err != nil {
		return nil, fmt.Errorf("❌ Файл %s не найден!\n   Скачайте OAuth credentials из Google Cloud Console", credPath)
	}

	var creds credentialsFile
	if err := json.Unmarshal(data, &creds); err != nil {
		return nil, fmt.Errorf("failed to parse credentials: %w", err)
	}

	return &oauth2.Config{
		ClientID:     creds.Installed.ClientID,
		ClientSecret: creds.Installed.ClientSecret,
		Endpoint:     google.Endpoint,
		Scopes:       Scopes,
		RedirectURL:  "http://localhost",
	}, nil
}

func loadToken(tokenPath string) (*oauth2.Token, error) {
	data, err := os.ReadFile(tokenPath)
	if err != nil {
		return nil, err
	}

	// Try Go oauth2 format first
	var tok oauth2.Token
	if err := json.Unmarshal(data, &tok); err == nil && tok.RefreshToken != "" {
		return &tok, nil
	}

	// Try Python format
	var pyTok pythonToken
	if err := json.Unmarshal(data, &pyTok); err != nil {
		return nil, fmt.Errorf("failed to parse token: %w", err)
	}

	goTok := &oauth2.Token{
		AccessToken:  pyTok.Token,
		RefreshToken: pyTok.RefreshToken,
		TokenType:    "Bearer",
	}

	if pyTok.Expiry != "" {
		if t, err := time.Parse(time.RFC3339, pyTok.Expiry); err == nil {
			goTok.Expiry = t
		}
	}

	return goTok, nil
}

func saveToken(tokenPath string, tok *oauth2.Token) error {
	data, err := json.MarshalIndent(tok, "", "  ")
	if err != nil {
		return err
	}
	data = append(data, '\n')
	return os.WriteFile(tokenPath, data, 0600)
}

// persistingTokenSource wraps a TokenSource and saves refreshed tokens to disk
type persistingTokenSource struct {
	src       oauth2.TokenSource
	tokenPath string
	mu        sync.Mutex
	lastToken *oauth2.Token
}

func newPersistingTokenSource(src oauth2.TokenSource, tokenPath string, initial *oauth2.Token) *persistingTokenSource {
	return &persistingTokenSource{
		src:       src,
		tokenPath: tokenPath,
		lastToken: initial,
	}
}

func (p *persistingTokenSource) Token() (*oauth2.Token, error) {
	p.mu.Lock()
	defer p.mu.Unlock()

	tok, err := p.src.Token()
	if err != nil {
		return nil, err
	}

	if p.lastToken == nil || tok.AccessToken != p.lastToken.AccessToken {
		fmt.Println("🔄 Обновляю токен...")
		if err := saveToken(p.tokenPath, tok); err != nil {
			fmt.Printf("  ⚠️  Не удалось сохранить токен: %v\n", err)
		}
		p.lastToken = tok
	}

	return tok, nil
}

func openBrowser(url string) error {
	var cmd *exec.Cmd
	switch runtime.GOOS {
	case "darwin":
		cmd = exec.Command("open", url)
	case "linux":
		cmd = exec.Command("xdg-open", url)
	case "windows":
		cmd = exec.Command("rundll32", "url.dll,FileProtocolHandler", url)
	default:
		return fmt.Errorf("unsupported platform")
	}
	return cmd.Start()
}

func authorizeBrowser(config *oauth2.Config) (*oauth2.Token, error) {
	fmt.Println("🌐 Открываю браузер для авторизации...")

	listener, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		return nil, fmt.Errorf("failed to start local server: %w", err)
	}
	port := listener.Addr().(*net.TCPAddr).Port
	config.RedirectURL = fmt.Sprintf("http://localhost:%d", port)

	codeCh := make(chan string, 1)
	errCh := make(chan error, 1)

	mux := http.NewServeMux()
	mux.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		code := r.URL.Query().Get("code")
		if code == "" {
			errCh <- fmt.Errorf("no code in callback")
			fmt.Fprint(w, "Ошибка авторизации")
			return
		}
		codeCh <- code
		fmt.Fprint(w, "✅ Авторизация успешна! Можно закрыть окно.")
	})

	server := &http.Server{Handler: mux}
	go server.Serve(listener)

	authURL := config.AuthCodeURL("state", oauth2.AccessTypeOffline, oauth2.SetAuthURLParam("prompt", "consent"))
	if err := openBrowser(authURL); err != nil {
		fmt.Printf("Откройте ссылку вручную:\n%s\n", authURL)
	}

	var code string
	select {
	case code = <-codeCh:
	case err := <-errCh:
		server.Close()
		return nil, err
	case <-time.After(5 * time.Minute):
		server.Close()
		return nil, fmt.Errorf("authorization timeout")
	}

	server.Close()

	tok, err := config.Exchange(context.Background(), code)
	if err != nil {
		return nil, fmt.Errorf("token exchange failed: %w", err)
	}

	return tok, nil
}

func Authenticate(credPath, tokenPath string) (*http.Client, error) {
	config, err := loadCredentials(credPath)
	if err != nil {
		return nil, err
	}

	tok, err := loadToken(tokenPath)
	if err != nil || tok.RefreshToken == "" {
		// Need new authorization
		tok, err = authorizeBrowser(config)
		if err != nil {
			return nil, err
		}
		if err := saveToken(tokenPath, tok); err != nil {
			return nil, fmt.Errorf("failed to save token: %w", err)
		}
		fmt.Println("✅ Авторизация успешна, токен сохранён.")
	}

	pts := newPersistingTokenSource(
		config.TokenSource(context.Background(), tok),
		tokenPath,
		tok,
	)

	return oauth2.NewClient(context.Background(), pts), nil
}
