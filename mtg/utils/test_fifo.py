# -*- coding: utf-8 -*-
# pylint: skip-file
import pytest
from unittest.mock import patch, MagicMock
from mtg.utils.fifo import create_fifo
import errno
import os
@patch('mtg.utils.fifo.os.mkfifo')
def test_create_fifo_success(mock_mkfifo):
    """Test successful FIFO creation"""
    test_path = "/tmp/test_fifo"

    create_fifo(test_path)

    mock_mkfifo.assert_called_once_with(test_path)

@patch('mtg.utils.fifo.os.mkfifo')
def test_create_fifo_already_exists(mock_mkfifo):
    """Test FIFO creation when file already exists"""
    test_path = "/tmp/test_fifo"

    # Mock OSError with EEXIST errno
    error = OSError("File exists")
    error.errno = errno.EEXIST
    mock_mkfifo.side_effect = error

    # Should not raise an exception
    create_fifo(test_path)

    mock_mkfifo.assert_called_once_with(test_path)

@patch('mtg.utils.fifo.os.mkfifo')
def test_create_fifo_permission_denied(mock_mkfifo):
    """Test FIFO creation with permission denied"""
    test_path = "/tmp/test_fifo"

    # Mock OSError with EACCES errno (permission denied)
    error = OSError("Permission denied")
    error.errno = errno.EACCES
    mock_mkfifo.side_effect = error

    # Should raise the exception
    with pytest.raises(OSError) as exc_info:
        create_fifo(test_path)

    assert exc_info.value.errno == errno.EACCES
    mock_mkfifo.assert_called_once_with(test_path)

@patch('mtg.utils.fifo.os.mkfifo')
def test_create_fifo_no_space_left(mock_mkfifo):
    """Test FIFO creation with no space left on device"""
    test_path = "/tmp/test_fifo"

    # Mock OSError with ENOSPC errno (no space left)
    error = OSError("No space left on device")
    error.errno = errno.ENOSPC
    mock_mkfifo.side_effect = error

    # Should raise the exception
    with pytest.raises(OSError) as exc_info:
        create_fifo(test_path)

    assert exc_info.value.errno == errno.ENOSPC
    mock_mkfifo.assert_called_once_with(test_path)

@patch('mtg.utils.fifo.os.mkfifo')
def test_create_fifo_invalid_path(mock_mkfifo):
    """Test FIFO creation with invalid path"""
    test_path = "/invalid/path/test_fifo"

    # Mock OSError with ENOENT errno (no such file or directory)
    error = OSError("No such file or directory")
    error.errno = errno.ENOENT
    mock_mkfifo.side_effect = error

    # Should raise the exception
    with pytest.raises(OSError) as exc_info:
        create_fifo(test_path)

    assert exc_info.value.errno == errno.ENOENT
    mock_mkfifo.assert_called_once_with(test_path)

def test_create_fifo_empty_path():
    """Test FIFO creation with empty path"""
    with patch('mtg.utils.fifo.os.mkfifo') as mock_mkfifo:
        create_fifo("")
        mock_mkfifo.assert_called_once_with("")

def test_create_fifo_relative_path():
    """Test FIFO creation with relative path"""
    test_path = "relative/path/fifo"

    with patch('mtg.utils.fifo.os.mkfifo') as mock_mkfifo:
        create_fifo(test_path)
        mock_mkfifo.assert_called_once_with(test_path)

@patch('mtg.utils.fifo.os.mkfifo')
def test_create_fifo_unicode_path(mock_mkfifo):
    """Test FIFO creation with unicode characters in path"""
    test_path = "/tmp/тест_фифо"  # Cyrillic characters

    create_fifo(test_path)

    mock_mkfifo.assert_called_once_with(test_path)