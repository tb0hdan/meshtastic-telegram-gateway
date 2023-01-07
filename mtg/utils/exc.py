import sys
import traceback

def log_exception(logger, exc: Any, description: str = '') -> None:
    """
    Log exception, including traceback
    :param exc:
    :return:
    """
    exc_type, exc_value, exc_tb = sys.exc_info()
    logger.error(description, exc, ''.join(traceback.format_exception(exc_type, exc_value, exc_tb)))
