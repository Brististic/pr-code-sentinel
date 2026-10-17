import os

os.environ.setdefault("GEMINI_API_KEY", "test-key")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")

from app.main import Settings, missing_env_message


def test_no_error_when_gemini_key_present():
    assert missing_env_message(Settings(gemini_api_key="abc")) is None


def test_error_names_the_key_and_where_to_set_it():
    message = missing_env_message(Settings(gemini_api_key=""))
    assert message is not None
    assert "GEMINI_API_KEY" in message
    assert "environment variable" in message
    assert "$env:" in message  # tells users PowerShell syntax is not accepted


def test_error_mentions_secret_file_caveat():
    message = missing_env_message(Settings(gemini_api_key=""))
    assert "Secret File" in message