# -*- coding: utf-8 -*-
# pylint: skip-file
import pytest
from unittest.mock import patch, MagicMock
from mtg.utils.exc import log_exception
import sys
import traceback


@pytest.fixture
def mock_logger():
    """Set up test fixtures"""
    return MagicMock()

@patch('mtg.utils.exc.sys.exc_info')
@patch('mtg.utils.exc.traceback.format_exception')
def test_log_exception_with_description(mock_format_exception, mock_exc_info, mock_logger):
    """Test logging exception with description"""
    # Setup mock data
    test_exception = ValueError("test error")
    test_description = "Test error occurred"
    mock_exc_type = ValueError
    mock_exc_value = test_exception
    mock_exc_tb = MagicMock()

    mock_exc_info.return_value = (mock_exc_type, mock_exc_value, mock_exc_tb)
    mock_format_exception.return_value = ['Traceback line 1\n', 'Traceback line 2\n']

    # Call the function
    log_exception(mock_logger, test_exception, test_description)

    # Assertions
    mock_exc_info.assert_called_once()
    mock_format_exception.assert_called_once_with(mock_exc_type, mock_exc_value, mock_exc_tb)
    mock_logger.error.assert_called_once_with(
        test_description,
        test_exception,
        'Traceback line 1\nTraceback line 2\n'
    )

@patch('mtg.utils.exc.sys.exc_info')
@patch('mtg.utils.exc.traceback.format_exception')
def test_log_exception_without_description(mock_format_exception, mock_exc_info, mock_logger):
        """Test logging exception without description"""
        # Setup mock data
        test_exception = RuntimeError("runtime error")
        mock_exc_type = RuntimeError
        mock_exc_value = test_exception
        mock_exc_tb = MagicMock()

        mock_exc_info.return_value = (mock_exc_type, mock_exc_value, mock_exc_tb)
        mock_format_exception.return_value = ['Error traceback\n']

        # Call the function with empty description
        log_exception(mock_logger, test_exception)

        # Assertions
        mock_exc_info.assert_called_once()
        mock_format_exception.assert_called_once_with(mock_exc_type, mock_exc_value, mock_exc_tb)
        mock_logger.error.assert_called_once_with(
            '',  # Empty description
            test_exception,
            'Error traceback\n'
        )

@patch('mtg.utils.exc.sys.exc_info')
@patch('mtg.utils.exc.traceback.format_exception')
def test_log_exception_none_exception(mock_format_exception, mock_exc_info, mock_logger):
        """Test logging with None exception"""
        mock_exc_info.return_value = (None, None, None)
        mock_format_exception.return_value = ['No traceback available\n']

        log_exception(mock_logger, None, "No exception")

        mock_exc_info.assert_called_once()
        mock_format_exception.assert_called_once_with(None, None, None)
        mock_logger.error.assert_called_once_with(
            "No exception",
            None,
            'No traceback available\n'
        )

@patch('mtg.utils.exc.sys.exc_info')
@patch('mtg.utils.exc.traceback.format_exception')
def test_log_exception_custom_exception_class(mock_format_exception, mock_exc_info, mock_logger):
        """Test logging with custom exception class"""
        class CustomException(Exception):
            pass

        test_exception = CustomException("custom error")
        mock_exc_type = CustomException
        mock_exc_value = test_exception
        mock_exc_tb = MagicMock()

        mock_exc_info.return_value = (mock_exc_type, mock_exc_value, mock_exc_tb)
        mock_format_exception.return_value = ['Custom exception traceback\n']

        log_exception(mock_logger, test_exception, "Custom exception occurred")

        mock_exc_info.assert_called_once()
        mock_format_exception.assert_called_once_with(mock_exc_type, mock_exc_value, mock_exc_tb)
        mock_logger.error.assert_called_once_with(
            "Custom exception occurred",
            test_exception,
            'Custom exception traceback\n'
        )

@patch('mtg.utils.exc.sys.exc_info')
@patch('mtg.utils.exc.traceback.format_exception')
def test_log_exception_multiline_traceback(mock_format_exception, mock_exc_info, mock_logger):
        """Test logging exception with multiline traceback"""
        test_exception = IndexError("list index out of range")
        mock_exc_type = IndexError
        mock_exc_value = test_exception
        mock_exc_tb = MagicMock()

        mock_exc_info.return_value = (mock_exc_type, mock_exc_value, mock_exc_tb)
        mock_format_exception.return_value = [
            'Traceback (most recent call last):\n',
            '  File "test.py", line 10, in <module>\n',
            '    print(my_list[5])\n',
            'IndexError: list index out of range\n'
        ]

        log_exception(mock_logger, test_exception, "Index error")

        expected_traceback = (
            'Traceback (most recent call last):\n'
            '  File "test.py", line 10, in <module>\n'
            '    print(my_list[5])\n'
            'IndexError: list index out of range\n'
        )

        mock_logger.error.assert_called_once_with(
            "Index error",
            test_exception,
            expected_traceback
        )

@patch('mtg.utils.exc.sys.exc_info')
@patch('mtg.utils.exc.traceback.format_exception')
def test_log_exception_empty_traceback(mock_format_exception, mock_exc_info, mock_logger):
        """Test logging exception with empty traceback"""
        test_exception = KeyError("missing key")
        mock_exc_type = KeyError
        mock_exc_value = test_exception
        mock_exc_tb = MagicMock()

        mock_exc_info.return_value = (mock_exc_type, mock_exc_value, mock_exc_tb)
        mock_format_exception.return_value = []  # Empty traceback

        log_exception(mock_logger, test_exception, "Key error")

        mock_logger.error.assert_called_once_with(
            "Key error",
            test_exception,
            ''  # Empty string from empty list
        )

def test_log_exception_logger_called_correctly(mock_logger):
        """Test that logger.error is called with correct number of arguments"""
        with patch('mtg.utils.exc.sys.exc_info') as mock_exc_info, \
             patch('mtg.utils.exc.traceback.format_exception') as mock_format_exception:

            mock_exc_info.return_value = (Exception, Exception("test"), MagicMock())
            mock_format_exception.return_value = ['traceback\n']

            log_exception(mock_logger, Exception("test"), "description")

            # Verify logger.error was called with exactly 3 arguments
            args, kwargs = mock_logger.error.call_args
            assert len(args) == 3
            assert args[0] == "description"
            assert isinstance(args[1], Exception)
            assert args[2] == "traceback\n"