import sys
from unittest.mock import patch, MagicMock

from auth import authenticate


class TestAuthenticate:
    def test_valid_cached_token(self, tmp_path):
        token_path = str(tmp_path / "token.json")
        creds_path = str(tmp_path / "credentials.json")

        mock_creds = MagicMock()
        mock_creds.valid = True

        with patch("auth.os.path.exists", return_value=True):
            with patch("auth.Credentials.from_authorized_user_file", return_value=mock_creds):
                result = authenticate(creds_path, token_path)

        assert result is mock_creds

    def test_expired_token_refreshes(self, tmp_path):
        token_path = str(tmp_path / "token.json")
        creds_path = str(tmp_path / "credentials.json")

        mock_creds = MagicMock()
        mock_creds.valid = False
        mock_creds.expired = True
        mock_creds.refresh_token = "refresh_tok"
        mock_creds.to_json.return_value = '{"token": "new"}'

        with patch("auth.os.path.exists", return_value=True):
            with patch("auth.Credentials.from_authorized_user_file", return_value=mock_creds):
                with patch("builtins.open", MagicMock()):
                    result = authenticate(creds_path, token_path)

        mock_creds.refresh.assert_called_once()
        assert result is mock_creds

    def test_missing_credentials_exits(self, tmp_path):
        token_path = str(tmp_path / "token.json")
        creds_path = str(tmp_path / "credentials.json")

        with patch("auth.os.path.exists", return_value=False):
            try:
                authenticate(creds_path, token_path)
                assert False, "Should have called sys.exit"
            except SystemExit as e:
                assert e.code == 1

    def test_new_auth_flow_when_no_token(self, tmp_path):
        token_path = str(tmp_path / "token.json")
        creds_path = str(tmp_path / "credentials.json")

        mock_creds = MagicMock()
        mock_creds.to_json.return_value = '{"token": "fresh"}'

        mock_flow = MagicMock()
        mock_flow.run_local_server.return_value = mock_creds

        def exists_side_effect(path):
            if path == token_path:
                return False
            return True  # credentials.json exists

        with patch("auth.os.path.exists", side_effect=exists_side_effect):
            with patch("auth.InstalledAppFlow.from_client_secrets_file", return_value=mock_flow):
                with patch("builtins.open", MagicMock()):
                    result = authenticate(creds_path, token_path)

        mock_flow.run_local_server.assert_called_once_with(port=0)
        assert result is mock_creds
