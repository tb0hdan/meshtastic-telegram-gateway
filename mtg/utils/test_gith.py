# -*- coding: utf-8 -*-
# pylint: skip-file
import pytest
from unittest.mock import patch, MagicMock, Mock, sys
import sys


@pytest.fixture
def mock_token():
    """Set up test token"""
    return "fake_github_token"


@pytest.fixture
def github_mock():
    """Set up github module mock"""
    github_mock = MagicMock()
    sys.modules['github'] = github_mock
    yield github_mock
    # Clean up after tests
    if 'github' in sys.modules:
        del sys.modules['github']
    if 'mtg.utils.gith' in sys.modules:
        del sys.modules['mtg.utils.gith']

def test_get_firmware_info_success(mock_token, github_mock):
    """Test successful firmware info retrieval"""
    # Import after mocking
    from mtg.utils.gith import get_firmware_info

    # Setup mock objects
    mock_github_instance = MagicMock()
    mock_repo = MagicMock()
    mock_release = MagicMock()
    mock_asset = MagicMock()

    # Configure the mocks
    github_mock.Github.return_value = mock_github_instance
    mock_github_instance.get_repo.return_value = mock_repo

    # Mock release data
    mock_release.title = "Meshtastic Firmware v2.1.0"
    mock_release.tag_name = "v2.1.0"
    mock_release.created_at = "2024-01-01T00:00:00Z"
    mock_release.html_url = "https://github.com/meshtastic/firmware/releases/tag/v2.1.0"

    # Mock asset data
    mock_asset.name = "firmware-esp32.bin"
    mock_asset.browser_download_url = "https://github.com/meshtastic/firmware/releases/download/v2.1.0/firmware-esp32.bin"

    mock_release.get_assets.return_value = [mock_asset]
    mock_repo.get_releases.return_value = [mock_release]

    # Call the function
    result = get_firmware_info(mock_token)

    # Assertions
    github_mock.Github.assert_called_once_with(mock_token)
    mock_github_instance.get_repo.assert_called_once_with('meshtastic/firmware')

    assert len(result) == 1
    assert result[0]['tag_name'] == "v2.1.0"
    assert result[0]['html_url'] == "https://github.com/meshtastic/firmware/releases/tag/v2.1.0"
    assert result[0]['download_url'] == "https://github.com/meshtastic/firmware/releases/download/v2.1.0/firmware-esp32.bin"
    assert result[0]['created_at'] == "2024-01-01T00:00:00Z"

def test_get_firmware_info_filters_invalid_title(mock_token, github_mock):
    """Test that releases with invalid titles are filtered out"""
    from mtg.utils.gith import get_firmware_info

    mock_github_instance = MagicMock()
    mock_repo = MagicMock()
    mock_release = MagicMock()

    github_mock.Github.return_value = mock_github_instance
    mock_github_instance.get_repo.return_value = mock_repo

    # Release with invalid title (doesn't start with "Meshtastic Firmware")
    mock_release.title = "Invalid Release Title"
    mock_release.tag_name = "v2.1.0"

    mock_repo.get_releases.return_value = [mock_release]

    result = get_firmware_info(mock_token)

    assert len(result) == 0

def test_get_firmware_info_filters_non_v2_tags(mock_token, github_mock):
    """Test that non-v2 releases are filtered out"""
    from mtg.utils.gith import get_firmware_info

    mock_github_instance = MagicMock()
    mock_repo = MagicMock()
    mock_release = MagicMock()

    github_mock.Github.return_value = mock_github_instance
    mock_github_instance.get_repo.return_value = mock_repo

    # Release with v1 tag
    mock_release.title = "Meshtastic Firmware v1.0.0"
    mock_release.tag_name = "v1.0.0"

    mock_repo.get_releases.return_value = [mock_release]

    result = get_firmware_info(mock_token)

    assert len(result) == 0

def test_get_firmware_info_filters_revoked_releases(mock_token, github_mock):
    """Test that revoked releases are filtered out"""
    from mtg.utils.gith import get_firmware_info

    mock_github_instance = MagicMock()
    mock_repo = MagicMock()
    mock_release = MagicMock()

    github_mock.Github.return_value = mock_github_instance
    mock_github_instance.get_repo.return_value = mock_repo

    # Release with "Revoked" in title
    mock_release.title = "Meshtastic Firmware v2.1.0 - Revoked"
    mock_release.tag_name = "v2.1.0"

    mock_repo.get_releases.return_value = [mock_release]

    result = get_firmware_info(mock_token)

    assert len(result) == 0

def test_get_firmware_info_filters_non_firmware_assets(mock_token, github_mock):
    """Test that non-firmware assets are filtered out"""
    from mtg.utils.gith import get_firmware_info

    mock_github_instance = MagicMock()
    mock_repo = MagicMock()
    mock_release = MagicMock()
    mock_asset = MagicMock()

    github_mock.Github.return_value = mock_github_instance
    mock_github_instance.get_repo.return_value = mock_repo

    mock_release.title = "Meshtastic Firmware v2.1.0"
    mock_release.tag_name = "v2.1.0"

    # Asset that doesn't start with "firmware"
    mock_asset.name = "documentation.pdf"
    mock_asset.browser_download_url = "https://example.com/doc.pdf"

    mock_release.get_assets.return_value = [mock_asset]
    mock_repo.get_releases.return_value = [mock_release]

    result = get_firmware_info(mock_token)

    assert len(result) == 0

def test_get_firmware_info_multiple_assets(mock_token, github_mock):
    """Test handling multiple firmware assets in a release"""
    from mtg.utils.gith import get_firmware_info

    mock_github_instance = MagicMock()
    mock_repo = MagicMock()
    mock_release = MagicMock()
    mock_asset1 = MagicMock()
    mock_asset2 = MagicMock()

    github_mock.Github.return_value = mock_github_instance
    mock_github_instance.get_repo.return_value = mock_repo

    mock_release.title = "Meshtastic Firmware v2.1.0"
    mock_release.tag_name = "v2.1.0"
    mock_release.created_at = "2024-01-01T00:00:00Z"
    mock_release.html_url = "https://github.com/meshtastic/firmware/releases/tag/v2.1.0"

    # Multiple firmware assets
    mock_asset1.name = "firmware-esp32.bin"
    mock_asset1.browser_download_url = "https://example.com/firmware-esp32.bin"
    mock_asset2.name = "firmware-nrf52.bin"
    mock_asset2.browser_download_url = "https://example.com/firmware-nrf52.bin"

    mock_release.get_assets.return_value = [mock_asset1, mock_asset2]
    mock_repo.get_releases.return_value = [mock_release]

    result = get_firmware_info(mock_token)

    # Should return one entry per firmware asset
    assert len(result) == 2
    assert result[0]['download_url'] == "https://example.com/firmware-esp32.bin"
    assert result[1]['download_url'] == "https://example.com/firmware-nrf52.bin"

def test_get_firmware_info_empty_releases(mock_token, github_mock):
    """Test handling when no releases are found"""
    from mtg.utils.gith import get_firmware_info

    mock_github_instance = MagicMock()
    mock_repo = MagicMock()

    github_mock.Github.return_value = mock_github_instance
    mock_github_instance.get_repo.return_value = mock_repo
    mock_repo.get_releases.return_value = []

    result = get_firmware_info(mock_token)

    assert len(result) == 0

def test_get_firmware_info_github_exception(mock_token, github_mock):
    """Test handling GitHub API exceptions"""
    from mtg.utils.gith import get_firmware_info

    github_mock.Github.side_effect = Exception("GitHub API error")

    with pytest.raises(Exception) as exc_info:
        get_firmware_info(mock_token)

    assert "GitHub API error" in str(exc_info.value)