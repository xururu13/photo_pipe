from config import SCOPES, API_BASE, SUPPORTED_EXTENSIONS, UPLOAD_LOG, MAX_FILE_SIZE


def test_scopes_non_empty():
    assert len(SCOPES) > 0


def test_scopes_are_urls():
    for scope in SCOPES:
        assert scope.startswith("https://")


def test_api_base_is_https():
    assert API_BASE.startswith("https://")


def test_extensions_are_lowercase_and_dotted():
    for ext in SUPPORTED_EXTENSIONS:
        assert ext.startswith(".")
        assert ext == ext.lower()


def test_supported_extensions_include_common_formats():
    for ext in (".jpg", ".jpeg", ".png", ".mp4", ".mov"):
        assert ext in SUPPORTED_EXTENSIONS


def test_upload_log_is_json():
    assert UPLOAD_LOG.endswith(".json")


def test_max_file_size_positive():
    assert MAX_FILE_SIZE > 0
    assert MAX_FILE_SIZE == 200 * 1024 * 1024
