# -*- coding: utf-8 -*-
""" message utilities """


import textwrap
import unicodedata


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


def is_emoji_reaction(text: str) -> bool:
    """Return True if the provided text looks like a standalone emoji reaction."""

    if text is None:
        return False
    candidate = text.strip()
    if not candidate or len(candidate) > 8:
        return False
    has_emoji = False
    for char in candidate:
        if char in ('\u200d', '\ufe0f'):
            continue
        category = unicodedata.category(char)
        if category.startswith('S') or category in ('Mn', 'Cf'):
            has_emoji = True
            continue
        return False
    return has_emoji


def first_emoji_codepoint(text: str):
    """Return the integer codepoint of the first emoji-like character in text."""

    if text is None:
        return None
    for char in text.strip():
        if char in ('\u200d', '\ufe0f'):
            continue
        category = unicodedata.category(char)
        if category.startswith('S') or category in ('Mn', 'Cf'):
            return ord(char)
        break
    return None
