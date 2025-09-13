# -*- coding: utf-8 -*-
# pylint: skip-file
import pytest
from unittest.mock import MagicMock
from mtg.utils.message import split_message


@pytest.fixture
def mock_callback():
    """Set up test fixtures"""
    return MagicMock()

def test_split_message_short_message(mock_callback):
    """Test splitting a message shorter than chunk_len"""
    message = "Short message"
    chunk_len = 100

    split_message(message, chunk_len, mock_callback)

    mock_callback.assert_called_once_with("Short message")

def test_split_message_empty_message(mock_callback):
    """Test splitting an empty message"""
    message = ""
    chunk_len = 100

    split_message(message, chunk_len, mock_callback)

    mock_callback.assert_not_called()

def test_split_message_multiline_short(mock_callback):
    """Test splitting a multiline message that fits in one chunk"""
    message = "Line 1\nLine 2\nLine 3"
    chunk_len = 100

    split_message(message, chunk_len, mock_callback)

    mock_callback.assert_called_once_with("Line 1\nLine 2\nLine 3")

def test_split_message_multiline_needs_splitting(mock_callback):
    """Test splitting a multiline message that needs to be split"""
    message = "Line 1\nLine 2\nLine 3\nLine 4\nLine 5"
    chunk_len = 15  # Will force splitting

    split_message(message, chunk_len, mock_callback)

    # Should be called multiple times
    assert mock_callback.call_count > 1

def test_split_message_with_kwargs(mock_callback):
    """Test split_message passes kwargs to callback"""
    message = "Test message"
    chunk_len = 100
    test_kwarg = "test_value"

    split_message(message, chunk_len, mock_callback, extra_param=test_kwarg)

    mock_callback.assert_called_once_with("Test message", extra_param=test_kwarg)

def test_split_message_empty_lines(mock_callback):
    """Test split_message handles empty lines correctly"""
    message = "Line 1\n\nLine 3\n\n"
    chunk_len = 100

    split_message(message, chunk_len, mock_callback)

    # Empty lines should be filtered out
    mock_callback.assert_called_once_with("Line 1\nLine 3")

def test_split_message_very_long_line(mock_callback):
    """Test splitting when a single line exceeds chunk_len"""
    long_line = "a" * 150
    chunk_len = 50

    split_message(long_line, chunk_len, mock_callback)

    # Should be called multiple times for the long line
    # Implementation adds 1 to handle remainder: (150 // 50) + 1 = 4 calls
    assert mock_callback.call_count == 4

    # Check that each call has the right chunk size or less
    for call in mock_callback.call_args_list:
        chunk = call[0][0]
        assert len(chunk) <= chunk_len

def test_split_message_exact_chunk_boundary(mock_callback):
    """Test splitting when message length equals chunk_len"""
    message = "a" * 50
    chunk_len = 50

    split_message(message, chunk_len, mock_callback)

    # The implementation will call twice: once with the message, once with empty string
    assert mock_callback.call_count == 2
    # First call should be with the full message
    mock_callback.assert_any_call(message)

def test_split_message_mixed_line_lengths(mock_callback):
    """Test splitting with mixed line lengths"""
    short_line = "short"
    long_line = "a" * 80
    message = f"{short_line}\n{long_line}\n{short_line}"
    chunk_len = 20

    split_message(message, chunk_len, mock_callback)

    # Should handle the mix appropriately
    assert mock_callback.call_count > 1

def test_split_message_callback_not_called_for_empty_parts(mock_callback):
    """Test that callback is not called for empty parts"""
    message = "\n\n\n"  # Only empty lines
    chunk_len = 100

    split_message(message, chunk_len, mock_callback)

    mock_callback.assert_not_called()