# -*- coding: utf-8 -*-
""" message utilities """


import textwrap


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


def split_user_message(sender: str, msg: str, chunk_len: int):
    """Split user's message into chunks with sender prefix and counters"""

    prefix = f"{sender}: "
    # initial assumption about parts
    parts_count = 1
    while True:
        counter = f"[{parts_count}/{parts_count}] "
        available = chunk_len - len(prefix) - len(counter)
        wrapper = textwrap.TextWrapper(
            width=available,
            break_long_words=False,
            break_on_hyphens=False,
            replace_whitespace=False,
        )
        parts = [p.strip() for p in wrapper.wrap(msg) if p.strip()]
        if len(parts) == parts_count:
            break
        parts_count = len(parts)

    return [f"{prefix}[{idx}/{parts_count}] {part}" for idx, part in enumerate(parts, start=1)]
