# -*- coding: utf-8 -*-
""" message utilities """


def split_message(msg, chunk_len, callback, **kwargs) -> None:
    """
    split_message - split message into smaller parts and invoke callback on each one

    :return:
    """
    # split into parts
    parts = []
    part = []
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
