"""Keep tests away from a user's private API settings file."""
import pytest


@pytest.fixture(autouse=True)
def isolated_settings(tmp_path, monkeypatch):
    monkeypatch.setenv('SDA_SETTINGS_DIR', str(tmp_path/'private-settings'))
    monkeypatch.setenv('SDA_MAINTENANCE_DIR', str(tmp_path/'maintenance'))
