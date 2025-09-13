# -*- coding: utf-8 -*-
""" message utilities """

from typing import Any, Callable, List


def split_message(msg: str, chunk_len: int, callback: Callable[..., Any], **kwargs: Any) -> None:
    """
    split_message - split message into smaller parts and invoke callback on each one

    :return:
    """
    # split into parts
    parts: List[List[str]] = []
    part: List[str] = []
    for line in msg.split('\n'):
        if len(line) == 0:
            continue
        if len('\n'.join(part) + line) < chunk_len:
            part.append(line)
        else:
            parts.append(part)
            part = [line]

    parts.append(part)

    for part in parts:
        if len(part) == 0:
            continue
        line = '\n'.join(part)
        if len(line) < chunk_len:
            callback(line, **kwargs)
        else:
            for i in range((len(line) // chunk_len) + 1):
                callback(line[i*chunk_len:i*chunk_len + chunk_len], **kwargs)
