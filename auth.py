import os
import sys

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from config import SCOPES


def authenticate(credentials_path: str = "credentials.json",
                 token_path: str = "token.json") -> Credentials:
    """
    OAuth2 аутентификация. При первом запуске откроет браузер.
    Токен сохраняется в token.json для последующих запусков.
    """
    creds = None

    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("🔄 Обновляю токен...")
            creds.refresh(Request())
        else:
            if not os.path.exists(credentials_path):
                print(f"❌ Файл {credentials_path} не найден!")
                print("   Скачай его из Google Cloud Console (см. README).")
                sys.exit(1)

            print("🌐 Открываю браузер для авторизации...")
            flow = InstalledAppFlow.from_client_secrets_file(
                credentials_path, SCOPES
            )
            creds = flow.run_local_server(port=0)

        with open(token_path, "w") as f:
            f.write(creds.to_json())
        print("✅ Авторизация успешна, токен сохранён.")

    return creds
